#!/usr/bin/env python
"""
Скрипт для тестирования арбитражных возможностей на DMarket.

Этот скрипт анализирует предметы из игр CS2, Dota 2, TF2 и Rust на платформе DMarket
для поиска потенциально прибыльных возможностей покупки и продажи.
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import time
import datetime
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dotenv import load_dotenv

# Настройка путей
current_dir = Path(__file__).parent.absolute()
dm_dir = current_dir / "DM"

# Создаем простую реализацию config модуля
# Это будет использоваться вместо сложной конфигурации из исходного проекта
class SimpleConfig:
    def __init__(self):
        class Marketplace:
            def __init__(self):
                self.BITSKINS_API_KEY = os.getenv("BITSKINS_API_KEY", "")
                self.BITSKINS_SECRET_KEY = os.getenv("BITSKINS_SECRET_KEY", "")
                self.CSMONEY_API_URL = "https://cs.money/api"
                self.CSMONEY_API_KEY = os.getenv("CSMONEY_API_KEY", "")
                self.BACKPACKTF_API_URL = "https://backpack.tf/api"
                self.BACKPACKTF_API_KEY = os.getenv("BACKPACKTF_API_KEY", "")
                
        class API:
            def __init__(self):
                self.DMARKET_API_URL = "https://api.dmarket.com"
                self.DMARKET_API_KEY = os.getenv("DMARKET_API_KEY", "")
                self.DMARKET_API_SECRET = os.getenv("DMARKET_API_SECRET", "")
                self.API_TIMEOUT = 30
                self.API_MAX_RETRIES = 3
                
        class Logging:
            def __init__(self):
                self.LOG_LEVEL = "INFO"
                self.LOG_FILE = "logs/bot.log"
                
        class Trading:
            def __init__(self):
                self.MIN_PROFIT_PERCENT = 5.0
                self.MAX_ITEMS_TO_MONITOR = 200
                self.CHECK_INTERVAL = 300
                
        self.marketplace = Marketplace()
        self.api = API()
        self.logging = Logging()
        self.trading = Trading()
        self.DMARKET_API_KEY = os.getenv("DMARKET_API_KEY", "")
        self.DMARKET_API_SECRET = os.getenv("DMARKET_API_SECRET", "")

# Создаем экземпляр конфигурации
config = SimpleConfig()

# Добавляем текущую директорию и директорию DM в путь
sys.path.append(str(current_dir))
sys.path.append(str(dm_dir))

# Инжекция нашего модуля config в sys.modules для использования в импортируемых модулях
sys.modules['config'] = type('', (), {'config': config})

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
log_dir = current_dir / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"arbitrage_test_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("arbitrage_test")

# Импорт API DMarket
try:
    from DM.api_wrapper import DMarketAPI
    logger.info("Импортирован модуль DMarketAPI из DM/api_wrapper.py")
except ImportError as e:
    logger.critical(f"Не удалось импортировать модуль DMarketAPI из DM/api_wrapper.py: {e}")
    sys.exit(1)

# Импорт функций арбитража, если они доступны
try:
    from DM.dmarket_arbitrage_finder import DMarketArbitrageFinder
    logger.info("Импортирован модуль DMarketArbitrageFinder из DM/dmarket_arbitrage_finder.py")
    USE_ARBITRAGE_FINDER = True
except ImportError as e:
    logger.warning(f"Не удалось импортировать модуль DMarketArbitrageFinder из DM: {e}")
    USE_ARBITRAGE_FINDER = False

# Константы и конфигурация
DMARKET_API_KEY = os.getenv("DMARKET_API_KEY")
DMARKET_API_SECRET = os.getenv("DMARKET_API_SECRET")

if not DMARKET_API_KEY or not DMARKET_API_SECRET:
    logger.critical("Не указаны DMARKET_API_KEY или DMARKET_API_SECRET в файле .env")
    sys.exit(1)

# Идентификаторы игр для DMarket API
GAME_IDS = {
    "CS2": "a8db",
    "DOTA2": "9a92",
    "TF2": "tf2", 
    "RUST": "rust"  # На основе предположения, что для Rust используется строка "rust"
}

# Класс для работы с DMarket API и поиска арбитражных возможностей
class ArbitrageAnalyzer:
    def __init__(self, api_key: str, api_secret: str):
        self.api = DMarketAPI(api_key, api_secret)
        self.logger = logging.getLogger("ArbitrageAnalyzer")
        
        # Инициализируем DMarketArbitrageFinder, если доступен
        self.arbitrage_finder = None
        if USE_ARBITRAGE_FINDER:
            self.arbitrage_finder = DMarketArbitrageFinder(api_key, api_secret)
    
    async def analyze_game(
        self, 
        game_id: str, 
        game_name: str,
        price_from: float = 1.0, 
        price_to: float = 100.0, 
        min_profit_percent: float = 5.0,
        max_items: int = 200
    ) -> List[Dict[str, Any]]:
        """
        Анализирует предметы из указанной игры для поиска арбитражных возможностей.
        
        Args:
            game_id: Идентификатор игры для DMarket API
            game_name: Название игры для логирования
            price_from: Минимальная цена предметов
            price_to: Максимальная цена предметов
            min_profit_percent: Минимальный процент прибыли
            max_items: Максимальное количество предметов для анализа
            
        Returns:
            Список потенциально прибыльных предметов
        """
        self.logger.info(f"Анализ игры {game_name} (ID: {game_id})")
        
        # Если доступен DMarketArbitrageFinder, используем его
        if self.arbitrage_finder is not None:
            try:
                opportunities = await self.arbitrage_finder.find_arbitrage_opportunities(
                    game_id=game_id,
                    price_from=price_from,
                    price_to=price_to,
                    min_profit_percent=min_profit_percent,
                    max_items=max_items
                )
                self.logger.info(f"Найдено {len(opportunities)} возможностей для {game_name} с помощью ArbitrageFinder")
                return opportunities
            except Exception as e:
                self.logger.error(f"Ошибка при использовании ArbitrageFinder для {game_name}: {e}")
                # Продолжаем с базовой логикой в случае ошибки
        
        # Базовая логика поиска прибыльных предметов
        try:
            # Получаем предметы с рынка
            response = await self.api.get_market_items_async(
                game_id=game_id,
                limit=max_items,
                price_from=price_from,
                price_to=price_to,
                currency="USD"
            )
            
            items = response.get("objects", [])
            if not items:
                self.logger.warning(f"Не найдены предметы для {game_name}")
                return []
            
            self.logger.info(f"Получено {len(items)} предметов для {game_name}")
            
            # Анализируем предметы для поиска потенциально прибыльных
            profitable_items = await self._analyze_items(items, min_profit_percent, game_name)
            
            self.logger.info(f"Найдено {len(profitable_items)} потенциально прибыльных предметов для {game_name}")
            return profitable_items
            
        except Exception as e:
            self.logger.error(f"Ошибка при анализе игры {game_name}: {e}")
            return []
    
    async def _analyze_items(
        self, 
        items: List[Dict[str, Any]], 
        min_profit_percent: float,
        game_name: str
    ) -> List[Dict[str, Any]]:
        """
        Анализирует список предметов для поиска потенциально прибыльных.
        
        Args:
            items: Список предметов
            min_profit_percent: Минимальный процент прибыли
            game_name: Название игры для логирования
            
        Returns:
            Список потенциально прибыльных предметов
        """
        profitable_items = []
        
        for item in items:
            try:
                # Получаем основную информацию о предмете
                item_name = item.get("title", "Неизвестный предмет")
                item_id = item.get("itemId", "")
                market_price = float(item.get("price", {}).get("USD", 0))
                
                if market_price <= 0:
                    continue
                
                # Получаем ордера на покупку для этого предмета (если они есть)
                buy_orders = item.get("buyOrders", [])
                best_buy_order_price = 0.0
                if buy_orders:
                    # Находим лучшую цену покупки
                    for order in buy_orders:
                        order_price = float(order.get("price", {}).get("USD", 0))
                        if order_price > best_buy_order_price:
                            best_buy_order_price = order_price
                
                # Если нет ордеров на покупку, используем приблизительную оценку
                if best_buy_order_price <= 0:
                    # Оценка цены покупки как 90% от рыночной цены
                    estimated_buy_price = market_price * 0.9
                    best_buy_order_price = estimated_buy_price
                
                # Получаем историю продаж, если доступно
                sales_history = []
                try:
                    # Получаем данные о последних продажах
                    sales_history_response = await self.api.get_item_history_async(item_id, limit=10)
                    sales_history = sales_history_response.get("history", [])
                except Exception as e:
                    self.logger.debug(f"Не удалось получить историю продаж для {item_name}: {e}")
                
                # Рассчитываем среднюю цену продаж, если есть история
                avg_sale_price = 0.0
                if sales_history:
                    sale_prices = [float(sale.get("price", {}).get("USD", 0)) for sale in sales_history]
                    if sale_prices:
                        avg_sale_price = sum(sale_prices) / len(sale_prices)
                else:
                    # Если нет истории продаж, используем текущую рыночную цену
                    avg_sale_price = market_price
                
                # Рассчитываем потенциальную прибыль
                potential_profit = avg_sale_price - best_buy_order_price
                profit_percent = (potential_profit / best_buy_order_price) * 100 if best_buy_order_price > 0 else 0
                
                # Проверяем, соответствует ли предмет критериям прибыльности
                if profit_percent >= min_profit_percent:
                    # Собираем информацию о прибыльном предмете
                    profitable_item = {
                        "name": item_name,
                        "id": item_id,
                        "current_price": market_price,
                        "buy_price": best_buy_order_price,
                        "avg_sale_price": avg_sale_price,
                        "potential_profit": potential_profit,
                        "profit_percent": profit_percent,
                        "sales_history_count": len(sales_history),
                        "game": game_name
                    }
                    
                    profitable_items.append(profitable_item)
                    
                    # Логируем найденную возможность
                    self.logger.info(f"Найден потенциально прибыльный предмет: {item_name} в игре {game_name}")
                    self.logger.info(f"  Цена покупки: ${best_buy_order_price:.2f}, "
                                   f"Средняя цена продажи: ${avg_sale_price:.2f}, "
                                   f"Прибыль: ${potential_profit:.2f} ({profit_percent:.2f}%)")
            
            except Exception as e:
                item_name = item.get("title", "Неизвестный предмет")
                self.logger.error(f"Ошибка при анализе предмета {item_name}: {e}")
                continue
        
        # Сортируем результаты по проценту прибыли (по убыванию)
        profitable_items.sort(key=lambda x: x["profit_percent"], reverse=True)
        
        return profitable_items

    async def analyze_all_games(
        self,
        price_from: float = 1.0,
        price_to: float = 100.0,
        min_profit_percent: float = 5.0,
        max_items_per_game: int = 200
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Анализирует все поддерживаемые игры для поиска арбитражных возможностей.
        
        Args:
            price_from: Минимальная цена предметов
            price_to: Максимальная цена предметов
            min_profit_percent: Минимальный процент прибыли
            max_items_per_game: Максимальное количество предметов для анализа в каждой игре
            
        Returns:
            Словарь с результатами анализа по играм
        """
        results = {}
        
        for game_name, game_id in GAME_IDS.items():
            start_time = time.time()
            self.logger.info(f"Начинаем анализ игры {game_name}...")
            
            opportunities = await self.analyze_game(
                game_id=game_id,
                game_name=game_name,
                price_from=price_from,
                price_to=price_to,
                min_profit_percent=min_profit_percent,
                max_items=max_items_per_game
            )
            
            results[game_name] = opportunities
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Анализ игры {game_name} завершен за {elapsed_time:.2f} сек. "
                           f"Найдено {len(opportunities)} возможностей.")
            
            # Добавляем задержку между запросами к разным играм, чтобы не перегружать API
            await asyncio.sleep(1)
        
        return results

    def save_results(self, results: Dict[str, List[Dict[str, Any]]], filename: str = None):
        """
        Сохраняет результаты анализа в JSON-файл.
        
        Args:
            results: Результаты анализа
            filename: Имя файла для сохранения (по умолчанию генерируется на основе текущей даты и времени)
        """
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"arbitrage_results_{timestamp}.json"
        
        # Создаем директорию results, если она не существует
        results_dir = Path("results")
        results_dir.mkdir(exist_ok=True)
        
        file_path = results_dir / filename
        
        # Подготавливаем данные для сохранения
        output_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "results": results,
            "summary": {
                "total_opportunities": sum(len(opportunities) for opportunities in results.values()),
                "opportunities_per_game": {game: len(opportunities) for game, opportunities in results.items()}
            }
        }
        
        # Сохраняем результаты в файл
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        self.logger.info(f"Результаты сохранены в файл: {file_path}")
        
        return file_path

    def print_summary(self, results: Dict[str, List[Dict[str, Any]]]):
        """
        Выводит сводку результатов анализа.
        
        Args:
            results: Результаты анализа
        """
        total_opportunities = sum(len(opportunities) for opportunities in results.values())
        
        print("\n" + "="*80)
        print(f"СВОДКА АНАЛИЗА АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НА DMARKET")
        print("="*80)
        
        print(f"\nВсего найдено возможностей: {total_opportunities}")
        
        for game_name, opportunities in results.items():
            if not opportunities:
                print(f"\n{game_name}: Не найдено прибыльных предметов")
                continue
            
            print(f"\n{game_name}: Найдено {len(opportunities)} прибыльных предметов")
            
            if opportunities:
                # Выводим Top-5 самых прибыльных предметов для каждой игры
                print(f"\nТоп-5 самых прибыльных предметов в {game_name}:")
                print("{:<40} {:<10} {:<10} {:<10} {:<10}".format(
                    "Название", "Цена покупки", "Цена продажи", "Прибыль", "Прибыль %"))
                print("-" * 80)
                
                for item in opportunities[:5]:
                    print("{:<40} ${:<9.2f} ${:<9.2f} ${:<9.2f} {:<9.2f}%".format(
                        item["name"][:38], 
                        item["buy_price"], 
                        item["avg_sale_price"], 
                        item["potential_profit"], 
                        item["profit_percent"]))
        
        print("\n" + "="*80)
        print(f"Результаты анализа сохранены в директории 'results'")
        print("="*80 + "\n")


async def main():
    """Главная функция скрипта."""
    logger.info("Запуск анализа арбитражных возможностей на DMarket")
    
    # Создаем анализатор арбитража
    analyzer = ArbitrageAnalyzer(DMARKET_API_KEY, DMARKET_API_SECRET)
    
    # Настройки для анализа
    price_from = 1.0  # Минимальная цена предметов в USD
    price_to = 100.0  # Максимальная цена предметов в USD
    min_profit_percent = 5.0  # Минимальный процент прибыли
    max_items_per_game = 200  # Максимальное количество предметов для анализа в каждой игре
    
    # Анализируем все игры
    results = await analyzer.analyze_all_games(
        price_from=price_from,
        price_to=price_to,
        min_profit_percent=min_profit_percent,
        max_items_per_game=max_items_per_game
    )
    
    # Сохраняем результаты в файл
    analyzer.save_results(results)
    
    # Выводим сводку результатов
    analyzer.print_summary(results)
    
    logger.info("Анализ арбитражных возможностей завершен")


if __name__ == "__main__":
    # Запускаем асинхронную функцию main
    asyncio.run(main()) 