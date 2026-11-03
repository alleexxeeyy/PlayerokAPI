import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import pytest

from playerokapi import _gql, models as m
from playerokapi import enums as legacy_enums
from playerokapi.account import Account
from playerokapi.client import Client
from playerokapi.errors import HTTPError, UnauthorizedError
from playerokapi.threadsafe import ThreadsafeClient

from conftest import FakeResponse


FIXTURES = Path(__file__).parent / "fixtures" / "http" / "test.json"
ME = "me-id"

DATA_KEYS = {"GamePage": "game", "GamePageCategory": "gameCategory", "userChats": "chats", "SbpBankMembers": "sbpBankMembers"}
LIST_OPS = {"itemPriorityStatuses", "transactionProviders", "SbpBankMembers"}
UPLOAD_RESPONSE = {"id": "att-1", "url": "u", "chatId": "c", "clientAttachmentId": "x", "expiresAt": None}

PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 16


def data_key(operation):
    return DATA_KEYS.get(operation, operation)


def fake_data(operation):
    if operation == "uploadChatImageIntoTemporaryStore":
        return UPLOAD_RESPONSE
    return [] if operation in LIST_OPS else None


def strip_none(value):
    if isinstance(value, dict):
        return {k: strip_none(v) for k, v in value.items() if v is not None and k != "clientAttachmentId"}
    if isinstance(value, list):
        return [strip_none(v) for v in value]
    return value


class LegacyRecorder:
    def __init__(self):
        self.calls = []

    def request(self, acc, method, url, headers, payload=None, files=None, pass_304=True):
        if files:
            operations = json.loads(payload["operations"])
            operation, variables = operations["operationName"], operations["variables"]
            paths = sorted(p for paths in json.loads(payload["map"]).values() for p in paths)
            blobs = sorted(f[1] if isinstance(f[1], bytes) else f[1].read() for f in files.values())
        else:
            operation, variables = payload["operationName"], payload.get("variables")
            if isinstance(variables, str):
                variables = json.loads(variables)
            paths, blobs = [], []
        self.calls.append((operation, strip_none(variables or {}), paths, blobs))
        return FakeResponse(json={"data": {data_key(operation): fake_data(operation)}})


class NewRecorder:
    def __init__(self):
        self.calls = []

    async def execute(self, transport, operation, variables=None):
        self.calls.append((operation, strip_none(variables or {}), [], []))
        return {data_key(operation): fake_data(operation)}

    async def upload(self, transport, operation, variables, files):
        self.calls.append((operation, strip_none(variables), sorted(files), sorted(f[2] for f in files.values())))
        return {data_key(operation): fake_data(operation)}


@pytest.fixture
def legacy(monkeypatch):
    rec = LegacyRecorder()
    monkeypatch.setattr(Account, "_refresh_clients", lambda self: None)
    monkeypatch.setattr(Account, "request", lambda self, *a, **kw: rec.request(self, *a, **kw))
    if hasattr(Account, "instance"):
        monkeypatch.delattr(Account, "instance")
    acc = Account(token="t")
    acc.id = ME
    acc._is_initiated = True
    return acc, rec


@pytest.fixture
def client(monkeypatch):
    rec = NewRecorder()
    monkeypatch.setattr(_gql, "execute", rec.execute)
    monkeypatch.setattr(_gql, "upload", rec.upload)
    c = Client(token="t")
    c.me = m.AccountProfile(id=ME, username="me")
    return c, rec


L, N = legacy_enums, m

