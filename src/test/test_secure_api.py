"""
Тестовый модуль, демонстрирующий использование модулей обработки ошибок и
безопасной конфигурации API ключей.

Этот модуль может быть запущен как скрипт для проверки функциональности.
"""

import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

# Настраиваем базовое логирование для тестирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("secure_api_test")

# Добавляем путь проекта в sys.path, если запускаем напрямую
if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.error_handling import (
    APIError,
    BotError,
    ConfigError,
    ErrorSeverity,
    handle_errors,
    log_execution,
    retry,
    validate_args
)
from src.utils.secure_config import (
    SecureConfig,
    save_api_keys,
    load_api_keys,
    add_api_key,
    has_api_keys
)


class APISimulator:
    """
    Класс для симуляции вызовов API с возможными ошибками.
    """

    def __init__(self, failure_rate: float = 0.3):
        """
        Инициализация симулятора.
        
        Args:
            failure_rate: Частота ошибок (0.0 - 1.0)
        """
        self.failure_rate = failure_rate
        self.call_count = 0
    
    @retry(max_attempts=3, delay=0.5, backoff_factor=2.0)
    def api_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Симулирует запрос к API.
        
        Args:
            endpoint: Целевой эндпоинт API
            params: Параметры запроса
            
        Returns:
            Dict[str, Any]: Результат запроса
            
        Raises:
            APIError: При ошибке запроса к API
        """
        import random
        
        self.call_count += 1
        logger.info(f"API request #{self.call_count} to {endpoint}")
        
        # Симулируем случайные ошибки
        if random.random() < self.failure_rate:
            if random.random() < 0.5:
                # Временная ошибка (будет повторена)
                logger.warning(f"Temporary API error on {endpoint}")
                raise APIError(
                    message=f"API request to {endpoint} failed: Connection timeout",
                    details={"endpoint": endpoint, "params": params},
                    is_temporary=True,
                    severity=ErrorSeverity.MEDIUM
                )
            else:
                # Постоянная ошибка (не будет повторена)
                logger.error(f"Permanent API error on {endpoint}")
                raise APIError(
                    message=f"API request to {endpoint} failed: Invalid authentication",
                    details={"endpoint": endpoint, "params": params},
                    is_temporary=False,
                    severity=ErrorSeverity.HIGH
                )
        
        # Успешный ответ
        time.sleep(0.1)  # Имитация задержки сети
        logger.info(f"API request to {endpoint} successful")
        return {
            "status": "success",
            "endpoint": endpoint,
            "params": params,
            "data": {"test_value": 42, "timestamp": time.time()}
        }


@validate_args(service=str, item_name=str, min_price=(int, float), max_price=(int, float))
@handle_errors(error_types=[APIError, BotError])
def analyze_market_item(
    service: str,
    item_name: str,
    min_price: float = 0.0,
    max_price: float = 1000.0
) -> Dict[str, Any]:
    """
    Анализирует предмет на рынке.
    
    Args:
        service: Сервис для анализа
        item_name: Название предмета
        min_price: Минимальная цена
        max_price: Максимальная цена
        
    Returns:
        Dict[str, Any]: Результаты анализа
        
    Raises:
        APIError: При ошибке API
        ValueError: При некорректных параметрах
    """
    if min_price > max_price:
        raise ValueError(f"min_price ({min_price}) cannot be greater than max_price ({max_price})")
    
    # Проверяем наличие API ключей
    if not has_api_keys():
        raise ConfigError(
            message=f"API keys for service '{service}' not configured",
            severity=ErrorSeverity.HIGH
        )
    
    # Симулируем API вызовы
    api = APISimulator(failure_rate=0.3)
    
    # Получаем информацию о предмете
    item_info = api.api_request(
        f"{service}/item/info",
        {"name": item_name}
    )
    
    # Получаем цены предмета
    pricing = api.api_request(
        f"{service}/item/price",
        {"name": item_name, "min_price": min_price, "max_price": max_price}
    )
    
    # Симулируем анализ и возвращаем результаты
    return {
        "item": item_name,
        "service": service,
        "average_price": (min_price + max_price) / 2,
        "availability": "high" if pricing["data"]["test_value"] > 30 else "low",
        "last_updated": time.time()
    }


@log_execution(log_args=True, log_result=True)
def demo_secure_config(
    test_password: str,
    service_name: str = "dmarket",
    test_key_id: str = "test_key_123",
    test_key_secret: str = "test_secret_456"
) -> None:
    """
    Демонстрирует работу с безопасной конфигурацией.
    
    Args:
        test_password: Пароль для шифрования
        service_name: Название сервиса
        test_key_id: Тестовый ID ключа
        test_key_secret: Тестовый секретный ключ
    """
    logger.info("===== SECURE CONFIG DEMO =====")
    
    # Сохраняем API ключи
    logger.info(f"Saving API keys for {service_name}")
    add_api_key(service_name, test_key_id, test_key_secret, test_password)
    
    # Загружаем API ключи
    logger.info(f"Loading API keys")
    keys = load_api_keys(test_password)
    
    # Выводим результаты (в реальном коде не следует выводить секретные ключи)
    logger.info(f"Loaded keys for services: {list(keys.keys())}")
    logger.info(f"Keys for {service_name}: {keys.get(service_name, {})}")


@log_execution()
def demo_error_handling(service_name: str, item_name: str) -> None:
    """
    Демонстрирует работу с системой обработки ошибок.
    
    Args:
        service_name: Название сервиса
        item_name: Название предмета
    """
    logger.info("===== ERROR HANDLING DEMO =====")
    
    try:
        # Пример с корректными параметрами
        logger.info(f"Analyzing item: {item_name}")
        result = analyze_market_item(service_name, item_name, 10.0, 100.0)
        logger.info(f"Analysis result: {result}")
        
        # Пример с некорректными параметрами
        logger.info("Trying with invalid prices (min > max)")
        result = analyze_market_item(service_name, item_name, 200.0, 100.0)
        logger.info(f"Result (should not reach here): {result}")
        
    except ValueError as e:
        logger.error(f"Validation error: {e}")
    except BotError as e:
        logger.error(f"Bot error: {e.message} (Severity: {e.severity.name})")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")


def run_demo() -> None:
    """
    Запускает полную демонстрацию всех компонентов.
    """
    try:
        # Параметры тестирования
        test_password = "secure_test_password"
        service_name = "dmarket"
        item_name = "AK-47 | Redline"
        
        # Демонстрация безопасной конфигурации
        demo_secure_config(test_password, service_name)
        
        # Демонстрация обработки ошибок
        demo_error_handling(service_name, item_name)
        
        logger.info("Demo completed successfully")
        
    except Exception as e:
        logger.error(f"Demo failed with error: {e}")
        if isinstance(e, BotError):
            logger.error(f"Details: {e.details}")


if __name__ == "__main__":
    run_demo() 