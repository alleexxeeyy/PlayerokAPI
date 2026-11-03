from __future__ import annotations

import hashlib
import random
import re
import uuid
from typing import Any


ENUM_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?$")
MARKER_RE = re.compile(r"^\{\{[A-Z_]+\}\}$")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)

KEEP_KEYS = {
    "__typename", "sha256Hash", "operationName", "query", "version", "statusCode", "code", "mime", "type",
    "operation", "kind", "t", "event_type"
}
TEXT_KEYS = {
    "username", "name", "text", "title", "description", "comment", "email", "slug", "login",
    "account", "phone", "phoneNumber", "fullName", "message", "label", "value", "placeholder",
    "filename", "statusDescription", "fragmentUsername", "tooltip", "commentFromBuyer", "ipAddress",
    "instructionForBuyer", "instructionForSeller", "sellerDealSubtitle", "buyerDealSubtitle", "buyerTimerText",
    "seoText", "metaTitle", "metaDescription", "metaKeywords", "cardFirstSix", "cardLastFour", "group"
}
URL_HINTS = ("url", "avatar", "icon", "image", "logo", "link", "href")
SMALL_INT = 10


class Anonymizer:
    def __init__(self, seed: int | None = None):
        self._salt = uuid.uuid4()
        self._rand = random.Random(seed)
        self._strings: dict[tuple[str, str], str] = {}
        self._numbers: dict[tuple[str, type, float], float] = {}

    def __call__(self, data: Any) -> Any:
        return self._walk(data, None)

    def _walk(self, value: Any, key: str | None) -> Any:
        if isinstance(value, dict):
            return {k: self._walk(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [self._walk(v, key) for v in value]
        if value is None or isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return self._number(value, key)
        if isinstance(value, str):
            return self._string(value, key)
        return value

    def _token(self, value: str) -> str:
        return hashlib.sha256(f"{self._salt}:{value}".encode()).hexdigest()[:10]

    def fake_id(self, value: str) -> str:
        return str(uuid.uuid5(self._salt, value))

    def _string(self, value: str, key: str | None) -> str:
        if not value or key in KEEP_KEYS or MARKER_RE.match(value) or DATE_RE.match(value):
            return value
        if UUID_RE.match(value):
            return self.fake_id(value)
        if ENUM_RE.match(value) and key not in TEXT_KEYS:
            return value
        if key and (key == "id" or key.endswith("Id")):
            return self.fake_id(value)

        cache_key = (key or "", value)
        if cache_key not in self._strings:
            token = self._token(value)
            lowered = (key or "").lower()
            if value.startswith("http") or any(h in lowered for h in URL_HINTS):
                fake = f"https://example.com/{token}"
            elif "email" in lowered:
                fake = f"{token}@example.com"
            else:
                fake = f"{key or 'text'}-{token}"
            self._strings[cache_key] = fake
        return self._strings[cache_key]

    def _number(self, value: int | float, key: str | None) -> int | float:
        if key in KEEP_KEYS or abs(value) <= SMALL_INT:
            return value
        cache_key = (key or "", type(value), value)
        if cache_key not in self._numbers:
            if isinstance(value, int):
                digits = len(str(abs(value)))
                self._numbers[cache_key] = self._rand.randint(10 ** (digits - 1), 10 ** digits - 1)
            else:
                self._numbers[cache_key] = round(self._rand.uniform(0, abs(value) * 2), 2)
        return self._numbers[cache_key]
