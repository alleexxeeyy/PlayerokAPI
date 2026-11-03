from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from .base import PlayerokModel, Tolerant
from .enums import UserType


class UserProfile(PlayerokModel):
    """
    Класс, описывающий профиль пользователя.
    """

    id: str | None = None
    """ ID пользователя. """
    username: str | None = None
    """ Никнейм пользователя. """
    role: Tolerant[UserType] = None
    """ Роль пользователя. """
    avatar_url: str | None = Field(None, alias="avatarURL")
    """ URL аватара. """
    is_online: bool | None = None
    """ В онлайне ли сейчас пользователь. """
    is_blocked: bool | None = None
    """ Заблокирован ли пользователь. """
    rating: int | float | None = None
    """ Рейтинг пользователя (0-5). """
    reviews_count: int | None = Field(None, alias="testimonialCounter")
    """ Кол-во отзывов пользователя. """
    support_chat_id: str | None = None
    """ ID чата поддержки. """
    system_chat_id: str | None = None
    """ ID системного чата. """
    created_at: Tolerant[datetime] = None
    """ Дата создания аккаунта пользователя. """


class AccountBalance(PlayerokModel):
    """
    Подкласс, описывающий баланс аккаунта.
    """

    id: str | None = None
    """ ID баланса. """
    value: int | float | None = None
    """ Сумма общего баланса. """
    frozen: int | float | None = None
    """ Сумма замороженного баланса. """
    available: int | float | None = None
    """ Сумма доступного баланса. """
    withdrawable: int | float | None = None
    """ Сумма баланса, доступного для вывода. """
    pending_income: int | float | None = None
    """ Ожидаемый доход. """


class AccountItemsStats(PlayerokModel):
    """
    Подкласс, описывающий статистику предметов аккаунта.
    """

    total: int | None = None
    """ Всего предметов. """
    finished: int | None = None
    """ Кол-во завершённых предметов. """


class AccountIncomingDealsStats(PlayerokModel):
    """
    Подкласс, описывающий статистику входящих сделок аккаунта.
    """

    total: int | None = None
    """ Всего входящих сделок. """
    finished: int | None = None
    """ Кол-во завершённых входящих сделок. """


class AccountOutgoingDealsStats(PlayerokModel):
    """
    Подкласс, описывающий статистику исходящих сделок аккаунта.
    """

    total: int | None = None
    """ Всего исходящих сделок. """
    finished: int | None = None
    """ Кол-во завершённых исходящих сделок. """
    automated_total: int | None = None
    """ Кол-во автоматических исходящих сделок. """


class AccountDealsStats(PlayerokModel):
    """
    Подкласс, описывающий статистику сделок аккаунта.
    """

    incoming: AccountIncomingDealsStats | None = None
    """ Входящие сделки. """
    outgoing: AccountOutgoingDealsStats | None = None
    """ Исходящие сделки. """


class AccountStats(PlayerokModel):
    """
    Подкласс, описывающий статистику аккаунта.
    """

    items: AccountItemsStats | None = None
    """ Статистика предметов. """
    deals: AccountDealsStats | None = None
    """ Статистика сделок. """


class AccountProfile(PlayerokModel):
    """
    Класс, описывающий профиль аккаунта.
    """

    id: str | None = None
    """ ID аккаунта. """
    username: str | None = None
    """ Никнейм аккаунта. """
    email: str | None = None
    """ Почта аккаунта. """
    balance: AccountBalance | None = None
    """ Объект баланса аккаунта. """
    stats: AccountStats | None = None
    """ Статистика аккаунта. """
    role: Tolerant[UserType] = None
    """ Роль аккаунта. """
    avatar_url: str | None = Field(None, alias="avatarURL")
    """ URL аватара аккаунта. """
    is_online: bool | None = None
    """ В онлайне ли сейчас аккаунт. """
    is_blocked: bool | None = None
    """ Заблокирован ли аккаунт. """
    is_blocked_for: str | None = None
    """ Причина блокировки аккаунта. """
    is_verified: bool | None = None
    """ Верифицирован ли аккаунт. """
    rating: int | float | None = None
    """ Рейтинг аккаунта (0-5). """
    reviews_count: int | None = Field(None, alias="testimonialCounter")
    """ Кол-во отзывов на аккаунте. """
    created_at: Tolerant[datetime] = None
    """ Дата создания аккаунта. """
    support_chat_id: str | None = None
    """ ID чата поддержки аккаунта. """
    system_chat_id: str | None = None
    """ ID системного чата аккаунта. """
    has_frozen_balance: bool | None = None
    """ Заморожен ли баланс на аккаунте. """
    has_enabled_notifications: bool | None = None
    """ Включены ли уведомления на аккаунте. """
    has_confirmed_phone_number: bool | None = None
    """ Подтверждён ли номер телефона. """
    can_publish_items: bool | None = None
    """ Может ли аккаунт выставлять предметы. """
    is_funds_protection_active: bool | None = None
    """ Включена ли защита средств. """
    unread_chats_counter: int | None = None
    """ Количество непрочитанных чатов. """
    last_item_created_at: Tolerant[datetime] = None
    """ Дата создания последнего предмета. """

    @model_validator(mode="before")
    @classmethod
    def _merge_profile(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("profile"), dict):
            data = {**data["profile"], **{k: v for k, v in data.items() if v is not None}}
        return data
