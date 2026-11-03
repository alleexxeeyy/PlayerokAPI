import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path

import pytest
from pydantic import BaseModel, TypeAdapter

from playerokapi import models as m
from playerokapi.models import base


FIXTURES = Path(__file__).parent / "fixtures"

ROOTS = {
    "viewer": m.AccountProfile,
    "user": m.UserProfile,
    "chats": m.Page[m.Chat],
    "chat": m.Chat,
    "chatMessages": m.Page[m.ChatMessage],
    "deals": m.Page[m.Deal],
    "deal": m.Deal,
    "games": m.Page[m.Game],
    "game": m.Game,
    "gameCategory": m.GameCategory,
    "gameCategoryAgreements": m.Page[m.GameCategoryAgreement],
    "gameCategoryObtainingTypes": m.Page[m.GameCategoryObtainingType],
    "gameCategoryInstructions": m.Page[m.GameCategoryInstruction],
    "gameCategoryDataFields": m.Page[m.GameCategoryDataField],
    "items": m.Page[m.ItemProfile],
    "item": m.AnyItem,
    "itemPriorityStatuses": list[m.ItemPriorityStatus],
    "transactionProviders": list[m.TransactionProvider],
    "transactions": m.Page[m.Transaction],
    "sbpBankMembers": list[m.SBPBankMember],
    "verifiedCards": m.Page[m.UserBankCard],
    "messageTemplates": m.Page[m.MessageTemplate],
    "testimonials": m.Page[m.Review],
    "markChatAsRead": m.Chat,
    "createChatMessage": m.ChatMessage,
    "uploadChatImageIntoTemporaryStore": m.TemporaryAttachmentUploadOutput,
    "chatUpdated": m.Chat,
    "chatMessageCreated": m.ChatMessage,
    "userUpdated": m.AccountProfile,
}

IGNORED = {
    ("AccountProfile", "profile"),
    ("AccountProfile", "chosenVerifiedCard"),
    ("AccountStats", "id"),
    ("AccountStats", "fragmentDeposits"),
    ("AccountStats", "steamDeposits"),
    ("UserProfile", "isVip"),
    ("UserProfile", "balance"),
    ("UserProfile", "canPublishItems"),
    ("UserProfile", "chosenVerifiedCard"),
    ("UserProfile", "email"),
    ("UserProfile", "hasConfirmedPhoneNumber"),
    ("UserProfile", "hasEnabledNotifications"),
    ("UserProfile", "hasFrozenBalance"),
    ("UserProfile", "isBlockedFor"),
    ("UserProfile", "isFundsProtectionActive"),
    ("UserProfile", "isVerified"),
    ("UserProfile", "lastItemCreatedAt"),
    ("UserProfile", "profile"),
    ("UserProfile", "stats"),
    ("UserProfile", "unreadChatsCounter"),
    ("Chat", "agent"),
    ("ChatMessage", "uncensorInfo"),
    ("ChatMessage", "plTokenAmount"),
    ("GameCategory", "seo"),
    ("GameCategoryDataField", "sequence"),
    ("GameCategoryDataField", "validationRules"),
    ("Page", "edges"),
}


def records():
    for path in sorted(FIXTURES.rglob("*.json")):
        for rec in json.loads(path.read_text(encoding="utf-8")):
            if rec["kind"] == "http":
                data = (rec["response"] or {}).get("data") or {}
            elif rec["kind"] == "ws" and rec["frame"].get("type") == "next":
                data = rec["frame"]["payload"].get("data") or {}
            else:
                continue
            for key, value in data.items():
                if value is not None:
                    yield f"{path.stem}:{rec.get('operation') or 'ws'}:{key}", key, value


def field_by_alias(model: type[BaseModel], key: str):
    for name, field in model.model_fields.items():
        if (field.alias or name) == key:
            return name
    return None


def compare(obj, raw, path: str, unmapped: set, mismatched: list):
    if isinstance(obj, BaseModel):
        cls = type(obj)
        owner = "Page" if cls.__name__.startswith("Page[") else cls.__name__
        if not isinstance(raw, dict):
            mismatched.append(f"{path}: модель против {type(raw).__name__}")
            return
        if owner == "Page":
            raw = {**raw, "items": [e["node"] for e in raw.get("edges") or []]}
        if owner == "AccountProfile" and isinstance(raw.get("profile"), dict):
            raw = {**raw["profile"], **{k: v for k, v in raw.items() if v is not None}}
        for key, value in raw.items():
            if key in ("__typename",):
                continue
            name = field_by_alias(cls, key)
            if name is None:
                if (owner, key) not in IGNORED:
                    unmapped.add((owner, key))
                continue
            compare(getattr(obj, name), value, f"{path}.{name}", unmapped, mismatched)
    elif isinstance(obj, list):
        if raw is None:
            if obj:
                mismatched.append(f"{path}: null против {obj!r}")
            return
        if len(obj) != len(raw):
            mismatched.append(f"{path}: длина {len(obj)} против {len(raw)}")
            return
        for i, (a, b) in enumerate(zip(obj, raw)):
            compare(a, b, f"{path}[{i}]", unmapped, mismatched)
    elif isinstance(obj, datetime):
        if not isinstance(raw, str):
            mismatched.append(f"{path}: дата против {raw!r}")
    elif isinstance(obj, Enum):
        if obj.value != raw:
            mismatched.append(f"{path}: {obj!r} против {raw!r}")
    else:
        if obj != raw or type(obj) is not type(raw):
            mismatched.append(f"{path}: {obj!r} против {raw!r}")


