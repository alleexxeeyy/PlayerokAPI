from __future__ import annotations

import asyncio
import atexit
import math
import os
import random
import shutil
import tempfile
import threading
import time
import traceback
from collections import deque
from contextlib import contextmanager
from logging import getLogger
from typing import Iterator, Literal

from curl_cffi import AsyncSession, CurlECode, CurlError, CurlMime, Response
from curl_cffi.requests.exceptions import SessionClosed

from .errors import BotCheckError, NetworkError


logger = getLogger("playerokapi")

BASE_URL = "https://playerok.com"
GRAPHQL_URL = f"{BASE_URL}/graphql"
WS_URL = "wss://ws.playerok.com/graphql"

DEFAULT_USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"

BOT_CHECK_SIGNS = (
    "<title>Just a moment...</title>",
    "window._cf_chl_opt",
    "Enable JavaScript and cookies to continue",
    "Checking your browser before accessing",
    "cf-browser-verification",
    "Cloudflare Ray ID",
)
RATE_LIMIT_STATUSES = {
    429: "Too Many Requests",
    502: "Bad Gateway",
    503: "Service Unavailable",
}
# при этих ошибках запрос точно не дошёл до сервера, поэтому его можно повторить даже для мутаций
NOT_SENT_CODES = {
    int(CurlECode.COULDNT_RESOLVE_PROXY),
    int(CurlECode.COULDNT_RESOLVE_HOST),
    int(CurlECode.COULDNT_CONNECT),
    int(CurlECode.SSL_CONNECT_ERROR),
    int(CurlECode.PROXY),
}
MAX_RETRY_AFTER = 300.0

_sleep = asyncio.sleep
_now = time.monotonic
_cert_path: str | None = None

FilePart = tuple[str, str, str, bytes]


def parse_cookies(
    cookies: str | dict[str, str] | None,
    token: str | None = None,
    ddg5: str | None = None
) -> dict[str, str]:
    if isinstance(cookies, str):
        parsed = {
            name.strip(): value.strip()
            for name, value in (c.split("=", 1) for c in cookies.split(";") if "=" in c)
        }
        if parsed:
            return parsed
    elif cookies:
        return dict(cookies)
    return {"token": token or "", "__ddg5_": ddg5 or ""}


def make_proxy_url(proxy: str | None) -> str | None:
    if not proxy:
        return None
    proxy = proxy.strip()
    if proxy.startswith(("socks5://", "socks5h://", "socks4://")):
        return proxy
    return "http://" + proxy.removeprefix("https://").removeprefix("http://")


def _prepare_cert() -> str:
    global _cert_path
    if _cert_path is None:
        src = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cacert.pem")
        cert_dir = tempfile.mkdtemp(prefix="playerokapi_")
        _cert_path = shutil.copy(src, os.path.join(cert_dir, "cacert.pem"))
        atexit.register(shutil.rmtree, cert_dir, True)
    return _cert_path


def _is_json(resp: Response) -> bool:
    return "json" in (resp.headers.get("content-type") or "")


def _rate_limit_reason(resp: Response, idempotent: bool, inspect_body: bool = True) -> str | None:
    reason = None
    if resp.status_code in RATE_LIMIT_STATUSES:
        reason = RATE_LIMIT_STATUSES[resp.status_code]
    elif inspect_body and not _is_json(resp):
        head = (resp.text or "")[:1200].lower()
        reason = next((s for s in RATE_LIMIT_STATUSES.values() if s.lower() in head), None)
    if reason == RATE_LIMIT_STATUSES[502] and not idempotent:
        return None # мутация могла выполниться до того, как шлюз отвалился
    return reason


def _rate_limit_delay(resp: Response, attempt: int) -> float:
    delay = min(120.0, 5.0 * 2 ** attempt)
    try:
        retry_after = float(resp.headers.get("Retry-After"))
        if math.isfinite(retry_after) and retry_after >= 0:
            delay = min(retry_after, MAX_RETRY_AFTER)
    except (TypeError, ValueError):
        pass
    return delay + random.uniform(0.2, 0.8)


