import asyncio
import threading
import time

import pytest

from playerokapi import _http
from playerokapi._http import RequestGate, Transport
from playerokapi.client import Client

from conftest import FakeResponse, ok


class Meter:
    def __init__(self):
        self.active = 0
        self.peak = 0
        self.lock = threading.Lock()
        self.starts: list[float] = []

    def enter(self):
        with self.lock:
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.starts.append(time.monotonic())

    def leave(self):
        with self.lock:
            self.active -= 1


class MeteredSession:
    def __init__(self, meter: Meter, script=None, delay=0.02):
        self.meter = meter
        self.script = script
        self.delay = delay
        self.calls = 0

    async def request(self, method, url, **kwargs):
        self.meter.enter()
        try:
            await asyncio.sleep(self.delay)
            self.calls += 1
            if self.script:
                return self.script.pop(0)
            return ok({})
        finally:
            self.meter.leave()

    async def close(self):
        pass


def transport_with(gate, session, **kw):
    t = Transport(cookies={"token": "t"}, request_gate=gate, **kw)
    t._new_session = lambda: session
    return t


def test_gate_validation():
    with pytest.raises(ValueError):
        RequestGate(0)
    with pytest.raises(ValueError):
        RequestGate(min_interval=-1)


async def test_two_transports_share_one_slot():
    gate, meter = RequestGate(), Meter()
    a = transport_with(gate, MeteredSession(meter))
    b = transport_with(gate, MeteredSession(meter))
    await asyncio.gather(*(t.request("GET", _http.GRAPHQL_URL) for t in (a, b) for _ in range(5)))
    assert meter.peak == 1
    assert gate.active == 0


async def test_async_and_sync_threads_share_one_slot():
    gate, meter = RequestGate(), Meter()
    t = transport_with(gate, MeteredSession(meter))

    def sync_worker():
        for _ in range(5):
            with gate.hold():
                meter.enter()
                time.sleep(0.01)
                meter.leave()

    threads = [threading.Thread(target=sync_worker) for _ in range(3)]
    for th in threads:
        th.start()
    await asyncio.gather(*(t.request("GET", _http.GRAPHQL_URL) for _ in range(10)))
    while any(th.is_alive() for th in threads):
        await asyncio.sleep(0.01)
    assert meter.peak == 1
    assert gate.active == 0


async def test_rate_limit_in_async_pauses_sync_side():
    gate, meter = RequestGate(), Meter()
    limited = FakeResponse(429, text="Too Many Requests", headers={"Retry-After": "0.3"})
    t = transport_with(gate, MeteredSession(meter, script=[limited, ok({})], delay=0))
    request = asyncio.ensure_future(t.request("GET", _http.GRAPHQL_URL))
    while gate.remaining_pause() == 0 and not request.done():
        await asyncio.sleep(0.005)
    started = time.monotonic()
    waited = []

    def sync_call():
        with gate.hold():
            waited.append(time.monotonic() - started)

    th = threading.Thread(target=sync_call)
    th.start()
    resp = await request
    while th.is_alive():
        await asyncio.sleep(0.01)
    assert resp.status_code == 200
    assert waited and waited[0] >= 0.25


async def test_sync_pause_holds_async_requests():
    gate, meter = RequestGate(), Meter()
    t = transport_with(gate, MeteredSession(meter, delay=0))
    gate.pause(0.3)
    started = time.monotonic()
    await t.request("GET", _http.GRAPHQL_URL)
    assert time.monotonic() - started >= 0.25


async def test_min_interval_spaces_request_starts():
    gate, meter = RequestGate(min_interval=0.1), Meter()
    t = transport_with(gate, MeteredSession(meter, delay=0))
    await asyncio.gather(*(t.request("GET", _http.GRAPHQL_URL) for _ in range(4)))
    gaps = [b - a for a, b in zip(meter.starts, meter.starts[1:])]
    assert len(gaps) == 3 and all(g >= 0.09 for g in gaps)


async def test_slot_released_after_network_error():
    gate = RequestGate()

    class Broken:
        async def request(self, *a, **kw):
            raise OSError("нет сети")

        async def close(self):
            pass

    t = transport_with(gate, Broken(), retries=1)
    with pytest.raises(Exception):
        await t.request("GET", _http.GRAPHQL_URL)
    assert gate.active == 0
    with gate.hold():
        assert gate.active == 1


async def test_slot_released_when_cancelled():
    gate = RequestGate()
    t = transport_with(gate, MeteredSession(Meter(), delay=10))
    task = asyncio.ensure_future(t.request("GET", _http.GRAPHQL_URL))
    while gate.active == 0:
        await asyncio.sleep(0.005)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert gate.active == 0


async def test_gate_with_two_slots():
    gate, meter = RequestGate(max_concurrent_requests=2), Meter()
    t = transport_with(gate, MeteredSession(meter))
    await asyncio.gather(*(t.request("GET", _http.GRAPHQL_URL) for _ in range(6)))
    assert meter.peak == 2


