from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Union

from pydantic import Field, PlainValidator, SerializeAsAny

from .base import PlayerokModel, Tolerant
from .common import FileObject, Moderator
from .enums import ItemLogEvent, ItemStatus, PriorityType, UserType
from .finance import Transaction
from .games import GameCategory, GameCategoryDataField, GameCategoryObtainingType, GameProfile
from .users import UserProfile


class ItemPriorityStatusPriceRange(PlayerokModel):
    """
    Подкласс, описывающий ценовой диапазон предмета, подходящего для опред. статуса приоритета.
    """

    min: int | float | None = None
    """ Минимальная цена предмета (в рублях). """
    max: int | float | None = None
    """ Максимальная цена предмета (в рублях). """


class ItemPriorityStatus(PlayerokModel):
    """
    Класс, описывающий статус приоритета предмета.
    """

    id: str | None = None
    """ ID статуса приоритета. """
    price: int | float | None = None
    """ Цена статуса (в рублях). """
    name: str | None = None
    """ Название статуса. """
    type: Tolerant[PriorityType] = None
    """ Тип статуса. """
    period: int | None = None
    """ Длительность статуса (в днях). """
    price_range: ItemPriorityStatusPriceRange | None = None
    """ Ценовой диапазон предмета статуса. """


class ItemLog(PlayerokModel):
    """
    Подкласс, описывающий лог действия с предметом.
    """

    id: str | None = None
    """ ID лога. """
    event: Tolerant[ItemLogEvent] = None
    """ Событие лога. """
    created_at: Tolerant[datetime] = None
    """ Дата создания лога. """
    user: UserProfile | None = None
    """ Профиль пользователя, совершившего лог. """


class ItemCharacteristic(PlayerokModel):
    """
    Подкласс, описывающий характеристику предмета.
    """

    label: str | None = None
    """ Название характеристики. """
    value: str | None = None
    """ Значение характеристики. """


class Item(PlayerokModel):
    """
    Объект предмета.
    """

    typename: str | None = Field("Item", alias="__typename")
    """ Тип объекта в API. """
    id: str | None = None
    """ ID предмета. """
    slug: str | None = None
    """ Имя страницы предмета. """
    name: str | None = None
    """ Название предмета. """
    description: str | None = None
    """ Описание предмета. """
    obtaining_type: GameCategoryObtainingType | None = None
    """ Способ получения. """
    price: int | float | None = None
    """ Цена предмета. """
    raw_price: int | float | None = None
    """ Цена без учёта скидки. """
    priority: Tolerant[PriorityType] = None
    """ Статус приоритета. """
    priority_position: int | None = None
    """ Приоритетная позиция. """
    attachments: list[FileObject] = []
    """ Файлы-приложения. """
    attributes: Any = None
    """ Аттрибуты предмета. """
    category: GameCategory | None = None
    """ Категория игры предмета. """
    comment: str | None = None
    """ Комментарий предмета. """
    data_fields: list[GameCategoryDataField] = []
    """ Поля данных предмета. """
    fee_multiplier: float | None = None
    """ Множитель комиссии. """
    game: GameProfile | None = None
    """ Профиль игры предмета. """
    seller_type: Tolerant[UserType] = None
    """ Тип продавца. """
    status: Tolerant[ItemStatus] = None
    """ Статус предмета. """
    user: UserProfile | None = None
    """ Профиль продавца. """
    characteristics: list[ItemCharacteristic] = []
    """ Характеристики предмета. """
    is_attachments_forbidden: bool | None = None
    """ Запрещены ли файлы-приложения. """
    is_automated: bool | None = None
    """ Является ли предмет автоматическим. """
    buyer: UserProfile | None = None
    """ Профиль покупателя предмета (если продан). """
    post_moderation_checked_at: Tolerant[datetime] = None
    """ Дата проверки постмодерацией. """


