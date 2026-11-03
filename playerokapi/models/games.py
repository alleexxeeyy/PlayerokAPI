from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .base import PlayerokModel, Tolerant
from .common import FileObject
from .enums import (
    GameCategoryAgreementIconType,
    GameCategoryAutoConfirmPeriod,
    GameCategoryDataFieldInputType,
    GameCategoryDataFieldType,
    GameCategoryOptionType,
    GameType,
)


class GameCategoryProps(PlayerokModel):
    """
    Подкласс, описывающий пропорции категории.
    """

    min_reviews: int | None = Field(None, alias="minTestimonials")
    """ Минимальное количество отзывов. """
    min_reviews_for_seller: int | None = Field(None, alias="minTestimonialsForSeller")
    """ Минимальное количество отзывов для продавца. """


class GameCategoryOptionValueRangeLimit(PlayerokModel):
    """
    Подкласс, описывающий лимит разброса по значению опции категории.
    """

    min: int | float | None = None
    """ Минимальное значение. """
    max: int | float | None = None
    """ Максимальное значение. """


class GameCategoryOption(PlayerokModel):
    """
    Подкласс, описывающий опцию категории.
    """

    id: str | None = None
    """ ID опции. """
    group: str | None = None
    """ Группа опции. """
    label: str | None = None
    """ Надпись-название опции. """
    type: Tolerant[GameCategoryOptionType] = None
    """ Тип опции. """
    field: str | None = None
    """ Название поля (для payload запроса на сайт). """
    value: str | None = None
    """ Значение поля (для payload запроса на сайт). """
    value_range_limit: GameCategoryOptionValueRangeLimit | None = None
    """ Лимит разброса по значению. """
    multiple: bool | None = None
    """ Можно ли выбрать несколько значений опции. """


class GameCategoryAgreement(PlayerokModel):
    """
    Подкласс, описывающий соглашения покупателя.
    """

    id: str | None = None
    """ ID соглашения. """
    description: str | None = None
    """ Описание соглашения. """
    icon_type: Tolerant[GameCategoryAgreementIconType] = None
    """ Тип иконки соглашения. """
    sequence: int | None = None
    """ Последовательность соглашения. """
    game_category_id: str | None = None
    """ ID категории игры соглашения. """
    game_category_obtaining_type_id: str | None = None
    """ ID способа получения соглашения. """


class GameCategoryObtainingType(PlayerokModel):
    """
    Подкласс, описывающий тип (способ) получения предмета в категории.
    """

    id: str | None = None
    """ ID способа. """
    name: str | None = None
    """ Название способа. """
    description: str | None = None
    """ Описание способа. """
    game_category_id: str | None = None
    """ ID категории игры способа. """
    no_comment_from_buyer: bool | None = None
    """ Без комментария от покупателя? """
    instruction_for_buyer: str | None = None
    """ Инструкция для покупателя. """
    instruction_for_seller: str | None = None
    """ Инструкция для продавца. """
    sequence: int | None = None
    """ Последовательность способа. """
    fee_multiplier: float | None = None
    """ Множитель комиссии. """
    agreements: list[GameCategoryAgreement] = []
    """ Соглашения покупателя на покупку/продавца на продажу. """
    props: GameCategoryProps | None = None
    """ Пропорции категории. """
    stock_type: str | None = None
    """ Тип склада способа получения. """


class GameCategoryDataField(PlayerokModel):
    """
    Подкласс, описывающий поля с данными предмета в категории (которые отправляются после покупки).
    """

    id: str | None = None
    """ ID поля с данными. """
    label: str | None = None
    """ Надпись-название поля. """
    type: Tolerant[GameCategoryDataFieldType] = None
    """ Тип поля с данными. """
    input_type: Tolerant[GameCategoryDataFieldInputType] = None
    """ Тип вводимого значения поля. """
    copyable: bool | None = None
    """ Разрешено ли копирование значения с поля. """
    hidden: bool | None = None
    """ Скрыты ли данные в поле. """
    required: bool | None = None
    """ Обязательно ли это поле. """
    value: str | None = None
    """ Значение данных в поле. """


class GameCategoryInstruction(PlayerokModel):
    """
    Подкласс, описывающий инструкцию по продаже/покупке в категории.
    """

    id: str | None = None
    """ ID инструкции. """
    text: str | None = None
    """ Текст инструкции. """


class GameCategory(PlayerokModel):
    """
    Объект категории игры/приложения.
    """

    id: str | None = None
    """ ID категории. """
    slug: str | None = None
    """ Имя страницы категории. """
    name: str | None = None
    """ Название категории. """
    category_id: str | None = None
    """ ID родительской категории. """
    game_id: str | None = None
    """ ID игры категории. """
    obtaining: str | None = None
    """ Тип получения. """
    options: list[GameCategoryOption] = []
    """ Опции категории. """
    props: GameCategoryProps | None = None
    """ Пропорции категории. """
    no_comment_from_buyer: bool | None = None
    """ Без комментария от покупателя? """
    instruction_for_buyer: str | None = None
    """ Инструкция для покупателя. """
    instruction_for_seller: str | None = None
    """ Инструкция для продавца. """
    use_custom_obtaining: bool | None = None
    """ Используется ли кастомное получение. """
    auto_confirm_period: Tolerant[GameCategoryAutoConfirmPeriod] = None
    """ Период авто-подтверждения сделки этой категории. """
    auto_moderation_mode: bool | None = None
    """ Включена ли автоматическая модерация. """
    agreements: list[GameCategoryAgreement] = []
    """ Соглашения покупателя. """
    fee_multiplier: float | None = None
    """ Множитель комиссии. """


class GameProfile(PlayerokModel):
    """
    Профиль игры/приложения.
    """

    id: str | None = None
    """ ID игры/приложения. """
    slug: str | None = None
    """ Имя страницы игры/приложения. """
    name: str | None = None
    """ Название игры/приложения. """
    type: Tolerant[GameType] = None
    """ Тип: игра или приложение. """
    logo: FileObject | None = None
    """ Лого игры/приложения. """


class Game(PlayerokModel):
    """
    Объект игры/приложения.
    """

    id: str | None = None
    """ ID игры/приложения. """
    slug: str | None = None
    """ Имя страницы игры/приложения. """
    name: str | None = None
    """ Название игры/приложения. """
    type: Tolerant[GameType] = None
    """ Тип: игра или приложение. """
    logo: FileObject | None = None
    """ Лого игры/приложения. """
    banner: FileObject | None = None
    """ Баннер игры/приложения. """
    categories: list[GameCategory] = []
    """ Список категорий игры/приложения. """
    is_new: bool | None = None
    """ Новая ли игра/приложение. """
    created_at: Tolerant[datetime] = None
    """ Дата создания. """
