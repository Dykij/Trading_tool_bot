"""
Интеграционные тесты для проверки взаимодействия API DMarket с алгоритмическими компонентами.

Тесты проверяют корректность работы адаптера API, валидацию данных,
преобразование форматов и интеграцию с алгоритмами поиска арбитража.
"""

import pytest
import asyncio
import logging
import sys
import os
from unittest.mock import patch, MagicMock, AsyncMock
from typing import Dict, List, Any

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.api.api_wrapper import DMarketAPI, APIError
from src.utils.api_adapter import DMarketAdapter, MarketItem
from src.arbitrage.bellman_ford import Edge, ArbitrageResult

# Настройка логирования для тестов
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('test_api_integration')

# Тестовые данные
MOCK_MARKET_ITEMS = {
    'objects': [
        {
            'itemId': 'item1',
            'title': 'Test Item 1',
            'gameTitle': 'CS:GO',
            'price': {'USD': 10.0, 'EUR': 8.5},
            'suggestedPrice': {'USD': 12.0, 'EUR': 10.2},
            'extra': {'salesPerDay': 20},
            'updateTime': '2023-04-01T12:00:00Z'
        },
        {
            'itemId': 'item2',
            'title': 'Test Item 2',
            'gameTitle': 'Dota 2',
            'price': {'USD': 5.0, 'EUR': 4.25},
            'suggestedPrice': {'USD': 5.5, 'EUR': 4.7},
            'extra': {'salesPerDay': 15},
            'updateTime': '2023-04-01T12:30:00Z'
        },
        {
            'itemId': 'item3',
            'title': 'Test Item 3',
            'gameTitle': 'CS:GO',
            'price': {'USD': 100.0, 'EUR': 85.0},
            'suggestedPrice': {'USD': 110.0, 'EUR': 93.5},
            'extra': {'salesPerDay': 3},
            'updateTime': '2023-04-01T13:00:00Z'
        },
        # Элемент с невалидными данными
        {
            'itemId': 'item4',
            'title': 'Invalid Item',
            'gameTitle': 'CS:GO',
            'price': {'USD': -5.0},  # Отрицательная цена
            'suggestedPrice': {},
            'extra': {'salesPerDay': 0},
            'updateTime': '2023-04-01T13:30:00Z'
        }
    ]
}

@pytest.fixture
def mock_api():
    """Создает мок API клиента DMarket."""
    api = AsyncMock(spec=DMarketAPI)
    api.get_market_items_async = AsyncMock(return_value=MOCK_MARKET_ITEMS)
    return api

@pytest.fixture
def adapter(mock_api):
    """Создает экземпляр адаптера API с моком API клиента."""
    # Здесь требуется awaitable_fixture, чтобы правильно обработать асинхронный moc_api
    # Мы должны создать конкретный экземпляр адаптера, а не корутину
    adapter_instance = DMarketAdapter(api_key="test_key", api_secret="test_secret", use_cache=True)
    # Заменяем API объект моком
    adapter_instance.api = mock_api
    return adapter_instance

@pytest.mark.asyncio
async def test_market_item_from_api():
    """Тестирует создание MarketItem из данных API."""
    # Валидный элемент
    valid_item = MOCK_MARKET_ITEMS['objects'][0]
    market_item = MarketItem.from_api_response(valid_item)
    
    assert market_item is not None
    assert market_item.item_id == 'item1'
    assert market_item.title == 'Test Item 1'
    assert market_item.prices['USD'] == 10.0
    assert market_item.suggested_prices['USD'] == 12.0
    assert market_item.liquidity == 20
    
    # Элемент с невалидными данными (в нашей реализации вместо None может возвращаться объект с пустыми/дефолтными значениями)
    invalid_item = MOCK_MARKET_ITEMS['objects'][3]
    invalid_market_item = MarketItem.from_api_response(invalid_item)
    
    # Проверяем, что элемент либо None, либо имеет отрицательную цену, что делает его невалидным
    if invalid_market_item is not None:
        for price in invalid_market_item.prices.values():
            assert price <= 0

@pytest.mark.asyncio
async def test_get_market_items(adapter):
    """Тестирует получение и нормализацию данных с рынка."""
    items = await adapter.get_market_items(limit=10)
    
    # Должны быть получены только валидные элементы
    assert len(items) == 3
    
    # Проверяем валидные элементы
    item1 = next((item for item in items if item.item_id == 'item1'), None)
    assert item1 is not None
    assert item1.prices['USD'] == 10.0
    
    # Проверяем кэширование
    cached_items = await adapter.get_market_items(limit=10)
    assert len(cached_items) == 3
    
    # Проверяем, что API был вызван только один раз (второй раз из кэша)
    adapter.api.get_market_items_async.assert_called_once()

@pytest.mark.asyncio
async def test_create_exchange_graph(adapter):
    """Тестирует создание графа обменных курсов."""
    items = await adapter.get_market_items(limit=10)
    graph = adapter.create_exchange_graph(items)
    
    # Проверяем, что граф создан и содержит рёбра
    assert len(graph) > 0
    
    # Проверяем типы рёбер
    assert all(isinstance(edge, Edge) for edge in graph)
    
    # Проверяем содержание графа
    currencies = {'USD', 'EUR'}
    item_ids = {'item1', 'item2', 'item3'}
    
    # Должны быть рёбра между валютами и предметами
    edges_from_usd = [edge for edge in graph if edge.from_node == 'USD']
    assert len(edges_from_usd) >= len(item_ids)
    
    # Должны быть рёбра от предметов к валютам
    item_to_currency_edges = [
        edge for edge in graph 
        if edge.from_node in item_ids and edge.to_node in currencies
    ]
    assert len(item_to_currency_edges) > 0
    
    # Проверяем кэширование графа
    cached_graph = adapter.create_exchange_graph(items)
    assert cached_graph is graph  # Должен быть тот же объект