def parse(key, value):
    return TypeAdapter(ROOTS[key]).validate_python(value)


RECORDS = list(records())


def test_fixtures_exist():
    keys = {key for _, key, _ in RECORDS}
    assert keys == set(ROOTS)


@pytest.mark.parametrize("rid,key,value", RECORDS, ids=[r[0] for r in RECORDS])
def test_fixture_parses_without_losses(rid, key, value, caplog):
    with caplog.at_level(logging.WARNING, logger="playerokapi"):
        parsed = parse(key, value)
    assert not caplog.records, [r.getMessage() for r in caplog.records]
    unmapped, mismatched = set(), []
    compare(parsed, value, key, unmapped, mismatched)
    assert not unmapped
    assert not mismatched[:10]


def test_unknown_enum_becomes_none_and_logs_once(caplog):
    base._reported.clear()
    with caplog.at_level(logging.WARNING, logger="playerokapi"):
        deals = [m.Deal.model_validate({"id": "1", "status": "BRAND_NEW"}) for _ in range(3)]
    assert all(d.status is None for d in deals)
    assert len(caplog.records) == 1
    assert "BRAND_NEW" in caplog.records[0].getMessage()


def test_bad_date_becomes_none():
    assert m.ChatMessage.model_validate({"id": "1", "createdAt": "вчера"}).created_at is None


def test_dates_are_aware_datetimes():
    msg = m.ChatMessage.model_validate({"createdAt": "2026-10-04T09:24:41.409Z"})
    assert msg.created_at.tzinfo is not None
    assert msg.created_at.utcoffset().total_seconds() == 0


def test_text_none_stays_none_and_empty_string_stays():
    assert m.ChatMessage.model_validate({"id": "1", "text": None}).text is None
    assert m.ChatMessage.model_validate({"id": "1"}).text is None
    assert m.ChatMessage.model_validate({"id": "1", "text": ""}).text == ""


def test_null_lists_and_objects():
    msg = m.ChatMessage.model_validate({"images": None, "buttons": None, "user": None, "deal": None})
    assert msg.images == [] and msg.buttons == []
    assert msg.user is None and msg.deal is None
    chat = m.Chat.model_validate({"participants": None, "deals": None, "lastMessage": None})
    assert chat.users == [] and chat.deals == [] and chat.last_message is None


def test_lists_are_not_shared_between_instances():
    a, b = m.ChatMessage(), m.ChatMessage()
    a.images.append(m.FileObject(id="1"))
    assert b.images == []


def test_page_from_edges_skips_null_nodes():
    page = m.Page[m.Chat].model_validate({
        "edges": [{"node": {"id": "1"}}, {"node": None}, None, {"node": {"id": "2"}}],
        "pageInfo": {"endCursor": "c", "hasNextPage": False},
        "totalCount": 2,
    })
    assert [c.id for c in page.items] == ["1", "2"]
    assert page.page_info.end_cursor == "c"
    assert page.page_info.has_next_page is False
    assert m.Page[m.Chat].model_validate({"edges": None}).items == []


@pytest.mark.parametrize("typename,cls", [
    ("MyItem", m.MyItem),
    ("ForeignItem", m.Item),
    ("Item", m.Item),
    ("MyItemProfile", m.ItemProfile),
    ("ForeignItemProfile", m.ItemProfile),
    ("ItemProfile", m.ItemProfile),
])
def test_item_by_typename(typename, cls):
    deal = m.Deal.model_validate({"item": {"__typename": typename, "id": "i", "name": "n"}})
    assert type(deal.item) is cls
    assert deal.item.name == "n"


def test_unknown_item_typename_becomes_none(caplog):
    base._reported.clear()
    with caplog.at_level(logging.WARNING, logger="playerokapi"):
        deal = m.Deal.model_validate({"item": {"__typename": "Something", "id": "i"}})
    assert deal.item is None
    assert len(caplog.records) == 1
    assert "item" in caplog.records[0].getMessage()


def test_warnings_do_not_repeat_for_unique_values(caplog):
    base._reported.clear()
    with caplog.at_level(logging.WARNING, logger="playerokapi"):
        for i in range(50):
            m.Deal.model_validate({"item": {"__typename": "Something", "id": f"id-{i}"}})
            m.ChatMessage.model_validate({"createdAt": f"вчера в {i} часов, а может и позавчера, кто его разберёт {i}" * 2})
    assert len(caplog.records) == 2
    assert all("id-" not in r.getMessage() for r in caplog.records)


