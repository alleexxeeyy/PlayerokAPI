from importlib import import_module
from typing import TYPE_CHECKING


__version__ = "2.0.0.dev0"

_EXPORTS = {
    ".client": ("Client",),
    ".threadsafe": ("ThreadsafeClient",),
    ".errors": ("PlayerokError", "NetworkError", "BotCheckError", "HTTPError", "GraphQLError", "UnauthorizedError"),
    ".dispatcher": (
        "Dispatcher", "Router", "F", "EventType", "EventSource", "BaseEvent",
        "ChatInitializedEvent", "NewMessageEvent", "NewDealEvent", "NewReviewEvent", "ItemPaidEvent", "ItemSentEvent",
        "DealConfirmedEvent", "DealRolledBackEvent", "DealHasProblemEvent", "DealProblemResolvedEvent", "DealStatusChangedEvent",
    ),
}

if TYPE_CHECKING:
    from magic_filter import F

    from .client import Client
    from .dispatcher import *
    from .errors import BotCheckError, GraphQLError, HTTPError, NetworkError, PlayerokError, UnauthorizedError
    from .models import *
    from .threadsafe import ThreadsafeClient


def __getattr__(name: str):
    # подмодули (account, types, listener, ...) в нижнем регистре — их ищет сам import, модели не трогаем
    if not name[:1].isupper():
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = None
    for module, names in _EXPORTS.items():
        if name in names:
            value = getattr(import_module(module, __name__), name)
            break
    else:
        models = import_module(".models", __name__)
        if name not in models.__all__:
            raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
        value = getattr(models, name)
    globals()[name] = value
    return value


def __dir__():
    names = [n for names in _EXPORTS.values() for n in names]
    return sorted({*globals(), *names, *import_module(".models", __name__).__all__})
