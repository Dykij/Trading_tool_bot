"""
Модуль для анализа рынка DMarket.

Содержит функции для поиска арбитражных возможностей, 
анализа исторических данных и оптимизации торговых стратегий.
"""

import os
import time
import json
import asyncio
import logging
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional, Set, Union, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import threading
import math
from functools import wraps
import multiprocessing
import uuid
from collections import defaultdict
import hashlib

# ИСПРАВЛЕННЫЕ ИМПОРТЫ
from src.api.api_wrapper import DMarketAPI, APIError, RateLimitError, AuthenticationError, NetworkError
from src.arbitrage.bellman_ford import create_graph, bellman_ford_optimized, find_arbitrage_advanced, ArbitrageResult, Edge
from src.arbitrage.linear_programming import optimize_trades, get_optimized_allocation
from src.DM.utils.database import save_market_snapshot, get_historical_prices, save_arbitrage_result
from src.DM.utils.caching import CacheManager
from src.DM.utils.performance_metrics import MetricsCollector
# Предполагаем, что PerformanceMonitor находится здесь же
from src.DM.utils.performance_monitor import PerformanceMonitor
from src.DM.utils.parallel_processor import ParallelProcessor
from src.DM.utils.api_retry import APIRetryManager, retry_async
from src.DM.utils.smart_cache import SmartCache
from src.DM.utils.market_graph import MarketGraph, create_market_graph_from_items
# Импорт для распределенного анализатора
try:
    from src.DM.utils.distributed_analyzer import distributed_analyze, DistributionConfig
except ImportError:
    distributed_analyze = None
    DistributionConfig = None
    # Логируем, что модуль не найден, если это важно
    # logger.warning("Модуль distributed_analyzer не найден.")


# Настройка логирования
logger = logging.getLogger('market_analyzer')

