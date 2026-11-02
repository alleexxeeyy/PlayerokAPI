import asyncio
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
from curl_cffi import AsyncSession, CurlECode, CurlError
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError

from playerokapi import _http
from playerokapi.errors import BotCheckError, NetworkError

from conftest import FakeResponse, ok


def curl_error(code: CurlECode) -> CurlConnectionError:
    return CurlConnectionError(f"curl: ({int(code)}) {code.name}", code)


def test_parse_cookies_string_keeps_equals_in_value():
    cookies = _http.parse_cookies("token=abc; __ddg5_=x=y==; empty")
    assert cookies == {"token": "abc", "__ddg5_": "x=y=="}


@pytest.mark.parametrize("cookies", [None, "", "   ", {}])
def test_parse_cookies_falls_back_to_token(cookies):
    assert _http.parse_cookies(cookies, token="abc", ddg5="d") == {"token": "abc", "__ddg5_": "d"}


@pytest.mark.parametrize("proxy, expected", [
    (None, None),
    ("user:pass@1.2.3.4:80", "http://user:pass@1.2.3.4:80"),
    ("https://1.2.3.4:80", "http://1.2.3.4:80"),
    ("us:phttp://x@1.2.3.4:80", "http://us:phttp://x@1.2.3.4:80"),
    ("socks5://user:pass@1.2.3.4:1080", "socks5://user:pass@1.2.3.4:1080"),
])
def test_make_proxy_url(proxy, expected):
    assert _http.make_proxy_url(proxy) == expected


@pytest.mark.parametrize("kwargs", [
    {"max_concurrent_requests": 0}, {"retries": 0}, {"rate_limit_retries": 0}
])
def test_invalid_limits(kwargs):
    with pytest.raises(ValueError):
        _http.Transport(cookies={}, **kwargs)


def test_cert_is_copied_once_into_private_dir():
    first = _http.Transport(cookies={}).cert_path
    second = _http.Transport(cookies={}).cert_path
    assert first == second
    assert os.path.basename(os.path.dirname(first)).startswith("playerokapi_")
    assert os.path.getsize(first) == os.path.getsize(os.path.join(os.path.dirname(_http.__file__), "cacert.pem"))


def test_graphql_headers_match_legacy_account(monkeypatch):
    from playerokapi.account import Account

    monkeypatch.setattr(Account, "_refresh_clients", lambda self: None)

    captured = {}

    class LegacyCurlSession:
        def get(self, url, params=None, headers=None, timeout=None):
            captured.update(headers)
            return FakeResponse(json={"data": {"chat": None}})

        def close(self):
            pass

    acc = Account(token="t", ddg5="d", user_agent="UA/1.0")
    acc._Account__curl_session = LegacyCurlSession()
    acc.get_chat("x")

    transport = _http.Transport(cookies=acc.cookies, user_agent=acc.user_agent)
    assert transport.graphql_headers("chat") == captured


async def test_retries_network_error_with_new_session(transport, fake_sessions):
    factory = fake_sessions([CurlError("reset"), ok()])
    resp = await transport.request("GET", _http.GRAPHQL_URL)
    assert resp.status_code == 200
    assert len(factory.sessions) == 2
    assert factory.sessions[0].closed
    assert not factory.sessions[1].closed


async def test_network_error_after_all_retries(transport, fake_sessions):
    factory = fake_sessions([CurlError("a"), OSError("b"), CurlError("c")])
    with pytest.raises(NetworkError) as e:
        await transport.request("GET", _http.GRAPHQL_URL)
    assert e.value.error == "c"
    assert len(factory.calls) == 3
    assert all(s.closed for s in factory.sessions)


async def test_programming_errors_are_not_retried(transport, fake_sessions):
    factory = fake_sessions([TypeError("bug")])
    with pytest.raises(TypeError):
        await transport.request("GET", _http.GRAPHQL_URL)
    assert len(factory.calls) == 1


async def test_mutation_is_not_retried_after_read_error(transport, fake_sessions):
    factory = fake_sessions([curl_error(CurlECode.RECV_ERROR), ok()])
    with pytest.raises(NetworkError):
        await transport.request("POST", _http.GRAPHQL_URL, idempotent=False)
    assert len(factory.calls) == 1


