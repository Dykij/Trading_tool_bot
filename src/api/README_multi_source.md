# Многоисточниковый провайдер рыночных данных

Этот модуль предоставляет унифицированный интерфейс для работы с данными из нескольких торговых площадок (DMarket, Steam и др.) и содержит инструменты для автоматического анализа арбитражных возможностей.

## Основные возможности

- Получение данных о предметах из нескольких источников одновременно
- Агрегация данных и вычисление статистических показателей
- Поиск арбитражных возможностей
- Централизованное кэширование для оптимизации запросов
- Объединение результатов поиска из разных источников

## Архитектура

Модуль состоит из нескольких ключевых компонентов:

1. **MarketDataProvider** - абстрактный базовый класс для провайдеров данных
2. **DMarketDataProvider** - реализация провайдера для DMarket
3. **SteamDataProvider** - реализация провайдера для Steam
4. **MarketDataAggregator** - класс для агрегации данных из разных источников
5. **MultiSourceMarketProvider** - расширенный провайдер с дополнительной функциональностью

## Примеры использования

### Поиск предметов на нескольких площадках

```python
import asyncio
from src.api.multi_source_market_provider import get_multi_source_provider

async def search_items():
    provider = get_multi_source_provider()
    
    # Ищем АК-47 | Redline на всех доступных площадках
    results = await provider.search_across_sources(
        game_code="a8db",  # CS2
        query="AK-47 Redline",
        merge_results=True  # Объединяем результаты из разных источников
    )
    
    # Выводим результаты
    print(f"Найдено {results['total_items']} предметов")
    for item in results['items']:
        print(f"{item['title']} - {item.get('price', {}).get('USD', 'N/A')}$ ({item['source']})")

# Запускаем поиск
asyncio.run(search_items())
```

### Поиск арбитражных возможностей

```python
import asyncio
from src.api.multi_source_market_provider import find_arbitrage_opportunities

async def find_arbitrage():
    # Ищем возможности с разницей в цене не менее 10%
    opportunities = await find_arbitrage_opportunities(
        game_code="a8db",
        min_price_diff=10.0,
        limit=5
    )
    
    # Выводим найденные возможности
    for opp in opportunities:
        print(f"{opp['item_name']}")
        print(f"  Покупка: {opp['buy_price']}$ ({opp['buy_from']})")
        print(f"  Продажа: {opp['sell_price']}$ ({opp['sell_to']})")
        print(f"  Разница: {opp['price_diff_percent']:.2f}% ({opp['price_diff']:.2f}$)")
        print(f"  Потенциал: {opp['profit_potential']}")
        print()

# Запускаем поиск арбитражных возможностей
asyncio.run(find_arbitrage())
```

### Получение детальной информации о предмете

```python
import asyncio
from src.api.multi_source_market_provider import get_multi_source_provider

async def get_item_details():
    provider = get_multi_source_provider()
    
    # Получаем детальную информацию о предмете из всех источников
    details = await provider.get_item_details(
        game_code="a8db",
        item_name="AK-47 | Redline",
        sources=["dmarket", "steam"]  # Указываем конкретные источники
    )
    
    # Выводим статистику по предмету
    stats = details['stats']
    print(f"Статистика по предмету {details['item_name']}:")
    print(f"  Средняя цена: {stats['mean_price']:.2f}$")
    print(f"  Медианная цена: {stats['median_price']:.2f}$")
    print(f"  Минимальная цена: {stats['min_price']:.2f}$ ({stats['best_source']})")
    print(f"  Волатильность: {stats['price_volatility']:.2f}")
    print(f"  Тренд цены: {stats['price_trend']}")
    print(f"  Достоверность данных: {stats['confidence_score']:.2f}")

# Запускаем получение информации
asyncio.run(get_item_details())
```

## Расширение функциональности

Для добавления нового источника данных:

1. Создайте новый класс, наследующийся от `MarketDataProvider`
2. Реализуйте все абстрактные методы
3. Зарегистрируйте провайдер в агрегаторе данных:

```python
from src.api.multi_source_provider import get_market_aggregator
from your_module import YourNewDataProvider

# Получаем агрегатор
aggregator = get_market_aggregator()

# Регистрируем новый провайдер
aggregator.register_provider("new_source", YourNewDataProvider()) 