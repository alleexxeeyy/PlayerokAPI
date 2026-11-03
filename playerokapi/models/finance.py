from __future__ import annotations

from datetime import datetime

from pydantic import Field

from .base import PlayerokModel, Tolerant
from .enums import (
    BankCardType,
    TransactionDirection,
    TransactionOperation,
    TransactionPaymentMethodId,
    TransactionProviderId,
    TransactionStatus,
)
from .users import UserProfile


class SBPBankMember(PlayerokModel):
    """
    Объект членов СБП банка.
    """

    id: str | None = None
    """ ID. """
    name: str | None = None
    """ Название. """
    icon: str | None = None
    """ URL иконки. """


class TransactionProviderLimitRange(PlayerokModel):
    """
    Диапазон лимитов провайдера транзакции.
    """

    min: int | float | None = None
    """ Минимальная сумма (в рублях). """
    max: int | float | None = None
    """ Максимальная сумма (в рублях). """


class TransactionProviderLimits(PlayerokModel):
    """
    Лимиты провайдера транзакции.
    """

    incoming: TransactionProviderLimitRange | None = None
    """ На пополнение. """
    outgoing: TransactionProviderLimitRange | None = None
    """ На вывод. """


class TransactionProviderRequiredUserData(PlayerokModel):
    """
    Обязательные пользовательские данные провайдера транзакции.
    """

    email: bool | None = None
    """ Обязательно ли указывать EMail? """
    phone_number: bool | None = None
    """ Обязательно ли указывать номер телефона? """
    erip_account_number: bool | None = None
    """ Обязательно ли указывать номер аккаунта ЕРИП? """


class TransactionProviderProps(PlayerokModel):
    """
    Параметры провайдера транзакции.
    """

    required_user_data: TransactionProviderRequiredUserData | None = None
    """ Обязательные пользовательские данные. """
    tooltip: str | None = None
    """ Подсказка. """


class TransactionProviderAccount(PlayerokModel):
    """
    Сохранённый счёт провайдера транзакции.
    """

    id: str | None = None
    """ ID счёта. """
    value: str | None = None
    """ Значение счёта (номер карты, телефона и т.п.). """
    user_id: str | None = None
    """ ID пользователя. """
    provider_id: Tolerant[TransactionProviderId] = None
    """ ID провайдера. """
    payment_method_id: str | None = None
    """ ID платёжного метода. """


class TransactionPaymentMethod(PlayerokModel):
    """
    Платёжный метод транзакции.
    """

    id: Tolerant[TransactionPaymentMethodId] = None
    """ ID метода. """
    name: str | None = None
    """ Название метода. """
    fee: int | float | None = None
    """ Комиссия метода. """
    provider_id: Tolerant[TransactionProviderId] = None
    """ ID провайдера транзакции. """
    account: TransactionProviderAccount | None = None
    """ Сохранённый счёт метода. """
    props: TransactionProviderProps | None = None
    """ Параметры провайдера транзакции. """
    limits: TransactionProviderLimits | None = None
    """ Лимиты провайдера транзакции. """


class TransactionProvider(PlayerokModel):
    """
    Объект провайдера транзакции.
    """

    id: Tolerant[TransactionProviderId] = None
    """ ID провайдера. """
    name: str | None = None
    """ Название провайдера. """
    fee: int | float | None = None
    """ Комиссия провайдера. """
    min_fee_amount: int | float | None = None
    """ Минимальная комиссия. """
    description: str | None = None
    """ Описание провайдера. """
    account: TransactionProviderAccount | None = None
    """ Сохранённый счёт провайдера. """
    props: TransactionProviderProps | None = None
    """ Параметры провайдера. """
    limits: TransactionProviderLimits | None = None
    """ Лимиты провайдера. """
    payment_methods: list[TransactionPaymentMethod] = []
    """ Платёжные методы. """


class TransactionPropsUserData(PlayerokModel):
    """
    Подкласс, описывающий данные пользователя в параметрах транзакции.
    """

    account: str | None = None
    """ Счёт пользователя. """
    email: str | None = None
    """ Почта пользователя. """
    ip_address: str | None = None
    """ IP адрес пользователя. """
    phone_number: str | None = None
    """ Номер телефона пользователя. """


