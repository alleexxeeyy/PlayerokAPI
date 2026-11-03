from __future__ import annotations

from logging import getLogger
from typing import Annotated, Any, Generic, Optional, TypeVar

from pydantic import (
    BaseModel,
    ConfigDict,
    ValidationError,
    ValidationInfo,
    ValidatorFunctionWrapHandler,
    WrapValidator,
    field_validator,
    model_validator,
)
from pydantic.alias_generators import to_camel


logger = getLogger("playerokapi")

T = TypeVar("T")

_reported: set[tuple] = set()
_MAX_REPORTED = 1000


def _describe(error: ValidationError) -> str:
    first = error.errors(include_url=False)[0]
    loc = ".".join(str(part) for part in first.get("loc", ())) or "-"
    return f"{first.get('type')} в {loc}"


def _or_none(value: Any, handler: ValidatorFunctionWrapHandler, info: ValidationInfo) -> Any:
    try:
        return handler(value)
    except ValidationError as e:
        if isinstance(value, str) and len(value) <= 64:
            key = (info.field_name, value)
            shown = repr(value)
        else:
            key = (info.field_name, type(value).__name__, _describe(e))
            shown = f"{type(value).__name__} ({_describe(e)})"
        if key not in _reported and len(_reported) < _MAX_REPORTED:
            _reported.add(key)
            logger.warning(f"Не удалось разобрать поле {info.field_name}: {shown}, будет None")
        return None


Tolerant = Annotated[Optional[T], WrapValidator(_or_none)]


class PlayerokModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        coerce_numbers_to_str=True,
        use_attribute_docstrings=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _drop_nulls(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {
                k: [i for i in v if i is not None] if isinstance(v, list) else v
                for k, v in data.items() if v is not None
            }
        return data


class PageInfo(PlayerokModel):
    """
    Информация о странице.
    """

    start_cursor: str | None = None
    """ Курсор начала страницы. """
    end_cursor: str | None = None
    """ Курсор конца страницы. """
    has_previous_page: bool | None = None
    """ Имеет ли предыдущую страницу. """
    has_next_page: bool | None = None
    """ Имеет ли следующую страницу. """


class Page(PlayerokModel, Generic[T]):
    """
    Страница объектов. Объект, который не удалось разобрать, пропускается с предупреждением в лог.
    """

    items: list[Annotated[T, WrapValidator(_or_none)]] = []
    """ Объекты страницы. """
    page_info: PageInfo | None = None
    """ Информация о странице. """
    total_count: int | None = None
    """ Всего объектов. """

    @model_validator(mode="before")
    @classmethod
    def _from_edges(cls, data: Any) -> Any:
        if isinstance(data, dict) and "edges" in data:
            edges = data.get("edges") or []
            data = {**data, "items": [e["node"] for e in edges if isinstance(e, dict) and e.get("node") is not None]}
        return data

    @field_validator("items", mode="after")
    @classmethod
    def _skip_broken(cls, items: list) -> list:
        return [item for item in items if item is not None]