def _is_not_sent(error: Exception) -> bool:
    if isinstance(error, SessionClosed):
        return True
    try: return int(getattr(error, "code", 0) or 0) in NOT_SENT_CODES
    except (TypeError, ValueError): return False


def _build_mime(form: dict[str, str] | None, files: list[FilePart] | None) -> CurlMime:
    mime = CurlMime()
    try:
        for name, value in (form or {}).items():
            mime.addpart(name=name, data=value.encode())
        for name, filename, content_type, data in files or []:
            mime.addpart(name=name, filename=filename, content_type=content_type, data=data)
    except BaseException:
        mime.close()
        raise
    return mime


class _Waiter:
    __slots__ = ("event", "loop", "future", "granted", "cancelled")

    def __init__(self, loop: asyncio.AbstractEventLoop | None = None):
        self.loop = loop
        self.event = None if loop is not None else threading.Event()
        self.future: asyncio.Future | None = None
        self.granted = False
        self.cancelled = False


def _running_loop() -> asyncio.AbstractEventLoop | None:
    try:
        return asyncio.get_running_loop()
    except RuntimeError:
        return None


class RequestGate:
    """
    Общий лимит запросов к Playerok для всех клиентов одного аккаунта — асинхронных (`Client`) и синхронного кода в других потоках.
    Запросы получают место строго по очереди; пока Playerok отвечает 429/502/503 одному из клиентов, ждут все.

    .. code-block:: python

        gate = RequestGate()
        client = Client(cookies="...", request_gate=gate)

        with gate.hold():  # синхронный код в своём потоке
            ...

    Синхронный `hold()` в одном потоке можно вкладывать (место берётся один раз).
    Нельзя вызывать `hold()` из event loop, в котором ждёт ответа запрос этого же шлюза — будет `RuntimeError` вместо зависания.

    :param max_concurrent_requests: Сколько запросов можно отправлять одновременно (на всех).
    :type max_concurrent_requests: `int`

    :param min_interval: Минимальная пауза между выдачами мест под запрос (в секундах).
    :type min_interval: `float`
    """

    def __init__(self, max_concurrent_requests: int = 1, min_interval: float = 0):
        if max_concurrent_requests < 1:
            raise ValueError("max_concurrent_requests должен быть не меньше 1")
        if min_interval < 0:
            raise ValueError("min_interval не может быть отрицательным")
        self.max_concurrent_requests = max_concurrent_requests
        self.min_interval = min_interval
        self._lock = threading.Lock()
        self._waiters: deque[_Waiter] = deque()
        self._active = 0
        self._pause_until = 0.0
        self._next_start = 0.0
        self._sync_holders: dict[int, int] = {}
        self._loop_holders: dict[int, int] = {}

    @property
    def active(self) -> int:
        """ Сколько мест занято сейчас. """
        return self._active

    def _delay(self, now: float) -> float:
        return max(self._pause_until - now, self._next_start - now, 0.0)

    def _take(self, now: float):
        self._active += 1
        self._next_start = now + self.min_interval

    def _free_now(self, now: float) -> bool:
        return not self._waiters and self._active < self.max_concurrent_requests and self._delay(now) == 0

    def _dispatch(self):
        wake: list[_Waiter] = []
        with self._lock:
            now = _now()
            while self._waiters and self._active < self.max_concurrent_requests and self._delay(now) == 0:
                waiter = self._waiters.popleft()
                if waiter.cancelled:
                    continue
                self._take(now)
                waiter.granted = True
                wake.append(waiter)
            if self._waiters and self._active < self.max_concurrent_requests:
                # место есть, но мешает пауза/интервал — первый в очереди сам дождётся и раздаст
                wake.append(self._waiters[0])
        for waiter in wake:
            self._wake(waiter)

    def _wake(self, waiter: _Waiter):
        if waiter.event is not None:
            waiter.event.set()
            return
        try:
            waiter.loop.call_soon_threadsafe(self._resolve, waiter)
        except RuntimeError:
            # loop ожидающего уже закрыт — место ему не понадобится
            with self._lock:
                granted, waiter.cancelled = waiter.granted, True
            if granted:
                self._release_slot()

    @staticmethod
    def _resolve(waiter: _Waiter):
        if waiter.future is not None and not waiter.future.done():
            waiter.future.set_result(None)

    def _release_slot(self):
        with self._lock:
            if self._active > 0:
                self._active -= 1
        self._dispatch()

    def pause(self, seconds: float):
        """
        Ставит все запросы на паузу (например, когда Playerok ответил 429).

        :param seconds: Длительность паузы в секундах.
        :type seconds: `float`
        """
        with self._lock:
            self._pause_until = max(self._pause_until, _now() + max(seconds, 0.0))

    def remaining_pause(self) -> float:
        """ Сколько секунд осталось до конца паузы. """
        return max(self._pause_until - _now(), 0.0)

    def acquire(self):
        """
        Занимает место для запроса (синхронно, блокирует поток). Освобождать — `release()`; удобнее `with gate.hold()`.
        """
        tid = threading.get_ident()
        with self._lock:
            if tid in self._sync_holders:
                self._sync_holders[tid] += 1
                return
            loop = _running_loop()
            if loop is not None and self._loop_holders.get(id(loop)):
                raise RuntimeError(
                    "RequestGate.hold() вызван из event loop, в котором ждёт ответа запрос этого же шлюза — это зависание. "
                    "Здесь используйте асинхронный клиент через await"
                )
            if self._free_now(_now()):
                self._take(_now())
                self._sync_holders[tid] = 1
                return
            waiter = _Waiter()
            self._waiters.append(waiter)
        try:
            while True:
                with self._lock:
                    if waiter.granted:
                        break
                    delay = self._delay(_now())
                    waiter.event.clear()
                waiter.event.wait(delay if delay > 0 else None)
                self._dispatch()
        except BaseException:
            with self._lock:
                granted, waiter.cancelled = waiter.granted, True
            if granted:
                self._release_slot()
            raise
        with self._lock:
            self._sync_holders[tid] = 1

    def release(self):
        """
        Освобождает место, занятое `acquire()` в этом потоке.
        """
        tid = threading.get_ident()
        with self._lock:
            depth = self._sync_holders.get(tid)
            if depth is None:
                return
            if depth > 1:
                self._sync_holders[tid] = depth - 1
                return
            del self._sync_holders[tid]
        self._release_slot()

    @contextmanager
    def hold(self) -> Iterator[None]:
        """
        Контекст-менеджер для синхронного кода: занимает место на время блока.
        """
        self.acquire()
        try:
            yield
        finally:
            self.release()

    async def acquire_async(self):
        """
        Занимает место для запроса, не блокируя event loop. Освобождать — `release_async()`.
        """
        loop = asyncio.get_running_loop()
        with self._lock:
            if self._free_now(_now()):
                self._take(_now())
                self._loop_holders[id(loop)] = self._loop_holders.get(id(loop), 0) + 1
                return
            waiter = _Waiter(loop)
            self._waiters.append(waiter)
        try:
            while True:
                with self._lock:
                    if waiter.granted:
                        break
                    delay = self._delay(_now())
                    waiter.future = loop.create_future()
                if delay > 0:
                    await _sleep(delay)
                else:
                    await waiter.future
                self._dispatch()
        except BaseException:
            with self._lock:
                granted, waiter.cancelled = waiter.granted, True
            if granted:
                self._release_slot()
            raise
        with self._lock:
            self._loop_holders[id(loop)] = self._loop_holders.get(id(loop), 0) + 1

    def release_async(self):
        """
        Освобождает место, занятое `acquire_async()` в текущем event loop.
        """
        loop = _running_loop()
        key = id(loop) if loop is not None else None
        with self._lock:
            if key in self._loop_holders:
                self._loop_holders[key] -= 1
                if self._loop_holders[key] <= 0:
                    del self._loop_holders[key]
        self._release_slot()


