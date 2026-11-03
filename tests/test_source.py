import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from curl_cffi import CurlWsFlag

from playerokapi import models as m
from playerokapi.client import Client
from playerokapi.dispatcher import events as ev
from playerokapi.dispatcher.source import EventSource


ME = "me-id"
BUYER = {"id": "buyer", "username": "buyer"}
WS_FIXTURE = Path(__file__).parent / "fixtures" / "ws" / "chat_session.json"


def iso(seconds_ago: float = 0) -> str:
    dt = datetime.now(timezone.utc) - timedelta(seconds=seconds_ago)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def msg(text, *, id=None, user=BUYER, ago=0, deal=None, images=None, event=None):
    return {
        "__typename": "ChatMessage", "id": id or str(uuid.uuid4()), "text": text, "createdAt": iso(ago),
        "user": user, "deal": deal, "images": images or [], "event": event,
    }


def chat(id, last=None, users=(BUYER,)):
    return {"__typename": "Chat", "id": id, "type": "PM", "participants": [{"id": ME, "username": "me"}, *users],
            "lastMessage": last}


def page(nodes):
    return {"edges": [{"node": n} for n in nodes], "pageInfo": {"hasNextPage": False}, "totalCount": len(nodes)}


class FakeWS:
    def __init__(self):
        self.incoming: asyncio.Queue = asyncio.Queue()
        self.sent: list[dict] = []
        self.closed = False

    async def recv(self):
        item = await self.incoming.get()
        if isinstance(item, BaseException):
            raise item
        return item

    async def send_str(self, payload):
        self.sent.append(json.loads(payload))

    async def close(self):
        self.closed = True

    def push(self, frame):
        data = frame if isinstance(frame, (bytes, str)) else json.dumps(frame)
        self.incoming.put_nowait((data.encode() if isinstance(data, str) else data, CurlWsFlag.TEXT))

    def push_next(self, sub_id, data):
        self.push({"id": sub_id, "type": "next", "payload": {"data": data}})

    def subs(self, operation):
        return [s for s in self.sent if s.get("type") == "subscribe" and s["payload"]["operationName"] == operation]

    def chat_sub(self, chat_id):
        return next(s["id"] for s in self.subs("chatMessageCreated") if s["payload"]["variables"]["filter"]["chatId"] == chat_id)


class Api:
    def __init__(self):
        self.chats = []
        self.messages: dict[str, list] = {}
        self.deals: dict[str, dict] = {}
        self.calls: list[tuple[str, dict]] = []

    async def execute(self, operation, variables=None):
        self.calls.append((operation, variables or {}))
        await asyncio.sleep(0)
        if operation == "userChats":
            nodes = self.chats
            if (variables or {}).get("filter", {}).get("type") == "PM":
                nodes = [c for c in nodes if c.get("type") == "PM"]
            return {"chats": page(nodes[: variables["pagination"]["first"]])}
        if operation == "chatMessages":
            return {"chatMessages": page(list(reversed(self.messages.get(variables["filter"]["chatId"], []))))}
        if operation == "deal":
            return {"deal": self.deals.get(variables["id"])}
        if operation == "chat":
            return {"chat": next((c for c in self.chats if c["id"] == variables["id"]), None)}
        raise AssertionError(operation)

    def count(self, operation):
        return sum(1 for op, _ in self.calls if op == operation)


@pytest.fixture
async def env(monkeypatch):
    api = Api()
    client = Client(token="t")
    client.me = m.AccountProfile(id=ME, username="me")
    monkeypatch.setattr(client, "_execute", api.execute)
    sockets: list[FakeWS] = []
    connect_errors: list[BaseException] = []

    async def connect(self):
        if connect_errors:
            raise connect_errors.pop(0)
        ws = FakeWS()
        sockets.append(ws)
        return ws

    monkeypatch.setattr(EventSource, "_connect", connect)
    source = EventSource(client)
    for attr in ("actual_message_delay", "actual_deal_delay", "new_chats_delay", "new_chats_interval", "restart_delay", "review_check_delay"):
        setattr(source, attr, 0)
    source.ping_interval = 0.2
    source.reconnect_delay = 0.01
    source.new_chats_poll_interval = 3600
    yield source, api, sockets, connect_errors
    await source.close()


