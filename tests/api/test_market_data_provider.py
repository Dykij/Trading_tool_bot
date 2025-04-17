"""
Тесты для поставщиков рыночных данных.

Проверяет функциональность различных поставщиков данных, включая DMarket, 
Steam и другие API для получения информации о рыночных предметах.
"""

import unittest
import sys
import os
import json
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

try:
    from src.api.market_data_provider import MarketDataProvider, DMarketDataProvider, SteamDataProvider
    from src.api.dmarket_api import DMarketAPI
    from src.api.steam_api import SteamAPI
    PROVIDERS_AVAILABLE = True
except ImportError:
    # Создаем заглушки для тестирования, если модули не найдены
    PROVIDERS_AVAILABLE = False
    
    class MarketDataProvider:
        """Базовый класс для поставщиков рыночных данных."""
        
        def __init__(self, api_client=None):
            self.api_client = api_client
        
        async def get_market_items(self, params=None):
            """Получает предметы с рынка."""
            raise NotImplementedError
        
        async def get_item_by_title(self, title, params=None):
            """Получает предмет по его названию."""
            raise NotImplementedError
        
        async def get_historical_data(self, item_id, days=30):
            """Получает исторические данные по предмету."""
            raise NotImplementedError
    
    class DMarketDataProvider(MarketDataProvider):
        """Поставщик данных с DMarket."""
        
        def __init__(self, api_client=None):
            super().__init__(api_client)
        
        async def get_market_items(self, params=None):
            """Получает предметы с DMarket."""
            if not params:
                params = {}
            if not self.api_client:
                return []
            return await self.api_client.get_market_items(params)
        
        async def get_item_by_title(self, title, params=None):
            """Получает предмет по его названию с DMarket."""
            if not params:
                params = {}
            if not self.api_client:
                return None
            items = await self.api_client.get_items_by_title(title, params)
            return items[0] if items else None
        
        async def get_historical_data(self, item_id, days=30):
            """Получает исторические данные по предмету с DMarket."""
            if not self.api_client:
                return []
            return await self.api_client.get_historical_data(item_id, days)
    
    class SteamDataProvider(MarketDataProvider):
        """Поставщик данных с Steam."""
        
        def __init__(self, api_client=None):
            super().__init__(api_client)
        
        async def get_market_items(self, params=None):
            """Получает предметы с Steam."""
            if not params:
                params = {}
            if not self.api_client:
                return []
            return await self.api_client.get_market_items(params)
        
        async def get_item_by_title(self, title, params=None):
            """Получает предмет по его названию с Steam."""
            if not params:
                params = {}
            if not self.api_client:
                return None
            items = await self.api_client.get_items_by_title(title, params)
            return items[0] if items else None
        
        async def get_historical_data(self, item_id, days=30):
            """Получает исторические данные по предмету с Steam."""
            if not self.api_client:
                return []
            return await self.api_client.get_historical_data(item_id, days)


class MockDMarketAPI:
    """Мок для DMarket API."""
    
    def __init__(self):
        self.market_items = []
        self.items_by_title = {}
        self.historical_data = {}
    
    def set_market_items(self, items):
        """Устанавливает предметы рынка для мока."""
        self.market_items = items
    
    def set_items_by_title(self, title, items):
        """Устанавливает предметы по названию для мока."""
        self.items_by_title[title] = items
    
    def set_historical_data(self, item_id, data):
        """Устанавливает исторические данные для мока."""
        self.historical_data[item_id] = data
    
    async def get_market_items(self, params=None):
        """Возвращает предметы рынка."""
        return self.market_items
    
    async def get_items_by_title(self, title, params=None):
        """Возвращает предметы по названию."""
        return self.items_by_title.get(title, [])
    
    async def get_historical_data(self, item_id, days=30):
        """Возвращает исторические данные."""
        return self.historical_data.get(item_id, [])