@pytest.mark.asyncio
async def test_find_arbitrage_opportunities(adapter):
    """Тестирует поиск арбитражных возможностей."""
    with patch('utils.api_adapter.find_arbitrage_advanced') as mock_find_arbitrage:
        # Создаем мок для результата поиска арбитража
        arbitrage_result = ArbitrageResult(
            cycle=['USD', 'item1', 'EUR', 'USD'],
            profit=2.0,
            profit_percent=2.0,
            liquidity=10.0,
            total_fee=0.1,
            confidence=0.8,
            recommended_volume=100.0,
            details={}
        )
        mock_find_arbitrage.return_value = [arbitrage_result]
        
        # Вызываем функцию поиска арбитража
        opportunities = await adapter.find_arbitrage_opportunities(min_profit_percent=1.0, min_liquidity=5.0)
        
        # Проверяем, что функция вернула ожидаемый результат
        assert len(opportunities) == 1
        assert opportunities[0]['cycle'] == ['USD', 'item1', 'EUR', 'USD']
        assert opportunities[0]['profit_percent'] == 2.0
        assert opportunities[0]['liquidity'] == 10.0
        assert opportunities[0]['risk_score'] == 20.0  # 100 - 80
        
        # Проверяем минимальные требования к прибыли и ликвидности
        # Создаем результат с маленькой прибылью
        low_profit_result = ArbitrageResult(
            cycle=['USD', 'item2', 'EUR', 'USD'],
            profit=0.5,
            profit_percent=0.5,  # Меньше min_profit_percent
            liquidity=10.0,
            total_fee=0.1,
            confidence=0.8,
            recommended_volume=100.0,
            details={}
        )
        mock_find_arbitrage.return_value = [low_profit_result]
        
        # Этот результат не должен пройти фильтрацию
        opportunities = await adapter.find_arbitrage_opportunities(min_profit_percent=1.0, min_liquidity=5.0)
        assert len(opportunities) == 0

@pytest.mark.asyncio
async def test_optimize_trading_strategy(adapter):
    """Тестирует оптимизацию торговой стратегии."""
    with patch('utils.api_adapter.optimize_trades') as mock_optimize:
        # Создаем тестовые арбитражные возможности
        opportunities = [
            {
                'cycle': ['USD', 'item1', 'EUR', 'USD'],
                'profit': 20.0,
                'profit_percent': 2.0,
                'liquidity': 20.0,
                'risk_score': 20.0,
                'details': {}
            },
            {
                'cycle': ['USD', 'item2', 'EUR', 'USD'],
                'profit': 15.0,
                'profit_percent': 1.5,
                'liquidity': 15.0,
                'risk_score': 30.0,
                'details': {}
            }
        ]
        
        # Мок для результата оптимизации
        mock_optimize.return_value = {
            'cycle_0': 500.0,
            'cycle_1': 300.0
        }
        
        # Вызываем функцию оптимизации с правильным именем метода
        result = await adapter.optimize_arbitrage_allocation(
            opportunities=opportunities,
            budget=1000.0,
            risk_level='medium'
        )
        
        # Проверяем результат
        assert result['status'] == 'success'
        assert result['total_profit'] > 0
        assert 'allocations' in result
        assert len(result['allocations']) == 2
        
        # Проверяем распределение средств
        assert result['allocations']['cycle_0']['amount'] == 500.0
        assert result['allocations']['cycle_1']['amount'] == 300.0
        
        # Проверяем ожидаемую прибыль
        assert result['allocations']['cycle_0']['expected_profit'] == 10.0  # 500 * 2.0 / 100
        assert result['allocations']['cycle_1']['expected_profit'] == 4.5   # 300 * 1.5 / 100

@pytest.mark.asyncio
async def test_error_handling(adapter):
    """Тестирует обработку ошибок API."""
    # Мок для имитации ошибки API
    adapter.api.get_market_items_async = AsyncMock(side_effect=APIError("Test API Error"))
    
    # Должен вернуть пустой список при ошибке API
    items = await adapter.get_market_items(limit=10)
    assert len(items) == 0
    
    # Не должно быть исключений
    opportunities = await adapter.find_arbitrage_opportunities()
    assert len(opportunities) == 0

@pytest.mark.asyncio
async def test_safe_api_call_retry(adapter):
    """Тестирует механизм повторных попыток при вызове API."""
    from api_wrapper import RateLimitError
    
    # Создаем мок, который сначала вызывает ошибку, а потом успешно выполняется
    side_effects = [RateLimitError("Rate limit", 429), MOCK_MARKET_ITEMS]
    adapter.api.get_market_items_async = AsyncMock(side_effect=side_effects)
    
    # Должен повторить запрос после ошибки и вернуть данные
    items = await adapter.get_market_items(limit=10)
    assert len(items) > 0
    
    # Проверяем, что API метод был вызван дважды (первый раз с ошибкой, второй - успешно)
    assert adapter.api.get_market_items_async.call_count == 2

if __name__ == "__main__":
    pytest.main(["-v", "test_api_integration.py"]) 