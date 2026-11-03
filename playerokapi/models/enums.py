from enum import StrEnum


class ItemLogEvent(StrEnum):
    """События логов предмета."""

    PAID = "PAID"
    """Продавец подтвердил выполнение сделки."""
    SENT = "SENT"
    """Товар сделки отправлен."""
    DEAL_CONFIRMED = "DEAL_CONFIRMED"
    """Сделка подтверждена."""
    DEAL_ROLLED_BACK = "DEAL_ROLLED_BACK"
    """Сделка возвращена."""
    PROBLEM_REPORTED = "PROBLEM_REPORTED"
    """Отправлена жалоба (создана проблема)."""
    PROBLEM_RESOLVED = "PROBLEM_RESOLVED"
    """Проблема решена."""


class TransactionOperation(StrEnum):
    """Операции транзакций."""

    DEPOSIT = "DEPOSIT"
    """Пополнение."""
    BUY = "BUY"
    """Оплата товара."""
    SELL = "SELL"
    """Продажа товара."""
    ITEM_DEFAULT_PRIORITY = "ITEM_DEFAULT_PRIORITY"
    """Оплата бесплатного приоритета."""
    ITEM_PREMIUM_PRIORITY = "ITEM_PREMIUM_PRIORITY"
    """Оплата премиум приоритета."""
    WITHDRAW = "WITHDRAW"
    """Выплата."""
    MANUAL_BALANCE_INCREASE = "MANUAL_BALANCE_INCREASE"
    """Начисление на баланс аккаунта."""
    MANUAL_BALANCE_DECREASE = "MANUAL_BALANCE_DECREASE"
    """Списание с баланса аккаунта."""
    REFERRAL_BONUS = "REFERRAL_BONUS"
    """Приглашение друга (реферал)."""
    STEAM_DEPOSIT = "STEAM_DEPOSIT"
    """Оплата пополнения Steam."""


class TransactionDirection(StrEnum):
    """Направления транзакций."""

    IN = "IN"
    """Начисление."""
    OUT = "OUT"
    """Списание."""


class TransactionStatus(StrEnum):
    """Статусы транзакций."""

    PENDING = "PENDING"
    """В ожидании (транзакция оплачена, но деньги за неё ещё не поступили на баланс)."""
    PROCESSING = "PROCESSING"
    """В заморозке."""
    CONFIRMED = "CONFIRMED"
    """Сделка транзакции подтверждена."""
    ROLLED_BACK = "ROLLED_BACK"
    """Возврат по сделке транзакции."""
    FAILED = "FAILED"
    """Ошибка транзакции."""


class TransactionPaymentMethodId(StrEnum):
    """Айди методов транзакции."""

    MIR = "MIR"
    """С помощью банковских карт МИР."""
    VISA_MASTERCARD = "VISA_MASTERCARD"
    """С помощью банковских карт VISA/Mastercard."""
    ERIP = "ERIP"
    """С помощью ЕРИП."""


class TransactionProviderDirection(StrEnum):
    """Направления провайдеров транзакции."""

    IN = "IN"
    """Пополнение."""
    OUT = "OUT"
    """Вывод."""


class TransactionProviderId(StrEnum):
    """Айди провайдеров транзакции."""

    LOCAL = "LOCAL"
    """С помощью баланса аккаунта."""
    SBP = "SBP"
    """С помощью СБП."""
    BANK_CARD_RU = "BANK_CARD_RU"
    """С помощью банковской карты России."""
    BANK_CARD_BY = "BANK_CARD_BY"
    """С помощью банковской карты Беларуси."""
    BANK_CARD = "BANK_CARD"
    """С помощью иностранной банковской карты."""
    YMONEY = "YMONEY"
    """С помощью ЮMoney."""
    USDT = "USDT"
    """Криптовалюта USDT (TRC20)."""
    PENDING_INCOME = "PENDING_INCOME"
    """Пополнение из замороженных средств."""


class BankCardType(StrEnum):
    """Типы банковских карт."""

    MIR = "MIR"
    """Банковская карта МИР."""
    VISA = "VISA"
    """Банковская карта VISA."""
    MASTERCARD = "MASTERCARD"
    """Банковская карта Mastercard."""


class DealStatus(StrEnum):
    """Состояния сделки."""

    PAID = "PAID"
    """Сделка оплачена."""
    PENDING = "PENDING"
    """Сделка в ожидании отправки товара."""
    SENT = "SENT"
    """Продавец подтвердил выполнение сделки."""
    CONFIRMED = "CONFIRMED"
    """Сделка подтверждена."""
    CONFIRMED_AUTOMATICALLY = "CONFIRMED_AUTOMATICALLY"
    """Сделка подтверждена автоматически."""
    ROLLED_BACK = "ROLLED_BACK"
    """Сделка возвращена."""


class DealDirection(StrEnum):
    """Направления сделки."""

    IN = "IN"
    """Покупка."""
    OUT = "OUT"
    """Продажа."""


