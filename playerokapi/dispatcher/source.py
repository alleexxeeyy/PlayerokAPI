from __future__ import annotations

import asyncio
import json
import time
import traceback
import uuid
from collections import OrderedDict, deque
from collections.abc import AsyncIterator, Awaitable, Callable
from logging import getLogger
from typing import TYPE_CHECKING, Any

from curl_cffi import CurlWsFlag
from curl_cffi.requests import AsyncSession

from .._http import WS_URL
from .._queries import QUERIES
from ..models import Chat, ChatMessage, ChatType, Deal
from .events import (
    BaseEvent,
    ChatInitializedEvent,
    DealConfirmedEvent,
    DealHasProblemEvent,
    DealProblemResolvedEvent,
    DealRolledBackEvent,
    DealStatusChangedEvent,
    ItemPaidEvent,
    ItemSentEvent,
    NewDealEvent,
    NewMessageEvent,
    NewReviewEvent,
)

if TYPE_CHECKING:
    from ..client import Client


logger = getLogger("playerokapi.listener")

_STATUS_EVENTS = {
    "{{ITEM_SENT}}": ItemSentEvent,
    "{{DEAL_ROLLED_BACK}}": DealRolledBackEvent,
    "{{DEAL_HAS_PROBLEM}}": DealHasProblemEvent,
    "{{DEAL_PROBLEM_RESOLVED}}": DealProblemResolvedEvent,
}


class _WsClosed(ConnectionError):
    pass


def _ts(message: ChatMessage | None) -> float:
    if message is None or message.created_at is None:
        return 0
    return message.created_at.timestamp()


