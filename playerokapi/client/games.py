from __future__ import annotations

from ..models import (
    Game,
    GameCategory,
    GameCategoryAgreement,
    GameCategoryDataField,
    GameCategoryDataFieldType,
    GameCategoryInstruction,
    GameCategoryInstructionType,
    GameCategoryObtainingType,
    GameType,
    Page,
)
from .base import BaseClient, value_of


class GamesMixin(BaseClient):

    async def get_games(
        self,
        name: str | None = None,
        type: GameType | None = None,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[Game]:
        """
        Получает все игры или/и приложения.

        :param name: Название игры (необязательно полное), _опционально_.
        :type name: `str` or `None`

        :param type: Тип игр, которые нужно получать. По умолчанию не указано, значит будут все сразу, _опционально_.
        :type type: `playerokapi.models.GameType` or `None`

        :param count: Кол-во игр, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница игр.
        :rtype: `playerokapi.models.Page[playerokapi.models.Game]`
        """

        return await self._query("games", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"name": name, "type": value_of(type)}
        }, "games", Page[Game])

    async def get_game(self, id: str | None = None, slug: str | None = None) -> Game:
        """
        Получает игру/приложение.\n
        Можно получить по любому из двух параметров:

        :param id: ID игры/приложения, _опционально_.
        :type id: `str` or `None`

        :param slug: Имя страницы игры/приложения, _опционально_.
        :type slug: `str` or `None`

        :return: Объект игры.
        :rtype: `playerokapi.models.Game`
        """

        if not any((id, slug)):
            raise TypeError("Не был передан ни один из обязательных аргументов: id, slug")

        return await self._query("GamePage", {"id": id, "slug": slug}, "game", Game)

    async def get_game_category(
        self,
        id: str | None = None,
        game_id: str | None = None,
        slug: str | None = None
    ) -> GameCategory:
        """
        Получает категорию игры/приложения.\n
        Можно получить по параметру `id` или по связке параметров `game_id` и `slug`.

        :param id: ID категории, _опционально_.
        :type id: `str` or `None`

        :param game_id: ID игры категории (лучше указывать в связке со slug, чтобы находить точную категорию), _опционально_.
        :type game_id: `str` or `None`

        :param slug: Имя страницы категории, _опционально_.
        :type slug: `str` or `None`

        :return: Объект категории игры.
        :rtype: `playerokapi.models.GameCategory`
        """

        if not id and not all((game_id, slug)):
            if game_id or slug:
                raise TypeError("Связка аргументов game_id, slug была передана не полностью")
            raise TypeError("Не был передан ни один из обязательных аргументов: id, game_id, slug")

        return await self._query("GamePageCategory", {"id": id, "gameId": game_id, "slug": slug}, "gameCategory", GameCategory)

    async def get_game_category_agreements(
        self,
        game_category_id: str,
        user_id: str | None = None,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[GameCategoryAgreement]:
        """
        Получает соглашения пользователя на продажу предметов в категории (если пользователь уже принял эти соглашения - список будет пуст).

        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param user_id: ID пользователя, чьи соглашения нужно получить. Если не указан, будет получать по ID вашего аккаунта, _опционально_.
        :type user_id: `str` or `None`

        :param count: Кол-во соглашений, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница соглашений.
        :rtype: `playerokapi.models.Page[playerokapi.models.GameCategoryAgreement]`
        """

        return await self._query("gameCategoryAgreements", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"gameCategoryId": game_category_id, "userId": user_id or await self._me_id()}
        }, "gameCategoryAgreements", Page[GameCategoryAgreement])

    async def get_game_category_obtaining_types(
        self,
        game_category_id: str,
        count: int = 24,
        after_cursor: str | None = None
    ) -> Page[GameCategoryObtainingType]:
        """
        Получает типы (способы) получения предмета в категории.

        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param count: Кол-во способов, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница способов получения.
        :rtype: `playerokapi.models.Page[playerokapi.models.GameCategoryObtainingType]`
        """

        return await self._query("gameCategoryObtainingTypes", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"gameCategoryId": game_category_id}
        }, "gameCategoryObtainingTypes", Page[GameCategoryObtainingType])

    async def get_game_category_instructions(
        self,
        game_category_id: str,
        obtaining_type_id: str,
        count: int = 24,
        type: GameCategoryInstructionType | None = None,
        after_cursor: str | None = None
    ) -> Page[GameCategoryInstruction]:
        """
        Получает инструкции по продаже/покупке в категории.

        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param obtaining_type_id: ID типа (способа) получения предмета.
        :type obtaining_type_id: `str`

        :param count: Кол-во инструкций, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param type: Тип инструкции: для продавца или для покупателя, _опционально_.
        :type type: `playerokapi.models.GameCategoryInstructionType` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница инструкций.
        :rtype: `playerokapi.models.Page[playerokapi.models.GameCategoryInstruction]`
        """

        return await self._query("gameCategoryInstructions", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"gameCategoryId": game_category_id, "obtainingTypeId": obtaining_type_id, "type": value_of(type)}
        }, "gameCategoryInstructions", Page[GameCategoryInstruction])

    async def get_game_category_data_fields(
        self,
        game_category_id: str,
        obtaining_type_id: str,
        count: int = 24,
        type: GameCategoryDataFieldType | None = None,
        after_cursor: str | None = None
    ) -> Page[GameCategoryDataField]:
        """
        Получает поля с данными категории (которые отправляются после покупки).

        :param game_category_id: ID категории игры.
        :type game_category_id: `str`

        :param obtaining_type_id: ID типа (способа) получения предмета.
        :type obtaining_type_id: `str`

        :param count: Кол-во полей, которые нужно получить (не более 24 за один запрос).
        :type count: `int`

        :param type: Тип полей с данными, _опционально_.
        :type type: `playerokapi.models.GameCategoryDataFieldType` or `None`

        :param after_cursor: Курсор, с которого будет идти парсинг (если нету - ищет с самого начала страницы), _опционально_.
        :type after_cursor: `str` or `None`

        :return: Страница полей с данными.
        :rtype: `playerokapi.models.Page[playerokapi.models.GameCategoryDataField]`
        """

        return await self._query("gameCategoryDataFields", {
            "pagination": {"first": count, "after": after_cursor},
            "filter": {"gameCategoryId": game_category_id, "obtainingTypeId": obtaining_type_id, "type": value_of(type)}
        }, "gameCategoryDataFields", Page[GameCategoryDataField])
