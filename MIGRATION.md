# Переход с PlayerokAPI 1.x на 2.0

2.0 — асинхронная версия: `Client` вместо `Account`, роутеры с декораторами вместо цикла по `EventListener`, модели на pydantic.

## Что будет со старым кодом
- Старые модули остаются в пакете по старым путям на всю 2.x: `playerokapi.account`, `playerokapi.types`, `playerokapi.enums`, `playerokapi.exceptions`, `playerokapi.listener`. Код на 1.x продолжает работать.
- В 3.0 старые модули будут удалены.
- Узнать версию API в коде: `playerokapi.__version__` (в 1.x с версии 1.2 — `"1.2"`, в 2.x — `"2.x.x"`; в более старых 1.x атрибута нет).
- Плагинам Playerok Universal **не нужно** указывать `playerokapi` в своём `requirements.txt`: API идёт вместе с ботом. Как подключать роутеры в плагинах и до какого срока бот поддерживает плагины на 1.x — будет в документации бота, когда выйдет его версия с 2.0.

## Было → стало

### Аккаунт
```python
# 1.x
from playerokapi.account import Account

acc = Account(cookies=cookies, user_agent=ua, proxy=proxy, requests_timeout=15).get()
print(acc.username, acc.profile.balance.available)
chats = acc.get_chats()
for chat in chats.chats:
    ...
```
```python
# 2.0
from playerokapi import Client

async with Client(cookies=cookies, user_agent=ua, proxy=proxy, timeout=15) as client:
    print(client.username, client.me.balance.available)
    page = await client.get_chats()
    for chat in page.items:
        ...
```

### События
```python
# 1.x
from playerokapi.listener.listener import EventListener
from playerokapi.enums import EventTypes

for event in EventListener(acc).listen():
    if event.type is EventTypes.NEW_MESSAGE and event.message.user.id != acc.id:
        if event.message.text == "!help":
            acc.send_message(event.chat.id, "Команды: ...")
```
```python
# 2.0
from playerokapi import Dispatcher, Router, F, NewMessageEvent

router = Router()

@router.new_message(F.message.text == "!help")
async def on_help(event: NewMessageEvent):
    await event.answer("Команды: ...")

dp = Dispatcher(client)
dp.include_router(router)
await dp.run()
```

- Хендлеры одного события вызываются **все**, по очереди, в порядке регистрации. Ошибка в одном не мешает остальным.
- Параметры хендлера заполняются по имени: `event`, `client`, `dispatcher`, `router` и всё из `dp[...]`.
- Свои сообщения в события не попадают (кроме служебных `{{...}}`) — проверка `user.id != acc.id` больше не нужна.
- `DealConfirmedEvent` приходит и на ручное, и на автоматическое подтверждение; отличить можно по `event.automatically`.
- Фото без подписи теперь не теряется: приходит `NewMessageEvent` с `message.text is None` и картинками в `message.images`.
- Без роутеров: `async for event in client.listen(): ...`.

### Синхронный код
Если код работает в обычных потоках и переписать его на async сразу нельзя — `ThreadsafeClient`:
```python
from playerokapi import ThreadsafeClient

sync_client = ThreadsafeClient(client, loop)   # loop — event loop, в котором живёт client
sync_client.send_message(chat_id, "привет")    # из любого потока, кроме потока самого loop
```

### Лимит запросов
Playerok отвечает 429, если слать запросы слишком часто. Поэтому `Client` по умолчанию отправляет запросы строго по одному (как 1.x со своим локом) и на 429/502/503 ставит на паузу все свои запросы.
Если в одном процессе на одном аккаунте работают и `Account` 1.x, и `Client` 2.0 (или несколько клиентов) — дайте им общий `RequestGate`, иначе запросы пойдут параллельно:
```python
from playerokapi import Client, RequestGate

gate = RequestGate()                      # 1 запрос одновременно на всех
client = Client(cookies=cookies, request_gate=gate)

with gate.hold():                         # синхронный код 1.x в своём потоке
    acc.get_deal(deal_id)
```

## Таблицы изменений

### Классы