CASES = [
    ("get_user", dict(id="u")),
    ("get_user", dict(username="n")),
    ("get_deals", dict(statuses=[(L.ItemDealStatuses.PAID, N.DealStatus.PAID)], direction=(L.ItemDealDirections.OUT, N.DealDirection.OUT), count=10, after_cursor="c")),
    ("get_deals", dict()),
    ("get_deal", dict(deal_id="d")),
    ("update_deal", dict(deal_id="d", new_status=(L.ItemDealStatuses.SENT, N.DealStatus.SENT))),
    ("get_games", dict(name="x", type=(L.GameTypes.GAME, N.GameType.GAME), count=5)),
    ("get_game", dict(id="g")),
    ("get_game", dict(slug="s")),
    ("get_game_category", dict(id="c")),
    ("get_game_category", dict(game_id="g", slug="s")),
    ("get_game_category_agreements", dict(game_category_id="gc")),
    ("get_game_category_agreements", dict(game_category_id="gc", user_id="u2", after_cursor="a")),
    ("get_game_category_obtaining_types", dict(game_category_id="gc")),
    ("get_game_category_instructions", dict(game_category_id="gc", obtaining_type_id="ot", type=(L.GameCategoryInstructionTypes.FOR_SELLER, N.GameCategoryInstructionType.FOR_SELLER))),
    ("get_game_category_data_fields", dict(game_category_id="gc", obtaining_type_id="ot", type=(L.GameCategoryDataFieldTypes.ITEM_DATA, N.GameCategoryDataFieldType.ITEM_DATA))),
    ("get_chats", dict()),
    ("get_chats", dict(type=(L.ChatTypes.PM, N.ChatType.PM), status=(L.ChatStatuses.FINISHED, N.ChatStatus.FINISHED), after_cursor="c")),
    ("get_chat", dict(chat_id="c")),
    ("get_chat_messages", dict(chat_id="c", count=5, after_cursor="x")),
    ("mark_chat_as_read", dict(chat_id="c")),
    ("send_message", dict(chat_id="c", text="hi")),
    ("send_message", dict(chat_id="c", text="hi", mark_chat_as_read=True)),
    ("send_message", dict(chat_id="c", images=[PNG, PNG])),
    ("upload_chat_image_into_temporary_store", dict(image=PNG, chat_id="c")),
    ("create_item", dict(game_category_id="gc", obtaining_type_id="ot", name="n", price="100", description="d",
                         options={"region": "RU"}, data_fields=[], attachments=[PNG])),
    ("remove_item", dict(id="i")),
    ("publish_item", dict(item_id="i", priority_status_id="p")),
    ("get_my_items", dict()),
    ("get_my_items", dict(game_id="g", statuses=None, obtaining_type_id="o")),
    ("get_my_items", dict(category_id="c", statuses=[(L.ItemStatuses.EXPIRED, N.ItemStatus.EXPIRED)])),
    ("get_items", dict(category_id="c", obtaining_type_id="o")),
    ("get_items", dict(game_id="g", statuses=[(L.ItemStatuses.SOLD, N.ItemStatus.SOLD)], count=3)),
    ("get_item", dict(slug="s")),
    ("get_item", dict(id="i")),
    ("get_item_priority_statuses", dict(item_id="i", item_price="100")),
    ("increase_item_priority_status", dict(item_id="i", priority_status_id="p", payment_method_id=(L.TransactionPaymentMethodIds.MIR, N.TransactionPaymentMethodId.MIR))),
    ("increase_item_priority_status", dict(item_id="i", priority_status_id="p")),
    ("get_transaction_providers", dict(direction=(L.TransactionProviderDirections.OUT, N.TransactionProviderDirection.OUT))),
    ("get_transactions", dict()),
    ("get_transactions", dict(
        status=(L.TransactionStatuses.CONFIRMED, N.TransactionStatus.CONFIRMED),
        operation=(L.TransactionOperations.SELL, N.TransactionOperation.SELL),
        provider_id=(L.TransactionProviderIds.SBP, N.TransactionProviderId.SBP),
        min_value=1, max_value=500,
        from_date=datetime(2026, 1, 2, 3, 4, 5), to_date=datetime(2026, 2, 3, 4, 5, 6),
    )),
    ("get_sbp_bank_members", dict()),
    ("get_verified_cards", dict()),
    ("get_verified_cards", dict(direction=(L.SortDirections.DESC, N.SortDirection.DESC), count=3)),
    ("delete_card", dict(card_id="k")),
    ("request_withdrawal", dict(provider=(L.TransactionProviderIds.SBP, N.TransactionProviderId.SBP), account="+7", value=100, sbp_bank_member_id="b")),
    ("request_withdrawal", dict(provider=(L.TransactionProviderIds.BANK_CARD_RU, N.TransactionProviderId.BANK_CARD_RU), account="card", value=500,
                                payment_method_id=(L.TransactionPaymentMethodIds.MIR, N.TransactionPaymentMethodId.MIR))),
    ("remove_transaction", dict(transaction_id="t")),
    ("get_message_templates", dict()),
    ("report_deal_problem", dict(deal_id="d", description="desc", problem_type_id="p")),
    ("get_my_reviews", dict()),
    ("get_my_reviews", dict(rating=5, game_id="g", category_id="c", min_item_price=1, max_item_price=9, comment_required=True,
                            sort_direction=(L.SortDirections.ASC, N.SortDirection.ASC))),
    ("update_item", dict(id="i", name="n", price=5, description="d", remove_attachments=["a1"])),
]


