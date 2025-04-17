# Документация по API

В этом каталоге содержатся ссылки и документация по API различных торговых площадок, интегрированных в нашего торгового бота.

## Интегрированные торговые площадки

### DMarket

DMarket - торговая площадка для обмена игровыми скинами и предметами.

**Документация API:** [https://docs.dmarket.com/v1/swagger.html](https://docs.dmarket.com/v1/swagger.html)

Основные возможности API:
- Авторизация
- Получение списка предметов
- Создание ордеров на покупку/продажу
- Создание и управление целевыми ордерами
- Получение рыночных данных и истории транзакций

### Bitskins

Bitskins - популярная торговая площадка для покупки и продажи игровых предметов.

**Документация API:** [https://bitskins.com/ru/docs/api](https://bitskins.com/ru/docs/api)

Основные возможности API:
- Авторизация через API-ключ
- Получение списка предметов
- Получение истории цен
- Выставление предметов на продажу
- Покупка предметов
- Вывод средств

### Backpack.tf

Backpack.tf - площадка для торговли предметами Team Fortress 2 и других игр Valve.

**Документация API:** [https://backpack.tf/api/index.html](https://backpack.tf/api/index.html)

Основные возможности API:
- Получение цен на предметы
- Информация о пользователях
- Создание и управление объявлениями
- Получение истории цен

### Total CS

Total CS - ресурс с информацией о CS2 (бывший CS:GO), включая данные о скинах и их ценах.

**Документация и информация:** [https://totalcsgo.com/launch-options](https://totalcsgo.com/launch-options)

Основные возможности:
- Получение информации о скинах и их ценах
- Анализ рыночных тенденций
- Поиск лучших предложений

## Telegram Bot API

Для взаимодействия с пользователем используется Telegram Bot API.

**Документация API:** [https://core.telegram.org/bots/api](https://core.telegram.org/bots/api)

Основные возможности API, используемые в боте:
- Отправка сообщений
- Создание и обработка инлайн-клавиатур
- Обработка команд
- Отправка файлов и изображений
- Работа с callback-запросами

## Использование в проекте

Интеграция с API реализована в следующих модулях:

1. `utils/api_adapter.py` - адаптер для работы с DMarket API
2. `utils/marketplace_integrator.py` - интегратор различных торговых площадок
3. `telegram_bot.py` - модуль Telegram бота для взаимодействия с пользователем
4. `keyboards.py` - модуль с клавиатурами для Telegram бота

## Примеры API-запросов

### DMarket

```python
# Получение целевых ордеров
async def get_target_orders(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    endpoint = "/target-orders"
    params = {
        "limit": limit,
        "offset": offset
    }
    response = await self._make_authenticated_request("GET", endpoint, params=params)
    return response.get("items", [])
```

### Bitskins

```python
# Получение информации о предмете по имени
async def get_item_by_name(self, name: str) -> Dict[str, Any]:
    endpoint = "/market/items"
    params = {
        "market_hash_name": name
    }
    response = await self._make_authenticated_request("GET", endpoint, params=params)
    return response.get("data", {})
```

### Backpack.tf

```python
# Получение цены предмета
async def get_item_price(self, item_name: str) -> Dict[str, Any]:
    endpoint = "/api/prices/items"
    params = {
        "item": item_name,
        "quality": "Unique",
        "tradable": 1,
        "craftable": 1
    }
    response = await self._make_authenticated_request("GET", endpoint, params=params)
    return response.get("response", {}).get("items", {}).get(item_name, {})
```

## Арбитражные стратегии

В проекте реализованы алгоритмы для поиска и использования арбитражных возможностей между различными площадками:

1. Алгоритм Беллмана-Форда для поиска отрицательных циклов в графе обмена
2. Линейное программирование для оптимизации распределения бюджета
3. Мониторинг рынка в реальном времени
4. Создание целевых ордеров на основе арбитражных возможностей

## Дополнительные ресурсы

Для получения дополнительной информации рекомендуется обратиться к официальной документации соответствующих API:

- [DMarket API Documentation](https://docs.dmarket.com/v1/swagger.html)
- [Bitskins API Documentation](https://bitskins.com/ru/docs/api)
- [Backpack.tf API Documentation](https://backpack.tf/api/index.html)
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api) 