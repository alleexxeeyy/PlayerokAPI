from __future__ import annotations

import json
from typing import Any

from curl_cffi import Response

from ._http import GRAPHQL_URL, Transport
from ._queries import PERSISTED_QUERIES, QUERIES
from .errors import GraphQLError, HTTPError


def _is_mutation(operation: str) -> bool:
    return QUERIES.get(operation, "").lstrip().startswith("mutation")


def _parse_response(operation: str, resp: Response) -> dict[str, Any]:
    try: data = resp.json()
    except ValueError: data = None

    if isinstance(data, dict) and data.get("errors"):
        raise GraphQLError(operation, data["errors"])
    if resp.status_code != 200:
        raise HTTPError(str(resp.url), resp.status_code, resp.text or "")
    if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
        raise HTTPError(str(resp.url), resp.status_code, f"Ответ не похож на GraphQL: {(resp.text or '')[:200]}")
    return data["data"]


async def execute(
    transport: Transport,
    operation: str,
    variables: dict[str, Any] | None = None
) -> dict[str, Any]:
    variables = variables or {}
    headers = transport.graphql_headers(operation)

    if operation in PERSISTED_QUERIES:
        params = {
            "operationName": operation,
            "variables": json.dumps(variables),
            "extensions": json.dumps({
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": PERSISTED_QUERIES[operation]
                }
            })
        }
        resp = await transport.request("GET", GRAPHQL_URL, headers=headers, params=params)
    elif operation in QUERIES:
        payload = {
            "operationName": operation,
            "query": QUERIES[operation],
            "variables": variables
        }
        resp = await transport.request(
            "POST", GRAPHQL_URL, headers=headers, json=payload, idempotent=not _is_mutation(operation)
        )
    else:
        raise KeyError(f"Неизвестная операция GraphQL: {operation}")

    return _parse_response(operation, resp)


async def upload(
    transport: Transport,
    operation: str,
    variables: dict[str, Any],
    files: dict[str, tuple[str, str, bytes]]
) -> dict[str, Any]:
    # files: {"variables.file": (имя файла, content-type, байты)}
    if operation not in QUERIES:
        raise KeyError(f"Неизвестная операция GraphQL: {operation}")
    paths = list(files)
    operations = {
        "operationName": operation,
        "query": QUERIES[operation],
        "variables": variables
    }
    form = {
        "operations": json.dumps(operations),
        "map": json.dumps({str(i): [path] for i, path in enumerate(paths, 1)})
    }
    parts = [(str(i), *files[path]) for i, path in enumerate(paths, 1)]

    headers = transport.graphql_headers(operation)
    del headers["content-type"] # boundary multipart'а проставит curl
    resp = await transport.request("POST", GRAPHQL_URL, headers=headers, form=form, files=parts, idempotent=False)
    return _parse_response(operation, resp)
