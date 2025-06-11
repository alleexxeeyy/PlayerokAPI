![alt text](https://github.com/alleexxeeyy/PlayerokAPI/blob/main/docs/_static/logo.png?raw=true)
Неофициальный API для работы с торговой площадкой Playerok на ЯП python, основанный на запросах.

## Навигация
- [Документация](https://playerokapi.readthedocs.io/ru/latest/)
- [Установка](#установка)
- [Примеры использования](#примеры-использования)
- [Ссылки](#ссылки)

## Установка
### С помощью pip
Откройте командную строку и отправьте в неё команду `pip install playerokapi`

### Напрямую с github
1. Скачайте репозиторий https://github.com/alleexxeeyy/PlayerokAPI
2. Убедитесь, что у вас установлен **Python версии 3.x.x - 3.12**. Если не установлен, сделайте это, перейдя по ссылке https://www.python.org/downloads (при установке нажмите на пункт `Add to PATH`)
3. Для установки зависимостей, напишите в командной строке `pip install -r requirements.txt`


## Примеры использования

### Быстрый старт
Пример простого бота, который будет отвечать на несложные команды

```python
from playerokapi.account import Account
from playerokapi.types import *
from playerokapi.enums import *
from playerokapi.listener.listener import EventListener

# --- инициализация аккаунта ---
acc = Account(token="l0eSI6IjFlZTEzODQ2LWVlNGUtNjcxMC1kZDNjLTNiMmVhODIxMT...",
              user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36").get()

# --- инициализация и запуск слушателя событий ---
listener = EventListener(acc)
for event in listener.listen(requests_delay=2): # - указываем периодичность запросов в 2 сек, меньше не рекомендую

    if event.type is EventTypes.NEW_MESSAGE: # ловим тип ивента "Новое сообщение"
        if event.message.user.id != acc.id: # проверяем, если это сообщение было отправлено не от своего же лица
            chat = acc.get_chat_by_username(event.message.user.username) # получаем чат с собеседником

            if event.message.text == "!команды": # проверяем, если текст сообщение - нужная наша команда
                acc.send_message(chat.id, "🤖 Доступные команды: \n┗ !что-то там - показывает что-то\n┗ !где-то там - показывает где-то", True) # отправляем пользователю сообщение
            if event.message.text == "!привет":
                acc.send_message(chat.id, "👋 Привет, я бот для Playerok!\n┗ Узнать команды - !команды", True)
            if event.message.text == "!дата":
                acc.send_message(chat.id, f"📅 Текущяя дата: {datetime.now().strftime("%d/%m/%Y, %H:%M:%S")}", True)
```

### Получение предметов пользователя
Пример простого кода, который получит последние 24 предмета пользователя «LexeyLex» и выведет в консоль их названия

```python
user = acc.get_user(username="LexeyLex")
item_list = user.get_items()
for item in item_list.items:
    print(item.name)
```

### Получение сообщений чата
Пример простого кода, который получит последние 24 сообщения в чате с пользователем «LexeyLex» и выведет в их в консоль

```python
chat = acc.get_chat_by_username("LexeyLex")
chat_message_list = acc.get_chat_messages(chat.id)
for message in chat_message_list.messages:
    print(message.text)
```

### Создание и публикация предмета
Пример кода, который создаст и опубликует предмет в приложении «Telegram», категории «Подарки (NFT)»

```python
from playerokapi.account import Account
from playerokapi.types import *
from playerokapi.enums import *

# --- инициализация аккаунта ---
acc = Account(token="l0eSI6IjFlZTEzODQ2LWVlNGUtNjcxMC1kZDNjLTNiMmVhODIxMT...",
              user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36").get()

# --- создание предмета ---
game = acc.get_game(slug="telegram") # получаем нужную игру
game_category = acc.get_game_category([category for category in game.categories if category.name == "Подарки (NFT)"][0]) # получаем категорию этой игры
obtaining_type_list = acc.get_game_category_obtaining_types(game_category.id) # получаем типы получения предмета в этой категории
gift_obtaining_type = [obtaining_type for obtaining_type in obtaining_type_list.obtaining_types if obtaining_type.name == "Подарок"][0] # берём тип выдачи подарком

gift_type_option = [gift_type for gift_type in game_category.options if gift_type.value == "heart"][0] # берём тип подарка "Сердце"
# тут могут быть прочие опции...

data_field_list = acc.get_game_category_data_fields(game_category.id, gift_obtaining_type.id) # получаем поля с данными категории определённого типа выдачи
commentary_data_field = [data_field for data_field in data_field_list.data_fields if data_field.label == "Комментарий"][0] # берём поле с данным о комментарие (в этом случае только одно, чаще всего несколько необходимых)
commentary_data_field.value = "Напишу вам в ТГ после оформления заказа" # задаём значение этому полю, так как оно обязательное

banner_attachment = ["banner.png"] # описываем пути к файлам-приложениям предмета

item = acc.create_item( # вызываем метод создания предмета
    game_category_id=game_category.id,   # - указываем id категории игры
    obtaining_type_id=gift_obtaining_type.id,   # указываем id типа получения предмета
    name="Подарок \"Сердце\"",   # - указываем название предмета
    price=500,   # - указываем цену предмета
    description="Выдача осуществляется без захода на ваш аккаунт",   # - указываем описание предмета
    options=[gift_type_option],   # - указываем опции предмета (в данном случае одна, но может быть несколько, поэтому указываются в массиве)
    data_fields=[commentary_data_field],   # - указываем поля с данными предмета
    attachments=[banner_attachment]   # - указываем файлы-приложения предмета (баннер и прочие изображения)
)

# --- публикация предмета ---
statuses = acc.get_item_priority_statuses(item.id, item.price) # получаем статусы приоритета предмета
free_status = statuses[1].id # получаем бесплатный статус, чтобы не платить за премиум выставление
new_item = acc.publish_item(item.id, free_status) # выставляем предмет на продажу
```

## Ссылки
Разработчик: https://github.com/alleexxeeyy (в профиле есть актуальные ссылки на все контакты для связи)
Telegram канал: https://t.me/alexeyproduction
