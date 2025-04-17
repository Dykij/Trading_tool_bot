#!/usr/bin/env python
"""
Продвинутый скрипт для тестирования арбитражных возможностей на DMarket.

Этот скрипт анализирует предметы из игр CS2, Dota 2, TF2 и Rust на платформе DMarket
для поиска потенциально прибыльных возможностей покупки и продажи с использованием:
1. Продвинутого анализа ликвидности
2. Машинного обучения для прогнозирования цен
3. Оценки рисков и верификации возможностей
"""

import os
import sys
import json
import logging
import asyncio
import time
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Set, Union
from pathlib import Path
from dotenv import load_dotenv

# Настройка путей проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# Загрузка переменных окружения
load_dotenv()

# Настройка логирования
log_dir = PROJECT_ROOT / "logs"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"advanced_arbitrage_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("advanced_arbitrage_test")

# Импорт необходимых модулей
try:
    from src.api.api_wrapper import DMarketAPI
    from src.arbitrage.liquidity_analyzer import LiquidityAnalyzer
    from src.ml.ml_predictor import MLPredictor
    logger.info("Успешно импортированы основные модули")
except ImportError as e:
    logger.error(f"Не удалось импортировать необходимые модули: {e}")
    logger.error("Убедитесь, что вы находитесь в корневой директории проекта")
    sys.exit(1)

# Константы
DMARKET_API_KEY = os.getenv("DMARKET_API_KEY")
DMARKET_API_SECRET = os.getenv("DMARKET_API_SECRET")

if not DMARKET_API_KEY or not DMARKET_API_SECRET:
    logger.error("Не указаны DMARKET_API_KEY или DMARKET_API_SECRET в файле .env")
    sys.exit(1)

# Идентификаторы игр для DMarket API
GAME_IDS = {
    "CS2": "a8db",
    "DOTA2": "9a92",
    "TF2": "tf2", 
    "RUST": "rust"
}