class MyItem(PlayerokModel):
    """
    Объект своего предмета.
    """

    typename: str | None = Field("MyItem", alias="__typename")
    """ Тип объекта в API. """
    id: str | None = None
    """ ID предмета. """
    slug: str | None = None
    """ Имя страницы предмета. """
    name: str | None = None
    """ Название предмета. """
    status: Tolerant[ItemStatus] = None
    """ Статус предмета. """
    description: str | None = None
    """ Описание предмета. """
    obtaining_type: GameCategoryObtainingType | None = None
    """ Способ получения. """
    price: int | float | None = None
    """ Цена предмета. """
    prev_price: int | float | None = None
    """ Предыдущая цена. """
    raw_price: int | float | None = None
    """ Цена без учёта скидки. """
    priority_position: int | None = None
    """ Приоритетная позиция. """
    attachments: list[FileObject] = []
    """ Файлы-приложения. """
    attributes: Any = None
    """ Аттрибуты предмета. """
    category: GameCategory | None = None
    """ Категория игры предмета. """
    comment: str | None = None
    """ Комментарий предмета. """
    data_fields: list[GameCategoryDataField] = []
    """ Поля данных предмета. """
    fee_multiplier: float | None = None
    """ Множитель комиссии. """
    prev_fee_multiplier: float | None = None
    """ Предыдущий множитель комиссии. """
    seller_notified_about_fee_change: bool | None = None
    """ Оповещён ли продавец о смене комиссии. """
    game: GameProfile | None = None
    """ Профиль игры предмета. """
    seller_type: Tolerant[UserType] = None
    """ Тип продавца. """
    user: UserProfile | None = None
    """ Профиль продавца. """
    buyer: UserProfile | None = None
    """ Профиль покупателя предмета (если продан). """
    priority: Tolerant[PriorityType] = None
    """ Статус приоритета предмета. """
    priority_price: int | float | None = None
    """ Цена статуса приоритета. """
    sequence: int | None = None
    """ Позиция предмета в таблице товаров пользователей. """
    status_expiration_date: Tolerant[datetime] = None
    """ Дата истечения статуса приоритета. """
    status_description: str | None = None
    """ Описание статуса приоритета. """
    status_payment: Transaction | None = None
    """ Платёж статуса (транзакция). """
    views_counter: int | None = None
    """ Количество просмотров предмета. """
    is_editable: bool | None = Field(None, alias="editable")
    """ Можно ли редактировать товар. """
    approval_date: Tolerant[datetime] = None
    """ Дата публикации товара. """
    deleted_at: Tolerant[datetime] = None
    """ Дата удаления товара. """
    updated_at: Tolerant[datetime] = None
    """ Дата последнего обновления товара. """
    created_at: Tolerant[datetime] = None
    """ Дата создания товара. """
    characteristics: list[ItemCharacteristic] = []
    """ Характеристики предмета. """
    is_attachments_forbidden: bool | None = None
    """ Запрещены ли файлы-приложения. """
    is_automated: bool | None = None
    """ Является ли предмет автоматическим. """
    deals_counter: int | None = None
    """ Количество сделок по предмету. """
    keep_in_sale: bool | None = None
    """ Оставить ли предмет в продаже после покупки. """
    keep_in_sale_available: bool | None = None
    """ Доступно ли оставление предмета в продаже после покупки. """
    may_be_published: bool | None = None
    """ Может ли предмет быть опубликован. """
    post_moderation_checked_at: Tolerant[datetime] = None
    """ Дата проверки постмодерацией. """
    moderator: Moderator | None = None
    """ Модератор, проверивший предмет. """


class ItemProfile(PlayerokModel):
    """
    Профиль предмета.
    """

    typename: str | None = Field("ItemProfile", alias="__typename")
    """ Тип объекта в API. """
    id: str | None = None
    """ ID предмета. """
    slug: str | None = None
    """ Имя страницы предмета. """
    priority: Tolerant[PriorityType] = None
    """ Приоритет предмета. """
    status: Tolerant[ItemStatus] = None
    """ Статус предмета. """
    name: str | None = None
    """ Название предмета. """
    price: int | float | None = None
    """ Цена предмета. """
    raw_price: int | float | None = None
    """ Цена без учёта скидки. """
    seller_type: Tolerant[UserType] = None
    """ Тип продавца. """
    attachment: FileObject | None = None
    """ Файл-приложение. """
    user: UserProfile | None = None
    """ Профиль продавца. """
    game: GameProfile | None = None
    """ Профиль игры предмета (передаётся только название). """
    category: GameCategory | None = None
    """ Категория игры предмета (передаётся только название). """
    approval_date: Tolerant[datetime] = None
    """ Дата одобрения. """
    priority_position: int | None = None
    """ Приоритетная позиция. """
    views_counter: int | None = None
    """ Количество просмотров. """
    fee_multiplier: float | None = None
    """ Множитель комиссии. """
    created_at: Tolerant[datetime] = None
    """ Дата создания. """
    deals_counter: int | None = None
    """ Количество сделок по предмету. """
    keep_in_sale: bool | None = None
    """ Оставить ли предмет в продаже после покупки (только у своих предметов). """
    status_expiration_date: Tolerant[datetime] = None
    """ Дата истечения статуса приоритета (только у своих предметов). """
    is_attachments_forbidden: bool | None = None
    """ Запрещены ли файлы-приложения. """
    is_automated: bool | None = None
    """ Является ли предмет автоматическим. """


_ITEM_CLASSES = {
    "MyItem": "MyItem",
    "Item": "Item",
    "ForeignItem": "Item",
    "ItemProfile": "ItemProfile",
    "MyItemProfile": "ItemProfile",
    "ForeignItemProfile": "ItemProfile",
}


def _parse_item(value: Any) -> MyItem | Item | ItemProfile:
    if isinstance(value, (MyItem, Item, ItemProfile)):
        return value
    if not isinstance(value, dict):
        raise ValueError(f"предмет должен быть объектом, а не {type(value).__name__}")
    typename = value.get("__typename") or value.get("typename")
    name = _ITEM_CLASSES.get(typename) if isinstance(typename, str) else None
    if name is None:
        raise ValueError(f"неизвестный тип предмета: {typename!r}")
    return {"MyItem": MyItem, "Item": Item, "ItemProfile": ItemProfile}[name].model_validate(value)


AnyItem = Tolerant[SerializeAsAny[Annotated[Union[MyItem, Item, ItemProfile], PlainValidator(_parse_item)]]]
