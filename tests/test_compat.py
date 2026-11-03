import json
from enum import Enum
from pathlib import Path

import pytest

from playerokapi import _compat, parser
from playerokapi import models as m
from playerokapi.dispatcher import Dispatcher, Router
from playerokapi.dispatcher import events as ev
from playerokapi.enums import EventTypes, ItemDealStatuses
from playerokapi.listener import events as legacy
from playerokapi import types as legacy_types

from test_source import env, started, wait_for, drain, next_event  # noqa: F401


FIXTURES = Path(__file__).parent / "fixtures"


def plain(obj, depth=0):
    if depth > 8:
        return "…"
    if isinstance(obj, Enum):
        return f"{type(obj).__name__}.{obj.name}"
    if isinstance(obj, list):
        return [plain(i, depth + 1) for i in obj]
    if hasattr(obj, "__dict__") and type(obj).__module__.startswith("playerokapi.types"):
        return {k: plain(v, depth + 1) for k, v in vars(obj).items()}
    return obj


def http_data(operation, predicate=lambda d: True):
    for rec in json.loads((FIXTURES / "http" / "test.json").read_text(encoding="utf-8")):
        if rec["operation"] == operation and rec["response"].get("data") and predicate(rec["response"]["data"]):
            return rec["response"]["data"]
    raise LookupError(operation)


def test_new_message_matches_legacy_parser():
    chats = http_data("userChats")["chats"]["edges"]
    chat_raw = chats[0]["node"]
    messages = http_data("chatMessages")["chatMessages"]["edges"]
    for edge in messages:
        raw = edge["node"]
        event = ev.NewMessageEvent(m.ChatMessage.model_validate(raw), m.Chat.model_validate(chat_raw),
                                   raw={"chat": chat_raw, "message": raw})
        old = _compat.to_legacy(event)
        assert isinstance(old, legacy.NewMessageEvent) and old.type is EventTypes.NEW_MESSAGE
        expected = parser.chat_message(raw)
        if event.message.text is None:
            expected.text = None
        assert plain(old.message) == plain(expected)
        assert plain(old.chat) == plain(parser.chat(chat_raw))
        assert isinstance(old.message.created_at, str)
        assert isinstance(old.chat, legacy_types.Chat)


def test_photo_without_caption_keeps_text_none():
    raw = {"id": "p", "text": "", "images": [{"id": "f", "url": "u"}], "createdAt": "2026-11-03T10:33:07.252Z"}
    event = ev.NewMessageEvent(m.ChatMessage.model_validate(raw), m.Chat(id="c"), raw={"chat": {"id": "c"}, "message": raw})
    event.message.text = None
    assert _compat.to_legacy(event).message.text is None
    raw2 = {**raw, "id": "t", "text": "текст"}
    event2 = ev.NewMessageEvent(m.ChatMessage.model_validate(raw2), m.Chat(id="c"), raw={"chat": {"id": "c"}, "message": raw2})
    assert _compat.to_legacy(event2).message.text == "текст"


@pytest.mark.parametrize("cls,legacy_cls,legacy_type", [
    (ev.NewDealEvent, legacy.NewDealEvent, EventTypes.NEW_DEAL),
    (ev.ItemPaidEvent, legacy.ItemPaidEvent, EventTypes.ITEM_PAID),
    (ev.ItemSentEvent, legacy.ItemSentEvent, EventTypes.ITEM_SENT),
    (ev.DealConfirmedEvent, legacy.DealConfirmedEvent, EventTypes.DEAL_CONFIRMED),
    (ev.DealRolledBackEvent, legacy.DealRolledBackEvent, EventTypes.DEAL_ROLLED_BACK),
    (ev.DealHasProblemEvent, legacy.DealHasProblemEvent, EventTypes.DEAL_HAS_PROBLEM),
    (ev.DealProblemResolvedEvent, legacy.DealProblemResolvedEvent, EventTypes.DEAL_PROBLEM_RESOLVED),
    (ev.DealStatusChangedEvent, legacy.DealStatusChangedEvent, EventTypes.DEAL_STATUS_CHANGED),
])
def test_deal_events_match_legacy_parser(cls, legacy_cls, legacy_type):
    deal_raw = http_data("deal")["deal"]
    chat_raw = http_data("chat")["chat"]
    event = cls(m.Deal.model_validate(deal_raw), m.Chat.model_validate(chat_raw), raw={"chat": chat_raw, "deal": deal_raw})
    old = _compat.to_legacy(event)
    assert type(old) is legacy_cls and old.type is legacy_type
    assert plain(old.deal) == plain(parser.item_deal(deal_raw))
    assert isinstance(old.deal.status, ItemDealStatuses)
    assert old.deal.created_at == deal_raw["createdAt"]
    assert old.time == event.time


