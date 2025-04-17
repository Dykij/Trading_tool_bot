"""
Общие утилиты для всего проекта.

Содержит функции, используемые в разных модулях для уменьшения дублирования кода.
"""

import os
import logging
import json
import time
from typing import Dict, List, Any, Optional, Union, Callable, TypeVar, Generic
from datetime import datetime, timedelta
from functools import wraps

# Настройка логирования
logger = logging.getLogger(__name__)

# Определение типовой переменной для типизации кеша
T = TypeVar('T')


class Cache(Generic[T]):
    """
    Класс для кеширования данных с возможностью установки TTL.
    
    Позволяет хранить данные в памяти на определенное время, 
    чтобы уменьшить количество повторных запросов.
    """
    
    def __init__(self, ttl: int = 3600):
        """
        Инициализация кеша.
        
        Args:
            ttl: Время жизни элементов кеша в секундах (по умолчанию 1 час)
        """
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[T]:
        """
        Получает значение из кеша по ключу.
        
        Args:
            key: Ключ для поиска в кеше
            
        Returns:
            Значение из кеша или None, если ключ не найден или истек срок жизни
        """
        if key not in self.cache:
            return None
        
        cache_entry = self.cache[key]
        
        # Проверяем, не истек ли срок жизни
        if time.time() > cache_entry['expires_at']:
            self.cache.pop(key)
            return None
        
        return cache_entry['value']
    
    def set(self, key: str, value: T, ttl: Optional[int] = None) -> None:
        """
        Сохраняет значение в кеш.
        
        Args:
            key: Ключ для сохранения значения
            value: Значение для сохранения
            ttl: Опциональное время жизни для этого конкретного значения
        """
        expiration_time = time.time() + (ttl if ttl is not None else self.ttl)
        
        self.cache[key] = {
            'value': value,
            'expires_at': expiration_time
        }
    
    def invalidate(self, key: str) -> bool:
        """
        Удаляет значение из кеша.
        
        Args:
            key: Ключ для удаления
            
        Returns:
            bool: True если ключ был найден и удален, иначе False
        """
        if key in self.cache:
            self.cache.pop(key)
            return True
        return False
    
    def clear(self) -> None:
        """Очищает весь кеш."""
        self.cache.clear()
    
    def get_size(self) -> int:
        """
        Возвращает количество элементов в кеше.
        
        Returns:
            int: Количество элементов в кеше
        """
        return len(self.cache)
    
    def cleanup(self) -> int:
        """
        Удаляет просроченные элементы из кеша.
        
        Returns:
            int: Количество удаленных элементов
        """
        current_time = time.time()
        expired_keys = [
            key for key, entry in self.cache.items() 
            if current_time > entry['expires_at']
        ]
        
        for key in expired_keys:
            self.cache.pop(key)
        
        return len(expired_keys)


# Глобальный кеш для использования во всем приложении
_global_cache: Optional[Cache[Any]] = None


def get_global_cache() -> Cache[Any]:
    """
    Получает глобальный экземпляр кеша.
    
    Returns:
        Cache: Глобальный экземпляр кеша
    """
    global _global_cache
    if _global_cache is None:
        _global_cache = Cache()
    return _global_cache