async def next_event(source, timeout=2.0):
    return await asyncio.wait_for(source._queue.get(), timeout)


async def drain(source, wait=0.15):
    await asyncio.sleep(wait)
    out = []
    while not source._queue.empty():
        out.append(source._queue.get_nowait())
    return out


async def wait_for(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("условие не выполнилось")
        await asyncio.sleep(0.005)


async def started(source, sockets):
    await source.start()
    await wait_for(lambda: sockets)
    ws = sockets[-1]
    ws.push({"type": "connection_ack"})
    await wait_for(lambda: ws.subs("userUpdated"))
    return ws


async def test_start_emits_chat_initialized_for_first_chats(env):
    source, api, sockets, _ = env
    api.chats = [chat(f"c{i}", msg("старое", ago=600)) for i in range(30)]
    await source.start()
    events = [await next_event(source) for _ in range(24)]
    assert all(isinstance(e, ev.ChatInitializedEvent) for e in events)
    assert [e.chat.id for e in events] == [f"c{i}" for i in range(24)]
    assert events[0].raw["chat"]["id"] == "c0"
    assert events[0].client is source.client
    assert all(source._is_msg_processed(c["lastMessage"]["id"]) for c in api.chats[:24])


async def test_connection_ack_subscribes(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1"), chat("c2")]
    ws = await started(source, sockets)
    assert ws.sent[0]["type"] == "connection_init"
    assert ws.subs("chatUpdated")[0]["payload"]["variables"]["filter"]["userId"] == ME
    assert ws.subs("userUpdated")[0]["payload"]["variables"] == {"userId": ME}
    await wait_for(lambda: len(ws.subs("chatMessageCreated")) == 2)


async def test_new_message_and_duplicate(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    node = msg("привет")
    sub = ws.chat_sub("c1")
    ws.push_next(sub, {"chatMessageCreated": node})
    ws.push_next(sub, {"chatMessageCreated": node})
    event = await next_event(source)
    assert isinstance(event, ev.NewMessageEvent)
    assert event.message.text == "привет" and event.chat.id == "c1"
    assert event.raw["message"]["id"] == node["id"]
    assert await drain(source) == []


async def test_photo_without_caption_is_refetched_with_images(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    node = msg(None)
    api.messages["c1"] = [{**node, "images": [{"id": "f1", "url": "https://x/1.png"}]}]
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": node})
    event = await next_event(source)
    assert isinstance(event, ev.NewMessageEvent)
    assert event.message.text is None
    assert [i.id for i in event.message.images] == ["f1"]


async def test_photo_without_caption_emitted_even_if_images_never_appear(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("")})
    event = await next_event(source)
    assert isinstance(event, ev.NewMessageEvent) and event.message.text is None
    assert api.count("chatMessages") == 3


async def test_service_message_without_text_is_skipped(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg(None, event="CHAT_STARTED")})
    assert await drain(source) == []


async def test_item_paid_gives_new_deal_then_item_paid_once(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    api.deals["d1"] = {"__typename": "ItemDeal", "id": "d1", "status": "PAID", "user": BUYER}
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    stale = {"id": "d1", "status": "SENT"}
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("{{ITEM_PAID}}", deal=stale, user=None)})
    first, second = await next_event(source), await next_event(source)
    assert isinstance(first, ev.NewDealEvent) and isinstance(second, ev.ItemPaidEvent)
    assert first.deal.status == m.DealStatus.PAID
    assert first.raw["deal"]["status"] == "PAID"
    assert not any(isinstance(e, ev.DealStatusChangedEvent) for e in await drain(source))
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("{{ITEM_PAID}}", deal=stale, user=None)})
    assert await drain(source) == []
    assert "d1" in source._review_deals


