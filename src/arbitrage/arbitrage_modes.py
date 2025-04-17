"""
Модуль, реализующий различные режимы арбитража для DMarket Trading Bot.

Поддерживает три режима:
- Разгон баланса: поиск скинов с прибылью $1-5
- Средний трейдер: поиск скинов с прибылью $5-20 с высокой ликвидностью
- Trade Pro: поиск скинов с прибылью $20-100 (редкие/недооцененные)
"""

import logging
import asyncio
from typing import Dict, List, Optional, Union, Tuple, Any
import pandas as pd
from enum import Enum
import json
from pathlib import Path
import os
import concurrent.futures
import numpy as np
from functools import partial

# Импортируем необходимые модули
from src.api.api_wrapper import DMarketAPI
from src.config.config import Config
from src.trading.trading_facade import get_trading_service
from src.db.models import ArbitrageResult

# Настраиваем логирование
logger = logging.getLogger(__name__)

class ArbitrageMode(Enum):
    """Режимы работы арбитража"""
    BALANCE_BOOST = "balance_boost"  # Разгон баланса
    MEDIUM_TRADER = "medium_trader"  # Средний трейдер
    TRADE_PRO = "trade_pro"         # Trade Pro

class ArbitrageParams:
    """Параметры для поиска арбитража в разных режимах"""
    
    def __init__(self, mode: ArbitrageMode, budget: Optional[float] = None, config: Optional[Dict] = None):
        """
        Инициализирует параметры арбитража на основе выбранного режима и конфигурации
        
        Args:
            mode: Режим арбитража
            budget: Бюджет для торговли (если указан)
            config: Словарь с конфигурацией (если не указан, загружается из Config)
        """
        self.mode = mode
        self.budget = budget
        
        # Загружаем конфигурацию
        if config is None:
            try:
                self.config = Config().arbitrage
            except Exception as e:
                logger.warning(f"Не удалось загрузить конфигурацию: {e}. Используем значения по умолчанию.")
                self.config = {}
        else:
            self.config = config
        
        # Базовые параметры
        self.games = ["cs2", "dota2", "tf2", "rust"]
        
        # Устанавливаем параметры из конфигурации или используем значения по умолчанию
        self._set_params_from_config()
            
        # Если указан бюджет, уточняем параметры
        if budget:
            self.max_price = min(self.max_price, budget)
    
    def _set_params_from_config(self):
        """Устанавливает параметры на основе конфигурации"""
        mode_value = self.mode.value
        
        # Получаем настройки для режима из конфигурации или используем значения по умолчанию
        mode_config = self.config.get(mode_value, {})
        
        if self.mode == ArbitrageMode.BALANCE_BOOST:
            # Параметры режима "Разгон баланса"
            self.min_profit = mode_config.get('min_profit', 1.0)
            self.max_profit = mode_config.get('max_profit', 5.0)
            self.min_price = mode_config.get('min_price', 0.5)
            self.max_price = mode_config.get('max_price', 20.0)
            self.require_liquidity = mode_config.get('require_liquidity', False)
            self.scan_depth = mode_config.get('max_items', 100)
            self.min_liquidity_score = 3.0  # Минимальный порог ликвидности
            self.min_profit_percent = 5.0  # Минимальный % прибыли
            self.use_ml = False  # Не используем ML для простого режима
            self.parallel_processing = False  # Не используем параллельную обработку
            
        elif self.mode == ArbitrageMode.MEDIUM_TRADER:
            # Параметры режима "Средний трейдер"
            self.min_profit = mode_config.get('min_profit', 5.0)
            self.max_profit = mode_config.get('max_profit', 20.0)
            self.min_price = mode_config.get('min_price', 5.0)
            self.max_price = mode_config.get('max_price', 100.0)
            self.require_liquidity = mode_config.get('require_liquidity', True)
            self.scan_depth = mode_config.get('max_items', 200)
            self.min_liquidity_score = 2.0
            self.min_profit_percent = 7.0
            self.use_ml = mode_config.get('use_ml', False)  # Опционально используем ML
            self.parallel_processing = False  # Не используем параллельную обработку
            
        elif self.mode == ArbitrageMode.TRADE_PRO:
            # Параметры режима "Trade Pro"
            self.min_profit = mode_config.get('min_profit', 20.0)
            self.max_profit = mode_config.get('max_profit', 100.0)
            self.min_price = mode_config.get('min_price', 20.0)
            self.max_price = mode_config.get('max_price', 500.0)
            self.require_liquidity = mode_config.get('require_liquidity', False)
            self.scan_depth = mode_config.get('max_items', 500)
            self.min_liquidity_score = 1.0
            self.min_profit_percent = 10.0
            self.use_ml = mode_config.get('use_ml', True)  # По умолчанию используем ML для Trade Pro
            self.parallel_processing = mode_config.get('parallel_processing', True)  # Используем параллельную обработку
            self.parallel_workers = mode_config.get('parallel_workers', 4)  # Количество воркеров для параллельной обработки
            self.ml_confidence_threshold = mode_config.get('ml_confidence_threshold', 0.65)  # Порог уверенности ML
            self.trend_analysis = mode_config.get('trend_analysis', True)  # Анализ тренда предмета
        
        # Логируем параметры
        logger.debug(f"Установлены параметры для режима {mode_value}: "
                    f"профит {self.min_profit}-{self.max_profit}, "
                    f"цена {self.min_price}-{self.max_price}, "
                    f"ликвидность {self.require_liquidity}, "
                    f"глубина сканирования {self.scan_depth}")

