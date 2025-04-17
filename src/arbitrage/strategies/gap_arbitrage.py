"""
Модуль реализует стратегию гэп-арбитража для торговли предметами.

Гэп-арбитраж фокусируется на поиске и использовании разницы в ценах
на одинаковые предметы между разными платформами/маркетплейсами или
внутри одной платформы.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import time
import json

from src.api.api_wrapper import DMarketAPI
from src.config.config import Config
from src.database.db_wrapper import DatabaseWrapper
from src.utils.error_handler import TradingError, handle_exceptions, ErrorType
from src.arbitrage.base_strategy import BaseArbitrageStrategy, ArbitrageOpportunity

# Настройка логирования
logger = logging.getLogger(__name__)

class GapArbitrageStrategy(BaseArbitrageStrategy):
    """
    Стратегия гэп-арбитража, которая находит и использует разницу в ценах 
    на одинаковые предметы между разными платформами или внутри одной.
    """
    
    def __init__(
        self, 
        api: Optional[DMarketAPI] = None,
        db: Optional[DatabaseWrapper] = None,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Инициализирует стратегию гэп-арбитража.
        
        Args:
            api: API-клиент DMarket
            db: Интерфейс работы с базой данных
            config: Конфигурация стратегии (переопределяет настройки из общей конфигурации)
        """
        super().__init__(api, db)
        
        # Загружаем конфигурацию стратегии
        self.gap_config = config or Config.get_arbitrage_config("gap")
        
        # Настройки стратегии по умолчанию
        self.default_settings = {
            "min_price_difference_percent": 10.0,   # Минимальная разница в процентах
            "min_absolute_profit": 1.0,             # Минимальная абсолютная прибыль
            "max_item_count": 50,                   # Максимальное количество предметов для анализа
            "excluded_items": [],                    # Исключенные предметы
            "target_games": ["cs2", "dota2", "rust"], # Целевые игры
            "external_markets": {                    # Внешние рынки
                "steam": {
                    "enabled": True,
                    "min_price_ratio": 1.2          # Минимальное соотношение цен для арбитража
                },
                "third_party": {
                    "enabled": False,
                    "sources": []
                }
            },
            "refresh_interval": 600,                # Интервал обновления данных (секунды)
            "max_concurrent_requests": 5,           # Максимальное количество одновременных запросов
            "prioritize_liquidity": True,           # Приоритет ликвидности
            "fee_calculation": {                    # Расчёт комиссий
                "dmarket_fee": 7.0,                 # Комиссия DMarket (%)
                "steam_fee": 15.0,                  # Комиссия Steam (%)
                "include_withdrawal_fee": True      # Учитывать комиссию за вывод
            }
        }
        
        # Применяем настройки из конфигурации, либо используем значения по умолчанию
        self.settings = {**self.default_settings, **(self.gap_config or {})}
        
        # Кэширование данных для снижения нагрузки на API
        self.cache = {
            "steam_prices": {},
            "dmarket_items": {},
            "last_update": datetime.now() - timedelta(hours=1)  # Начальное значение для принудительного обновления
        }
        
        self.name = "Gap Arbitrage"
        self.description = "Ищет разницу в ценах на одинаковые предметы между разными рынками"
        
        # Семафор для ограничения одновременных запросов
        self.semaphore = asyncio.Semaphore(self.settings["max_concurrent_requests"])
        
        logger.info(f"Инициализирована стратегия гэп-арбитража с настройками: {json.dumps(self.settings, indent=2)}")
    
    @handle_exceptions(ErrorType.STRATEGY_ERROR)
    async def find_opportunities(self) -> List[ArbitrageOpportunity]:
        """
        Находит возможности для гэп-арбитража.
        
        Returns:
            Список найденных возможностей для арбитража
        """
        logger.info("Поиск возможностей для гэп-арбитража...")
        
        # Обновляем кэш, если нужно
        await self._update_cache_if_needed()
        
        opportunities = []
        
        # Обрабатываем все целевые игры
        for game in self.settings["target_games"]:
            logger.info(f"Анализ игры: {game}")
            
            # Ищем возможности внутри DMarket
            internal_opportunities = await self._find_internal_opportunities(game)
            if internal_opportunities:
                opportunities.extend(internal_opportunities)
                logger.info(f"Найдено {len(internal_opportunities)} внутренних возможностей для {game}")
            
            # Ищем возможности между DMarket и Steam, если включено
            if self.settings["external_markets"]["steam"]["enabled"]:
                steam_opportunities = await self._find_steam_opportunities(game)
                if steam_opportunities:
                    opportunities.extend(steam_opportunities)
                    logger.info(f"Найдено {len(steam_opportunities)} возможностей DMarket-Steam для {game}")
            
            # Можно добавить другие внешние рынки по аналогии
        
        # Сортируем по ожидаемой прибыли
        sorted_opportunities = sorted(
            opportunities, 
            key=lambda x: x.profit, 
            reverse=True
        )
        
        logger.info(f"Всего найдено {len(sorted_opportunities)} возможностей для гэп-арбитража")
        return sorted_opportunities
    
    async def _find_internal_opportunities(self, game: str) -> List[ArbitrageOpportunity]:
        """
        Ищет возможности для арбитража внутри платформы DMarket.
        
        Args:
            game: Код игры
            
        Returns:
            Список найденных возможностей
        """
        opportunities = []
        
        try:
            # Получаем список предметов с возможными несоответствиями в ценах
            items = await self.api.get_market_items(
                gameId=game,
                limit=self.settings["max_item_count"],
                orderBy="popularity",
                orderDir="desc"
            )
            
            if not items:
                logger.warning(f"Не удалось получить предметы для игры {game}")
                return []
            
            # Группируем предметы по названию
            items_by_title = {}
            for item in items:
                title = item.get("title", "")
                if not title or title in self.settings["excluded_items"]:
                    continue
                
                if title not in items_by_title:
                    items_by_title[title] = []
                
                items_by_title[title].append(item)
            
            # Анализируем предметы с несколькими предложениями
            for title, item_list in items_by_title.items():
                if len(item_list) < 2:
                    continue
                
                # Сортируем по цене
                sorted_items = sorted(item_list, key=lambda x: float(x.get("price", 0)))
                
                # Ищем значительный разрыв в ценах
                cheapest = sorted_items[0]
                cheapest_price = float(cheapest.get("price", 0))
                
                for i, item in enumerate(sorted_items[1:], 1):
                    current_price = float(item.get("price", 0))
                    
                    # Проверяем, достаточно ли велика разница
                    price_diff_percent = ((current_price - cheapest_price) / cheapest_price * 100) 
                    if price_diff_percent >= self.settings["min_price_difference_percent"]:
                        
                        # Расчет прибыли с учетом комиссий
                        fee_percent = self.settings["fee_calculation"]["dmarket_fee"] / 100
                        profit = current_price * (1 - fee_percent) - cheapest_price
                        
                        # Если прибыль достаточна, добавляем возможность
                        if profit >= self.settings["min_absolute_profit"]:
                            opp = ArbitrageOpportunity(
                                buy_item=cheapest,
                                sell_item=item,
                                buy_market="DMarket",
                                sell_market="DMarket",
                                profit=profit,
                                profit_percent=price_diff_percent,
                                game=game,
                                strategy="gap",
                                timestamp=datetime.now().isoformat(),
                                details={
                                    "buy_price": cheapest_price,
                                    "sell_price": current_price,
                                    "fee": fee_percent * 100,
                                    "confidence": self._calculate_confidence(cheapest, item)
                                }
                            )
                            opportunities.append(opp)
                    
                    # Если нашли более дешевый предмет, обновляем для следующего сравнения
                    if i < len(sorted_items) - 1 and current_price < cheapest_price * 1.05:
                        cheapest = item
                        cheapest_price = current_price
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Ошибка при поиске внутренних возможностей арбитража: {e}")
            return []
    
    async def _find_steam_opportunities(self, game: str) -> List[ArbitrageOpportunity]:
        """
        Ищет возможности для арбитража между DMarket и Steam.
        
        Args:
            game: Код игры
            
        Returns:
            Список найденных возможностей
        """
        opportunities = []
        steam_prices = self.cache["steam_prices"].get(game, {})
        
        if not steam_prices:
            logger.warning(f"Нет данных о ценах Steam для игры {game}")
            return []
        
        try:
            # Проверяем наличие кэшированных данных DMarket
            if game not in self.cache["dmarket_items"]:
                # Если нет, запрашиваем популярные предметы
                items = await self.api.get_market_items(
                    gameId=game,
                    limit=self.settings["max_item_count"],
                    orderBy="popularity",
                    orderDir="desc"
                )
                
                if not items:
                    logger.warning(f"Не удалось получить предметы DMarket для игры {game}")
                    return []
                
                # Сохраняем в кэш
                self.cache["dmarket_items"][game] = items
            else:
                items = self.cache["dmarket_items"][game]
            
            # Минимальное соотношение цен для арбитража
            min_price_ratio = self.settings["external_markets"]["steam"]["min_price_ratio"]
            
            # Обрабатываем каждый предмет
            for item in items:
                title = item.get("title", "")
                if not title or title in self.settings["excluded_items"]:
                    continue
                
                # Получаем цену DMarket и Steam
                dmarket_price = float(item.get("price", 0))
                steam_price = steam_prices.get(title, 0)
                
                if not dmarket_price or not steam_price:
                    continue
                
                # Ищем разницу в ценах DMarket < Steam (покупка на DMarket, продажа на Steam)
                if steam_price > dmarket_price * min_price_ratio:
                    # Рассчитываем прибыль с учетом комиссий Steam
                    steam_fee_percent = self.settings["fee_calculation"]["steam_fee"] / 100
                    profit = steam_price * (1 - steam_fee_percent) - dmarket_price
                    
                    # Если есть комиссия за вывод, учитываем её
                    if self.settings["fee_calculation"]["include_withdrawal_fee"]:
                        withdrawal_fee = min(1.0, dmarket_price * 0.02)  # Примерная комиссия 2%, минимум 1 USD
                        profit -= withdrawal_fee
                    
                    profit_percent = (profit / dmarket_price) * 100
                    
                    # Если прибыль достаточна, добавляем возможность
                    if profit >= self.settings["min_absolute_profit"] and profit_percent >= self.settings["min_price_difference_percent"]:
                        opp = ArbitrageOpportunity(
                            buy_item=item,
                            sell_item={
                                "title": title,
                                "price": str(steam_price),
                                "market": "Steam"
                            },
                            buy_market="DMarket",
                            sell_market="Steam",
                            profit=profit,
                            profit_percent=profit_percent,
                            game=game,
                            strategy="gap_steam",
                            timestamp=datetime.now().isoformat(),
                            details={
                                "buy_price": dmarket_price,
                                "sell_price": steam_price,
                                "steam_fee": steam_fee_percent * 100,
                                "confidence": 0.7,  # Фиксированное значение для Steam, т.к. нет подробных данных
                                "notes": "Требуется вывод предмета в Steam"
                            }
                        )
                        opportunities.append(opp)
                
                # Ищем разницу в ценах Steam < DMarket (покупка на Steam, продажа на DMarket)
                # Не реализуем эту часть, так как требуется сложная логика работы с Steam API
                # и управление инвентарем Steam, что выходит за рамки данной стратегии
            
            return opportunities
            
        except Exception as e:
            logger.error(f"Ошибка при поиске возможностей арбитража DMarket-Steam: {e}")
            return []
    
    async def _update_cache_if_needed(self) -> None:
        """
        Обновляет кэш данных, если прошло достаточно времени с последнего обновления.
        """
        # Проверяем, нужно ли обновлять кэш
        now = datetime.now()
        time_since_update = (now - self.cache["last_update"]).total_seconds()
        
        if time_since_update < self.settings["refresh_interval"]:
            logger.debug(f"Используем кэшированные данные (обновление через {self.settings['refresh_interval'] - time_since_update:.1f} сек)")
            return
        
        logger.info("Обновление кэшированных данных...")
        
        # Обновляем данные по ценам Steam
        if self.settings["external_markets"]["steam"]["enabled"]:
            for game in self.settings["target_games"]:
                try:
                    # В реальном сценарии здесь будет обращение к API или парсинг данных Steam
                    # Для демонстрации используем заглушку
                    await self._update_steam_prices(game)
                except Exception as e:
                    logger.error(f"Ошибка при обновлении цен Steam для {game}: {e}")
        
        # Обновляем метку времени последнего обновления
        self.cache["last_update"] = now
        logger.info("Кэш данных обновлен")
    
    async def _update_steam_prices(self, game: str) -> None:
        """
        Обновляет кэш цен Steam для заданной игры.
        
        Args:
            game: Код игры
        """
        # В реальном приложении здесь будет вызов API Steam или парсинг данных
        # Для демонстрации используем заглушку с примерными данными
        
        if game not in self.cache["steam_prices"]:
            self.cache["steam_prices"][game] = {}
        
        # Получаем предметы из DMarket для получения их названий
        if game in self.cache["dmarket_items"]:
            items = self.cache["dmarket_items"][game]
        else:
            items = await self.api.get_market_items(
                gameId=game,
                limit=self.settings["max_item_count"],
                orderBy="popularity",
                orderDir="desc"
            )
            self.cache["dmarket_items"][game] = items
        
        # Для каждого предмета генерируем примерную цену Steam
        # В реальном приложении здесь будет получение реальных данных с рынка Steam
        steam_prices = {}
        for item in items:
            title = item.get("title", "")
            if not title:
                continue
            
            # Примерная логика генерации цены Steam (для демонстрации)
            dmarket_price = float(item.get("price", 0))
            
            # Цена Steam случайно выше или ниже DMarket
            import random
            ratio = random.uniform(0.8, 1.3)  # Случайное соотношение цены
            steam_price = dmarket_price * ratio
            
            steam_prices[title] = steam_price
        
        # Обновляем кэш
        self.cache["steam_prices"][game] = steam_prices
        logger.debug(f"Обновлены цены Steam для {game}: {len(steam_prices)} предметов")
    
    def _calculate_confidence(self, buy_item: Dict[str, Any], sell_item: Dict[str, Any]) -> float:
        """
        Рассчитывает уровень уверенности в возможности арбитража.
        
        Args:
            buy_item: Данные о предмете для покупки
            sell_item: Данные о предмете для продажи
            
        Returns:
            Уровень уверенности от 0 до 1
        """
        # Проверяем соответствие предметов (должны быть идентичны)
        if buy_item.get("title") != sell_item.get("title"):
            return 0.0
        
        # Базовая уверенность
        confidence = 0.8
        
        # Корректируем уверенность на основе разницы в цене (слишком большая разница может быть подозрительной)
        buy_price = float(buy_item.get("price", 0))
        sell_price = float(sell_item.get("price", 0))
        
        if buy_price > 0:
            price_diff_ratio = sell_price / buy_price
            
            # Если разница слишком велика, снижаем уверенность
            if price_diff_ratio > 2.0:
                confidence -= 0.3
            elif price_diff_ratio > 1.5:
                confidence -= 0.1
            
            # Если цена покупки очень низкая, это может быть ошибкой или нетоварным предметом
            if buy_price < 1.0:
                confidence -= 0.2
        
        # Проверяем ликвидность предметов (если доступна)
        buy_market_hash = buy_item.get("marketHashName", "")
        sell_market_hash = sell_item.get("marketHashName", "")
        
        if buy_market_hash != sell_market_hash and buy_market_hash and sell_market_hash:
            confidence -= 0.2
        
        # Проверяем доступность
        if not buy_item.get("inMarket", True) or not sell_item.get("inMarket", True):
            confidence -= 0.4
        
        # Ограничиваем значение от 0 до 1
        return max(0.0, min(1.0, confidence))
    
    @handle_exceptions(ErrorType.STRATEGY_ERROR)
    async def execute_arbitrage(self, opportunity: ArbitrageOpportunity) -> bool:
        """
        Выполняет арбитражную операцию.
        
        Args:
            opportunity: Арбитражная возможность для исполнения
            
        Returns:
            True, если операция успешно выполнена, иначе False
        """
        logger.info(f"Выполнение гэп-арбитража: {opportunity.buy_item.get('title')} "
                   f"({opportunity.profit_percent:.2f}%, ${opportunity.profit:.2f})")
        
        # Проверяем достаточность баланса
        balance = await self.api.get_balance()
        buy_price = float(opportunity.buy_item.get("price", 0))
        
        if balance < buy_price:
            logger.warning(f"Недостаточно средств для покупки: {balance} < {buy_price}")
            return False
        
        # Проверяем, что предмет всё ещё доступен для покупки
        item_id = opportunity.buy_item.get("itemId")
        if not item_id:
            logger.error("Отсутствует идентификатор предмета для покупки")
            return False
        
        # Проверяем актуальность предложения
        try:
            item_details = await self.api.get_item_details(item_id)
            
            if not item_details or not item_details.get("inMarket", False):
                logger.warning(f"Предмет больше не доступен на рынке: {item_id}")
                return False
            
            current_price = float(item_details.get("price", 0))
            if current_price > buy_price * 1.05:
                logger.warning(f"Цена предмета увеличилась: {current_price} > {buy_price}")
                return False
            
        except Exception as e:
            logger.error(f"Ошибка при проверке актуальности предмета: {e}")
            return False
        
        # Если арбитраж с внешней платформой, вывести предупреждение
        if opportunity.sell_market != "DMarket":
            logger.warning(f"Арбитраж с {opportunity.sell_market} требует ручного завершения")
            # Записываем в БД для дальнейшего отслеживания
            if self.db:
                await self.db.save_arbitrage_opportunity(opportunity)
            return False
        
        # Выполняем покупку
        try:
            logger.info(f"Покупка предмета {item_id} за ${buy_price}")
            purchase_result = await self.api.buy_item(item_id)
            
            if not purchase_result or not purchase_result.get("success", False):
                logger.error(f"Ошибка при покупке предмета: {purchase_result}")
                return False
            
            # Ожидаем завершения покупки и получение предмета в инвентарь
            inventory_item = await self._wait_for_inventory_item(item_id)
            if not inventory_item:
                logger.error("Не удалось получить предмет в инвентарь")
                return False
            
            # Выставляем предмет на продажу
            sell_price = float(opportunity.sell_item.get("price", 0))
            adjusted_sell_price = sell_price * 0.95  # Небольшая скидка для быстрой продажи
            
            logger.info(f"Выставление предмета {item_id} на продажу за ${adjusted_sell_price}")
            listing_result = await self.api.list_item_for_sale(
                inventory_item.get("inventoryItemId"), 
                adjusted_sell_price
            )
            
            if not listing_result or not listing_result.get("success", False):
                logger.error(f"Ошибка при выставлении предмета на продажу: {listing_result}")
                return False
            
            # Сохраняем информацию о выполненной операции
            if self.db:
                # Обновляем статус операции
                opportunity.status = "executed"
                opportunity.execution_details = {
                    "buy_transaction_id": purchase_result.get("transactionId", ""),
                    "sell_listing_id": listing_result.get("listingId", ""),
                    "buy_time": datetime.now().isoformat(),
                    "adjusted_sell_price": adjusted_sell_price
                }
                await self.db.save_arbitrage_opportunity(opportunity)
            
            logger.info(f"Гэп-арбитраж успешно выполнен: {item_id}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении арбитража: {e}")
            return False
    
    async def _wait_for_inventory_item(self, item_id: str, max_attempts: int = 10) -> Optional[Dict[str, Any]]:
        """
        Ждет появления предмета в инвентаре после покупки.
        
        Args:
            item_id: Идентификатор предмета
            max_attempts: Максимальное количество попыток
            
        Returns:
            Данные о предмете в инвентаре или None, если предмет не найден
        """
        logger.info(f"Ожидание получения предмета {item_id} в инвентарь...")
        
        for attempt in range(max_attempts):
            try:
                # Получаем инвентарь
                inventory = await self.api.get_user_inventory()
                
                # Ищем предмет в инвентаре
                for inv_item in inventory:
                    if inv_item.get("itemId") == item_id:
                        logger.info(f"Предмет {item_id} получен в инвентарь")
                        return inv_item
                
                # Предмет не найден, ждем и пробуем снова
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Ошибка при проверке инвентаря (попытка {attempt+1}/{max_attempts}): {e}")
                await asyncio.sleep(2)
        
        logger.warning(f"Предмет {item_id} не найден в инвентаре после {max_attempts} попыток")
        return None

# Функция для тестирования модуля
async def test_gap_arbitrage():
    """
    Тестирует функциональность модуля гэп-арбитража.
    """
    # Инициализация стратегии
    strategy = GapArbitrageStrategy()
    
    # Поиск возможностей
    opportunities = await strategy.find_opportunities()
    
    # Вывод результатов
    print(f"\nНайдено {len(opportunities)} возможностей для гэп-арбитража:")
    
    for i, opp in enumerate(opportunities[:5], 1):
        print(f"\n{i}. {opp.buy_item.get('title')} - {opp.game}")
        print(f"   Покупка: ${float(opp.buy_item.get('price', 0)):.2f} ({opp.buy_market})")
        print(f"   Продажа: ${float(opp.sell_item.get('price', 0)):.2f} ({opp.sell_market})")
        print(f"   Прибыль: ${opp.profit:.2f} ({opp.profit_percent:.2f}%)")
        print(f"   Уверенность: {opp.details.get('confidence', 0):.2f}")
    
    print("\nТестирование завершено")

if __name__ == "__main__":
    # Настраиваем логирование
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Запускаем тест
    asyncio.run(test_gap_arbitrage()) 