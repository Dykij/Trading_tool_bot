import logging
from typing import Dict, Any, Optional, Callable, Type, Tuple
import time
import functools
import inspect

from src.utils.function_optimizer import optimizer
from src.api.api_wrapper import DMarketAPI, APIError, RateLimitError, NetworkError

logger = logging.getLogger(__name__)

class APIOptimizer:
    """
    Класс для оптимизации работы с API DMarket.
    
    Предоставляет оптимизированные версии методов API, используя технические приемы:
    - Кэширование результатов запросов
    - Профилирование производительности
    - Интеллектуальное управление повторными попытками
    - Мониторинг использования API
    """
    
    def __init__(self, api_client: DMarketAPI):
        """
        Инициализирует оптимизатор API.
        
        Args:
            api_client: Экземпляр класса DMarketAPI
        """
        self.api_client = api_client
        self.request_stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "cache_hits": 0,
            "average_response_time": 0
        }
        self.cached_methods = []  # Храним ссылки на методы с кэшем
    
    def optimize_api_method(self, cache_ttl: int = 60, 
                           enable_profiling: bool = True,
                           enable_caching: bool = True,
                           retry_exceptions: Tuple = (NetworkError, RateLimitError)):
        """
        Декоратор для оптимизации методов API.
        
        Args:
            cache_ttl: Время жизни кэша в секундах (0 - отключить кэширование)
            enable_profiling: Включить профилирование времени выполнения
            enable_caching: Включить кэширование результатов
            retry_exceptions: Кортеж исключений, при которых делать повторные попытки.
                             По умолчанию (NetworkError, RateLimitError)
            
        Returns:
            Декорированная функция API с оптимизациями
        """
        def decorator(func: Callable) -> Callable:
            # Применяем декораторы из FunctionOptimizer
            if enable_profiling:
                func = optimizer.timer(func)
            
            if enable_caching and cache_ttl > 0:
                # Создаем временное кэширование с TTL
                cache = {}
                cache_timestamps = {}
                
                @functools.wraps(func)
                def caching_wrapper(*args, **kwargs):
                    # Создаем кэш-ключ
                    key_args = tuple(args)
                    key_kwargs = tuple(sorted(kwargs.items()))
                    cache_key = (key_args, key_kwargs)
                    
                    current_time = time.time()
                    
                    # Проверяем кэш
                    if cache_key in cache:
                        cache_time = cache_timestamps.get(cache_key, 0)
                        # Проверяем не истек ли срок кэша
                        if current_time - cache_time < cache_ttl:
                            self.request_stats["cache_hits"] += 1
                            logger.debug(f"Cache hit for {func.__name__}")
                            return cache[cache_key]
                    
                    # Вызываем оригинальную функцию
                    self.request_stats["total_requests"] += 1
                    start_time = time.time()
                    
                    try:
                        result = func(*args, **kwargs)
                        self.request_stats["successful_requests"] += 1
                        
                        # Обновляем среднее время ответа
                        elapsed = time.time() - start_time
                        prev_avg = self.request_stats["average_response_time"]
                        total_successful = self.request_stats["successful_requests"]
                        new_avg = ((prev_avg * (total_successful - 1)) + elapsed) / total_successful
                        self.request_stats["average_response_time"] = new_avg
                        
                        # Кэшируем результат
                        cache[cache_key] = result
                        cache_timestamps[cache_key] = current_time
                        
                        return result
                    except Exception as e:
                        self.request_stats["failed_requests"] += 1
                        raise e
                
                # Добавляем метод очистки кэша
                def clear_cache():
                    cache.clear()
                    cache_timestamps.clear()
                    logger.debug(f"Cache cleared for {func.__name__}")
                
                caching_wrapper.clear_cache = clear_cache
                
                # Сохраняем ссылку на метод в списке кэшированных методов
                self.cached_methods.append(caching_wrapper)
                
                # Замена функции на обертку с кэшированием
                func = caching_wrapper
            
            # Добавляем логирование и повторные попытки
            func = optimizer.debug_log(func)
            func = optimizer.retry(max_attempts=3, 
                                   delay=2.0, 
                                   backoff=2.0, 
                                   exceptions=retry_exceptions)(func)
            
            return func
        
        return decorator
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику использования API.
        
        Returns:
            Словарь со статистикой запросов
        """
        return self.request_stats
    
    def clear_caches(self) -> None:
        """
        Очищает все кэши оптимизированных методов.
        """
        cleared_count = 0
        
        # Очищаем кэши из сохраненного списка методов
        for method in self.cached_methods:
            if hasattr(method, 'clear_cache'):
                method.clear_cache()
                cleared_count += 1
        
        # Дополнительно ищем методы с clear_cache в атрибутах класса
        for attr_name in dir(self):
            if not attr_name.startswith('_'):
                attr = getattr(self, attr_name)
                if hasattr(attr, 'clear_cache') and callable(attr.clear_cache):
                    attr.clear_cache()
                    cleared_count += 1
        
        logger.info(f"Cleared {cleared_count} API caches")


def create_optimized_api(api_key: str, api_secret: Optional[str] = None, 
                        base_url: str = "https://api.dmarket.com") -> APIOptimizer:
    """
    Создает экземпляр оптимизированного API клиента.
    
    Args:
        api_key: API ключ для DMarket
        api_secret: API секрет (опционально)
        base_url: Базовый URL API
        
    Returns:
        Экземпляр APIOptimizer с настроенным клиентом DMarketAPI
    """
    api_client = DMarketAPI(api_key, api_secret, base_url)
    return APIOptimizer(api_client) 