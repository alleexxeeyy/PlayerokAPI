from __future__ import annotations

from ..models import Page, Review, ReviewStatus, SortDirection, UserProfile
from .base import BaseClient, parse, value_of


class UsersMixin(BaseClient):

    async def get_user(
        self,
        id: str | None = None,
        username: str | None = None
    ) -> UserProfile | None:
        """
        Получает профиль пользователя.\n
        Можно получить по любому из двух параметров:

        :param id: ID пользователя, _опционально_.
        :type id: `str` or `None`

        :param username: Никнейм пользователя, _опционально_.
        :type username: `str` or `None`

        :return: Объект профиля пользователя (`None`, если не найден).
        :rtype: `playerokapi.models.UserProfile` or `None`
        """

        if not any((id, username)):
            raise TypeError("Не был передан ни один из обязательных аргументов: id, username")

        data = (await self._execute("user", {"id": id, "username": username, "hasSupportAccess": False})).get("user")
        if not isinstance(data, dict):
            return None
        if data.get("__typename") == "User":
            data = data.get("profile")
        return parse(UserProfile, data)

    async def get_my_reviews(
        self,
        status: ReviewStatus | None = ReviewStatus.APPROVED,
        comment_required: bool = False,
        rating: int | None = None,
        game_id: str | None = None,
        category_id: str | None = None,
        min_item_price: int | None = None,
        max_item_price: int | None = None,
        sort_direction: SortDirection | None = SortDirection.DESC,
        sort_field: str = "createdAt",
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[Review]:
        """
        Получает отзывы вашего аккаунта.

        :param status: Тип отзывов, которые нужно получить.
        :type status: `playerokapi.models.ReviewStatus` or `None`

        :param comment_required: Обязателен ли комментарий в отзыве, _опционально_.
        :type comment_required: `bool`

        :param rating: Рейтинг отзывов (1-5), _опционально_.
        :type rating: `int` or `None`

        :param game_id: ID игры отзывов, _опционально_.
        :type game_id: `str` or `None`

        :param category_id: ID категории отзывов, _опционально_.
        :type category_id: `str` or `None`

        :param min_item_price: Минимальная цена предмета отзыва, _опционально_.
        :type min_item_price: `int` or `None`

        :param max_item_price: Максимальная цена предмета отзыва, _опционально_.
        :type max_item_price: `int` or `None`

        :param sort_direction: Тип сортировки.
        :type sort_direction: `playerokapi.models.SortDirection` or `None`

        :param sort_field: Поле, по которому будет идти сортировка (по умолчанию `createdAt` - по дате).
        :type sort_field: `str`

        :param count: Кол-во отзывов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница отзывов.
        :rtype: `playerokapi.models.Page[playerokapi.models.Review]`
        """

        filters = {
            "userId": await self._me_id(),
            "hasComment": comment_required,
            "status": [value_of(status)] if status else None
        }
        if game_id is not None:
            filters["gameId"] = game_id
        if category_id is not None:
            filters["categoryId"] = category_id
        if rating is not None:
            filters["rating"] = rating
        if min_item_price is not None or max_item_price is not None:
            item_price = {}
            if min_item_price is not None:
                item_price["min"] = min_item_price
            if max_item_price is not None:
                item_price["max"] = max_item_price
            filters["itemPrice"] = item_price

        return await self._query("testimonials", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": filters,
            "sort": {"direction": value_of(sort_direction), "field": sort_field},
            "hasSupportAccess": False
        }, "testimonials", Page[Review])