@pytest.mark.parametrize("text,cls,automatic", [
    ("{{DEAL_CONFIRMED}}", ev.DealConfirmedEvent, False),
    ("{{DEAL_CONFIRMED_AUTOMATICALLY}}", ev.DealConfirmedEvent, True),
    ("{{ITEM_SENT}}", ev.ItemSentEvent, None),
    ("{{DEAL_ROLLED_BACK}}", ev.DealRolledBackEvent, None),
    ("{{DEAL_HAS_PROBLEM}}", ev.DealHasProblemEvent, None),
    ("{{DEAL_PROBLEM_RESOLVED}}", ev.DealProblemResolvedEvent, None),
])
async def test_status_messages(env, text, cls, automatic):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    api.deals["d1"] = {"id": "d1", "status": "CONFIRMED"}
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg(text, deal={"id": "d1"}, user=None)})
    first, second = await next_event(source), await next_event(source)
    assert type(first) is cls and isinstance(second, ev.DealStatusChangedEvent)
    assert first.deal.id == "d1"
    if automatic is not None:
        assert first.automatically is automatic


async def test_status_message_without_deal_falls_back_to_message(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("{{ITEM_SENT}}", user=None)})
    event = await next_event(source)
    assert isinstance(event, ev.NewMessageEvent) and event.message.text == "{{ITEM_SENT}}"


