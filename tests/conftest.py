from __future__ import annotations

import asyncio
import json as jsonlib

import pytest

from playerokapi import _http


class FakeHeaders(dict):
    def __init__(self, data: dict | None = None):
        super().__init__({k.lower(): v for k, v in (data or {}).items()})

    def get(self, key, default=None):
        return super().get(key.lower(), default)


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        text: str = "",
        headers: dict | None = None,
        url: str = _http.GRAPHQL_URL,
        json: dict | None = None
    ):
        if json is not None:
            text = jsonlib.dumps(json)
            headers = {"content-type": "application/json", **(headers or {})}
        self.status_code = status_code
        self.text = text
        self.headers = FakeHeaders(headers)
        self.url = url
        self.content = text.encode()

    def json(self):
        return jsonlib.loads(self.text)


def ok(data: dict | None = None) -> FakeResponse:
    return FakeResponse(json={"data": data or {}})


class FakeSession:
    def __init__(self, script: list):
        self.script = script
        self.calls: list[dict] = []
        self.closed = False

    async def request(self, method, url, **kwargs):
        assert not self.closed, "запрос на закрытой сессии"
        self.calls.append({"method": method, "url": url, **kwargs})
        item = self.script.pop(0)
        if callable(item):
            item = await item()
        if isinstance(item, BaseException):
            raise item
        return item

    async def close(self):
        self.closed = True


class SessionFactory:
    def __init__(self, script: list):
        self.script = script
        self.sessions: list[FakeSession] = []

    def __call__(self):
        session = FakeSession(self.script)
        self.sessions.append(session)
        return session

    @property
    def calls(self) -> list[dict]:
        return [call for s in self.sessions for call in s.calls]


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float):
        self.sleeps.append(delay)
        target = self.now + delay
        for _ in range(3):
            await asyncio.sleep(0)
        self.now = max(self.now, target)


@pytest.fixture
def clock(monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(_http, "_now", fake)
    monkeypatch.setattr(_http, "_sleep", fake.sleep)
    return fake


@pytest.fixture
def sleeps(clock):
    return clock.sleeps


@pytest.fixture
def fake_sessions(monkeypatch, clock):
    def install(script: list) -> SessionFactory:
        factory = SessionFactory(script)
        monkeypatch.setattr(_http.Transport, "_new_session", lambda self: factory())
        return factory
    return install


@pytest.fixture
def transport():
    return _http.Transport(cookies={"token": "t", "__ddg5_": "d"}, user_agent="UA/1.0")