async def test_mutation_is_retried_when_not_sent(transport, fake_sessions):
    factory = fake_sessions([curl_error(CurlECode.COULDNT_CONNECT), ok()])
    resp = await transport.request("POST", _http.GRAPHQL_URL, idempotent=False)
    assert resp.status_code == 200
    assert len(factory.calls) == 2


async def test_rate_limit_backoff_uses_retry_after(transport, fake_sessions, sleeps):
    fake_sessions([FakeResponse(429, headers={"Retry-After": "7"}), FakeResponse(503), ok()])
    resp = await transport.request("GET", _http.GRAPHQL_URL)
    assert resp.status_code == 200
    assert len(sleeps) == 2
    assert 7.2 <= sleeps[0] <= 7.8
    assert 10.2 <= sleeps[1] <= 10.8


@pytest.mark.parametrize("value", ["inf", "nan", "-5", "Wed, 21 Oct 2015 07:28:00 GMT"])
async def test_bad_retry_after_falls_back(transport, fake_sessions, sleeps, value):
    fake_sessions([FakeResponse(429, headers={"Retry-After": value}), ok()])
    await transport.request("GET", _http.GRAPHQL_URL)
    assert 5.2 <= sleeps[0] <= 5.8


async def test_retry_after_is_capped(transport, fake_sessions, sleeps):
    fake_sessions([FakeResponse(429, headers={"Retry-After": "100000"}), ok()])
    await transport.request("GET", _http.GRAPHQL_URL)
    assert sleeps[0] <= _http.MAX_RETRY_AFTER + 1


async def test_rate_limit_gives_up_without_extra_sleep(transport, fake_sessions, sleeps):
    fake_sessions([FakeResponse(429) for _ in range(6)])
    resp = await transport.request("GET", _http.GRAPHQL_URL)
    assert resp.status_code == 429
    assert len(sleeps) == 5


async def test_mutation_retries_429_but_not_502(transport, fake_sessions):
    factory = fake_sessions([FakeResponse(429), ok(), FakeResponse(502)])
    assert (await transport.request("POST", _http.GRAPHQL_URL, idempotent=False)).status_code == 200
    assert (await transport.request("POST", _http.GRAPHQL_URL, idempotent=False)).status_code == 502
    assert len(factory.calls) == 3


async def test_rate_limit_text_in_html_page(transport, fake_sessions, sleeps):
    fake_sessions([FakeResponse(200, text="<html>502 Bad Gateway</html>", headers={"content-type": "text/html"}), ok()])
    await transport.request("GET", _http.GRAPHQL_URL)
    assert len(sleeps) == 1


async def test_rate_limit_words_inside_json_are_ignored(transport, fake_sessions, sleeps):
    fake_sessions([ok({"text": "Service Unavailable"})])
    await transport.request("GET", _http.GRAPHQL_URL)
    assert sleeps == []


async def test_bot_check_detected(transport, fake_sessions):
    fake_sessions([FakeResponse(403, text="<title>Just a moment...</title>")])
    with pytest.raises(BotCheckError):
        await transport.request("GET", _http.GRAPHQL_URL)


async def test_bot_check_signs_inside_json_are_ignored(transport, fake_sessions):
    fake_sessions([ok({"message": {"text": "Just a moment... Cloudflare Ray ID"}})])
    resp = await transport.request("GET", _http.GRAPHQL_URL)
    assert resp.status_code == 200


async def test_rate_limit_pause_is_shared(transport, fake_sessions, sleeps):
    fake_sessions([FakeResponse(429, headers={"Retry-After": "10"}), ok(), ok()])
    first = asyncio.create_task(transport.request("GET", _http.GRAPHQL_URL))
    await asyncio.sleep(0)
    second = asyncio.create_task(transport.request("GET", _http.GRAPHQL_URL))
    await asyncio.gather(first, second)
    assert len(sleeps) >= 2 and all(9.5 <= s <= 11 for s in sleeps[:2])


async def test_semaphore_limits_concurrency(fake_sessions):
    active = peak = 0

    async def slow():
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return ok()

    fake_sessions([slow] * 5)
    transport = _http.Transport(cookies={}, max_concurrent_requests=2)
    await asyncio.gather(*(transport.request("GET", _http.GRAPHQL_URL) for _ in range(5)))
    assert peak == 2


