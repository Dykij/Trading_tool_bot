"""
Тесты для модуля marketplace_integrator.py

Проверяет работу MarketplaceIntegrator, включая:
- Обработку ответов API
- Нормализацию данных предметов
- Построение графа обменных курсов
- Обработку ошибок при пустых данных
"""

import os
import sys
import pytest
import logging
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Dict, List, Any, Optional

# Добавляем корневую директорию проекта в путь импорта
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.marketplace_integrator import MarketplaceIntegrator
from models.item_models import GameType, SkinArbitrageOption

# Настраиваем логирование для тестов
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class TestMarketplaceIntegrator:
    """Тесты для класса MarketplaceIntegrator."""

    @pytest.fixture
    def mock_dmarket_adapter(self):
        """Фикстура для создания мок-объекта DMarketAdapter."""
        adapter_mock = AsyncMock()
        # Настраиваем мок для метода get_market_items
        adapter_mock.get_market_items = AsyncMock()
        return adapter_mock

    @pytest.fixture
    def integrator(self, mock_dmarket_adapter):
        """Фикстура для создания экземпляра MarketplaceIntegrator с мок-адаптером."""
        return MarketplaceIntegrator(
            dmarket_adapter=mock_dmarket_adapter,
            bitskins_api_key="test_bitskins_key",
            backpack_api_key="test_backpack_key"
        )

    @pytest.mark.asyncio
    async def test_get_market_items_empty_response(self, integrator, mock_dmarket_adapter):
        """Тест обработки пустого ответа от API при получении предметов."""
        # Настраиваем мок для возврата пустого списка
        mock_dmarket_adapter.get_market_items.return_value = []
        
        # Вызываем тестируемый метод
        result = await integrator.get_market_items(game_id='a8db', limit=10)
        
        # Проверяем результат
        assert result == []
        mock_dmarket_adapter.get_market_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_market_items_with_dict_format(self, integrator, mock_dmarket_adapter):
        """Тест обработки данных в формате словаря при получении предметов."""
        # Подготавливаем тестовые данные в формате словаря
        mock_items = [
            {
                'itemId': 'item1',
                'title': 'Test Item 1',
                'gameId': 'a8db',
                'price': {'USD': 10.5},
                'suggestedPrice': {'USD': 11.0},
                'extra': {'salesPerDay': 5.0},
                'category': 'weapon',
                'rarity': 'rare'
            }
        ]
        
        # Настраиваем мок для возврата тестовых данных
        mock_dmarket_adapter.get_market_items.return_value = mock_items
        
        # Вызываем тестируемый метод
        result = await integrator.get_market_items(game_id='a8db', limit=10)
        
        # Проверяем результат
        assert len(result) == 1
        assert result[0]['itemId'] == 'item1'
        assert result[0]['title'] == 'Test Item 1'
        assert result[0]['price']['USD'] == 10.5

    @pytest.mark.asyncio
    async def test_get_market_items_with_object_format(self, integrator, mock_dmarket_adapter):
        """Тест обработки данных в формате объектов при получении предметов."""
        # Создаем класс для имитации объектов MarketItem
        class MarketItem:
            def __init__(self, item_id, title, game, prices, liquidity, category, rarity):
                self.item_id = item_id
                self.title = title
                self.game = game
                self.prices = prices
                self.liquidity = liquidity
                self.category = category
                self.rarity = rarity
                self.suggested_prices = {'USD': prices['USD'] * 1.05}
        
        # Подготавливаем тестовые данные в формате объектов
        mock_items = [
            MarketItem(
                item_id='item1',
                title='Test Item 1',
                game='a8db',
                prices={'USD': 10.5},
                liquidity=5.0,
                category='weapon',
                rarity='rare'
            )
        ]
        
        # Настраиваем мок для возврата тестовых данных
        mock_dmarket_adapter.get_market_items.return_value = mock_items
        
        # Вызываем тестируемый метод
        result = await integrator.get_market_items(game_id='a8db', limit=10)
        
        # Проверяем результат
        assert len(result) == 1
        assert 'itemId' in result[0]
        assert result[0]['itemId'] == 'item1'
        assert result[0]['title'] == 'Test Item 1'
        assert result[0]['price']['USD'] == 10.5

    @pytest.mark.asyncio
    async def test_get_exchange_data_empty_response(self, integrator, mock_dmarket_adapter):
        """Тест обработки пустого ответа от API при построении графа обменных курсов."""
        # Настраиваем мок для возврата пустого списка
        mock_dmarket_adapter.get_market_items.return_value = []
        
        # Вызываем тестируемый метод
        result = await integrator.get_exchange_data(game_id='a8db', max_items=10)
        
        # Проверяем результат
        assert result == {}
        mock_dmarket_adapter.get_market_items.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_exchange_data_with_valid_data(self, integrator, mock_dmarket_adapter):
        """Тест построения графа обменных курсов с валидными данными."""
        # Создаем класс для имитации объектов MarketItem
        class MarketItem:
            def __init__(self, item_id, title, prices, liquidity):
                self.item_id = item_id
                self.title = title
                self.prices = prices
                self.liquidity = liquidity
        
        # Подготавливаем тестовые данные
        mock_items = [
            MarketItem(
                item_id='item1',
                title='Item 1',
                prices={'USD': 10.0},
                liquidity=5.0
            ),
            MarketItem(
                item_id='item2',
                title='Item 2',
                prices={'USD': 5.0},
                liquidity=3.0
            ),
            MarketItem(
                item_id='item3',
                title='Item 3',
                prices={'USD': 2.0},
                liquidity=7.0
            )
        ]
        
        # Настраиваем мок для возврата тестовых данных
        mock_dmarket_adapter.get_market_items.return_value = mock_items
        
        # Вызываем тестируемый метод
        result = await integrator.get_exchange_data(game_id='a8db', max_items=10)
        
        # Проверяем результат
        assert len(result) == 3  # Три узла в графе
        assert 'Item 1' in result
        assert 'Item 2' in result
        assert 'Item 3' in result
        
        # Проверяем структуру рёбер
        assert 'Item 2' in result['Item 1']
        assert 'Item 3' in result['Item 1']
        
        # Проверяем пример обменного курса
        assert 'rate' in result['Item 1']['Item 2']
        assert 'liquidity' in result['Item 1']['Item 2']
        assert 'fee' in result['Item 1']['Item 2']
        
        # Проверяем расчет обменного курса для одной пары предметов
        # Item 1 ($10) -> Item 2 ($5) с комиссией 5%
        # rate = (10 * 0.95) / 5 = 1.9
        assert abs(result['Item 1']['Item 2']['rate'] - 1.9) < 0.01

    @pytest.mark.asyncio
    async def test_get_exchange_data_with_invalid_prices(self, integrator, mock_dmarket_adapter):
        """Тест обработки некорректных цен при построении графа обменных курсов."""
        # Создаем класс для имитации объектов MarketItem с некорректными ценами
        class MarketItem:
            def __init__(self, item_id, title, prices, liquidity):
                self.item_id = item_id
                self.title = title
                self.prices = prices
                self.liquidity = liquidity
        
        # Подготавливаем тестовые данные с нулевыми ценами
        mock_items = [
            MarketItem(
                item_id='item1',
                title='Item 1',
                prices={'USD': 0.0},  # Нулевая цена
                liquidity=5.0
            ),
            MarketItem(
                item_id='item2',
                title='Item 2',
                prices={'USD': 5.0},
                liquidity=3.0
            )
        ]
        
        # Настраиваем мок для возврата тестовых данных
        mock_dmarket_adapter.get_market_items.return_value = mock_items
        
        # Вызываем тестируемый метод
        result = await integrator.get_exchange_data(game_id='a8db', max_items=10)
        
        # Проверяем результат
        assert len(result) == 1  # Только один узел в графе с валидной ценой
        assert 'Item 1' not in result  # Предмет с нулевой ценой должен быть пропущен
        assert 'Item 2' in result

    @pytest.mark.asyncio
    async def test_find_arbitrage_opportunities_empty_graph(self, integrator):
        """Тест обработки пустого графа при поиске арбитражных возможностей."""
        # Вызываем тестируемый метод с пустым графом
        result = await integrator.find_arbitrage_opportunities(
            exchange_data={},
            min_profit_percent=1.0,
            min_liquidity=0.5
        )
        
        # Проверяем результат
        assert result == []

    @pytest.mark.asyncio
    @patch('utils.marketplace_integrator.find_arbitrage_advanced')
    async def test_find_arbitrage_opportunities_with_valid_data(self, mock_find_arbitrage, integrator):
        """Тест поиска арбитражных возможностей с валидными данными."""
        # Подготавливаем тестовые данные
        exchange_data = {
            'Item 1': {
                'Item 2': {
                    'rate': 1.9,
                    'liquidity': 3.0,
                    'fee': 0.05,
                    'from_price': 10.0,
                    'to_price': 5.0,
                    'from_id': 'item1',
                    'to_id': 'item2'
                }
            },
            'Item 2': {
                'Item 3': {
                    'rate': 2.375,
                    'liquidity': 3.0,
                    'fee': 0.05,
                    'from_price': 5.0,
                    'to_price': 2.0,
                    'from_id': 'item2',
                    'to_id': 'item3'
                }
            },
            'Item 3': {
                'Item 1': {
                    'rate': 0.19,
                    'liquidity': 5.0,
                    'fee': 0.05,
                    'from_price': 2.0,
                    'to_price': 10.0,
                    'from_id': 'item3',
                    'to_id': 'item1'
                }
            }
        }
        
        # Готовим мок-ответ для функции find_arbitrage_advanced
        mock_arbitrage_result = [
            {
                'cycle': ['Item 1', 'Item 2', 'Item 3', 'Item 1'],
                'total_rate': 1.05,  # 5% прибыли
                'edges': [
                    {'from_name': 'Item 1', 'to_name': 'Item 2', 'rate': 1.9, 'liquidity': 3.0},
                    {'from_name': 'Item 2', 'to_name': 'Item 3', 'rate': 2.375, 'liquidity': 3.0},
                    {'from_name': 'Item 3', 'to_name': 'Item 1', 'rate': 0.19, 'liquidity': 5.0}
                ],
                'min_liquidity': 3.0
            }
        ]
        mock_find_arbitrage.return_value = mock_arbitrage_result
        
        # Вызываем тестируемый метод
        result = await integrator.find_arbitrage_opportunities(
            exchange_data=exchange_data,
            min_profit_percent=1.0,
            min_liquidity=0.5
        )
        
        # Проверяем результат
        assert len(result) == 1
        assert result[0]['cycle'] == ['Item 1', 'Item 2', 'Item 3', 'Item 1']
        assert result[0]['total_rate'] == 1.05

    @pytest.mark.asyncio
    @patch('utils.marketplace_integrator.create_graph')
    @patch('utils.marketplace_integrator.find_arbitrage_advanced')
    async def test_find_arbitrage_opportunities_error_handling(self, mock_find_arbitrage, mock_create_graph, integrator):
        """Тест обработки ошибок при поиске арбитражных возможностей."""
        # Настраиваем мок для выброса исключения
        mock_create_graph.side_effect = Exception("Test error in graph creation")
        
        # Подготавливаем тестовые данные
        exchange_data = {'Item 1': {'Item 2': {'rate': 1.0}}}
        
        # Вызываем тестируемый метод
        result = await integrator.find_arbitrage_opportunities(
            exchange_data=exchange_data,
            min_profit_percent=1.0,
            min_liquidity=0.5
        )
        
        # Проверяем результат
        assert result == []
        # Проверяем, что create_graph был вызван
        mock_create_graph.assert_called_once()
        # Проверяем, что find_arbitrage_advanced не был вызван из-за ошибки
        mock_find_arbitrage.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_cross_platform_arbitrage_cache_usage(self, integrator):
        """Тест использования кэша при поиске кросс-платформенных арбитражных возможностей."""
        # Подготавливаем тестовые данные для кэша
        test_arbitrage_option = SkinArbitrageOption(
            item_name="Test Item",
            market1="DMarket",
            market2="Bitskins",
            price1=10.0,
            price2=15.0,
            profit_amount=5.0,
            profit_percent=50.0,
            liquidity=3.0,
            game=GameType.CS2
        )
        
        # Устанавливаем кэш
        integrator.arbitrage_cache['a8db'] = [test_arbitrage_option]
        integrator.last_update['a8db'] = integrator.cache_ttl + 1  # Устаревший кэш
        
        # Подменяем метод _find_cross_platform_arbitrage_for_game
        integrator._find_cross_platform_arbitrage_for_game = AsyncMock()
        integrator._find_cross_platform_arbitrage_for_game.return_value = [test_arbitrage_option]
        
        # Вызываем тестируемый метод без принудительного обновления
        result = await integrator.get_cross_platform_arbitrage(
            game=GameType.CS2,
            force_update=False
        )
        
        # Проверяем, что метод _find_cross_platform_arbitrage_for_game был вызван,
        # так как кэш устарел
        integrator._find_cross_platform_arbitrage_for_game.assert_called_once()
        assert len(result) == 1
        assert result[0].item_name == "Test Item"
        
        # Сбрасываем счетчик вызовов
        integrator._find_cross_platform_arbitrage_for_game.reset_mock()
        # Обновляем время последнего обновления кэша
        integrator.last_update['a8db'] = 0  # Свежий кэш
        
        # Вызываем тестируемый метод еще раз
        result = await integrator.get_cross_platform_arbitrage(
            game=GameType.CS2,
            force_update=False
        )
        
        # Проверяем, что метод _find_cross_platform_arbitrage_for_game не был вызван,
        # так как использовался свежий кэш
        integrator._find_cross_platform_arbitrage_for_game.assert_not_called()
        assert len(result) == 1
        assert result[0].item_name == "Test Item"
        
        # Вызываем метод с принудительным обновлением
        result = await integrator.get_cross_platform_arbitrage(
            game=GameType.CS2,
            force_update=True
        )
        
        # Проверяем, что метод _find_cross_platform_arbitrage_for_game был вызван
        # из-за принудительного обновления
        integrator._find_cross_platform_arbitrage_for_game.assert_called_once()


if __name__ == "__main__":
    pytest.main(["-v", "test_marketplace_integrator.py"]) 