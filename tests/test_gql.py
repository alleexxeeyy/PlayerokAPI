import json

import pytest

from playerokapi import _gql
from playerokapi._queries import PERSISTED_QUERIES, QUERIES
from playerokapi.errors import GraphQLError, HTTPError

from conftest import FakeResponse


async def test_persisted_query_is_get_with_hash(transport, fake_sessions):
    factory = fake_sessions([FakeResponse(json={"data": {"chats": {"edges": []}}})])
    data = await _gql.execute(transport, "userChats", {"pagination": {"first": 24}})

    assert data == {"chats": {"edges": []}}
    call = factory.calls[0]
    assert call["method"] == "GET"
    assert call["params"]["operationName"] == "userChats"
    assert json.loads(call["params"]["variables"]) == {"pagination": {"first": 24}}
    extensions = json.loads(call["params"]["extensions"])
    assert extensions["persistedQuery"]["sha256Hash"] == PERSISTED_QUERIES["userChats"]
    assert call["headers"]["x-gql-op"] == "userChats"


async def test_full_query_is_post(transport, fake_sessions):
    factory = fake_sessions([FakeResponse(json={"data": {"viewer": {"id": "1"}}})])
    data = await _gql.execute(transport, "viewer")

    assert data == {"viewer": {"id": "1"}}
    call = factory.calls[0]
    assert call["method"] == "POST"
    assert call["json"] == {"operationName": "viewer", "query": QUERIES["viewer"], "variables": {}}


async def test_unknown_operation(transport):
    with pytest.raises(KeyError):
        await _gql.execute(transport, "nope")


async def test_graphql_errors_raise_even_with_200(transport, fake_sessions):
    fake_sessions([FakeResponse(json={
        "errors": [{"message": "Сделка не найдена", "extensions": {"code": "NOT_FOUND", "statusCode": 404}}],
        "data": None
    })])
    with pytest.raises(GraphQLError) as e:
        await _gql.execute(transport, "deal", {"id": "x"})
    assert e.value.code == "NOT_FOUND"
    assert e.value.status_code == 404
    assert str(e.value) == "Сделка не найдена"


async def test_http_error_status(transport, fake_sessions):
    fake_sessions([FakeResponse(500, text="oops")])
    with pytest.raises(HTTPError) as e:
        await _gql.execute(transport, "viewer")
    assert e.value.status_code == 500


async def test_not_graphql_body(transport, fake_sessions):
    fake_sessions([FakeResponse(200, text="<html></html>")])
    with pytest.raises(HTTPError, match="не похож на GraphQL"):
        await _gql.execute(transport, "viewer")


async def test_upload_builds_multipart(transport, fake_sessions, monkeypatch):
    built = []

    def fake_build(form, files):
        built.append((form, files))
        return None

    monkeypatch.setattr("playerokapi._http._build_mime", fake_build)
    factory = fake_sessions([FakeResponse(json={"data": {"uploadChatImageIntoTemporaryStore": {"id": "a"}}})])

    data = await _gql.upload(
        transport,
        "uploadChatImageIntoTemporaryStore",
        {"file": None, "input": {"chatId": "c"}},
        {"variables.file": ("image.png", "image/png", b"\x89PNG")}
    )

    assert data == {"uploadChatImageIntoTemporaryStore": {"id": "a"}}
    form, files = built[0]
    assert json.loads(form["map"]) == {"1": ["variables.file"]}
    assert json.loads(form["operations"])["variables"] == {"file": None, "input": {"chatId": "c"}}
    assert files == [("1", "image.png", "image/png", b"\x89PNG")]
    assert "content-type" not in factory.calls[0]["headers"]


async def test_mutation_is_sent_as_not_idempotent(transport, monkeypatch):
    seen = {}

    async def fake_request(method, url, **kwargs):
        seen[kwargs["json"]["operationName"]] = kwargs.get("idempotent", True)
        return FakeResponse(json={"data": {}})

    monkeypatch.setattr(transport, "request", fake_request)
    await _gql.execute(transport, "viewer")
    await _gql.execute(transport, "createChatMessage", {"input": {}})
    assert seen == {"viewer": True, "createChatMessage": False}


async def test_304_is_an_error(transport, fake_sessions):
    fake_sessions([FakeResponse(304, text="")])
    with pytest.raises(HTTPError):
        await _gql.execute(transport, "viewer")


def test_graphql_error_with_strange_errors():
    assert GraphQLError("op", ["boom"]).code is None
    assert GraphQLError("op", [{"message": "m", "extensions": "x"}]).message == "m"
    assert GraphQLError("op", []).message == ""