async def test_message_for_unknown_subscription_is_ignored(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await drain(source)
    ws.push_next("unknown-sub", {"chatMessageCreated": msg("кто я")})
    assert await drain(source) == []


async def test_chat_updated_for_new_chat(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await drain(source)
    new_chat = chat("c9", msg("первое сообщение"))
    ws.push_next("chat-updated", {"chatUpdated": new_chat})
    first, second = await next_event(source), await next_event(source)
    assert isinstance(first, ev.ChatInitializedEvent) and first.chat.id == "c9"
    assert isinstance(second, ev.NewMessageEvent) and second.message.text == "первое сообщение"
    await wait_for(lambda: any(s["payload"]["variables"]["filter"]["chatId"] == "c9" for s in ws.subs("chatMessageCreated")))
    ws.push_next("chat-updated", {"chatUpdated": new_chat})
    assert await drain(source) == []


async def test_broken_frames_are_skipped(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    ws.push(b"\xff\xfe not json")
    ws.push("[1, 2, 3]")
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": {"id": "x", "createdAt": 5, "images": "bad"}})
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("живой")})
    event = await next_event(source)
    assert event.message.text == "живой"
    assert len(sockets) == 1


async def test_server_ping_gets_pong(env):
    source, api, sockets, _ = env
    ws = await started(source, sockets)
    ws.push({"type": "ping"})
    await wait_for(lambda: {"type": "pong"} in ws.sent)


async def test_silence_sends_ping_then_reconnects_and_catches_up(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    await wait_for(lambda: {"type": "ping"} in ws.sent, timeout=1)

    missed = msg("пока не было связи")
    api.chats = [chat("c1", missed)]
    api.messages["c1"] = [missed]
    await wait_for(lambda: len(sockets) == 2, timeout=3)
    assert ws.closed
    sockets[1].push({"type": "connection_ack"})
    event = await next_event(source, timeout=3)
    assert isinstance(event, ev.NewMessageEvent) and event.message.text == "пока не было связи"
    await wait_for(lambda: sockets[1].subs("chatMessageCreated"))


async def test_reader_error_reconnects_and_skips_own_messages_in_catch_up(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)

    own = msg("мой ответ", user={"id": ME, "username": "me"}, ago=-1)
    own_marker = msg("{{ITEM_SENT}}", user={"id": ME, "username": "me"}, ago=-2)
    theirs = msg("ответ покупателя", ago=-3)
    api.messages["c1"] = [own, own_marker, theirs]
    api.chats = [chat("c1", theirs)]
    ws.incoming.put_nowait(ConnectionResetError("WinError 10054"))
    await wait_for(lambda: len(sockets) == 2, timeout=5)
    sockets[1].push({"type": "connection_ack"})
    got = [await next_event(source, timeout=3), await next_event(source, timeout=3)]
    texts = sorted(e.message.text for e in got)
    assert texts == ["{{ITEM_SENT}}", "ответ покупателя"]
    assert await drain(source) == []


async def test_catch_up_does_not_repeat_ws_messages(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    seen = msg("уже пришло по WS")
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": seen})
    await next_event(source)
    api.messages["c1"] = [seen]
    api.chats = [chat("c1", seen)]
    ws.incoming.put_nowait(ConnectionResetError())
    await wait_for(lambda: len(sockets) == 2, timeout=5)
    sockets[1].push({"type": "connection_ack"})
    await asyncio.sleep(0.3)
    assert await drain(source) == []
    assert api.count("chatMessages") >= 1


async def test_failed_connect_is_retried(env):
    source, api, sockets, connect_errors = env
    connect_errors.append(OSError("нет сети"))
    await source.start()
    await wait_for(lambda: sockets, timeout=5)
    assert source._ws_lost_at is not None


async def test_new_deal_found_by_polling_after_user_updated(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await drain(source)
    paid = msg("{{ITEM_PAID}}", deal={"id": "d7"}, user=None)
    api.chats = [chat("c7", paid), chat("c1")]
    api.messages["c7"] = [paid]
    api.deals["d7"] = {"id": "d7", "status": "PAID"}
    ws.push_next("user-updated", {"userUpdated": {"id": ME, "unreadChatsCounter": 1}})
    first = await next_event(source, timeout=3)
    second = await next_event(source, timeout=3)
    assert isinstance(first, ev.NewDealEvent) and first.chat.id == "c7"
    assert isinstance(second, ev.ItemPaidEvent)


async def test_new_deal_found_in_history_when_last_message_is_newer(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await drain(source)
    paid = msg("{{ITEM_PAID}}", deal={"id": "d8"}, user=None, ago=5)
    after = msg("я оплатил", ago=1)
    api.chats = [chat("c8", after)]
    api.messages["c8"] = [paid, after]
    api.deals["d8"] = {"id": "d8", "status": "PAID"}
    source._possible_new_chat.set()
    events = [await next_event(source, timeout=3), await next_event(source, timeout=3)]
    assert [type(e) for e in events] == [ev.NewDealEvent, ev.ItemPaidEvent]


async def test_new_review_event(env):
    source, api, sockets, _ = env
    source.new_messages = False
    api.chats = [chat("c1")]
    api.deals["d1"] = {"id": "d1", "chat": {"id": "c1"}, "testimonial": {"id": "r1", "rating": 5, "text": "супер"}}
    source._review_deals["d1"] = {"last": 0.0, "tries": 0}
    await source.start()
    events = [await next_event(source) for _ in range(2)]
    review = events[-1]
    assert isinstance(review, ev.NewReviewEvent)
    assert review.deal.review.text == "супер" and review.chat.id == "c1"
    assert review.chat.users
    assert "d1" not in source._review_deals


async def test_review_checks_stop_after_tries(env):
    source, api, sockets, _ = env
    source.review_check_tries = 2
    source._review_deals["d1"] = {"last": 0.0, "tries": 0}
    assert source._should_check_review("d1")
    source._review_deals["d1"]["last"] = 0.0
    assert source._should_check_review("d1")
    source.review_check_delay = 3600
    assert not source._should_check_review("d1")
    assert "d1" not in source._review_deals


async def test_close_cancels_everything(env):
    source, api, sockets, _ = env
    ws = await started(source, sockets)
    await source.close()
    assert not source._tasks and not source._conn_tasks or all(t.done() for t in [*source._tasks, *source._conn_tasks])
    assert ws.closed


async def test_listen_iterator_closes_source(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    agen = source.listen()
    first = await asyncio.wait_for(agen.__anext__(), 2)
    assert isinstance(first, ev.ChatInitializedEvent)
    await agen.aclose()
    assert source._closed


def test_requires_some_events():
    with pytest.raises(ValueError):
        EventSource(Client(token="t"), new_messages=False, new_reviews=False)


async def test_recorded_session_frames(env):
    source, api, sockets, _ = env
    records = json.loads(WS_FIXTURE.read_text(encoding="utf-8"))
    http = {}
    for r in records:
        if r["kind"] == "http":
            http.setdefault(r["operation"], r["response"]["data"])
    chats_raw = http["userChats"]["chats"]["edges"]
    api.chats = [e["node"] for e in chats_raw]
    for c in api.chats:
        if c.get("lastMessage"):
            c["lastMessage"]["createdAt"] = iso(3600)
    ws = await started(source, sockets)
    await wait_for(lambda: len(ws.subs("chatMessageCreated")) == len(api.chats))
    await drain(source)

    frames = [r["frame"] for r in records if r["kind"] == "ws" and r["frame"].get("type") == "next"]
    created = [f for f in frames if "chatMessageCreated" in f["payload"]["data"]]
    chat_id = next(f["payload"]["data"]["chatUpdated"]["id"] for f in frames if "chatUpdated" in f["payload"]["data"])
    sub = ws.chat_sub(chat_id)
    photo_id = next(f["payload"]["data"]["chatMessageCreated"]["id"] for f in created
                    if f["payload"]["data"]["chatMessageCreated"]["text"] is None)
    api.messages[chat_id] = [{**f["payload"]["data"]["chatMessageCreated"], "images": [{"id": "img"}]}
                             for f in created if f["payload"]["data"]["chatMessageCreated"]["id"] == photo_id]
    for f in frames:
        f = {**f, "id": sub if "chatMessageCreated" in f["payload"]["data"] else f.get("id")}
        ws.push(f)

    got = []
    while len(got) < len(created):
        got.append(await next_event(source, timeout=3))
    assert all(isinstance(e, ev.NewMessageEvent) for e in got)
    texts = [e.message.text for e in got]
    assert None in texts
    photo = next(e for e in got if e.message.text is None)
    assert photo.message.images and photo.message.id == photo_id
    assert await drain(source) == []


async def test_client_listen_uses_event_source(env):
    source, api, sockets, _ = env
    client = source.client
    api.chats = [chat("c1")]
    agen = client.listen(new_reviews=False)
    first = await asyncio.wait_for(agen.__anext__(), 2)
    assert isinstance(first, ev.ChatInitializedEvent) and first.client is client
    await agen.aclose()


async def test_failed_ack_handling_reconnects(env, monkeypatch):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    calls = {"n": 0}
    orig = source._subscribe

    async def flaky(operation, variables, sub_id=None):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("подписка не ушла")
        return await orig(operation, variables, sub_id)

    monkeypatch.setattr(source, "_subscribe", flaky)
    await source.start()
    await wait_for(lambda: sockets)
    sockets[0].push({"type": "connection_ack"})
    await wait_for(lambda: len(sockets) == 2, timeout=3)
    sockets[1].push({"type": "connection_ack"})
    await wait_for(lambda: sockets[1].subs("userUpdated"))


async def test_missing_ack_reconnects(env):
    source, api, sockets, _ = env
    source.connect_timeout = 0.2
    await source.start()
    await wait_for(lambda: sockets)
    await wait_for(lambda: len(sockets) == 2, timeout=3)
    assert sockets[0].closed


async def test_message_survives_reconnect_during_catch_up(env):
    source, api, sockets, _ = env
    source.actual_message_delay = 0.3
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    paid = msg("{{ITEM_PAID}}", deal={"id": "d1"}, user=None, ago=-1)
    api.chats = [chat("c1", paid)]
    api.messages["c1"] = [paid]
    api.deals["d1"] = {"id": "d1", "status": "PAID"}
    ws.incoming.put_nowait(ConnectionResetError())
    await wait_for(lambda: len(sockets) == 2, timeout=3)
    sockets[1].push({"type": "connection_ack"})
    await wait_for(lambda: source._claimed_ids.get(paid["id"]), timeout=3)
    sockets[1].incoming.put_nowait(ConnectionResetError())
    first, second = await next_event(source, timeout=5), await next_event(source, timeout=5)
    assert [type(first), type(second)] == [ev.NewDealEvent, ev.ItemPaidEvent]


async def test_chat_found_by_catch_up_gets_new_messages(env):
    source, api, sockets, _ = env
    api.chats = []
    ws = await started(source, sockets)
    await drain(source)
    own = msg("моё сообщение в новом чате", user={"id": ME, "username": "me"}, ago=-1)
    api.chats = [chat("c5", own)]
    api.messages["c5"] = [own]
    ws.incoming.put_nowait(ConnectionResetError())
    await wait_for(lambda: len(sockets) == 2, timeout=3)
    ws2 = sockets[1]
    ws2.push({"type": "connection_ack"})
    init = await next_event(source, timeout=3)
    assert isinstance(init, ev.ChatInitializedEvent) and init.chat.id == "c5"
    await wait_for(lambda: any(s["payload"]["variables"]["filter"]["chatId"] == "c5" for s in ws2.subs("chatMessageCreated")))
    ws2.push_next(ws2.chat_sub("c5"), {"chatMessageCreated": msg("ответ в новом чате")})
    event = await next_event(source)
    assert isinstance(event, ev.NewMessageEvent) and event.message.text == "ответ в новом чате"


async def test_chat_updated_for_known_chat_gives_no_events(env):
    source, api, sockets, _ = env
    last = msg("последнее", ago=600)
    api.chats = [chat("c1", last)]
    await source.start()
    await wait_for(lambda: sockets)
    await drain(source)
    sockets[0].push_next("chat-updated", {"chatUpdated": chat("c1", last)})
    sockets[0].push({"type": "connection_ack"})
    await wait_for(lambda: sockets[0].subs("chatMessageCreated"))
    assert await drain(source) == []
    assert len(sockets[0].subs("chatMessageCreated")) == 1


async def test_own_messages_via_ws_are_not_emitted(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    ws = await started(source, sockets)
    await wait_for(lambda: ws.subs("chatMessageCreated"))
    await drain(source)
    me = {"id": ME, "username": "me"}
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("моё", user=me)})
    ws.push_next(ws.chat_sub("c1"), {"chatMessageCreated": msg("{{ITEM_SENT}}", user=me)})
    event = await next_event(source)
    assert event.message.text == "{{ITEM_SENT}}"
    assert await drain(source) == []


async def test_failed_start_can_be_retried(env, monkeypatch):
    source, api, sockets, _ = env
    client = source.client
    client.me = None
    attempts = {"n": 0}

    async def flaky_refresh():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise ConnectionError("нет сети")
        client.me = m.AccountProfile(id=ME)
        return client.me

    monkeypatch.setattr(client, "refresh", flaky_refresh)
    api.chats = [chat("c1")]
    with pytest.raises(ConnectionError):
        await source.start()
    await source.start()
    event = await next_event(source)
    assert isinstance(event, ev.ChatInitializedEvent)


async def test_first_connection_catches_up_since_start(env):
    source, api, sockets, _ = env
    api.chats = [chat("c1")]
    await source.start()
    await wait_for(lambda: sockets)
    await drain(source)
    early = msg("пришло до первого ack", ago=-1)
    api.chats = [chat("c1", early)]
    api.messages["c1"] = [early]
    sockets[0].push({"type": "connection_ack"})
    event = await next_event(source, timeout=3)
    assert isinstance(event, ev.NewMessageEvent) and event.message.text == "пришло до первого ack"
