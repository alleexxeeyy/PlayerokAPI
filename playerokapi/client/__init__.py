from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING

from .base import BaseClient
from .chats import ChatsMixin
from .deals import DealsMixin
from .finance import FinanceMixin
from .games import GamesMixin
from .items import ItemsMixin
from .users import UsersMixin

if TYPE_CHECKING:
    from ..dispatcher.events import BaseEvent


class Client(ChatsMixin, DealsMixin, ItemsMixin, GamesMixin, FinanceMixin, UsersMixin, BaseClient):
    """
    Асинхронный клиент Playerok аккаунта.

    Пример:

    .. code-block:: python

        async with Client(cookies="token=...; __ddg1_=...", user_agent="...") as client:
            print(client.me.username, client.me.balance.available)
            chats = await client.get_chats()

    :param token: Токен аккаунта, _опционально_.
    :type token: `str` or `None`

    :param cookies: Куки-данные авторизованного аккаунта (строкой из браузера или словарём). Можно указывать вместо `token`.
    :type cookies: `str` or `dict[str, str]` or `None`

    :param user_agent: Юзер-агент браузера, _опционально_.
    :type user_agent: `str` or `None`

    :param proxy: IPV4 прокси в формате: `user:pass@ip:port` или `ip:port`, _опционально_.
    :type proxy: `str` or `None`

    :param timeout: Таймаут ожидания ответов на запросы (в секундах).
    :type timeout: `int` or `float`

    :param max_concurrent_requests: Сколько запросов можно отправлять одновременно (по умолчанию по одному, как в 1.x).
    :type max_concurrent_requests: `int`

    :param request_gate: Общий лимит запросов с другими клиентами этого аккаунта (тогда `max_concurrent_requests` берётся из него), _опционально_.
    :type request_gate: `playerokapi.RequestGate` or `None`
    """

    def listen(self, new_messages: bool = True, new_reviews: bool = True) -> AsyncIterator[BaseEvent]:
        """
        Слушает события Playerok (низкоуровневый способ, без роутеров):

        .. code-block:: python

            async for event in client.listen():
                if isinstance(event, NewMessageEvent):
                    ...

        :param new_messages: Получать ли события сообщений, сделок и их статусов.
        :type new_messages: `bool`

        :param new_reviews: Получать ли события новых отзывов.
        :type new_reviews: `bool`

        :return: Асинхронный итератор событий.
        :rtype: `AsyncIterator[playerokapi.dispatcher.events.BaseEvent]`
        """

        from ..dispatcher.source import EventSource
        return EventSource(self, new_messages, new_reviews).listen()


__all__ = ["Client"]
