"""
Модуль для осуществления торговых операций на основе данных из нескольких источников.

Реализует функциональность для автоматизированной торговли между разными площадками
на основе арбитражных возможностей и аналитики, полученной из multi_source_market_provider.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional, Union, Callable
from datetime import datetime, timedelta

from src.api.multi_source_provider import get_market_aggregator, MarketDataProvider
from src.api.multi_source_market_provider import (
    get_multi_source_provider, find_arbitrage_opportunities
)
from src.utils.error_handler import handle_exceptions, ErrorType, TradingError
from src.api.api_wrapper import DMarketAPI

# Настройка логирования
logger = logging.getLogger(__name__)


class MultiSourceTrader:
    """
    Реализует стратегии торговли на основе данных из нескольких источников.
    
    Автоматизирует процесс выявления и использования арбитражных возможностей
    между разными торговыми площадками.
    """
    
    def __init__(
        self, 
        min_profit_percent: float = 10.0,
        min_absolute_profit: float = 1.0,
        max_trades_per_hour: int = 5,
        risk_threshold: float = 0.7,
        auto_execute: bool = False
    ):
        """
        Инициализирует трейдер.
        
        Args:
            min_profit_percent: Минимальный процент прибыли для выполнения сделки
            min_absolute_profit: Минимальная абсолютная прибыль в USD для сделки
            max_trades_per_hour: Максимальное количество сделок в час
            risk_threshold: Порог риска (0-1), ниже которого сделки не выполняются
            auto_execute: Автоматически выполнять сделки без подтверждения
        """
        self.min_profit_percent = min_profit_percent
        self.min_absolute_profit = min_absolute_profit
        self.max_trades_per_hour = max_trades_per_hour
        self.risk_threshold = risk_threshold
        self.auto_execute = auto_execute
        
        self.market_provider = get_multi_source_provider()
        self.market_aggregator = get_market_aggregator()
        
        self.executed_trades = []
        self.last_trade_time = None
        self.trading_locks = {}  # блокировки для предотвращения повторной торговли
    
    async def scan_for_opportunities(
        self, 
        game_code: str = "a8db",
        max_items: int = 100,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Сканирует рынок на наличие арбитражных возможностей.
        
        Args:
            game_code: Код игры
            max_items: Максимальное количество проверяемых предметов
            min_price: Минимальная цена предмета
            max_price: Максимальная цена предмета
            
        Returns:
            List[Dict[str, Any]]: Список выявленных возможностей
        """
        logger.info(f"Сканирование рынка на наличие арбитражных возможностей для {game_code}...")
        
        # Находим арбитражные возможности
        opportunities = await find_arbitrage_opportunities(
            game_code=game_code,
            min_price_diff=self.min_profit_percent,
            limit=max_items
        )
        
        # Фильтруем по дополнительным параметрам
        filtered_opportunities = []
        
        for opp in opportunities:
            # Проверяем ограничения по цене
            if min_price and opp["buy_price"] < min_price:
                continue
            if max_price and opp["buy_price"] > max_price:
                continue
            
            # Проверяем абсолютную прибыль
            if opp["price_diff"] < self.min_absolute_profit:
                continue
            
            # Проверяем, не заблокирован ли предмет для торговли
            item_key = f"{game_code}:{opp['item_name']}"
            if item_key in self.trading_locks:
                lock_time = self.trading_locks[item_key]
                if datetime.now() < lock_time:
                    logger.debug(f"Предмет {opp['item_name']} заблокирован для торговли до {lock_time}")
                    continue
                else:
                    # Блокировка истекла, удаляем ее
                    del self.trading_locks[item_key]
            
            # Получаем дополнительную информацию для анализа рисков
            try:
                details = await self.market_provider.get_item_details(
                    game_code, opp["item_name"], sources=[opp["buy_from"], opp["sell_to"]]
                )
                
                # Анализируем риски
                risk_score = self._calculate_risk_score(opp, details)
                
                # Добавляем информацию о риске к возможности
                opp["risk_score"] = risk_score
                opp["risk_level"] = self._risk_level_name(risk_score)
                opp["details"] = details
                
                # Проверяем порог риска
                if risk_score <= self.risk_threshold:
                    filtered_opportunities.append(opp)
                else:
                    logger.debug(
                        f"Возможность для {opp['item_name']} отклонена из-за высокого риска: "
                        f"{risk_score:.2f} > {self.risk_threshold}"
                    )
            except Exception as e:
                logger.warning(f"Ошибка при анализе рисков для {opp['item_name']}: {e}")
        
        # Сортируем по прибыльности (от большей к меньшей)
        filtered_opportunities.sort(key=lambda x: x["price_diff_percent"], reverse=True)
        
        logger.info(f"Найдено {len(filtered_opportunities)} подходящих арбитражных возможностей")
        return filtered_opportunities
    
    def _calculate_risk_score(self, opportunity: Dict[str, Any], details: Dict[str, Any]) -> float:
        """
        Рассчитывает оценку риска для арбитражной возможности.
        
        Args:
            opportunity: Информация о возможности
            details: Детальная информация о предмете
            
        Returns:
            float: Оценка риска от 0 (минимальный) до 1 (максимальный)
        """
        stats = details.get("stats", {})
        
        # Базовый риск основан на волатильности
        base_risk = stats.get("price_volatility", 0.5)
        
        # Учитываем тренд цены
        trend = stats.get("price_trend", "stable")
        if trend == "down":
            # Если цена падает, риск выше
            trend_factor = 0.3
        elif trend == "up":
            # Если цена растет, риск ниже
            trend_factor = -0.2
        else:
            # Если цена стабильна, нейтральный фактор
            trend_factor = 0
        
        # Учитываем достоверность данных
        confidence = stats.get("confidence_score", 0.5)
        confidence_factor = (1 - confidence) * 0.3  # чем ниже достоверность, тем выше риск
        
        # Учитываем разницу в цене (чем больше разница, тем меньше риск)
        price_diff_percent = opportunity.get("price_diff_percent", 0)
        price_diff_factor = -0.01 * min(price_diff_percent, 20)  # максимум -0.2 (при 20% разнице)
        
        # Итоговая оценка риска (ограничиваем диапазоном 0-1)
        risk_score = max(0, min(1, base_risk + trend_factor + confidence_factor + price_diff_factor))
        
        return risk_score
    
    def _risk_level_name(self, risk_score: float) -> str:
        """
        Возвращает текстовое представление уровня риска.
        
        Args:
            risk_score: Числовая оценка риска от 0 до 1
            
        Returns:
            str: Текстовое описание уровня риска
        """
        if risk_score < 0.2:
            return "очень низкий"
        elif risk_score < 0.4:
            return "низкий"
        elif risk_score < 0.6:
            return "средний"
        elif risk_score < 0.8:
            return "высокий"
        else:
            return "очень высокий"
    
    async def execute_trade(self, opportunity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет торговую операцию на основе арбитражной возможности.
        
        Args:
            opportunity: Информация о возможности
            
        Returns:
            Dict[str, Any]: Результат операции
        """
        if not self._can_execute_trade():
            raise TradingError(
                "Превышен лимит количества сделок в час",
                ErrorType.RATE_LIMIT_ERROR
            )
        
        logger.info(f"Выполнение торговой операции для {opportunity['item_name']}...")
        
        try:
            # Проверяем доступность предмета
            buy_source = opportunity["buy_from"]
            sell_source = opportunity["sell_to"]
            item_name = opportunity["item_name"]
            game_code = opportunity.get("game", "a8db")
            
            # Получаем провайдеры для источников
            buy_provider = self.market_aggregator.get_provider(buy_source)
            sell_provider = self.market_aggregator.get_provider(sell_source)
            
            if not buy_provider or not sell_provider:
                raise TradingError(
                    f"Не найдены провайдеры для {buy_source} или {sell_source}",
                    ErrorType.CONFIGURATION_ERROR
                )
            
            # Проверяем актуальность цены (повторно получаем информацию)
            latest_info = await self.market_aggregator.get_price_comparison(game_code, item_name)
            
            current_buy_price = latest_info.get("prices", {}).get(buy_source)
            current_sell_price = latest_info.get("prices", {}).get(sell_source)
            
            if not current_buy_price or not current_sell_price:
                raise TradingError(
                    f"Не удалось получить актуальные цены для {item_name}",
                    ErrorType.DATA_ERROR
                )
            
            # Проверяем, что условия все еще выгодны
            current_diff_percent = ((current_sell_price / current_buy_price) - 1) * 100
            current_diff = current_sell_price - current_buy_price
            
            if (current_diff_percent < self.min_profit_percent or 
                current_diff < self.min_absolute_profit):
                raise TradingError(
                    f"Условия для {item_name} больше не выгодны. "
                    f"Текущая разница: {current_diff_percent:.2f}% (${current_diff:.2f})",
                    ErrorType.MARKET_CONDITION_ERROR
                )
            
            # В реальной реализации здесь будет код для:
            # 1. Покупки предмета на первой площадке
            # 2. Перемещения/передачи предмета на вторую площадку
            # 3. Продажи предмета на второй площадке
            
            # Пока просто имитируем успешную сделку
            trade_result = {
                "item_name": item_name,
                "game": game_code,
                "buy_source": buy_source,
                "buy_price": current_buy_price,
                "sell_source": sell_source,
                "sell_price": current_sell_price,
                "profit": current_diff,
                "profit_percent": current_diff_percent,
                "status": "simulated",  # в реальной реализации здесь будет "completed"
                "timestamp": datetime.now().isoformat(),
                "error": None
            }
            
            # Обновляем статистику
            self.executed_trades.append(trade_result)
            self.last_trade_time = datetime.now()
            
            # Блокируем предмет для повторной торговли на некоторое время
            item_key = f"{game_code}:{item_name}"
            self.trading_locks[item_key] = datetime.now() + timedelta(hours=6)
            
            logger.info(f"Торговая операция для {item_name} успешно выполнена с прибылью ${current_diff:.2f}")
            
            return trade_result
            
        except Exception as e:
            logger.error(f"Ошибка при выполнении торговой операции для {opportunity['item_name']}: {e}")
            
            # Возвращаем информацию об ошибке
            return {
                "item_name": opportunity["item_name"],
                "status": "failed",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    def _can_execute_trade(self) -> bool:
        """
        Проверяет, можно ли выполнить торговую операцию согласно ограничениям.
        
        Returns:
            bool: True, если можно выполнить операцию, иначе False
        """
        # Если еще не было сделок, разрешаем
        if not self.last_trade_time:
            return True
        
        # Проверяем, сколько сделок было за последний час
        hour_ago = datetime.now() - timedelta(hours=1)
        trades_in_last_hour = sum(
            1 for trade in self.executed_trades
            if "timestamp" in trade and datetime.fromisoformat(trade["timestamp"]) > hour_ago
        )
        
        return trades_in_last_hour < self.max_trades_per_hour
    
    async def get_trading_statistics(self) -> Dict[str, Any]:
        """
        Возвращает статистику торговых операций.
        
        Returns:
            Dict[str, Any]: Статистика торговых операций
        """
        total_trades = len(self.executed_trades)
        successful_trades = sum(1 for trade in self.executed_trades if trade.get("status") != "failed")
        total_profit = sum(trade.get("profit", 0) for trade in self.executed_trades 
                          if trade.get("status") != "failed")
        
        # Статистика за последние 24 часа
        day_ago = datetime.now() - timedelta(days=1)
        trades_in_last_day = [
            trade for trade in self.executed_trades
            if "timestamp" in trade and datetime.fromisoformat(trade["timestamp"]) > day_ago
        ]
        
        day_trades_count = len(trades_in_last_day)
        day_profit = sum(trade.get("profit", 0) for trade in trades_in_last_day 
                        if trade.get("status") != "failed")
        
        # Самые прибыльные предметы
        items_profit = {}
        for trade in self.executed_trades:
            if trade.get("status") != "failed":
                item_name = trade.get("item_name", "unknown")
                if item_name in items_profit:
                    items_profit[item_name] += trade.get("profit", 0)
                else:
                    items_profit[item_name] = trade.get("profit", 0)
        
        top_items = sorted(
            [{"item": k, "profit": v} for k, v in items_profit.items()],
            key=lambda x: x["profit"],
            reverse=True
        )[:5]  # топ-5 предметов
        
        return {
            "total_trades": total_trades,
            "successful_trades": successful_trades,
            "success_rate": (successful_trades / total_trades * 100) if total_trades > 0 else 0,
            "total_profit": total_profit,
            "average_profit_per_trade": (total_profit / successful_trades) if successful_trades > 0 else 0,
            "last_24h_trades": day_trades_count,
            "last_24h_profit": day_profit,
            "top_profitable_items": top_items,
            "last_trade_time": self.last_trade_time.isoformat() if self.last_trade_time else None,
            "trades_in_last_hour": sum(
                1 for trade in self.executed_trades
                if "timestamp" in trade and 
                datetime.fromisoformat(trade["timestamp"]) > (datetime.now() - timedelta(hours=1))
            )
        }
    
    async def run_trading_cycle(
        self, 
        game_code: str = "a8db",
        max_trades: int = 3,
        confirm_callback: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Выполняет полный цикл торговли: поиск возможностей и их реализацию.
        
        Args:
            game_code: Код игры
            max_trades: Максимальное количество сделок за цикл
            confirm_callback: Функция для подтверждения сделки
            
        Returns:
            List[Dict[str, Any]]: Результаты выполненных сделок
        """
        logger.info(f"Запуск торгового цикла для {game_code}...")
        
        # Находим возможности для арбитража
        opportunities = await self.scan_for_opportunities(game_code)
        
        if not opportunities:
            logger.info("Не найдено подходящих арбитражных возможностей")
            return []
        
        # Выполняем сделки
        executed_trades = []
        
        for opp in opportunities[:max_trades]:
            # Проверяем, можно ли выполнить еще одну сделку
            if not self._can_execute_trade():
                logger.warning("Достигнут лимит сделок в час. Прерываем цикл торговли.")
                break
            
            # Запрашиваем подтверждение, если нужно
            if not self.auto_execute and confirm_callback:
                if not confirm_callback(opp):
                    logger.info(f"Сделка для {opp['item_name']} отклонена пользователем")
                    continue
            
            # Выполняем сделку
            trade_result = await self.execute_trade(opp)
            executed_trades.append(trade_result)
            
            # Если сделка не удалась, продолжаем с другими возможностями
            if trade_result.get("status") == "failed":
                logger.warning(f"Не удалось выполнить сделку для {opp['item_name']}: {trade_result.get('error')}")
                continue
            
            # Делаем небольшую паузу между сделками
            await asyncio.sleep(2)
        
        # Возвращаем результаты
        return executed_trades


# Глобальный экземпляр трейдера
_multi_source_trader: Optional[MultiSourceTrader] = None


def get_multi_source_trader(
    min_profit_percent: float = 10.0,
    auto_execute: bool = False
) -> MultiSourceTrader:
    """
    Получает глобальный экземпляр трейдера.
    
    Args:
        min_profit_percent: Минимальный процент прибыли для сделки
        auto_execute: Автоматически выполнять сделки
        
    Returns:
        MultiSourceTrader: Экземпляр трейдера
    """
    global _multi_source_trader
    if _multi_source_trader is None:
        _multi_source_trader = MultiSourceTrader(
            min_profit_percent=min_profit_percent,
            auto_execute=auto_execute
        )
    
    return _multi_source_trader


async def find_and_execute_trades(
    game_code: str = "a8db",
    min_profit: float = 10.0,
    max_trades: int = 3,
    auto_execute: bool = False
) -> List[Dict[str, Any]]:
    """
    Находит и выполняет выгодные сделки.
    
    Args:
        game_code: Код игры
        min_profit: Минимальный процент прибыли
        max_trades: Максимальное количество сделок
        auto_execute: Автоматически выполнять сделки
        
    Returns:
        List[Dict[str, Any]]: Результаты выполненных сделок
    """
    trader = get_multi_source_trader(min_profit, auto_execute)
    
    # Запускаем торговый цикл
    return await trader.run_trading_cycle(
        game_code=game_code,
        max_trades=max_trades,
        # Если auto_execute=False, запрашиваем подтверждение через консоль
        confirm_callback=None if auto_execute else lambda opp: input(
            f"Выполнить сделку для {opp['item_name']} "
            f"(купить за ${opp['buy_price']:.2f} на {opp['buy_from']}, "
            f"продать за ${opp['sell_price']:.2f} на {opp['sell_to']})? [y/N] "
        ).lower() == 'y'
    ) 