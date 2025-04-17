"""
Модуль для прогнозирования цен предметов с использованием машинного обучения.

Этот модуль предоставляет функциональность для:
- Сбора и обработки исторических данных о ценах
- Обучения моделей машинного обучения
- Прогнозирования будущих цен и трендов
- Оценки потенциальной прибыльности предметов
"""

import logging
import asyncio
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Union, Any
from pathlib import Path
import pickle
import os
import joblib

# Для машинного обучения
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split, GridSearchCV

# Импортируем необходимые модули
from src.api.api_wrapper import DMarketAPI
from src.config.config import Config
from src.utils.error_handler import TradingError, handle_exceptions, ErrorType

# Настраиваем логирование
logger = logging.getLogger(__name__)


class PricePredictor:
    """
    Класс для прогнозирования цен предметов на основе машинного обучения.
    """

    def __init__(self, api: Optional[DMarketAPI] = None):
        """
        Инициализирует предсказатель цен.
        
        Args:
            api: Экземпляр API DMarket (если не указан, будет создан новый)
        """
        self.api = api or DMarketAPI()

        # Путь для сохранения/загрузки моделей
        self.models_dir = Path(Config.get_path("models"))
        os.makedirs(self.models_dir, exist_ok=True)

        # Параметры для моделей
        self.feature_columns = ['price', 'volume', 'liquidity', 'days_from_release']
        self.target_column = 'next_price'

        # Словарь обученных моделей для разных игр/предметов
        self.models = {}
        self.scalers = {}

    async def get_historical_data(
        self,
        game: str,
        item_name: Optional[str] = None,
        days: int = 30
    ) -> pd.DataFrame:
        """
        Получает исторические данные о ценах предметов.

        Args:
            game: Код игры
            item_name: Название предмета (если None, данные по всем популярным предметам)
            days: Количество дней истории

        Returns:
            DataFrame с историческими данными
        """
        try:
            if item_name:
                # Получаем данные для конкретного предмета
                item_data = await self.api.get_item_price_history(game, item_name, days)
                if not item_data:
                    logger.warning(
                        f"Не удалось получить исторические данные для {item_name} в {game}")
                    return pd.DataFrame()

                # Формируем DataFrame
                df = pd.DataFrame(item_data)
                df['item_name'] = item_name
            else:
                # Получаем данные по популярным предметам
                items = await self.api.get_popular_items(game, limit=50)

                all_data = []
                for item in items:
                    item_name = item.get('title')
                    item_data = await self.api.get_item_price_history(game, item_name, days)
                    if item_data:
                        item_df = pd.DataFrame(item_data)
                        item_df['item_name'] = item_name
                        all_data.append(item_df)

                    # Задержка между запросами
                    await asyncio.sleep(0.5)

                if not all_data:
                    logger.warning(f"Не удалось получить исторические данные для игры {game}")
                    return pd.DataFrame()

                # Объединяем данные
                df = pd.concat(all_data, ignore_index=True)

            # Обрабатываем и преобразуем данные
            if not df.empty:
                # Преобразуем временные метки
                df['date'] = pd.to_datetime(df['timestamp'])

                # Сортируем по дате
                df.sort_values(['item_name', 'date'], inplace=True)

                # Рассчитываем дополнительные признаки
                df['day_of_week'] = df['date'].dt.dayofweek
                df['month'] = df['date'].dt.month

                # Добавляем смещенную цену как целевую переменную
                df['next_price'] = df.groupby('item_name')['price'].shift(-1)

                # Рассчитываем скользящие средние
                df['price_ma7'] = df.groupby('item_name')['price'].transform(
                    lambda x: x.rolling(window=7, min_periods=1).mean()
                )
                df['price_ma14'] = df.groupby('item_name')['price'].transform(
                    lambda x: x.rolling(window=14, min_periods=1).mean()
                )

                # Рассчитываем изменение цены
                df['price_change'] = df.groupby('item_name')['price'].pct_change()

                # Обрабатываем пропущенные значения
                df.fillna(method='ffill', inplace=True)
                df.fillna(method='bfill', inplace=True)
                df.fillna(0, inplace=True)

            return df

        except Exception as e:
            logger.error(f"Ошибка при получении исторических данных: {e}")
            return pd.DataFrame()
    
    def prepare_features(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Подготавливает признаки и целевую переменную для обучения модели.
        
        Args:
            df: DataFrame с историческими данными
            
        Returns:
            Tuple[pd.DataFrame, pd.Series]: X (признаки) и y (целевая переменная)
        """
        if df.empty:
            return pd.DataFrame(), pd.Series()

        # Удаляем строки, где целевая переменная отсутствует
        df = df.dropna(subset=[self.target_column])

        # Создаем дополнительные признаки если нужно
        if 'volume' not in df.columns:
            df['volume'] = 1  # Заполняем дефолтным значением

        if 'liquidity' not in df.columns:
            df['liquidity'] = 5  # Среднее значение ликвидности

        if 'days_from_release' not in df.columns:
            df['days_from_release'] = 365  # Дефолтное значение

        # Используем категориальные признаки
        if 'day_of_week' in df.columns:
            df = pd.get_dummies(df, columns=['day_of_week'], prefix='dow')

        if 'month' in df.columns:
            df = pd.get_dummies(df, columns=['month'], prefix='month')

        # Выбираем числовые признаки и целевую переменную
        feature_cols = [col for col in df.columns if col not in [
            self.target_column, 'date', 'timestamp', 'item_name'
        ]]

        X = df[feature_cols]
        y = df[self.target_column]

        return X, y

    def train_model(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_type: str = 'random_forest',
        game_code: str = 'cs2',
        item_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Обучает модель на предоставленных данных.
        
        Args:
            X: DataFrame с признаками
            y: Series с целевой переменной
            model_type: Тип модели ('random_forest', 'gradient_boosting', 'linear')
            game_code: Код игры
            item_name: Название предмета (если None, общая модель для игры)
            
        Returns:
            Dict[str, Any]: Словарь с обученной моделью и метриками
        """
        if X.empty or len(y) == 0:
            logger.error("Недостаточно данных для обучения модели")
            return {}

        # Разбиваем на обучающую и тестовую выборки
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        # Масштабируем признаки
        scaler = MinMaxScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)

        # Выбираем модель в зависимости от типа
        if model_type == 'random_forest':
            model = RandomForestRegressor(n_estimators=100, random_state=42)
        elif model_type == 'gradient_boosting':
            model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        elif model_type == 'linear':
            model = LinearRegression()
        else:
            logger.error(f"Неизвестный тип модели: {model_type}")
            return {}
        
        # Обучаем модель
        model.fit(X_train_scaled, y_train)
        
        # Оцениваем модель
        y_pred = model.predict(X_test_scaled)
        
        # Рассчитываем метрики
        mse = mean_squared_error(y_test, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        logger.info(f"Модель обучена: {model_type}, {game_code}/{item_name}, "
                    f"RMSE={rmse:.4f}, MAE={mae:.4f}, R²={r2:.4f}")

        # Сохраняем модель и масштабизатор
        model_key = self._get_model_key(game_code, item_name)
        self.models[model_key] = model
        self.scalers[model_key] = scaler

        # Сохраняем на диск
        self._save_model(game_code, item_name, model, scaler, model_type)

        return {
            'model': model,
            'scaler': scaler,
            'metrics': {
                'mse': mse,
                'rmse': rmse,
                'mae': mae,
                'r2': r2
            },
            'feature_names': X.columns.tolist()
        }

    def _get_model_key(self, game_code: str, item_name: Optional[str] = None) -> str:
        """
        Формирует ключ для хранения модели.

        Args:
            game_code: Код игры
            item_name: Название предмета (если None, общая модель для игры)

        Returns:
            str: Ключ модели
        """
        if item_name:
            return f"{game_code}_{item_name}"
        else:
            return game_code

    def _save_model(
        self,
        game_code: str,
        item_name: Optional[str],
        model: Any,
        scaler: Any,
        model_type: str
    ) -> bool:
        """
        Сохраняет модель и масштабизатор на диск.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            model: Обученная модель
            scaler: Масштабизатор признаков
            model_type: Тип модели
            
        Returns:
            bool: True если сохранение успешно, иначе False
        """
        try:
            model_key = self._get_model_key(game_code, item_name)
            model_dir = self.models_dir / game_code
            os.makedirs(model_dir, exist_ok=True)

            # Создаем имя файла
            if item_name:
                safe_name = "".join(c if c.isalnum() else "_" for c in item_name)
                file_name = f"{safe_name}_{model_type}"
            else:
                file_name = f"general_{model_type}"

            # Сохраняем модель
            model_path = model_dir / f"{file_name}.joblib"
            joblib.dump(model, model_path)

            # Сохраняем скейлер
            scaler_path = model_dir / f"{file_name}_scaler.joblib"
            joblib.dump(scaler, scaler_path)

            logger.info(f"Модель сохранена: {model_path}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка при сохранении модели: {e}")
            return False
    
    def load_model(self, game_code: str, item_name: Optional[str] = None, model_type: str = 'random_forest') -> bool:
        """
        Загружает модель из файла.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            model_type: Тип модели
            
        Returns:
            bool: True если загрузка успешна, иначе False
        """
        try:
            model_key = self._get_model_key(game_code, item_name)
            model_dir = self.models_dir / game_code

            # Создаем имя файла
            if item_name:
                safe_name = "".join(c if c.isalnum() else "_" for c in item_name)
                file_name = f"{safe_name}_{model_type}"
            else:
                file_name = f"general_{model_type}"

            # Пути к файлам модели и скейлера
            model_path = model_dir / f"{file_name}.joblib"
            scaler_path = model_dir / f"{file_name}_scaler.joblib"

            # Проверяем существование файлов
            if not model_path.exists() or not scaler_path.exists():
                logger.warning(f"Модель или скейлер не найдены: {model_path}")
                return False

            # Загружаем модель и скейлер
            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)

            # Сохраняем в словари
            self.models[model_key] = model
            self.scalers[model_key] = scaler

            logger.info(f"Модель загружена: {model_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели: {e}")
            return False

    @handle_exceptions(ErrorType.DATA_ERROR)
    async def predict_price(
        self,
        game_code: str,
        item_name: str,
        days_ahead: int = 7,
        model_type: str = 'random_forest'
    ) -> Dict[str, Any]:
        """
        Прогнозирует цену предмета на указанное количество дней вперед.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days_ahead: Количество дней для прогноза
            model_type: Тип модели
            
        Returns:
            Dict[str, Any]: Словарь с прогнозом
        """
        model_key = self._get_model_key(game_code, item_name)

        # Проверяем, загружена ли модель, если нет - пробуем загрузить
        if model_key not in self.models:
            model_loaded = self.load_model(game_code, item_name, model_type)

            # Если модель не удалось загрузить, пробуем загрузить общую модель для игры
            if not model_loaded:
                game_model_key = self._get_model_key(game_code)
                if game_model_key not in self.models:
                    model_loaded = self.load_model(game_code, None, model_type)

                    # Если и общую модель не удалось загрузить, тренируем новую
                    if not model_loaded:
                        logger.info(f"Обучаем новую модель для {game_code}/{item_name}")
                        # Получаем исторические данные
                        df = await self.get_historical_data(game_code, item_name, days=60)
                        if df.empty:
                            raise TradingError(
                                f"Недостаточно данных для предсказания цены {item_name}",
                                ErrorType.DATA_ERROR
                            )

                        # Подготавливаем признаки и обучаем модель
                        X, y = self.prepare_features(df)
                        self.train_model(X, y, model_type, game_code, item_name)

                # Используем общую модель для игры
                model = self.models.get(game_model_key)
                scaler = self.scalers.get(game_model_key)
            else:
                # Используем модель для конкретного предмета
                model = self.models.get(model_key)
                scaler = self.scalers.get(model_key)
        else:
            # Используем уже загруженную модель
            model = self.models.get(model_key)
            scaler = self.scalers.get(model_key)

        # Проверяем, что модель загружена
        if not model or not scaler:
            raise TradingError(
                f"Не удалось загрузить модель для {item_name}",
                ErrorType.DATA_ERROR
            )

        # Получаем последние данные о предмете
        df = await self.get_historical_data(game_code, item_name, days=30)
        if df.empty:
            raise TradingError(
                f"Не удалось получить данные для {item_name}",
                ErrorType.DATA_ERROR
            )

        # Подготавливаем данные для прогноза
        latest_data = df.iloc[-1].copy()
        current_price = latest_data['price']

        # Создаем пустой DataFrame для прогноза
        forecast_df = pd.DataFrame()

        # Заполняем начальные данные
        last_price = current_price

        # Делаем прогноз на указанное количество дней
        forecasted_prices = []
        dates = []

        for i in range(1, days_ahead + 1):
            # Создаем новую строку с признаками
            new_row = {}

            # Базовые признаки
            new_row['price'] = last_price
            new_row['volume'] = latest_data.get('volume', 1)
            new_row['liquidity'] = latest_data.get('liquidity', 5)
            new_row['days_from_release'] = latest_data.get('days_from_release', 365) + i

            # Дополнительные признаки
            forecast_date = pd.to_datetime(latest_data['date']) + timedelta(days=i)
            new_row['day_of_week'] = forecast_date.dayofweek
            new_row['month'] = forecast_date.month

            # Преобразуем в DataFrame для обработки категориальных признаков
            temp_df = pd.DataFrame([new_row])

            # Создаем dummy переменные
            if 'day_of_week' in temp_df.columns:
                temp_df = pd.get_dummies(temp_df, columns=['day_of_week'], prefix='dow')

            if 'month' in temp_df.columns:
                temp_df = pd.get_dummies(temp_df, columns=['month'], prefix='month')

            # Добавляем отсутствующие столбцы
            for col in X.columns:
                if col not in temp_df.columns:
                    temp_df[col] = 0

            # Оставляем только столбцы, которые использовались при обучении
            temp_df = temp_df[X.columns]

            # Масштабируем данные
            scaled_data = scaler.transform(temp_df)

            # Делаем прогноз
            predicted_price = model.predict(scaled_data)[0]

            # Обновляем последнюю цену для следующей итерации
            last_price = predicted_price

            # Сохраняем результат
            forecasted_prices.append(predicted_price)
            dates.append(forecast_date)

        # Создаем результат
        result = {
            'item_name': item_name,
            'game': game_code,
            'current_price': current_price,
            'forecast': [
                {
                    'date': date.strftime('%Y-%m-%d'),
                    'price': price,
                    'change': ((price / current_price) - 1) * 100  # Изменение в процентах
                }
                for date, price in zip(dates, forecasted_prices)
            ],
            'trend': 'up' if forecasted_prices[-1] > current_price else 'down',
            'expected_change': ((forecasted_prices[-1] / current_price) - 1) * 100,
            'confidence': self._calculate_confidence(forecasted_prices, current_price)
        }

        return result

    def _calculate_confidence(self, prices: List[float], current_price: float) -> float:
        """
        Рассчитывает уровень доверия к прогнозу.
        
        Args:
            prices: Список прогнозируемых цен
            current_price: Текущая цена
            
        Returns:
            float: Уровень доверия (от 0 до 1)
        """
        # Простой алгоритм: чем стабильнее тренд, тем выше доверие
        if len(prices) <= 1:
            return 0.5

        # Рассчитываем стандартное отклонение изменений
        changes = np.diff(prices) / prices[:-1]
        std_dev = np.std(changes)

        # Если стандартное отклонение высокое, доверие низкое
        confidence = max(0, min(1, 1 - std_dev * 10))

        return confidence

    async def analyze_item_investment(
        self,
        game_code: str,
        item_name: str,
        days_ahead: int = 30,
        model_type: str = 'random_forest'
    ) -> Dict[str, Any]:
        """
        Анализирует инвестиционную привлекательность предмета.
        
        Args:
            game_code: Код игры
            item_name: Название предмета
            days_ahead: Количество дней для прогноза
            model_type: Тип модели
            
        Returns:
            Dict[str, Any]: Результаты анализа
        """
        try:
            # Получаем прогноз цены
            forecast = await self.predict_price(game_code, item_name, days_ahead, model_type)

            # Получаем текущую информацию о предмете
            item_info = await self.api.get_item_info(game_code, item_name)

            current_price = forecast['current_price']
            final_price = forecast['forecast'][-1]['price']

            # Рассчитываем потенциальную прибыль
            profit = final_price - current_price
            profit_percent = ((final_price / current_price) - 1) * 100 if current_price > 0 else 0

            # Рассчитываем ROI с учетом комиссии
            game_config = Config.get_game_config(game_code)
            commission = game_config.get('fee', 0.07) if game_config else 0.07

            # Для предметов высокого спроса используем пониженную комиссию
            is_high_demand = item_info.get('liquidity', 0) > 7
            if is_high_demand and game_config:
                commission = game_config.get('high_demand_fee', 0.02)

            # Рассчитываем чистую прибыль
            net_profit = final_price * (1 - commission) - current_price
            roi = (net_profit / current_price) * 100 if current_price > 0 else 0

            # Оцениваем риск
            risk_score = self._calculate_risk_score(
                forecast['confidence'],
                profit_percent,
                item_info.get('liquidity', 5)
            )

            # Формируем результат
            result = {
                'item_name': item_name,
                'game': game_code,
                'current_price': current_price,
                'predicted_price': final_price,
                'profit': profit,
                'profit_percent': profit_percent,
                'commission': commission * 100,  # в процентах
                'net_profit': net_profit,
                'roi': roi,
                'confidence': forecast['confidence'],
                'risk_score': risk_score,
                'risk_level': self._get_risk_level(risk_score),
                'recommendation': self._get_recommendation(roi, risk_score),
                'forecast': forecast['forecast']
            }

            return result

        except Exception as e:
            logger.error(f"Ошибка при анализе инвестиций: {e}")
            raise TradingError(
                f"Не удалось проанализировать предмет: {str(e)}",
                ErrorType.DATA_ERROR,
                original_exception=e
            )

    def _calculate_risk_score(
        self,
        confidence: float,
        profit_percent: float,
        liquidity: float
    ) -> float:
        """
        Рассчитывает показатель риска инвестиции.
        
        Args:
            confidence: Уровень доверия к прогнозу (0-1)
            profit_percent: Ожидаемая прибыль в процентах
            liquidity: Показатель ликвидности предмета (0-10)
            
        Returns:
            float: Показатель риска (0-10, где 0 - минимальный риск)
        """
        # Базовый риск - обратно пропорционален доверию
        base_risk = 10 * (1 - confidence)

        # Корректируем на основе прибыли (высокая прибыль - выше риск)
        profit_factor = min(10, max(0, profit_percent)) / 10

        # Корректируем на основе ликвидности (низкая ликвидность - выше риск)
        liquidity_factor = (10 - min(10, max(0, liquidity))) / 10

        # Взвешенная сумма факторов
        risk_score = (base_risk * 0.5) + (profit_factor * 0.3) + (liquidity_factor * 0.2)

        # Ограничиваем значение от 0 до 10
        return min(10, max(0, risk_score))

    def _get_risk_level(self, risk_score: float) -> str:
        """
        Возвращает текстовое описание уровня риска.
        
        Args:
            risk_score: Показатель риска (0-10)
            
        Returns:
            str: Текстовое описание риска
        """
        if risk_score < 2:
            return "очень низкий"
        elif risk_score < 4:
            return "низкий"
        elif risk_score < 6:
            return "средний"
        elif risk_score < 8:
            return "высокий"
        else:
            return "очень высокий"

    def _get_recommendation(self, roi: float, risk_score: float) -> str:
        """
        Формирует рекомендацию по инвестированию.
        
        Args:
            roi: Ожидаемая доходность инвестиции в процентах
            risk_score: Показатель риска (0-10)
            
        Returns:
            str: Рекомендация
        """
        # Соотношение доходности к риску
        ratio = roi / (risk_score + 0.1)  # +0.1 чтобы избежать деления на ноль

        if ratio > 10:
            return "Очень привлекательная инвестиция"
        elif ratio > 5:
            return "Привлекательная инвестиция"
        elif ratio > 2:
            return "Умеренно привлекательная инвестиция"
        elif ratio > 1:
            return "Нейтральная инвестиция"
        else:
            return "Непривлекательная инвестиция"

