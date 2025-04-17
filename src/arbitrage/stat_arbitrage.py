"""
Модуль для статистического арбитража на платформе DMarket с использованием алгоритма Беллмана-Форда.

Этот модуль реализует интеграцию алгоритма Беллмана-Форда с API DMarket для
автоматического анализа рынка, поиска ликвидных скинов и создания отложенных ордеров.
"""

import logging
import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
import os
import random
import math

from api_wrapper import DMarketAPI, APIError
from bellman_ford import (
    Edge, 
    ArbitrageResult, 
    create_graph, 
    find_arbitrage_advanced, 
    find_all_arbitrage_opportunities_async,
    generate_dmarket_target_orders
)

# Настройка логгера
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Директория для кэширования данных
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)


class StatArbitrage:
    """
    Класс для статистического арбитража на платформе DMarket.
    
    Реализует методы для анализа рынка, поиска ликвидных скинов, расчета оптимальных
    цен и объемов для торговли, а также создания отложенных ордеров.
    """
    
    def __init__(
        self, 
        api_key: str,
        api_secret: str,
        min_profit: float = 5.0,
        min_liquidity: float = 10.0,
        min_confidence: float = 0.3,
        max_fee: float = 5.0,
        market_fee: float = 7.0,
        cache_ttl: int = 3600,
        workers: int = 4
    ):
        """
        Инициализация класса для статистического арбитража.
        
        Args:
            api_key: Ключ API DMarket
            api_secret: Секрет API DMarket
            min_profit: Минимальный процент прибыли для создания ордеров
            min_liquidity: Минимальная ликвидность предметов
            min_confidence: Минимальный уровень уверенности для арбитражных возможностей
            max_fee: Максимальная комиссия для учета в расчетах
            market_fee: Комиссия DMarket (в процентах)
            cache_ttl: Время жизни кэша (в секундах)
            workers: Количество рабочих потоков для асинхронных операций
        """
        self.api = DMarketAPI(api_key=api_key, api_secret=api_secret)
        self.min_profit = min_profit
        self.min_liquidity = min_liquidity
        self.min_confidence = min_confidence
        self.max_fee = max_fee
        self.market_fee = market_fee
        self.cache_ttl = cache_ttl
        self.workers = workers
        self.exchange_rates: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.cached_items: Dict[str, Dict[str, Any]] = {}
        self.cached_market_info: Dict[str, Dict[str, Any]] = {}
        self.active_orders: List[Dict[str, Any]] = []
        self.last_update: float = 0
    
    async def update_market_data(
        self, 
        games: Optional[List[str]] = None,
        limit: int = 100,
        force: bool = False
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Обновляет данные о рынке, собирая информацию о цене и ликвидности предметов.
        
        Args:
            games: Список игр для анализа (если None, используются все доступные)
            limit: Максимальное количество предметов для каждой игры
            force: Принудительное обновление кэша
            
        Returns:
            Словарь с обменными курсами между предметами
        """
        current_time = time.time()
        
        # Проверяем, не устарел ли кэш
        if not force and self.last_update > 0 and current_time - self.last_update < self.cache_ttl:
            logger.info("Используем кэшированные данные о рынке")
            return self.exchange_rates
        
        # Определяем игры для сбора данных
        if games is None:
            # Если игры не указаны, получаем список популярных игр
            try:
                # DMarket API не имеет метода get_games_list_async, используем фиксированный список
                games = ["CS:GO", "Dota 2", "Rust"]
                logger.info(f"Используем стандартный список игр для анализа: {games}")
            except APIError as e:
                logger.error(f"Ошибка API: {e}")
                games = ["CS:GO", "Dota 2", "Rust"]  # Резервный список игр
        
        # Собираем данные рынка для каждой игры
        exchange_rates = {}
        tasks = []
        
        for game in games:
            task = self._fetch_market_data_for_game(game, limit)
            tasks.append(task)
        
        # Выполняем запросы асинхронно
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Объединяем результаты
            for game, result in zip(games, results):
                if isinstance(result, Exception):
                    logger.error(f"Ошибка при получении данных для {game}: {result}")
                    continue
                
                # Безопасное обновление словаря
                if isinstance(result, dict):
                    exchange_rates.update(result)
            
            # Сохраняем результаты в кэш
            self.exchange_rates = exchange_rates
            self.last_update = current_time
            
            # Сохраняем в файл для отладки
            cache_file = os.path.join(CACHE_DIR, "market_data.json")
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(exchange_rates, f, indent=2)
                logger.info(f"Данные рынка сохранены в {cache_file}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении кэша: {e}")
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при обновлении данных рынка: {e}")
            # Если произошла ошибка при обновлении данных, но у нас есть кэшированные данные, используем их
            if self.exchange_rates:
                logger.info("Используем существующие кэшированные данные после ошибки обновления")
                return self.exchange_rates
        
        return exchange_rates
    
    async def _fetch_market_data_for_game(
        self, 
        game: str, 
        limit: int
    ) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Получает данные рынка для конкретной игры и строит граф обменных курсов.
        
        Args:
            game: Название игры
            limit: Максимальное количество предметов
            
        Returns:
            Словарь с обменными курсами между предметами этой игры
        """
        try:
            # Получаем предметы с рынка
            market_items = await self.api.get_market_items_async(
                game_id=game,
                limit=limit,
                order_by="price",
                order_dir="asc",
                currency="USD"
            )
            
            if not market_items:
                logger.warning(f"Не найдены предметы для игры {game}")
                return {}
            
            logger.info(f"Получено {len(market_items)} предметов для {game}")
            
            # Строим словарь обменных курсов
            exchange_rates = {}
            
            # Сначала индексируем предметы по имени для быстрого доступа
            items_by_name = {}
            for item in market_items:
                # Проверяем, что item является словарем, а не строкой
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except json.JSONDecodeError:
                        logger.error(f"Не удалось декодировать item как JSON: {item[:100]}")
                        continue
                
                # Теперь безопасно получаем данные из dictionary
                name = item.get("title", "")
                if not name:
                    continue
                
                # Сохраняем основную информацию о предмете
                items_by_name[name] = {
                    "price": float(item.get("price", {}).get("USD", 0)),
                    "amount": int(item.get("inMarket", 0)),
                    "market_depth": len(item.get("offers", [])),
                    "discount": float(item.get("discount", 0)),
                    "item_id": item.get("itemId", ""),
                    "game": game,
                    "timestamp": time.time()
                }
                
                # Кэшируем информацию о предмете
                self.cached_items[name] = items_by_name[name]
            
            # Теперь строим граф обменных курсов между предметами
            for from_item, from_data in items_by_name.items():
                exchange_rates[from_item] = {}
                
                # Если цена предмета равна 0, пропускаем его
                if from_data["price"] <= 0:
                    continue
                
                for to_item, to_data in items_by_name.items():
                    # Пропускаем тот же самый предмет
                    if from_item == to_item:
                        continue
                    
                    # Пропускаем предметы с нулевой ценой
                    if to_data["price"] <= 0:
                        continue
                    
                    # Рассчитываем курс обмена (сколько to_item можно получить за from_item)
                    # с учетом комиссии маркетплейса
                    fee_factor = 1.0 - (self.market_fee / 100.0)
                    exchange_rate = (from_data["price"] * fee_factor) / to_data["price"]
                    
                    # Оцениваем ликвидность как минимум из количества предметов
                    liquidity = min(from_data["amount"], to_data["amount"])
                    
                    # Оцениваем объем торгов (можно запросить дополнительно, если API предоставляет такие данные)
                    volume_24h = random.uniform(0.5, 1.5) * liquidity  # Имитация данных
                    
                    # Сохраняем информацию о курсе обмена
                    exchange_rates[from_item][to_item] = {
                        "rate": exchange_rate,
                        "liquidity": float(liquidity),
                        "fee": self.market_fee,
                        "timestamp": time.time(),
                        "market_depth": float(min(from_data["market_depth"], to_data["market_depth"])),
                        "volume_24h": volume_24h,
                        "from_price": from_data["price"],
                        "to_price": to_data["price"],
                        "from_id": from_data["item_id"],
                        "to_id": to_data["item_id"]
                    }
            
            return exchange_rates
        
        except APIError as e:
            logger.error(f"Ошибка API при получении данных для {game}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Непредвиденная ошибка для {game}: {str(e)}")
            return {}
    
    async def find_arbitrage_opportunities(self) -> List[ArbitrageResult]:
        """
        Находит арбитражные возможности на основе текущих данных рынка.
        
        Returns:
            Список найденных арбитражных возможностей
        """
        # Проверяем, есть ли актуальные данные о рынке
        if not self.exchange_rates:
            await self.update_market_data()
        
        if not self.exchange_rates:
            logger.error("Не удалось получить данные о рынке для поиска арбитража")
            return []
        
        try:
            # Находим арбитражные возможности асинхронно
            # Преобразуем типы для совместимости с ожидаемым интерфейсом
            exchange_rates_compatible = {}
            for from_item, to_items in self.exchange_rates.items():
                exchange_rates_compatible[from_item] = {}
                for to_item, rate_data in to_items.items():
                    exchange_rates_compatible[from_item][to_item] = rate_data
            
            opportunities = await find_all_arbitrage_opportunities_async(
                exchange_rates=exchange_rates_compatible,
                min_profit=self.min_profit,
                min_liquidity=self.min_liquidity,
                max_opportunities=10,
                min_confidence=self.min_confidence,
                fee=self.market_fee,
                workers=self.workers
            )
            
            logger.info(f"Найдено {len(opportunities)} арбитражных возможностей")
            
            # Логирование деталей каждой возможности
            for i, opp in enumerate(opportunities, 1):
                profit_percent = (opp.profit_factor - 1) * 100
                logger.info(f"Возможность #{i}: {' -> '.join(opp.cycle)}, "
                          f"прибыль: {profit_percent:.2f}%, "
                          f"уверенность: {opp.confidence:.2f}")
            
            return opportunities
        
        except Exception as e:
            logger.error(f"Ошибка при поиске арбитражных возможностей: {str(e)}")
            return []
    
    async def generate_target_orders(self) -> List[Dict[str, Any]]:
        """
        Генерирует отложенные ордера на основе найденных арбитражных возможностей.
        
        Returns:
            Список отложенных ордеров для выставления
        """
        try:
            # Находим арбитражные возможности
            opportunities = await self.find_arbitrage_opportunities()
            
            if not opportunities:
                logger.info("Арбитражных возможностей не найдено, ордера не созданы")
                return []
            
            # Генерируем отложенные ордера
            target_orders = generate_dmarket_target_orders(
                opportunities=opportunities,
                max_targets=5,
                min_profit=self.min_profit,
                execution_delay=60  # 1 минута на подготовку
            )
            
            logger.info(f"Сгенерировано {len(target_orders)} целевых ордеров")
            
            # Сохраняем ордера в файл для отладки
            orders_file = os.path.join(CACHE_DIR, "target_orders.json")
            try:
                with open(orders_file, 'w', encoding='utf-8') as f:
                    json.dump(target_orders, f, indent=2)
                logger.info(f"Целевые ордера сохранены в {orders_file}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении ордеров: {e}")
            
            # Возвращаем ордера для дальнейшей обработки
            self.active_orders = target_orders
            return target_orders
        
        except Exception as e:
            logger.error(f"Ошибка при генерации целевых ордеров: {str(e)}")
            return []
    
    async def execute_target_orders(self) -> List[Dict[str, Any]]:
        """
        Выполняет отложенные ордера, когда приходит время их исполнения.
        
        Returns:
            Список выполненных ордеров с результатами
        """
        if not self.active_orders:
            logger.info("Отсутствуют активные ордера для выполнения")
            return []
        
        executed_orders = []
        current_time = time.time()
        
        # Фильтруем ордера, которые должны быть выполнены
        orders_to_execute = [
            order for order in self.active_orders 
            if order.get("execution_time", 0) <= current_time
        ]
        
        if not orders_to_execute:
            logger.info("Нет ордеров, готовых к исполнению")
            return []
        
        logger.info(f"Готово к исполнению {len(orders_to_execute)} ордеров")
        
        # Выполняем каждый ордер
        for order in orders_to_execute:
            try:
                # Получаем информацию о предмете
                item_name = order.get("item_name", "")
                price = order.get("price", 0)
                item_type = order.get("type", "")
                
                if not item_name or price <= 0:
                    logger.error(f"Некорректные данные ордера: {order}")
                    continue
                
                # Проверяем актуальность рыночных данных
                if item_name in self.cached_items:
                    item_info = self.cached_items[item_name]
                    
                    # Если данные устарели, пропускаем ордер
                    if current_time - item_info.get("timestamp", 0) > self.cache_ttl:
                        logger.warning(f"Устаревшие данные для {item_name}, обновите рыночные данные")
                        continue
                    
                    # Проверяем, доступен ли предмет на рынке
                    if item_info.get("amount", 0) <= 0:
                        logger.warning(f"Предмет {item_name} недоступен на рынке")
                        continue
                    
                    # Проверяем, не изменилась ли цена значительно
                    current_price = item_info.get("price", 0)
                    price_change_percent = abs(current_price - price) / price * 100
                    
                    if price_change_percent > 5:  # Если цена изменилась более чем на 5%
                        logger.warning(f"Цена на {item_name} изменилась на {price_change_percent:.2f}%, "
                                     f"с {price} до {current_price}")
                        continue
                
                # Выполняем ордер (симуляция)
                logger.info(f"Выполняется ордер: {item_type} {item_name} по цене {price}")
                
                # В реальной системе здесь был бы вызов API для покупки/продажи
                # api_response = await self.api.buy_item(item_id=order.get("from_id"), price=price)
                
                # Имитируем успешное выполнение ордера
                executed_order = {
                    **order,
                    "executed_at": current_time,
                    "success": True,
                    "message": "Ордер успешно выполнен (симуляция)"
                }
                
                executed_orders.append(executed_order)
                
                # Удаляем ордер из списка активных
                self.active_orders.remove(order)
                
                # Логирование
                logger.info(f"Ордер успешно выполнен: {item_type} {item_name}")
                
            except Exception as e:
                logger.error(f"Ошибка при выполнении ордера на {order.get('item_name')}: {str(e)}")
                
                # Отмечаем ордер как неудачный
                executed_order = {
                    **order,
                    "executed_at": current_time,
                    "success": False,
                    "message": f"Ошибка: {str(e)}"
                }
                
                executed_orders.append(executed_order)
        
        return executed_orders
    
    async def analyze_items_liquidity(
        self, 
        game: str = "CS:GO", 
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Анализирует ликвидность предметов в заданной игре.
        
        Args:
            game: Название игры
            limit: Максимальное количество предметов для анализа
            
        Returns:
            Список предметов с оценкой ликвидности
        """
        try:
            # Получаем предметы с рынка
            market_items = await self.api.get_market_items_async(
                game_id=game,
                limit=limit,
                order_by="popularity",
                order_dir="desc",
                currency="USD"
            )
            
            if not market_items:
                logger.warning(f"Не найдены предметы для игры {game}")
                return []
            
            logger.info(f"Получено {len(market_items)} предметов для анализа ликвидности")
            
            # Анализируем ликвидность каждого предмета
            liquidity_analysis = []
            
            for item in market_items:
                # Проверяем, что item является словарем, а не строкой
                if isinstance(item, str):
                    try:
                        item = json.loads(item)
                    except json.JSONDecodeError:
                        logger.error(f"Не удалось декодировать item как JSON: {item[:100]}")
                        continue
                
                name = item.get("title", "")
                if not name:
                    continue
                
                price = float(item.get("price", {}).get("USD", 0))
                if price <= 0:
                    continue
                
                # Рассчитываем базовые метрики ликвидности
                in_market = int(item.get("inMarket", 0))
                market_depth = len(item.get("offers", []))
                lowest_price = float(item.get("minPrice", {}).get("USD", price))
                highest_price = float(item.get("maxPrice", {}).get("USD", price))
                
                # Диапазон цен (в процентах)
                price_range_percent = 0
                if lowest_price > 0:
                    price_range_percent = (highest_price - lowest_price) / lowest_price * 100
                
                # Рассчитываем оценку ликвидности (от 0 до 100)
                liquidity_score = 0
                
                # Учитываем количество предметов на рынке
                if in_market > 0:
                    market_score = min(in_market / 10, 30)  # до 30 баллов
                    liquidity_score += market_score
                
                # Учитываем глубину рынка
                if market_depth > 0:
                    depth_score = min(market_depth / 5, 20)  # до 20 баллов
                    liquidity_score += depth_score
                
                # Учитываем диапазон цен (меньше = лучше)
                if price_range_percent < 50:
                    range_score = 20 * (1 - price_range_percent / 50)  # до 20 баллов
                    liquidity_score += range_score
                
                # Учитываем цену (предметы среднего диапазона обычно более ликвидны)
                if 1 <= price <= 100:
                    price_score = 30 * (1 - abs(price - 20) / 80)  # до 30 баллов
                    liquidity_score += max(0, price_score)
                
                # Округляем итоговую оценку
                liquidity_score = round(liquidity_score, 1)
                
                # Формируем запись анализа
                analysis = {
                    "name": name,
                    "price": price,
                    "in_market": in_market,
                    "market_depth": market_depth,
                    "price_range_percent": price_range_percent,
                    "liquidity_score": liquidity_score,
                    "liquidity_category": self._get_liquidity_category(liquidity_score),
                    "item_id": item.get("itemId", ""),
                    "game": game
                }
                
                liquidity_analysis.append(analysis)
            
            # Сортируем по оценке ликвидности
            liquidity_analysis.sort(key=lambda x: x["liquidity_score"], reverse=True)
            
            # Сохраняем результат анализа в файл
            analysis_file = os.path.join(CACHE_DIR, f"liquidity_analysis_{game}.json")
            try:
                with open(analysis_file, 'w', encoding='utf-8') as f:
                    json.dump(liquidity_analysis, f, indent=2)
                logger.info(f"Анализ ликвидности сохранен в {analysis_file}")
            except Exception as e:
                logger.error(f"Ошибка при сохранении анализа: {e}")
            
            return liquidity_analysis
        
        except Exception as e:
            logger.error(f"Ошибка при анализе ликвидности: {str(e)}")
            return []
    
    def _get_liquidity_category(self, score: float) -> str:
        """
        Определяет категорию ликвидности на основе оценки.
        
        Args:
            score: Оценка ликвидности от 0 до 100
            
        Returns:
            Категория ликвидности
        """
        if score >= 80:
            return "Очень высокая"
        elif score >= 60:
            return "Высокая"
        elif score >= 40:
            return "Средняя"
        elif score >= 20:
            return "Низкая"
        else:
            return "Очень низкая"


async def main():
    """
    Основная функция для запуска статистического арбитража.
    """
    # Настройка логгера для основной функции
    logger = logging.getLogger("main")
    logger.setLevel(logging.INFO)
    
    # Загрузка ключей API из файла или переменных окружения
    api_key = os.environ.get("DMARKET_API_KEY", "your_api_key")
    api_secret = os.environ.get("DMARKET_API_SECRET", "your_api_secret")
    
    # Инициализация класса статистического арбитража
    stat_arb = StatArbitrage(
        api_key=api_key,
        api_secret=api_secret,
        min_profit=5.0,
        min_liquidity=10.0
    )
    
    # Обновление данных о рынке
    logger.info("Обновление данных о рынке...")
    exchange_rates = await stat_arb.update_market_data(games=["CS:GO"], limit=200)
    logger.info(f"Получены данные о рынке для {len(exchange_rates)} предметов")
    
    # Поиск арбитражных возможностей
    logger.info("Поиск арбитражных возможностей...")
    opportunities = await stat_arb.find_arbitrage_opportunities()
    logger.info(f"Найдено {len(opportunities)} арбитражных возможностей")
    
    # Генерация целевых ордеров
    logger.info("Генерация целевых ордеров...")
    target_orders = await stat_arb.generate_target_orders()
    logger.info(f"Сгенерировано {len(target_orders)} целевых ордеров")
    
    # Анализ ликвидности предметов
    logger.info("Анализ ликвидности предметов...")
    liquidity_analysis = await stat_arb.analyze_items_liquidity(game="CS:GO", limit=100)
    
    # Вывод результатов анализа ликвидности
    if liquidity_analysis:
        logger.info("Топ-5 наиболее ликвидных предметов:")
        for i, item in enumerate(liquidity_analysis[:5], 1):
            logger.info(f"{i}. {item['name']} - Ликвидность: {item['liquidity_score']} "
                      f"({item['liquidity_category']}), Цена: ${item['price']:.2f}")
    
    # Выполнение ордеров (симуляция)
    logger.info("Симуляция выполнения ордеров...")
    executed_orders = await stat_arb.execute_target_orders()
    logger.info(f"Выполнено {len(executed_orders)} ордеров")
    
    logger.info("Завершение работы статистического арбитража")


if __name__ == "__main__":
    # Запуск основной функции
    asyncio.run(main())
