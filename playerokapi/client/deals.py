from __future__ import annotations

from collections.abc import Sequence

from ..models import Deal, DealDirection, DealStatus, Page
from .base import BaseClient, value_of


class DealsMixin(BaseClient):

    async def get_deals(
        self,
        statuses: Sequence[DealStatus] | None = None,
        direction: DealDirection | None = None,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[Deal]:
        """
        Получает сделки аккаунта.

        :param statuses: Статусы, сделки которых нужно получать, _опционально_.
        :type statuses: `list[playerokapi.models.DealStatus]` or `None`

        :param direction: Направление сделок, _опционально_.
        :type direction: `playerokapi.models.DealDirection` or `None`

        :param count: Кол-во сделок, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница сделок.
        :rtype: `playerokapi.models.Page[playerokapi.models.Deal]`
        """

        return await self._query("deals", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {
                "userId": await self._me_id(),
                "direction": value_of(direction),
                "status": [value_of(s) for s in statuses] if statuses else None
            },
            "showForbiddenImage": True
        }, "deals", Page[Deal])

    async def get_deal(self, deal_id: str) -> Deal:
        """
        Получает сделку.

        :param deal_id: ID сделки.
        :type deal_id: `str`

        :return: Объект сделки.
        :rtype: `playerokapi.models.Deal`
        """

        return await self._query("deal", {
            "id": deal_id,
            "hasSupportAccess": False,
            "showForbiddenImage": True
        }, "deal", Deal)

    async def update_deal(self, deal_id: str, new_status: DealStatus) -> Deal:
        """
        Обновляет статус сделки
        (используется, чтобы подтвердить, оформить возврат и т.д).

        :param deal_id: ID сделки.
        :type deal_id: `str`

        :param new_status: Новый статус сделки.
        :type new_status: `playerokapi.models.DealStatus`

        :return: Объект обновлённой сделки.
        :rtype: `playerokapi.models.Deal`
        """

        return await self._query("updateDeal", {
            "input": {"id": deal_id, "status": value_of(new_status)}
        }, "updateDeal", Deal)

    async def report_deal_problem(self, deal_id: str, description: str, problem_type_id: str) -> Deal:
        """
        Создаёт проблему в сделке.

        :param deal_id: ID сделки.
        :type deal_id: `str`

        :param description: Описание проблемы.
        :type description: `str`

        :param problem_type_id: ID типа проблемы (шаблонного сообщения в `get_message_templates()`).
        :type problem_type_id: `str`

        :return: Объект обновлённой сделки.
        :rtype: `playerokapi.models.Deal`
        """

        return await self._query("reportDealProblem", {
            "input": {"dealId": deal_id, "description": description, "problemTypeId": problem_type_id}
        }, "reportDealProblem", Deal)
