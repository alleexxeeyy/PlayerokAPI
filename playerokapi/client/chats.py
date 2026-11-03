from __future__ import annotations

import os
import uuid

from ..models import (
    Chat,
    ChatMessage,
    ChatStatus,
    ChatType,
    MessageTemplate,
    MessageTemplateType,
    Page,
    TemporaryAttachmentUploadOutput,
)
from ..errors import PlayerokError
from .base import BaseClient, read_image, value_of


class ChatsMixin(BaseClient):

    async def get_chats(
        self,
        count: int = 24,
        type: ChatType | None = None,
        status: ChatStatus | None = None,
        after_cursor: str | None = None
    ) -> Page[Chat]:
        """
        Получает все чаты аккаунта.

        :param count: Кол-во чатов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param type: Тип чатов, которые нужно получать. По умолчанию не указано, значит будут все сразу, _опционально_.
        :type type: `playerokapi.models.ChatType` or `None`

        :param status: Статус чатов, которые нужно получать. По умолчанию не указано, значит будут любые, _опционально_.
        :type status: `playerokapi.models.ChatStatus` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница чатов.
        :rtype: `playerokapi.models.Page[playerokapi.models.Chat]`
        """

        return await self._query("userChats", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"userId": await self._me_id(), "type": value_of(type), "status": value_of(status)},
            "hasSupportAccess": False
        }, "chats", Page[Chat])

    async def get_chat(self, chat_id: str) -> Chat:
        """
        Получает чат.

        :param chat_id: ID чата.
        :type chat_id: `str`

        :return: Объект чата.
        :rtype: `playerokapi.models.Chat`
        """

        return await self._query("chat", {"id": chat_id, "hasSupportAccess": False}, "chat", Chat)

    async def get_chat_by_username(self, username: str, max_pages: int | None = None) -> Chat | None:
        """
        Получает чат по никнейму собеседника.

        :param username: Никнейм собеседника.
        :type username: `str`

        :param max_pages: Сколько страниц чатов (по 24) просмотреть, прежде чем сдаться (`None` - все), _опционально_.
        :type max_pages: `int` or `None`

        :return: Объект чата (`None`, если не найден).
        :rtype: `playerokapi.models.Chat` or `None`
        """

        username = username.lower()
        cursor = None
        pages = 0
        while max_pages is None or pages < max_pages:
            pages += 1
            page = await self.get_chats(count=24, after_cursor=cursor)
            for chat in page.items:
                if any(user.username and user.username.lower() == username for user in chat.users):
                    return chat
            if not page.page_info or not page.page_info.has_next_page:
                break
            cursor = page.page_info.end_cursor
        return None

    async def get_chat_messages(
        self,
        chat_id: str,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[ChatMessage]:
        """
        Получает сообщения чата.

        :param chat_id: ID чата.
        :type chat_id: `str`

        :param count: Кол-во сообщений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница сообщений.
        :rtype: `playerokapi.models.Page[playerokapi.models.ChatMessage]`
        """

        return await self._query("chatMessages", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"chatId": chat_id},
            "hasSupportAccess": False,
            "showForbiddenImage": True
        }, "chatMessages", Page[ChatMessage])

    async def mark_chat_as_read(self, chat_id: str) -> Chat:
        """
        Помечает чат как прочитанный (все сообщения).

        :param chat_id: ID чата.
        :type chat_id: `str`

        :return: Объект чата с обновлёнными данными.
        :rtype: `playerokapi.models.Chat`
        """

        return await self._query("markChatAsRead", {"input": {"chatId": chat_id}}, "markChatAsRead", Chat)

    async def upload_chat_image_into_temporary_store(
        self,
        image: str | os.PathLike | bytes,
        chat_id: str
    ) -> TemporaryAttachmentUploadOutput:
        """
        Выкладывает изображение чата во временное хранилище
        (перед отправкой сообщения с изображением).

        :param image: Путь к изображению или байты изображения.
        :type image: `str` or `bytes`

        :param chat_id: ID чата.
        :type chat_id: `str`

        :return: Объект временного вложения.
        :rtype: `playerokapi.models.TemporaryAttachmentUploadOutput`
        """

        return await self._upload(
            "uploadChatImageIntoTemporaryStore",
            {"file": None, "input": {"chatId": chat_id, "clientAttachmentId": str(uuid.uuid4())}},
            {"variables.file": await read_image(image)},
            "uploadChatImageIntoTemporaryStore",
            TemporaryAttachmentUploadOutput
        )

    async def send_message(
        self,
        chat_id: str,
        text: str | None = None,
        images: list[str | os.PathLike | bytes] | None = None,
        mark_chat_as_read: bool = False
    ) -> ChatMessage:
        """
        Отправляет сообщение в чат.
        Можно отправить текстовое сообщение `text` или изображения `images`.

        :param chat_id: ID чата, в который нужно отправить сообщение.
        :type chat_id: `str`

        :param text: Текст сообщения, _опционально_.
        :type text: `str` or `None`

        :param images: Список изображений — пути к файлам или байты, _опционально_.
        :type images: `list[str | bytes]` or `None`

        :param mark_chat_as_read: Пометить чат как прочитанный перед отправкой, _опционально_.
        :type mark_chat_as_read: `bool`

        :return: Объект отправленного сообщения.
        :rtype: `playerokapi.models.ChatMessage`
        """

        if not any((text, images)):
            raise TypeError("Не был передан ни один из обязательных аргументов: text, images")

        if mark_chat_as_read:
            await self.mark_chat_as_read(chat_id)

        images_ids = []
        for image in images or []:
            uploaded = await self.upload_chat_image_into_temporary_store(image, chat_id)
            if not uploaded or not uploaded.id:
                raise PlayerokError("Playerok не вернул ID загруженного изображения, сообщение не отправлено")
            images_ids.append(uploaded.id)

        return await self._query("createChatMessage", {
            "input": {"chatId": chat_id, "imagesIds": images_ids, "text": text or ""}
        }, "createChatMessage", ChatMessage)

    async def get_message_templates(
        self,
        type: MessageTemplateType = MessageTemplateType.ACTIVE_DEAL_PROBLEM,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[MessageTemplate]:
        """
        Получает шаблонные сообщения.

        :param type: Тип шаблонных сообщений.
        :type type: `playerokapi.models.MessageTemplateType`

        :param count: Кол-во сообщений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница шаблонных сообщений.
        :rtype: `playerokapi.models.Page[playerokapi.models.MessageTemplate]`
        """

        return await self._query("messageTemplates", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"type": value_of(type)}
        }, "messageTemplates", Page[MessageTemplate])