class GameType(StrEnum):
    """Типы игр."""

    GAME = "GAME"
    """Игра."""
    APPLICATION = "APPLICATION"
    """Приложение."""
    MOBILE_GAME = "MOBILE_GAME"
    """Мобильная игра."""


class UserType(StrEnum):
    """Типы пользователей."""

    USER = "USER"
    """Обычный пользователь."""
    MODERATOR = "MODERATOR"
    """Модератор."""
    BOT = "BOT"
    """Бот."""
    CHECKER = "CHECKER"
    """Проверяющий."""


class ChatType(StrEnum):
    """Типы чатов."""

    PM = "PM"
    """Приватный чат (диалог с пользователем)."""
    NOTIFICATIONS = "NOTIFICATIONS"
    """Чат уведомлений."""
    SUPPORT = "SUPPORT"
    """Чат поддержки."""


class ChatStatus(StrEnum):
    """Статусы чатов."""

    NEW = "NEW"
    """Новый чат (в нём нет ни единого прочитанного сообщения)."""
    FINISHED = "FINISHED"
    """Чат доступен, в нём сейчас можно переписываться."""


class ChatMessageButtonType(StrEnum):
    """Типы кнопок сообщений."""

    REDIRECT = "REDIRECT"
    """Перенаправляет на ссылку."""
    LOTTERY = "LOTTERY"
    """Перенаправляет на розыгрыш/акцию."""


class ItemStatus(StrEnum):
    """Статусы предметов."""

    PENDING_APPROVAL = "PENDING_APPROVAL"
    """Ожидает принятия (на проверке модерацией)."""
    PENDING_MODERATION = "PENDING_MODERATION"
    """Ожидает проверки изменений модерацией."""
    APPROVED = "APPROVED"
    """Активный (принятый модерацией)."""
    DECLINED = "DECLINED"
    """Отклонённый."""
    BLOCKED = "BLOCKED"
    """Заблокированный."""
    EXPIRED = "EXPIRED"
    """Истёкший."""
    SOLD = "SOLD"
    """Проданный."""
    DRAFT = "DRAFT"
    """Черновик (если предмет не выставлен на продажу)."""
    DISCONTINUED = "DISCONTINUED"
    """Снятый с продажи."""


class ReviewStatus(StrEnum):
    """Статусы отзывов."""

    APPROVED = "APPROVED"
    """Активный."""
    DELETED = "DELETED"
    """Удалённый."""


class SortDirection(StrEnum):
    """Типы сортировки."""

    DESC = "DESC"
    """По убыванию."""
    ASC = "ASC"
    """По возрастанию."""


class PriorityType(StrEnum):
    """Типы приоритетов."""

    DEFAULT = "DEFAULT"
    """Стандартный приоритет."""
    PREMIUM = "PREMIUM"
    """Премиум приоритет."""


class GameCategoryAgreementIconType(StrEnum):
    """Типы иконок соглашения покупателя в определённой категории."""

    RESTRICTION = "RESTRICTION"
    """Ограничение."""
    CONFIRMATION = "CONFIRMATION"
    """Подтверждение."""


class GameCategoryOptionType(StrEnum):
    """Типы опции категории."""

    SELECTOR = "SELECTOR"
    """Выбор типа."""
    SWITCH = "SWITCH"
    """Переключатель."""


class GameCategoryDataFieldType(StrEnum):
    """Типы полей с данными категории игры."""

    ITEM_DATA = "ITEM_DATA"
    """Данные предмета."""
    OBTAINING_DATA = "OBTAINING_DATA"
    """Получаемые данные (после покупки предмета)."""


class GameCategoryDataFieldInputType(StrEnum):
    """Типы вводимых полей с данными категории игры."""

    INPUT = "INPUT"
    """Вводимое значение (вводится покупателем при оформлении предмета)."""
    TEXTAREA = "TEXTAREA"
    """Многострочное вводимое значение."""


class GameCategoryAutoConfirmPeriod(StrEnum):
    """Периоды автоматического подтверждения сделки в категории игры."""

    TWO_DAYS = "TWO_DAYS"
    """Два дня."""
    SEVEN_DAYS = "SEVEN_DAYS"
    """Семь дней."""


class GameCategoryInstructionType(StrEnum):
    """Типы инструкций категории."""

    FOR_SELLER = "FOR_SELLER"
    """Для продавца."""
    FOR_BUYER = "FOR_BUYER"
    """Для покупателя."""


class MessageTemplateType(StrEnum):
    """Типы шаблонных сообщений."""

    ACTIVE_DEAL_PROBLEM = "ACTIVE_DEAL_PROBLEM"
    """Проблема в активной сделке."""
    FINISHED_DEAL_PROBLEM = "FINISHED_DEAL_PROBLEM"
    """Проблема в завершённой сделке."""


class ChatMessageEvent(StrEnum):
    """Ивенты сообщения."""

    CHAT_STARTED = "CHAT_STARTED"
    """Переписка началась (когда к вам в чате поддержки подключается помощник)."""
    CHAT_FINISHED = "CHAT_FINISHED"
    """Переписка завершилась."""