def test_review_event_puts_chat_into_deal():
    deal_raw = http_data("deal")["deal"]
    chat_raw = http_data("chat")["chat"]
    event = ev.NewReviewEvent(m.Deal.model_validate(deal_raw), m.Chat.model_validate(chat_raw), raw={"chat": chat_raw, "deal": deal_raw})
    old = _compat.to_legacy(event)
    assert isinstance(old, legacy.NewReviewEvent)
    assert old.deal.chat is old.chat


def test_chat_initialized_and_cache():
    chat_raw = http_data("chat")["chat"]
    event = ev.ChatInitializedEvent(m.Chat.model_validate(chat_raw), raw={"chat": chat_raw})
    old = _compat.to_legacy(event)
    assert isinstance(old, legacy.ChatInitializedEvent) and old.chat.id == chat_raw["id"]
    assert _compat.to_legacy(event) is old
    old.chat.unread_messages_counter = 999
    assert _compat.to_legacy(event).chat.unread_messages_counter == 999


async def test_recorded_session_bridges_like_old_listener(env):  # noqa: F811
    source, api, sockets, _ = env
    records = json.loads((FIXTURES / "ws" / "chat_session.json").read_text(encoding="utf-8"))
    old_events = [r["event"] for r in records if r["kind"] == "event"]
    first_chats = next(r for r in records if r["kind"] == "http" and r["operation"] == "userChats")["response"]["data"]
    api.chats = [e["node"] for e in first_chats["chats"]["edges"]]

    ws = await started(source, sockets)
    await wait_for(lambda: len(ws.subs("chatMessageCreated")) == len(api.chats))
    new_events = await drain(source)

    frames = [r["frame"] for r in records if r["kind"] == "ws" and r["frame"].get("type") == "next"]
    created = [f for f in frames if "chatMessageCreated" in f["payload"]["data"]]
    chat_id = next(f["payload"]["data"]["chatUpdated"]["id"] for f in frames if "chatUpdated" in f["payload"]["data"])
    sub = ws.chat_sub(chat_id)
    photo = next(f["payload"]["data"]["chatMessageCreated"] for f in created if f["payload"]["data"]["chatMessageCreated"]["text"] is None)
    api.messages[chat_id] = [{**photo, "images": [{"id": "img", "url": "u"}]}]
    for f in frames:
        ws.push({**f, "id": sub if "chatMessageCreated" in f["payload"]["data"] else f.get("id")})
    while sum(isinstance(e, ev.NewMessageEvent) for e in new_events) < len(created):
        new_events.append(await next_event(source, timeout=3))

    def summary(old):
        message = getattr(old, "message", None)
        return {"event_type": old.type.name, "chatId": old.chat.id if old.chat else None,
                "messageId": message.id if message else None, "messageText": message.text if message else None}

    def token(text):
        # анонимайзер ставит перед токеном имя ключа: text-xxx в кадре и messageText-xxx в сводке события
        return text.rsplit("-", 1)[-1] if isinstance(text, str) else text

    bridged = [{**summary(_compat.to_legacy(e)), "messageText": token(summary(_compat.to_legacy(e))["messageText"])} for e in new_events]
    expected = [{**{k: e[k] for k in ("event_type", "chatId", "messageId")}, "messageText": token(e["messageText"])} for e in old_events]
    assert [b for b in bridged if b["event_type"] == "CHAT_INITIALIZED"] == [e for e in expected if e["event_type"] == "CHAT_INITIALIZED"]
    old_messages = [e for e in expected if e["event_type"] == "NEW_MESSAGE"]
    new_messages = [b for b in bridged if b["event_type"] == "NEW_MESSAGE"]
    assert all(e in new_messages for e in old_messages)
    extra = [b for b in new_messages if b not in old_messages]
    assert extra == [{"event_type": "NEW_MESSAGE", "chatId": chat_id, "messageId": photo["id"], "messageText": None}]


async def test_legacy_style_handler_through_dispatcher():
    from playerokapi.client import Client
    dp = Dispatcher(Client(token="t"))
    dp["plbot"] = "BOT"
    seen = []

    async def old_plugin_handler(plbot, event):
        seen.append((plbot, type(event), event.message.text, event.type))

    bridge = Router("legacy")

    @bridge.new_message()
    async def call_legacy(plbot, event):
        await old_plugin_handler(plbot, _compat.to_legacy(event))

    dp.include_router(bridge)
    raw = {"id": "1", "text": "привет", "createdAt": "2026-11-03T10:33:07.252Z"}
    await dp.feed_event(ev.NewMessageEvent(m.ChatMessage.model_validate(raw), m.Chat(id="c"), raw={"chat": {"id": "c"}, "message": raw}))
    assert seen == [("BOT", legacy.NewMessageEvent, "привет", EventTypes.NEW_MESSAGE)]


def test_unknown_event_type():
    class Strange(ev.BaseEvent):
        pass
    with pytest.raises(TypeError):
        _compat.to_legacy(Strange())
