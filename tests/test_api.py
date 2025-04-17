import unittest
from unittest.mock import patch, Mock, MagicMock
import json
import asyncio
import aiohttp
from requests.exceptions import Timeout, ConnectionError, RequestException
from datetime import datetime

from api_wrapper import DMarketAPI, APIError, AuthenticationError, RateLimitError, NetworkError


def run_async(coroutine):
    """Вспомогательная функция для запуска асинхронных тестов."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(coroutine)


class TestDMarketAPI(unittest.TestCase):
    """Тесты для класса DMarketAPI."""

    def setUp(self):
        """Настройка перед каждым тестом."""
        self.api = DMarketAPI("test_public_key", "test_secret_key", base_url="https://api.test.com")
        
        # Применяем патч для requests
        self.requests_patcher = patch('api_wrapper.requests')
        self.mock_requests = self.requests_patcher.start()
        
        # Настраиваем поведение по умолчанию для моков
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        self.mock_requests.get.return_value = mock_response
        self.mock_requests.post.return_value = mock_response
        
    def tearDown(self):
        """Очистка после каждого теста."""
        self.requests_patcher.stop()
    
    @patch('api_wrapper.requests.get')
    def test_get_market_items_success(self, mock_get):
        """Тест успешного получения предметов с рынка."""
        # Подготовка моков
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"objects": [{"id": "1", "title": "Test Item"}]}
        mock_get.return_value = mock_response

        # Выполнение метода
        result = self.api.get_market_items(limit=10)

        # Проверки
        self.assertIsInstance(result, dict)
        self.assertIn("objects", result)
        self.assertEqual(len(result["objects"]), 1)
        self.assertEqual(result["objects"][0]["id"], "1")
        
        # Проверка правильности вызова requests.get
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["limit"], 10)
        self.assertEqual(kwargs["headers"]["X-Api-Key"], "test_public_key")
    
    @patch('api_wrapper.requests.get')
    def test_get_market_items_auth_error(self, mock_get):
        """Тест ошибки аутентификации при получении предметов."""
        # Подготовка моков
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_response.text = json.dumps({"error": "Unauthorized"})
        mock_get.return_value = mock_response

        # Проверка исключения
        with self.assertRaises(AuthenticationError):
            self.api.get_market_items()
        
        mock_get.assert_called_once()
    
    @patch('api_wrapper.requests.get')
    def test_get_market_items_rate_limit_error(self, mock_get):
        """Тест ошибки превышения лимита запросов."""
        # Подготовка моков
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        mock_response.text = json.dumps({"error": "Rate limit exceeded"})
        mock_get.return_value = mock_response

        # Проверка исключения
        with self.assertRaises(RateLimitError):
            self.api.get_market_items()
        
        mock_get.assert_called_once()
    
    @patch('api_wrapper.requests.get')
    def test_get_market_items_network_error(self, mock_get):
        """Тест ошибки сети."""
        mock_get.side_effect = ConnectionError("Connection error")

        # Проверка исключения
        with self.assertRaises(NetworkError):
            self.api.get_market_items()
        
        mock_get.assert_called_once()
    
    @patch('api_wrapper.requests.get')
    def test_get_market_items_timeout(self, mock_get):
        """Тест таймаута запроса."""
        mock_get.side_effect = Timeout("Request timeout")

        # Проверка исключения
        with self.assertRaises(NetworkError):
            self.api.get_market_items()
        
        mock_get.assert_called_once()
    
    @patch('api_wrapper.requests.post')
    def test_buy_item_success(self, mock_post):
        """Тест успешной покупки предмета."""
        # Подготовка моков
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"item": {"id": "1", "title": "Test Item"}, "success": True}
        mock_post.return_value = mock_response

        # Выполнение метода
        result = self.api.buy_item("item_123", 10.50)

        # Проверки
        self.assertIsInstance(result, dict)
        self.assertIn("item", result)
        self.assertTrue(result["success"])
        
        # Проверка правильности вызова requests.post
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["itemId"], "item_123")
        self.assertIn("price", kwargs["json"])
    
    @patch('api_wrapper.requests.post')
    def test_sell_item_success(self, mock_post):
        """Тест успешной продажи предмета."""
        # Подготовка моков
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"offer": {"id": "1", "price": {"amount": "10.50", "currency": "USD"}}, "success": True}
        mock_post.return_value = mock_response

        # Выполнение метода
        result = self.api.sell_item("item_123", 10.50)

        # Проверки
        self.assertIsInstance(result, dict)
        self.assertIn("offer", result)
        self.assertTrue(result["success"])
        
        # Проверка правильности вызова requests.post
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["itemId"], "item_123")
        self.assertIn("price", kwargs["json"])
    
    @patch('aiohttp.ClientSession.get')
    def test_get_market_items_async_success(self, mock_get):
        """Тест успешного асинхронного получения предметов с рынка."""
        # Подготовка моков
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = MagicMock(return_value={"objects": [{"id": "1", "title": "Test Item"}]})
        mock_get.return_value.__aenter__.return_value = mock_response

        # Выполнение метода
        result = run_async(self.api.get_market_items_async(limit=10))

        # Проверки
        self.assertIsInstance(result, dict)
        self.assertIn("objects", result)
        self.assertEqual(len(result["objects"]), 1)
        
        # Проверка правильности вызова aiohttp.ClientSession.get
        mock_get.assert_called_once()
    
    @patch('aiohttp.ClientSession.get')
    def test_get_market_items_async_auth_error(self, mock_get):
        """Тест ошибки аутентификации при асинхронном получении предметов."""
        # Подготовка моков
        mock_response = MagicMock()
        mock_response.status = 401
        mock_response.json = MagicMock(return_value={"error": "Unauthorized"})
        mock_response.text = MagicMock(return_value=json.dumps({"error": "Unauthorized"}))
        mock_get.return_value.__aenter__.return_value = mock_response

        # Проверка исключения
        with self.assertRaises(AuthenticationError):
            run_async(self.api.get_market_items_async())
        
        mock_get.assert_called_once()
    
    def test_signature_generation(self):
        """Тест генерации подписи для запроса."""
        # Тестируем непосредственно метод объекта
        result = self.api._generate_signature("GET", "/test-endpoint", {"param": "value"})
        
        # Проверки
        self.assertIsInstance(result, dict)
        self.assertIn("X-Sign-Date", result)
        self.assertIn("X-Request-Sign", result)
        self.assertTrue(len(result["X-Sign-Date"]) > 0)
        self.assertTrue(len(result["X-Request-Sign"]) > 0)
    
    @patch('api_wrapper.DMarketAPI.get_available_games')
    def test_ping_method(self, mock_get_available_games):
        """Тест метода ping."""
        # Настраиваем мок для get_available_games, чтобы он не вызывал ошибок
        mock_get_available_games.return_value = {"success": True}
        
        # Тестируемый метод
        result = self.api.ping()
        
        # Проверки
        self.assertTrue(result)
        mock_get_available_games.assert_called_once()
    
    @patch('api_wrapper.DMarketAPI.get_available_games')
    def test_ping_method_failed(self, mock_get_available_games):
        """Тест метода ping при ошибке."""
        # Настраиваем мок для get_available_games, чтобы он вызывал ошибку
        mock_get_available_games.side_effect = APIError("Тестовая ошибка API")
        
        # Тестируемый метод
        result = self.api.ping()
        
        # Проверки
        self.assertFalse(result)
        mock_get_available_games.assert_called_once()


if __name__ == '__main__':
    unittest.main()