def cached(ttl: int = 3600, key_prefix: str = ""):
    """
    Декоратор для кеширования результатов функций.
    
    Args:
        ttl: Время жизни кеша в секундах (по умолчанию 1 час)
        key_prefix: Префикс ключа для разделения контекстов кеширования
        
    Returns:
        Callable: Декорированная функция
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Формируем ключ кеширования
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Получаем глобальный кеш
            cache = get_global_cache()
            
            # Проверяем, есть ли значение в кеше
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Возвращено кешированное значение для {func.__name__}")
                return cached_value
            
            # Выполняем функцию и кешируем результат
            result = await func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Формируем ключ кеширования
            cache_key = f"{key_prefix}:{func.__name__}:{hash(str(args) + str(sorted(kwargs.items())))}"
            
            # Получаем глобальный кеш
            cache = get_global_cache()
            
            # Проверяем, есть ли значение в кеше
            cached_value = cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Возвращено кешированное значение для {func.__name__}")
                return cached_value
            
            # Выполняем функцию и кешируем результат
            result = func(*args, **kwargs)
            cache.set(cache_key, result, ttl)
            
            return result
        
        # Выбираем подходящий враппер в зависимости от типа функции
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions=(Exception,)):
    """
    Декоратор для повторения вызова функции в случае исключения.
    
    Args:
        max_attempts: Максимальное количество попыток
        delay: Начальная задержка между попытками в секундах
        backoff: Множитель для увеличения задержки с каждой попыткой
        exceptions: Кортеж исключений, при которых нужно делать повторную попытку
        
    Returns:
        Callable: Декорированная функция
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"Попытка {attempt + 1}/{max_attempts} вызова {func.__name__} не удалась: {e}")
                    
                    if attempt < max_attempts - 1:
                        logger.info(f"Повторная попытка через {current_delay} секунд")
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            # Если все попытки исчерпаны, вызываем последнее исключение
            logger.error(f"Все {max_attempts} попыток вызова {func.__name__} не удались")
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(f"Попытка {attempt + 1}/{max_attempts} вызова {func.__name__} не удалась: {e}")
                    
                    if attempt < max_attempts - 1:
                        logger.info(f"Повторная попытка через {current_delay} секунд")
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            # Если все попытки исчерпаны, вызываем последнее исключение
            logger.error(f"Все {max_attempts} попыток вызова {func.__name__} не удались")
            raise last_exception
        
        # Выбираем подходящий враппер в зависимости от типа функции
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def format_price(price: float, currency: str = "USD") -> str:
    """
    Форматирует цену с символом валюты.
    
    Args:
        price: Цена для форматирования
        currency: Код валюты (по умолчанию USD)
        
    Returns:
        str: Отформатированная цена с символом валюты
    """
    currency_symbols = {
        "USD": "$",
        "EUR": "€",
        "RUB": "₽",
        "GBP": "£"
    }
    
    symbol = currency_symbols.get(currency, currency)
    
    if currency in ["USD", "EUR", "GBP"]:
        return f"{symbol}{price:.2f}"
    else:
        return f"{price:.2f} {symbol}"


def format_date(date: Union[str, datetime], format_str: str = "%d.%m.%Y") -> str:
    """
    Форматирует дату в указанный формат.
    
    Args:
        date: Дата для форматирования (строка ISO или объект datetime)
        format_str: Строка формата (по умолчанию дд.мм.гггг)
        
    Returns:
        str: Отформатированная дата
    """
    if isinstance(date, str):
        try:
            date_obj = datetime.fromisoformat(date.replace('Z', '+00:00'))
        except ValueError:
            return date
    else:
        date_obj = date
    
    return date_obj.strftime(format_str)


def calculate_percent_change(old_value: float, new_value: float) -> float:
    """
    Рассчитывает процентное изменение между двумя значениями.
    
    Args:
        old_value: Старое значение
        new_value: Новое значение
        
    Returns:
        float: Процентное изменение
    """
    if old_value == 0:
        return 0.0
    
    return ((new_value / old_value) - 1) * 100


def generate_cache_key(*args, **kwargs) -> str:
    """
    Генерирует ключ кеша на основе аргументов.
    
    Args:
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы
        
    Returns:
        str: Ключ кеша
    """
    args_str = ':'.join(str(arg) for arg in args)
    kwargs_str = ':'.join(f"{k}={v}" for k, v in sorted(kwargs.items()))
    
    return f"{args_str}:{kwargs_str}"


def is_similar_item(item1: Dict[str, Any], item2: Dict[str, Any], threshold: float = 0.8) -> bool:
    """
    Проверяет, похожи ли два предмета на основе их атрибутов.
    
    Args:
        item1: Первый предмет
        item2: Второй предмет
        threshold: Порог сходства (от 0 до 1)
        
    Returns:
        bool: True если предметы похожи, иначе False
    """
    # Проверяем обязательные поля
    required_fields = ['title', 'game']
    for field in required_fields:
        if field not in item1 or field not in item2:
            return False
        
        if item1[field] != item2[field]:
            return False
    
    # Сравниваем цены, если они есть
    if 'price' in item1 and 'price' in item2:
        price1 = item1['price']
        price2 = item2['price']
        
        # Если цены представлены как словари с валютами
        if isinstance(price1, dict) and isinstance(price2, dict):
            # Сравниваем USD, если доступно
            if 'USD' in price1 and 'USD' in price2:
                price1_usd = float(price1['USD'])
                price2_usd = float(price2['USD'])
                
                # Если цены сильно различаются, предметы не похожи
                price_ratio = min(price1_usd, price2_usd) / max(price1_usd, price2_usd)
                if price_ratio < threshold:
                    return False
        # Если цены представлены как числа
        elif isinstance(price1, (int, float)) and isinstance(price2, (int, float)):
            price_ratio = min(price1, price2) / max(price1, price2)
            if price_ratio < threshold:
                return False
    
    # Если все проверки пройдены, предметы считаются похожими
    return True


# Импортируем asyncio для поддержки декораторов с асинхронными функциями
import asyncio 