class AdvancedArbitrageAnalyzer:
    """
    Продвинутый анализатор арбитражных возможностей с использованием ML и анализа ликвидности.
    """
    
    def __init__(self, api_key: str, api_secret: str, use_ml: bool = True):
        """
        Инициализация анализатора.
        
        Args:
            api_key: Ключ API DMarket
            api_secret: Секрет API DMarket
            use_ml: Использовать ли ML для прогнозирования цен
        """
        self.api = DMarketAPI(api_key, api_secret)
        self.logger = logging.getLogger("AdvancedArbitrageAnalyzer")
        self.use_ml = use_ml
        
        # Инициализируем ML предиктор, если требуется
        self.ml_predictor = None
        if use_ml:
            try:
                self.ml_predictor = MLPredictor(self.api)
                self.logger.info("ML предиктор инициализирован успешно")
            except Exception as e:
                self.logger.warning(f"Не удалось инициализировать ML предиктор: {e}")
                self.use_ml = False
        
        # Инициализируем анализатор ликвидности
        self.liquidity_analyzer = LiquidityAnalyzer(self.api, self.ml_predictor)
        
        # Параметры для анализа
        self.min_opportunity_score = 0.3  # Минимальная оценка возможности для включения в результаты
    
    async def analyze_game(
        self, 
        game_id: str, 
        game_name: str,
        price_from: float = 1.0, 
        price_to: float = 100.0, 
        min_profit_percent: float = 5.0,
        max_items: int = 100,
        min_opportunity_score: float = None
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
            min_opportunity_score: Минимальная оценка возможности (если не указана, используется стандартная)
            
        Returns:
            Список потенциально прибыльных предметов с оценкой возможности
        """
        start_time = time.time()
        self.logger.info(f"Анализ игры {game_name} (ID: {game_id})")
        
        # Используем указанный минимальный score или стандартный
        min_score = min_opportunity_score if min_opportunity_score is not None else self.min_opportunity_score
        
        try:
            # Получаем предметы с рынка
            # Преобразуем цены в целые числа в строковом формате как требует API
            price_from_str = str(int(price_from * 100))
            price_to_str = str(int(price_to * 100))
            
            response = await self.api.get_market_items_async(
                game_id=game_id,
                limit=max_items,
                price_from=price_from_str,
                price_to=price_to_str,
                currency="USD"
            )
            
            items = response.get("objects", [])
            if not items:
                self.logger.warning(f"Не найдены предметы для {game_name}")
                return []
            
            self.logger.info(f"Получено {len(items)} предметов для {game_name}")
            
            # Анализируем предметы для поиска потенциально прибыльных
            profitable_items = await self._analyze_items(
                items=items, 
                min_profit_percent=min_profit_percent, 
                game_name=game_name,
                min_opportunity_score=min_score
            )
            
            elapsed_time = time.time() - start_time
            self.logger.info(f"Анализ игры {game_name} завершен за {elapsed_time:.2f} сек. Найдено {len(profitable_items)} возможностей.")
            return profitable_items
            
        except Exception as e:
            self.logger.error(f"Ошибка при анализе игры {game_name}: {e}")
            return []
    
    async def _analyze_items(
        self, 
        items: List[Dict[str, Any]], 
        min_profit_percent: float,
        game_name: str,
        min_opportunity_score: float
    ) -> List[Dict[str, Any]]:
        """
        Анализирует список предметов для поиска потенциально прибыльных с оценкой возможности.
        
        Args:
            items: Список предметов
            min_profit_percent: Минимальный процент прибыли
            game_name: Название игры для логирования
            min_opportunity_score: Минимальная оценка возможности
            
        Returns:
            Список потенциально прибыльных предметов с оценкой возможности
        """
        profitable_items = []
        
        # Создаем задачи для асинхронного анализа каждого предмета
        tasks = []
        for item in items:
            task = self._analyze_single_item(item, min_profit_percent, game_name)
            tasks.append(task)
        
        # Запускаем асинхронное выполнение задач с ограничением
        # Обрабатываем по 10 предметов одновременно, чтобы не перегружать API
        chunk_size = 10
        for i in range(0, len(tasks), chunk_size):
            chunk_tasks = tasks[i:i+chunk_size]
            chunk_results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            # Фильтруем результаты
            for result in chunk_results:
                if isinstance(result, Exception):
                    self.logger.error(f"Ошибка при анализе предмета: {result}")
                    continue
                
                if result is None:
                    continue
                
                # Проверяем оценку возможности
                opportunity_score = result.get('opportunity_score', 0)
                if opportunity_score >= min_opportunity_score:
                    profitable_items.append(result)
        
        # Сортировка результатов по оценке возможности (от лучших к худшим)
        profitable_items.sort(key=lambda x: x.get('opportunity_score', 0), reverse=True)
        
        return profitable_items
    
    async def _analyze_single_item(
        self, 
        item: Dict[str, Any], 
        min_profit_percent: float,
        game_name: str
    ) -> Optional[Dict[str, Any]]:
        """
        Анализирует один предмет для поиска арбитражной возможности.
        
        Args:
            item: Данные о предмете
            min_profit_percent: Минимальный процент прибыли
            game_name: Название игры для логирования
            
        Returns:
            Данные о потенциально прибыльном предмете или None
        """
        try:
            item_name = item.get('title', 'Неизвестный предмет')
            item_id = item.get('itemId', '')
            
            # Рассчитываем реалистичную прибыль с учетом комиссий, рисков и ликвидности
            profit_data = await self.liquidity_analyzer.calculate_realistic_profit(
                item_data=item,
                use_ml_prediction=self.use_ml
            )
            
            # Проверяем, достаточен ли процент прибыли
            profit_percent = profit_data.get('profit_percent', 0)
            if profit_percent < min_profit_percent:
                return None
            
            # Добавляем дополнительную информацию о предмете к результату
            result = {
                'item_name': item_name,
                'item_id': item_id,
                'game': game_name,
                **profit_data,
                'raw_item_data': item
            }
            
            # Логируем найденную возможность
            self.logger.info(f"Найден потенциально прибыльный предмет: {item_name} в игре {game_name}")
            self.logger.info(f"  Цена покупки: ${profit_data.get('buy_price', 0):.2f}, "
                             f"Ожидаемая цена продажи: ${profit_data.get('expected_sell_price', 0):.2f}, "
                             f"Прибыль: ${profit_data.get('net_profit', 0):.2f} ({profit_data.get('profit_percent', 0):.2f}%)")
            self.logger.info(f"  Оценка возможности: {profit_data.get('opportunity_score', 0):.2f}, "
                             f"Оценка риска: {profit_data.get('risk_score', 0):.2f}, "
                             f"Оценка ликвидности: {profit_data.get('liquidity_score', 0):.2f}")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка при анализе предмета {item.get('title', 'Unknown')}: {e}")
            return None
            
    async def analyze_all_games(
        self,
        price_from: float = 1.0,
        price_to: float = 100.0,
        min_profit_percent: float = 5.0,
        max_items_per_game: int = 100,
        min_opportunity_score: float = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Анализирует все поддерживаемые игры для поиска арбитражных возможностей.
        
        Args:
            price_from: Минимальная цена предметов
            price_to: Максимальная цена предметов
            min_profit_percent: Минимальный процент прибыли
            max_items_per_game: Максимальное количество предметов для анализа в каждой игре
            min_opportunity_score: Минимальная оценка возможности
            
        Returns:
            Словарь с результатами анализа по играм
        """
        results = {}
        
        for game_name, game_id in GAME_IDS.items():
            self.logger.info(f"Начинаем анализ игры {game_name}...")
            
            game_results = await self.analyze_game(
                game_id=game_id,
                game_name=game_name,
                price_from=price_from,
                price_to=price_to,
                min_profit_percent=min_profit_percent,
                max_items=max_items_per_game,
                min_opportunity_score=min_opportunity_score
            )
            
            results[game_name] = game_results
            
            # Небольшая пауза между играми
            await asyncio.sleep(1)
        
        return results
    
    def save_results(self, results: Dict[str, List[Dict[str, Any]]], filename: str = None) -> str:
        """
        Сохраняет результаты анализа в JSON файл.
        
        Args:
            results: Словарь с результатами анализа по играм
            filename: Имя файла для сохранения (если не указано, генерируется автоматически)
            
        Returns:
            Путь к сохраненному файлу
        """
        # Создаем директорию для результатов, если она не существует
        results_dir = PROJECT_ROOT / "results"
        results_dir.mkdir(exist_ok=True)
        
        # Генерируем имя файла, если не указано
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"advanced_arbitrage_results_{timestamp}.json"
        
        # Полный путь к файлу
        filepath = results_dir / filename
        
        # Подготовка данных для сохранения (удаляем raw_item_data для экономии места)
        clean_results = {}
        for game_name, game_results in results.items():
            clean_game_results = []
            for item in game_results:
                clean_item = item.copy()
                if 'raw_item_data' in clean_item:
                    del clean_item['raw_item_data']
                clean_game_results.append(clean_item)
            clean_results[game_name] = clean_game_results
        
        # Сохраняем в файл
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(clean_results, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Результаты сохранены в файл: {filepath}")
        return str(filepath)
    
    def print_summary(self, results: Dict[str, List[Dict[str, Any]]]):
        """
        Выводит сводку результатов анализа.
        
        Args:
            results: Словарь с результатами анализа по играм
        """
        total_opportunities = sum(len(items) for items in results.values())
        
        print("\n" + "=" * 80)
        print("СВОДКА ПРОДВИНУТОГО АНАЛИЗА АРБИТРАЖНЫХ ВОЗМОЖНОСТЕЙ НА DMARKET")
        print("=" * 80 + "\n")
        
        print(f"Всего найдено возможностей: {total_opportunities}\n")
        
        for game_name, game_results in results.items():
            print(f"{game_name}: Найдено {len(game_results)} прибыльных предметов\n")
            
            if game_results:
                print(f"Топ-5 самых перспективных предметов в {game_name}:")
                print("Название                                 Цена покупки Цена продажи Прибыль    Прибыль %   Оценка")
                print("-" * 80)
                
                # Берем топ-5 предметов с лучшей оценкой возможности
                top_items = sorted(game_results, key=lambda x: x.get('opportunity_score', 0), reverse=True)[:5]
                
                for item in top_items:
                    name = item.get('item_name', 'Неизвестный предмет')
                    name = name[:35] + "..." if len(name) > 38 else name.ljust(38)
                    
                    buy_price = item.get('buy_price', 0)
                    sell_price = item.get('expected_sell_price', 0)
                    profit = item.get('net_profit', 0)
                    profit_percent = item.get('profit_percent', 0)
                    opportunity_score = item.get('opportunity_score', 0)
                    
                    print(f"{name} ${buy_price:<10.2f} ${sell_price:<10.2f} ${profit:<10.2f} {profit_percent:<10.2f}% {opportunity_score:.2f}")
                
                print()
        
        print("=" * 80)
        print("Результаты анализа сохранены в директории 'results'")
        print("=" * 80 + "\n")

async def main():
    """Основная функция для запуска анализа."""
    logger.info("Запуск продвинутого анализа арбитражных возможностей")
    
    # Проверяем наличие ключей API
    if not DMARKET_API_KEY or not DMARKET_API_SECRET:
        logger.error("Не указаны DMARKET_API_KEY или DMARKET_API_SECRET в файле .env")
        return 1
    
    # Параметры анализа
    price_from = 5.0  # Минимальная цена в USD
    price_to = 50.0   # Максимальная цена в USD
    min_profit_percent = 5.0  # Минимальный процент прибыли
    max_items_per_game = 20   # Ограничиваем количество предметов для анализа
    min_opportunity_score = 0.3  # Минимальная оценка возможности
    use_ml = True  # Используем ML для прогнозирования
    
    # Инициализируем анализатор
    analyzer = AdvancedArbitrageAnalyzer(
        api_key=DMARKET_API_KEY,
        api_secret=DMARKET_API_SECRET,
        use_ml=use_ml
    )
    
    # Анализируем все игры
    results = await analyzer.analyze_all_games(
        price_from=price_from,
        price_to=price_to,
        min_profit_percent=min_profit_percent,
        max_items_per_game=max_items_per_game,
        min_opportunity_score=min_opportunity_score
    )
    
    # Сохраняем результаты
    analyzer.save_results(results)
    
    # Выводим сводку
    analyzer.print_summary(results)
    
    logger.info("Анализ арбитражных возможностей завершен")
    return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 