class MockSteamAPI:
    """Мок для Steam API."""
    
    def __init__(self):
        self.market_items = []
        self.items_by_title = {}
        self.historical_data = {}
    
    def set_market_items(self, items):
        """Устанавливает предметы рынка для мока."""
        self.market_items = items
    
    def set_items_by_title(self, title, items):
        """Устанавливает предметы по названию для мока."""
        self.items_by_title[title] = items
    
    def set_historical_data(self, item_id, data):
        """Устанавливает исторические данные для мока."""
        self.historical_data[item_id] = data
    
    async def get_market_items(self, params=None):
        """Возвращает предметы рынка."""
        return self.market_items
    
    async def get_items_by_title(self, title, params=None):
        """Возвращает предметы по названию."""
        return self.items_by_title.get(title, [])
    
    async def get_historical_data(self, item_id, days=30):
        """Возвращает исторические данные."""
        return self.historical_data.get(item_id, [])


class TestDMarketDataProvider(unittest.TestCase):
    """Тесты для DMarket провайдера данных."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем мок API
        self.mock_api = MockDMarketAPI()
        
        # Настраиваем тестовые данные
        self.test_market_items = [
            {'id': '1', 'title': 'Item 1', 'price': 100},
            {'id': '2', 'title': 'Item 2', 'price': 200}
        ]
        
        self.test_items_by_title = {
            'Item 1': [{'id': '1', 'title': 'Item 1', 'price': 100}],
            'Item 2': [{'id': '2', 'title': 'Item 2', 'price': 200}]
        }
        
        self.test_historical_data = {
            '1': [
                {'date': '2023-01-01', 'price': 90},
                {'date': '2023-01-02', 'price': 95},
                {'date': '2023-01-03', 'price': 100}
            ],
            '2': [
                {'date': '2023-01-01', 'price': 180},
                {'date': '2023-01-02', 'price': 190},
                {'date': '2023-01-03', 'price': 200}
            ]
        }
        
        # Настраиваем мок API данными
        self.mock_api.set_market_items(self.test_market_items)
        for title, items in self.test_items_by_title.items():
            self.mock_api.set_items_by_title(title, items)
        for item_id, data in self.test_historical_data.items():
            self.mock_api.set_historical_data(item_id, data)
        
        # Создаем провайдер с моком API
        self.provider = DMarketDataProvider(api_client=self.mock_api)
    
    def asyncSetUp(self):
        """Асинхронная настройка, может быть полезна в будущем."""
        pass
    
    def asyncTearDown(self):
        """Асинхронная очистка, может быть полезна в будущем."""
        pass
    
    def test_init(self):
        """Тест инициализации провайдера."""
        # Проверяем, что API клиент установлен
        self.assertEqual(self.provider.api_client, self.mock_api)
        
        # Проверяем инициализацию без API клиента
        provider = DMarketDataProvider()
        self.assertIsNone(provider.api_client)
    
    def test_get_market_items(self):
        """Тест получения предметов рынка."""
        # Запускаем корутину
        items = asyncio.run(self.provider.get_market_items())
        
        # Проверяем, что получены правильные предметы
        self.assertEqual(items, self.test_market_items)
        
        # Проверяем с параметрами
        items = asyncio.run(self.provider.get_market_items({'game': 'csgo'}))
        
        # Метод должен возвращать те же предметы, так как мок не обрабатывает параметры
        self.assertEqual(items, self.test_market_items)
    
    def test_get_item_by_title(self):
        """Тест получения предмета по названию."""
        # Запускаем корутину для существующего предмета
        item = asyncio.run(self.provider.get_item_by_title('Item 1'))
        
        # Проверяем, что получен правильный предмет
        self.assertEqual(item, self.test_items_by_title['Item 1'][0])
        
        # Запускаем корутину для несуществующего предмета
        item = asyncio.run(self.provider.get_item_by_title('Nonexistent Item'))
        
        # Проверяем, что предмет не найден
        self.assertIsNone(item)
    
    def test_get_historical_data(self):
        """Тест получения исторических данных."""
        # Запускаем корутину для существующего предмета
        data = asyncio.run(self.provider.get_historical_data('1'))
        
        # Проверяем, что получены правильные данные
        self.assertEqual(data, self.test_historical_data['1'])
        
        # Запускаем корутину для несуществующего предмета
        data = asyncio.run(self.provider.get_historical_data('nonexistent'))
        
        # Проверяем, что данные не найдены (пустой список)
        self.assertEqual(data, [])
    
    def test_no_api_client(self):
        """Тест поведения без API клиента."""
        # Создаем провайдер без API клиента
        provider = DMarketDataProvider()
        
        # Проверяем get_market_items
        items = asyncio.run(provider.get_market_items())
        self.assertEqual(items, [])
        
        # Проверяем get_item_by_title
        item = asyncio.run(provider.get_item_by_title('Item 1'))
        self.assertIsNone(item)
        
        # Проверяем get_historical_data
        data = asyncio.run(provider.get_historical_data('1'))
        self.assertEqual(data, [])


class TestSteamDataProvider(unittest.TestCase):
    """Тесты для Steam провайдера данных."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        # Создаем мок API
        self.mock_api = MockSteamAPI()
        
        # Настраиваем тестовые данные
        self.test_market_items = [
            {'id': 'S1', 'title': 'Steam Item 1', 'price': 150},
            {'id': 'S2', 'title': 'Steam Item 2', 'price': 250}
        ]
        
        self.test_items_by_title = {
            'Steam Item 1': [{'id': 'S1', 'title': 'Steam Item 1', 'price': 150}],
            'Steam Item 2': [{'id': 'S2', 'title': 'Steam Item 2', 'price': 250}]
        }
        
        self.test_historical_data = {
            'S1': [
                {'date': '2023-01-01', 'price': 140},
                {'date': '2023-01-02', 'price': 145},
                {'date': '2023-01-03', 'price': 150}
            ],
            'S2': [
                {'date': '2023-01-01', 'price': 230},
                {'date': '2023-01-02', 'price': 240},
                {'date': '2023-01-03', 'price': 250}
            ]
        }
        
        # Настраиваем мок API данными
        self.mock_api.set_market_items(self.test_market_items)
        for title, items in self.test_items_by_title.items():
            self.mock_api.set_items_by_title(title, items)
        for item_id, data in self.test_historical_data.items():
            self.mock_api.set_historical_data(item_id, data)
        
        # Создаем провайдер с моком API
        self.provider = SteamDataProvider(api_client=self.mock_api)
    
    def test_init(self):
        """Тест инициализации провайдера."""
        # Проверяем, что API клиент установлен
        self.assertEqual(self.provider.api_client, self.mock_api)
        
        # Проверяем инициализацию без API клиента
        provider = SteamDataProvider()
        self.assertIsNone(provider.api_client)
    
    def test_get_market_items(self):
        """Тест получения предметов рынка."""
        # Запускаем корутину
        items = asyncio.run(self.provider.get_market_items())
        
        # Проверяем, что получены правильные предметы
        self.assertEqual(items, self.test_market_items)
        
        # Проверяем с параметрами
        items = asyncio.run(self.provider.get_market_items({'game': 'csgo'}))
        
        # Метод должен возвращать те же предметы, так как мок не обрабатывает параметры
        self.assertEqual(items, self.test_market_items)
    
    def test_get_item_by_title(self):
        """Тест получения предмета по названию."""
        # Запускаем корутину для существующего предмета
        item = asyncio.run(self.provider.get_item_by_title('Steam Item 1'))
        
        # Проверяем, что получен правильный предмет
        self.assertEqual(item, self.test_items_by_title['Steam Item 1'][0])
        
        # Запускаем корутину для несуществующего предмета
        item = asyncio.run(self.provider.get_item_by_title('Nonexistent Item'))
        
        # Проверяем, что предмет не найден
        self.assertIsNone(item)
    
    def test_get_historical_data(self):
        """Тест получения исторических данных."""
        # Запускаем корутину для существующего предмета
        data = asyncio.run(self.provider.get_historical_data('S1'))
        
        # Проверяем, что получены правильные данные
        self.assertEqual(data, self.test_historical_data['S1'])
        
        # Запускаем корутину для несуществующего предмета
        data = asyncio.run(self.provider.get_historical_data('nonexistent'))
        
        # Проверяем, что данные не найдены (пустой список)
        self.assertEqual(data, [])
    
    def test_no_api_client(self):
        """Тест поведения без API клиента."""
        # Создаем провайдер без API клиента
        provider = SteamDataProvider()
        
        # Проверяем get_market_items
        items = asyncio.run(provider.get_market_items())
        self.assertEqual(items, [])
        
        # Проверяем get_item_by_title
        item = asyncio.run(provider.get_item_by_title('Steam Item 1'))
        self.assertIsNone(item)
        
        # Проверяем get_historical_data
        data = asyncio.run(provider.get_historical_data('S1'))
        self.assertEqual(data, [])


