"""
Модуль для анализа ликвидности и точного расчета потенциальной прибыли.

Этот модуль содержит функции для:
1. Анализа ликвидности предметов на основе истории продаж и текущего рыночного объема
2. Расчета реалистичной прибыли с учетом риска, комиссий и времени продажи
3. Интеграции с модулем машинного обучения для прогнозирования цен
"""

import logging
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
import statistics

# Настройка логирования
logger = logging.getLogger('liquidity_analyzer')

class LiquidityAnalyzer:
    """
    Анализирует ликвидность предметов и рассчитывает реалистичную потенциальную прибыль.
    """
    
    def __init__(self, api_client=None, ml_predictor=None):
        """
        Инициализация анализатора ликвидности.
        
        Args:
            api_client: API клиент для получения данных о рынке
            ml_predictor: Объект предиктора ML для прогнозирования цен (опционально)
        """
        self.api = api_client
        self.ml_predictor = ml_predictor
        self.fee_rate = 0.05  # Стандартная комиссия 5%
        self.price_cache = {}  # Кэш прогнозов цен
        self.liquidity_cache = {}  # Кэш оценок ликвидности
        self.cache_ttl = 3600  # Время жизни кэша в секундах (1 час)
        self.logger = logging.getLogger('liquidity_analyzer')
    
    async def analyze_item_liquidity(
        self, 
        item_data: Dict[str, Any],
        history_days: int = 7
    ) -> Dict[str, Any]:
        """
        Анализирует ликвидность предмета на основе истории продаж.
        
        Args:
            item_data: Данные о предмете
            history_days: Количество дней истории для анализа
            
        Returns:
            Словарь с оценкой ликвидности и связанными метриками
        """
        item_id = item_data.get('itemId', '')
        item_name = item_data.get('title', 'Unknown Item')
        
        # Проверяем кэш ликвидности
        cache_key = f"liquidity_{item_id}"
        if cache_key in self.liquidity_cache:
            cache_time, cache_data = self.liquidity_cache[cache_key]
            if time.time() - cache_time < self.cache_ttl:
                return cache_data
        
        # Получаем историю предмета
        if self.api:
            history_data = await self.api.get_item_history_safe(item_id, limit=100)
            history = history_data.get('history', [])
        else:
            history = []
            self.logger.warning(f"API клиент не доступен для анализа ликвидности: {item_name}")
        
        # Если история недоступна, используем базовую оценку
        if not history:
            basic_result = {
                'liquidity_score': 0.3,  # Низкая оценка ликвидности
                'avg_sales_per_day': 0.1,
                'price_volatility': 0.0,
                'estimated_sell_time_days': 14.0,  # Предполагаем, что продажа займет 2 недели
                'confidence': 0.2  # Низкая уверенность в оценке
            }
            self.liquidity_cache[cache_key] = (time.time(), basic_result)
            return basic_result
            
        # Анализируем историю продаж
        try:
            # Сортируем историю по дате
            sorted_history = sorted(history, key=lambda x: x.get('date', ''), reverse=True)
            
            # Разделяем историю по дням
            daily_sales = {}
            prices = []
            
            for sale in sorted_history:
                sale_date = sale.get('date', '')
                try:
                    date_obj = datetime.fromisoformat(sale_date.replace('Z', '+00:00'))
                    day_key = date_obj.strftime('%Y-%m-%d')
                    
                    if day_key not in daily_sales:
                        daily_sales[day_key] = []
                    
                    price_usd = float(sale.get('price', {}).get('USD', 0))
                    if price_usd > 0:
                        daily_sales[day_key].append(price_usd)
                        prices.append(price_usd)
                except (ValueError, TypeError, AttributeError) as e:
                    self.logger.warning(f"Ошибка при обработке даты продажи: {e}")
            
            # Расчет метрик ликвидности
            total_days = len(daily_sales.keys())
            total_sales = sum(len(sales) for sales in daily_sales.values())
            
            # Если данных слишком мало, используем консервативную оценку
            if total_days < 3 or total_sales < 5:
                result = {
                    'liquidity_score': 0.4,
                    'avg_sales_per_day': total_sales / max(total_days, 1),
                    'price_volatility': 0.05,
                    'estimated_sell_time_days': 10.0,
                    'confidence': 0.3
                }
                self.liquidity_cache[cache_key] = (time.time(), result)
                return result
            
            # Расчет среднего количества продаж в день
            avg_sales_per_day = total_sales / total_days
            
            # Расчет волатильности цен
            price_volatility = 0.0
            if len(prices) > 1:
                avg_price = statistics.mean(prices)
                variance = sum((p - avg_price) ** 2 for p in prices) / len(prices)
                std_dev = variance ** 0.5
                price_volatility = std_dev / avg_price if avg_price > 0 else 0.0
            
            # Оценка времени продажи
            estimated_sell_time_days = 1.0 / avg_sales_per_day if avg_sales_per_day > 0 else 14.0
            
            # Общая оценка ликвидности (от 0 до 1)
            # Учитываем:
            # - Среднее количество продаж в день (больше = лучше)
            # - Волатильность цен (меньше = лучше)
            # - Оценка времени продажи (меньше = лучше)
            
            # Нормализуем среднее количество продаж (максимум 10 продаж в день = 1.0)
            normalized_sales = min(avg_sales_per_day / 10.0, 1.0)
            
            # Нормализуем волатильность (0% = 1.0, 50% и выше = 0.0)
            normalized_volatility = max(1.0 - (price_volatility * 2.0), 0.0)
            
            # Нормализуем время продажи (1 день или меньше = 1.0, 30 дней и выше = 0.0)
            normalized_sell_time = max(1.0 - (estimated_sell_time_days / 30.0), 0.0)
            
            # Взвешенная оценка ликвидности
            liquidity_score = (
                normalized_sales * 0.5 +
                normalized_volatility * 0.3 +
                normalized_sell_time * 0.2
            )
            
            # Оценка уверенности в результате
            confidence = min(total_sales / 20.0, 1.0) * 0.7 + min(total_days / 14.0, 1.0) * 0.3
            
            result = {
                'liquidity_score': liquidity_score,
                'avg_sales_per_day': avg_sales_per_day,
                'price_volatility': price_volatility,
                'estimated_sell_time_days': estimated_sell_time_days,
                'confidence': confidence
            }
            
            # Кэшируем результат
            self.liquidity_cache[cache_key] = (time.time(), result)
            return result
            
        except Exception as e:
            self.logger.error(f"Ошибка при анализе ликвидности предмета {item_name}: {e}")
            
            # Возвращаем базовую оценку при ошибке
            fallback_result = {
                'liquidity_score': 0.3,
                'avg_sales_per_day': 0.2,
                'price_volatility': 0.1,
                'estimated_sell_time_days': 10.0,
                'confidence': 0.3
            }
            self.liquidity_cache[cache_key] = (time.time(), fallback_result)
            return fallback_result
    
    async def calculate_realistic_profit(
        self, 
        item_data: Dict[str, Any],
        buy_price: float = None,
        fee_rate: float = None,
        use_ml_prediction: bool = True
    ) -> Dict[str, Any]:
        """
        Рассчитывает реалистичную прибыль с учетом комиссий, рисков и ликвидности.
        
        Args:
            item_data: Данные о предмете
            buy_price: Цена покупки (если не указана, берется из item_data)
            fee_rate: Ставка комиссии (если не указана, используется стандартная)
            use_ml_prediction: Использовать ли ML для прогнозирования цен
            
        Returns:
            Словарь с расчетом прибыли и связанными метриками
        """
        item_id = item_data.get('itemId', '')
        item_name = item_data.get('title', 'Unknown Item')
        
        # Определяем цену покупки
        if buy_price is None:
            buy_price = float(item_data.get('price', {}).get('USD', 0))
        
        # Используем указанную ставку комиссии или стандартную
        fee_rate = fee_rate if fee_rate is not None else self.fee_rate
        
        # Получаем анализ ликвидности
        liquidity_data = await self.analyze_item_liquidity(item_data)
        
        # Определяем ожидаемую цену продажи
        expected_sell_price = 0.0
        
        # Если доступен ML предиктор и его нужно использовать, получаем прогноз
        prediction_confidence = 0.0
        if self.ml_predictor and use_ml_prediction:
            try:
                # Проверяем кэш прогнозов
                cache_key = f"prediction_{item_id}"
                if cache_key in self.price_cache:
                    cache_time, cache_data = self.price_cache[cache_key]
                    if time.time() - cache_time < self.cache_ttl:
                        prediction = cache_data
                    else:
                        prediction = await self.ml_predictor.predict_price(item_data)
                        self.price_cache[cache_key] = (time.time(), prediction)
                else:
                    prediction = await self.ml_predictor.predict_price(item_data)
                    self.price_cache[cache_key] = (time.time(), prediction)
                
                if prediction and 'predicted_price' in prediction:
                    expected_sell_price = prediction['predicted_price']
                    prediction_confidence = prediction.get('confidence', 0.5)
            except Exception as e:
                self.logger.warning(f"Ошибка получения ML прогноза для {item_name}: {e}")
        
        # Если ML прогноз не доступен или не нужен, используем среднюю цену из истории
        if expected_sell_price <= 0:
            # Получаем историю цен
            if self.api:
                history_data = await self.api.get_item_history_safe(item_id, limit=20)
                history = history_data.get('history', [])
                
                if history:
                    # Извлекаем цены из истории
                    prices = []
                    for sale in history:
                        price_usd = float(sale.get('price', {}).get('USD', 0))
                        if price_usd > 0:
                            prices.append(price_usd)
                    
                    if prices:
                        # Используем среднюю цену продаж как ожидаемую
                        expected_sell_price = statistics.mean(prices)
                        prediction_confidence = 0.6  # Средняя уверенность
            
            # Если нет истории, используем текущую цену плюс наценка
            if expected_sell_price <= 0:
                # Используем текущую цену предмета + 10% как ожидаемую цену продажи
                current_price = float(item_data.get('price', {}).get('USD', 0))
                expected_sell_price = current_price * 1.1
                prediction_confidence = 0.3  # Низкая уверенность
        
        # Расчет комиссий
        fees = expected_sell_price * fee_rate
        
        # Расчет чистой прибыли
        net_profit = expected_sell_price - fees - buy_price
        profit_percent = (net_profit / buy_price) * 100 if buy_price > 0 else 0
        
        # Оценка риска на основе ликвидности и уверенности в прогнозе
        liquidity_score = liquidity_data.get('liquidity_score', 0.3)
        sell_time_days = liquidity_data.get('estimated_sell_time_days', 10.0)
        price_volatility = liquidity_data.get('price_volatility', 0.1)
        
        # Оценка риска (от 0 до 1, где 0 = низкий риск, 1 = высокий риск)
        risk_score = (
            (1.0 - liquidity_score) * 0.4 +  # Низкая ликвидность = высокий риск
            (1.0 - prediction_confidence) * 0.3 +  # Низкая уверенность в прогнозе = высокий риск
            min(sell_time_days / 30.0, 1.0) * 0.2 +  # Долгое время продажи = высокий риск
            min(price_volatility * 2.0, 1.0) * 0.1  # Высокая волатильность = высокий риск
        )
        
        # Общая оценка возможности (от 0 до 1, где 1 = отличная возможность)
        # Учитываем прибыль и риск
        normalized_profit = min(profit_percent / 20.0, 1.0)  # 20% и выше считаем максимальной прибылью
        opportunity_score = normalized_profit * (1.0 - risk_score)
        
        # Формируем результат
        result = {
            'buy_price': buy_price,
            'expected_sell_price': expected_sell_price,
            'fees': fees,
            'net_profit': net_profit,
            'profit_percent': profit_percent,
            'risk_score': risk_score,
            'liquidity_score': liquidity_score,
            'estimated_sell_time_days': sell_time_days,
            'price_volatility': price_volatility,
            'prediction_confidence': prediction_confidence,
            'opportunity_score': opportunity_score
        }
        
        return result

