from __future__ import annotations

import argparse
import traceback

import struct
import zlib

from _recording import Tape, load_account
from anonymize import Anonymizer

from playerokapi.enums import (
    ChatTypes,
    ItemDealDirections,
    ItemStatuses,
    TransactionProviderDirections,
)


def tiny_png() -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    header = struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)
    pixels = zlib.compress(b"".join(b"\x00" + b"\xff\x80\x00" * 8 for _ in range(8)))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels) + chunk(b"IEND", b"")


def main():
    parser = argparse.ArgumentParser(description="Записывает ответы read-запросов Playerok в tests/fixtures/http")
    parser.add_argument("--account", default="test", help="ключ аккаунта в tests/.accounts.json")
    parser.add_argument("--raw", action="store_true", help="дополнительно сохранить сырые ответы в tests/.raw")
    parser.add_argument("--chat-id", help="чат для write-запросов (send_message с картинкой, mark_chat_as_read)")
    args = parser.parse_args()

    tape = Tape(Anonymizer())
    tape.patch_requests()
    acc = load_account(args.account)

    def step(name, func):
        try:
            result = func()
            print(f"+ {name}")
            return result
        except Exception:
            print(f"- {name}: {traceback.format_exc().strip().splitlines()[-1]}")

    chats = step("get_chats", lambda: acc.get_chats(count=24))
    step("get_chats PM", lambda: acc.get_chats(count=24, type=ChatTypes.PM))
    if chats and chats.chats:
        chat = chats.chats[0]
        step("get_chat", lambda: acc.get_chat(chat.id))
        step("get_chat_messages", lambda: acc.get_chat_messages(chat.id, count=24))
        partner = next((u for u in chat.users if u.id != acc.id), None)
        if partner:
            step("get_user", lambda: acc.get_user(username=partner.username))

    deals = step("get_deals OUT", lambda: acc.get_deals(direction=ItemDealDirections.OUT, count=24))
    step("get_deals IN", lambda: acc.get_deals(direction=ItemDealDirections.IN, count=24))
    seen_statuses = set()
    for deal in (deals.deals if deals else []):
        if deal.status not in seen_statuses:
            seen_statuses.add(deal.status)
            step(f"get_deal {deal.status}", lambda d=deal: acc.get_deal(d.id))

    games = step("get_games", lambda: acc.get_games(count=24))
    if games and games.games:
        game = step("get_game", lambda: acc.get_game(id=games.games[0].id))
        category = game.categories[0] if game and game.categories else None
        if category:
            step("get_game_category", lambda: acc.get_game_category(id=category.id))
            step("get_game_category_agreements", lambda: acc.get_game_category_agreements(category.id))
            obtaining = step("get_game_category_obtaining_types", lambda: acc.get_game_category_obtaining_types(category.id))
            if obtaining and obtaining.obtaining_types:
                ot = obtaining.obtaining_types[0]
                step("get_game_category_instructions", lambda: acc.get_game_category_instructions(category.id, ot.id))
                step("get_game_category_data_fields", lambda: acc.get_game_category_data_fields(category.id, ot.id))
            items = step("get_items", lambda: acc.get_items(game_id=game.id, category_id=category.id, count=24))
            if items and items.items:
                step("get_item (чужой)", lambda: acc.get_item(id=items.items[0].id))

    my_items = step("get_my_items", lambda: acc.get_my_items(count=24))
    step("get_my_items EXPIRED", lambda: acc.get_my_items(statuses=[ItemStatuses.EXPIRED], count=24))
    if my_items and my_items.items:
        mine = my_items.items[0]
        step("get_item (свой)", lambda: acc.get_item(id=mine.id))
        step("get_item_priority_statuses", lambda: acc.get_item_priority_statuses(mine.id, mine.price))

    step("get_transaction_providers IN", lambda: acc.get_transaction_providers(TransactionProviderDirections.IN))
    step("get_transaction_providers OUT", lambda: acc.get_transaction_providers(TransactionProviderDirections.OUT))
    step("get_transactions", lambda: acc.get_transactions())
    step("get_sbp_bank_members", lambda: acc.get_sbp_bank_members())
    step("get_verified_cards", lambda: acc.get_verified_cards())
    step("get_message_templates", lambda: acc.get_message_templates())
    step("get_my_reviews", lambda: acc.get_my_reviews())
    step("get_deal (несуществующая)", lambda: acc.get_deal("00000000-0000-0000-0000-000000000000"))

    if args.chat_id:
        step("mark_chat_as_read", lambda: acc.mark_chat_as_read(args.chat_id))
        step("send_message", lambda: acc.send_message(args.chat_id, text="тест PlayerokAPI 2.0"))
        step("send_message с картинкой", lambda: acc.send_message(args.chat_id, images=[tiny_png()]))

    out = tape.dump(f"http/{args.account}", raw=args.raw)
    print(f"Записано {len(tape.records)} ответов → {out}")


if __name__ == "__main__":
    main()