class Transport:
    def __init__(
        self,
        cookies: dict[str, str],
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 15,
        max_concurrent_requests: int = 1,
        retries: int = 3,
        rate_limit_retries: int = 6,
        impersonate: str = "chrome",
        request_gate: RequestGate | None = None
    ):
        if min(max_concurrent_requests, retries, rate_limit_retries) < 1:
            raise ValueError("max_concurrent_requests, retries и rate_limit_retries должны быть не меньше 1")

        self.cookies = cookies
        self.user_agent = user_agent or DEFAULT_USER_AGENT
        self.proxy = proxy
        self.timeout = timeout
        self.max_concurrent_requests = max_concurrent_requests
        self.retries = retries
        self.rate_limit_retries = rate_limit_retries
        self.impersonate = impersonate
        self.request_gate = request_gate

        self.proxy_url = make_proxy_url(proxy)
        self.cert_path = _prepare_cert()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._session: AsyncSession | None = None
        self._inflight: dict[int, int] = {}
        self._pause_until = 0.0

    @property
    def cookie_header(self) -> str:
        return "; ".join(f"{k}={v}" for k, v in self.cookies.items())

    def graphql_headers(self, operation: str) -> dict[str, str]:
        return {
            "accept-language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "access-control-allow-headers": "sentry-trace, baggage",
            "apollo-require-preflight": "true",
            "apollographql-client-name": "web",
            "content-type": "application/json",
            "cookie": self.cookie_header,
            "priority": "u=1, i",
            "origin": BASE_URL,
            "referer": f"{BASE_URL}/",
            "sec-ch-ua": '"Chromium";v="146", "Not-A.Brand";v="24", "Google Chrome";v="146"',
            "sec-ch-ua-arch": '"x86"',
            "sec-ch-ua-bitness": '"64"',
            "sec-ch-ua-full-version": '"146.0.7680.180"',
            "sec-ch-ua-full-version-list": '"Chromium";v="146.0.7680.180", "Not-A.Brand";v="24.0.0.0", "Google Chrome";v="146.0.7680.180"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-model": '""',
            "sec-ch-ua-platform": '"Windows"',
            "sec-ch-ua-platform-version": '"19.0.0"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-origin",
            "user-agent": self.user_agent,
            "x-gql-op": operation,
            "x-gql-path": "/",
            "x-timezone-offset": "-240",
            "x-apollo-operation-name": operation,
        }

    def _new_session(self) -> AsyncSession:
        return AsyncSession(
            impersonate=self.impersonate,
            timeout=self.timeout,
            proxy=self.proxy_url,
            verify=self.cert_path
        )

    def _bind_loop(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
            self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        elif self._loop is not loop:
            raise RuntimeError(
                "Клиент Playerok уже работает в другом event loop. "
                "Для вызовов из других потоков используйте playerokapi.threadsafe"
            )
        return self._semaphore

    def _acquire_session(self) -> AsyncSession:
        if self._session is None:
            self._session = self._new_session()
        session = self._session
        self._inflight[id(session)] = self._inflight.get(id(session), 0) + 1
        return session

    async def _release_session(self, session: AsyncSession):
        key = id(session)
        self._inflight[key] -= 1
        if self._inflight[key] > 0:
            return
        del self._inflight[key]
        if session is not self._session:
            await self._close_session(session)

    def _retire_session(self, session: AsyncSession):
        # закроется в _release_session, когда на ней не останется запросов
        if self._session is session:
            self._session = None

    async def _close_session(self, session: AsyncSession):
        try: await session.close()
        except Exception: logger.debug(f"Ошибка при закрытии сессии: {traceback.format_exc()}")

    async def _wait_pause(self):
        delay = self._pause_until - _now()
        if delay > 0:
            await _sleep(delay)

    def _set_pause(self, delay: float):
        if self.request_gate is not None:
            self.request_gate.pause(delay)
        else:
            self._pause_until = max(self._pause_until, _now() + delay)

    async def _send_limited(
        self,
        semaphore: asyncio.Semaphore,
        attempt: int,
        url: str,
        idempotent: bool,
        inspect_body: bool,
        args: tuple
    ) -> tuple[Response, str | None]:
        gate = self.request_gate
        if gate is not None:
            await gate.acquire_async()
            try:
                resp = await self._send(*args)
                return resp, self._check_rate_limit(resp, attempt, url, idempotent, inspect_body)
            finally:
                gate.release_async()
        await self._wait_pause()
        async with semaphore:
            await self._wait_pause()
            resp = await self._send(*args)
            return resp, self._check_rate_limit(resp, attempt, url, idempotent, inspect_body)

    def _check_rate_limit(self, resp: Response, attempt: int, url: str, idempotent: bool, inspect_body: bool) -> str | None:
        # пауза ставится, пока место ещё занято — иначе между ответом 429 и паузой успеет уйти чужой запрос
        reason = _rate_limit_reason(resp, idempotent, inspect_body)
        if reason:
            delay = _rate_limit_delay(resp, attempt)
            self._set_pause(delay)
            if attempt < self.rate_limit_retries - 1:
                logger.debug(f"{url} — {reason}. Пробую отправить запрос снова через {delay:.1f} сек.")
            else:
                logger.debug(f"{url} — {reason}. Попытки закончились, следующие запросы подождут {delay:.1f} сек.")
        return reason

    async def _send(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None,
        params: dict | None,
        json: dict | None,
        form: dict[str, str] | None,
        files: list[FilePart] | None,
        idempotent: bool
    ) -> Response:
        error = ""
        for _ in range(self.retries):
            session = self._acquire_session()
            mime = _build_mime(form, files) if form or files else None
            try:
                return await session.request(
                    method,
                    url,
                    headers=headers,
                    params=params,
                    json=json,
                    multipart=mime,
                    timeout=self.timeout
                )
            except (CurlError, OSError) as e:
                error = str(e).strip() or traceback.format_exc()
                self._retire_session(session)
                if not idempotent and not _is_not_sent(e):
                    raise NetworkError(url, error) from e
                logger.debug(f"Ошибка при отправке запроса: {error}")
                logger.debug("Пересоздаю сессию и отправляю запрос повторно...")
            finally:
                if mime is not None:
                    mime.close()
                await self._release_session(session)
        raise NetworkError(url, error)

    async def request(
        self,
        method: Literal["GET", "POST"],
        url: str,
        headers: dict[str, str] | None = None,
        params: dict | None = None,
        json: dict | None = None,
        form: dict[str, str] | None = None,
        files: list[FilePart] | None = None,
        idempotent: bool = True,
        inspect_body: bool = True
    ) -> Response:
        semaphore = self._bind_loop()
        args = (method, url, headers, params, json, form, files, idempotent)
        for attempt in range(self.rate_limit_retries):
            # пауза общая: пока Playerok ограничивает, не шлём ничего, но и место не держим
            resp, reason = await self._send_limited(semaphore, attempt, url, idempotent, inspect_body, args)
            if not reason:
                break

        if inspect_body and not _is_json(resp) and any(sign in (resp.text or "") for sign in BOT_CHECK_SIGNS):
            raise BotCheckError(url)
        return resp

    async def close(self):
        session, self._session = self._session, None
        self._loop = None
        self._semaphore = None
        self._pause_until = 0.0
        if session is not None and id(session) not in self._inflight:
            await self._close_session(session)
