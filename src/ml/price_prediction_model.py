"""
Модуль для предсказания цен предметов.
"""

import os
import logging
import pickle
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score

# Настройка логирования
logger = logging.getLogger("price_prediction")

class PricePredictionModel:
    """
    Модель для прогнозирования цен на основе исторических данных.
    """
    
    def __init__(self, game_id: str = "default", item_name: str = "unknown", 
                 model_type: str = "random_forest", model_dir: Optional[str] = None):
        """
        Инициализирует модель предсказания цен.
        
        Args:
            game_id (str): Идентификатор игры
            item_name (str): Имя предмета
            model_type (str): Тип модели (random_forest, gradient_boosting)
            model_dir (Optional[str]): Директория для сохранения модели
        """
        self.game_id = game_id
        self.item_name = item_name
        self.model_type = model_type
        self.model_dir = model_dir
        
        # Инициализация базовых атрибутов
        self.model = None
        self.scaler = StandardScaler()
        self.features = []
        self.target = "price"
        self.metrics = {}
        self.creation_date = datetime.now()
        self.last_training_date = None
        
        # Настройка логирования
        self.logger = logger
    
    def _prepare_features(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Подготавливает признаки для обучения или предсказания.
        
        Args:
            data (DataFrame): Исходные данные
            
        Returns:
            DataFrame: Подготовленные данные
        """
        # Создаем копию DataFrame
        df = data.copy()
        
        # Преобразуем даты в формат datetime
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], errors='coerce')
            
            # Добавляем признаки на основе даты
            df["dayofweek"] = df["date"].dt.dayofweek
            df["month"] = df["date"].dt.month
            df["hour"] = df["date"].dt.hour
            df["is_weekend"] = (df["dayofweek"] >= 5).astype(int)
            
        # Преобразуем категориальные признаки в числовые
        for col in df.select_dtypes(include=['object']).columns:
            if col not in ["date", "title", self.target]:
                df[col] = pd.factorize(df[col])[0]
        
        # Удаляем ненужные признаки
        features_to_drop = ["date", "title"] 
        for col in features_to_drop:
            if col in df.columns:
                df.drop(col, axis=1, inplace=True)
        
        # Заполняем оставшиеся пропуски (используем обновленные методы)
        df.ffill(inplace=True)  # Вместо df.fillna(method="ffill", inplace=True)
        df.bfill(inplace=True)  # Вместо df.fillna(method="bfill", inplace=True)
        
        # Возвращаем только X и y для совместимости с тестами
        if self.target in df.columns:
            X = df.drop(self.target, axis=1)
            y = df[self.target]
            return X, y
        
        return df
    
    def train(self, data: Union[pd.DataFrame, List[Dict[str, Any]]], test_size: float = 0.2, 
              model_type: Optional[str] = None) -> Dict[str, float]:
        """
        Обучает модель на исторических данных.
        
        Args:
            data (Union[DataFrame, List[Dict]]): Исторические данные
            test_size (float): Размер тестовой выборки (0 до 1)
            model_type (Optional[str]): Тип модели (random_forest, gradient_boosting)
            
        Returns:
            Dict[str, float]: Метрики качества модели
        """
        # Преобразуем список словарей в DataFrame, если необходимо
        if isinstance(data, list):
            data = pd.DataFrame(data)
        
        # Обновляем тип модели, если он задан
        if model_type:
            self.model_type = model_type
        
        try:
            # Подготавливаем данные
            X, y = self._prepare_features(data)
            
            # Сохраняем список признаков
            self.features = X.columns.tolist()
            
            # Масштабируем признаки
            X_scaled = self.scaler.fit_transform(X)
            
            # Разделяем на обучающую и тестовую выборки
            X_train, X_test, y_train, y_test = train_test_split(X_scaled, y, test_size=test_size, random_state=42)
            
            # Создаем и обучаем модель в зависимости от выбранного типа
            if self.model_type == "gradient_boosting":
                self.model = GradientBoostingRegressor(n_estimators=100, random_state=42)
            else:  # По умолчанию random_forest
                self.model = RandomForestRegressor(n_estimators=100, random_state=42)
            
            # Обучаем модель
            self.model.fit(X_train, y_train)
            
            # Вычисляем метрики на тестовой выборке
            y_pred = self.model.predict(X_test)
            
            # Регистрируем метрики
            self.metrics = {
                "mse": mean_squared_error(y_test, y_pred),
                "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
                "r2": r2_score(y_test, y_pred)
            }
            
            # Обновляем дату последнего обучения
            self.last_training_date = datetime.now()
            
            return self.metrics
            
        except Exception as e:
            self.logger.error(f"Ошибка при обучении модели: {e}")
            raise
    
    def predict(self, data: Union[pd.DataFrame, Dict[str, Any]]) -> float:
        """
        Прогнозирует цену для заданных данных.
        
        Args:
            data (Union[DataFrame, Dict]): Данные для предсказания
            
        Returns:
            float: Прогнозируемая цена
        """
        if self.model is None:
            raise ValueError("Модель не обучена. Сначала выполните метод train().")
        
        try:
            # Преобразуем словарь в DataFrame, если необходимо
            if isinstance(data, dict):
                data = pd.DataFrame([data])
            
            # Подготавливаем данные
            X, _ = self._prepare_features(data)
            
            # Проверяем соответствие признаков
            missing_features = set(self.features) - set(X.columns)
            if missing_features:
                self.logger.warning(f"Отсутствуют признаки: {missing_features}. Заполняем нулями.")
                for feature in missing_features:
                    X[feature] = 0
                    
            # Выбираем только нужные признаки в правильном порядке
            X = X[self.features]
            
            # Масштабируем признаки
            X_scaled = self.scaler.transform(X)
            
            # Выполняем предсказание
            prediction = self.model.predict(X_scaled)
            
            # Возвращаем результат
            return float(prediction[0])
            
        except Exception as e:
            self.logger.error(f"Ошибка при предсказании: {e}")
            return 0.0
    
    def save(self, model_path: Optional[str] = None) -> str:
        """
        Сохраняет модель в файл.
        
        Args:
            model_path (Optional[str]): Путь для сохранения модели или None для автоматического определения
            
        Returns:
            str: Путь к сохраненной модели
        """
        if self.model is None:
            raise ValueError("Модель не обучена. Сначала выполните метод train().")
        
        try:
            # Определяем путь для сохранения
            if model_path is None:
                if self.model_dir is None:
                    raise ValueError("Директория для сохранения модели не указана.")
                
                # Создаем имя файла на основе игры и предмета
                filename = f"{self.game_id}_{self.item_name.replace(' ', '_')}.pkl"
                model_path = os.path.join(self.model_dir, filename)
            
            # Создаем директорию, если она не существует
            os.makedirs(os.path.dirname(model_path), exist_ok=True)
            
            # Создаем словарь с данными модели
            model_data = {
                "model": self.model,
                "scaler": self.scaler,
                "features": self.features,
                "target": self.target,
                "metrics": self.metrics,
                "game_id": self.game_id,
                "item_name": self.item_name,
                "model_type": self.model_type,
                "creation_date": self.creation_date,
                "last_training_date": self.last_training_date
            }
            
            # Сохраняем в файл
            with open(model_path, "wb") as f:
                pickle.dump(model_data, f)
            
            self.logger.info(f"Модель сохранена в {model_path}")
            return model_path
            
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении модели: {e}")
            raise
    
    @classmethod
    def load(cls, model_path: str) -> Optional['PricePredictionModel']:
        """
        Загружает модель из файла.
        
        Args:
            model_path (str): Путь к файлу модели
            
        Returns:
            Optional[PricePredictionModel]: Загруженная модель или None в случае ошибки
        """
        try:
            # Проверяем существование файла
            if not os.path.exists(model_path):
                logger.error(f"Файл модели {model_path} не существует")
                return None
            
            # Загружаем данные модели
            with open(model_path, "rb") as f:
                model_data = pickle.load(f)
            
            # Создаем экземпляр класса
            model_dir = os.path.dirname(model_path)
            instance = cls(
                game_id=model_data.get("game_id", "default"),
                item_name=model_data.get("item_name", "unknown"),
                model_type=model_data.get("model_type", "random_forest"),
                model_dir=model_dir
            )
            
            # Устанавливаем атрибуты
            instance.model = model_data.get("model")
            instance.scaler = model_data.get("scaler")
            instance.features = model_data.get("features", [])
            instance.target = model_data.get("target", "price")
            instance.metrics = model_data.get("metrics", {})
            instance.creation_date = model_data.get("creation_date", datetime.now())
            instance.last_training_date = model_data.get("last_training_date")
            
            logger.info(f"Модель успешно загружена из {model_path}")
            return instance
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке модели из {model_path}: {e}")
            return None

def create_sample_model() -> Optional[PricePredictionModel]:
    """
    Создает и обучает образец модели на синтетических данных.
    
    Returns:
        Optional[PricePredictionModel]: Обученная модель или None в случае ошибки
    """
    try:
        # Создаем синтетические данные
        np.random.seed(42)
        dates = [datetime.now() - timedelta(days=i) for i in range(30)]
        
        data = pd.DataFrame({
            "date": dates,
            "price": np.random.normal(100, 10, 30),  # Цены с нормальным распределением
            "volume": np.random.randint(10, 100, 30)  # Объемы торгов
        })
        
        # Добавляем тренд
        data["price"] = data["price"] + np.linspace(0, 20, 30)
        
        # Создаем и обучаем модель
        model = PricePredictionModel(game_id="default", item_name="sample_item")
        metrics = model.train(data)
        
        logger.info(f"Создана образцовая модель с метриками: {metrics}")
        return model
        
    except Exception as e:
        logger.error(f"Ошибка при создании образцовой модели: {e}")
        return None 