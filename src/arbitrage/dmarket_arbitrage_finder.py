"""
Модуль интеграции алгоритма Беллмана-Форда с API DMarket для поиска выгодных скинов.

Этот модуль обеспечивает анализ рынка DMarket для поиска возможностей покупки и продажи
скинов с прибылью, используя алгоритм Беллмана-Форда для обнаружения арбитражных циклов.
"""

import asyncio
import logging
import time
import hashlib
import json
import multiprocessing
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Set, Union, Callable
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import math

# Импортируем необходимые компоненты для интеграции
from api_wrapper import DMarketAPI, RateLimitError, NetworkError
from bellman_ford import (
    create_graph, find_arbitrage, ArbitrageResult, Edge,
    filter_arbitrage_opportunities, find_arbitrage_advanced
)
from utils.market_analyzer import AdaptiveParameters
from utils.caching import cache_result
from utils.market_graph import create_market_graph_from_items, MarketGraph
from utils.parallel_processor import ParallelProcessor
from utils.performance_monitor import PerformanceMonitor
from utils.smart_cache import SmartCache
from utils.api_retry import retry_async
from utils.performance_metrics import MetricsCollector
from ml_predictor import MLPredictor  # Добавляем импорт предиктора для ML-интеграции

# Настройка логирования
logger = logging.getLogger('dmarket_arbitrage_finder')


class ArbitrageFinderParams:
    """
    Параметры для настройки поиска арбитражных возможностей.
    """
    def __init__(self, 
                 min_profit: float = 1.0,
                 max_profit: float = 100.0,
                 min_price: float = 1.0,
                 max_price: float = 1000.0,
                 base_fee: float = 0.07, 
                 high_demand_fee: float = 0.02,
                 min_liquidity: float = 1.0,
                 max_results: int = 20,
                 mode: str = "balance_boost"):
        """
        Инициализирует параметры поиска арбитража.
        
        Args:
            min_profit: Минимальная прибыль в USD
            max_profit: Максимальная прибыль в USD
            min_price: Минимальная цена предмета
            max_price: Максимальная цена предмета
            base_fee: Базовая комиссия площадки (в процентах/100)
            high_demand_fee: Сниженная комиссия для предметов высокого спроса
            min_liquidity: Минимальная ликвидность предмета
            max_results: Максимальное количество результатов
            mode: Режим работы - "balance_boost", "medium_trader" или "trade_pro"
        """
        self.min_profit = min_profit
        self.max_profit = max_profit
        self.min_price = min_price
        self.max_price = max_price
        self.base_fee = base_fee
        self.high_demand_fee = high_demand_fee
        self.min_liquidity = min_liquidity
        self.max_results = max_results
        self.mode = mode
        
        # Настройка параметров в зависимости от режима
        self._adjust_params_for_mode()
    
    def _adjust_params_for_mode(self):
        """
        Корректирует параметры поиска в зависимости от выбранного режима работы.
        """
        if self.mode == "balance_boost":
            # Режим "Разгон баланса" ($1-5)
            self.min_profit = 1.0
            self.max_profit = 5.0
            self.min_price = 5.0
            self.max_price = 100.0
            # Повышаем требования к ликвидности для быстрых сделок
            self.min_liquidity = 3.0
            
        elif self.mode == "medium_trader":
            # Режим "Средний трейдер" ($5-20)
            self.min_profit = 5.0
            self.max_profit = 20.0
            self.min_price = 20.0
            self.max_price = 300.0
            self.min_liquidity = 2.0
            
        elif self.mode == "trade_pro":
            # Режим "Trade Pro" ($20-100)
            self.min_profit = 20.0
            self.max_profit = 100.0
            self.min_price = 50.0
            self.max_price = 1000.0
            # Снижаем требования к ликвидности для редких предметов
            self.min_liquidity = 1.0