# Класс для адаптивных параметров анализа
class AdaptiveParameters:
    """
    Адаптивные параметры для оптимизации производительности анализа.
    """
    
    def __init__(self):
        """Инициализирует параметры с значениями по умолчанию."""
        # Параметры параллельной обработки
        self.max_workers = max(1, multiprocessing.cpu_count() - 1)
        self.chunk_size = 50
        self.use_processes_threshold = 1000  # Порог для использования процессов
        
        # Параметры анализа
        self.max_opportunities = 50
        self.max_path_length = 8
        self.min_price = 1.0
        self.max_price = 1000.0
        
        # Параметры кэширования
        self.cache_ttl_base = 3600  # 1 час базовый TTL
        self.cache_volatility_factor = 5.0  # Коэффициент для пересчета TTL на основе волатильности
        
        # Параметры повторных попыток
        self.retry_attempts = 3
        self.retry_backoff_factor = 2.0
        self.retry_max_delay = 30.0
        
        # Счетчики для адаптивной настройки
        self._adjustment_counts = defaultdict(int)
        self._parameter_history = defaultdict(list)
        
        # Пределы для адаптивных параметров
        self._limits = {
            'max_workers': (1, multiprocessing.cpu_count() * 2),
            'chunk_size': (10, 500),
            'cache_ttl_base': (60, 86400),  # от 1 минуты до 24 часов
            'retry_attempts': (1, 10)
        }
        
        logger.info(f"AdaptiveParameters инициализированы: max_workers={self.max_workers}, chunk_size={self.chunk_size}")
    
    def adjust(self, metric_name: str, value: float) -> None:
        """
        Адаптивно настраивает параметры на основе метрик производительности.
        
        Args:
            metric_name: Название метрики
            value: Значение метрики
        """
        # Увеличиваем счетчик
        self._adjustment_counts[metric_name] += 1
        
        # Записываем историю значений
        self._parameter_history[metric_name].append(value)
        if len(self._parameter_history[metric_name]) > 10:
            self._parameter_history[metric_name].pop(0)
        
        # Адаптируем параметры на основе метрик
        if metric_name == 'analyze_time' and len(self._parameter_history[metric_name]) >= 3:
            # Если анализ занимает слишком много времени, корректируем параметры
            avg_time = sum(self._parameter_history[metric_name]) / len(self._parameter_history[metric_name])
            
            if avg_time > 20:  # Если анализ занимает больше 20 секунд
                # Увеличиваем количество воркеров или уменьшаем размер чанка
                if self.chunk_size > self._limits['chunk_size'][0]:
                    self.chunk_size = max(self._limits['chunk_size'][0], int(self.chunk_size * 0.8))
                    logger.info(f"Уменьшаем размер чанка до {self.chunk_size} для оптимизации")
                elif self.max_workers < self._limits['max_workers'][1]:
                    self.max_workers = min(self._limits['max_workers'][1], self.max_workers + 1)
                    logger.info(f"Увеличиваем количество воркеров до {self.max_workers} для оптимизации")
            
            elif avg_time < 5:  # Если анализ быстрый (ИСПРАВЛЕНО: было a5)
                # Возвращаем параметры ближе к сбалансированным значениям
                if self.chunk_size < 50:
                    self.chunk_size = min(50, int(self.chunk_size * 1.2))
                    logger.info(f"Увеличиваем размер чанка до {self.chunk_size} для экономии ресурсов")
        
        elif metric_name == 'api_error_rate' and value > 0.1:  # Если частота ошибок API > 10%
            # Увеличиваем количество повторных попыток
            if self.retry_attempts < self._limits['retry_attempts'][1]:
                self.retry_attempts += 1
                logger.info(f"Увеличиваем количество повторных попыток до {self.retry_attempts}")
        
        elif metric_name == 'cache_miss_rate' and value > 0.5:  # Если промахи кэша > 50%
            # Увеличиваем базовое время жизни кэша
            if self.cache_ttl_base < self._limits['cache_ttl_base'][1]:
                self.cache_ttl_base = min(self._limits['cache_ttl_base'][1], 
                                         int(self.cache_ttl_base * 1.5))
                logger.info(f"Увеличиваем базовое TTL кэша до {self.cache_ttl_base} сек.")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает текущие значения параметров и статистику адаптаций.
        
        Returns:
            Словарь с параметрами и статистикой
        """
        return {
            'processing': {
                'max_workers': self.max_workers,
                'chunk_size': self.chunk_size,
                'use_processes_threshold': self.use_processes_threshold
            },
            'analysis': {
                'max_opportunities': self.max_opportunities,
                'max_path_length': self.max_path_length,
                'price_range': [self.min_price, self.max_price]
            },
            'caching': {
                'ttl_base': self.cache_ttl_base,
                'volatility_factor': self.cache_volatility_factor
            },
            'retry': {
                'attempts': self.retry_attempts,
                'backoff_factor': self.retry_backoff_factor,
                'max_delay': self.retry_max_delay
            },
            'adjustments': dict(self._adjustment_counts),
            'metric_history': {k: v for k, v in self._parameter_history.items()}
        }

class MarketAnalyzer:
    """
    Анализатор рыночных данных для поиска арбитражных возможностей.
    
    Предоставляет методы для получения данных о рынке, анализа и поиска
    арбитражных возможностей с использованием различных алгоритмов.
    """
    
    def __init__(self, api_key: Optional[str] = None, api_secret: Optional[str] = None):
        """
        Инициализирует анализатор рынка.
    
    Args:
            api_key: API-ключ для доступа к рыночным данным
            api_secret: API-секрет для доступа к рыночным данным
        """
        self.api_key = api_key
        self.api_secret = api_secret
        
        # Инициализация API-клиента
        self.api = DMarketAPI(
            api_key=api_key or os.environ.get('DMARKET_API_KEY', ''),
            api_secret=api_secret or os.environ.get('DMARKET_API_SECRET', '')
        )
        
        # Внутренние сервисы
        self.cache = CacheManager.get_instance()
        self.params = AdaptiveParameters()
        
        # Настраиваем параллельную обработку
        self.thread_pool = ThreadPoolExecutor(max_workers=self.params.max_workers)
        self.parallel_processor = ParallelProcessor(
            max_workers=self.params.max_workers,
            chunk_size=self.params.chunk_size
        )
        
        # Настраиваем retry-менеджер
        self.retry_manager = APIRetryManager(
            max_retries=self.params.retry_attempts,
            base_delay=1.0,
            max_delay=self.params.retry_max_delay,
            factor=self.params.retry_backoff_factor,
            jitter=True,
            logger=logger
        )
        
        # Привязываем мониторинг производительности
        # Убедимся, что PerformanceMonitor импортирован
        self.performance_monitor = PerformanceMonitor.get_instance()
        self.metrics = self.performance_monitor # Используем одно имя для согласованности
        
        # Статистика работы
        self.success_count = 0
        self.error_count = 0
        self.last_run_time = 0.0
        self.last_result = None
        
        # Семафор для ограничения конкурентных запросов
        self.request_semaphore = asyncio.Semaphore(20)
        
        # Флаг для отслеживания выполнения долгих операций
        self.long_running_operations = {}
        
        logger.info("MarketAnalyzer инициализирован")

    @retry_async(max_retries=3, base_delay=1.0, max_delay=10.0, factor=2.0)
    async def make_api_request_with_retry(self, 
                                     func: Callable, 
                                     *args, 
                                     **kwargs) -> Any:
        """
        Выполняет API-запрос с автоматическими повторными попытками.
        
        Args:
            func: Функция API для вызова
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы
        
    Returns:
            Результат вызова API
            
        Raises:
            APIError: При ошибке API после всех повторных попыток
        """
        start_time = time.time()
        operation_id = str(uuid.uuid4())[:8]
        
        # Регистрируем операцию в списке выполняющихся
        self.long_running_operations[operation_id] = {
            'type': func.__name__,
            'start_time': start_time,
            'status': 'running',
            'progress': 0
        }
        
        try:
            # Используем семафор для ограничения конкурентных запросов
            async with self.request_semaphore:
                try:
                    result = await func(*args, **kwargs)
                    
                    # Обновляем статистику
                    duration = time.time() - start_time
                    self.metrics.record_time(f"api_call.{func.__name__}", duration, {'success': True})
                    
                    # Обновляем статус операции
                    self.long_running_operations[operation_id]['status'] = 'completed'
                    self.long_running_operations[operation_id]['duration'] = duration
                    
                    return result
                    
                except Exception as e:
                    # Обновляем статистику ошибок
                    duration = time.time() - start_time
                    self.metrics.record_time(f"api_call.{func.__name__}", duration, {'success': False, 'error': str(e)})
                    
                    # Обновляем статус операции
                    self.long_running_operations[operation_id]['status'] = 'error'
                    self.long_running_operations[operation_id]['error'] = str(e)
                    
                    # Решаем, повторять ли запрос
                    if isinstance(e, (RateLimitError, NetworkError)):
                        # Это ошибки, которые можно повторить
                        logger.warning(f"Повторяемая ошибка API: {str(e)}")
                        
                        # Адаптируем параметры на основе ошибок API
                        self.params.adjust('api_error_rate', 1.0)
                        
                        raise  # Позволяем декоратору retry_async обработать повтор
                    elif isinstance(e, AuthenticationError):
                        # Проблемы с аутентификацией, повторный запрос не поможет
                        logger.error(f"Ошибка аутентификации: {str(e)}")
                        raise
                    else:
                        # Другие ошибки
                        logger.error(f"Ошибка API: {str(e)}")
                        raise
        finally:
            # Через 5 минут удаляем информацию о завершенной операции
            asyncio.create_task(self._cleanup_operation(operation_id, 300))
    
    async def _cleanup_operation(self, operation_id: str, delay: int) -> None:
        """Очищает информацию о завершенной операции через указанное время"""
        await asyncio.sleep(delay)
        if operation_id in self.long_running_operations:
            del self.long_running_operations[operation_id]

    def calculate_price_volatility(self, items: List[Dict[str, Any]]) -> float:
        """
        Рассчитывает волатильность цен для коллекции предметов.
        
        Args:
            items: Список предметов с рынка
            
        Returns:
            Процент волатильности (стандартное отклонение / среднее * 100)
        """
        if not items:
            return 0.0
            
        # Извлекаем цены
        prices = []
        for item in items:
            price = 0.0
            if isinstance(item.get('price'), dict):
                price = float(item['price'].get('USD', 0))
            elif hasattr(item, 'prices') and isinstance(item.prices, dict):
                price = float(item.prices.get('USD', 0))
                
            if price > 0:
                prices.append(price)
                
        if not prices:
            return 0.0
            
        # Рассчитываем стандартное отклонение и коэффициент вариации
        mean = sum(prices) / len(prices)
        variance = sum((p - mean) ** 2 for p in prices) / len(prices)
        std_dev = math.sqrt(variance)
        
        # Коэффициент вариации (CV) как мера волатильности
        cv = (std_dev / mean) * 100 if mean > 0 else 0
        
        return min(100.0, cv)  # Ограничиваем максимальное значение
    
    async def get_market_data(
        self, 
        game_id: str = 'a8db',  # CS2 по умолчанию
        limit: int = 500,
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        categories: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Получает данные о предметах на рынке.
        
        Args:
            game_id: Идентификатор игры
            limit: Максимальное количество предметов
            price_from: Минимальная цена предмета
            price_to: Максимальная цена предмета
            categories: Список категорий предметов
            force_refresh: Принудительное обновление данных
            
        Returns:
            Список предметов с рынка
        """
        try:
            # Формируем ключ кэша
            cache_key = f"market_items_{game_id}_{limit}"
            if price_from is not None:
                cache_key += f"_from{price_from}"
            if price_to is not None:
                cache_key += f"_to{price_to}"
            if categories:
                cache_key += f"_cats{'_'.join(categories)}"
            
            # Проверяем кэш, если не требуется принудительное обновление
            if not force_refresh:
                cached_data = self.cache.get(cache_key)
                if cached_data:
                    logger.info(f"Данные о рынке получены из кэша, {len(cached_data)} предметов")
                    
                    # Обновляем метрики кэша
                    self.params.adjust('cache_miss_rate', 0.0)
                    
                    return cached_data
                else:
                    # Записываем промах кэша
                    self.params.adjust('cache_miss_rate', 1.0)
            
            # Запускаем и измеряем время выполнения
            start_time = time.time()
            
            # Создаем функцию для получения страницы данных
            async def fetch_page(page):
                offset = page * 100  # Стандартный размер страницы API
                try:
                    response = await self.make_api_request_with_retry(
                        self.api.get_market_items_async,
                        game_id=game_id,
                        limit=min(100, limit - offset),  # Не запрашиваем больше, чем нужно
                        offset=offset,
                        currency='USD'
                    )
                    
                    # Логируем количество полученных предметов
                    items = response.get('items', [])
                    logger.debug(f"Получено {len(items)} предметов с offset={offset}")
                    
                    # Фильтруем по цене
                    if price_from is not None or price_to is not None:
                        filtered_items = []
                        for item in items:
                            item_price = float(item.get('price', {}).get('USD', 0))
                            if (price_from is None or item_price >= price_from) and \
                               (price_to is None or item_price <= price_to):
                                filtered_items.append(item)
                        items = filtered_items
                    
                    # Фильтруем по категориям
                    if categories:
                        items = [item for item in items if item.get('category') in categories]
                    
                    # Обновляем прогресс операции
                    for op_id, op_info in self.long_running_operations.items():
                        if op_info['type'] == 'get_market_items_async' and op_info['status'] == 'running':
                            op_info['progress'] = min(100, int((offset + len(items)) / limit * 100))
                    
                    return items
                except Exception as e:
                    logger.error(f"Ошибка при получении страницы {page}: {str(e)}")
                    return []
            
            # Определяем количество страниц и запрашиваем их параллельно
            num_pages = (limit + 99) // 100  # Округление вверх
            logger.info(f"Запрашиваем {num_pages} страниц(ы) по 100 предметов")
            
            # Используем ParallelProcessor для эффективной обработки
            page_tasks = [fetch_page(page) for page in range(num_pages)]
            all_pages_results = await asyncio.gather(*page_tasks)
            
            # Объединяем результаты и ограничиваем количество
            market_items = []
            for page_items in all_pages_results:
                market_items.extend(page_items)
            
            if len(market_items) > limit:
                market_items = market_items[:limit]
            
            # Рассчитываем волатильность для динамического TTL кэша
            volatility = self.calculate_price_volatility(market_items)
            cache_ttl = int(self.params.cache_ttl_base / (1 + volatility / self.params.cache_volatility_factor))
            
            # Сохраняем в кэш с динамическим TTL
            self.cache.set(cache_key, market_items, data_type='market_items', ttl=cache_ttl)
            logger.debug(f"Данные сохранены в кэш с TTL {cache_ttl}с (волатильность: {volatility:.2f}%)")
            
            # Обновляем метрики
            duration = time.time() - start_time
            self.metrics.record_time("get_market_data", duration, {
                'game_id': game_id, 
                'items_count': len(market_items),
                'volatility': volatility
            })
            
            # Адаптируем параметры на основе времени выполнения
            self.params.adjust('analyze_time', duration)
            
            return market_items
        
        except Exception as e:
            logger.error(f"Ошибка при получении данных о рынке: {str(e)}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")
            self.error_count += 1
            return []

    async def analyze_market_parallel(
        self, 
        market_items: List[Dict[str, Any]], 
        chunk_size: int = 50,
        budget: float = 100.0,
        min_profit: float = 1.0,
        max_opportunities: int = 50,
        use_processes: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Анализирует данные рынка в параллельном режиме для поиска арбитражных возможностей.
        
        Улучшенная версия с отказоустойчивостью, адаптивной обработкой и динамическим распределением нагрузки.
        
        Args:
            market_items: Список предметов с рынка
            chunk_size: Размер чанка для параллельной обработки
            budget: Бюджет для анализа
            min_profit: Минимальная прибыль в процентах
            max_opportunities: Максимальное количество возможностей
            use_processes: Использовать процессы вместо потоков
            
        Returns:
            Список арбитражных возможностей
        """
        if not market_items:
            logger.warning("Пустой список предметов для анализа рынка")
            return []
        
        # Создаем уникальный идентификатор операции для отслеживания
        operation_id = str(uuid.uuid4())[:8]
        self.long_running_operations[operation_id] = {
            'type': 'analyze_market_parallel',
            'start_time': time.time(),
            'status': 'running',
            'progress': 0,
            'params': {
                'items_count': len(market_items),
                'chunk_size': chunk_size,
                'budget': budget,
                'min_profit': min_profit
            }
        }
        
        # Замеряем время
        start_time = time.time()
        
        try:
            # Валидируем данные перед обработкой - асинхронно
            logger.info(f"Валидация {len(market_items)} предметов перед анализом")
            valid_items = await self._validate_market_data_async(market_items)
            
            if not valid_items:
                logger.warning("Нет валидных предметов для анализа")
                self._update_operation_status(operation_id, 'completed', 100, "Нет валидных предметов для анализа")
                return []
            
            # Обновляем статус операции
            self._update_operation_status(operation_id, 'running', 20, f"Валидировано {len(valid_items)} предметов")
            self.long_running_operations[operation_id]['valid_items'] = len(valid_items)
            
            # Определяем оптимальные параметры параллельной обработки
            cpu_count = os.cpu_count() or 4
            # Для CPU-bound задач оптимально использовать N-1 ядер, для I/O-bound - больше
            optimal_workers = max(2, cpu_count - 1) if use_processes else max(4, cpu_count * 2)
            
            # Адаптивный размер чанка: меньшие чанки для большого числа элементов
            item_count = len(valid_items)
            if item_count > 5000:
                adaptive_chunk_size = max(10, min(chunk_size, item_count // (optimal_workers * 4)))
            elif item_count > 1000:
                adaptive_chunk_size = max(20, min(chunk_size, item_count // (optimal_workers * 2)))
            else:
                adaptive_chunk_size = min(chunk_size, max(10, item_count // optimal_workers))
            
            logger.info(f"Оптимизированные параметры: {optimal_workers} воркеров, размер чанка: {adaptive_chunk_size}")
            
            # Определяем стратегию обработки в зависимости от размера данных и доступных ресурсов
            large_dataset = item_count > 2000
            complex_calculation = budget > 1000 or min_profit < 0.5
            
            # Для очень больших наборов данных или сложных расчетов используем distributed_analyzer
            if (large_dataset or complex_calculation) and distributed_analyze: # Проверяем, что функция импортирована
                logger.info(f"Переключение на распределенный анализ для {item_count} предметов (большой набор данных)")
                try:
                    # Убираем повторный импорт внутри метода
                    # from utils.distributed_analyzer import distributed_analyze

                    self._update_operation_status(
                        operation_id,
                        'running',
                        30,
                        "Запуск распределенного анализа для оптимальной производительности"
                    )

                    opportunities = await distributed_analyze(
                        market_items=valid_items,
                        budget=budget,
                        min_profit=min_profit,
                        max_workers=optimal_workers,
                        use_processes=use_processes
                    )

                    duration = time.time() - start_time
                    logger.info(f"Распределенный анализ завершен за {duration:.2f}с, найдено {len(opportunities)} возможностей")

                    # Записываем метрики и обновляем статус
                    self.metrics.record_time('analyze_market_distributed', duration, {
                        'items_count': len(valid_items),
                        'opportunities_found': len(opportunities),
                        'workers': optimal_workers
                    })

                    self._update_operation_status(
                        operation_id,
                        'completed',
                        100,
                        f"Найдено {len(opportunities)} возможностей (распределенный анализ)"
                    )
                    self.long_running_operations[operation_id]['opportunities_found'] = len(opportunities)
                    self.long_running_operations[operation_id]['duration'] = duration

                    return opportunities[:max_opportunities]

                except Exception as dist_err: # Ловим ошибку выполнения, а не ImportError
                    logger.warning(f"Ошибка при выполнении распределенного анализа: {dist_err}. Используем стандартный параллельный анализ.")
                    # Продолжаем со стандартным параллельным анализом ниже
            # else: # Убираем else, чтобы код выполнялся, если distributed_analyze недоступен или не выбран

            # Инициализируем процессор для параллельной обработки (этот блок выполнится, если распределенный анализ не использовался)
            processor = ParallelProcessor(
                max_workers=optimal_workers,
                use_processes=use_processes,
                chunk_size=adaptive_chunk_size,
                timeout=180  # Увеличенный таймаут для сложных расчетов
            )
            
            # Подготавливаем данные для анализа
            exchange_data = self._prepare_exchange_data(valid_items)
            
            self._update_operation_status(
                operation_id, 
                'running', 
                40, 
                f"Запуск параллельного анализа с {optimal_workers} воркерами"
            )
            
            # Функция для обработки чанка данных с улучшенной обработкой ошибок
            def process_chunk(chunk_items):
                try:
                    # Создаем локальные данные для чанка
                    chunk_exchange_data = self._prepare_exchange_data(chunk_items)
                    
                    # Используем оптимизированный алгоритм поиска арбитража
                    opportunities = find_arbitrage_advanced(
                        chunk_exchange_data, 
                        budget=budget,
                        min_profit=min_profit,
                        # Добавляем дополнительные параметры для более точного поиска
                        min_liquidity=0.2,  # Минимальная ликвидность
                        max_cycle_length=6  # Оптимальная длина цикла для эффективного поиска
                    )
                    
                    # Добавляем дополнительную информацию к каждой возможности
                    timestamp = datetime.now().isoformat()
                    for opp in opportunities:
                        opp['timestamp'] = timestamp
                        opp['source'] = 'parallel_analyzer'
                        # Добавляем хеш для идентификации уникальных возможностей
                        path_str = "->".join(str(node) for node in opp['path'])
                        opp['hash'] = hashlib.md5(path_str.encode()).hexdigest()[:10]
                    
                    return opportunities
                    
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"Ошибка при обработке чанка: {error_msg}")
                    if "memory" in error_msg.lower():
                        logger.critical("Недостаточно памяти для обработки чанка, уменьшите размер чанка")
                    logger.debug(traceback.format_exc())
                    return []  # Возвращаем пустой список при ошибке
            
            # Разделяем данные на чанки оптимального размера
            chunks = [valid_items[i:i+adaptive_chunk_size] for i in range(0, len(valid_items), adaptive_chunk_size)]
            chunks_count = len(chunks)
            
            logger.info(f"Данные разбиты на {chunks_count} чанков по {adaptive_chunk_size} предметов")
            
            # Используем ParallelProcessor для параллельной обработки с мониторингом прогресса
            if chunks_count > 20 or len(valid_items) > 1000:
                # Для больших объемов данных используем асинхронную обработку
                
                # Создаем callback для обновления прогресса
                async def progress_callback(processed, total):
                    progress = int(40 + (processed / total) * 50)
                    self._update_operation_status(
                        operation_id, 
                        'running', 
                        progress, 
                        f"Обработано {processed}/{total} чанков"
                    )
                
                # Запускаем асинхронную обработку с отслеживанием прогресса
                result_opportunities = await processor.batch_process_async(
                    chunks, 
                    process_chunk,
                    progress_callback=progress_callback  # Это требует доработки ParallelProcessor
                )
            else:
                # Для небольших объемов используем синхронную обработку
                result_opportunities = processor.batch_process(chunks, process_chunk)
                
            # Объединяем результаты из всех чанков и удаляем дубликаты
            all_opportunities = []
            opportunity_hashes = set()
            
            for chunk_results in result_opportunities:
                for opp in chunk_results:
                    # Пропускаем дубликаты на основе хеша
                    opp_hash = opp.get('hash')
                    if opp_hash and opp_hash not in opportunity_hashes:
                        all_opportunities.append(opp)
                        opportunity_hashes.add(opp_hash)
                
            # Сортируем по прибыли и ограничиваем количество
            all_opportunities.sort(key=lambda x: x.get('profit', 0), reverse=True)
            result = all_opportunities[:max_opportunities]
            
            # Метрики и завершение операции
            duration = time.time() - start_time
            opportunities_found = len(result)
            
            logger.info(f"Параллельный анализ завершен за {duration:.2f}с, найдено {opportunities_found} возможностей")
            
            # Записываем метрики
            self.metrics.record_time('analyze_market_parallel', duration, {
                'items_count': len(valid_items),
                'opportunities_found': opportunities_found,
                'workers': optimal_workers,
                'chunk_size': adaptive_chunk_size,
                'chunks_processed': chunks_count
            })
            
            # Обновляем статус операции
            self._update_operation_status(operation_id, 'completed', 100, f"Найдено {opportunities_found} возможностей")
            self.long_running_operations[operation_id]['duration'] = duration
            self.long_running_operations[operation_id]['opportunities_found'] = opportunities_found
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка при параллельном анализе рынка: {str(e)}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")
            
            # Обновляем статус операции при ошибке
            self._update_operation_status(operation_id, 'error', 100, f"Ошибка: {str(e)}")
            
            # Записываем метрику ошибки
            self.metrics.increment('analyze_market_errors')
            
            return []
    
    def _update_operation_status(self, operation_id: str, status: str, progress: int, message: str = ""):
        """
        Вспомогательный метод для обновления статуса длительной операции.
        
        Args:
            operation_id: Идентификатор операции
            status: Статус операции ('running', 'completed', 'error')
            progress: Прогресс выполнения (0-100)
            message: Сообщение о текущем состоянии
        """
        if operation_id in self.long_running_operations:
            self.long_running_operations[operation_id]['status'] = status
            self.long_running_operations[operation_id]['progress'] = progress
            if message:
                self.long_running_operations[operation_id]['message'] = message
            # Добавляем временную метку обновления
            self.long_running_operations[operation_id]['updated_at'] = time.time()

    async def _validate_market_data_async(self, market_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Асинхронно валидирует данные рынка перед анализом.
    
    Args:
        market_items: Список предметов с рынка
        
    Returns:
        Отфильтрованный список валидных предметов
    """
        # Функция для валидации одного предмета
        def validate_item(item):
            # Базовая валидация структуры предмета
            if not isinstance(item, dict):
                return False
                
            # Проверяем наличие обязательных полей
            if not item.get('itemId'):
                return False
                
        # Проверяем актуальность (не старше 1 часа)
            current_time = time.time()
        update_time = item.get('updateTime', current_time)
        if isinstance(update_time, str):
            try:
                update_time = datetime.fromisoformat(update_time.replace('Z', '+00:00')).timestamp()
            except (ValueError, TypeError):
                update_time = current_time
        
        if (current_time - update_time) > 3600:
                return False
            
        # Проверяем ликвидность (минимум 5 продаж в день)
        sales_per_day = 0
        if isinstance(item.get('extra'), dict):
                sales_per_day = item['extra'].get('salesPerDay', 0)
        elif hasattr(item, 'liquidity'):
                sales_per_day = item.liquidity
            
        if sales_per_day < self.params.min_liquidity:
                return False
                
            # Проверяем наличие цен
        buy_price = 0.0
        sell_price = 0.0
            
            # Пытаемся извлечь цены
        if isinstance(item.get('price'), dict):
                buy_price = float(item['price'].get('USD', 0))
        elif hasattr(item, 'prices') and isinstance(item.prices, dict):
                buy_price = float(item.prices.get('USD', 0))
            
        if isinstance(item.get('suggestedPrice'), dict):
                sell_price = float(item['suggestedPrice'].get('USD', 0))
        elif hasattr(item, 'suggested_prices') and isinstance(item.suggested_prices, dict):
                sell_price = float(item.suggested_prices.get('USD', 0))
        
        if buy_price <= 0 or sell_price <= 0:
                return False
        
            # Проверяем, что прибыль превышает минимальный порог
        profit_percent = ((sell_price - buy_price) / buy_price) * 100
        if profit_percent < self.params.min_profit:
                return False
                
        return True
        
        # Валидируем все предметы параллельно с использованием потоков
        with ThreadPoolExecutor(max_workers=self.params.max_workers) as executor:
            loop = asyncio.get_event_loop()
            validation_tasks = [
                loop.run_in_executor(executor, validate_item, item)
                for item in market_items
            ]
            
            validation_results = await asyncio.gather(*validation_tasks)
            
            # Фильтруем предметы, которые прошли валидацию
            valid_items = [
                item for item, is_valid in zip(market_items, validation_results)
                if is_valid
            ]
        logger.info(f"Валидация данных: {len(valid_items)} из {len(market_items)} предметов прошли валидацию")
        return valid_items

    def _prepare_exchange_data(self, market_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Преобразует данные о предметах в формат для поиска арбитража.
    
    Args:
            market_items: Список предметов с рынка
        
    Returns:
            Словарь обменных курсов в формате {from_item: {to_item: {rate, liquidity, fee}}}
        """
        exchange_data = {}
        
        # USD как базовая валюта
        exchange_data['USD'] = {}
        
        # Добавляем предметы и курсы обмена
        for item in market_items:
            item_id = item.get('itemId', '')
            if not item_id:
                continue
            
            # Получаем цены в USD
            buy_price = 0.0
            sell_price = 0.0
            
            # Извлекаем цены покупки и продажи
            if isinstance(item.get('price'), dict):
                buy_price = float(item['price'].get('USD', 0))
            elif hasattr(item, 'prices') and isinstance(item.prices, dict):
                buy_price = float(item.prices.get('USD', 0))
            
            if isinstance(item.get('suggestedPrice'), dict):
                sell_price = float(item['suggestedPrice'].get('USD', 0))
            elif hasattr(item, 'suggested_prices') and isinstance(item.suggested_prices, dict):
                sell_price = float(item.suggested_prices.get('USD', 0))
            
            if buy_price <= 0 or sell_price <= 0:
                continue
            
            # Получаем ликвидность
            liquidity = 0.0
            if isinstance(item.get('extra'), dict):
                liquidity = float(item['extra'].get('salesPerDay', 0))
            elif hasattr(item, 'liquidity'):
                liquidity = float(item.liquidity)
            
            # Добавляем курс USD -> item (покупка предмета)
            exchange_data['USD'][item_id] = {
                'rate': 1 / buy_price,  # Количество предметов за 1 USD
                'liquidity': liquidity,
                'fee': 0.05  # 5% комиссия маркетплейса
            }
            
            # Добавляем курс item -> USD (продажа предмета)
            if item_id not in exchange_data:
                exchange_data[item_id] = {}
            
            exchange_data[item_id]['USD'] = {
                'rate': sell_price,  # Количество USD за 1 предмет
                'liquidity': liquidity,
                'fee': 0.05  # 5% комиссия маркетплейса
            }
        
        return exchange_data
    
    async def analyze_market_distributed(
        self, 
        market_items: List[Dict[str, Any]], 
        budget: float = 100.0,
        min_profit: float = 1.0,
        max_opportunities: Optional[int] = None,
        use_processes: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Анализирует рыночные данные с использованием распределенной обработки.
        
        Этот метод использует модуль distributed_analyzer для более эффективного
        распараллеливания анализа на многоядерных системах.
    
        Args:
            market_items: Список предметов с рынка
            budget: Бюджет для анализа
            min_profit: Минимальная прибыль в процентах
            max_opportunities: Максимальное количество возможностей
            use_processes: Использовать процессы вместо потоков
        
        Returns:
            Список арбитражных возможностей
        """
        if not market_items:
            return []
        
        # Используем параметры по умолчанию, если не указаны
        max_opportunities = max_opportunities or self.params.max_opportunities
        
        # Замеряем время
        start_time = time.time()
        
        try:
            # Импортируем модуль распределенного анализа - УЖЕ ИМПОРТИРОВАН В НАЧАЛЕ ФАЙЛА
            # from utils.distributed_analyzer import distributed_analyze, DistributionConfig
            if not distributed_analyze or not DistributionConfig:
                 raise ImportError("Модуль distributed_analyzer недоступен.")

            # Выполняем распределенный анализ
            logger.info(f"Запуск распределенного анализа для {len(market_items)} предметов")
            
            opportunities = await distributed_analyze(
                market_items=market_items,
                budget=budget,
                min_profit=min_profit,
                max_workers=self.params.max_workers,
                use_processes=use_processes
            )
            
            # Сортируем по прибыльности и ограничиваем количество
            opportunities = sorted(opportunities, key=lambda x: x['profit'], reverse=True)
            if max_opportunities > 0:
                opportunities = opportunities[:max_opportunities]
            
            # Добавляем время обнаружения
            for opp in opportunities:
                if 'detected_at' not in opp:
                    opp['detected_at'] = datetime.now().isoformat()
            
            # Запись метрик
            duration = time.time() - start_time
            
            if self.performance_monitor:
                self.performance_monitor.record_execution_time("distributed_analysis", duration, {
                    'items_count': len(market_items),
                    'opportunities_found': len(opportunities)
                })
            
            logger.info(f"Найдено {len(opportunities)} арбитражных возможностей за {duration:.2f} сек.")
            
            # Регистрируем успешную обработку
            self.success_count += 1
            self.last_run_time = time.time()
            
            return opportunities
            
        except ImportError:
            logger.warning("Модуль distributed_analyzer не найден, используем стандартный метод")
            return await self.analyze_market_parallel(
                market_items=market_items,
                budget=budget,
                min_profit=min_profit,
                max_opportunities=max_opportunities
            )
        except Exception as e:
            logger.error(f"Ошибка при распределенном анализе: {str(e)}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")
            self.error_count += 1
            
            # В случае ошибки пробуем использовать обычный метод
            logger.info("Переключение на стандартный метод анализа")
            return await self.analyze_market_parallel(
                market_items=market_items,
                budget=budget,
                min_profit=min_profit,
                max_opportunities=max_opportunities
            )

    async def find_best_opportunities(
        self, 
        game_id: str = 'a8db', 
        limit: int = 500, 
        budget: float = 100.0,
        min_profit: float = 1.0,
        force_refresh: bool = False,
        use_distributed: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Находит лучшие арбитражные возможности.
        
        Args:
            game_id: Идентификатор игры
            limit: Максимальное количество предметов для анализа
            budget: Бюджет для анализа
            min_profit: Минимальная прибыль в процентах
            force_refresh: Принудительное обновление данных
            use_distributed: Использовать распределенный анализ
            
        Returns:
            Список арбитражных возможностей
        """
        try:
            # Проверяем кэш для арбитражных возможностей
            cache_key = f"arbitrage_opportunities_{game_id}_{budget}_{min_profit}"
            
            if not force_refresh:
                cached_results = self.cache.get(cache_key)
                if cached_results:
                    logger.info(f"Арбитражные возможности получены из кэша, найдено {len(cached_results)}")
                    return cached_results
            
            # Получаем данные о рынке
            market_items = await self.get_market_data(
                game_id=game_id,
                limit=limit,
                price_from=self.params.min_price,
                price_to=self.params.max_price,
                force_refresh=force_refresh
            )
            
            if not market_items:
                logger.warning("Не удалось получить данные о рынке")
                return []
    
            # Создаем идентификатор для отслеживания операции
            operation_id = str(uuid.uuid4())[:8]
            self.long_running_operations[operation_id] = {
                'type': 'find_best_opportunities',
                'start_time': time.time(),
                'status': 'running',
                'progress': 0,
                'params': {
                    'game_id': game_id,
                    'limit': limit,
                    'budget': budget,
                    'min_profit': min_profit
                }
            }
            
            try:
                # Анализируем рынок с использованием выбранного метода
                if use_distributed:
                    self.long_running_operations[operation_id]['method'] = 'distributed'
                    opportunities = await self.analyze_market_distributed(
                        market_items=market_items,
                        budget=budget,
                        min_profit=min_profit
                    )
                else:
                    self.long_running_operations[operation_id]['method'] = 'parallel'
                    opportunities = await self.analyze_market_parallel(
                        market_items=market_items,
                        budget=budget,
                        min_profit=min_profit
                    )
                
                # Обновляем статус операции
                self.long_running_operations[operation_id]['status'] = 'completed'
                self.long_running_operations[operation_id]['opportunities_found'] = len(opportunities)
                
                # Сохраняем результаты в кэш
                if opportunities:
                    # Используем адаптивное TTL на основе волатильности рынка
                    volatility = self.calculate_price_volatility(market_items)
                    cache_ttl = int(self.params.cache_ttl_base / (1 + volatility / 10))  # Более агрессивная адаптация для результатов
                    
                    self.cache.set(
                        cache_key,
                        opportunities,
                        data_type='arbitrage',
                        ttl=cache_ttl
                    )
                    
                    logger.info(f"Результаты сохранены в кэш с TTL {cache_ttl}с")
                    
                    # Сохраняем лучшие возможности для истории
                    self.last_result = {
                        'timestamp': time.time(),
                        'game_id': game_id,
                        'opportunities_count': len(opportunities),
                        'max_profit': opportunities[0]['profit'] if opportunities else 0,
                        'method': 'distributed' if use_distributed else 'parallel',
                        'volatility': volatility
                    }
                
                return opportunities
                
            except Exception as analysis_error:
                logger.error(f"Ошибка при анализе рынка: {str(analysis_error)}")
                logger.debug(f"Трассировка: {traceback.format_exc()}")
                
                # Обновляем статус операции
                self.long_running_operations[operation_id]['status'] = 'error'
                self.long_running_operations[operation_id]['error'] = str(analysis_error)
                
                return []
                
        except Exception as e:
            logger.error(f"Ошибка при поиске арбитражных возможностей: {str(e)}")
            logger.debug(f"Трассировка: {traceback.format_exc()}")
            self.error_count += 1
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Возвращает статистику работы анализатора.
        
        Returns:
            Словарь со статистикой
        """
        return {
            'success_count': self.success_count,
            'error_count': self.error_count,
            'last_run_time': datetime.fromtimestamp(self.last_run_time).isoformat() if self.last_run_time else None,
            'last_result': self.last_result,
            'params': self.params.get_stats(),
            'cache_stats': self.cache.get_stats(),
            'metrics': self.metrics.get_stats()
        }
    
    def close(self):
        """Закрывает ресурсы анализатора."""
        self.thread_pool.shutdown(wait=False)
        logger.info("Анализатор рынка закрыт")

# Глобальный экземпляр анализатора
_analyzer: Optional[MarketAnalyzer] = None

def get_analyzer() -> MarketAnalyzer:
    """
    Получает глобальный экземпляр анализатора рынка.
    
    Returns:
        MarketAnalyzer: Экземпляр анализатора
    """
    global _analyzer
    if _analyzer is None:
        _analyzer = MarketAnalyzer()
    return _analyzer

async def find_arbitrage_opportunities(
    game_id: str = 'a8db',
    limit: int = 500,
    budget: float = 100.0,
    min_profit: float = 1.0,
    force_refresh: bool = False,
    use_distributed: bool = True
) -> List[Dict[str, Any]]:
    """
    Находит арбитражные возможности на рынке.
    
    Args:
        game_id: Идентификатор игры
        limit: Максимальное количество предметов
        budget: Бюджет для анализа
        min_profit: Минимальная прибыль
        force_refresh: Принудительное обновление данных
        use_distributed: Использовать распределенный анализ
        
    Returns:
        Список арбитражных возможностей
    """
    analyzer = get_analyzer()
    return await analyzer.find_best_opportunities(
        game_id=game_id,
        limit=limit,
        budget=budget,
        min_profit=min_profit,
        force_refresh=force_refresh,
        use_distributed=use_distributed
    )

async def analyze_historical_trends(item_id: str, days: int = 30) -> Dict[str, Any]:
    """
    Анализирует исторические тренды цен для предмета.
    
    Args:
        item_id: Идентификатор предмета
        days: Количество дней для анализа
        
    Returns:
        Словарь с результатами анализа
    """
    # Получаем исторические данные
    historical_data = get_historical_prices(item_id, days)
    
    if not historical_data:
        return {
            "status": "error",
            "message": "Недостаточно исторических данных"
        }
    
    # Рассчитываем базовые метрики
    prices = [entry['price'] for entry in historical_data]
    dates = [entry['date'] for entry in historical_data]
    
    avg_price = sum(prices) / len(prices)
    max_price = max(prices)
    min_price = min(prices)
    volatility = calculate_volatility(prices)
    
    # Определяем тренд
    if len(prices) >= 2:
        trend = "rising" if prices[-1] > prices[0] else "falling"
    else:
        trend = "unknown"
    
    # Прогнозируем будущую цену
    predicted_price = predict_future_price(historical_data)
    
    return {
        "status": "success",
        "item_id": item_id,
        "avg_price": avg_price,
        "max_price": max_price,
        "min_price": min_price,
        "volatility": volatility,
        "trend": trend,
        "predicted_price": predicted_price,
        "data_points": len(historical_data)
    }

def calculate_volatility(prices: List[float]) -> float:
    """
    Рассчитывает волатильность цен.
    
    Args:
        prices: Список цен
        
    Returns:
        Значение волатильности
    """
    if len(prices) < 2:
        return 0.0
    
    # Стандартное отклонение в процентах
    mean = sum(prices) / len(prices)
    variance = sum((price - mean) ** 2 for price in prices) / len(prices)
    std_dev = variance ** 0.5
    
    return (std_dev / mean) * 100

def predict_future_price(historical_data: List[Dict[str, Any]]) -> float:
    """
    Прогнозирует будущую цену на основе исторических данных.
    
    Args:
        historical_data: Список исторических данных о цене
        
    Returns:
        Прогнозируемая цена
    """
    if len(historical_data) < 5:
        # Недостаточно данных для прогноза, возвращаем последнюю цену
        return historical_data[-1]['price']
    
    # Простой алгоритм линейной регрессии
    x = list(range(len(historical_data)))
    y = [entry['price'] for entry in historical_data]
    
    # Расчет коэффициентов линейной регрессии
    n = len(x)
    sum_x = sum(x)
    sum_y = sum(y)
    sum_xy = sum(xi * yi for xi, yi in zip(x, y))
    sum_xx = sum(xi ** 2 for xi in x)
    
    # Формула для коэффициента наклона (slope)
    slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x ** 2)
    
    # Формула для свободного члена (intercept)
    intercept = (sum_y - slope * sum_x) / n
    
    # Прогноз на следующий период
    next_period = len(x)
    predicted_price = slope * next_period + intercept
    
    return max(0.01, predicted_price)  # Цена не может быть отрицательной