def split(kwargs, index):
    def pick(v):
        if isinstance(v, tuple) and len(v) == 2:
            return v[index]
        if isinstance(v, list):
            return [pick(i) for i in v]
        return v
    return {k: pick(v) for k, v in kwargs.items()}


@pytest.mark.parametrize("method,kwargs", CASES, ids=[f"{c[0]}-{i}" for i, c in enumerate(CASES)])
async def test_same_request_as_legacy(method, kwargs, legacy, client):
    acc, legacy_rec = legacy
    new, new_rec = client
    try:
        getattr(acc, method)(**split(kwargs, 0))
    except (AttributeError, TypeError, KeyError):
        if not legacy_rec.calls:
            raise
    await getattr(new, method)(**split(kwargs, 1))
    assert new_rec.calls == legacy_rec.calls


def test_every_legacy_method_is_ported():
    skip = {"request", "get"}
    legacy_methods = {n for n in dir(Account) if not n.startswith("_") and callable(getattr(Account, n)) and n not in skip}
    new_methods = {n for n in dir(Client) if not n.startswith("_")}
    assert legacy_methods - new_methods == set()
    covered = {c[0] for c in CASES} | {"get_chat_by_username", "download_file"}
    assert legacy_methods - covered == set()


async def test_update_item_attachments_go_to_added_attachments(client):
    new, rec = client
    await new.update_item("i", add_attachments=[PNG])
    operation, variables, paths, blobs = rec.calls[0]
    assert operation == "updateItem"
    assert paths == ["variables.addedAttachments.0"]
    assert variables == {"input": {"id": "i"}, "addedAttachments": [None]}
    assert blobs == [PNG]


async def test_update_item_falsy_values_are_sent(client):
    new, rec = client
    await new.update_item("i", price=0, description="", options=[])
    assert rec.calls[0][1] == {"input": {"id": "i", "price": 0, "description": "", "attributes": {}}}


async def test_report_deal_problem_returns_deal(monkeypatch, client):
    new, _ = client

    async def execute(transport, operation, variables=None):
        return {"reportDealProblem": {"id": "d", "status": "SENT", "hasProblem": True}}

    monkeypatch.setattr(_gql, "execute", execute)
    deal = await new.report_deal_problem("d", "desc", "p")
    assert isinstance(deal, m.Deal) and deal.has_problem is True


def fixture_response(operation, predicate=lambda r: True):
    for rec in json.loads(FIXTURES.read_text(encoding="utf-8")):
        if rec["operation"] == operation and predicate(rec):
            return rec["response"]["data"]
    raise LookupError(operation)


def replay(monkeypatch, responses):
    calls = []

    async def execute(transport, operation, variables=None):
        calls.append((operation, variables))
        await asyncio.sleep(0.01)
        value = responses[operation]
        if isinstance(value, BaseException):
            raise value
        return value(variables) if callable(value) else value

    monkeypatch.setattr(_gql, "execute", execute)
    return calls


async def test_refresh_merges_viewer_and_user(monkeypatch):
    viewer = fixture_response("viewer")
    user = fixture_response("user", lambda r: r["response"]["data"]["user"]["__typename"] == "User")
    calls = replay(monkeypatch, {"viewer": viewer, "user": user})
    async with Client(token="t") as c:
        assert c.me.id == viewer["viewer"]["id"]
        assert c.id == c.me.id and c.username == viewer["viewer"]["username"]
        assert c.me.stats is not None and c.me.stats.deals is not None
        assert c.me.balance.available == user["user"]["balance"]["available"]
        assert c.me.balance.id == user["user"]["balance"]["id"]
        assert c.me.balance.value == viewer["viewer"]["balance"]["value"]
        assert c.me.can_publish_items == viewer["viewer"]["canPublishItems"]
        assert c.me.reviews_count == user["user"]["profile"]["testimonialCounter"]
    assert calls[1] == ("user", {"username": viewer["viewer"]["username"], "hasSupportAccess": False})


