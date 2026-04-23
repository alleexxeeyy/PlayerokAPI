Примеры использования
=====================

Здесь собраны примеры кода для демонстрации работы библиотеки.

.. _quick_start:

Быстрое начало
--------------

Пример простого бота, который будет отвечать на несложные команды

.. code-block:: python

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

.. _create_and_publish_item:

Создание и публикация предмета
------------------------------

Пример кода, который создаст и опубликует предмет в приложении "Telegram", категории "Подарки (NFT)"

.. code-block:: python

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