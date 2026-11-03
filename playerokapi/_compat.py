from __future__ import annotations

from typing import Any

from . import parser
from .dispatcher import events as ev
from .listener import events as legacy


_DEAL_EVENTS = {
    ev.NewDealEvent: legacy.NewDealEvent,
    ev.NewReviewEvent: legacy.NewReviewEvent,
    ev.ItemPaidEvent: legacy.ItemPaidEvent,
    ev.ItemSentEvent: legacy.ItemSentEvent,
    ev.DealConfirmedEvent: legacy.DealConfirmedEvent,
    ev.DealRolledBackEvent: legacy.DealRolledBackEvent,
    ev.DealHasProblemEvent: legacy.DealHasProblemEvent,
    ev.DealProblemResolvedEvent: legacy.DealProblemResolvedEvent,
    ev.DealStatusChangedEvent: legacy.DealStatusChangedEvent,
}


def to_legacy(event: ev.BaseEvent) -> Any:
    """
    Превращает событие 2.0 в событие 1.x (`playerokapi.listener.events`) для старых плагинов.
    Объекты собираются старым парсером из исходных ответов Playerok, поэтому выглядят ровно как в 1.x
    (даты строками, енумы 1.x). Для одного события возвращается один и тот же объект.

    :param event: Событие 2.0.
    :type event: `playerokapi.dispatcher.BaseEvent`

    :return: Событие 1.x.
    """

    cached = event.__dict__.get("_legacy")
    if cached is not None:
        return cached

    raw = event.raw or {}
    chat = parser.chat(raw.get("chat"))

    if isinstance(event, ev.ChatInitializedEvent):
        result = legacy.ChatInitializedEvent(chat)
    elif isinstance(event, ev.NewMessageEvent):
        message = parser.chat_message(raw.get("message"))
        if message is not None and event.message.text is None:
            # модули отсекают фото без подписи по `is None`
            message.text = None
        result = legacy.NewMessageEvent(message, chat)
    elif type(event) in _DEAL_EVENTS:
        deal = parser.item_deal(raw.get("deal"))
        if isinstance(event, ev.NewReviewEvent) and deal is not None and chat is not None:
            deal.chat = chat
        result = _DEAL_EVENTS[type(event)](deal, chat)
    else:
        raise TypeError(f"Неизвестное событие: {type(event).__name__}")

    result.time = event.time
    event.__dict__["_legacy"] = result
    return result