async def test_refresh_without_session_raises_unauthorized(monkeypatch):
    replay(monkeypatch, {"viewer": {"viewer": None}})
    with pytest.raises(UnauthorizedError):
        await Client(token="t").refresh()


async def test_methods_load_me_lazily_once(monkeypatch):
    viewer = fixture_response("viewer")
    user = fixture_response("user", lambda r: r["response"]["data"]["user"]["__typename"] == "User")
    chats = fixture_response("userChats")
    calls = replay(monkeypatch, {"viewer": viewer, "user": user, "userChats": chats})
    c = Client(token="t")
    pages = await asyncio.gather(*(c.get_chats() for _ in range(6)))
    assert [op for op, _ in calls].count("viewer") == 1
    assert [op for op, _ in calls].count("user") == 1
    assert pages[0].items and all(isinstance(ch, m.Chat) for ch in pages[0].items)
    assert calls[-1][1]["filter"]["userId"] == viewer["viewer"]["id"]


async def test_get_user_handles_both_typenames(monkeypatch):
    full = fixture_response("user", lambda r: r["response"]["data"]["user"]["__typename"] == "User")
    fragment = fixture_response("user", lambda r: r["response"]["data"]["user"]["__typename"] == "UserFragment")
    c = Client(token="t")
    replay(monkeypatch, {"user": full})
    assert (await c.get_user(username="x")).username == full["user"]["profile"]["username"]
    replay(monkeypatch, {"user": fragment})
    assert (await c.get_user(username="x")).username == fragment["user"]["username"]
    replay(monkeypatch, {"user": {"user": None}})
    assert await c.get_user(id="nope") is None
    with pytest.raises(TypeError):
        await c.get_user()


async def test_get_item_returns_class_by_typename(monkeypatch):
    c = Client(token="t")
    replay(monkeypatch, {"item": fixture_response("item", lambda r: r["response"]["data"]["item"]["__typename"] == "MyItem")})
    assert isinstance(await c.get_item(id="i"), m.MyItem)
    replay(monkeypatch, {"item": fixture_response("item", lambda r: r["response"]["data"]["item"]["__typename"] == "ForeignItem")})
    assert type(await c.get_item(id="i")) is m.Item


async def test_get_chat_by_username_pages_and_stops(monkeypatch, client):
    new, _ = client

    def page(variables):
        cursor = variables["pagination"]["after"]
        n = int(cursor or 0)
        users = [{"id": "u", "username": None}, {"id": "v", "username": "Target" if n == 2 else f"x{n}"}]
        return {"chats": {"edges": [{"node": {"id": f"chat{n}", "participants": users}}],
                          "pageInfo": {"hasNextPage": True, "endCursor": str(n + 1)}}}

    calls = replay(monkeypatch, {"userChats": page})
    chat = await new.get_chat_by_username("target")
    assert chat.id == "chat2" and len(calls) == 3
    calls.clear()
    assert await new.get_chat_by_username("nobody", max_pages=4) is None
    assert len(calls) == 4


async def test_send_message_requires_text_or_images(client):
    with pytest.raises(TypeError):
        await client[0].send_message("c")


async def test_images_from_path(tmp_path, client):
    new, rec = client
    path = tmp_path / "photo.jpg"
    path.write_bytes(b"\xff\xd8\xff" + b"1" * 10)
    await new.send_message("c", images=[path, str(path)])
    uploads = [c for c in rec.calls if c[0] == "uploadChatImageIntoTemporaryStore"]
    assert len(uploads) == 2
    assert rec.calls[-1][1]["input"]["imagesIds"] == ["att-1", "att-1"]


