import asyncio
import logging

import pytest
from magic_filter import F

from playerokapi import models as m
from playerokapi.client import Client
from playerokapi.dispatcher import dispatcher as dispatcher_module
from playerokapi.dispatcher import events as ev
from playerokapi.dispatcher import Dispatcher, Router


def message_event(text="привет", chat_id="c1"):
    return ev.NewMessageEvent(m.ChatMessage(id=f"m-{text}", text=text), m.Chat(id=chat_id))


def deal_event(chat_id="c1"):
    return ev.NewDealEvent(m.Deal(id="d1", status=m.DealStatus.PAID), m.Chat(id=chat_id))


@pytest.fixture
def dp():
    return Dispatcher(Client(token="t"))


async def test_all_matching_handlers_run_in_registration_order(dp):
    calls = []
    bot, plugin, nested = Router("bot"), Router("plugin"), Router("nested")

    @bot.new_message()
    async def bot_first(event):
        calls.append("bot1")

    @bot.new_message()
    def bot_second_sync(event):
        calls.append("bot2")

    @plugin.new_message()
    async def plugin_handler(event):
        calls.append("plugin")

    @nested.new_message()
    async def nested_handler(event):
        calls.append("nested")

    @dp.new_message()
    async def dp_handler(event):
        calls.append("dp")

    plugin.include_router(nested)
    dp.include_routers(bot, plugin)
    await dp.feed_event(message_event())
    assert calls == ["dp", "bot1", "bot2", "plugin", "nested"]


async def test_filters_sync_async_and_magic(dp):
    calls = []
    router = dp.include_router(Router())

    async def is_help(event):
        return event.message.text.startswith("!help")

    @router.new_message(F.message.text.startswith("!"))
    async def magic(event):
        calls.append("magic")

    @router.new_message(is_help)
    async def async_filter(event):
        calls.append("async")

    @router.new_message(lambda e: e.chat.id == "c2")
    async def sync_filter(event):
        calls.append("sync")

    @router.new_message(F.message.text == "!help", lambda e: e.chat.id == "c1")
    async def both(event):
        calls.append("both")

    await dp.feed_event(message_event("!help"))
    assert calls == ["magic", "async", "both"]
    calls.clear()
    await dp.feed_event(message_event("обычное", chat_id="c2"))
    assert calls == ["sync"]


async def test_event_types_are_separated(dp):
    calls = []

    @dp.new_deal(F.deal.status == m.DealStatus.PAID)
    async def on_deal(event):
        calls.append(("deal", event.deal.id))

    @dp.new_message()
    async def on_message(event):
        calls.append("message")

    await dp.feed_event(deal_event())
    assert calls == [("deal", "d1")]


async def test_router_filter_blocks_whole_router(dp):
    calls = []
    plugin = Router()
    nested = plugin.include_router(Router())
    plugin.filter(lambda e: e.chat.id != "blacklisted")

    @plugin.new_message()
    async def h1(event):
        calls.append("h1")

    @nested.new_message()
    async def h2(event):
        calls.append("h2")

    @dp.new_message()
    async def always(event):
        calls.append("dp")

    dp.include_router(plugin)
    await dp.feed_event(message_event(chat_id="blacklisted"))
    assert calls == ["dp"]
    await dp.feed_event(message_event(chat_id="ok"))
    assert calls == ["dp", "dp", "h1", "h2"]


async def test_dependency_injection_by_name(dp):
    seen = {}
    dp["plbot"] = "BOT"
    router = dp.include_router(Router())

    @router.new_message()
    async def legacy_style(plbot, event):
        seen["legacy"] = (plbot, event.message.text)

    @router.new_message()
    async def short(e, client, router):
        seen["short"] = (e.message.text, client is dp.client, router.name)

    @router.new_message()
    async def everything(**kwargs):
        seen["kwargs"] = sorted(kwargs)

    @router.new_message()
    async def keyword_only(*, event, dispatcher):
        seen["kw"] = dispatcher is dp

    await dp.feed_event(message_event("x"))
    assert seen["legacy"] == ("BOT", "x")
    assert seen["short"] == ("x", True, router.name)
    assert seen["kwargs"] == ["client", "dispatcher", "event", "plbot", "router"]
    assert seen["kw"] is True


def test_reserved_context_names(dp):
    with pytest.raises(KeyError):
        dp["event"] = 1
    with pytest.raises(KeyError):
        Dispatcher(Client(token="t"), router=1)
    dp["x"] = 1
    assert dp["x"] == 1 and "x" in dp and dp.get("y", 2) == 2
    del dp["x"]
    assert "x" not in dp