class DMarketArbitrageFinder:
    """
    Класс для поиска арбитражных возможностей на платформе DMarket.
    
    Интегрирует API DMarket с алгоритмом Беллмана-Форда для поиска прибыльных 
    возможностей купли-продажи скинов.
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None, use_parallel: bool = True, use_ml: bool = False):
        """
        Инициализирует объект DMarketArbitrageFinder.
        
        Args:
            api_key: API ключ для доступа к DMarket API
            api_secret: Секретный ключ для подписи запросов (опционально)
            use_parallel: Использовать ли параллельную обработку данных
            use_ml: Использовать ли машинное обучение для прогнозирования
        """
        self.api = DMarketAPI(api_key, api_secret)
        self.params = AdaptiveParameters()
        self.use_parallel = use_parallel
        self.use_ml = use_ml
        
        # Инициализация улучшенной системы кэширования
        self.smart_cache = SmartCache(
            ttl_base=self.params.cache_ttl_base,
            volatility_factor=self.params.cache_volatility_factor
        )
        
        # Инициализация мониторинга производительности
        self.perf_monitor = PerformanceMonitor('dmarket_arbitrage_finder')
        self.metrics = MetricsCollector('arbitrage_metrics')
        
        # Инициализация параллельного процессора
        cores = multiprocessing.cpu_count()
        max_workers = max(1, cores - 1)  # Оставляем один ядро свободным
        self.parallel_processor = ParallelProcessor(
            max_workers=max_workers,
            use_processes=False,  # По умолчанию используем потоки
            chunk_size=self.params.chunk_size
        )
        
        # Инициализация ML-предиктора, если включено использование ML
        self.ml_predictor = None
        if use_ml:
            try:
                logger.info("Инициализация ML-предиктора для прогнозирования цен")
                self.ml_predictor = MLPredictor()
            except Exception as e:
                logger.warning(f"Не удалось инициализировать ML-предиктор: {e}")
                self.use_ml = False
        
        self.last_request_time = datetime.now()
        logger.info(f"DMarketArbitrageFinder инициализирован с {max_workers} рабочими потоками")
        logger.info(f"Машинное обучение {'включено' if self.use_ml else 'отключено'}")
    
    async def _respect_rate_limit(self, min_interval: float = 1.0):
        """
        Соблюдает минимальный интервал между запросами к API.
        
        Args:
            min_interval: Минимальный интервал между запросами в секундах
        """
        if self.last_request_time is None:
            self.last_request_time = datetime.now()
            return
        
        # Рассчитываем, сколько времени прошло с последнего запроса
        now = datetime.now()
        elapsed = (now - self.last_request_time).total_seconds()
        
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            logger.debug(f"Соблюдение ограничений API: ожидание {sleep_time:.2f} сек")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = datetime.now()
    
    @retry_async(max_retries=3, factor=2.0, 
                 retry_exceptions=(RateLimitError, NetworkError))
    @cache_result(ttl=300)  # Кэшируем результат на 5 минут
    async def get_market_items(
        self,
        game_id: str = "a8db",  # CS2 по умолчанию
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        price_from: Optional[float] = None,
        price_to: Optional[float] = None,
        title: Optional[str] = None,
        category: Optional[str] = None,
        rarity: Optional[str] = None,
        exterior: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Получает список предметов с рынка DMarket.
        
        Args:
            game_id: Идентификатор игры ('a8db' для CS2, '9a92' для Dota 2)
            limit: Максимальное количество предметов для получения
            offset: Смещение для пагинации
            currency: Валюта для цен
            price_from: Минимальная цена для фильтрации
            price_to: Максимальная цена для фильтрации
            title: Фильтр по названию предмета
            category: Фильтр по категории предмета
            rarity: Фильтр по редкости предмета
            exterior: Фильтр по состоянию предмета (Factory New, Minimal Wear и т.д.)
            
        Returns:
            Список предметов на рынке
        """
        with self.perf_monitor.measure("get_market_items"):
            await self._respect_rate_limit()
            
            logger.info(f"Запрос предметов рынка для {game_id}, лимит: {limit}, смещение: {offset}")
            
            # Создаем хеш запроса для кэширования
            cache_params = {
                "gameId": game_id,
                "limit": limit,
                "offset": offset,
                "currency": currency,
                "priceFrom": price_from,
                "priceTo": price_to,
                "title": title,
                "category": category,
                "rarity": rarity,
                "exterior": exterior
            }
            cache_key = hashlib.md5(json.dumps(cache_params, sort_keys=True).encode()).hexdigest()
            
            # Проверяем кэш
            cached_data = self.smart_cache.get(cache_key)
            if cached_data:
                logger.info(f"Использую кэшированные данные для запроса {game_id}, смещение: {offset}")
                return cached_data
            
            try:
                # Создаем параметры запроса на основе переданных аргументов
                params = {
                    "gameId": game_id,
                    "limit": limit,
                    "offset": offset,
                    "currency": currency,
                    "orderBy": "price",
                    "orderDir": "asc"
                }
                
                # Добавляем опциональные параметры, если они указаны
                if price_from is not None:
                    params["priceFrom"] = price_from
                
                if price_to is not None:
                    params["priceTo"] = price_to
                    
                if title:
                    params["title"] = title
                    
                if category:
                    params["category"] = category
                    
                if rarity:
                    params["rarity"] = rarity
                    
                if exterior:
                    params["exterior"] = exterior
                
                # Выполняем запрос к API с метриками
                start_time = time.time()
                try:
                    response = await self.api.get_market_items_async(**params)
                    request_time = time.time() - start_time
                    self.metrics.record_metric("api_request_time", request_time)
                except Exception as e:
                    self.metrics.record_metric("api_error_rate", 1.0)
                    raise
                    
                # Обрабатываем ответ
                if "objects" in response:
                    items = response["objects"]
                    logger.info(f"Получено {len(items)} предметов")
                    
                    # Сохраняем в кэш с адаптивным TTL на основе волатильности цен
                    volatility = self._calculate_price_volatility(items)
                    ttl = max(60, self.params.cache_ttl_base / (1 + volatility * self.params.cache_volatility_factor))
                    self.smart_cache.put(cache_key, items, ttl=ttl)
                    
                    # Записываем метрики
                    self.metrics.record_metric("items_count", len(items))
                    self.metrics.record_metric("cache_hit_rate", 0.0)
                    
                    return items
                else:
                    logger.warning(f"Некорректный ответ API: {response}")
                    return []
            
            except Exception as e:
                logger.error(f"Ошибка при получении предметов рынка: {e}")
                return []
    
    def _calculate_price_volatility(self, items: List[Dict[str, Any]]) -> float:
        """
        Рассчитывает волатильность цен предметов для определения динамического TTL кэша.
        
        Args:
            items: Список предметов с рынка
            
        Returns:
            Нормализованная волатильность (от 0 до 1)
        """
        if not items:
            return 0.5  # Значение по умолчанию
        
        # Получаем цены предметов
        prices = []
        for item in items:
            price = float(item.get("price", {}).get("USD", 0))
            if price > 0:
                prices.append(price)
        
        if not prices:
            return 0.5
        
        # Рассчитываем стандартное отклонение и среднее
        mean_price = sum(prices) / len(prices)
        if mean_price == 0:
            return 0.5
            
        # Рассчитываем стандартное отклонение
        variance = sum((price - mean_price) ** 2 for price in prices) / len(prices)
        std_dev = variance ** 0.5
        
        # Рассчитываем коэффициент вариации (стандартное отклонение / среднее)
        coefficient_of_variation = std_dev / mean_price
        
        # Нормализуем к диапазону от 0 до 1
        # Значение 0.3 (30%) и выше считается высокой волатильностью
        normalized_volatility = min(1.0, coefficient_of_variation / 0.3)
        
        return normalized_volatility
    
    async def get_all_market_items(
        self,
        game_id: str,
        price_from: float = 0.0,
        price_to: float = 1000.0,
        max_items: int = 1000,
        category: Optional[str] = None,
        use_parallel: bool = True,
        max_parallel_requests: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Получает все доступные предметы с рынка с пагинацией.
        
        Args:
            game_id: Идентификатор игры
            price_from: Минимальная цена для фильтрации
            price_to: Максимальная цена для фильтрации
            max_items: Максимальное количество предметов для анализа
            category: Категория предметов для фильтрации
            use_parallel: Использовать параллельные запросы
            max_parallel_requests: Максимальное количество параллельных запросов
            
        Returns:
            Список предметов с рынка
        """
        logger.info(f"Получение всех предметов для game_id={game_id}, цена от {price_from} до {price_to}")
        
        # Ключ для кэша
        cache_key = f"items_{game_id}_{price_from}_{price_to}_{category}"
        
        # Проверяем кэш
        cached_data = self.smart_cache.get(cache_key)
        if cached_data:
            logger.info(f"Используются кэшированные предметы для {cache_key}")
            self.metrics.record_metric("cache_hit_rate", 1.0)
            return cached_data[:max_items]
        
        try:
            # Начальный запрос для определения общего количества страниц
            initial_items, total, limit = await self.api.get_market_items(
                game_id=game_id,
                price_from=price_from,
                price_to=price_to,
                limit=100,
                offset=0,
                category=category
            )
            
            # Если нет предметов, возвращаем пустой список
            if not initial_items:
                return []
                
            all_items = initial_items
            
            # Рассчитываем общее количество страниц
            total_pages = math.ceil(min(max_items, total) / limit)
            
            if total_pages <= 1:
                # Если всего одна страница, возвращаем уже полученные предметы
                return all_items[:max_items]
            
            # Получаем остальные страницы предметов
            if use_parallel and total_pages > 1:
                additional_items = await self._get_all_market_items_parallel(
                    game_id=game_id,
                    price_from=price_from,
                    price_to=price_to,
                    total_pages=total_pages,
                    limit=limit,
                    max_items=max_items,
                    category=category,
                    max_parallel_requests=max_parallel_requests
                )
            else:
                # Последовательные запросы
                additional_items = []
                for page in range(1, total_pages):
                    offset = page * limit
                    
                    # Если достигли максимального количества предметов, прерываем цикл
                    if len(all_items) >= max_items:
                        break
                        
                    page_items, _, _ = await self.api.get_market_items(
                        game_id=game_id,
                        price_from=price_from,
                        price_to=price_to,
                        limit=limit,
                        offset=offset,
                        category=category
                    )
                    
                    if page_items:
                        additional_items.extend(page_items)
            
            # Объединяем результаты
            all_items.extend(additional_items)
            
            # Ограничиваем количество предметов
            all_items = all_items[:max_items]
            
            # Сохраняем в кэш с адаптивным TTL в зависимости от волатильности
            volatility = self._calculate_price_volatility(all_items)
            ttl = max(60, self.params.cache_ttl_base * (1 - volatility * 0.5))
            
            self.smart_cache.put(cache_key, all_items, ttl=ttl)
            
            logger.info(f"Получено {len(all_items)} предметов для game_id={game_id}")
            return all_items
            
        except Exception as e:
            logger.error(f"Ошибка при получении предметов: {str(e)}")
            return []
    
    async def _get_all_market_items_parallel(
        self,
        game_id: str,
        price_from: float,
        price_to: float,
        total_pages: int,
        limit: int,
        max_items: int,
        category: Optional[str] = None,
        max_parallel_requests: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Получает предметы с рынка используя параллельные запросы.
        
        Args:
            game_id: Идентификатор игры
            price_from: Минимальная цена для фильтрации
            price_to: Максимальная цена для фильтрации
            total_pages: Общее количество страниц
            limit: Лимит предметов на страницу
            max_items: Максимальное количество предметов для анализа
            category: Категория предметов для фильтрации
            max_parallel_requests: Максимальное количество параллельных запросов
            
        Returns:
            Список предметов с рынка
        """
        all_items = []
        
        # Ограничиваем количество одновременных запросов
        semaphore = asyncio.Semaphore(max_parallel_requests)
        
        async def fetch_page(page):
            async with semaphore:
                offset = page * limit
                try:
                    page_items, _, _ = await self.api.get_market_items(
                        game_id=game_id,
                        price_from=price_from,
                        price_to=price_to,
                        limit=limit,
                        offset=offset,
                        category=category
                    )
                    return page_items
                except Exception as e:
                    logger.error(f"Ошибка при получении страницы {page}: {str(e)}")
                    return []
        
        # Рассчитываем, сколько страниц нам нужно получить, чтобы достичь max_items
        pages_needed = min(total_pages - 1, math.ceil((max_items - limit) / limit))
        
        # Создаем задачи для всех страниц, начиная со второй (первую уже получили)
        tasks = [fetch_page(page) for page in range(1, pages_needed + 1)]
        
        # Выполняем все задачи параллельно
        results = await asyncio.gather(*tasks)
        
        # Объединяем результаты
        for page_items in results:
            if page_items:
                all_items.extend(page_items)
                
                # Если собрали достаточно предметов, прерываем
                if len(all_items) >= max_items - limit:  # Вычитаем limit, т.к. первую страницу уже получили
                    break
        
        return all_items
        
    async def prepare_graph_data(
        self, 
        items: List[Dict[str, Any]],
        use_parallel: bool = True,
        max_workers: int = 5
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Подготавливает данные о предметах для создания графа обмена.
        
        Args:
            items: Список предметов
            use_parallel: Использовать параллельную обработку
            max_workers: Максимальное количество параллельных воркеров
            
        Returns:
            Данные для графа обмена в формате {from_node: {to_node: {"rate": rate, "fee": fee, "liquidity": liquidity}}}
        """
        if use_parallel:
            return await self._prepare_graph_data_parallel(items, max_workers)
        else:
            return await self._prepare_graph_data_sequential(items)
    
    async def _prepare_graph_data_sequential(self, items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Последовательно подготавливает данные для графа обмена.
        
        Args:
            items: Список предметов
            
        Returns:
            Данные для графа обмена
        """
        exchange_data = {}
        
        # Добавляем доллар как базовую валюту
        exchange_data["USD"] = {}
        
        # Обрабатываем каждый предмет
        for item in items:
            try:
                item_id = item.get("itemId") or item.get("id", "")
                title = item.get("title", "Unknown")
                price_data = item.get("price", {})
                
                if not item_id or not price_data:
                    continue
                
                # Получаем цену в USD
                price_usd = float(price_data.get("USD", 0))
                
                if price_usd <= 0:
                    continue
                
                # Создаем узел для предмета
                item_node = f"{title}_{item_id}"
                
                # Определяем ликвидность предмета
                liquidity = float(item.get("inMarket", 1))
                
                # Рассчитываем комиссию на основе цены и категории
                category = item.get("category", "")
                base_fee = self.params.base_fee
                
                # Разные категории могут иметь разные комиссии
                fee_multiplier = {
                    "knife": 0.9,  # Ножи обычно имеют меньшую комиссию
                    "gloves": 0.9,
                    "rifle": 1.0,
                    "pistol": 1.1,
                    "smg": 1.1,
                    "shotgun": 1.2,
                    "machinegun": 1.2,
                    "container": 1.3,  # Контейнеры обычно имеют большую комиссию
                }.get(category.lower(), 1.0)
                
                fee = base_fee * fee_multiplier
                
                # Добавляем ребра для покупки предмета (USD -> item)
                if "USD" not in exchange_data:
                    exchange_data["USD"] = {}
                
                exchange_data["USD"][item_node] = {
                    "rate": 1.0 / price_usd,
                    "fee": fee,
                    "liquidity": liquidity
                }
                
                # Добавляем ребра для продажи предмета (item -> USD)
                if item_node not in exchange_data:
                    exchange_data[item_node] = {}
                
                exchange_data[item_node]["USD"] = {
                    "rate": price_usd * (1.0 - fee),
                    "fee": fee,
                    "liquidity": liquidity
                }
                
                # Добавляем ребра для обмена между предметами
                for other_item in items:
                    other_id = other_item.get("itemId") or other_item.get("id", "")
                    other_title = other_item.get("title", "Unknown")
                    other_price_data = other_item.get("price", {})
                    
                    if not other_id or not other_price_data or other_id == item_id:
                        continue
                    
                    other_price_usd = float(other_price_data.get("USD", 0))
                    
                    if other_price_usd <= 0:
                        continue
                    
                    other_node = f"{other_title}_{other_id}"
                    other_liquidity = float(other_item.get("inMarket", 1))
                    
                    # Рассчитываем эффективную ставку обмена с учетом комиссий
                    effective_rate = (price_usd * (1.0 - fee)) / other_price_usd
                    
                    # Учитываем ликвидность обоих предметов
                    effective_liquidity = min(liquidity, other_liquidity)
                    
                    # Добавляем ребро для обмена
                    if item_node not in exchange_data:
                        exchange_data[item_node] = {}
                    
                    exchange_data[item_node][other_node] = {
                        "rate": effective_rate,
                        "fee": fee,
                        "liquidity": effective_liquidity
                    }
            except Exception as e:
                logger.error(f"Ошибка при обработке предмета {item.get('itemId', '')}: {str(e)}")
                continue
        
        return exchange_data
    
    async def _prepare_graph_data_parallel(
        self, 
        items: List[Dict[str, Any]], 
        max_workers: int = 5
    ) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Параллельно подготавливает данные для графа обмена.
        
        Args:
            items: Список предметов
            max_workers: Максимальное количество параллельных воркеров
            
        Returns:
            Данные для графа обмена
        """
        exchange_data = {"USD": {}}
        
        # Функция для обработки части предметов
        async def process_items_chunk(chunk, results):
            chunk_exchange_data = {}
            
            for item in chunk:
                try:
                    item_id = item.get("itemId") or item.get("id", "")
                    title = item.get("title", "Unknown")
                    price_data = item.get("price", {})
                    
                    if not item_id or not price_data:
                        continue
                    
                    # Получаем цену в USD
                    price_usd = float(price_data.get("USD", 0))
                    
                    if price_usd <= 0:
                        continue
                    
                    # Создаем узел для предмета
                    item_node = f"{title}_{item_id}"
                    
                    # Определяем ликвидность предмета
                    liquidity = float(item.get("inMarket", 1))
                    
                    # Рассчитываем комиссию
                    category = item.get("category", "")
                    base_fee = self.params.base_fee
                    
                    fee_multiplier = {
                        "knife": 0.9,
                        "gloves": 0.9,
                        "rifle": 1.0,
                        "pistol": 1.1,
                        "smg": 1.1,
                        "shotgun": 1.2,
                        "machinegun": 1.2,
                        "container": 1.3,
                    }.get(category.lower(), 1.0)
                    
                    fee = base_fee * fee_multiplier
                    
                    # Добавляем ребра для покупки предмета (USD -> item)
                    if "USD" not in chunk_exchange_data:
                        chunk_exchange_data["USD"] = {}
                    
                    chunk_exchange_data["USD"][item_node] = {
                        "rate": 1.0 / price_usd,
                        "fee": fee,
                        "liquidity": liquidity
                    }
                    
                    # Добавляем ребра для продажи предмета (item -> USD)
                    if item_node not in chunk_exchange_data:
                        chunk_exchange_data[item_node] = {}
                    
                    chunk_exchange_data[item_node]["USD"] = {
                        "rate": price_usd * (1.0 - fee),
                        "fee": fee,
                        "liquidity": liquidity
                    }
                    
                    # Добавляем ребра для обмена между предметами (внутри чанка)
                    for other_item in chunk:
                        other_id = other_item.get("itemId") or other_item.get("id", "")
                        other_title = other_item.get("title", "Unknown")
                        other_price_data = other_item.get("price", {})
                        
                        if not other_id or not other_price_data or other_id == item_id:
                            continue
                        
                        other_price_usd = float(other_price_data.get("USD", 0))
                        
                        if other_price_usd <= 0:
                            continue
                        
                        other_node = f"{other_title}_{other_id}"
                        other_liquidity = float(other_item.get("inMarket", 1))
                        
                        # Рассчитываем эффективную ставку обмена
                        effective_rate = (price_usd * (1.0 - fee)) / other_price_usd
                        
                        # Учитываем ликвидность
                        effective_liquidity = min(liquidity, other_liquidity)
                        
                        # Добавляем ребро для обмена
                        if item_node not in chunk_exchange_data:
                            chunk_exchange_data[item_node] = {}
                        
                        chunk_exchange_data[item_node][other_node] = {
                            "rate": effective_rate,
                            "fee": fee,
                            "liquidity": effective_liquidity
                        }
                except Exception as e:
                    logger.error(f"Ошибка при обработке предмета {item.get('itemId', '')}: {str(e)}")
                    continue
            
            results.append(chunk_exchange_data)
        
        # Разбиваем список предметов на чанки
        chunk_size = max(1, len(items) // max_workers)
        chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        
        results = []
        tasks = []
        
        # Создаем задачи для обработки чанков
        for chunk in chunks:
            task = asyncio.create_task(process_items_chunk(chunk, results))
            tasks.append(task)
        
        # Ждем завершения всех задач
        await asyncio.gather(*tasks)
        
        # Объединяем результаты
        for chunk_data in results:
            for from_node, to_nodes in chunk_data.items():
                if from_node not in exchange_data:
                    exchange_data[from_node] = {}
                
                exchange_data[from_node].update(to_nodes)
        
        return exchange_data
    
    async def find_arbitrage_opportunities(
        self,
        game_id: str,
        price_from: float = 0.0,
        price_to: float = 1000.0,
        min_profit_percent: float = 5.0,
        max_items: int = 1000,
        category: Optional[str] = None,
        force_refresh: bool = False,
        max_path_length: int = 3,
        use_ml_filtering: bool = False,  # Добавляем параметр для ML-фильтрации
        liquidity_threshold: float = 0.5  # Добавляем порог ликвидности
    ) -> List[Dict[str, Any]]:
        """
        Находит арбитражные возможности на платформе DMarket.
        
        Args:
            game_id: Идентификатор игры ('a8db' для CS2, '9a92' для Dota 2)
            price_from: Минимальная цена предметов для анализа
            price_to: Максимальная цена предметов для анализа
            min_profit_percent: Минимальный процент прибыли для фильтрации возможностей
            max_items: Максимальное количество предметов для анализа
            category: Категория предметов для анализа (опционально)
            force_refresh: Принудительно обновить данные, игнорируя кэш
            max_path_length: Максимальная длина пути для арбитражного цикла
            use_ml_filtering: Использовать ли ML для дополнительной фильтрации возможностей
            liquidity_threshold: Порог ликвидности для фильтрации предметов
            
        Returns:
            Список арбитражных возможностей
        """
        # Используем хеширование параметров для эффективного кэширования
        cache_key = hashlib.md5(
            f"{game_id}_{price_from}_{price_to}_{min_profit_percent}_{max_items}_{category}_{max_path_length}".encode()
        ).hexdigest()
        
        if not force_refresh:
            cached = self.smart_cache.get(cache_key)
            if cached:
                logger.info(f"Использую кэшированные арбитражные возможности для {game_id}")
                return cached
        
        with self.perf_monitor.measure("find_arbitrage_opportunities"):
            # Получаем предметы с рынка
            logger.info(f"Получение предметов для анализа: game_id={game_id}, price_from={price_from}, price_to={price_to}")
            items = await self.get_all_market_items(
                game_id=game_id,
                price_from=price_from,
                price_to=price_to,
                max_items=max_items,
                category=category,
                use_parallel=self.use_parallel
            )
            
            # Применяем предварительную фильтрацию по ликвидности
            items = [
                item for item in items 
                if self._calculate_liquidity_score(item) >= liquidity_threshold
            ]
            
            # Если включено использование ML и есть предиктор, обогащаем данные предметов
            if self.use_ml and self.ml_predictor and use_ml_filtering:
                await self._enrich_items_with_ml_predictions(items)
            
            # Подготавливаем данные для графа
            logger.info(f"Подготовка данных графа из {len(items)} предметов")
            graph_data = await self.prepare_graph_data(
                items=items,
                use_parallel=self.use_parallel
            )
            
            # Используем оптимизированную версию алгоритма поиска арбитража
            logger.info(f"Поиск арбитражных возможностей с мин. прибылью {min_profit_percent}%")
            opportunities = find_arbitrage_advanced(
                graph_data,
                min_profit_percent=min_profit_percent,
                max_path_length=max_path_length
            )
            
            # Обрабатываем и обогащаем результаты
            logger.info(f"Найдено {len(opportunities)} предварительных арбитражных возможностей")
            result = await self._process_opportunities(opportunities, items)
            
            # Применяем ML-фильтрацию, если включено
            if self.use_ml and self.ml_predictor and use_ml_filtering:
                logger.info("Применение ML-фильтрации к арбитражным возможностям")
                result = self._apply_ml_filtering(result, items, risk_threshold=0.5)
            
            # Сортируем возможности по нескольким критериям
            result = self._sort_opportunities_multi_criteria(result)
            
            logger.info(f"Финальное количество арбитражных возможностей: {len(result)}")
            
            # Кэшируем результаты
            self.smart_cache.set(cache_key, result, ttl=300)  # Кэшируем на 5 минут
            
            return result

    async def _enrich_items_with_ml_predictions(self, items: List[Dict[str, Any]]) -> None:
        """
        Обогащает предметы предсказаниями ML-модели.
        
        Args:
            items: Список предметов для обогащения
        """
        if not self.ml_predictor:
            return
        
        logger.info(f"Обогащение {len(items)} предметов ML-предсказаниями")
        
        # Создаем список идентификаторов предметов для пакетного предсказания
        item_ids = [item.get('itemId') for item in items if 'itemId' in item]
        
        try:
            # Получаем предсказания цен для всех предметов одним пакетом
            predictions = await self.ml_predictor.predict_prices_batch(item_ids)
            
            # Добавляем предсказания к предметам
            for item in items:
                item_id = item.get('itemId')
                if item_id and item_id in predictions:
                    item['predicted_price'] = predictions[item_id]
                    
                    # Рассчитываем потенциальный рост/падение цены
                    current_price = float(item.get('price', {}).get('amount', 0))
                    if current_price > 0:
                        price_change_percent = (predictions[item_id] - current_price) / current_price * 100
                        item['predicted_price_change'] = price_change_percent
                        
                        # Оцениваем потенциал на основе предсказания
                        if price_change_percent > 5:
                            item['price_potential'] = 'high'
                        elif price_change_percent > 0:
                            item['price_potential'] = 'medium'
                        else:
                            item['price_potential'] = 'low'
        
        except Exception as e:
            logger.error(f"Ошибка при обогащении предметов ML-предсказаниями: {e}")

    def _calculate_liquidity_score(self, item: Dict[str, Any]) -> float:
        """
        Рассчитывает показатель ликвидности предмета.
        
        Args:
            item: Информация о предмете
            
        Returns:
            Значение ликвидности от 0 до 1
        """
        # Используем несколько метрик для оценки ликвидности
        
        # 1. Количество предложений (больше предложений = выше ликвидность)
        offers_count = item.get('offersCount', 0)
        
        # 2. Частота продаж (если доступна)
        sales_frequency = item.get('salesFrequency', 0)
        
        # 3. Рейтинг популярности (если доступен)
        popularity = item.get('popularity', 0)
        
        # 4. Разница между ценой покупки и продажи (меньше = выше ликвидность)
        buy_price = float(item.get('buyPrice', {}).get('amount', 0))
        sell_price = float(item.get('price', {}).get('amount', 0))
        
        price_diff_ratio = 0
        if sell_price > 0 and buy_price > 0:
            price_diff_ratio = min(1, 1 - abs(buy_price - sell_price) / sell_price)
        
        # Нормализуем и комбинируем факторы
        normalized_offers = min(1, offers_count / 100)  # Нормализация до 1
        normalized_sales = min(1, sales_frequency / 10)
        normalized_popularity = min(1, popularity / 100)
        
        # Взвешенное среднее
        liquidity_score = (
            normalized_offers * 0.4 +
            normalized_sales * 0.3 +
            normalized_popularity * 0.2 +
            price_diff_ratio * 0.1
        )
        
        return max(0, min(1, liquidity_score))  # Ограничиваем от 0 до 1

    def _apply_ml_filtering(
        self, 
        opportunities: List[Dict[str, Any]], 
        items: List[Dict[str, Any]],
        risk_threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Применяет ML-фильтрацию к арбитражным возможностям.
        
        Args:
            opportunities: Список арбитражных возможностей
            items: Список предметов
            risk_threshold: Порог риска для фильтрации (от 0 до 1)
            
        Returns:
            Отфильтрованный список арбитражных возможностей
        """
        if not self.ml_predictor:
            return opportunities
        
        try:
            # Создаем словарь для быстрого поиска предметов по ID
            items_dict = {item.get('itemId'): item for item in items if 'itemId' in item}
            
            # Фильтруем возможности на основе ML-предсказаний
            filtered_opportunities = []
            
            for opp in opportunities:
                # Проверяем, есть ли у возможности предметы с ML-предсказаниями
                path = opp.get('path', [])
                path_items = [items_dict.get(item_id) for item_id in path if item_id in items_dict]
                
                # Рассчитываем общий риск на основе предсказаний
                risk_score = 0
                valid_items = 0
                
                for item in path_items:
                    if item and 'predicted_price_change' in item:
                        # Отрицательное изменение цены увеличивает риск
                        price_change = item['predicted_price_change']
                        if price_change < 0:
                            risk_score += abs(price_change) / 100
                        valid_items += 1
                
                # Нормализуем риск по количеству предметов
                avg_risk = risk_score / max(1, valid_items)
                
                # Добавляем возможность, если риск ниже порога
                if avg_risk <= risk_threshold:
                    # Добавляем оценку риска к возможности
                    opp['ml_risk_score'] = avg_risk
                    filtered_opportunities.append(opp)
            
            return filtered_opportunities
            
        except Exception as e:
            logger.error(f"Ошибка при применении ML-фильтрации: {e}")
            return opportunities  # В случае ошибки возвращаем исходные возможности
    
    async def _process_opportunities(
        self, 
        opportunities: List[Dict[str, Any]], 
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Обрабатывает арбитражные возможности для получения более подробной информации.
        
        Args:
            opportunities: Список арбитражных возможностей
            items: Список предметов с рынка
            
        Returns:
            Список обработанных арбитражных возможностей
        """
        # Создаем словарь предметов для быстрого поиска
        items_dict = {}
        for item in items:
            item_id = item.get("itemId") or item.get("id", "")
            if item_id:
                items_dict[item_id] = item
        
        processed_opportunities = []
        
        for opp in opportunities:
            try:
                path = opp["path"]
                
                # Получаем подробную информацию о предметах в пути
                path_items = []
                for i, node in enumerate(path):
                    if node == "USD":
                        continue
                    
                    # Извлекаем идентификатор предмета из узла
                    item_id = node.split("_")[-1]
                    
                    if item_id in items_dict:
                        item_info = items_dict[item_id]
                        path_items.append({
                            "index": i,
                            "item_id": item_id,
                            "title": item_info.get("title", "Unknown"),
                            "price": item_info.get("price", {}).get("USD", 0),
                            "category": item_info.get("category", ""),
                            "image": item_info.get("image", ""),
                            "inMarket": item_info.get("inMarket", 0)
                        })
                
                # Рассчитываем риск и рекомендуемый объем
                risk_score = self._calculate_risk_score(opp, path_items)
                recommended_volume = self._calculate_recommended_volume(opp, path_items)
                
                # Оцениваем время выполнения
                estimated_time = self._estimate_execution_time(opp, path_items)
                
                # Добавляем дополнительную информацию к возможности
                processed_opp = opp.copy()
                processed_opp.update({
                    "path_items": path_items,
                    "risk_score": risk_score,
                    "recommended_volume": recommended_volume,
                    "estimated_time": estimated_time
                })
                
                processed_opportunities.append(processed_opp)
            except Exception as e:
                logger.error(f"Ошибка при обработке возможности: {str(e)}")
                continue
        
        return processed_opportunities
    
    def _sort_opportunities_multi_criteria(
        self, 
        opportunities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Сортирует арбитражные возможности по нескольким критериям.
        
        Args:
            opportunities: Список арбитражных возможностей
            
        Returns:
            Отсортированный список арбитражных возможностей
        """
        def multi_key(opp):
            # Вес для различных критериев
            profit_weight = 0.5
            risk_weight = 0.3
            liquidity_weight = 0.2
            
            # Нормализуем значения
            profit_ratio = opp.get("profit_ratio", 1.0)
            normalized_profit = min(1.0, (profit_ratio - 1.0) * 5.0)  # 20% прибыли считается максимальной
            
            risk_score = opp.get("risk_score", 0.5)
            normalized_risk = 1.0 - risk_score  # Инвертируем, чтобы низкий риск был лучше
            
            liquidity = opp.get("liquidity", 0)
            normalized_liquidity = min(1.0, liquidity / 10.0)  # 10 считается хорошей ликвидностью
            
            # Комбинированная оценка
            score = (
                normalized_profit * profit_weight +
                normalized_risk * risk_weight +
                normalized_liquidity * liquidity_weight
            )
            
            return -score  # Отрицательное значение для сортировки по убыванию
        
        # Сортируем возможности по комбинированной оценке
        return sorted(opportunities, key=multi_key)
    
    def _calculate_risk_score(
        self, 
        opportunity: Dict[str, Any],
        path_items: List[Dict[str, Any]]
    ) -> float:
        """
        Рассчитывает оценку риска для арбитражной возможности.
        
        Args:
            opportunity: Арбитражная возможность
            path_items: Информация о предметах в пути
            
        Returns:
            Оценка риска (от 0 до 1, где 1 - максимальный риск)
        """
        # Факторы риска
        path_length = len(opportunity.get("path", []))
        profit_ratio = opportunity.get("profit_ratio", 1.0)
        liquidity = opportunity.get("liquidity", 0)
        
        # Риск увеличивается с длиной пути
        path_risk = min(1.0, (path_length - 2) / 5.0)
        
        # Риск уменьшается с прибылью (до определенного предела)
        profit_risk = max(0.0, 1.0 - (profit_ratio - 1.0) * 5.0)  # 20% прибыли считается минимальным риском
        
        # Риск уменьшается с ликвидностью
        liquidity_risk = max(0.0, 1.0 - (liquidity / 10.0))
        
        # Добавляем риск по категориям предметов
        category_risk = 0.0
        high_risk_categories = ["container", "sticker", "agent", "patch"]
        
        for item in path_items:
            category = item.get("category", "").lower()
            if category in high_risk_categories:
                category_risk += 0.1
        
        category_risk = min(0.5, category_risk)
        
        # Комбинированная оценка риска
        risk_weights = {
            "path": 0.3,
            "profit": 0.2,
            "liquidity": 0.3,
            "category": 0.2
        }
        
        risk_score = (
            path_risk * risk_weights["path"] +
            profit_risk * risk_weights["profit"] +
            liquidity_risk * risk_weights["liquidity"] +
            category_risk * risk_weights["category"]
        )
        
        return min(1.0, max(0.0, risk_score))
    
    def _calculate_recommended_volume(
        self, 
        opportunity: Dict[str, Any],
        path_items: List[Dict[str, Any]]
    ) -> int:
        """
        Рассчитывает рекомендуемый объем для арбитражной возможности.
        
        Args:
            opportunity: Арбитражная возможность
            path_items: Информация о предметах в пути
            
        Returns:
            Рекомендуемый объем сделки
        """
        # Базовый объем
        base_volume = 1
        
        # Учитываем прибыль
        profit_ratio = opportunity.get("profit_ratio", 1.0)
        profit_multiplier = min(3.0, 1.0 + (profit_ratio - 1.0) * 10.0)  # 10% прибыли -> объем x2
        
        # Учитываем ликвидность
        liquidity = opportunity.get("liquidity", 0)
        liquidity_multiplier = min(1.0, liquidity / 3.0)  # Максимум 1/3 от доступной ликвидности
        
        # Учитываем риск
        risk_score = opportunity.get("risk_score", 0.5)
        risk_multiplier = 1.0 - (risk_score * 0.7)  # Высокий риск снижает объем до 30%
        
        # Комбинированный множитель
        volume_multiplier = profit_multiplier * liquidity_multiplier * risk_multiplier
        
        # Рассчитываем рекомендуемый объем
        recommended_volume = max(1, int(base_volume * volume_multiplier))
        
        # Ограничиваем максимальным объемом
        max_volume = min([item.get("inMarket", 1) for item in path_items]) if path_items else 1
        recommended_volume = min(recommended_volume, max_volume)
        
        return max(1, recommended_volume)
    
    def _estimate_execution_time(
        self, 
        opportunity: Dict[str, Any],
        path_items: List[Dict[str, Any]]
    ) -> int:
        """
        Оценивает время выполнения арбитражного цикла в секундах.
        
        Args:
            opportunity: Арбитражная возможность
            path_items: Информация о предметах в пути
            
        Returns:
            Оценка времени выполнения в секундах
        """
        # Базовое время на транзакцию
        transaction_time = 30  # секунд
        
        # Получаем количество транзакций
        num_transactions = len(opportunity.get("path", [])) - 1
        
        # Учитываем ликвидность (более низкая ликвидность увеличивает время)
        liquidity = opportunity.get("liquidity", 1)
        liquidity_factor = max(1.0, 2.0 / liquidity)
        
        # Учитываем сложность пути
        path_complexity = 1.0 + (num_transactions - 2) * 0.2  # Каждая дополнительная транзакция добавляет 20%
        
        # Рассчитываем общее время
        total_time = int(transaction_time * num_transactions * liquidity_factor * path_complexity)
        
        return total_time

    async def get_arbitrage_opportunities(self, game_id: str, budget: float = None) -> List[Dict[str, Any]]:
        """
        Получает список арбитражных возможностей для указанной игры и бюджета.
        
        Args:
            game_id: Идентификатор игры ('a8db' для CS2, '9a92' для Dota 2)
            budget: Доступный бюджет для арбитража
            
        Returns:
            Список арбитражных возможностей
        """
        self.logger.info(f"Поиск арбитражных возможностей для игры {game_id} в режиме {self.params.mode}...")
        
        # Получаем данные рынка для указанной игры
        market_data = await self._get_game_market_data(game_id)
        if not market_data:
            self.logger.error(f"Не удалось получить данные рынка для игры {game_id}")
            return []
        
        # Фильтруем и анализируем возможности
        arbitrage_opportunities = self._analyze_market_data(market_data)
        
        # Применяем фильтры в зависимости от режима
        filtered_opportunities = self._filter_opportunities_by_mode(arbitrage_opportunities, budget)
        
        # Добавляем дополнительные данные, специфичные для режима
        enriched_opportunities = await self._enrich_opportunities_by_mode(filtered_opportunities)
        
        # Сортируем результаты
        sorted_opportunities = self._sort_opportunities(enriched_opportunities)
        
        # Ограничиваем количество результатов
        limited_results = sorted_opportunities[:self.params.max_results]
        
        self.logger.info(f"Найдено {len(limited_results)} арбитражных возможностей из {len(arbitrage_opportunities)} проанализированных")
        return limited_results

    def _filter_opportunities_by_mode(self, opportunities: List[Dict[str, Any]], budget: float = None) -> List[Dict[str, Any]]:
        """
        Фильтрует возможности в зависимости от выбранного режима работы.
        
        Args:
            opportunities: Список арбитражных возможностей
            budget: Бюджет для фильтрации
            
        Returns:
            Отфильтрованный список возможностей
        """
        filtered = []
        
        for opp in opportunities:
            # Базовые фильтры для всех режимов
            if (opp["profit"] < self.params.min_profit or 
                opp["profit"] > self.params.max_profit or
                opp["buy_price"] < self.params.min_price or
                opp["buy_price"] > self.params.max_price):
                continue
            
            # Если указан бюджет, фильтруем по нему
            if budget and opp["buy_price"] > budget:
                continue
            
            # Специфические фильтры для режимов
            if self.params.mode == "balance_boost":
                # Для режима "Разгон баланса" требуется высокая ликвидность
                if opp.get("liquidity", 0) < self.params.min_liquidity:
                    continue
                # И низкий риск
                if opp.get("risk_level", "high") == "high":
                    continue
                    
            elif self.params.mode == "medium_trader":
                # Для режима "Средний трейдер" приоритет предметам высокого спроса
                if not opp.get("is_high_demand", False) and opp.get("liquidity", 0) < self.params.min_liquidity:
                    continue
                    
            elif self.params.mode == "trade_pro":
                # Для режима "Trade Pro" допускаем более редкие предметы
                # но требуем высокую прогнозируемую прибыль
                if opp.get("profit_percent", 0) < 10:  # Минимум 10% прибыли для Trade Pro
                    continue
            
            filtered.append(opp)
            
        return filtered
    
    async def _enrich_opportunities_by_mode(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Обогащает возможности дополнительными данными в зависимости от режима.
        
        Args:
            opportunities: Список арбитражных возможностей
            
        Returns:
            Обогащенный список возможностей
        """
        for opp in opportunities:
            # Добавляем режим в данные для отображения
            opp["mode"] = self.params.mode
            
            # Определяем комиссию в зависимости от свойств предмета
            if opp.get("is_high_demand", False):
                opp["fee"] = self.params.high_demand_fee
                # Для предметов высокого спроса в режиме Trade Pro добавляем прогнозы
                if self.params.mode == "trade_pro" and self.use_ml and self.ml_predictor:
                    try:
                        # Получаем прогноз цены на неделю вперед
                        prediction = await self.ml_predictor.predict_price(
                            game_id=opp.get("game_id", "a8db"),
                            item_name=opp.get("item_name", ""),
                            days_ahead=7
                        )
                        if prediction and isinstance(prediction, dict):
                            opp["price_prediction"] = prediction
                    except Exception as e:
                        self.logger.warning(f"Ошибка при получении прогноза: {e}")
            else:
                opp["fee"] = self.params.base_fee
            
            # Рассчитываем чистую прибыль с учетом комиссии
            sell_price = opp.get("sell_price", 0)
            buy_price = opp.get("buy_price", 0)
            fee = opp.get("fee", self.params.base_fee)
            
            opp["net_profit"] = sell_price * (1 - fee) - buy_price
            opp["profit_percent"] = (opp["net_profit"] / buy_price) * 100 if buy_price > 0 else 0
            
            # Добавляем рекомендации в зависимости от режима
            if self.params.mode == "balance_boost":
                opp["recommendation"] = "Быстро купить и перепродать"
            elif self.params.mode == "medium_trader":
                opp["recommendation"] = "Купить и держать 1-2 дня"
            elif self.params.mode == "trade_pro":
                opp["recommendation"] = "Купить и держать 3-7 дней"
            
        return opportunities
    
    def _sort_opportunities(self, opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Сортирует возможности в зависимости от выбранного режима.
        
        Args:
            opportunities: Список возможностей
            
        Returns:
            Отсортированный список возможностей
        """
        if self.params.mode == "balance_boost":
            # Для режима "Разгон баланса" приоритет ликвидности и низкому риску
            return sorted(opportunities, key=lambda x: (
                -x.get("liquidity", 0),  # Высокая ликвидность
                -x.get("net_profit", 0)  # Затем по прибыли
            ))
        elif self.params.mode == "medium_trader":
            # Для режима "Средний трейдер" приоритет соотношению прибыли и риска
            return sorted(opportunities, key=lambda x: (
                -x.get("profit_percent", 0),  # Высокий процент прибыли
                -x.get("liquidity", 0)        # Затем по ликвидности
            ))
        elif self.params.mode == "trade_pro":
            # Для режима "Trade Pro" приоритет абсолютной прибыли
            return sorted(opportunities, key=lambda x: (
                -x.get("net_profit", 0),   # Высокая абсолютная прибыль
                -x.get("profit_percent", 0)  # Затем по проценту прибыли
            ))
        else:
            # По умолчанию сортируем по прибыли
            return sorted(opportunities, key=lambda x: -x.get("net_profit", 0))


async def main():
    """
    Пример использования класса DMarketArbitrageFinder.
    """
    import json
    from config import config
    
    # Получаем API ключи из конфигурации
    api_key = config.api.DMARKET_API_KEY
    api_secret = config.api.DMARKET_API_SECRET
    
    # Создаем экземпляр класса
    finder = DMarketArbitrageFinder(api_key, api_secret)
    
    # Находим рекомендуемые предметы для покупки
    recommendations = await finder.get_recommended_buys(
        game_id="a8db",  # CS2
        budget=100.0,
        min_profit=3.0,
        max_results=10
    )
    
    # Выводим результаты
    print(json.dumps(recommendations, indent=2))


if __name__ == "__main__":
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запускаем асинхронный пример
    asyncio.run(main()) 