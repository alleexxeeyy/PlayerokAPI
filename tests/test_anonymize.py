import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "tools"))

from anonymize import Anonymizer  # noqa: E402


REAL = {
    "__typename": "ItemDeal",
    "id": "1f0b9a12-3c4d-4e5f-8a9b-0c1d2e3f4a5b",
    "status": "PAID",
    "createdAt": "2026-10-01T12:00:00.000Z",
    "user": {"id": "1f0b9a12-3c4d-4e5f-8a9b-0c1d2e3f4a5b", "username": "REALSELLER", "email": "me@mail.ru",
             "avatarURL": "https://cdn.playerok.com/a.png"},
    "chat": {"lastMessage": {"text": "{{ITEM_PAID}}"}},
    "messages": [{"text": "привет, мой телефон 89991234567"}, {"text": None}, {"text": ""}],
    "item": {"name": "Аккаунт Steam", "slug": "akkaunt-steam-123", "price": 15990, "rating": 5},
    "balance": {"value": 123456, "frozen": 0},
    "isRead": True,
    "frame": {"type": "next", "id": "sub-1", "payload": {}},
    "operation": "userChats",
}


def test_secrets_do_not_survive():
    out = json.dumps(Anonymizer(seed=1)(REAL), ensure_ascii=False)
    for secret in ("1f0b9a12", "REALSELLER", "me@mail.ru", "cdn.playerok.com", "89991234567",
                   "Аккаунт Steam", "akkaunt-steam", "15990", "123456"):
        assert secret not in out


def test_technical_values_survive():
    out = Anonymizer(seed=1)(REAL)
    assert out["__typename"] == "ItemDeal"
    assert out["status"] == "PAID"
    assert out["createdAt"] == REAL["createdAt"]
    assert out["chat"]["lastMessage"]["text"] == "{{ITEM_PAID}}"
    assert out["messages"][1]["text"] is None
    assert out["messages"][2]["text"] == ""
    assert out["item"]["rating"] == 5
    assert out["balance"]["frozen"] == 0
    assert out["isRead"] is True
    assert out["frame"]["type"] == "next"
    assert out["operation"] == "userChats"


def test_enum_values_under_id_keys_survive():
    out = Anonymizer(seed=1)({"providerId": "SBP", "id": "MIR", "userId": "u1", "chatId": "abc123"})
    assert out["providerId"] == "SBP"
    assert out["id"] == "MIR"
    assert out["userId"] != "u1"
    assert out["chatId"] != "abc123"


def test_same_value_maps_consistently():
    out = Anonymizer(seed=1)(REAL)
    assert out["id"] == out["user"]["id"]
    assert len(str(out["item"]["price"])) == len("15990")


def test_text_starting_with_date_is_replaced():
    out = Anonymizer(seed=1)({"comment": "2026-10-04T09:24 встреча у метро", "createdAt": "2026-10-04T09:24:41.409Z"})
    assert "метро" not in out["comment"]
    assert out["createdAt"] == "2026-10-04T09:24:41.409Z"


def test_uppercase_words_in_text_fields_are_replaced():
    out = Anonymizer(seed=1)({"fragmentUsername": "IVANOV", "statusDescription": "BLOCKED", "filename": "PASSPORT"})
    assert out["fragmentUsername"] != "IVANOV"
    assert out["statusDescription"] != "BLOCKED"
    assert out["filename"] != "PASSPORT"


def test_int_and_float_do_not_share_cache():
    out = Anonymizer(seed=1)([{"value": 81}, {"value": 81.0}])
    assert type(out[0]["value"]) is int
    assert type(out[1]["value"]) is float
