События, роутеры и диспетчер
============================

Роутер
------

.. autoclass:: playerokapi.Router
   :members:

Диспетчер
---------

.. autoclass:: playerokapi.Dispatcher
   :members: run, stop, feed_event, include_router, include_routers, remove_router, running, shutdown_timeout

События
-------

.. automodule:: playerokapi.dispatcher.events
   :members:
   :exclude-members: Event

Источник событий
----------------

.. autoclass:: playerokapi.dispatcher.EventSource
   :members: listen, start, close
