from __future__ import annotations

import asyncio
import traceback
from logging import getLogger
from typing import TYPE_CHECKING, Any, Literal

from .events import BaseEvent
from .router import Handler, Router, check_filter
from .source import EventSource

if TYPE_CHECKING:
    from ..client import Client


logger = getLogger("playerokapi.dispatcher")

RESERVED = frozenset({"event", "client", "dispatcher", "router", "exception", "handler_name"})


def _cancelled_from_outside() -> bool:
    task = asyncio.current_task()
    return task is not None and task.cancelling() > 0


class Dispatcher(Router):
    """
    Диспетчер: получает события Playerok и передаёт их хендлерам роутеров.
    Сам тоже роутер — на нём можно регистрировать хендлеры напрямую.

    .. code-block:: python

        async with Client(cookies="...") as client:
            dp = Dispatcher(client)
            dp["plbot"] = bot
            dp.include_router(router)
            await dp.run()

    :param client: Клиент Playerok.
    :type client: `playerokapi.Client`

    :param mode: Режим обработки событий: `sequential` — строго по одному (по умолчанию),
        `parallel_chats` — разные чаты параллельно, события одного чата по порядку.
    :type mode: `str`

    :param max_concurrency: Сколько событий обрабатывать одновременно в режиме `parallel_chats` (`None` - без ограничения).
    :type max_concurrency: `int` or `None`

    :param context: Данные для хендлеров: параметр хендлера с таким именем получит значение.
    """

    shutdown_timeout = 10
    """ Сколько секунд при `stop()` ждать хендлеры, которые ещё работают в режиме `parallel_chats`, прежде чем отменить их. """
    __iter__ = None

    def __init__(
        self,
        client: Client,
        mode: Literal["sequential", "parallel_chats"] = "sequential",
        max_concurrency: int | None = None,
        **context: Any
    ):
        super().__init__(name="dispatcher")
        if mode not in ("sequential", "parallel_chats"):
            raise ValueError(f"Неизвестный режим обработки событий: {mode}")
        if max_concurrency is not None and max_concurrency < 1:
            raise ValueError("max_concurrency должен быть не меньше 1")
        self.client = client
        self.mode = mode
        self.max_concurrency = max_concurrency
        self.context: dict[str, Any] = {}
        for key, value in context.items():
            self[key] = value

        self._source: EventSource | None = None
        self._stop: asyncio.Event | None = None
        self._chains: dict[str | None, asyncio.Task] = {}
        self._pending: set[asyncio.Task] = set()
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def __getitem__(self, key: str) -> Any:
        return self.context[key]

    def __setitem__(self, key: str, value: Any):
        if key in RESERVED:
            raise KeyError(f"Имя {key} занято диспетчером")
        self.context[key] = value

    def __delitem__(self, key: str):
        del self.context[key]

    def __contains__(self, key: str) -> bool:
        return key in self.context

    def get(self, key: str, default: Any = None) -> Any:
        return self.context.get(key, default)

    @property
    def running(self) -> bool:
        """ Запущен ли диспетчер. """
        return self._stop is not None

    def _attached(self, router: Router) -> bool:
        node = router
        while node is not None:
            if node is self:
                return True
            node = node.parent
        return False

    async def feed_event(self, event: BaseEvent):
        """
        Передаёт событие хендлерам (используется `run()`, можно вызывать вручную, например в тестах).

        :param event: Событие.
        :type event: `playerokapi.dispatcher.BaseEvent`
        """

        if event.client is None:
            event.client = self.client
        data = {**self.context, "event": event, "client": self.client, "dispatcher": self}
        await self._propagate(self, event, data)

    async def _propagate(self, router: Router, event: BaseEvent, data: dict[str, Any]):
        if not self._attached(router):
            return
        for flt in router.filters:
            try:
                if not await check_filter(flt, event):
                    return
            except asyncio.CancelledError as e:
                if _cancelled_from_outside():
                    raise
                await self._on_error(router, None, event, data, e)
                return
            except Exception as e:
                await self._on_error(router, None, event, data, e)
                return

        for handler in list(router.handlers.get(event.type, ())):
            if not self._attached(router):
                return
            try:
                if await handler.check(event) and self._attached(router):
                    await handler.call({**data, "router": router})
            except asyncio.CancelledError as e:
                # отменили не нас, а что-то внутри хендлера — это его ошибка, остальные хендлеры работают дальше
                if _cancelled_from_outside():
                    raise
                await self._on_error(router, handler, event, data, e)
            except Exception as e:
                await self._on_error(router, handler, event, data, e)

        for sub in list(router.sub_routers):
            await self._propagate(sub, event, data)

    async def _on_error(self, router: Router, handler: Handler | None, event: BaseEvent, data: dict[str, Any], exc: BaseException):
        name = handler.name if handler else f"фильтр {router}"
        logger.error(
            f"Ошибка в {name} при обработке {event.type}: "
            f"{''.join(traceback.format_exception(exc))}"
        )
        error_data = {**data, "router": router, "exception": exc, "handler_name": name}
        node: Router | None = router
        while node is not None:
            matched = False
            for error_handler in node.error_handlers:
                try:
                    if await error_handler.check(event):
                        matched = True
                        await error_handler.call(error_data)
                except Exception:
                    logger.error(f"Ошибка в обработчике ошибок {error_handler.name}: {traceback.format_exc()}")
            if matched:
                return
            node = node.parent

    def _dispatch_parallel(self, event: BaseEvent):
        key = event.chat.id if getattr(event, "chat", None) is not None and event.chat.id else None
        task = asyncio.ensure_future(self._after(self._chains.get(key), event))
        self._chains[key] = task
        self._pending.add(task)

        def done(t: asyncio.Task, key=key):
            self._pending.discard(t)
            if self._chains.get(key) is t:
                del self._chains[key]
        task.add_done_callback(done)

    async def _after(self, previous: asyncio.Task | None, event: BaseEvent):
        if previous is not None:
            await asyncio.wait({previous})
            if not previous.cancelled():
                previous.exception()
        if self._semaphore is None:
            await self.feed_event(event)
            return
        async with self._semaphore:
            await self.feed_event(event)

    async def run(self, new_messages: bool = True, new_reviews: bool = True):
        """
        Запускает получение событий и работает, пока не вызван `stop()` (или задачу не отменили).

        :param new_messages: Получать ли события сообщений, сделок и их статусов.
        :type new_messages: `bool`

        :param new_reviews: Получать ли события новых отзывов.
        :type new_reviews: `bool`
        """

        if self.running:
            raise RuntimeError("Диспетчер уже запущен")
        self._stop = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        self._semaphore = asyncio.Semaphore(self.max_concurrency) if self.max_concurrency else None
        self._source = EventSource(self.client, new_messages, new_reviews)
        stop_wait = asyncio.ensure_future(self._stop.wait())
        get: asyncio.Future | None = None
        stopped = False
        try:
            await self._source.start()
            while not self._stop.is_set():
                get = asyncio.ensure_future(self._source._queue.get())
                done, _ = await asyncio.wait({get, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
                if get not in done:
                    break
                event = get.result()
                get = None
                if self.mode == "sequential":
                    await self.feed_event(event)
                else:
                    self._dispatch_parallel(event)
            stopped = True
        finally:
            stop_event, self._stop = self._stop, None
            source, self._source = self._source, None
            helpers = [f for f in (get, stop_wait) if f is not None]
            try:
                for f in helpers:
                    f.cancel()
                pending = list(self._pending)
                if stopped and pending:
                    # stop() — даём хендлерам доработать (в том числе тому, кто вызвал stop)
                    await asyncio.wait(pending, timeout=self.shutdown_timeout)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, *helpers, return_exceptions=True)
                self._chains.clear()
            finally:
                if source is not None:
                    await source.close()

    def stop(self):
        """
        Останавливает диспетчер: `run()` завершится после текущего события.
        В режиме `parallel_chats` работающим хендлерам даётся `shutdown_timeout` секунд, потом они отменяются.
        События, которые ещё не начали обрабатываться, отбрасываются. Можно вызывать из любого потока.
        """
        stop_event, loop = self._stop, self._loop
        if stop_event is None:
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if loop is None or running is loop:
            stop_event.set()
        else:
            loop.call_soon_threadsafe(stop_event.set)
