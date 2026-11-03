Примеры использования
=====================

.. _quick_start:

Быстрое начало
--------------

Бот, который отвечает на несложные команды. Хендлеры вешаются декораторами на роутер, фильтры пишутся через ``F``.

.. code-block:: python

    import asyncio
    from datetime import datetime

    from playerokapi import Client, Dispatcher, Router, F, NewMessageEvent

    router = Router()


    @router.new_message(F.message.text == "!команды")
    async def on_commands(event: NewMessageEvent):
        await event.answer("🤖 Доступные команды:\n- !привет - отправляет приветствие\n- !дата - показывает текущую дату и время")


    @router.new_message(F.message.text == "!привет")
    async def on_hello(event: NewMessageEvent):
        await event.answer("👋 Привет, я бот для Playerok!\n- Узнать команды - !команды")


    @router.new_message(F.message.text == "!дата")
    async def on_date(event: NewMessageEvent):
        await event.answer(f"📅 Текущая дата: {datetime.now().strftime('%d/%m/%Y, %H:%M:%S')}")


    async def main():
        async with Client(cookies="token=...; __ddg1_=...", user_agent="Mozilla/5.0 ...") as client:
            dp = Dispatcher(client)
            dp.include_router(router)
            await dp.run()


    asyncio.run(main())

Свои сообщения в события не попадают, поэтому проверять ``event.message.user.id != client.id`` не нужно.

Новая сделка
------------

.. code-block:: python

    from playerokapi import Client, NewDealEvent, DealStatus


    @router.new_deal()
    async def on_new_deal(event: NewDealEvent, client: Client):
        deal = event.deal
        print(f"Новая сделка {deal.id}: {deal.item.name} за {deal.item.price} ₽ от {deal.user.username}")
        await event.answer("Спасибо за покупку! Сейчас всё выдам.")
        await client.update_deal(deal.id, DealStatus.SENT)

В хендлер можно получить по имени параметра ``event``, ``client``, ``dispatcher``, ``router`` и всё, что положено в диспетчер:
``dp["config"] = config`` → параметр ``config``.

События без роутеров
--------------------

.. code-block:: python

    async with Client(cookies="...") as client:
        async for event in client.listen():
            if isinstance(event, NewMessageEvent):
                print(event.chat.id, event.message.text)

Сообщения чата
--------------

.. code-block:: python

    chat = await client.get_chat_by_username("LexeyLex")
    page = await client.get_chat_messages(chat.id)

    for message in page.items:
        print(message.created_at, message.text)

Вызов из обычных потоков
------------------------

.. code-block:: python

    from playerokapi import ThreadsafeClient

    sync_client = ThreadsafeClient(client, asyncio.get_running_loop())
    # в другом потоке:
    chats = sync_client.get_chats()
