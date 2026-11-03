from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from ..models import (
    AnyItem,
    GameCategoryDataField,
    GameCategoryOption,
    Item,
    ItemPriorityStatus,
    ItemProfile,
    ItemStatus,
    MyItem,
    Page,
    TransactionPaymentMethodId,
    TransactionProviderId,
)
from .base import BaseClient, read_image, value_of


def _attributes(options: Sequence[GameCategoryOption] | dict[str, Any]) -> dict[str, Any]:
    if isinstance(options, dict):
        return options
    return {option.field: option.value for option in options}


def _data_fields(data_fields: Sequence[GameCategoryDataField]) -> list[dict[str, Any]]:
    return [{"fieldId": field.id, "value": field.value} for field in data_fields]


class ItemsMixin(BaseClient):

    async def get_item(self, id: str | None = None, slug: str | None = None) -> MyItem | Item | ItemProfile | None:
        """
        Получает предмет (товар).\n
        Можно получить по любому из двух параметров:

        :param id: ID предмета, _опционально_.
        :type id: `str` or `None`

        :param slug: Имя страницы предмета, _опционально_.
        :type slug: `str` or `None`

        :return: Объект предмета: `MyItem`, если предмет ваш, иначе `Item`.
        :rtype: `playerokapi.models.MyItem` or `playerokapi.models.Item` or `playerokapi.models.ItemProfile` or `None`
        """

        if not any((id, slug)):
            raise TypeError("Не был передан ни один из обязательных аргументов: id, slug")

        return await self._query("item", {
            "id": id,
            "slug": slug,
            "hasSupportAccess": False,
            "showForbiddenImage": True
        }, "item", AnyItem)

    async def get_items(
        self,
        game_id: str | None = None,
        category_id: str | None = None,
        obtaining_type_id: str | None = None,
        statuses: Sequence[ItemStatus] | None = (ItemStatus.APPROVED,),
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[ItemProfile]:
        """
        Получает предметы игры/приложения.\n
        Можно получить по любому из двух параметров: `game_id`, `category_id`.

        :param game_id: ID игры/приложения, _опционально_.
        :type game_id: `str` or `None`

        :param category_id: ID категории игры/приложения, _опционально_.
        :type category_id: `str` or `None`

        :param obtaining_type_id: ID типа получения товара, _опционально_.
        :type obtaining_type_id: `str` or `None`

        :param statuses: Статусы, предметы которых нужно получать (`None` - любые).
        :type statuses: `list[playerokapi.models.ItemStatus]` or `None`

        :param count: Кол-во предметов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница профилей предметов.
        :rtype: `playerokapi.models.Page[playerokapi.models.ItemProfile]`
        """

        if not any((game_id, category_id)):
            raise TypeError("Не был передан ни один из обязательных аргументов: game_id, category_id")

        filter = {"gameCategoryId": category_id} if category_id else {"gameId": game_id}
        filter["status"] = [value_of(s) for s in statuses] if statuses else None
        if obtaining_type_id:
            filter["obtainingTypeId"] = obtaining_type_id

        return await self._query("items", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": filter
        }, "items", Page[ItemProfile])

    async def get_my_items(
        self,
        game_id: str | None = None,
        category_id: str | None = None,
        obtaining_type_id: str | None = None,
        statuses: Sequence[ItemStatus] | None = (ItemStatus.APPROVED,),
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[ItemProfile]:
        """
        Получает предметы вашего аккаунта.

        :param game_id: ID игры/приложения, _опционально_.
        :type game_id: `str` or `None`

        :param category_id: ID категории игры/приложения, _опционально_.
        :type category_id: `str` or `None`

        :param obtaining_type_id: ID типа получения товара, _опционально_.
        :type obtaining_type_id: `str` or `None`

        :param statuses: Статусы, предметы которых нужно получать (`None` - любые).
        :type statuses: `list[playerokapi.models.ItemStatus]` or `None`

        :param count: Кол-во предметов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница профилей предметов.
        :rtype: `playerokapi.models.Page[playerokapi.models.ItemProfile]`
        """

        filter = {
            "userId": await self._me_id(),
            "status": [value_of(s) for s in statuses] if statuses else None
        }
        if game_id:
            filter["gameId"] = game_id
        elif category_id:
            filter["gameCategoryId"] = category_id
        if obtaining_type_id:
            filter["obtainingTypeId"] = obtaining_type_id

        return await self._query("items", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": filter,
            "showForbiddenImage": True
        }, "items", Page[ItemProfile])

    async def create_item(
        self,
        game_category_id: str,
        obtaining_type_id: str,
        name: str,
        price: int,
        description: str,
        options: Sequence[GameCategoryOption] | dict[str, Any],
        data_fields: Sequence[GameCategoryDataField],
        attachments: Sequence[str | os.PathLike | bytes]
    ) -> Item:
        """
        Создаёт предмет (после создания помещается в черновик, а не сразу выставляется на продажу).

        :param game_category_id: ID категории игры, в которой необходимо создать предмет.
        :type game_category_id: `str`

        :param obtaining_type_id: ID типа получения предмета.
        :type obtaining_type_id: `str`

        :param name: Название предмета.
        :type name: `str`

        :param price: Цена предмета.
        :type price: `int` or `str`

        :param description: Описание предмета.
        :type description: `str`

        :param options: Массив **выбранных** опций (аттрибутов) предмета,
            либо готовый словарь аттрибутов вида `{поле: значение}`.
        :type options: `list[playerokapi.models.GameCategoryOption]` or `dict`

        :param data_fields: Массив полей с данными предмета. \n
            !!! Должны быть заполнены данные с типом поля `ITEM_DATA`, то есть те данные, которые указываются при заполнении информации о товаре.
            Поля с типом `OBTAINING_DATA` **заполнять и передавать не нужно**, так как эти данные будет указывать сам покупатель при оформлении предмета.
        :type data_fields: `list[playerokapi.models.GameCategoryDataField]`

        :param attachments: Массив файлов-приложений предмета. Пути к файлам или байты.
        :type attachments: `list[str | bytes]`

        :return: Объект созданного предмета.
        :rtype: `playerokapi.models.Item`
        """

        files = {f"variables.attachments.{i}": await read_image(att) for i, att in enumerate(attachments)}
        return await self._upload("createItem", {
            "input": {
                "gameCategoryId": game_category_id,
                "obtainingTypeId": obtaining_type_id,
                "name": name,
                "price": int(price),
                "description": description,
                "attributes": _attributes(options),
                "dataFields": _data_fields(data_fields)
            },
            "attachments": [None] * len(files)
        }, files, "createItem", Item)

    async def update_item(
        self,
        id: str,
        name: str | None = None,
        price: int | None = None,
        description: str | None = None,
        options: Sequence[GameCategoryOption] | dict[str, Any] | None = None,
        data_fields: Sequence[GameCategoryDataField] | None = None,
        remove_attachments: Sequence[str] | None = None,
        add_attachments: Sequence[str | os.PathLike | bytes] | None = None
    ) -> Item:
        """
        Обновляет предмет аккаунта. Изменяются только переданные параметры.

        :param id: ID предмета.
        :type id: `str`

        :param name: Название предмета, _опционально_.
        :type name: `str` or `None`

        :param price: Цена предмета, _опционально_.
        :type price: `int` or `str` or `None`

        :param description: Описание предмета, _опционально_.
        :type description: `str` or `None`

        :param options: Массив **выбранных** опций (аттрибутов) предмета или словарь `{поле: значение}`, _опционально_.
        :type options: `list[playerokapi.models.GameCategoryOption]` or `dict` or `None`

        :param data_fields: Массив полей с данными предмета (только `ITEM_DATA`), _опционально_.
        :type data_fields: `list[playerokapi.models.GameCategoryDataField]` or `None`

        :param remove_attachments: Массив ID файлов-приложений предмета, которые нужно удалить, _опционально_.
        :type remove_attachments: `list[str]` or `None`

        :param add_attachments: Массив файлов-приложений предмета, которые нужно добавить. Пути к файлам или байты, _опционально_.
        :type add_attachments: `list[str | bytes]` or `None`

        :return: Объект обновлённого предмета.
        :rtype: `playerokapi.models.Item`
        """

        input: dict[str, Any] = {"id": id}
        if name is not None:
            input["name"] = name
        if price is not None:
            input["price"] = int(price)
        if description is not None:
            input["description"] = description
        if options is not None:
            input["attributes"] = _attributes(options)
        if data_fields is not None:
            input["dataFields"] = _data_fields(data_fields)
        if remove_attachments:
            input["removedAttachments"] = list(remove_attachments)

        if not add_attachments:
            return await self._query("updateItem", {"input": input}, "updateItem", Item)

        files = {f"variables.addedAttachments.{i}": await read_image(att) for i, att in enumerate(add_attachments)}
        return await self._upload("updateItem", {
            "input": input,
            "addedAttachments": [None] * len(files)
        }, files, "updateItem", Item)

    async def remove_item(self, id: str) -> bool:
        """
        Полностью удаляет предмет вашего аккаунта.

        :param id: ID предмета.
        :type id: `str`

        :return: True, если запрос прошёл без ошибок.
        :rtype: `bool`
        """

        await self._execute("removeItem", {"id": id})
        return True

    async def publish_item(
        self,
        item_id: str,
        priority_status_id: str,
        transaction_provider_id: TransactionProviderId = TransactionProviderId.LOCAL
    ) -> Item:
        """
        Выставляет предмет на продажу.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param priority_status_id: ID статуса приоритета предмета, под которым его нужно выставить на продажу.
        :type priority_status_id: `str`

        :param transaction_provider_id: ID провайдера транзакции.
        :type transaction_provider_id: `playerokapi.models.TransactionProviderId`

        :return: Объект опубликованного предмета.
        :rtype: `playerokapi.models.Item`
        """

        return await self._query("publishItem", {
            "input": {
                "transactionProviderId": value_of(transaction_provider_id),
                "priorityStatuses": [priority_status_id],
                "itemId": item_id
            }
        }, "publishItem", Item)

    async def get_item_priority_statuses(self, item_id: str, item_price: int | str) -> list[ItemPriorityStatus]:
        """
        Получает статусы приоритетов для предмета.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param item_price: Цена предмета.
        :type item_price: `int` or `str`

        :return: Массив статусов приоритета предмета.
        :rtype: `list[playerokapi.models.ItemPriorityStatus]`
        """

        return await self._query("itemPriorityStatuses", {
            "itemId": item_id,
            "price": int(item_price)
        }, "itemPriorityStatuses", list[ItemPriorityStatus]) or []

    async def increase_item_priority_status(
        self,
        item_id: str,
        priority_status_id: str,
        payment_method_id: TransactionPaymentMethodId | None = None,
        transaction_provider_id: TransactionProviderId = TransactionProviderId.LOCAL
    ) -> Item:
        """
        Повышает статус приоритета предмета.

        :param item_id: ID предмета.
        :type item_id: `str`

        :param priority_status_id: ID статуса приоритета, на который нужно изменить.
        :type priority_status_id: `str`

        :param payment_method_id: Метод оплаты, _опционально_.
        :type payment_method_id: `playerokapi.models.TransactionPaymentMethodId` or `None`

        :param transaction_provider_id: ID провайдера транзакции (LOCAL - с баланса кошелька на сайте).
        :type transaction_provider_id: `playerokapi.models.TransactionProviderId`

        :return: Объект обновлённого предмета.
        :rtype: `playerokapi.models.Item`
        """

        return await self._query("increaseItemPriorityStatus", {
            "input": {
                "itemId": item_id,
                "priorityStatuses": [priority_status_id],
                "transactionProviderData": {"paymentMethodId": value_of(payment_method_id)},
                "transactionProviderId": value_of(transaction_provider_id)
            }
        }, "increaseItemPriorityStatus", Item)
