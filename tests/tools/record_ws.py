from __future__ import annotations

import argparse
import json
import threading
import time

from _recording import Tape, load_account
from anonymize import Anonymizer

from playerokapi.listener.listener import EventListener


def summarize(event) -> dict:
    message = getattr(event, "message", None)
    deal = getattr(event, "deal", None)
    chat = getattr(event, "chat", None)
    return {
        "event_type": event.type.name,
        "chatId": chat.id if chat else None,
        "messageId": message.id if message else None,
        "messageText": message.text if message else None,
        "dealId": deal.id if deal else None,
        "dealStatus": deal.status.name if deal and deal.status else None,
    }


def main():
    parser = argparse.ArgumentParser(description="Записывает WS-кадры, HTTP-ответы и события старого листенера")
    parser.add_argument("--account", default="test")
    parser.add_argument("--minutes", type=float, default=10)
    parser.add_argument("--name", default="session", help="имя записи: tests/fixtures/ws/<name>.json")
    parser.add_argument("--raw", action="store_true")
    args = parser.parse_args()

    tape = Tape(Anonymizer())
    tape.patch_requests()

    orig = EventListener.proccess_ws_message

    def capture(self, msg, gen=None):
        try: frame = json.loads(msg)
        except ValueError: frame = {"non_json": str(msg)[:500]}
        tape.add("ws", frame=frame)
        return orig(self, msg, gen)

    EventListener.proccess_ws_message = capture

    acc = load_account(args.account)
    listener = EventListener(acc)

    def consume():
        for event in listener.listen():
            tape.add("event", event=summarize(event))
            print(f"  событие {event.type.name}")

    threading.Thread(target=consume, daemon=True).start()
    print(f"Слушаю {args.minutes} мин. Пиши со второго аккаунта, отправь фото без подписи, оборви интернет на минуту...")
    deadline = time.monotonic() + args.minutes * 60
    try:
        while time.monotonic() < deadline:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Остановлено вручную")

    out = tape.dump(f"ws/{args.name}", raw=args.raw)
    print(f"Записано {len(tape.records)} записей → {out}")


if __name__ == "__main__":
    main()