# Функция для запуска в качестве отдельного модуля


async def main():
    """
    Основная функция для запуска модуля в качестве отдельного приложения.
    """
    import argparse

    # Настраиваем аргументы командной строки
    parser = argparse.ArgumentParser(description='Анализ и прогнозирование цен предметов')
    parser.add_argument('--game', type=str, default='cs2', help='Код игры (cs2, dota2, tf2, rust)')
    parser.add_argument('--item', type=str, help='Название предмета для анализа')
    parser.add_argument('--days', type=int, default=30, help='Количество дней для прогноза')
    parser.add_argument('--model', type=str, default='random_forest',
                        choices=['random_forest', 'gradient_boosting', 'linear'],
                        help='Тип модели для прогнозирования')
    parser.add_argument('--train', action='store_true', help='Обучить новую модель')

    args = parser.parse_args()

    # Инициализируем предсказатель
    predictor = PricePredictor()

    if args.train:
        print(f"Обучение модели для {args.game}...")
        # Получаем исторические данные
        df = await predictor.get_historical_data(args.game, args.item, days=60)
        if df.empty:
            print("Не удалось получить исторические данные")
            return

        # Подготавливаем признаки и обучаем модель
        X, y = predictor.prepare_features(df)
        result = predictor.train_model(X, y, args.model, args.game, args.item)

        if result:
            print(f"Модель обучена. Метрики:")
            for metric, value in result['metrics'].items():
                print(f"  {metric}: {value:.4f}")
        else:
            print("Не удалось обучить модель")

    if args.item:
        print(f"Анализ предмета {args.item} в {args.game}...")
        try:
            # Получаем анализ инвестиций
            analysis = await predictor.analyze_item_investment(
                args.game, args.item, args.days, args.model
            )

            print("\nРезультаты анализа:")
            print(f"Предмет: {analysis['item_name']} ({analysis['game']})")
            print(f"Текущая цена: ${analysis['current_price']:.2f}")
            print(f"Прогноз через {args.days} дней: ${analysis['predicted_price']:.2f}")
            print(
                f"Потенциальная прибыль: ${analysis['profit']:.2f} ({analysis['profit_percent']:.2f}%)")
            print(
                f"Чистая прибыль (с учетом комиссии {analysis['commission']:.1f}%): ${analysis['net_profit']:.2f}")
            print(f"ROI: {analysis['roi']:.2f}%")
            print(f"Уровень доверия: {analysis['confidence']:.2f}")
            print(f"Уровень риска: {analysis['risk_level']} ({analysis['risk_score']:.2f}/10)")
            print(f"Рекомендация: {analysis['recommendation']}")

            print("\nПрогноз по дням:")
            for day in analysis['forecast']:
                print(f"{day['date']}: ${day['price']:.2f} ({day['change']:+.2f}%)")

        except Exception as e:
            print(f"Ошибка при анализе: {e}")

    print("\nЗавершено")

# Запуск как отдельного модуля
if __name__ == "__main__":
    asyncio.run(main())