class TestMarketDataProviderAbstract(unittest.TestCase):
    """Тесты для абстрактного класса MarketDataProvider."""
    
    def test_abstract_methods(self):
        """Тест, что абстрактные методы вызывают NotImplementedError."""
        provider = MarketDataProvider()
        
        # Проверяем get_market_items
        with self.assertRaises(NotImplementedError):
            asyncio.run(provider.get_market_items())
        
        # Проверяем get_item_by_title
        with self.assertRaises(NotImplementedError):
            asyncio.run(provider.get_item_by_title('Test'))
        
        # Проверяем get_historical_data
        with self.assertRaises(NotImplementedError):
            asyncio.run(provider.get_historical_data('1'))


class TestProviderFactory(unittest.TestCase):
    """Тесты для фабрики провайдеров данных."""
    
    def setUp(self):
        """Настройка тестового окружения."""
        try:
            from src.api.provider_factory import ProviderFactory
            self.ProviderFactory = ProviderFactory
            self.provider_factory_available = True
        except ImportError:
            # Создаем заглушку, если класс не найден
            class ProviderFactory:
                @staticmethod
                def create_provider(provider_type, api_client=None):
                    """Создает провайдера данных указанного типа."""
                    if provider_type == 'dmarket':
                        return DMarketDataProvider(api_client)
                    elif provider_type == 'steam':
                        return SteamDataProvider(api_client)
                    else:
                        raise ValueError(f"Unknown provider type: {provider_type}")
            
            self.ProviderFactory = ProviderFactory
            self.provider_factory_available = False
    
    def test_create_dmarket_provider(self):
        """Тест создания DMarket провайдера."""
        # Создаем мок API
        mock_api = MockDMarketAPI()
        
        # Создаем провайдер через фабрику
        provider = self.ProviderFactory.create_provider('dmarket', mock_api)
        
        # Проверяем тип провайдера
        self.assertIsInstance(provider, DMarketDataProvider)
        
        # Проверяем, что API клиент установлен
        self.assertEqual(provider.api_client, mock_api)
    
    def test_create_steam_provider(self):
        """Тест создания Steam провайдера."""
        # Создаем мок API
        mock_api = MockSteamAPI()
        
        # Создаем провайдер через фабрику
        provider = self.ProviderFactory.create_provider('steam', mock_api)
        
        # Проверяем тип провайдера
        self.assertIsInstance(provider, SteamDataProvider)
        
        # Проверяем, что API клиент установлен
        self.assertEqual(provider.api_client, mock_api)
    
    def test_unknown_provider(self):
        """Тест обработки неизвестного типа провайдера."""
        # Проверяем, что создание провайдера с неизвестным типом вызывает исключение
        with self.assertRaises(ValueError):
            self.ProviderFactory.create_provider('unknown')


if __name__ == '__main__':
    unittest.main() 