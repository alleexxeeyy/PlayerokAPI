![alt text](https://github.com/alleexxeeyy/PlayerokAPI/blob/main/docs/source/_static/logo.png?raw=true)

[![telegram](https://img.shields.io/badge/telegram-%D0%BA%D0%B0%D0%BD%D0%B0%D0%BB-blue?style=for-the-badge&logo=telegram)](https://t.me/alexeyproduction)
[![bot](https://img.shields.io/badge/%F0%9F%A4%96%20playerok-%D0%B1%D0%BE%D1%82-blue?style=for-the-badge)](https://github.com/alleexxeeyy/playerok-universal)
[![python](https://img.shields.io/badge/python-3.11+-yellow?style=for-the-badge&logo=python&link=https%3A%2F%2Fimg.shields.io%2Fbadge%2Ftelegram-%25D0%25BA%25D0%25B0%25D0%25BD%25D0%25B0%25D0%25BB-blue%3Fstyle%3Dfor-the-badge%26logo%3Dtelegram)](https://www.python.org/downloads/release/python-3119/)
[![stars](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Falleexxeeyy%2FPlayerokAPI&query=%24.stargazers_count&style=for-the-badge&label=stars&color=43d433&logo=github)](https://github.com/alleexxeeyy/PlayerokAPI/stargazers)
[![forks](https://img.shields.io/badge/dynamic/json?url=https%3A%2F%2Fapi.github.com%2Frepos%2Falleexxeeyy%2FPlayerokAPI&query=%24.forks_count&style=for-the-badge&label=forks&color=%236c70e6&logo=github)](https://github.com/alleexxeeyy/PlayerokAPI/forks)

Неофициальный API для работы с торговой площадкой Playerok на ЯП python, основанный на запросах.

## Навигация
- [Документация](https://playerokapi.readthedocs.io/ru/latest/)
- [Установка](#установка)
- [Примеры использования](#примеры-использования)
- [Полезные ссылки](#полезные-ссылки)

## Установка
### С помощью pip
Откройте командную строку и отправьте в неё команду `pip install git+https://github.com/alleexxeeyy/PlayerokAPI.git` 

### Напрямую с github
1. Скачайте репозиторий https://github.com/alleexxeeyy/PlayerokAPI
2. Убедитесь, что у вас установлен **Python версии 3.11+**. Если не установлен, сделайте это, перейдя по ссылке https://www.python.org/downloads (при установке нажмите на пункт `Add to PATH`)
3. Для установки зависимостей, напишите в командной строке `pip install -r requirements.txt`

## Примеры использования

### Быстрый старт
Пример простого бота, который будет отвечать на несложные команды

```python
from datetime import datetime

from playerokapi.account import Account
from playerokapi.types import *
from playerokapi.enums import *
from playerokapi.listener.listener import EventListener

# ----- ИНИЦИАЛИЗАЦИЯ АККАУНТА -----
acc = Account(
    cookies="__ddg3=4L7yBmrBwMwKm15X;token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
).get()

# ----- ЗАПУСК СЛУШАТЕЛЯ СОБЫТИЙ -----
listener = EventListener(acc)

for event in listener.listen():
    if event.type is EventTypes.NEW_MESSAGE: # ловим тип ивента "Новое сообщение"
        if event.message.user.id != acc.id: # проверяем, если это сообщение было отправлено не от своего же лица
            if event.message.text == "!команды": # проверяем, если текст сообщение - нужная наша команда
                acc.send_message(
                    chat_id=event.chat.id, 
                    text="🤖 Доступные команды:\n- !привет - отправляет приветствие\n- !дата - показывает текущую дату и время"
                ) # отправляем сообщение
            if event.message.text == "!привет":
                acc.send_message(
                    chat_id=event.chat.id, 
                    text="👋 Привет, я бот для Playerok!\n- Узнать команды - !команды"
                )
            if event.message.text == "!дата":
                acc.send_message(
                    chat_id=event.chat.id, 
                    text=f"📅 Текущая дата: {datetime.now().strftime("%d/%m/%Y, %H:%M:%S")}"
                )
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


# ----- ИНИЦИАЛИЗАЦИЯ АККАУНТА -----
acc = Account(
    cookies="__ddg3=4L7yBmrBwMwKm15X;token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
).get()

# ----- ПОЛУЧЕНИЕ ДАННЫХ О ТОВАРЕ -----
game = acc.get_game(slug="telegram") # получаем нужную игру

_category = next((cat for cat in game.categories if cat.name == "Подарки (NFT)"), None) 
category = acc.get_game_category(_category.id) # получаем полные даные о категории

obt_list = acc.get_game_category_obtaining_types(category.id)
obt_type = next((obt for obt in obt_list.obtaining_types if obt.name == "Подарок"), None)

option = next((opt for opt in category.options if opt.value == "heart"), None)
# тут могут быть прочие опции...

df_list = acc.get_game_category_data_fields(category.id, obt_type.id)
data_field = next((df for df in df_list.data_fields if df.label == "Комментарий"), None) # берём поле с обязательным данным (в этом случае только одно, чаще всего несколько необходимых)
data_field.value = "Напишу вам в ТГ после оформления заказа" # задаём значение этому полю, так как оно обязательное
# тут могут быть прочие обязательные поля с данными...

banner = "banner.png"

# ----- СОЗДАНИЕ ПРЕДМЕТА -----
item = acc.create_item(
    game_category_id=category.id,                                    # указываем id категории игры
    obtaining_type_id=obt_type.id,                                   # указываем id типа получения предмета
    name='Подарок "❤️ Сердце" (13 ⭐) / Авто-Выдача 🤖',            # указываем название предмета
    price=90,                                                        # указываем цену предмета
    description="Выдача осуществляется без захода на ваш аккаунт.",  # указываем описание предмета
    options=[option],                                                # указываем опции предмета
    data_fields=[data_field],                                        # указываем поля с данными предмета
    attachments=[banner]                                             # указываем файлы-приложения предмета (баннер и прочие изображения)
)

# ----- ПУБЛИКАЦИЯ ПРЕДМЕТА -----
statuses = acc.get_item_priority_statuses(item.id, item.price)
free_status = next((status for status in statuses if status.price == 0), None)
new_item = acc.publish_item(item.id, free_status.id)
```

## Полезные ссылки
- Разработчик: https://github.com/alleexxeeyy (в профиле есть актуальные ссылки на все контакты для связи)
- Telegram канал: https://t.me/alexeyproduction
- Telegram бот для покупки официальных модулей: https://t.me/alexey_production_bot
