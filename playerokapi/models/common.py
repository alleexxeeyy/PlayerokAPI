from __future__ import annotations

from .base import PlayerokModel


class FileObject(PlayerokModel):
    """
    Объект файла.
    """

    id: str | None = None
    """ ID файла. """
    url: str | None = None
    """ URL файла. """
    filename: str | None = None
    """ Имя файла. """
    mime: str | None = None
    """ Mime файла. """


class Moderator(PlayerokModel):
    """
    Объект модератора.
    """

    id: str | None = None
    """ ID модератора. """
    username: str | None = None
    """ Имя пользователя модератора. """