async def test_errors_are_isolated_and_logged(dp, caplog):
    calls = []

    @dp.new_message()
    async def broken(event):
        raise ValueError("сломался")

    @dp.new_message()
    async def missing_param(event, nothing_here):
        calls.append("never")

    @dp.new_message()
    async def works(event):
        calls.append("works")

    with caplog.at_level(logging.ERROR, logger="playerokapi.dispatcher"):
        await dp.feed_event(message_event())
    assert calls == ["works"]
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "broken" in text and "сломался" in text and "missing_param" in text


async def test_exception_in_filter(dp, caplog):
    calls = []

    @dp.new_message(lambda e: 1 / 0)
    async def never(event):
        calls.append("never")

    @dp.new_message()
    async def works(event):
        calls.append("works")

    with caplog.at_level(logging.ERROR, logger="playerokapi.dispatcher"):
        await dp.feed_event(message_event())
    assert calls == ["works"]
    assert any("ZeroDivisionError" in r.getMessage() for r in caplog.records)


async def test_exception_in_router_filter_skips_router(dp, caplog):
    calls = []
    plugin = dp.include_router(Router())
    plugin.filter(lambda e: e.nope)

    @plugin.new_message()
    async def never(event):
        calls.append("never")

    with caplog.at_level(logging.ERROR, logger="playerokapi.dispatcher"):
        await dp.feed_event(message_event())
    assert calls == []
    assert caplog.records


async def test_error_handlers_nearest_router_first(dp):
    seen = []
    plugin = dp.include_router(Router("plugin"))
    nested = plugin.include_router(Router("nested"))

    @nested.new_message()
    async def broken(event):
        raise RuntimeError("boom")

    @plugin.error()
    async def plugin_errors(event, exception, handler_name):
        seen.append(("plugin", str(exception), handler_name.endswith("broken")))

    @dp.error()
    async def dp_errors(exception):
        seen.append(("dp", str(exception)))

    await dp.feed_event(message_event())
    assert seen == [("plugin", "boom", True)]

    @dp.new_message()
    async def broken_in_dp(event):
        raise RuntimeError("top")

    seen.clear()
    await dp.feed_event(message_event())
    assert seen == [("dp", "top"), ("plugin", "boom", True)]


async def test_broken_error_handler_is_logged(dp, caplog):
    @dp.new_message()
    async def broken(event):
        raise RuntimeError("a")

    @dp.error()
    async def broken_errors(exception):
        raise RuntimeError("b")

    with caplog.at_level(logging.ERROR, logger="playerokapi.dispatcher"):
        await dp.feed_event(message_event())
    assert any("broken_errors" in r.getMessage() for r in caplog.records)


async def test_remove_router_during_handler(dp):
    calls = []
    plugin = Router()

    @plugin.new_message()
    async def first(event, dispatcher):
        calls.append("first")
        dispatcher.remove_router(plugin)

    @plugin.new_message()
    async def second(event):
        calls.append("second")

    dp.include_router(plugin)
    await dp.feed_event(message_event())
    assert calls == ["first"]
    await dp.feed_event(message_event())
    assert calls == ["first"]
    dp.include_router(plugin)
    await dp.feed_event(message_event())
    assert calls == ["first", "first"]


def test_router_tree_validation():
    a, b, c = Router("a"), Router("b"), Router("c")
    a.include_router(b)
    b.include_router(c)
    with pytest.raises(RuntimeError):
        c.include_router(a)
    with pytest.raises(RuntimeError):
        Router().include_router(b)
    with pytest.raises(ValueError):
        a.include_router(a)
    with pytest.raises(ValueError):
        a.remove_router(c)


async def test_events_are_shared_and_mutable(dp):
    @dp.new_message()
    async def mutate(event):
        event.message.text = "изменено"

    seen = []
    router = dp.include_router(Router())

    @router.new_message()
    async def read(event):
        seen.append(event.message.text)

    await dp.feed_event(message_event())
    assert seen == ["изменено"]


async def test_answer_shortcut(dp, monkeypatch):
    sent = []

    async def send_message(chat_id, text=None, images=None, mark_chat_as_read=False):
        sent.append((chat_id, text, images, mark_chat_as_read))
        return m.ChatMessage(id="x", text=text)

    monkeypatch.setattr(dp.client, "send_message", send_message)

    @dp.new_message()
    async def reply(event):
        await event.answer("ответ", mark_chat_as_read=True)

    await dp.feed_event(message_event())
    assert sent == [("c1", "ответ", None, True)]
    with pytest.raises(RuntimeError):
        await ev.NewMessageEvent(m.ChatMessage(), m.Chat()).answer("x")