async def test_failed_session_is_closed_only_after_neighbours_finish(fake_sessions):
    release = asyncio.Event()

    async def slow_ok():
        await release.wait()
        return ok()

    async def fail():
        raise CurlError("reset")

    factory = fake_sessions([slow_ok, fail, ok()])
    transport = _http.Transport(cookies={}, max_concurrent_requests=2)
    slow_task = asyncio.create_task(transport.request("GET", _http.GRAPHQL_URL))
    await asyncio.sleep(0)
    await transport.request("GET", _http.GRAPHQL_URL)

    old = factory.sessions[0]
    assert not old.closed
    release.set()
    await slow_task
    assert old.closed
    assert not factory.sessions[1].closed


async def test_other_event_loop_is_rejected_even_under_contention(fake_sessions):
    gate = asyncio.Event()

    async def blocked():
        await gate.wait()
        return ok()

    fake_sessions([blocked, ok()])
    transport = _http.Transport(cookies={})
    busy = asyncio.create_task(transport.request("GET", _http.GRAPHQL_URL))
    await asyncio.sleep(0)

    def run_in_new_loop():
        return asyncio.run(transport.request("GET", _http.GRAPHQL_URL))

    with pytest.raises(RuntimeError, match="другом event loop"):
        await asyncio.to_thread(run_in_new_loop)
    gate.set()
    await busy


async def test_close_allows_reuse_in_new_loop(fake_sessions):
    async def tick():
        await asyncio.sleep(0.001)
        return ok()

    factory = fake_sessions([tick] * 6)
    transport = _http.Transport(cookies={})
    await asyncio.gather(*(transport.request("GET", _http.GRAPHQL_URL) for _ in range(3)))
    await transport.close()
    assert factory.sessions[0].closed

    async def again():
        await asyncio.gather(*(transport.request("GET", _http.GRAPHQL_URL) for _ in range(3)))
        await transport.close()

    await asyncio.to_thread(asyncio.run, again())
    assert len(factory.calls) == 6
    assert all(s.closed for s in factory.sessions)


async def test_real_async_session_and_mime_are_created(transport):
    session = transport._new_session()
    assert isinstance(session, AsyncSession)
    await session.close()

    mime = _http._build_mime({"operations": "{}"}, [("1", "a.png", "image/png", b"\x89PNG")])
    mime.close()


def test_build_mime_closes_on_error(monkeypatch):
    closed = []

    class BrokenMime:
        def addpart(self, **kwargs):
            raise ValueError("bad part")

        def close(self):
            closed.append(True)

    monkeypatch.setattr(_http, "CurlMime", BrokenMime)
    with pytest.raises(ValueError):
        _http._build_mime({"a": "b"}, None)
    assert closed == [True]


@pytest.fixture
def local_server():
    received = []

    class Handler(BaseHTTPRequestHandler):
        def _reply(self):
            length = int(self.headers.get("content-length") or 0)
            received.append({
                "method": self.command,
                "path": self.path,
                "headers": {k.lower(): v for k, v in self.headers.items()},
                "body": self.rfile.read(length) if length else b"",
            })
            body = json.dumps({"data": {"ok": True}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = do_POST = _reply

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/graphql", received
    server.shutdown()


async def test_real_requests_reach_server(local_server):
    url, received = local_server
    transport = _http.Transport(cookies={"token": "t"}, user_agent="UA/1.0")
    try:
        headers = transport.graphql_headers("chat")
        await transport.request("GET", url, headers=headers, params={"operationName": "chat", "variables": '{"id": "x"}'})

        upload_headers = transport.graphql_headers("upload")
        del upload_headers["content-type"]
        await transport.request(
            "POST", url, headers=upload_headers,
            form={"operations": '{"query": "q"}', "map": '{"1": ["variables.file"]}'},
            files=[("1", "image.png", "image/png", b"\x89PNG-bytes")],
            idempotent=False
        )
    finally:
        await transport.close()

    get, post = received
    assert parse_qs(urlparse(get["path"]).query) == {"operationName": ["chat"], "variables": ['{"id": "x"}']}
    assert get["headers"]["cookie"] == "token=t"
    assert get["headers"]["x-gql-op"] == "chat"
    assert get["headers"]["user-agent"] == "UA/1.0"

    assert post["headers"]["content-type"].startswith("multipart/form-data; boundary=")
    assert b'name="operations"' in post["body"] and b'{"query": "q"}' in post["body"]
    assert b'name="map"' in post["body"]
    assert b'filename="image.png"' in post["body"] and b"\x89PNG-bytes" in post["body"]
