from __future__ import annotations

import json
import sys
import threading
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from playerokapi.account import Account  # noqa: E402
from playerokapi.exceptions import RequestPlayerokError  # noqa: E402

from anonymize import Anonymizer  # noqa: E402


ACCOUNTS_FILE = ROOT / "tests" / ".accounts.json"
FIXTURES = ROOT / "tests" / "fixtures"
RAW_DIR = ROOT / "tests" / ".raw"


def load_account(name: str) -> Account:
    if not ACCOUNTS_FILE.exists():
        raise SystemExit(
            f"Нет файла {ACCOUNTS_FILE}. Формат: "
            '{"test": {"cookies": "token=...; __ddg5_=...", "user_agent": "...", "proxy": null}, "main": {...}}'
        )
    cfg = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))[name]
    return Account(
        token=cfg.get("token"),
        ddg5=cfg.get("ddg5", ""),
        cookies=cfg.get("cookies"),
        user_agent=cfg.get("user_agent", ""),
        proxy=cfg.get("proxy")
    ).get()


class Tape:
    def __init__(self, anonymizer: Anonymizer):
        self.anonymize = anonymizer
        self.records: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._started = time.monotonic()

    def add(self, kind: str, **data):
        with self._lock:
            self.records.append({"kind": kind, "t": round(time.monotonic() - self._started, 3), **data})

    def patch_requests(self):
        orig = Account.request
        tape = self

        def request(self, method, url, headers, payload=None, files=None, pass_304=True):
            if files:
                operations = json.loads(payload["operations"])
                operation, variables = operations["operationName"], operations["variables"]
            else:
                operation = (payload or {}).get("operationName")
                variables = (payload or {}).get("variables")
                if isinstance(variables, str):
                    variables = json.loads(variables)
            try:
                resp = orig(self, method, url, headers, payload, files, pass_304)
            except RequestPlayerokError as e:
                tape.add("http", operation=operation, variables=variables, response=e.json)
                raise
            try: body = resp.json()
            except ValueError: body = {"non_json": resp.text[:500]}
            tape.add("http", operation=operation, variables=variables, response=body)
            return resp

        Account.request = request

    def dump(self, name: str, raw: bool = False) -> Path:
        out = FIXTURES / f"{name}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        if raw:
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            (RAW_DIR / f"{name.replace('/', '_')}.json").write_text(
                json.dumps(self.records, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        out.write_text(json.dumps(self.anonymize(self.records), ensure_ascii=False, indent=2), encoding="utf-8")
        return out