| 1.x (`playerokapi.types`) | 2.0 (`playerokapi.models`) | Почему |
|---|---|---|
| `ItemDeal` | `Deal` | префикс `Item` лишний, везде говорят «сделка» |
| `ItemDealProps` | `DealProps` | то же |
| `ItemDealWarning` | `DealWarning` | то же |
| `ItemDealConfirmationRestrictionTexts` | `DealConfirmationRestrictionTexts` | то же |
| `ItemDealAutomationObtainingField` | `DealAutomationObtainingField` | то же |
| 15 пар `*List` + `*PageInfo` (`ChatList`, `ItemDealList`, `ReviewList`, …) | `Page[T]` + один `PageInfo` | одинаковые классы ×15 |
| — | `TransactionProviderAccount` | новое: сохранённый счёт провайдера (в 1.x парсился как `AccountProfile` — баг) |
| остальные (`Chat`, `ChatMessage`, `UserProfile`, `AccountProfile`, `Item`, `MyItem`, `ItemProfile`, `Game`, `Transaction`, `Review`, …) | те же имена | — |

Страница: `ChatList.chats` → `Page[Chat].items`, `ItemDealList.deals` → `Page[Deal].items` и т.д. Поля `page_info` и `total_count` остались.

### Enum'ы

Имена в единственном числе (как принято в Python), значения — строки API: `DealStatus.PAID == "PAID"`.

| 1.x (`playerokapi.enums`) | 2.0 |
|---|---|
| `ItemDealStatuses` | `DealStatus` |
| `ItemDealDirections` | `DealDirection` |
| `ItemStatuses` | `ItemStatus` |
| `ItemLogEvents` | `ItemLogEvent` |
| `UserTypes` | `UserType` |
| `ChatTypes` / `ChatStatuses` | `ChatType` / `ChatStatus` |
| `ChatMessageEvents` / `ChatMessageButtonTypes` | `ChatMessageEvent` / `ChatMessageButtonType` |
| `TransactionOperations` / `TransactionDirections` / `TransactionStatuses` | `TransactionOperation` / `TransactionDirection` / `TransactionStatus` |
| `TransactionPaymentMethodIds` / `TransactionProviderIds` / `TransactionProviderDirections` | `TransactionPaymentMethodId` / `TransactionProviderId` / `TransactionProviderDirection` |
| `BankCardTypes` | `BankCardType` |
| `GameTypes` | `GameType` |
| `ReviewStatuses` | `ReviewStatus` |
| `SortDirections` | `SortDirection` |
| `PriorityTypes` | `PriorityType` |
| `MessageTemplateTypes` | `MessageTemplateType` |
| `GameCategoryAgreementIconTypes`, `GameCategoryOptionTypes`, `GameCategoryDataFieldTypes`, `GameCategoryDataFieldInputTypes`, `GameCategoryAutoConfirmPeriods`, `GameCategoryInstructionTypes` | то же без `s` на конце |
| `EventTypes` | переедет в диспетчер (этап 5) |

### Поля

| Где | 1.x | 2.0 |
|---|---|---|
| `Deal` | `completed_user` | `completed_by` (как в API и как у `Transaction`) |
| `GameCategoryAgreement` | `icontype` | `icon_type` |
| все модели | даты строкой `"2026-10-04T09:24:41.409Z"` | `datetime` с таймзоной UTC |
| `ChatMessage.game` | `Game` | `GameProfile` (API присылает именно профиль) |
| `ChatMessage.item` | всегда `Item` | `MyItem` / `Item` / `ItemProfile` по `__typename`, как у `Deal.item` |
| `TransactionProvider.account`, `TransactionPaymentMethod.account` | `AccountProfile` | `TransactionProviderAccount` |
| `UserProfile.username` | `"Поддержка"`, если ключа нет в ответе | `None` |

Новые поля (API их присылает, 1.x терял): `ChatMessage.file`, `ChatMessage.image_links`,
`AccountProfile.has_confirmed_phone_number / can_publish_items / is_funds_protection_active / last_item_created_at`,
`AccountOutgoingDealsStats.automated_total`, `Transaction.auto_claimed_at`, `Game.is_new`,
`ItemProfile.game / category / keep_in_sale / status_expiration_date`, `TransactionProviderAccount.*`.

### Баги 1.x, которые в 2.0 исправлены