def test_client_takes_limit_from_gate():
    gate = RequestGate(max_concurrent_requests=3)
    c = Client(token="t", request_gate=gate)
    assert c._transport.request_gate is gate
    assert c._transport.max_concurrent_requests == 3
    assert Client(token="t")._transport.request_gate is None


def test_release_without_acquire_is_harmless():
    gate = RequestGate()
    gate.release()
    assert gate.active == 0


async def test_sync_waiter_gets_slot_right_after_async_release():
    gate = RequestGate()
    t = transport_with(gate, MeteredSession(Meter(), delay=0.2))
    request = asyncio.ensure_future(t.request("GET", _http.GRAPHQL_URL))
    while gate.active == 0:
        await asyncio.sleep(0.005)
    got = []

    def sync_call():
        with gate.hold():
            got.append(time.monotonic())

    th = threading.Thread(target=sync_call)
    th.start()
    await request
    released = time.monotonic()
    while th.is_alive():
        await asyncio.sleep(0.005)
    assert got and got[0] - released < 0.1


async def test_sync_side_is_not_starved_by_async_loop():
    gate = RequestGate()
    order = []
    t = transport_with(gate, MeteredSession(Meter(), delay=0.01))

    async def hammer():
        # следующий запрос сразу после предыдущего — раньше такой цикл перехватывал место у потоков
        for i in range(30):
            await t.request("GET", _http.GRAPHQL_URL)
            order.append(("async", i))

    task = asyncio.ensure_future(hammer())
    await asyncio.sleep(0.05)

    def sync_call():
        with gate.hold():
            order.append(("sync", 0))

    th = threading.Thread(target=sync_call)
    th.start()
    arrived = len(order)
    await task
    while th.is_alive():
        await asyncio.sleep(0.005)
    assert order.index(("sync", 0)) - arrived <= 2, order


async def test_pause_is_set_before_slot_is_released():
    gate = RequestGate()
    limited = FakeResponse(429, text="Too Many Requests", headers={"Retry-After": "0.4"})
    t = transport_with(gate, MeteredSession(Meter(), script=[limited, ok({})], delay=0.05))
    request = asyncio.ensure_future(t.request("GET", _http.GRAPHQL_URL))
    while gate.active == 0:
        await asyncio.sleep(0.002)
    sent_at = []

    def sync_call():
        with gate.hold():
            sent_at.append(gate.remaining_pause())

    th = threading.Thread(target=sync_call)
    th.start()
    await request
    while th.is_alive():
        await asyncio.sleep(0.005)
    assert sent_at and sent_at[0] == 0


async def test_last_attempt_still_pauses_everyone():
    gate = RequestGate()
    limited = FakeResponse(429, text="Too Many Requests", headers={"Retry-After": "0.3"})
    t = transport_with(gate, MeteredSession(Meter(), script=[limited], delay=0), rate_limit_retries=1)
    resp = await t.request("GET", _http.GRAPHQL_URL)
    assert resp.status_code == 429
    assert gate.remaining_pause() > 0.2


async def test_sync_hold_from_loop_with_pending_async_request_raises():
    gate = RequestGate()
    t = transport_with(gate, MeteredSession(Meter(), delay=0.1))
    request = asyncio.ensure_future(t.request("GET", _http.GRAPHQL_URL))
    while gate.active == 0:
        await asyncio.sleep(0.005)
    with pytest.raises(RuntimeError, match="зависание"):
        with gate.hold():
            pass
    await request
    with gate.hold():
        assert gate.active == 1


def test_sync_hold_is_reentrant_in_one_thread():
    gate = RequestGate()
    with gate.hold():
        with gate.hold():
            assert gate.active == 1
        assert gate.active == 1
    assert gate.active == 0


async def test_cancelled_async_waiter_leaves_queue():
    gate = RequestGate()
    gate.acquire()
    waiter = asyncio.ensure_future(gate.acquire_async())
    await asyncio.sleep(0.02)
    waiter.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter
    gate.release()
    assert gate.active == 0
    await asyncio.wait_for(gate.acquire_async(), 1)
    assert gate.active == 1
    gate.release_async()
    assert gate.active == 0


async def test_fifo_order_across_sides():
    gate = RequestGate()
    gate.acquire()
    order = []

    async def async_side(i):
        await gate.acquire_async()
        order.append(f"a{i}")
        gate.release_async()

    def sync_side(i):
        with gate.hold():
            order.append(f"s{i}")

    tasks = []
    threads = []
    for i in range(3):
        tasks.append(asyncio.ensure_future(async_side(i)))
        await asyncio.sleep(0.02)
        th = threading.Thread(target=sync_side, args=(i,))
        th.start()
        threads.append(th)
        await asyncio.sleep(0.02)
    gate.release()
    await asyncio.gather(*tasks)
    while any(th.is_alive() for th in threads):
        await asyncio.sleep(0.005)
    assert order == ["a0", "s0", "a1", "s1", "a2", "s2"]