def test_reported_set_is_bounded():
    base._reported.clear()
    for i in range(base._MAX_REPORTED + 50):
        m.Deal.model_validate({"status": f"S{i}"})
    assert len(base._reported) == base._MAX_REPORTED
    base._reported.clear()


def test_broken_item_in_page_is_skipped(caplog):
    base._reported.clear()
    with caplog.at_level(logging.WARNING, logger="playerokapi"):
        page = m.Page[m.Chat].model_validate({"edges": [
            {"node": {"id": "1"}},
            {"node": {"id": "2", "unreadMessagesCounter": "много"}},
            {"node": {"id": "3"}},
        ]})
    assert [c.id for c in page.items] == ["1", "3"]
    assert caplog.records


def test_numbers_where_strings_expected_are_kept():
    field = m.GameCategoryDataField.model_validate({"id": 5, "value": 123})
    assert field.id == "5" and field.value == "123"


def test_null_elements_inside_lists_are_dropped():
    msg = m.ChatMessage.model_validate({"images": [None, {"id": "f"}], "imageLinks": [None, "u"]})
    assert [i.id for i in msg.images] == ["f"]
    assert msg.image_links == ["u"]
    assert [u.id for u in m.Chat.model_validate({"participants": [None, {"id": "u"}]}).users] == ["u"]


def test_attributes_accept_any_json():
    for value in ({"a": 1}, [], "x"):
        assert m.MyItem.model_validate({"attributes": value}).attributes == value


def test_item_model_instance_accepted():
    item = m.MyItem(id="i")
    assert type(m.Deal(item=item).item) is m.MyItem
    assert m.Deal(item=item).item.id == "i"


def test_item_subclass_instance_accepted():
    class Custom(m.MyItem):
        pass
    assert isinstance(m.Deal(item=Custom(id="c")).item, m.MyItem)


def test_item_survives_dump_and_validate():
    deal = m.Deal.model_validate({"id": "d", "item": {"__typename": "MyItem", "id": "i", "name": "n"}})
    for dumped in (deal.model_dump(), deal.model_dump(by_alias=True)):
        again = m.Deal.model_validate(dumped)
        assert type(again.item) is m.MyItem and again.item.name == "n"
    again = m.Deal.model_validate_json(deal.model_dump_json())
    assert type(again.item) is m.MyItem
    assert type(m.Deal.model_validate(m.Deal(item=m.Item(id="x")).model_dump()).item) is m.Item


def test_account_profile_takes_missing_fields_from_profile():
    acc = m.AccountProfile.model_validate({
        "id": "a",
        "username": "top",
        "profile": {"id": "a", "username": "inner", "avatarURL": "ava", "isOnline": True, "rating": 4.5, "testimonialCounter": 7},
    })
    assert acc.username == "top"
    assert acc.avatar_url == "ava"
    assert acc.is_online is True
    assert acc.rating == 4.5
    assert acc.reviews_count == 7


def test_aliases_and_population_by_name():
    t = m.Transaction.model_validate({"spbBankName": "Банк", "props": {"paymentURL": "p", "successURL": "s"}})
    assert t.sbp_bank_name == "Банк"
    assert t.props.payment_url == "p" and t.props.success_url == "s"
    d = m.Deal.model_validate({"prevStatus": "PAID", "testimonial": {"id": "r"}, "completedBy": {"id": "u"}})
    assert d.previous_status == m.DealStatus.PAID
    assert d.review.id == "r"
    assert d.completed_by.id == "u"
    assert m.MyItem.model_validate({"editable": True}).is_editable is True
    assert m.Deal(previous_status="SENT").previous_status == m.DealStatus.SENT
    assert m.UserProfile(avatar_url="x", reviews_count=3).reviews_count == 3


def test_numbers_keep_their_type():
    bal = m.AccountBalance.model_validate({"value": 81, "available": 81.5})
    assert bal.value == 81 and type(bal.value) is int
    assert bal.available == 81.5
    assert type(m.GameCategory.model_validate({"feeMultiplier": 1}).fee_multiplier) is float


def test_enums_are_strings():
    assert m.DealStatus.PAID == "PAID"
    assert m.Deal.model_validate({"status": "PAID"}).status is m.DealStatus.PAID
    assert m.GameCategoryAgreementIconType.CONFIRMATION is not m.GameCategoryAgreementIconType.RESTRICTION


def test_payment_method_account_is_provider_account():
    method = m.TransactionPaymentMethod.model_validate({
        "providerId": "SBP",
        "account": {"id": "a", "value": "+7", "userId": "u", "providerId": "SBP", "paymentMethodId": None},
    })
    assert method.provider_id == m.TransactionProviderId.SBP
    assert method.account.value == "+7"
    assert method.account.provider_id == m.TransactionProviderId.SBP


def test_models_are_mutable():
    msg = m.ChatMessage(text="a")
    msg.text = "b"
    assert msg.text == "b"