class EventSource:
    """
    Источник событий Playerok: WebSocket (новые сообщения и чаты) + опрос новых сделок и отзывов.
    Обычно используется через `Dispatcher` или `client.listen()`.

    :param client: Клиент Playerok.
    :type client: `playerokapi.Client`

    :param new_messages: Получать ли события сообщений, сделок и их статусов.
    :type new_messages: `bool`

    :param new_reviews: Получать ли события новых отзывов.
    :type new_reviews: `bool`
    """

    ping_interval = 30
    """ Через сколько секунд тишины проверять WebSocket пингом. """
    connect_timeout = 15
    """ Таймаут подключения к WebSocket. """
    reconnect_delay = 3
    """ Пауза перед переподключением, растёт с каждой неудачной попыткой (не больше 30 секунд). """
    catch_up_max_age = 600
    """ За какой срок (в секундах) догонять сообщения, пропущенные во время обрыва. """
    actual_message_delay = 6
    """ Пауза перед перезапросом свежего сообщения (Playerok отдаёт его не сразу). """
    actual_deal_delay = 3
    """ Пауза между попытками получить свежую сделку. """
    new_chats_delay = 8
    """ Пауза перед проверкой новых чатов (Playerok может не сразу отобразить актуальные чаты). """
    new_chats_interval = 10
    """ Не чаще, чем раз в сколько секунд проверять новые чаты. """
    new_chats_poll_interval = 15
    """ Как часто проверять новые чаты, если WebSocket ничего не подсказал. """
    review_check_delay = 30
    """ Как часто проверять отзыв по сделке. """
    review_check_tries = 30
    """ Сколько раз проверять отзыв по сделке, прежде чем перестать. """
    restart_delay = 10
    """ Через сколько секунд перезапускать упавшую фоновую задачу. """

    def __init__(self, client: Client, new_messages: bool = True, new_reviews: bool = True):
        if not any((new_messages, new_reviews)):
            raise ValueError("Нужно включить хотя бы одно из: new_messages, new_reviews")

        self.client = client
        self.new_messages = new_messages
        self.new_reviews = new_reviews

        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        self._tasks: set[asyncio.Task] = set()
        self._conn_tasks: set[asyncio.Task] = set()
        self._started = False
        self._closed = False

        self._chats: OrderedDict[str, tuple[Chat, dict]] = OrderedDict()
        self._subscriptions: dict[str, str] = {}
        self._processed_msgs: deque[str] = deque(maxlen=300)
        self._claimed_ids: OrderedDict[str, bool] = OrderedDict()
        self._processed_deals: deque[str] = deque(maxlen=3000)
        self._review_deals: dict[str, dict[str, float]] = {}
        self._possible_new_chat = asyncio.Event()
        self._last_chats_check = 0.0

        self._ws: Any = None
        self._send_lock = asyncio.Lock()
        self._acked = False
        self._acked_subscribed = False
        self._frames: asyncio.Queue = asyncio.Queue()
        self._ws_session: AsyncSession | None = None
        self._started_at = time.time()
        self._ws_last_recv = 0.0
        self._ws_lost_at: float | None = None
        self._ws_alarm = False
        self._clock_offset = 0.0

    async def listen(self) -> AsyncIterator[BaseEvent]:
        """
        Запускает источник и отдаёт события по одному.
        При выходе из цикла источник останавливается.
        """
        await self.start()
        try:
            while True:
                yield await self._queue.get()
        finally:
            await self.close()

    async def start(self):
        """
        Загружает первые 24 чата (события `ChatInitializedEvent`) и запускает фоновые задачи.
        """
        if self._started or self._closed:
            return
        self._started_at = time.time()

        await self.client._me_id()
        try:
            chats = await self._fetch_chats(24)
        except Exception:
            logger.debug(f"Не удалось получить чаты при запуске: {traceback.format_exc()}")
            chats = []
        if self._started or self._closed:
            return
        self._started = True

        for chat, raw in chats:
            self._chats[chat.id] = (chat, raw)
        self._mark_old_last_messages(chats)
        for chat, raw in chats:
            self._put(ChatInitializedEvent(chat, raw={"chat": raw}))
        # то, что пришло между загрузкой чатов и первым connection_ack, добираем догоном
        self._ws_lost_at = self._started_at

        if self.new_messages:
            self._spawn_forever(self._ws_loop)
            self._spawn_forever(self._deals_loop)
        if self.new_reviews:
            self._spawn_forever(self._reviews_loop)

    async def close(self):
        """
        Останавливает фоновые задачи и закрывает WebSocket.
        """
        if self._closed:
            return
        self._closed = True
        tasks = [*self._tasks, *self._conn_tasks]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._close_ws()

    def _put(self, event: BaseEvent):
        event.client = self.client
        self._queue.put_nowait(event)

    def _spawn(self, coro: Awaitable, conn: bool = False) -> asyncio.Task:
        task = asyncio.ensure_future(coro)
        bucket = self._conn_tasks if conn else self._tasks
        bucket.add(task)
        task.add_done_callback(self._task_done(bucket))
        return task

    @staticmethod
    def _task_done(bucket: set):
        def done(task: asyncio.Task):
            bucket.discard(task)
            if not task.cancelled() and task.exception() is not None:
                e = task.exception()
                logger.debug(f"Ошибка фоновой задачи: {''.join(traceback.format_exception(e))}")
        return done

    def _spawn_forever(self, func: Callable[[], Awaitable]):
        async def run():
            while True:
                try:
                    await func()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.error(f"Слушатель {func.__name__} упал, перезапускаю: {traceback.format_exc()}")
                await asyncio.sleep(self.restart_delay)
        self._spawn(run())

    async def _fetch_chats(self, count: int, type: ChatType | None = None) -> list[tuple[Chat, dict]]:
        data = await self.client._execute("userChats", {
            "pagination": {"first": count, "after": None},
            "filter": {"userId": await self.client._me_id(), "type": type.value if type else None, "status": None},
            "hasSupportAccess": False
        })
        edges = (data.get("chats") or {}).get("edges") or []
        nodes = [e["node"] for e in edges if isinstance(e, dict) and isinstance(e.get("node"), dict)]
        return [(Chat.model_validate(node), node) for node in nodes]

    async def _fetch_messages(self, chat_id: str, count: int) -> list[tuple[ChatMessage, dict]]:
        data = await self.client._execute("chatMessages", {
            "pagination": {"first": count, "after": None},
            "filter": {"chatId": chat_id},
            "hasSupportAccess": False,
            "showForbiddenImage": True
        })
        edges = (data.get("chatMessages") or {}).get("edges") or []
        nodes = [e["node"] for e in edges if isinstance(e, dict) and isinstance(e.get("node"), dict)]
        return [(ChatMessage.model_validate(node), node) for node in nodes]

    async def _fetch_deal(self, deal_id: str) -> tuple[Deal, dict] | None:
        data = await self.client._execute("deal", {"id": deal_id, "hasSupportAccess": False, "showForbiddenImage": True})
        raw = data.get("deal")
        return (Deal.model_validate(raw), raw) if isinstance(raw, dict) else None

    async def _fetch_chat(self, chat_id: str) -> tuple[Chat, dict] | None:
        data = await self.client._execute("chat", {"id": chat_id, "hasSupportAccess": False})
        raw = data.get("chat")
        return (Chat.model_validate(raw), raw) if isinstance(raw, dict) else None

    def _is_msg_processed(self, message_id: str | None) -> bool:
        return message_id in self._processed_msgs or message_id in self._claimed_ids

    def _mark_processed(self, message_id: str | None):
        if message_id and message_id not in self._processed_msgs:
            self._processed_msgs.append(message_id)

    def _claim_msg(self, message: ChatMessage | None) -> bool:
        if message is None or not message.id:
            return False
        if message.id in self._claimed_ids or self._is_msg_processed(message.id):
            return False
        # processed_msgs держит только 300 последних — догон за 10 минут может выйти за него
        self._claimed_ids[message.id] = True
        if len(self._claimed_ids) > 3000:
            self._claimed_ids.popitem(last=False)
        self._mark_processed(message.id)
        return True

    def _is_own(self, message: ChatMessage) -> bool:
        return bool(message.user and message.user.id and message.user.id == self.client.id)

    def _should_emit(self, message: ChatMessage) -> bool:
        # свои сообщения не выдаём, кроме служебных ({{...}}) — одинаково для WS, догона и поллинга
        return not self._is_own(message) or (message.text or "").startswith("{{")

    def _server_now(self) -> float:
        return time.time() + self._clock_offset

    def _mark_old_last_messages(self, chats: list[tuple[Chat, dict]]):
        now = self._server_now()
        for chat, _ in chats:
            msg = chat.last_message
            if msg and msg.id and now - _ts(msg) > 90:
                self._mark_processed(msg.id)

    def _remember_chat(self, chat: Chat, raw: dict):
        self._chats.pop(chat.id, None)
        self._chats[chat.id] = (chat, raw)

    async def _process_message(self, chat: Chat, chat_raw: dict, message: ChatMessage, message_raw: dict):
        self._remember_chat(chat, chat_raw)
        self._mark_processed(message.id)
        for event in await self._message_events(chat, chat_raw, message, message_raw):
            self._put(event)

    async def _actual_message(
        self,
        message_id: str,
        chat_id: str,
        ready: Callable[[ChatMessage], bool] = lambda m: True
    ) -> tuple[ChatMessage, dict] | None:
        found = None
        for _ in range(3):
            await asyncio.sleep(self.actual_message_delay)
            try:
                messages = await self._fetch_messages(chat_id, 12)
            except Exception:
                return found
            found = next(((m, raw) for m, raw in messages if m.id == message_id), found)
            if found and ready(found[0]):
                return found
        return found

    async def _actual_deal(self, deal_id: str) -> tuple[Deal, dict] | None:
        # в сообщении сделка приходит устаревшая — перезапрашиваем
        for _ in range(3):
            try:
                return await self._fetch_deal(deal_id)
            except Exception:
                pass
            await asyncio.sleep(self.actual_deal_delay)
        return None

    async def _message_events(self, chat: Chat, chat_raw: dict, message: ChatMessage, message_raw: dict) -> list[BaseEvent]:
        text = message.text

        if not text:
            if message.images:
                message.text = None
                return [NewMessageEvent(message, chat, raw={"chat": chat_raw, "message": message_raw})]
            if message.event or message.deal:
                return []
            # фото по WS приходит без картинок: их прикрепляют позже, через HTTP они уже есть
            actual = await self._actual_message(message.id, chat.id, ready=lambda m: bool(m.images))
            if actual:
                message, message_raw = actual
            message.text = message.text or None
            return [NewMessageEvent(message, chat, raw={"chat": chat_raw, "message": message_raw})]

        is_paid = text == "{{ITEM_PAID}}"
        is_confirmed = text.startswith("{{DEAL_CONFIRMED") and text.endswith("}}")
        status_event = _STATUS_EVENTS.get(text)

        if is_paid or is_confirmed or status_event:
            actual = await self._actual_message(message.id, chat.id)
            actual_msg = actual[0] if actual else message
            deal_id = (actual_msg.deal or message.deal).id if (actual_msg.deal or message.deal) else None
            fresh = await self._actual_deal(deal_id) if deal_id else None
            if fresh:
                deal, deal_raw = fresh
            elif message.deal:
                deal, deal_raw = message.deal, message_raw.get("deal") or {}
            else:
                deal = None

            if deal is not None:
                raw = {"chat": chat_raw, "message": actual[1] if actual else message_raw, "deal": deal_raw}
                if is_paid:
                    if deal.id:
                        if deal.id in self._processed_deals:
                            return []
                        self._processed_deals.append(deal.id)
                        self._review_deals.setdefault(deal.id, {"last": 0.0, "tries": 0})
                    return [NewDealEvent(deal, chat, raw=raw), ItemPaidEvent(deal, chat, raw=raw)]
                if is_confirmed:
                    first = DealConfirmedEvent(deal, chat, automatically=text == "{{DEAL_CONFIRMED_AUTOMATICALLY}}", raw=raw)
                else:
                    first = status_event(deal, chat, raw=raw)
                return [first, DealStatusChangedEvent(deal, chat, raw=raw)]

        return [NewMessageEvent(message, chat, raw={"chat": chat_raw, "message": message_raw})]

    async def _connect(self):
        transport = self.client._transport
        self._ws_session = AsyncSession(
            impersonate=transport.impersonate,
            proxy=transport.proxy_url,
            verify=transport.cert_path
        )
        headers = {
            "accept-language": "ru,en;q=0.9",
            "cache-control": "no-cache",
            "origin": "https://playerok.com",
            "pragma": "no-cache",
            "sec-websocket-protocol": "graphql-transport-ws",
            "cookie": transport.cookie_header,
            "user-agent": transport.user_agent
        }
        return await asyncio.wait_for(
            self._ws_session.ws_connect(WS_URL, headers=headers, timeout=self.connect_timeout),
            self.connect_timeout + 5
        )

    async def _close_ws(self):
        ws, self._ws = self._ws, None
        session, self._ws_session = self._ws_session, None
        if ws is not None:
            try: await asyncio.wait_for(ws.close(), 5)
            except Exception: pass
        if session is not None:
            try: await asyncio.wait_for(session.close(), 5)
            except Exception: pass

    async def _send(self, payload: dict):
        ws = self._ws
        if ws is None:
            raise _WsClosed("WebSocket не подключён")
        async with self._send_lock:
            try:
                await asyncio.wait_for(ws.send_str(json.dumps(payload)), self.connect_timeout)
            except asyncio.TimeoutError:
                raise _WsClosed("WebSocket не принимает отправку") from None

    async def _reader(self, ws, frames: asyncio.Queue):
        try:
            while True:
                data, flags = await ws.recv()
                if flags & CurlWsFlag.CLOSE:
                    raise _WsClosed("Playerok закрыл WebSocket")
                frames.put_nowait(data)
        except asyncio.CancelledError:
            raise
        except BaseException as e:
            frames.put_nowait(e)

    async def _ws_loop(self):
        fails = 0
        while True:
            connected_at = time.time()
            try:
                await self._ws_session_run()
            except asyncio.CancelledError:
                raise
            except Exception:
                # рвётся сразу после подключения — соединение не рабочее, backoff растёт
                worked = self._ws_last_recv >= connected_at and time.time() - connected_at >= 60
                fails = 1 if worked else fails + 1
                if self._ws_lost_at is None:
                    # не подключились с самого старта — догоняем с момента запуска
                    self._ws_lost_at = self._ws_last_recv or self._started_at
                if fails <= 3:
                    logger.debug(f"Соединение с WebSocket потеряно (попытка {fails}): {traceback.format_exc()}")
                else:
                    logger.debug(f"Соединение с WebSocket потеряно (попытка {fails})")
                if fails == 3:
                    self._ws_alarm = True
                    logger.warning("Нет соединения с Playerok, новые сообщения не приходят. Переподключаюсь...")
            finally:
                for task in list(self._conn_tasks):
                    task.cancel()
                await self._close_ws()
            await asyncio.sleep(min(self.reconnect_delay * fails, 30))

    async def _ws_session_run(self):
        self._acked = False
        self._ws = await self._connect()
        frames: asyncio.Queue = asyncio.Queue()
        self._frames = frames
        self._spawn(self._reader(self._ws, frames), conn=True)
        await self._send({
            "type": "connection_init",
            "payload": {"x-gql-op": "ws-subscription", "x-gql-path": "/chats/[id]", "x-timezone-offset": -180}
        })
        ack_deadline = time.monotonic() + self.connect_timeout

        awaiting_pong = False
        while True:
            timeout = self.ping_interval
            if not self._acked:
                timeout = min(timeout, max(ack_deadline - time.monotonic(), 0))
            try:
                frame = await asyncio.wait_for(frames.get(), timeout)
            except asyncio.TimeoutError:
                if not self._acked and time.monotonic() >= ack_deadline:
                    raise _WsClosed("Playerok не подтвердил подключение (нет connection_ack)")
                # долго тихо — проверяем, живо ли соединение. не ответил на ping — переподключаемся
                if awaiting_pong:
                    raise _WsClosed("WebSocket не ответил на ping")
                await self._send({"type": "ping"})
                awaiting_pong = True
                continue

            if isinstance(frame, BaseException):
                raise frame
            awaiting_pong = False
            self._ws_last_recv = time.time()
            if self._ws_alarm:
                self._ws_alarm = False
                logger.info("Соединение с Playerok восстановлено, сообщения снова приходят")
            try:
                await self._handle_frame(frame)
            except _WsClosed:
                raise
            except Exception:
                logger.debug(f"Ошибка обработки сообщения в WebSocket`е: {traceback.format_exc()}")

    async def _handle_frame(self, frame: bytes | str):
        try: msg = json.loads(frame)
        except ValueError: return
        if not isinstance(msg, dict):
            return

        kind = msg.get("type")
        if kind == "ping":
            await self._send({"type": "pong"})
            return
        if kind == "pong":
            return

        logger.debug(f"WS -> {msg}")

        if kind == "connection_ack":
            self._acked = True
            self._spawn(self._on_connection_ack(self._frames), conn=True)
            return

        data = (msg.get("payload") or {}).get("data") or {}

        user_updated = data.get("userUpdated")
        if isinstance(user_updated, dict) and (user_updated.get("unreadChatsCounter") or 0) > 0:
            self._possible_new_chat.set()

        chat_raw = data.get("chatUpdated")
        if isinstance(chat_raw, dict):
            chat = Chat.model_validate(chat_raw)
            if chat.id and chat.id not in self._chats:
                self._remember_chat(chat, chat_raw)
                if not self._is_chat_subscribed(chat.id):
                    await self._subscribe_chat(chat.id)
                self._put(ChatInitializedEvent(chat, raw={"chat": chat_raw}))
                message = chat.last_message
                message_raw = chat_raw.get("lastMessage")
                if isinstance(message_raw, dict) and message and self._claim_msg(message) and self._should_emit(message):
                    self._spawn(self._process_message(chat, chat_raw, message, message_raw))
            elif chat.id and not self._is_chat_subscribed(chat.id) and self._acked_subscribed:
                await self._subscribe_chat(chat.id)

        message_raw = data.get("chatMessageCreated")
        if isinstance(message_raw, dict):
            chat_id = self._subscriptions.get(msg.get("id"))
            known = self._chats.get(chat_id) if chat_id else None
            if known is None:
                logger.debug(f"Чат {chat_id} ещё не известен — пропуск chatMessageCreated")
                return
            message = ChatMessage.model_validate(message_raw)
            # одно сообщение могут прислать дважды (двойная подписка) или его уже выпустил догон
            if not self._claim_msg(message):
                return
            if message.created_at:
                self._clock_offset = _ts(message) - time.time()
            if not self._should_emit(message):
                return
            chat, chat_raw = known
            self._spawn(self._process_message(chat, chat_raw, message, message_raw))

    def _is_chat_subscribed(self, chat_id: str) -> bool:
        return chat_id in self._subscriptions.values()

    async def _subscribe(self, operation: str, variables: dict, sub_id: str | None = None):
        await self._send({
            "id": sub_id or str(uuid.uuid4()),
            "type": "subscribe",
            "payload": {"extensions": {}, "operationName": operation, "query": QUERIES[operation], "variables": variables}
        })

    async def _subscribe_chat(self, chat_id: str):
        sub_id = str(uuid.uuid4())
        self._subscriptions[sub_id] = chat_id
        try:
            await self._subscribe("chatMessageCreated", {"filter": {"chatId": chat_id}}, sub_id)
        except BaseException:
            # иначе чат числится подписанным и больше никогда не переподпишется
            self._subscriptions.pop(sub_id, None)
            raise

    async def _on_connection_ack(self, frames: asyncio.Queue):
        # подписки прошлого соединения мертвы — иначе _is_chat_subscribed врёт и чат не переподпишется
        self._subscriptions.clear()
        self._acked_subscribed = False
        lost_at, self._ws_lost_at = self._ws_lost_at, None
        caught_up = False
        try:
            me = await self.client._me_id()
            await self._subscribe("chatUpdated", {"filter": {"userId": me}, "showForbiddenImage": True})
            await self._subscribe("userUpdated", {"userId": me})
            for chat_id in list(self._chats):
                if not self._is_chat_subscribed(chat_id):
                    await self._subscribe_chat(chat_id)
            self._acked_subscribed = True
            caught_up = not lost_at or await self._catch_up(lost_at)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            # без подписок соединение бесполезно — пусть переподключится
            logger.warning(f"Не удалось подписаться на события Playerok, переподключаюсь: {e}")
            frames.put_nowait(e)
        finally:
            if lost_at and not caught_up:
                # не догнали — повторим на следующем подключении с того же места
                self._ws_lost_at = min(lost_at, self._ws_lost_at or lost_at)

    async def _catch_up(self, lost_at: float) -> bool:
        # подписки не присылают то, что пришло, пока WS был отключён — добираем через историю чатов.
        # created_at серверный, поэтому окно сдвигаем на расхождение часов ПК с сервером
        offset = self._clock_offset
        since = max(lost_at - 30, self._started_at) + offset
        oldest = time.time() + offset - self.catch_up_max_age
        if since < oldest:
            logger.warning(
                f"Связи с Playerok не было дольше {self.catch_up_max_age // 60} минут — "
                f"сообщения из чатов раньше этого не восстановлены"
            )
            since = oldest

        chats = None
        for _ in range(3):
            try:
                chats = await self._fetch_chats(24)
                break
            except Exception:
                logger.debug(f"Не удалось получить чаты для догона сообщений: {traceback.format_exc()}")
                await asyncio.sleep(2)
        if chats is None:
            return False

        for chat, chat_raw in chats:
            if not chat.last_message or _ts(chat.last_message) < since:
                continue
            if chat.id not in self._chats:
                self._remember_chat(chat, chat_raw)
                self._put(ChatInitializedEvent(chat, raw={"chat": chat_raw}))
            if not self._is_chat_subscribed(chat.id):
                await self._subscribe_chat(chat.id)

            try:
                messages = await self._fetch_messages(chat.id, 24)
            except Exception:
                last_raw = chat_raw.get("lastMessage")
                messages = [(chat.last_message, last_raw if isinstance(last_raw, dict) else {})]

            for message, message_raw in sorted(messages, key=lambda pair: _ts(pair[0])):
                if _ts(message) < since:
                    continue
                if not self._claim_msg(message) or not self._should_emit(message):
                    continue
                logger.debug(f"Догнал пропущенное сообщение {message.id} в чате {chat.id}")
                # обработка (с дозапросом сделки) не должна оборваться вместе с соединением — иначе сообщение потеряется
                self._spawn(self._process_message(chat, chat_raw, message, message_raw))

            await asyncio.sleep(0.5)
        return True

    async def _deals_loop(self):
        while True:
            try:
                await asyncio.wait_for(self._possible_new_chat.wait(), self.new_chats_poll_interval)
                by_event = True
            except asyncio.TimeoutError:
                by_event = False
            try:
                if by_event:
                    self._possible_new_chat.clear()
                    wait = self.new_chats_interval - (time.time() - self._last_chats_check)
                    if wait > 0:
                        await asyncio.sleep(wait)
                await self._check_new_deals(by_event)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug(f"Ошибка проверки новых сделок: {traceback.format_exc()}")
            self._last_chats_check = time.time()

    async def _check_new_deals(self, by_event: bool):
        possible: OrderedDict[str, tuple[Chat, dict]] = OrderedDict()
        now = self._server_now()

        for _ in range(3):
            try:
                if by_event:
                    await asyncio.sleep(self.new_chats_delay)
                for chat, raw in await self._fetch_chats(15, ChatType.PM):
                    last = chat.last_message
                    if not last:
                        continue
                    if (
                        chat.id not in self._chats
                        or not self._is_msg_processed(last.id)
                        or now - _ts(last) <= 90
                    ):
                        possible.setdefault(chat.id, (chat, raw))
                if possible:
                    break # если найдены чаты с возможными новыми сделками - останавливаем цикл
                if not by_event:
                    await asyncio.sleep(self.new_chats_delay)
            except asyncio.CancelledError:
                raise
            except Exception:
                pass

        for chat, chat_raw in possible.values():
            last = chat.last_message
            last_raw = chat_raw.get("lastMessage")
            # быстрый путь: в чате последнее сообщение — оплата
            if last and last.text == "{{ITEM_PAID}}" and now - _ts(last) <= 90 and isinstance(last_raw, dict):
                await self._process_message(chat, chat_raw, last, last_raw)
                continue

            # медленный путь: last_message перебит новым сообщением от покупателя, ищем оплату в истории
            try:
                await asyncio.sleep(1)
                messages = await self._fetch_messages(chat.id, 12)
                paid = next(
                    ((m, raw) for m, raw in messages if m.text == "{{ITEM_PAID}}" and now - _ts(m) <= 90),
                    None
                )
                if paid:
                    await self._process_message(chat, chat_raw, *paid)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.debug(f"Ошибка получения истории сообщений нового чата {chat.id}: {traceback.format_exc()}")

    def _should_check_review(self, deal_id: str) -> bool:
        info = self._review_deals.get(deal_id)
        if info is None:
            return False
        now = time.time()
        if now - info["last"] > self.review_check_delay:
            info["last"] = now
            info["tries"] += 1
            return True
        if info["tries"] >= self.review_check_tries:
            del self._review_deals[deal_id]
        return False

    async def _reviews_loop(self):
        while True:
            for deal_id in list(self._review_deals):
                try:
                    if not self._should_check_review(deal_id):
                        continue
                    try:
                        fetched = await self._fetch_deal(deal_id)
                    except Exception:
                        continue
                    if not fetched or not fetched[0].review:
                        continue
                    deal, deal_raw = fetched
                    self._review_deals.pop(deal_id, None)

                    chat_id = deal.chat.id if deal.chat else None
                    known = self._chats.get(chat_id) if chat_id else None
                    if known is None and chat_id:
                        try: known = await self._fetch_chat(chat_id)
                        except Exception: known = None
                    chat, chat_raw = known if known else (deal.chat, deal_raw.get("chat") or {})
                    deal.chat = chat
                    self._put(NewReviewEvent(deal, chat, raw={"chat": chat_raw, "deal": deal_raw}))
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.debug(f"Ошибка проверки новых отзывов в сделке {deal_id}: {traceback.format_exc()}")
            await asyncio.sleep(1)
