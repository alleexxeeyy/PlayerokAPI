from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from pydantic import Field

from .base import PlayerokModel, Tolerant
from .enums import DealDirection, DealStatus
from .finance import Transaction
from .games import GameCategoryDataField
from .items import AnyItem, ItemLog
from .users import UserProfile

if TYPE_CHECKING:
    from .chats import Chat
    from .reviews import Review


class DealConfirmationRestrictionTexts(PlayerokModel):
    """
    Тексты ограничения подтверждения сделки.
    """

    seller_deal_subtitle: str | None = None
    """ Подзаголовок сделки для продавца. """
    buyer_deal_subtitle: str | None = None
    """ Подзаголовок сделки для покупателя. """
    buyer_timer_text: str | None = None
    """ Текст таймера для покупателя. """


class DealProps(PlayerokModel):
    """
    Параметры сделки.
    """

    auto_confirm_period: int | None = None
    """ Срок авто-подтверждения сделки. """
    confirmation_restriction: bool | None = None
    """ Ограничено ли подтверждение сделки. """
    confirmation_restriction_texts: DealConfirmationRestrictionTexts | None = None
    """ Тексты ограничения подтверждения сделки. """


class DealWarning(PlayerokModel):
    """
    Предупреждение сделки.
    """

    id: str | None = None
    """ ID предупреждения. """
    status: Tolerant[DealStatus] = None
    """ Статус сделки, на котором показывается предупреждение. """
    title: str | None = None
    """ Заголовок предупреждения. """
    text: str | None = None
    """ Текст предупреждения. """


class DealAutomationObtainingField(PlayerokModel):
    """
    Поле автоматической выдачи сделки.
    """

    code: str | None = None
    """ Код поля. """
    value: str | None = None
    """ Значение поля. """
    name: str | None = None
    """ Название поля. """


class Deal(PlayerokModel):
    """
    Объект сделки с предметом.
    """

    id: str | None = None
    """ ID сделки. """
    status: Tolerant[DealStatus] = None
    """ Статус сделки. """
    status_expiration_date: Tolerant[datetime] = None
    """ Дата истечения статуса. """
    status_description: str | None = None
    """ Описание статуса сделки. """
    direction: Tolerant[DealDirection] = None
    """ Направление сделки (покупка/продажа). """
    obtaining: str | None = None
    """ Получение сделки. """
    has_problem: bool | None = None
    """ Есть ли проблема в сделке. """
    report_problem_enabled: bool | None = None
    """ Включено ли обжалование проблемы. """
    completed_by: UserProfile | None = None
    """ Профиль пользователя, подтвердившего сделку. """
    props: DealProps | None = None
    """ Прочие настройки сделки. """
    previous_status: Tolerant[DealStatus] = Field(None, alias="prevStatus")
    """ Предыдущий статус. """
    completed_at: Tolerant[datetime] = None
    """ Дата подтверждения сделки. """
    created_at: Tolerant[datetime] = None
    """ Дата создания сделки. """
    logs: list[ItemLog] = []
    """ Логи сделки. """
    transaction: Transaction | None = None
    """ Транзакция сделки. """
    user: UserProfile | None = None
    """ Профиль пользователя, совершившего сделку. """
    chat: Chat | None = None
    """ Чат сделки (передаётся только его ID). """
    item: AnyItem = None
    """ Предмет сделки. """
    review: Review | None = Field(None, alias="testimonial")
    """ Отзыв по сделке. """
    obtaining_fields: list[GameCategoryDataField] = []
    """ Получаемые поля. """
    comment_from_buyer: str | None = None
    """ Комментарий от покупателя. """
    automation_obtaining_fields: list[DealAutomationObtainingField] = []
    """ Поля автоматической выдачи. """
    game_category_warnings: list[DealWarning] = []
    """ Предупреждения категории игры. """
    obtaining_type_warnings: list[DealWarning] = []
    """ Предупреждения способа получения. """
    is_automated: bool | None = None
    """ Является ли сделка автоматической. """
