from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from .base import PlayerokModel, Tolerant
from .common import Moderator
from .enums import ReviewStatus
from .users import UserProfile

if TYPE_CHECKING:
    from .deals import Deal


class Review(PlayerokModel):
    """
    Объект отзыва.
    """

    id: str | None = None
    """ ID отзыва. """
    status: Tolerant[ReviewStatus] = None
    """ Статус отзыва. """
    text: str | None = None
    """ Текст отзыва. """
    rating: int | float | None = None
    """ Рейтинг отзыва. """
    created_at: Tolerant[datetime] = None
    """ Дата создания отзыва. """
    updated_at: Tolerant[datetime] = None
    """ Дата изменения отзыва. """
    deal: Deal | None = None
    """ Сделка, связанная с отзывом. """
    creator: UserProfile | None = None
    """ Профиль создателя отзыва. """
    moderator: Moderator | None = None
    """ Модератор, обработавший отзыв. """
    user: UserProfile | None = None
    """ Профиль продавца, к которому относится отзыв. """