async def main():
    """Тестовая функция для проверки модуля."""
    from src.api.api_wrapper import DMarketAPI
    import os
    from dotenv import load_dotenv
    
    # Загружаем переменные окружения
    load_dotenv()
    
    # Настройка логирования
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем API клиент
    api_key = os.getenv("DMARKET_API_KEY")
    api_secret = os.getenv("DMARKET_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("Не указаны DMARKET_API_KEY или DMARKET_API_SECRET в .env файле")
        return
    
    api_client = DMarketAPI(api_key, api_secret)
    
    # Инициализируем анализатор ликвидности
    analyzer = LiquidityAnalyzer(api_client)
    
    # Получаем тестовый предмет
    game_id = "a8db"  # CS2
    response = await api_client.get_market_items_async(
        game_id=game_id,
        limit=1,
        price_from=10.0,
        price_to=100.0,
        currency="USD"
    )
    
    if not response or not response.get("objects"):
        logger.error("Не удалось получить тестовый предмет")
        return
    
    test_item = response["objects"][0]
    
    # Анализируем ликвидность
    liquidity_data = await analyzer.analyze_item_liquidity(test_item)
    logger.info(f"Анализ ликвидности для {test_item.get('title')}:")
    logger.info(f"  Оценка ликвидности: {liquidity_data.get('liquidity_score', 0):.2f}")
    logger.info(f"  Среднее количество продаж в день: {liquidity_data.get('avg_sales_per_day', 0):.2f}")
    logger.info(f"  Оценка времени продажи: {liquidity_data.get('estimated_sell_time_days', 0):.2f} дней")
    
    # Расчет прибыли
    profit_data = await analyzer.calculate_realistic_profit(test_item)
    logger.info(f"Расчет прибыли для {test_item.get('title')}:")
    logger.info(f"  Цена покупки: ${profit_data.get('buy_price', 0):.2f}")
    logger.info(f"  Ожидаемая цена продажи: ${profit_data.get('expected_sell_price', 0):.2f}")
    logger.info(f"  Чистая прибыль: ${profit_data.get('net_profit', 0):.2f} ({profit_data.get('profit_percent', 0):.2f}%)")
    logger.info(f"  Оценка риска: {profit_data.get('risk_score', 0):.2f}")
    logger.info(f"  Общая оценка возможности: {profit_data.get('opportunity_score', 0):.2f}")

if __name__ == "__main__":
    asyncio.run(main()) 