from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from magic_filter import MagicFilter

from .events import BaseEvent, EventType


Filter = Callable[..., Any] | MagicFilter


async def check_filter(flt: Filter, event: BaseEvent) -> bool:
    if isinstance(flt, MagicFilter):
        result = flt.resolve(event)
    else:
        result = flt(event)
    if inspect.isawaitable(result):
        result = await result
    return bool(result)


class Handler:
    """
    Зарегистрированный хендлер события.
    """

    def __init__(self, callback: Callable[..., Awaitable[Any] | Any], filters: tuple[Filter, ...], router: Router):
        self.callback = callback
        self.filters = filters
        self.router = router
        self.name = f"{getattr(callback, '__module__', '?')}.{getattr(callback, '__qualname__', repr(callback))}"

        params = inspect.signature(callback).parameters
        self._accepts_any = any(p.kind is inspect.Parameter.VAR_KEYWORD for p in params.values())
        self._params = [
            p.name for p in params.values()
            if p.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY)
        ]

    async def check(self, event: BaseEvent) -> bool:
        for flt in self.filters:
            if not await check_filter(flt, event):
                return False
        return True

    def arguments(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._accepts_any:
            return dict(data)
        args = {name: data[name] for name in self._params if name in data}
        # первый параметр с незнакомым именем получает само событие: async def handler(msg_event): ...
        if self._params and self._params[0] not in data and "event" not in self._params:
            args[self._params[0]] = data["event"]
        return args

    async def call(self, data: dict[str, Any]) -> Any:
        result = self.callback(**self.arguments(data))
        if inspect.isawaitable(result):
            result = await result
        return result


class Router:
    """
    Роутер событий: хендлеры регистрируются декораторами.

    .. code-block:: python

        router = Router()

        @router.new_message(F.message.text.startswith("!help"))
        async def on_help(event: NewMessageEvent):
            await event.answer("Команды: ...")

    Хендлеры одного события вызываются **все**, по очереди, в порядке регистрации
    (сначала хендлеры роутера, потом вложенных роутеров в порядке подключения).
    Параметры хендлера заполняются по имени: `event`, `client`, `dispatcher`, `router`
    и всё, что положено в диспетчер (`dp["plbot"] = bot` → параметр `plbot`).

    :param name: Имя роутера (для логов), _опционально_.
    :type name: `str` or `None`
    """

    def __init__(self, name: str | None = None):
        self.name = name or f"router_{id(self):x}"
        self.parent: Router | None = None
        self.sub_routers: list[Router] = []
        self.filters: list[Filter] = []
        self.handlers: dict[EventType, list[Handler]] = {t: [] for t in EventType}
        self.error_handlers: list[Handler] = []

    def __repr__(self) -> str:
        return f"<Router {self.name}>"

    def include_router(self, router: Router) -> Router:
        """
        Подключает вложенный роутер.

        :param router: Роутер.
        :type router: `playerokapi.Router`

        :return: Подключённый роутер.
        :rtype: `playerokapi.Router`
        """

        if router is self:
            raise ValueError("Роутер нельзя подключить к самому себе")
        if router.parent is not None:
            raise RuntimeError(f"{router} уже подключён к {router.parent}")
        node = self
        while node is not None:
            if node is router:
                raise RuntimeError(f"Подключение {router} к {self} создаст цикл")
            node = node.parent
        router.parent = self
        self.sub_routers.append(router)
        return router

    def include_routers(self, *routers: Router):
        """
        Подключает несколько вложенных роутеров по порядку.
        """
        for router in routers:
            self.include_router(router)

    def remove_router(self, router: Router):
        """
        Отключает вложенный роутер (можно на лету: события, которые уже обрабатываются, его хендлеры больше не вызовут).

        :param router: Роутер.
        :type router: `playerokapi.Router`
        """

        if router not in self.sub_routers:
            raise ValueError(f"{router} не подключён к {self}")
        self.sub_routers.remove(router)
        router.parent = None

    def filter(self, *filters: Filter) -> Router:
        """
        Добавляет фильтры на весь роутер: если хоть один не пройден, ни хендлеры роутера, ни вложенные роутеры событие не получат.
        """
        self.filters.extend(filters)
        return self

    def on(self, event_type: EventType, *filters: Filter):
        """
        Декоратор хендлера события указанного типа.

        :param event_type: Тип события.
        :type event_type: `playerokapi.dispatcher.EventType`

        :param filters: Фильтры: функции (обычные или async), принимающие событие, или magic-filter `F`.
        """

        event_type = EventType(event_type)

        def decorator(callback):
            self.handlers[event_type].append(Handler(callback, filters, self))
            return callback
        return decorator

    def error(self, *filters: Filter):
        """
        Декоратор хендлера ошибок этого роутера и вложенных в него.
        Хендлер получает параметры по имени, в том числе `exception` и `handler_name`.
        """

        def decorator(callback):
            self.error_handlers.append(Handler(callback, filters, self))
            return callback
        return decorator

    def chat_initialized(self, *filters: Filter):
        """ Декоратор хендлера `ChatInitializedEvent`. """
        return self.on(EventType.CHAT_INITIALIZED, *filters)

    def new_message(self, *filters: Filter):
        """ Декоратор хендлера `NewMessageEvent`. """
        return self.on(EventType.NEW_MESSAGE, *filters)

    def new_deal(self, *filters: Filter):
        """ Декоратор хендлера `NewDealEvent`. """
        return self.on(EventType.NEW_DEAL, *filters)

    def new_review(self, *filters: Filter):
        """ Декоратор хендлера `NewReviewEvent`. """
        return self.on(EventType.NEW_REVIEW, *filters)

    def item_paid(self, *filters: Filter):
        """ Декоратор хендлера `ItemPaidEvent`. """
        return self.on(EventType.ITEM_PAID, *filters)

    def item_sent(self, *filters: Filter):
        """ Декоратор хендлера `ItemSentEvent`. """
        return self.on(EventType.ITEM_SENT, *filters)

    def deal_confirmed(self, *filters: Filter):
        """ Декоратор хендлера `DealConfirmedEvent`. """
        return self.on(EventType.DEAL_CONFIRMED, *filters)

    def deal_rolled_back(self, *filters: Filter):
        """ Декоратор хендлера `DealRolledBackEvent`. """
        return self.on(EventType.DEAL_ROLLED_BACK, *filters)

    def deal_has_problem(self, *filters: Filter):
        """ Декоратор хендлера `DealHasProblemEvent`. """
        return self.on(EventType.DEAL_HAS_PROBLEM, *filters)

    def deal_problem_resolved(self, *filters: Filter):
        """ Декоратор хендлера `DealProblemResolvedEvent`. """
        return self.on(EventType.DEAL_PROBLEM_RESOLVED, *filters)

    def deal_status_changed(self, *filters: Filter):
        """ Декоратор хендлера `DealStatusChangedEvent`. """
        return self.on(EventType.DEAL_STATUS_CHANGED, *filters)
