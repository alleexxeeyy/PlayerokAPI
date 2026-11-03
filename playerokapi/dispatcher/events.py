from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any, ClassVar

from ..models import Chat, ChatMessage, Deal

if TYPE_CHECKING:
    from ..client import Client


class EventType(StrEnum):
    """Типы событий."""

    CHAT_INITIALIZED = "CHAT_INITIALIZED"
    """Чат инициализирован (при запуске или при первом сообщении в новом чате)."""
    NEW_MESSAGE = "NEW_MESSAGE"
    """Новое сообщение в чате."""
    NEW_DEAL = "NEW_DEAL"
    """Создана новая сделка (когда покупатель оплатил товар)."""
    NEW_REVIEW = "NEW_REVIEW"
    """Новый отзыв от покупателя."""
    DEAL_CONFIRMED = "DEAL_CONFIRMED"
    """Сделка подтверждена (покупателем или автоматически)."""
    DEAL_ROLLED_BACK = "DEAL_ROLLED_BACK"
    """Продавец оформил возврат сделки."""
    DEAL_HAS_PROBLEM = "DEAL_HAS_PROBLEM"
    """Пользователь сообщил о проблеме в сделке."""
    DEAL_PROBLEM_RESOLVED = "DEAL_PROBLEM_RESOLVED"
    """Проблема в сделке решена."""
    DEAL_STATUS_CHANGED = "DEAL_STATUS_CHANGED"
    """Статус сделки изменён."""
    ITEM_PAID = "ITEM_PAID"
    """Пользователь оплатил предмет."""
    ITEM_SENT = "ITEM_SENT"
    """Предмет отправлен (продавец подтвердил выполнение сделки)."""


@dataclass(eq=False, kw_only=True)
class BaseEvent:
    """
    Базовый класс события.
    """

    type: ClassVar[EventType]
    """ Тип события. """
    if TYPE_CHECKING:
        chat: Chat
    raw: dict[str, Any] = field(default_factory=dict, repr=False)
    """ Исходные ответы Playerok, из которых собрано событие (`chat`, `message`, `deal`). """
    time: float = field(default_factory=time.time)
    """ Время события. """
    client: Client | None = field(default=None, repr=False)
    """ Клиент, получивший событие. """

    async def answer(
        self,
        text: str | None = None,
        images: list[str | os.PathLike | bytes] | None = None,
        mark_chat_as_read: bool = False
    ) -> ChatMessage:
        """
        Отправляет сообщение в чат события.

        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`

        :param images: Список изображений — пути к файлам или байты, _опционально_.
        :type images: `list[str | bytes]` or `None`

        :param mark_chat_as_read: Пометить чат как прочитанный перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`

        :return: Объект отправленного сообщения.
        :rtype: `playerokapi.models.ChatMessage`
        """

        if self.client is None or self.chat is None or not self.chat.id:
            raise RuntimeError("У события нет клиента или чата, ответить некуда")
        return await self.client.send_message(self.chat.id, text, images, mark_chat_as_read)


@dataclass(eq=False)
class ChatInitializedEvent(BaseEvent):
    """
    Класс события: обнаружен чат (при запуске — первые 24 чата, дальше — новые чаты).
    """

    type: ClassVar[EventType] = EventType.CHAT_INITIALIZED
    chat: Chat
    """ Объект обнаруженного чата. """


@dataclass(eq=False)
class NewMessageEvent(BaseEvent):
    """
    Класс события: новое сообщение в чате.
    """

    type: ClassVar[EventType] = EventType.NEW_MESSAGE
    message: ChatMessage
    """ Объект полученного сообщения. """
    chat: Chat
    """ Объект чата, в котором произошло событие. """


@dataclass(eq=False)
class _DealEvent(BaseEvent):
    deal: Deal
    """ Объект сделки. """
    chat: Chat
    """ Объект чата, в котором произошло событие. """


@dataclass(eq=False)
class NewDealEvent(_DealEvent):
    """
    Класс события: новая созданная сделка (когда покупатель оплатил предмет).
    """

    type: ClassVar[EventType] = EventType.NEW_DEAL


@dataclass(eq=False)
class NewReviewEvent(_DealEvent):
    """
    Класс события: новый отзыв от покупателя (отзыв лежит в `deal.review`).
    """

    type: ClassVar[EventType] = EventType.NEW_REVIEW


@dataclass(eq=False)
class ItemPaidEvent(_DealEvent):
    """
    Класс события: предмет оплачен (приходит сразу после `NewDealEvent`).
    """

    type: ClassVar[EventType] = EventType.ITEM_PAID


@dataclass(eq=False)
class ItemSentEvent(_DealEvent):
    """
    Класс события: предмет отправлен (продавец подтвердил выполнение сделки).
    """

    type: ClassVar[EventType] = EventType.ITEM_SENT


@dataclass(eq=False)
class DealConfirmedEvent(_DealEvent):
    """
    Класс события: сделка подтверждена.
    """

    type: ClassVar[EventType] = EventType.DEAL_CONFIRMED
    automatically: bool = False
    """ Подтверждена ли сделка автоматически (покупатель долго не выходил на связь). """


@dataclass(eq=False)
class DealRolledBackEvent(_DealEvent):
    """
    Класс события: продавец оформил возврат сделки.
    """

    type: ClassVar[EventType] = EventType.DEAL_ROLLED_BACK


@dataclass(eq=False)
class DealHasProblemEvent(_DealEvent):
    """
    Класс события: пользователь сообщил о проблеме в сделке.
    """

    type: ClassVar[EventType] = EventType.DEAL_HAS_PROBLEM


@dataclass(eq=False)
class DealProblemResolvedEvent(_DealEvent):
    """
    Класс события: проблема в сделке решена.
    """

    type: ClassVar[EventType] = EventType.DEAL_PROBLEM_RESOLVED


@dataclass(eq=False)
class DealStatusChangedEvent(_DealEvent):
    """
    Класс события: статус сделки изменён (приходит после событий отправки, подтверждения, возврата и проблем сделки).
    """

    type: ClassVar[EventType] = EventType.DEAL_STATUS_CHANGED


Event = (
    ChatInitializedEvent
    | NewMessageEvent
    | NewDealEvent
    | NewReviewEvent
    | ItemPaidEvent
    | ItemSentEvent
    | DealConfirmedEvent
    | DealRolledBackEvent
    | DealHasProblemEvent
    | DealProblemResolvedEvent
    | DealStatusChangedEvent
)