- `TransactionPaymentMethod.provider_id` всегда `None`: парсер читал `provider_id` вместо `providerId`.
- `GameCategoryAgreementIconTypes.CONFIRMATION = 0` — синоним `RESTRICTION`, подтверждение не отличить от ограничения.
- `GameType.MOBILE_GAME` и `GameCategoryDataFieldInputType.TEXTAREA` приходят от API, в 1.x становились `None`.
- `account` у провайдера/метода парсился как профиль аккаунта (оставался только `id`).

### Поведение моделей

- Все поля опциональные; лишние ключи игнорируются.
- `null` в ответе → `None` у скаляров и объектов, `[]` у списков. `text=None` у фото без подписи остаётся `None`.
- Неизвестное значение enum или битая дата → `None` + одно предупреждение в лог `playerokapi` на каждое новое значение.
- Числа как в API: `81` → `int`, `81.5` → `float` (как и в 1.x).
- Модели изменяемые (`msg.text = ...` работает) — хендлеры бота так делают.

### Клиент: `Account` → `Client`

| 1.x | 2.0 |
|---|---|
| `Account(token=..., ddg5=..., cookies=..., user_agent=..., proxy=..., requests_timeout=15).get()` | `async with Client(token=..., cookies=..., user_agent=..., proxy=..., timeout=15) as client:` или `await client.refresh()` |
| `ddg5` | убран: все куки DDoS-Guard передаются в `cookies` (сейчас это `__ddg1_`, `__ddg8_`, `__ddg9_`, `__ddg10_`, а не `__ddg5_`) |
| синглтон `Account()` / `get_account()` | нет, каждый `Client(...)` — отдельный клиент |
| `account.profile` | `client.me` (`AccountProfile`, склейка `viewer` + `user`) |
| `account.id`, `account.username` | `client.id`, `client.username`; остальные поля — `client.me.*` |
| все методы синхронные | все методы `async`, имена и параметры те же |
| вызов из потоков | `ThreadsafeClient(client, loop)` — те же методы, но синхронно, из любого потока, кроме потока loop |
| `send_message(..., images=[])` | `images=None`, принимает пути, `Path` и байты |
| `get_chat_by_username(username)` — листает все чаты до конца | так же (можно ограничить `max_pages`), `None`, если не нашёл; не падает на собеседнике без ника |
| `get_items/get_my_items(statuses=[APPROVED])` | `statuses=(ItemStatus.APPROVED,)`, `None` — любые статусы (как и было при явном `None`) |
| `update_item` пропускал «ложные» значения (`price=0`, `description=""`, `options=[]`) | отправляет всё, что не `None`; `options` принимает и словарь |
| `update_item(add_attachments=...)` — файлы уходили в `variables.attachments.N`, а переменная называется `addedAttachments` | исправлено |
| `report_deal_problem` разбирал сделку как транзакцию | возвращает `Deal` |
| `get_user` падал, если пользователь не найден | возвращает `None` |
| `get_transactions(from_date=...)` — дата без учёта таймзоны | дата с таймзоной переводится в UTC, без таймзоны считается UTC (как раньше) |
| `get_transactions(min_value=0)` — ноль отбрасывался | отправляется |
| `token` вместе с `cookies` — `token` игнорировался | добавляется в куки, если его там нет; без токена вообще — `TypeError` сразу |
| енумы 1.x (`ItemDealStatuses.PAID`) | новый клиент их тоже принимает (отправляет имя), но лучше `DealStatus.PAID` |
| `send_message` молча пропускал картинку, если загрузка не вернула ID | `PlayerokError`, сообщение не уходит |
| в ответе нет нужного поля → `KeyError` | `PlayerokError` с именем операции |
| `download_file` → `RequestSendingError` | `HTTPError` / `NetworkError` |
| мутации (`send_message`, `increase_item_priority_status`, `request_withdrawal`, ...) повторялись после таймаута | повторяются, только если запрос точно не ушёл |
| исключения `RequestPlayerokError`, `RequestFailedError`, `BotCheckDetectedException`, `UnauthorizedError`, ... | `GraphQLError`, `HTTPError`, `BotCheckError`, `UnauthorizedError`, `NetworkError` (все от `PlayerokError`) |