async def test_read_image_detects_type(tmp_path):
    from playerokapi.client.base import read_image
    assert await read_image(PNG) == ("image.png", "image/png", PNG)
    assert (await read_image(b"\xff\xd8\xff123"))[:2] == ("image.jpg", "image/jpeg")
    assert (await read_image(b"RIFF0000WEBP"))[:2] == ("image.webp", "image/webp")
    noext = tmp_path / "noext"
    noext.write_bytes(PNG)
    assert (await read_image(noext))[:2] == ("noext", "image/png")


async def test_transactions_dates_with_timezone(client):
    new, rec = client
    msk = timezone(__import__("datetime").timedelta(hours=3))
    await new.get_transactions(from_date=datetime(2026, 1, 2, 3, 0, tzinfo=msk))
    assert rec.calls[0][1]["filter"]["dateRange"]["from"] == "2026-01-02T00:00:00.000Z"


async def test_download_file(monkeypatch):
    c = Client(token="t")
    seen = {}

    async def request(method, url, headers=None, **kw):
        seen.update(method=method, url=url, headers=headers)
        return FakeResponse(200, text="bytes") if url.endswith("ok") else FakeResponse(404, text="nope")

    monkeypatch.setattr(c._transport, "request", request)
    assert await c.download_file("https://x/ok") == b"bytes"
    assert seen["headers"] == {"user-agent": c.user_agent}
    with pytest.raises(HTTPError):
        await c.download_file("https://x/missing")


def test_client_requires_credentials():
    with pytest.raises(TypeError):
        Client()
    assert Client(cookies="token=abc; __ddg1_=x").cookies == {"token": "abc", "__ddg1_": "x"}
    assert Client(token="abc", cookies="__ddg1_=x").cookies == {"__ddg1_": "x", "token": "abc"}
    assert Client(token="abc", cookies={"token": "zzz"}).cookies == {"token": "zzz"}
    for bad in ("__ddg1_=x", "мусор без равно", {"__ddg1_": "x"}):
        with pytest.raises(TypeError):
            Client(cookies=bad)


async def test_failed_enter_closes_transport(monkeypatch):
    replay(monkeypatch, {"viewer": {"viewer": None}})
    c = Client(token="t")
    closed = []

    async def close():
        closed.append(True)

    monkeypatch.setattr(c._transport, "close", close)
    with pytest.raises(UnauthorizedError):
        async with c:
            pass
    assert closed == [True]


async def test_refresh_keeps_viewer_data_if_user_fails(monkeypatch, caplog):
    from playerokapi.errors import GraphQLError
    viewer = fixture_response("viewer")
    replay(monkeypatch, {"viewer": viewer, "user": GraphQLError("user", [{"message": "boom"}])})
    c = Client(token="t")
    me = await c.refresh()
    assert me.id == viewer["viewer"]["id"] and c.id == me.id
    assert me.stats is None
    assert any("полный профиль" in r.getMessage() for r in caplog.records)


async def test_missing_key_in_response_raises(monkeypatch, client):
    from playerokapi.errors import PlayerokError
    new, _ = client
    replay(monkeypatch, {"chat": {"somethingElse": {}}})
    with pytest.raises(PlayerokError, match="нет поля chat"):
        await new.get_chat("c")


async def test_upload_without_id_stops_sending(monkeypatch, client):
    from playerokapi.errors import PlayerokError
    new, rec = client

    async def upload(transport, operation, variables, files):
        return {"uploadChatImageIntoTemporaryStore": {"url": "u"}}

    monkeypatch.setattr(_gql, "upload", upload)
    with pytest.raises(PlayerokError):
        await new.send_message("c", text="t", images=[PNG])
    assert not any(c[0] == "createChatMessage" for c in rec.calls)


async def test_legacy_enums_are_sent_by_name(client):
    new, rec = client
    await new.get_deals(statuses=[legacy_enums.ItemDealStatuses.PAID], direction=legacy_enums.ItemDealDirections.IN)
    assert rec.calls[0][1]["filter"]["status"] == ["PAID"]
    assert rec.calls[0][1]["filter"]["direction"] == "IN"


async def test_zero_transaction_values_are_sent(client):
    new, rec = client
    await new.get_transactions(min_value=0, max_value=0)
    assert rec.calls[0][1]["filter"]["value"] == {"min": "0", "max": "0"}


