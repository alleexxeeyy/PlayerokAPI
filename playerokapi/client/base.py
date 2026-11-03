from __future__ import annotations

import asyncio
import mimetypes
import os
from enum import Enum
from logging import getLogger
from typing import Any, TypeVar

from pydantic import TypeAdapter

from .. import _gql
from .._http import Transport, parse_cookies
from ..errors import HTTPError, PlayerokError, UnauthorizedError
from ..models import AccountProfile


logger = getLogger("playerokapi")

T = TypeVar("T")

_adapters: dict[Any, TypeAdapter] = {}


def parse(type_: Any, data: Any) -> Any:
    if data is None:
        return None
    adapter = _adapters.get(type_)
    if adapter is None:
        adapter = _adapters[type_] = TypeAdapter(type_)
    return adapter.validate_python(data)


def value_of(enum_or_str: Any) -> Any:
    if isinstance(enum_or_str, Enum):
        # у енумов 1.x значения числовые, а API ждёт имя
        return enum_or_str.value if isinstance(enum_or_str, str) else enum_or_str.name
    return enum_or_str


def _guess_image(data: bytes) -> tuple[str, str]:
    sig = data[:12]
    if sig[:8] == b"\x89PNG\r\n\x1a\n":
        return "image.png", "image/png"
    if sig[:3] == b"\xff\xd8\xff":
        return "image.jpg", "image/jpeg"
    if sig[:6] in (b"GIF87a", b"GIF89a"):
        return "image.gif", "image/gif"
    if sig[:4] == b"RIFF" and sig[8:12] == b"WEBP":
        return "image.webp", "image/webp"
    return "image.bin", "application/octet-stream"


async def read_image(image: str | os.PathLike | bytes | bytearray) -> tuple[str, str, bytes]:
    if isinstance(image, (bytes, bytearray)):
        data = bytes(image)
        filename, content_type = _guess_image(data)
        return filename, content_type, data
    path = os.fspath(image)
    data = await asyncio.to_thread(_read_file, path)
    filename = os.path.basename(path)
    return filename, mimetypes.guess_type(filename)[0] or _guess_image(data)[1], data


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value is None:
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = {**merged[key], **{k: v for k, v in value.items() if v is not None}}
        else:
            merged[key] = value
    return merged


def _read_file(path: str) -> bytes:
    with open(path, "rb") as f:
        return f.read()


class BaseClient:
    """
    Асинхронный клиент Playerok аккаунта.

    :param token: Токен аккаунта, _опционально_.
    :type token: `str` or `None`

    :param cookies: Куки-данные авторизованного аккаунта (строкой из браузера или словарём). Можно указывать вместо `token`.
        \n Куки защиты DDoS-Guard (`__ddg*`) привязаны к IP и User-Agent, поэтому запросы должны идти с того же IP и с тем же юзер-агентом, под которыми куки получены.
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

    def __init__(
        self,
        token: str | None = None,
        cookies: str | dict[str, str] | None = None,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 15,
        max_concurrent_requests: int = 1
    ):
        jar = {k: v for k, v in parse_cookies(cookies).items() if v} if cookies else {}
        if token and not jar.get("token"):
            jar["token"] = token
        if not jar.get("token"):
            raise TypeError("Нужен token: передайте его параметром token или в cookies")

        self._transport = Transport(
            cookies=jar,
            user_agent=user_agent,
            proxy=proxy,
            timeout=timeout,
            max_concurrent_requests=max_concurrent_requests
        )
        self._refresh_lock: asyncio.Lock | None = None

        self.me: AccountProfile | None = None
        """ Профиль аккаунта. \n\n_Заполняется при входе в `async with` или вызове `refresh()`_ """

    @property
    def id(self) -> str | None:
        """ ID аккаунта. """
        return self.me.id if self.me else None

    @property
    def username(self) -> str | None:
        """ Никнейм аккаунта. """
        return self.me.username if self.me else None

    @property
    def user_agent(self) -> str:
        """ Юзер-агент, с которым идут запросы. """
        return self._transport.user_agent

    @property
    def cookies(self) -> dict[str, str]:
        """ Куки-данные аккаунта. """
        return self._transport.cookies

    async def __aenter__(self):
        try:
            await self.refresh()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def refresh(self) -> AccountProfile:
        """
        Получает/обновляет данные об аккаунте.

        :return: Профиль аккаунта.
        :rtype: `playerokapi.models.AccountProfile`
        """

        data = (await self._execute("viewer")).get("viewer")
        if not isinstance(data, dict):
            raise UnauthorizedError()
        if self.me is None:
            self.me = parse(AccountProfile, data)

        # баланс полностью, статистику и верификацию отдаёт только запрос user
        try:
            user = (await self._execute("user", {"username": data.get("username"), "hasSupportAccess": False})).get("user")
        except PlayerokError as e:
            logger.warning(f"Не удалось получить полный профиль аккаунта, часть полей me будет пустой: {e}")
            user = None
        if isinstance(user, dict) and user.get("__typename") == "User":
            data = _merge(data, user)

        self.me = parse(AccountProfile, data)
        return self.me

    async def close(self):
        """
        Закрывает сетевую сессию клиента.
        """
        self._refresh_lock = None
        await self._transport.close()

    async def download_file(self, url: str) -> bytes:
        """
        Скачивает файл по прямой ссылке.

        :param url: Ссылка на файл.
        :type url: `str`

        :return: Байты файла.
        :rtype: `bytes`
        """

        resp = await self._transport.request("GET", url, headers={"user-agent": self.user_agent}, inspect_body=False)
        if resp.status_code != 200:
            raise HTTPError(url, resp.status_code, resp.text or "")
        return resp.content

    async def _me_id(self) -> str:
        if self.me is None:
            if self._refresh_lock is None:
                self._refresh_lock = asyncio.Lock()
            async with self._refresh_lock:
                if self.me is None:
                    await self.refresh()
        return self.me.id

    async def _execute(self, operation: str, variables: dict[str, Any] | None = None) -> dict[str, Any]:
        return await _gql.execute(self._transport, operation, variables)

    async def _query(self, operation: str, variables: dict[str, Any] | None, key: str, type_: Any) -> Any:
        data = await self._execute(operation, variables)
        if key not in data:
            raise PlayerokError(f"В ответе Playerok на {operation} нет поля {key}")
        return parse(type_, data[key])

    async def _upload(
        self,
        operation: str,
        variables: dict[str, Any],
        files: dict[str, tuple[str, str, bytes]],
        key: str,
        type_: Any
    ) -> Any:
        data = await _gql.upload(self._transport, operation, variables, files)
        if key not in data:
            raise PlayerokError(f"В ответе Playerok на {operation} нет поля {key}")
        return parse(type_, data[key])
