from __future__ import annotations

from datetime import datetime, timezone

from ..models import (
    Page,
    SBPBankMember,
    SortDirection,
    Transaction,
    TransactionOperation,
    TransactionPaymentMethodId,
    TransactionProvider,
    TransactionProviderDirection,
    TransactionProviderId,
    TransactionStatus,
    UserBankCard,
)
from .base import BaseClient, value_of


def _iso(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


class FinanceMixin(BaseClient):

    async def get_transaction_providers(
        self,
        direction: TransactionProviderDirection | None = TransactionProviderDirection.IN
    ) -> list[TransactionProvider]:
        """
        Получает всех провайдеров транзакций.

        :param direction: Направление транзакций (пополнение/вывод).
        :type direction: `playerokapi.models.TransactionProviderDirection` or `None`

        :return: Список провайдеров транзакций.
        :rtype: `list[playerokapi.models.TransactionProvider]`
        """

        return await self._query("transactionProviders", {
            "filter": {"direction": value_of(direction)}
        }, "transactionProviders", list[TransactionProvider]) or []

    async def get_transactions(
        self,
        status: TransactionStatus | None = None,
        operation: TransactionOperation | None = None,
        provider_id: TransactionProviderId | None = None,
        min_value: int | None = None,
        max_value: int | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[Transaction]:
        """
        Получает все транзакции аккаунта.

        :param status: Статус транзакции, _опционально_.
        :type status: `playerokapi.models.TransactionStatus` or `None`

        :param operation: Операция транзакции, _опционально_.
        :type operation: `playerokapi.models.TransactionOperation` or `None`

        :param provider_id: ID провайдера транзакции, _опционально_.
        :type provider_id: `playerokapi.models.TransactionProviderId` or `None`

        :param min_value: Минимальная сумма транзакции, _опционально_.
        :type min_value: `int` or `None`

        :param max_value: Максимальная сумма транзакции, _опционально_.
        :type max_value: `int` or `None`

        :param from_date: Минимальная дата транзакции (без таймзоны считается UTC), _опционально_.
        :type from_date: `datetime` or `None`

        :param to_date: Максимальная дата транзакции (без таймзоны считается UTC), _опционально_.
        :type to_date: `datetime` or `None`

        :param count: Кол-во транзакций, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница транзакций.
        :rtype: `playerokapi.models.Page[playerokapi.models.Transaction]`
        """

        filter: dict = {"userId": await self._me_id()}
        if status:
            filter["status"] = [value_of(status)]
        if operation:
            filter["operation"] = [value_of(operation)]
        if provider_id:
            filter["providerId"] = [value_of(provider_id)]
        if min_value is not None or max_value is not None:
            filter["value"] = {}
            if min_value is not None:
                filter["value"]["min"] = str(min_value)
            if max_value is not None:
                filter["value"]["max"] = str(max_value)
        if from_date or to_date:
            filter["dateRange"] = {}
            if from_date:
                filter["dateRange"]["from"] = _iso(from_date)
            if to_date:
                filter["dateRange"]["to"] = _iso(to_date)

        return await self._query("transactions", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": filter,
            "hasSupportAccess": False
        }, "transactions", Page[Transaction])

    async def get_sbp_bank_members(self) -> list[SBPBankMember]:
        """
        Получает всех членов банка СБП.

        :return: Список членов банка СБП.
        :rtype: `list[playerokapi.models.SBPBankMember]`
        """

        return await self._query("SbpBankMembers", {}, "sbpBankMembers", list[SBPBankMember]) or []

    async def get_verified_cards(
        self,
        count: int = 24,
        after_cursor: str | None = None,
        direction: SortDirection = SortDirection.ASC
    ) -> Page[UserBankCard]:
        """
        Получает верифицированные карты аккаунта.

        :param count: Кол-во банковских карт, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :param direction: Тип сортировки банковских карт.
        :type direction: `playerokapi.models.SortDirection`

        :return: Страница банковских карт пользователя.
        :rtype: `playerokapi.models.Page[playerokapi.models.UserBankCard]`
        """

        return await self._query("verifiedCards", {
            "pagination": {"first": count, "after": after_cursor},
            "sort": {"direction": value_of(direction)},
            "field": "createdAt"
        }, "verifiedCards", Page[UserBankCard])

    async def delete_card(self, card_id: str) -> bool:
        """
        Удаляет карту из сохранённых в аккаунте.

        :param card_id: ID банковской карты.
        :type card_id: `str`

        :return: True, если карта удалилась, иначе False.
        :rtype: `bool`
        """

        data = await self._execute("deleteCard", {"input": {"cardId": card_id}})
        return bool(data.get("deleteCard"))

    async def request_withdrawal(
        self,
        provider: TransactionProviderId,
        account: str,
        value: int,
        payment_method_id: TransactionPaymentMethodId | None = None,
        sbp_bank_member_id: str | None = None
    ) -> Transaction:
        """
        Создаёт запрос на вывод средств с баланса аккаунта.\n
        Запрос не повторяется автоматически, если ответ не дошёл: проверьте `get_transactions()`, прежде чем отправлять снова.

        :param provider: Провайдер транзакции.
        :type provider: `playerokapi.models.TransactionProviderId`

        :param account: ID добавленной карты (или номер телефона, если провайдер СБП), на которую нужно совершить вывод.
        :type account: `str`

        :param value: Сумма вывода.
        :type value: `int`

        :param payment_method_id: ID платёжного метода, _опционально_.
        :type payment_method_id: `playerokapi.models.TransactionPaymentMethodId` or `None`

        :param sbp_bank_member_id: ID члена банка СБП (только если указан провайдер СБП), _опционально_.
        :type sbp_bank_member_id: `str` or `None`

        :return: Объект транзакции вывода.
        :rtype: `playerokapi.models.Transaction`
        """

        return await self._query("requestWithdrawal", {
            "input": {
                "provider": value_of(provider),
                "account": account,
                "value": value,
                "providerData": {
                    "paymentMethodId": value_of(payment_method_id),
                    "sbpBankMemberId": sbp_bank_member_id or None
                }
            }
        }, "requestWithdrawal", Transaction)

    async def remove_transaction(self, transaction_id: str) -> Transaction:
        """
        Удаляет транзакцию (например, можно отменить вывод).

        :param transaction_id: ID транзакции.
        :type transaction_id: `str`

        :return: Объект отменённой транзакции.
        :rtype: `playerokapi.models.Transaction`
        """

        return await self._query("removeTransaction", {"id": transaction_id}, "removeTransaction", Transaction)
