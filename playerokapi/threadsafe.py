from __future__ import annotations

import asyncio
import concurrent.futures
import inspect
from typing import Any

from .client import Client


class ThreadsafeClient:
    """
    Обёртка над `Client` для вызова его методов из обычных (синхронных) потоков.
    Сами запросы выполняются в event loop, в котором живёт клиент, а поток ждёт результат.

    Пример:

    .. code-block:: python

        sync_client = ThreadsafeClient(client, asyncio.get_running_loop())
        threading.Thread(target=lambda: print(sync_client.get_chats().items)).start()

    :param client: Клиент, работающий в event loop `loop`.
    :type client: `playerokapi.Client`

    :param loop: Event loop клиента.
    :type loop: `asyncio.AbstractEventLoop`

    :param timeout: Сколько секунд ждать результат вызова (`None` - без ограничения).
        \n Если время вышло, вызов отменяется, но запрос мог уже уйти: для `send_message`, `request_withdrawal` и других изменяющих методов исход неизвестен.
    :type timeout: `float` or `None`
    """

    def __init__(self, client: Client, loop: asyncio.AbstractEventLoop, timeout: float | None = None):
        self._client = client
        self._loop = loop
        self._timeout = timeout

    @property
    def client(self) -> Client:
        """ Исходный асинхронный клиент. """
        return self._client

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        attr = getattr(self._client, name)
        if not inspect.iscoroutinefunction(attr):
            return attr

        def call(*args, **kwargs):
            return self._run(attr(*args, **kwargs))

        call.__name__ = name
        call.__doc__ = attr.__doc__
        return call

    def _run(self, coro):
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is self._loop:
            coro.close()
            raise RuntimeError(
                "ThreadsafeClient нельзя вызывать из потока event loop клиента — это заблокирует loop. "
                "Здесь используйте сам Client через await"
            )
        if self._loop.is_closed() or not self._loop.is_running():
            coro.close()
            raise RuntimeError("Event loop клиента не запущен или уже закрыт")

        try:
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        except RuntimeError:
            coro.close()
            raise
        try:
            return future.result(self._timeout)
        except concurrent.futures.TimeoutError:
            if future.done():
                raise
            future.cancel()
            raise TimeoutError(f"Вызов не завершился за {self._timeout} сек.") from None
