from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from .base import PlayerokModel, Tolerant
from .common import FileObject, Moderator
from .enums import ChatMessageButtonType, ChatMessageEvent, ChatStatus, ChatType, MessageTemplateType
from .finance import Transaction
from .games import GameProfile
from .items import AnyItem
from .users import UserProfile

if TYPE_CHECKING:
    from .deals import Deal


class ChatMessageButton(PlayerokModel):
    """
    Объект кнопки сообщения.
    """

    type: Tolerant[ChatMessageButtonType] = None
    """ Тип кнопки. """
    url: str | None = None
    """ URL кнопки. """
    text: str | None = None
    """ Текст кнопки. """


class ChatMessage(PlayerokModel):
    """
    Класс, описывающий сообщение в чате.
    """

    id: str | None = None
    """ ID сообщения. """
    text: str | None = None
    """ Текст сообщения (`None` у фото без подписи и служебных сообщений). """
    created_at: Tolerant[datetime] = None
    """ Дата создания сообщения. """
    deleted_at: Tolerant[datetime] = None
    """ Дата удаления сообщения. """
    is_read: bool | None = None
    """ Прочитано ли сообщение. """
    is_suspicious: bool | None = None
    """ Подозрительное ли сообщение. """
    is_bulk_messaging: bool | None = None
    """ Массовая ли это рассылка. """
    game: GameProfile | None = None
    """ Игра, к которой относится сообщение. """
    file: FileObject | None = None
    """ Файл, прикреплённый к сообщению. """
    images: list[FileObject] = []
    """ Изображения, прикреплённые к сообщению. """
    image_links: list[str] = []
    """ Ссылки на изображения сообщения (с водяным знаком). """
    user: UserProfile | None = None
    """ Пользователь, который отправил сообщение. """
    deal: Deal | None = None
    """ Сделка, к которой относится сообщение. """
    item: AnyItem = None
    """ Предмет, к которому относится сообщение (обычно передаётся только сама сделка в переменную deal). """
    transaction: Transaction | None = None
    """ Транзакция сообщения. """
    moderator: Moderator | None = None
    """ Модератор сообщения. """
    event: Tolerant[ChatMessageEvent] = None
    """ Ивент сообщения. """
    event_by_user: UserProfile | None = None
    """ Ивент от пользователя. """
    event_to_user: UserProfile | None = None
    """ Ивент для пользователя. """
    is_auto_response: bool | None = None
    """ Авто-ответ ли это. """
    buttons: list[ChatMessageButton] = []
    """ Кнопки сообщения. """


class Chat(PlayerokModel):
    """
    Объект чата.
    """

    id: str | None = None
    """ ID чата. """
    type: Tolerant[ChatType] = None
    """ Тип чата. """
    status: Tolerant[ChatStatus] = None
    """ Статус чата. """
    unread_messages_counter: int | None = None
    """ Количество непрочитанных сообщений. """
    bookmarked: bool | None = None
    """ В закладках ли чат. """
    is_texting_allowed: bool | None = None
    """ Разрешено ли писать в чат. """
    owner: UserProfile | None = None
    """ Владелец чата. """
    deals: list[Deal] = []
    """ Сделки в чате. """
    started_at: Tolerant[datetime] = None
    """ Дата начала диалога. """
    finished_at: Tolerant[datetime] = None
    """ Дата завершения диалога. """
    last_message: ChatMessage | None = None
    """ Объект последнего сообщения в чате. """
    users: list[UserProfile] = Field([], alias="participants")
    """ Участники чата. """


class MessageTemplate(PlayerokModel):
    """
    Объект шаблонного сообщения.
    """

    id: str | None = None
    """ ID шаблонного сообщения. """
    type: Tolerant[MessageTemplateType] = None
    """ Тип шаблонного сообщения. """
    title: str | None = None
    """ Заголовок шаблонного сообщения. """
    text: str | None = None
    """ Текст шаблонного сообщения. """
    sequence: int | None = None
    """ Последовательность шаблонного сообщения. """
    created_at: Tolerant[datetime] = None
    """ Дата создания шаблонного сообщения. """
    group: str | None = None
    """ Группа шаблонного сообщения. """


class TemporaryAttachmentUploadOutput(PlayerokModel):
    """
    Выходные данные для загрузки временного вложения.
    """

    id: str | None = None
    """ ID данных. """
    url: str | None = None
    """ URL изображения. """
    chat_id: str | None = None
    """ ID чата, куда отправляется изображение. """
    client_attachment_id: str | None = None
    """ ID приложения клиента. """
    expires_at: Tolerant[datetime] = None
    """ Дата истечения. """