async def test_get_chat_by_username_without_limit_reads_until_end(monkeypatch, client):
    new, _ = client

    def page(variables):
        n = int(variables["pagination"]["after"] or 0)
        return {"chats": {"edges": [{"node": {"id": f"c{n}", "participants": [{"username": "x"}]}}],
                          "pageInfo": {"hasNextPage": n < 30, "endCursor": str(n + 1)}}}

    calls = replay(monkeypatch, {"userChats": page})
    assert await new.get_chat_by_username("nobody") is None
    assert len(calls) == 31


async def test_download_skips_body_checks(monkeypatch):
    c = Client(token="t")
    seen = {}

    async def request(method, url, headers=None, inspect_body=True, **kw):
        seen["inspect_body"] = inspect_body
        return FakeResponse(200, text="Just a moment... Cloudflare Ray ID")

    monkeypatch.setattr(c._transport, "request", request)
    assert await c.download_file("https://x/file.txt")
    assert seen["inspect_body"] is False


def test_legacy_imports_do_not_load_new_code():
    import subprocess, sys
    code = (
        "import sys, playerokapi.account, playerokapi.types, playerokapi.listener.listener\n"
        "from playerokapi import types, enums\n"
        "assert 'playerokapi.models' not in sys.modules and 'pydantic' not in sys.modules, sorted(m for m in sys.modules if 'pydantic' in m)[:3]\n"
        "from playerokapi import Client, Deal\n"
        "assert 'playerokapi.models' in sys.modules\n"
    )
    env_root = str(Path(__file__).resolve().parents[1])
    subprocess.run([sys.executable, "-c", code], cwd=env_root, check=True)


def test_threadsafe_client_can_be_copied_and_hides_private():
    import copy
    sync = ThreadsafeClient(Client(token="t"), asyncio.new_event_loop())
    assert copy.copy(sync).client is sync.client
    with pytest.raises(AttributeError):
        sync._transport


def test_threadsafe_client_with_stopped_loop():
    loop = asyncio.new_event_loop()
    sync = ThreadsafeClient(Client(token="t"), loop)
    with pytest.raises(RuntimeError, match="не запущен"):
        sync.get_chat("c")
    loop.close()
    with pytest.raises(RuntimeError):
        sync.get_chat("c")


async def test_threadsafe_passes_coroutine_timeout_error_through(monkeypatch, client):
    new, _ = client

    async def fails(chat_id):
        raise TimeoutError("свой таймаут")

    monkeypatch.setattr(new, "get_chat", fails)
    sync = ThreadsafeClient(new, asyncio.get_running_loop(), timeout=5)
    errors = []

    def worker():
        try:
            sync.get_chat("c")
        except TimeoutError as e:
            errors.append(str(e))

    thread = threading.Thread(target=worker)
    thread.start()
    while thread.is_alive():
        await asyncio.sleep(0.01)
    assert errors == ["свой таймаут"]


async def test_threadsafe_client_from_other_thread(client):
    new, rec = client
    sync = ThreadsafeClient(new, asyncio.get_running_loop(), timeout=5)
    result = {}

    def worker():
        result["chat"] = sync.get_chat("c")
        result["id"] = sync.id

    thread = threading.Thread(target=worker)
    thread.start()
    while thread.is_alive():
        await asyncio.sleep(0.01)
    assert rec.calls[0][0] == "chat"
    assert result["id"] == ME


async def test_threadsafe_client_in_loop_thread_raises(client):
    sync = ThreadsafeClient(client[0], asyncio.get_running_loop())
    with pytest.raises(RuntimeError, match="потока event loop"):
        sync.get_chat("c")


async def test_threadsafe_timeout_cancels(monkeypatch, client):
    new, _ = client
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def slow(chat_id):
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    monkeypatch.setattr(new, "get_chat", slow)
    sync = ThreadsafeClient(new, asyncio.get_running_loop(), timeout=0.05)
    errors = []
    thread = threading.Thread(target=lambda: errors.append(pytest.raises(TimeoutError, sync.get_chat, "c")))
    thread.start()
    while thread.is_alive():
        await asyncio.sleep(0.01)
    await asyncio.wait_for(cancelled.wait(), 1)
    assert len(errors) == 1