class FakeSource:
    instances = []

    def __init__(self, client, new_messages=True, new_reviews=True):
        self.client = client
        self._queue = asyncio.Queue()
        self.closed = False
        self.started = False
        FakeSource.instances.append(self)

    async def start(self):
        self.started = True

    async def close(self):
        self.closed = True


@pytest.fixture
def fake_source(monkeypatch):
    FakeSource.instances.clear()
    monkeypatch.setattr(dispatcher_module, "EventSource", FakeSource)
    return FakeSource.instances


async def wait_until(predicate, timeout=2.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while not predicate():
        if loop.time() > end:
            raise AssertionError("не дождался")
        await asyncio.sleep(0.005)


async def test_run_sequential_and_stop_from_handler(dp, fake_source):
    calls = []

    @dp.new_message()
    async def handler(event, dispatcher):
        calls.append(event.message.text)
        await asyncio.sleep(0.01)
        if event.message.text == "стоп":
            dispatcher.stop()

    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    source = fake_source[0]
    for text in ("a", "b", "стоп", "после"):
        source._queue.put_nowait(message_event(text))
    await asyncio.wait_for(run, 2)
    assert calls == ["a", "b", "стоп"]
    assert source.closed and not dp.running


async def test_run_twice_is_rejected(dp, fake_source):
    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: dp.running and fake_source)
    with pytest.raises(RuntimeError):
        await dp.run()
    dp.stop()
    await asyncio.wait_for(run, 2)


async def test_stop_from_outside_while_idle(dp, fake_source):
    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    dp.stop()
    await asyncio.wait_for(run, 2)
    assert fake_source[0].closed


async def test_cancel_run_closes_source(dp, fake_source):
    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    run.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run
    assert fake_source[0].closed and not dp.running


async def test_parallel_chats_keeps_order_inside_chat(fake_source):
    dp = Dispatcher(Client(token="t"), mode="parallel_chats")
    log = []
    gate = asyncio.Event()

    @dp.new_message()
    async def handler(event):
        log.append(("start", event.chat.id, event.message.text))
        if event.chat.id == "slow":
            await gate.wait()
        log.append(("end", event.chat.id, event.message.text))

    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    q = fake_source[0]._queue
    q.put_nowait(message_event("s1", "slow"))
    q.put_nowait(message_event("s2", "slow"))
    q.put_nowait(message_event("f1", "fast"))
    await wait_until(lambda: ("end", "fast", "f1") in log)
    assert ("start", "slow", "s2") not in log
    gate.set()
    await wait_until(lambda: ("end", "slow", "s2") in log)
    slow = [entry for entry in log if entry[1] == "slow"]
    assert slow == [("start", "slow", "s1"), ("end", "slow", "s1"), ("start", "slow", "s2"), ("end", "slow", "s2")]
    dp.stop()
    await asyncio.wait_for(run, 2)
    assert not dp._pending and not dp._chains


async def test_parallel_stop_cancels_hanging_handlers(fake_source):
    dp = Dispatcher(Client(token="t"), mode="parallel_chats")
    cancelled = asyncio.Event()

    @dp.new_message()
    async def hangs(event):
        try:
            await asyncio.sleep(100)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    fake_source[0]._queue.put_nowait(message_event())
    await asyncio.sleep(0.05)
    dp.stop()
    await asyncio.wait_for(run, 2)
    assert cancelled.is_set()
    assert not dp._pending


async def test_parallel_max_concurrency(fake_source):
    dp = Dispatcher(Client(token="t"), mode="parallel_chats", max_concurrency=2)
    active, peak = 0, 0

    @dp.new_message()
    async def handler(event):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1

    run = asyncio.ensure_future(dp.run())
    await wait_until(lambda: fake_source)
    for i in range(6):
        fake_source[0]._queue.put_nowait(message_event(str(i), chat_id=f"c{i}"))
    await asyncio.sleep(0.2)
    dp.stop()
    await asyncio.wait_for(run, 2)
    assert peak == 2


def test_bad_mode():
    with pytest.raises(ValueError):
        Dispatcher(Client(token="t"), mode="chaos")
    with pytest.raises(ValueError):
        Dispatcher(Client(token="t"), mode="parallel_chats", max_concurrency=0)


def test_on_accepts_string_event_type():
    router = Router()

    @router.on("NEW_DEAL")
    async def h(event):
        pass

    assert router.handlers[ev.EventType.NEW_DEAL][0].callback is h
    with pytest.raises(ValueError):
        router.on("SOMETHING")
