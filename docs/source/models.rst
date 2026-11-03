Модели
======

Все модели — pydantic v2. Поля опциональные: если Playerok не прислал поле, в нём `None` (у списков — `[]`).
Списки возвращаются страницей :class:`playerokapi.models.Page`: объекты в ``page.items``.

.. automodule:: playerokapi.models.base
   :members: Page, PageInfo

.. automodule:: playerokapi.models.users
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.chats
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.deals
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.items
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.games
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.finance
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.reviews
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

.. automodule:: playerokapi.models.common
   :members:
   :exclude-members: model_config, model_fields, model_computed_fields

Enums
-----

.. automodule:: playerokapi.models.enums
   :members:
   :undoc-members:
