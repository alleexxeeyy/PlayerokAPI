from __future__ import annotations


class PlayerokError(Exception):
    pass


class NetworkError(PlayerokError):
    def __init__(self, url: str, error: str):
        self.url = url
        self.error = error
        super().__init__(f"Не удалось отправить запрос к {url}: {error}")


class BotCheckError(PlayerokError):
    def __init__(self, url: str):
        self.url = url
        super().__init__(
            "Бот-проверка Playerok заметила подозрительную активность. "
            "Обновите cookies (token и __ddg5_) и убедитесь, что запросы идут с того же IP и User-Agent, "
            "под которыми вы авторизовывались на сайте"
        )


class HTTPError(PlayerokError):
    def __init__(self, url: str, status_code: int, text: str):
        self.url = url
        self.status_code = status_code
        self.text = text
        super().__init__(f"Ошибка запроса к {url}, код ответа {status_code}: {text[:500]}")


class GraphQLError(PlayerokError):
    def __init__(self, operation: str, errors: list[dict]):
        self.operation = operation
        self.errors = errors

        first = errors[0] if errors and isinstance(errors[0], dict) else {}
        extensions = first.get("extensions") if isinstance(first.get("extensions"), dict) else {}
        self.message: str = first.get("message") or ""
        self.code: str | None = extensions.get("code")
        self.status_code: int | None = extensions.get("statusCode")
        super().__init__(self.message or f"Ошибка Playerok в запросе {operation}: {self.code}")


class UnauthorizedError(PlayerokError):
    def __init__(self):
        super().__init__("Не удалось подключиться к аккаунту Playerok. Проверьте token или cookies")