class ArbitrageManager:
    """Менеджер для поиска и исполнения арбитражных стратегий"""
    
    def __init__(self, api: Optional[DMarketAPI] = None, config: Optional[Dict] = None):
        """
        Инициализирует менеджер арбитража
        
        Args:
            api: Экземпляр API DMarket (если не указан, будет создан новый)
            config: Словарь с конфигурацией (если не указан, загружается из Config)
        """
        # Загружаем конфигурацию
        from src.config.config import Config
        self.config_obj = Config()
        
        # Получаем API ключи из конфигурации
        api_key = os.getenv("DMARKET_API_KEY") or self.config_obj.API_KEY
        api_secret = os.getenv("DMARKET_API_SECRET") or self.config_obj.API_SECRET
        
        if not api and (not api_key or not api_secret):
            logger.warning("API ключи не найдены в конфигурации, некоторая функциональность может быть недоступна")
        
        # Инициализируем API клиент
        self.api = api or DMarketAPI(api_key=api_key) if api_key else None
        self.trading_service = get_trading_service()
        self.config = config
        self.ml_model = None
        
        # Создаем директории для отчетов, если их нет
        Path("reports").mkdir(exist_ok=True)
        
        # Инициализируем ML-модель, если возможно
        self._initialize_ml_model()
    
    def _initialize_ml_model(self):
        """Инициализирует ML-модель для прогнозирования успешности арбитражных сделок"""
        try:
            # Пытаемся импортировать необходимые ML-библиотеки
            from src.ml.price_predictor import PricePredictor
            from src.ml.market_analyzer import MarketAnalyzer
            
            # Инициализируем компоненты ML
            self.price_predictor = PricePredictor()
            self.market_analyzer = MarketAnalyzer()
            
            logger.info("ML-модель успешно инициализирована")
        except (ImportError, Exception) as e:
            logger.warning(f"Не удалось инициализировать ML-модель: {e}. ML-функции будут отключены.")
            self.price_predictor = None
            self.market_analyzer = None
        
    async def find_arbitrage_opportunities(
        self, 
        mode: Union[ArbitrageMode, str],
        budget: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Находит арбитражные возможности в зависимости от выбранного режима
        
        Args:
            mode: Режим арбитража (можно передать строку или enum)
            budget: Максимальный бюджет для поиска
            
        Returns:
            DataFrame с найденными возможностями
        """
        # Преобразуем строку в enum, если необходимо
        if isinstance(mode, str):
            try:
                mode = ArbitrageMode(mode)
            except ValueError:
                logger.error(f"Неизвестный режим арбитража: {mode}")
                return pd.DataFrame()
            
        params = ArbitrageParams(mode, budget, self.config)
        logger.info(f"Запуск поиска арбитража в режиме: {mode.value}, бюджет: {budget}")
        
        # Результаты для всех игр
        all_results = []
        
        try:
            # Запускаем поиск для каждой игры параллельно
            tasks = []
            for game in params.games:
                tasks.append(self._find_opportunities_for_game(game, params))
                
            # Ожидаем завершения всех задач
            results_list = await asyncio.gather(*tasks)
            
            # Объединяем результаты
            for result in results_list:
                all_results.extend(result)
                
            # Преобразуем результаты в DataFrame
            if all_results:
                df = pd.DataFrame(all_results)
                
                # Применяем фильтры в зависимости от режима
                df = self._filter_by_mode(df, params)
                
                # Если это режим Trade Pro и доступны ML-компоненты, применяем ML-анализ
                if params.mode == ArbitrageMode.TRADE_PRO and params.use_ml and self.price_predictor:
                    df = self._apply_ml_analysis(df, params)
                
                # Сортируем с учетом режима
                df = self._sort_by_mode(df, params)
                
                # Сохраняем отчет для дальнейшего использования
                self._save_results_report(df, mode.value, budget)
            
                return df
            else:
                # Возвращаем пустой DataFrame с нужными колонками
                logger.warning(f"Не найдено арбитражных возможностей для режима {mode.value}")
                return pd.DataFrame(columns=[
                    'name', 'game', 'price', 'market_price', 
                    'profit', 'profit_percent', 'liquidity_score',
                    'item_id', 'sale_fee', 'recommended_price'
                ])
        except Exception as e:
            logger.error(f"Ошибка при поиске арбитражных возможностей: {e}", exc_info=True)
            # Возвращаем пустой DataFrame с информацией об ошибке
            error_df = pd.DataFrame(columns=['error'])
            error_df.loc[0] = {'error': f"Произошла ошибка: {str(e)}"}
            return error_df
    
    async def _find_opportunities_for_game(
        self, 
        game: str, 
        params: ArbitrageParams
    ) -> List[Dict]:
        """
        Находит арбитражные возможности для конкретной игры
        
        Args:
            game: Название игры
            params: Параметры поиска
            
        Returns:
            Список словарей с арбитражными возможностями
        """
        try:
            logger.debug(f"Поиск арбитража для игры {game} в режиме {params.mode.value}")
            
            # Получаем данные с маркетплейса
            items = await self.api.get_market_items(
                game=game,
                limit=params.scan_depth,
                min_price=params.min_price,
                max_price=params.max_price
            )
            
            if not items:
                logger.warning(f"Не удалось получить предметы для игры {game}")
                return []
            
            # Для режима Trade Pro используем параллельную обработку при необходимости
            if params.mode == ArbitrageMode.TRADE_PRO and params.parallel_processing:
                return await self._process_items_parallel(items, game, params)
            else:
                # Обычная последовательная обработка
                return await self._process_items_sequential(items, game, params)
                
        except Exception as e:
            logger.error(f"Ошибка при поиске арбитража для {game}: {e}", exc_info=True)
            return []
    
    async def _process_items_sequential(self, items: List[Dict], game: str, params: ArbitrageParams) -> List[Dict]:
        """Последовательная обработка предметов"""
        results = []
        for item in items:
            try:
                result = self._process_single_item(item, game, params)
                if result:
                    results.append(result)
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(f"Ошибка при обработке предмета: {e}")
                continue
        
        logger.info(f"Найдено {len(results)} арбитражных возможностей для {game}")
        return results

    async def _process_items_parallel(self, items: List[Dict], game: str, params: ArbitrageParams) -> List[Dict]:
        """Параллельная обработка предметов для режима Trade Pro"""
        results = []
        
        logger.debug(f"Запуск параллельной обработки для {len(items)} предметов игры {game}")
        
        # Создаем частичную функцию с предустановленными параметрами
        process_func = partial(self._process_single_item, game=game, params=params)
        
        # Используем ThreadPoolExecutor для параллельной обработки
        with concurrent.futures.ThreadPoolExecutor(max_workers=params.parallel_workers) as executor:
            # Запускаем обработку в пуле потоков
            future_results = list(executor.map(process_func, items))
            
            # Собираем результаты, отфильтровывая None
            results = [r for r in future_results if r is not None]
        
        logger.info(f"Параллельная обработка: найдено {len(results)} арбитражных возможностей для {game}")
        return results
    
    def _process_single_item(self, item: Dict, game: str, params: ArbitrageParams) -> Optional[Dict]:
        """Обрабатывает один предмет и возвращает результат, если он соответствует критериям"""
        try:
            # Рассчитываем потенциальную прибыль
            price = float(item.get('price', {}).get('USD', 0))
            market_price = float(item.get('marketPrice', {}).get('USD', 0))
            
            # Если цена покупки нулевая или рыночная цена нулевая, пропускаем
            if price <= 0 or market_price <= 0:
                return None
            
            # Определяем комиссию в зависимости от ликвидности
            liquidity_score = item.get('extra', {}).get('liquidity', 0)
            is_high_demand = liquidity_score > 7  # Высокий спрос (значок огня)
            
            # Комиссия ниже для предметов высокого спроса
            sale_fee = 0.02 if is_high_demand else 0.07
            
            # Рассчитываем прибыль
            recommended_price = market_price * 0.95  # Цена немного ниже рыночной для быстрой продажи
            profit = recommended_price * (1 - sale_fee) - price
            profit_percent = (profit / price) * 100 if price > 0 else 0
            
            # Проверяем соответствие критериям режима
            if (profit >= params.min_profit and profit <= params.max_profit and 
                (not params.require_liquidity or is_high_demand or liquidity_score >= params.min_liquidity_score) and
                profit_percent >= params.min_profit_percent):
                
                # Рассчитываем уровень риска
                risk_level = self._calculate_risk_level(item, liquidity_score, profit_percent)
                
                # Оцениваем время продажи
                estimated_time = self._estimate_sale_time(liquidity_score, is_high_demand)
                
                # Создаем базовый результат
                result = {
                    'name': item.get('title', 'Неизвестный предмет'),
                    'game': game,
                    'price': price,
                    'market_price': market_price,
                    'profit': round(profit, 2),
                    'profit_percent': round(profit_percent, 2),
                    'liquidity_score': liquidity_score,
                    'is_high_demand': is_high_demand,
                    'item_id': item.get('itemId'),
                    'sale_fee': sale_fee,
                    'recommended_price': round(recommended_price, 2),
                    'mode': params.mode.value,
                    'risk_level': risk_level,
                    'estimated_time': estimated_time
                }
                
                # Добавляем дополнительные данные для Trade Pro
                if params.mode == ArbitrageMode.TRADE_PRO:
                    # Расширенная информация для Trade Pro
                    result.update({
                        'historical_volatility': item.get('extra', {}).get('volatility', 0),
                        'listings_count': item.get('extra', {}).get('listingsCount', 0),
                        'market_trend': item.get('extra', {}).get('trend', 'stable'),
                    })
                
                return result
            
            return None
            
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Ошибка при обработке предмета: {e}")
            return None
        
    def _apply_ml_analysis(self, df: pd.DataFrame, params: ArbitrageParams) -> pd.DataFrame:
        """Применяет ML-анализ для предсказания успешности арбитражных сделок"""
        if df.empty or not self.price_predictor:
            return df
            
        try:
            logger.info("Применение ML-анализа для прогнозирования успешности арбитража")
            
            # Создаем копию DataFrame для безопасного изменения
            enriched_df = df.copy()
            
            # Создаем список записей для ML-анализа
            items_for_prediction = []
            for _, row in df.iterrows():
                items_for_prediction.append({
                    'name': row['name'],
                    'game': row['game'],
                    'price': row['price'],
                    'market_price': row['market_price'],
                    'liquidity_score': row['liquidity_score'],
                    'is_high_demand': row['is_high_demand'],
                    'profit_percent': row['profit_percent'],
                    'risk_level': row['risk_level']
                })
            
            # Получаем предсказания от ML-модели
            predictions = self.price_predictor.predict_success_probability(items_for_prediction)
            
            # Добавляем предсказания в DataFrame
            if predictions and len(predictions) == len(enriched_df):
                enriched_df['ml_success_probability'] = predictions
                
                # Фильтруем по порогу уверенности ML
                enriched_df = enriched_df[enriched_df['ml_success_probability'] >= params.ml_confidence_threshold]
                
                logger.info(f"После ML-анализа осталось {len(enriched_df)} арбитражных возможностей с высокой вероятностью успеха")
            else:
                logger.warning("ML-модель не вернула предсказания или количество предсказаний не соответствует числу записей")
                
            return enriched_df
            
        except Exception as e:
            logger.error(f"Ошибка при применении ML-анализа: {e}", exc_info=True)
            return df
    
    def _calculate_risk_level(self, item: Dict, liquidity_score: float, profit_percent: float) -> str:
        """
        Рассчитывает уровень риска для предмета
        
        Args:
            item: Данные предмета
            liquidity_score: Оценка ликвидности
            profit_percent: Процент прибыли
            
        Returns:
            Уровень риска: "low", "medium", "high"
        """
        # Базовая оценка риска
        if liquidity_score >= 7:
            risk = "low"
        elif liquidity_score >= 4:
            risk = "medium"
        else:
            risk = "high"
        
        # Корректируем с учетом прибыли (высокая прибыль часто означает высокий риск)
        if profit_percent > 15 and risk == "low":
            risk = "medium"
        elif profit_percent > 25 and risk != "high":
            risk = "high"
            
        # Учитываем дополнительные факторы
        listings_count = item.get('extra', {}).get('listingsCount', 0)
        if listings_count < 5 and risk != "high":
            risk = "high"
        elif listings_count > 50 and risk == "high":
            risk = "medium"
            
        # Учитываем тренд предмета, если он доступен
        trend = item.get('extra', {}).get('trend', 'stable')
        if trend == 'rising' and risk == "high":
            risk = "medium"
        elif trend == 'falling' and risk != "high":
            risk = "high"
            
        return risk
    
    def _estimate_sale_time(self, liquidity_score: float, is_high_demand: bool) -> str:
        """
        Оценивает примерное время продажи предмета
        
        Args:
            liquidity_score: Оценка ликвидности
            is_high_demand: Флаг высокого спроса
            
        Returns:
            Строка с оценкой времени продажи
        """
        if is_high_demand:
            return "1-2 часа"
        elif liquidity_score >= 5:
            return "3-6 часов"
        elif liquidity_score >= 3:
            return "12-24 часа"
        else:
            return "2-7 дней"
    
    def _filter_by_mode(self, df: pd.DataFrame, params: ArbitrageParams) -> pd.DataFrame:
        """
        Применяет дополнительные фильтры в зависимости от режима
        
        Args:
            df: DataFrame с результатами
            params: Параметры режима
            
        Returns:
            Отфильтрованный DataFrame
        """
        if df.empty:
            return df
            
        # Общие фильтры
        filtered_df = df[
            (df['profit'] >= params.min_profit) & 
            (df['profit'] <= params.max_profit) &
            (df['price'] >= params.min_price) &
            (df['price'] <= params.max_price) &
            (df['profit_percent'] >= params.min_profit_percent)
        ]
        
        # Специфичные для режима фильтры
        if params.mode == ArbitrageMode.BALANCE_BOOST:
            # Для режима "Разгон баланса" требуется высокая ликвидность и низкий риск
            filtered_df = filtered_df[
                ((filtered_df['liquidity_score'] >= params.min_liquidity_score) |
                (filtered_df['is_high_demand'] == True)) &
                (filtered_df['risk_level'] != "high")  # Исключаем предметы с высоким риском
            ]
            
            # Предпочитаем быстрые сделки для быстрого разгона
            fast_deals = filtered_df[filtered_df['estimated_time'].isin(['1-2 часа', '3-6 часов'])]
            if not fast_deals.empty:
                filtered_df = fast_deals
            
        elif params.mode == ArbitrageMode.MEDIUM_TRADER:
            # Для "Среднего трейдера" баланс риска и прибыли
            if params.require_liquidity:
                filtered_df = filtered_df[
                    (filtered_df['liquidity_score'] >= params.min_liquidity_score) |
                    (filtered_df['is_high_demand'] == True)
                ]
            
            # Предпочитаем сделки со средним риском, но с хорошей прибылью
            medium_risk = filtered_df[filtered_df['risk_level'] == "medium"]
            if len(medium_risk) >= 5:  # Если достаточно предметов среднего риска
                filtered_df = medium_risk
                
        elif params.mode == ArbitrageMode.TRADE_PRO:
            # Для "Trade Pro" применяем более сложную логику фильтрации
            
            # Разделяем на категории по прибыльности и риску
            high_profit_items = filtered_df[filtered_df['profit_percent'] >= 20]
            medium_profit_items = filtered_df[(filtered_df['profit_percent'] >= 15) & (filtered_df['profit_percent'] < 20)]
            
            # Для высокой прибыли допускаем больший риск
            acceptable_high_profit = high_profit_items[
                (high_profit_items['risk_level'] != "high") | 
                (high_profit_items['profit_percent'] >= 30)  # Если прибыль очень высокая, допускаем высокий риск
            ]
            
            # Средняя прибыль - только низкий и средний риск
            acceptable_medium_profit = medium_profit_items[medium_profit_items['risk_level'] != "high"]
            
            # Объединяем подходящие предметы
            filtered_df = pd.concat([acceptable_high_profit, acceptable_medium_profit])
            
            # Если у нас есть информация о тренде, учитываем её
            if 'trend_direction' in filtered_df.columns:
                # Предпочитаем предметы с растущим трендом
                rising_trend_items = filtered_df[filtered_df['trend_direction'] == 'rising']
                if len(rising_trend_items) >= 3:  # Если достаточно предметов с растущим трендом
                    filtered_df = rising_trend_items
            
            # Если доступен ML-анализ, можем учесть его уже здесь
            if 'ml_success_probability' in filtered_df.columns:
                # Сортируем по вероятности успеха
                filtered_df = filtered_df.sort_values('ml_success_probability', ascending=False)
                
                # Берем только верхние 30% с высокой вероятностью успеха
                if len(filtered_df) > 10:
                    top_percent = max(3, int(len(filtered_df) * 0.3))
                    filtered_df = filtered_df.head(top_percent)
            
        return filtered_df
    
    def _sort_by_mode(self, df: pd.DataFrame, params: ArbitrageParams) -> pd.DataFrame:
        """
        Сортирует результаты в зависимости от режима
        
        Args:
            df: DataFrame с результатами
            params: Параметры режима
            
        Returns:
            Отсортированный DataFrame
        """
        if df.empty:
            return df
            
        if params.mode == ArbitrageMode.BALANCE_BOOST:
            # Для режима "Разгон баланса" приоритет ликвидности и быстрым продажам
            # Сначала сортируем по высокому спросу, затем по ликвидности и проценту прибыли
            return df.sort_values(
                by=['is_high_demand', 'liquidity_score', 'profit_percent'], 
                ascending=[False, False, False]
            )
            
        elif params.mode == ArbitrageMode.MEDIUM_TRADER:
            # Для "Среднего трейдера" баланс прибыли, риска и ликвидности
            # Создаем функцию для сортировки по нескольким критериям
            def sort_key(row):
                # Комбинируем факторы в единую оценку
                risk_score = {'low': 3, 'medium': 2, 'high': 1}.get(row['risk_level'], 1)
                liquidity_factor = row['liquidity_score'] / 10  # Нормализуем ликвидность
                profit_factor = row['profit_percent'] / 100  # Нормализуем прибыль
                
                # Взвешенная оценка
                return (risk_score * 0.3) + (liquidity_factor * 0.3) + (profit_factor * 0.4)
                
            # Применяем пользовательскую сортировку
            return df.assign(sort_score=df.apply(sort_key, axis=1)).sort_values('sort_score', ascending=False).drop('sort_score', axis=1)
            
        elif params.mode == ArbitrageMode.TRADE_PRO:
            # Для "Trade Pro" приоритет комплексной оценке сделки
            
            # Если у нас есть ML-предсказания, учитываем их
            if 'ml_success_probability' in df.columns:
                # Создаем комплексную оценку, учитывающую прибыль, вероятность успеха и риск
                def trade_pro_score(row):
                    # Нормализуем факторы
                    profit_norm = min(row['profit'] / params.max_profit, 1.0)  # Нормализованная прибыль
                    ml_prob = row.get('ml_success_probability', 0.5)  # ML-предсказание или по умолчанию 0.5
                    risk_factor = {'low': 0.9, 'medium': 0.7, 'high': 0.5}.get(row['risk_level'], 0.5)
                    
                    # Если есть тренд, учитываем его
                    trend_factor = 1.0
                    if 'trend_strength' in row and 'trend_direction' in row:
                        trend_str = row.get('trend_strength', 0)
                        if row.get('trend_direction') == 'rising':
                            trend_factor += trend_str * 0.1  # Бонус за растущий тренд
                        elif row.get('trend_direction') == 'falling':
                            trend_factor -= trend_str * 0.1  # Штраф за падающий тренд
                    
                    # Комплексная оценка с учетом всех факторов
                    return (profit_norm * 0.4) + (ml_prob * 0.3) + (risk_factor * 0.2) + (trend_factor * 0.1)
                
                # Применяем комплексную оценку
                return df.assign(final_score=df.apply(trade_pro_score, axis=1)).sort_values('final_score', ascending=False).drop('final_score', axis=1)
            else:
                # Если ML недоступен, используем упрощенную логику
                # Сортируем по абсолютной прибыли и проценту прибыли, с учетом риска
                df['risk_factor'] = df['risk_level'].map({'low': 3, 'medium': 2, 'high': 1})
                sorted_df = df.sort_values(
                    by=['risk_factor', 'profit', 'profit_percent'], 
                    ascending=[False, False, False]
                )
                return sorted_df.drop('risk_factor', axis=1)
            
        # По умолчанию сортируем по прибыли
        return df.sort_values(by='profit', ascending=False)
    
    def _save_results_report(self, df: pd.DataFrame, mode: str, budget: Optional[float] = None) -> None:
        """
        Сохраняет результаты в JSON-файл для дальнейшего использования
        
        Args:
            df: DataFrame с результатами
            mode: Режим арбитража
            budget: Бюджет
        """
        if df.empty:
            return
            
        try:
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"arbitrage_{mode}_{timestamp}.json"
            
            # Создаем отчет
            report = {
                "mode": mode,
                "budget": budget,
                "timestamp": timestamp,
                "total_items": len(df),
                "total_profit": float(df['profit'].sum()),
                "items": json.loads(df.to_json(orient='records'))
            }
            
            # Сохраняем в файл
            file_path = os.path.join("reports", filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2)
                
            logger.info(f"Отчет сохранен в файл: {file_path}")
        except Exception as e:
            logger.error(f"Ошибка при сохранении отчета: {e}")
    
    async def execute_arbitrage_strategy(
        self, 
        opportunities: pd.DataFrame,
        mode: ArbitrageMode,
        execute: bool = False
    ) -> Dict:
        """
        Выполняет арбитражную стратегию (покупка и выставление на продажу)
        
        Args:
            opportunities: DataFrame с возможностями
            mode: Режим арбитража
            execute: Флаг выполнения реальных сделок (если False, только имитация)
            
        Returns:
            Словарь с результатами операций
        """
        if opportunities.empty:
            return {"success": False, "message": "Не найдено арбитражных возможностей"}
        
        results = {
            "success": True,
            "mode": mode.value,
            "total_opportunities": len(opportunities),
            "total_potential_profit": round(float(opportunities['profit'].sum()), 2),
            "executed": execute,
            "operations": []
        }
        
        if not execute:
            # Если это имитация, просто возвращаем потенциальные сделки
            for _, item in opportunities.iterrows():
                results["operations"].append({
                    "item_name": item['name'],
                    "game": item['game'],
                    "buy_price": float(item['price']),
                    "sell_price": float(item['recommended_price']),
                    "profit": float(item['profit']),
                    "profit_percent": float(item['profit_percent']),
                    "estimated_time": item.get('estimated_time', 'Неизвестно'),
                    "risk_level": item.get('risk_level', 'medium'),
                    "status": "simulated"
                })
            return results
        
        # Иначе выполняем реальные операции
        for _, item in opportunities.iterrows():
            try:
                # Покупаем предмет
                buy_result = await self.trading_service.buy_item(
                    item_id=item['item_id'],
                    price=float(item['price'])
                )
                
                if buy_result['success']:
                    # Выставляем на продажу
                    sell_result = await self.trading_service.sell_item(
                        item_id=item['item_id'],
                        price=float(item['recommended_price'])
                    )
                    
                    status = "completed" if sell_result['success'] else "bought_not_listed"
                    
                    results["operations"].append({
                        "item_name": item['name'],
                        "game": item['game'],
                        "buy_price": float(item['price']),
                        "sell_price": float(item['recommended_price']),
                        "profit": float(item['profit']),
                        "profit_percent": float(item['profit_percent']),
                        "estimated_time": item.get('estimated_time', 'Неизвестно'),
                        "risk_level": item.get('risk_level', 'medium'),
                        "status": status,
                        "transaction_id": buy_result.get('transaction_id')
                    })
                else:
                    results["operations"].append({
                        "item_name": item['name'],
                        "game": item['game'],
                        "status": "buy_failed",
                        "error": buy_result.get('error')
                    })
            
            except Exception as e:
                logger.error(f"Ошибка при выполнении арбитража для {item['name']}: {e}")
                results["operations"].append({
                    "item_name": item['name'],
                    "game": item['game'],
                    "status": "error",
                    "error": str(e)
                })
        
        return results
    
    async def export_results(self, opportunities: pd.DataFrame, format: str = 'csv') -> str:
        """
        Экспортирует результаты в файл
        
        Args:
            opportunities: DataFrame с результатами
            format: Формат экспорта ('csv', 'excel' или 'json')
            
        Returns:
            Путь к экспортированному файлу
        """
        import datetime
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"arbitrage_results_{timestamp}"
        
        # Создаем директорию, если она не существует
        reports_dir = Path("reports")
        reports_dir.mkdir(exist_ok=True)
        
        if format.lower() == 'csv':
            filepath = reports_dir / f"{filename}.csv"
            opportunities.to_csv(filepath, index=False)
        elif format.lower() == 'excel':
            filepath = reports_dir / f"{filename}.xlsx"
            opportunities.to_excel(filepath, index=False)
        elif format.lower() == 'json':
            filepath = reports_dir / f"{filename}.json"
            opportunities.to_json(filepath, orient='records', indent=2)
        else:
            raise ValueError(f"Неподдерживаемый формат: {format}")
        
        logger.info(f"Результаты экспортированы в файл: {filepath}")
        return str(filepath) 