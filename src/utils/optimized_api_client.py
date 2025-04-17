import logging
from typing import Dict, List, Any, Optional
import functools

from src.utils.api_optimizer import APIOptimizer, create_optimized_api
from src.api.api_wrapper import DMarketAPI, APIError

logger = logging.getLogger(__name__)

class OptimizedDMarketAPI:
    """
    Оптимизированная версия DMarketAPI с улучшенной производительностью.
    
    Использует кэширование, профилирование и другие оптимизации
    для повышения эффективности работы с API DMarket.
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None, 
                 base_url: str = "https://api.dmarket.com"):
        """
        Инициализирует оптимизированный API клиент.
        
        Args:
            api_key: Ключ API DMarket
            api_secret: Секрет API DMarket (опционально)
            base_url: Базовый URL API
        """
        self.optimizer = create_optimized_api(api_key, api_secret, base_url)
        self.api_client = self.optimizer.api_client
        self._setup_optimized_methods()
    
    def _setup_optimized_methods(self):
        """
        Настраивает оптимизированные методы API.
        Мы обертываем методы api_client оптимизатором вместо создания новых функций.
        """
        # Создаем словарь с методами и их настройками кэширования
        optimized_methods = {
            # Кэширование 30 секунд для рыночных запросов
            'get_market_items': {'cache_ttl': 30, 'enable_profiling': True},
            
            # Долгое кэширование для деталей предметов, так как они редко меняются
            'get_item_details': {'cache_ttl': 300, 'enable_profiling': True},
            
            # Короткое кэширование для поисковых запросов
            'search_market_items': {'cache_ttl': 15, 'enable_profiling': True},
            
            # Методы баланса и истории не кэшируются, так как важна актуальность
            'get_user_balance': {'cache_ttl': 0, 'enable_profiling': True},
            'get_user_offers': {'cache_ttl': 0, 'enable_profiling': True},
        }
        
        # Применяем оптимизацию к каждому методу
        for method_name, options in optimized_methods.items():
            if hasattr(self.api_client, method_name):
                original_method = getattr(self.api_client, method_name)
                
                # Создаем обертку, которая вызывает оригинальный метод
                @functools.wraps(original_method)
                def optimized_method_wrapper(m_name=method_name, **kwargs):
                    # Получаем оригинальный метод и вызываем его с такими же аргументами
                    original = getattr(self.api_client, m_name)
                    return original(**kwargs)
                
                # Применяем декоратор оптимизации
                optimized_method = self.optimizer.optimize_api_method(
                    cache_ttl=options['cache_ttl'],
                    enable_profiling=options['enable_profiling']
                )(optimized_method_wrapper)
                
                # Привязываем оптимизированный метод к экземпляру класса
                setattr(self, method_name, optimized_method)
    
    def clear_caches(self) -> None:
        """
        Очищает все кэши оптимизированных методов API.
        """
        self.optimizer.clear_caches()
        logger.info("All API caches cleared")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику использования API.
        
        Returns:
            Словарь со статистикой запросов
        """
        return self.optimizer.get_stats()
    
    # Пример прямой передачи некоторых методов к оригинальному клиенту
    def create_offer(self, *args, **kwargs):
        """Прямая передача метода create_offer к оригинальному API клиенту."""
        return self.api_client.create_offer(*args, **kwargs)
    
    def cancel_offer(self, *args, **kwargs):
        """Прямая передача метода cancel_offer к оригинальному API клиенту."""
        return self.api_client.cancel_offer(*args, **kwargs)
    
    def buy_item(self, *args, **kwargs):
        """Прямая передача метода buy_item к оригинальному API клиенту."""
        return self.api_client.buy_item(*args, **kwargs) 