class TransactionPropsPaymentAccount(PlayerokModel):
    """
    Подкласс, описывающий платёжный счёт в параметрах транзакции.
    """

    id: str | None = None
    """ ID счёта. """
    value: str | None = None
    """ Значение счёта. """


class TransactionProps(PlayerokModel):
    """
    Подкласс, описывающий параметры транзакции.
    """

    creator_id: str | None = None
    """ ID создателя транзакции. """
    deal_id: str | None = None
    """ ID сделки транзакции. """
    paid_from_pending_income: bool | None = None
    """ Оплачено ли из замороженных средств. """
    payment_url: str | None = Field(None, alias="paymentURL")
    """ Ссылка на оплату. """
    success_url: str | None = Field(None, alias="successURL")
    """ Ссылка на страницу успешной оплаты. """
    fee: int | float | None = None
    """ Комиссия транзакции. """
    payment_account: TransactionPropsPaymentAccount | None = None
    """ Платёжный счёт. """
    payment_gateway: str | None = None
    """ Платёжный шлюз. """
    already_spent: int | float | None = None
    """ Уже потраченная сумма. """
    exchange_rate: float | None = None
    """ Курс обмена. """
    amount_after_conversion_rub: float | None = None
    """ Сумма после конвертации в рублях. """
    amount_after_conversion_usdt: float | None = None
    """ Сумма после конвертации в USDT. """
    fragment_username: str | None = None
    """ Имя пользователя Fragment. """
    user_data: TransactionPropsUserData | None = None
    """ Данные пользователя. """


class Transaction(PlayerokModel):
    """
    Объект транзакции.
    """

    id: str | None = None
    """ ID транзакции. """
    operation: Tolerant[TransactionOperation] = None
    """ Тип выполненной операции. """
    direction: Tolerant[TransactionDirection] = None
    """ Направление транзакции. """
    provider_id: Tolerant[TransactionProviderId] = None
    """ ID платёжного провайдера. """
    provider: TransactionProvider | None = None
    """ Объект провайдера транзакции. """
    user: UserProfile | None = None
    """ Объект пользователя-совершателя транзакции. """
    creator: UserProfile | None = None
    """ Объект пользователя-создателя транзакции. """
    status: Tolerant[TransactionStatus] = None
    """ Статус обработки транзакции. """
    status_description: str | None = None
    """ Описание статуса. """
    status_expiration_date: Tolerant[datetime] = None
    """ Дата истечения статуса. """
    value: int | float | None = None
    """ Сумма транзакции. """
    fee: int | float | None = None
    """ Комиссия транзакции. """
    created_at: Tolerant[datetime] = None
    """ Дата создания транзакции. """
    verified_at: Tolerant[datetime] = None
    """ Дата подтверждения транзакции. """
    verified_by: UserProfile | None = None
    """ Объект пользователя, подтвердившего транзакцию. """
    completed_at: Tolerant[datetime] = None
    """ Дата выполнения транзакции. """
    completed_by: UserProfile | None = None
    """ Объект пользователя, выполнившего транзакцию. """
    auto_claimed_at: Tolerant[datetime] = None
    """ Дата автоматического зачисления. """
    payment_method_id: str | None = None
    """ ID способа оплаты. """
    is_suspicious: bool | None = None
    """ Подозрительная ли транзакция. """
    sbp_bank_name: str | None = Field(None, alias="spbBankName")
    """ Название банка СБП (если транзакция была совершена с помощью СБП). """
    props: TransactionProps | None = None
    """ Параметры транзакции. """


class UserBankCard(PlayerokModel):
    """
    Объект банковской карты пользователя.
    """

    id: str | None = None
    """ ID карты. """
    card_first_six: str | None = None
    """ Первые шесть цифр карты. """
    card_last_four: str | None = None
    """ Последние четыре цифры карты. """
    card_type: Tolerant[BankCardType] = None
    """ Тип банковской карты. """
    is_chosen: bool | None = None
    """ Выбрана ли эта карта как по умолчанию? """
