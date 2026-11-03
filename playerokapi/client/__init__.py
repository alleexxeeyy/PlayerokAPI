from .base import BaseClient
from .chats import ChatsMixin
from .deals import DealsMixin
from .finance import FinanceMixin
from .games import GamesMixin
from .items import ItemsMixin
from .users import UsersMixin


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
    """


__all__ = ["Client"]
