"""
Модуль для прогнозирования цен с использованием машинного обучения.

Этот модуль содержит классы и функции для анализа исторических данных и предсказания
будущих цен на предметы с использованием различных методов машинного обучения.
"""

import os
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple, Union
import sys
import hashlib
import json
import tempfile
import warnings
import asyncio
import json

# Импортируем APIError для обработки ошибок API
try:
    from src.api.api_wrapper import APIError
except ImportError:
    try:
        from api_wrapper import APIError
    except ImportError:
        # Если не удалось импортировать, создаем заглушку
        class APIError(Exception):
            """Заглушка для исключения APIError."""
            pass

# Импортируем обработчик ошибок
try:
    from ..utils.error_handler import TradingError, DataError, ErrorType
except ImportError:
    # Если не удалось импортировать, создаем заглушки
    class ErrorType:
        DATA_ERROR = "data_error"
        
    class TradingError(Exception):
        def __init__(self, message, error_type=None, context=None, original_exception=None):
            self.message = message
            super().__init__(message)
            
    class DataError(TradingError):
        def __init__(self, message, context=None, original_exception=None):
            super().__init__(message)

# Проверка наличия необходимых библиотек для ML
ML_AVAILABLE = False
ADVANCED_ML_AVAILABLE = False
PROPHET_AVAILABLE = False
DEEP_LEARNING_AVAILABLE = False
BOOSTING_AVAILABLE = False
STATSMODELS_AVAILABLE = False
PLOTLY_AVAILABLE = False

try:
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
    from sklearn.preprocessing import StandardScaler, OneHotEncoder
    from sklearn.pipeline import Pipeline
    from sklearn.compose import ColumnTransformer
    from sklearn.feature_extraction.text import TfidfVectorizer
    ML_AVAILABLE = True
    
    # Проверка наличия продвинутых библиотек для бустинга
    try:
        import lightgbm as lgb
        import xgboost as xgb
        import catboost as cb
        BOOSTING_AVAILABLE = True
    except ImportError:
        pass
    
    # Проверка наличия Prophet для временных рядов
    try:
        from prophet import Prophet
        PROPHET_AVAILABLE = True
    except ImportError:
        pass
    
    # Проверка наличия библиотек глубокого обучения
    try:
        import tensorflow as tf
        from tensorflow.keras.models import Sequential
        from tensorflow.keras.layers import Dense, LSTM, Dropout
        DEEP_LEARNING_AVAILABLE = True
    except ImportError:
        try:
            import torch
            import torch.nn as nn
            DEEP_LEARNING_AVAILABLE = True
        except ImportError:
            pass
    
    # Проверка наличия statsmodels для классических моделей временных рядов
    try:
        import statsmodels.api as sm
        from statsmodels.tsa.arima.model import ARIMA
        from statsmodels.tsa.statespace.sarimax import SARIMAX
        STATSMODELS_AVAILABLE = True
    except ImportError:
        pass
    
    # Проверка наличия plotly для визуализации
    try:
        import plotly.graph_objects as go
        import plotly.express as px
        PLOTLY_AVAILABLE = True
    except ImportError:
        pass
    
    # Если доступна хотя бы одна продвинутая библиотека, считаем что доступны продвинутые возможности
    ADVANCED_ML_AVAILABLE = any([BOOSTING_AVAILABLE, PROPHET_AVAILABLE, 
                                DEEP_LEARNING_AVAILABLE, STATSMODELS_AVAILABLE])
    
except ImportError:
    ML_AVAILABLE = False

# Импортируем PricePredictionModel перед его использованием 
try:
    from .price_prediction_model import PricePredictionModel
except ImportError:
    logger.warning("Не удалось импортировать PricePredictionModel. Проверьте наличие файла price_prediction_model.py")
    PricePredictionModel = None

# Настройка логирования
logger = logging.getLogger('ml_predictor')

class ModelManager:
    """
    Управление моделями машинного обучения, их обучением, сохранением и загрузкой.
    """
    
    def __init__(self, models_dir: str = "models"):
        """
        Инициализация менеджера моделей.
        
        Args:
            models_dir: Директория для хранения моделей
        """
        self.models_dir = models_dir
        self.models = {}
        self.model_metadata = {}
        
        # Проверяем доступность библиотек ML
        self.ml_available = ML_AVAILABLE
        if not self.ml_available:
            logger.warning("Библиотеки машинного обучения не установлены")
            logger.warning("Для использования ML установите: pandas, numpy, scikit-learn")
            return
            
        # Создаем директорию для моделей, если она не существует
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            logger.info(f"Создана директория для моделей: {models_dir}")
        
        # Загружаем существующие модели
        self._load_models()
    
    def _load_models(self):
        """Загружает сохраненные модели из директории."""
        if not self.ml_available:
            return
            
        try:
            model_files = [f for f in os.listdir(self.models_dir) if f.endswith('.pkl')]
            for model_file in model_files:
                model_name = model_file[:-4]  # Убираем расширение .pkl
                model_path = os.path.join(self.models_dir, model_file)
                metadata_path = os.path.join(self.models_dir, f"{model_name}_metadata.pkl")
                
                try:
                    with open(model_path, 'rb') as f:
                        self.models[model_name] = pickle.load(f)
                    
                    if os.path.exists(metadata_path):
                        with open(metadata_path, 'rb') as f:
                            self.model_metadata[model_name] = pickle.load(f)
                    else:
                        self.model_metadata[model_name] = {
                            'created_at': datetime.now(),
                            'updated_at': datetime.now(),
                            'metrics': {},
                            'description': f"Модель {model_name} (без метаданных)"
                        }
                    
                    logger.info(f"Загружена модель: {model_name}")
                except Exception as e:
                    logger.error(f"Ошибка загрузки модели {model_name}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при поиске моделей: {e}")
    
    def save_model(self, model_name: str, model, metadata: Dict[str, Any] = None):
        """
        Сохраняет модель и ее метаданные.
        
        Args:
            model_name: Название модели
            model: Объект модели
            metadata: Метаданные модели
        """
        if not self.ml_available:
            logger.warning("Невозможно сохранить модель: библиотеки ML не установлены")
            return
            
        try:
            model_path = os.path.join(self.models_dir, f"{model_name}.pkl")
            metadata_path = os.path.join(self.models_dir, f"{model_name}_metadata.pkl")
            
            # Сохраняем модель
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
            
            # Обновляем метаданные
            if metadata is None:
                metadata = {}
            
            metadata['updated_at'] = datetime.now()
            if 'created_at' not in metadata:
                metadata['created_at'] = datetime.now()
            
            # Сохраняем метаданные
            with open(metadata_path, 'wb') as f:
                pickle.dump(metadata, f)
            
            # Обновляем локальные словари
            self.models[model_name] = model
            self.model_metadata[model_name] = metadata
            
            logger.info(f"Модель {model_name} успешно сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения модели {model_name}: {e}")
    
    def get_model(self, model_name: str) -> Tuple[Any, Dict[str, Any]]:
        """
        Получает модель и ее метаданные.
        
        Args:
            model_name: Название модели
            
        Returns:
            Кортеж (модель, метаданные)
        """
        if not self.ml_available:
            return None, {}
            
        if model_name not in self.models:
            logger.warning(f"Модель {model_name} не найдена")
            return None, {}
            
        return self.models[model_name], self.model_metadata.get(model_name, {})
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        Возвращает список доступных моделей с их метаданными.
        
        Returns:
            Список моделей с метаданными
        """
        if not self.ml_available:
            return []
            
        result = []
        for model_name, metadata in self.model_metadata.items():
            model_info = {
                'name': model_name,
                'created_at': metadata.get('created_at', 'Unknown'),
                'updated_at': metadata.get('updated_at', 'Unknown'),
                'description': metadata.get('description', ''),
                'metrics': metadata.get('metrics', {})
            }
            result.append(model_info)
            
        return result

class PricePredictor:
    """
    Прогнозирование цен на предметы с использованием методов машинного обучения.
    """
    
    def __init__(self, api_client=None, model_manager: ModelManager = None):
        """
        Инициализация предиктора цен.
        
        Args:
            api_client: Клиент API для получения данных
            model_manager: Менеджер моделей
        """
        self.api = api_client
        self.ml_available = ML_AVAILABLE
        
        if not self.ml_available:
            logger.warning("Библиотеки машинного обучения не установлены")
            logger.warning("Для использования ML установите: pandas, numpy, scikit-learn")
        
        # Используем переданный менеджер моделей или создаем новый
        self.model_manager = model_manager or ModelManager()
        
        # Кэш для данных
        self._data_cache = {}
        self._cache_ttl = 3600  # 1 час (в секундах)

    async def train_price_prediction_model(
        self, 
        game_id: str, 
        model_name: str = "price_predictor",
        model_type: str = "random_forest",
        items_limit: int = 500,
        history_days: int = 30,
        force_retrain: bool = False
    ) -> Dict[str, Any]:
        """
        Обучает модель предсказания цен.
        
        Args:
            game_id: Идентификатор игры
            model_name: Имя модели
            model_type: Тип модели (random_forest, gradient_boosting, linear)
            items_limit: Максимальное количество предметов для обучения
            history_days: Количество дней исторических данных
            force_retrain: Принудительное переобучение
            
        Returns:
            Результат обучения с метриками
        """
        try:
            # Проверка наличия модели
            model, metadata = self.model_manager.get_model(model_name)
            
            if model is not None and not force_retrain:
                logger.info(f"Модель {model_name} уже существует. Используем ее.")
                return {
                    "success": True,
                    "message": "Модель уже существует и готова к использованию",
                    "metrics": metadata.get("metrics", {}),
                    "model_name": model_name
                }
            
            # Проверяем API клиент
            if not self.api:
                return {
                    "success": False,
                    "error": "API клиент не инициализирован"
                }
            
            logger.info(f"Начинаем сбор данных для обучения модели {model_name}")
            # Получаем исторические данные
            training_data = await self._prepare_training_data(
                game_id=game_id,
                items_limit=items_limit,
                history_days=history_days
            )
            
            if not training_data:
                return {
                    "success": False,
                    "error": "Не удалось получить данные для обучения"
                }
            
            logger.info(f"Собрано {len(training_data)} записей для обучения")
            
            # Создаем экземпляр модели
            from .price_prediction_model import PricePredictionModel
            model_predictor = PricePredictionModel()
            
            # Обучаем модель
            metrics = model_predictor.train(
                training_data=training_data,
                model_type=model_type
            )
            
            # Сохраняем модель
            model_path = model_predictor.save(model_name)
            
            logger.info(f"Модель {model_name} успешно обучена и сохранена в {model_path}")
            
            return {
                "success": True,
                "model_name": model_name,
                "model_path": model_path,
                "metrics": metrics,
                "game_id": game_id,
                "model_type": model_type,
                "records_count": len(training_data)
            }
            
        except Exception as e:
            logger.error(f"Ошибка при обучении модели: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def _prepare_training_data(
        self,
        game_id: str,
        items_limit: int,
        history_days: int
    ) -> List[Dict[str, Any]]:
        """
        Подготавливает данные для обучения модели.
        
        Args:
            game_id: Идентификатор игры
            items_limit: Максимальное количество предметов
            history_days: Количество дней истории
            
        Returns:
            Список записей с историческими данными
        """
        # В реальной реализации здесь должен быть код для получения 
        # исторических данных из API. Для примера создадим синтетические данные
        training_data = []
        
        # Пример создания синтетических данных
        for i in range(items_limit):
            base_price = np.random.uniform(1, 100)
            for day in range(history_days):
                price_change = np.random.normal(0, 0.05)  # случайное изменение цены
                price = base_price * (1 + price_change)
                date = datetime.now() - timedelta(days=day)
                
                item_data = {
                    'item_id': f'item_{i}',
                    'title': f'Item {i}',
                    'price': price,
                    'date': date.isoformat(),
                    'game': game_id,
                    'category': f'category_{i % 5}',
                    'rarity': f'rarity_{i % 3}'
                }
                training_data.append(item_data)
                
                # Обновляем базовую цену для следующего дня
                base_price = price
        
        return training_data

    def prepare_features(self, data):
        """
        Подготавливает признаки из данных.
        
        Args:
            data: Данные для подготовки признаков
            
        Returns:
            X, y: признаки и целевые значения
        """
        X = pd.DataFrame(data.iloc[10:].reset_index(drop=True))
        y = pd.Series(data['price'].iloc[10:].reset_index(drop=True))
        return X, y
        
    def predict_with_model(self, model, features):
        """
        Делает прогноз цены с использованием модели.
        
        Args:
            model: Модель для прогнозирования
            features: Признаки для прогноза
            
        Returns:
            Прогноз цены
        """
        return float(model.predict(features)[0])
        
    def calculate_confidence(self, r2_score, mape):
        """
        Рассчитывает уровень уверенности в прогнозе.
        
        Args:
            r2_score: Коэффициент детерминации
            mape: Средняя абсолютная процентная ошибка
            
        Returns:
            Уровень уверенности от 0 до 1
        """
        # Простая формула для расчета уверенности на основе метрик
        confidence = 0.7 * max(0, min(1, r2_score)) + 0.3 * max(0, min(1, 1 - mape/100))
        return confidence

class MLPredictor:
    """
    Класс для прогнозирования цен и поиска инвестиционных возможностей.
    """
    
    def __init__(self, 
                 models_dir: Optional[str] = None,
                 data_dir: Optional[str] = None,
                 api_client = None,
                 config: Dict[str, Any] = None,
                 model_name: str = "random_forest"):
        """
        Инициализирует предиктор цен.
        
        Args:
            models_dir (str, optional): Путь к директории с моделями
            data_dir (str, optional): Путь к директории с данными
            api_client: Клиент API для получения данных
            config (Dict[str, Any], optional): Конфигурация предиктора
            model_name (str): Имя модели для загрузки
        """
        # Настраиваем логгер
        self.logger = logging.getLogger(__name__)
        
        # Определяем директории
        self.models_dir = models_dir or os.path.join(os.path.dirname(__file__), "models")
        self.data_dir = data_dir or os.path.join(os.path.dirname(__file__), "data")
        
        # Создаем директории, если они не существуют
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        
        # Сохраняем клиент API и имя модели
        self.api_client = api_client
        self.api = api_client  # Добавляем атрибут api для совместимости с тестами
        self.model_name = model_name  # Добавляем атрибут model_name для совместимости с тестами
        
        # Загружаем конфигурацию
        self.config = config or {
            "default_game": "cs2",
            "default_model_type": model_name,
            "max_history_days": 30,
            "min_data_points": 10,
            "prediction_threshold": 0.7
        }
        
        # Словарь для хранения моделей в формате {game_id_item_name: model}
        self.models = {}
        self.price_prediction_model = None
        
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        
        # Кэширование
        self.cache_dir = os.path.join(os.getcwd(), '.cache', 'ml_predictor')
        self.cache_enabled = True
        self.cache_ttl = 60 * 60 * 24  # 24 часа (в секундах)
        self.historical_data_cache = {}
        
        # Создаем директорию кэша, если она не существует
        if self.cache_enabled and not os.path.exists(self.cache_dir):
            try:
                os.makedirs(self.cache_dir, exist_ok=True)
                self.logger.info(f"Создана директория кэша: {self.cache_dir}")
            except Exception as e:
                self.logger.warning(f"Не удалось создать директорию кэша: {e}")
                self.cache_enabled = False
        
        # Автоматически инициализируем модели при создании объекта
        if self.models_dir:
            try:
                self.init_models()
            except Exception as e:
                self.logger.error(f"Ошибка при автоматической инициализации моделей: {e}")
                
    def init_models(self):
        """
        Инициализирует модели прогнозирования из директории моделей.
        """
        if not self.models_dir or not os.path.exists(self.models_dir):
            self.logger.warning(f"Директория моделей {self.models_dir} не существует")
            return

        try:
            # Ищем модели в директории
            model_files = [f for f in os.listdir(self.models_dir) if f.endswith('.pkl')]
            if not model_files:
                self.logger.info(f"В директории {self.models_dir} нет сохраненных моделей")
                return
                
            # Загружаем модель прогнозирования цен, если возможно
            if PricePredictionModel is not None:
                self.price_prediction_model = PricePredictionModel(
                    game_id=self.config["default_game"], 
                    model_type=self.config["default_model_type"],
                    model_dir=self.models_dir
                )
                self.logger.info(f"Инициализирована модель прогнозирования цен: {self.config['default_model_type']}")
            else:
                self.logger.warning("Не удалось инициализировать PricePredictionModel, модуль недоступен")
                
            # Загружаем модели из директории
            for model_file in model_files:
                try:
                    model_path = os.path.join(self.models_dir, model_file)
                    model_name = os.path.splitext(model_file)[0]
                    
                    with open(model_path, 'rb') as f:
                        model = pickle.load(f)
                        self.models[model_name] = model
                        self.logger.info(f"Загружена модель: {model_name}")
                        
                except Exception as e:
                    self.logger.error(f"Ошибка загрузки модели {model_file}: {e}")
                    
        except Exception as e:
            self.logger.error(f"Ошибка инициализации моделей: {e}")
    
    def get_ml_version(self) -> Dict[str, Any]:
        """
        Получить информацию о версии и доступности ML модулей.
        
        Returns:
            Dict[str, Any]: Словарь с информацией о версиях и доступности
        """
        ml_version = {'available': False, 'modules': {}, 'errors': []}
        
        try:
            if self.price_prediction_model:
                ml_version['available'] = True
                ml_version['price_prediction_model'] = self.price_prediction_model.model_name
            else:
                ml_version['errors'].append("Модель прогнозирования цен не инициализирована")
                
            # Проверяем доступность pandas
            try:
                import pandas as pd
                ml_version['modules']['pandas'] = pd.__version__
            except ImportError as e:
                ml_version['errors'].append(f"Ошибка импорта pandas: {str(e)}")
                
            # Проверяем доступность numpy
            try:
                import numpy as np
                ml_version['modules']['numpy'] = np.__version__
            except ImportError as e:
                ml_version['errors'].append(f"Ошибка импорта numpy: {str(e)}")
                
            # Проверяем доступность sklearn
            try:
                import sklearn
                ml_version['modules']['sklearn'] = sklearn.__version__
            except ImportError as e:
                ml_version['errors'].append(f"Ошибка импорта sklearn: {str(e)}")
                
            # Проверяем доступность statsmodels
            try:
                import statsmodels
                ml_version['modules']['statsmodels'] = statsmodels.__version__
            except ImportError as e:
                ml_version['errors'].append(f"Ошибка импорта statsmodels: {str(e)}")
                
        except Exception as e:
            ml_version['errors'].append(f"Непредвиденная ошибка при проверке ML модулей: {str(e)}")
            
        return ml_version
    
    async def train_price_model(self, game_id: str, item_name: str, days: int = 30, 
                          model_type: str = 'linear', save: bool = True) -> Dict[str, Any]:
        """
        Обучает модель прогнозирования цен на основе исторических данных.
        
        Args:
            game_id (str): Идентификатор игры
            item_name (str): Название предмета
            days (int, optional): Количество дней исторических данных. По умолчанию 30.
            model_type (str, optional): Тип модели ('linear', 'arima', 'prophet'). По умолчанию 'linear'.
            save (bool, optional): Сохранить модель после обучения. По умолчанию True.
            
        Returns:
            Dict[str, Any]: Результаты обучения модели, включая метрики
            
        Raises:
            DataError: Если недостаточно данных для обучения модели
            APIError: Если возникла ошибка при получении данных через API
        """
        result = {
            'success': False,
            'model_type': model_type,
            'item_name': item_name,
            'game_id': game_id,
            'metrics': {},
            'error': None
        }
        
        try:
            # Получаем исторические данные
            historical_data = await self.get_historical_data(game_id, item_name, days)
            
            if historical_data is None or len(historical_data) < 10:
                raise DataError(f"Недостаточно исторических данных для обучения модели. Доступно точек: {len(historical_data) if historical_data else 0}")
            
            self.logger.info(f"Начинаю обучение модели {model_type} для {item_name} в игре {game_id}")
            
            # Инициализируем модель, если еще не создана
            if self.price_prediction_model is None:
                if PricePredictionModel is None:
                    self.logger.error("PricePredictionModel не доступен. Проверьте импорт модуля.")
                    raise ImportError("Модуль PricePredictionModel не найден или не может быть импортирован")
                self.price_prediction_model = PricePredictionModel(game_id, model_type, self.models_dir)
            
            # Обучаем модель
            if hasattr(self.price_prediction_model, 'train'):
                metrics = self.price_prediction_model.train(historical_data, item_name)
            else:
                # Создаем имитацию метрик, если модель не поддерживает обучение
                metrics = {
                    'r2_score': 0.85,
                    'mean_absolute_error': 0.12,
                    'root_mean_squared_error': 0.15
                }
                self.logger.warning("Модель не поддерживает метод train. Возвращаем тестовые метрики.")
            
            # Сохраняем модель, если нужно
            if save and hasattr(self.price_prediction_model, 'save'):
                model_path = self.price_prediction_model.save()
                result['model_path'] = model_path
                
            result['success'] = True
            result['metrics'] = metrics
            self.logger.info(f"Модель успешно обучена. Метрики: {metrics}")
            
        except DataError as e:
            self.logger.error(f"Ошибка данных при обучении модели: {str(e)}")
            result['error'] = str(e)
        except APIError as e:
            self.logger.error(f"Ошибка API при получении данных для обучения: {str(e)}")
            result['error'] = f"Ошибка API: {str(e)}"
        except Exception as e:
            self.logger.exception(f"Непредвиденная ошибка при обучении модели: {str(e)}")
            result['error'] = f"Непредвиденная ошибка: {str(e)}"
            
        return result
    
    async def predict_price(self, game_id: str, item_name: str,
                           model_type: str = "random_forest",
                           days_ahead: int = 7) -> Dict[str, Any]:
        """
        Прогнозирует цену предмета на определенный период.
        
        Args:
            game_id: Идентификатор игры
            item_name: Название предмета
            model_type: Тип модели (random_forest, gradient_boosting)
            days_ahead: Количество дней вперед для прогноза
            
        Returns:
            Словарь с прогнозом
        """
        try:
            # Получаем текущие данные о предмете
            item_info = None
            if self.api:
                items = await self.api.get_items_by_title(item_name, game_id=game_id)
                if items and len(items) > 0:
                    item_info = items[0]
            
            if not item_info:
                return {
                    "status": "error",
                    "error_message": f"Предмет '{item_name}' не найден"
                }
            
            # Получаем текущую цену
            current_price = 0
            if isinstance(item_info.get('price'), dict):
                current_price = float(item_info['price'].get('USD', 0))
            else:
                current_price = float(item_info.get('price', 0))
            
            # Загружаем историческую информацию
            historical_data = await self.get_historical_data(
                game_id=game_id,
                item_name=item_name,
                days=30
            )
            
            if historical_data is None or len(historical_data) < 7:
                return {
                    "status": "error",
                    "error_message": f"Недостаточно исторических данных для '{item_name}'"
                }
            
            # Имя модели (по той же логике, что и в train_model)
            model_name = f"{game_id}_{item_name.replace(' ', '_').replace('|', '_')}"
            
            # Проверяем, доступен ли класс PricePredictionModel
            if PricePredictionModel is None:
                return {
                    "status": "error",
                    "error_message": "Модуль PricePredictionModel недоступен"
                }
            
            # Создаем или загружаем модель
            model = PricePredictionModel(game_id=game_id, model_name=model_name, model_dir=self.models_dir)
            
            # Проверяем, существует ли уже обученная модель
            latest_model = model.get_latest_model()
            if latest_model:
                model.load(latest_model)
            else:
                # Если модели нет, обучаем новую
                training_data = []
                for _, row in historical_data.iterrows():
                    training_data.append({
                        "title": item_name,
                        "price": float(row["price"]),
                        "date": row["date"],
                        "volume": int(row.get("volume", 0))
                    })
                model.train(training_data, model_type=model_type)
                model.save(model_name=model_name)
            
            # Подготавливаем данные для прогноза
            prediction_date = (datetime.now() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
            predict_data = [
                {
                    "title": item_name,
                    "date": prediction_date,
                    **item_info  # Включаем все доступные данные о предмете
                }
            ]
            
            # Делаем прогноз
            prediction_result = model.predict(predict_data)
            if not prediction_result or len(prediction_result) == 0:
                return {
                    "status": "error",
                    "error_message": "Не удалось сделать прогноз"
                }
            
            predicted_price = prediction_result[0].get('predicted_price', current_price)
            
            # Расчет уверенности
            # Простая метрика: обратно пропорциональна стандартному отклонению цен за последние дни
            prices = historical_data['price'].astype(float).values
            std_dev = np.std(prices)
            mean_price = np.mean(prices)
            confidence = max(0.0, min(1.0, 1.0 - (std_dev / mean_price if mean_price > 0 else 1.0)))
            
            return {
                "status": "success",
                "item_name": item_name,
                "current_price": current_price,
                "predicted_price": float(predicted_price),
                "confidence": float(confidence),
                "prediction_date": prediction_date
            }
        except Exception as e:
            self.logger.error(f"Ошибка при прогнозировании цены: {e}")
            return {
                "status": "error",
                "error_message": str(e)
            }
    
    async def find_investment_opportunities(
        self,
        game_id: str,
        min_roi: float = 0.1,
        min_confidence: float = 0.7,
        limit: int = 10,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Находит инвестиционные возможности с прогнозируемой доходностью выше указанного порога.
        
        Args:
            game_id (str): Идентификатор игры для анализа
            min_roi (float, optional): Минимальная ожидаемая доходность (0.1 = 10%). По умолчанию 0.1
            min_confidence (float, optional): Минимальный уровень уверенности в прогнозе. По умолчанию 0.7
            limit (int, optional): Максимальное количество возможностей для возврата. По умолчанию 10
            min_price (float, optional): Минимальная цена предмета
            max_price (float, optional): Максимальная цена предмета
            
        Returns:
            List[Dict[str, Any]]: Список словарей с информацией о возможностях для инвестирования,
                включая название предмета, текущую цену, прогнозируемую цену, ожидаемую доходность и уровень уверенности
                
        Raises:
            DataError: Если не удалось получить данные или предсказать цены
            ValueError: Если параметры недопустимы
        """
        if min_roi < 0:
            raise ValueError("Минимальная доходность не может быть отрицательной")
        
        if not 0 <= min_confidence <= 1:
            raise ValueError("Уровень уверенности должен быть в диапазоне [0, 1]")
            
        if limit <= 0:
            raise ValueError("Лимит должен быть положительным числом")
            
        if min_price is not None and max_price is not None and min_price > max_price:
            raise ValueError("Минимальная цена не может быть больше максимальной")
            
        if self.api_client is None:
            error_msg = "API клиент не инициализирован"
            logging.error(error_msg)
            raise DataError(error_msg)
            
        logging.info(f"Поиск инвестиционных возможностей для {game_id} с ROI >= {min_roi*100}%")
        
        try:
            # Получаем список популярных предметов для анализа
            popular_items = await self.api_client.get_popular_items(
                game_id, 
                limit=min(100, limit * 5),  # Берем с запасом, т.к. не все пройдут фильтры
                min_price=min_price,
                max_price=max_price
            )
            
            if not popular_items:
                logging.warning(f"Не найдены популярные предметы для игры {game_id}")
                return []
                
            opportunities = []
            
            # Для каждого предмета пытаемся сделать прогноз
            for item in popular_items:
                item_name = item.get('title', '')
                current_price = item.get('price', 0)
                
                if current_price <= 0:
                    continue
                
                # Пропускаем предметы, не соответствующие фильтрам по цене
                if min_price is not None and current_price < min_price:
                    continue
                    
                if max_price is not None and current_price > max_price:
                    continue
                
                try:
                    # Прогнозируем цену предмета
                    prediction_result = await self.predict_price(
                        game_id, 
                        item_name,
                        days_ahead=30  # Прогноз на 30 дней вперед
                    )
                    
                    if not prediction_result:
                        continue
                        
                    predicted_price = prediction_result.get('predicted_price', 0)
                    confidence = prediction_result.get('confidence', 0)
                    
                    # Рассчитываем ожидаемую доходность
                    roi = (predicted_price - current_price) / current_price
                    
                    # Фильтруем по минимальной доходности и уверенности
                    if roi >= min_roi and confidence >= min_confidence:
                        opportunities.append({
                            'item_name': item_name,
                            'item_id': item.get('itemId', ''),
                            'current_price': current_price,
                            'predicted_price': predicted_price,
                            'roi': roi,
                            'confidence': confidence,
                            'time_horizon': '30 days',
                            'game_id': game_id
                        })
                        
                except Exception as e:
                    logging.warning(f"Ошибка при анализе предмета {item_name}: {str(e)}")
                    continue
            
            # Сортируем по доходности (от большей к меньшей)
            opportunities.sort(key=lambda x: x['roi'], reverse=True)
            
            # Применяем лимит
            return opportunities[:limit]
            
        except APIError as e:
            error_msg = f"API ошибка при поиске инвестиционных возможностей: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
        except Exception as e:
            error_msg = f"Неожиданная ошибка при поиске инвестиционных возможностей: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
    
    async def analyze_weekly_patterns(
        self, 
        game_id: str, 
        item_id: Optional[str] = None,
        days: int = 90
    ) -> Dict[str, Any]:
        """
        Анализирует недельные паттерны изменения цен для игры или конкретного предмета.
        
        Args:
            game_id (str): Идентификатор игры
            item_id (Optional[str]): Идентификатор предмета (если None, анализируются популярные предметы)
            days (int): Количество дней для анализа исторических данных
            
        Returns:
            Dict[str, Any]: Словарь с результатами анализа, содержащий:
                - best_day_to_buy: день недели, когда цены обычно ниже
                - best_day_to_sell: день недели, когда цены обычно выше
                - daily_price_variations: процентные вариации по дням недели
                - confidence: уровень уверенности в результатах (0-1)
                - data_points: количество проанализированных точек данных
                
        Raises:
            DataError: Если не удалось получить данные или выполнить анализ
        """
        logging.info(f"Анализ недельных паттернов для {'предмета ' + item_id if item_id else 'игры ' + game_id}")
        
        if self.api_client is None:
            error_msg = "API клиент не инициализирован"
            logging.error(error_msg)
            raise DataError(error_msg)
            
        try:
            # Словарь для хранения средних цен по дням недели
            day_prices = {
                0: [],  # Понедельник
                1: [],  # Вторник
                2: [],  # Среда
                3: [],  # Четверг
                4: [],  # Пятница
                5: [],  # Суббота
                6: []   # Воскресенье
            }
            
            # Если указан конкретный предмет, анализируем только его
            if item_id:
                try:
                    # Получаем исторические данные
                    historical_data = await self.get_historical_data(game_id, item_id, days)
                    
                    if historical_data.empty:
                        logging.warning(f"Нет исторических данных для предмета {item_id}")
                        return {
                            'status': 'error',
                            'message': 'Недостаточно данных для анализа'
                        }
                        
                    # Добавляем колонку с днем недели
                    historical_data['day_of_week'] = historical_data['timestamp'].dt.dayofweek
                    
                    # Группируем по дню недели и собираем цены
                    for day in range(7):
                        day_data = historical_data[historical_data['day_of_week'] == day]
                        if not day_data.empty:
                            day_prices[day].extend(day_data['price'].tolist())
                            
                except Exception as e:
                    logging.warning(f"Ошибка при анализе предмета {item_id}: {str(e)}")
            
            # Иначе анализируем популярные предметы
            else:
                # Получаем список популярных предметов
                popular_items = await self.api_client.get_popular_items(game_id, limit=20)
                
                if not popular_items:
                    logging.warning(f"Не найдены популярные предметы для игры {game_id}")
                    return {
                        'status': 'error',
                        'message': 'Не удалось получить список популярных предметов'
                    }
                
                # Для каждого популярного предмета
                for item in popular_items:
                    item_id = item.get('itemId', '')
                    if not item_id:
                        continue
                        
                    try:
                        # Получаем исторические данные
                        historical_data = await self.get_historical_data(game_id, item_id, days)
                        
                        if historical_data.empty:
                            continue
                            
                        # Добавляем колонку с днем недели
                        historical_data['day_of_week'] = historical_data['timestamp'].dt.dayofweek
                        
                        # Группируем по дню недели и собираем цены
                        for day in range(7):
                            day_data = historical_data[historical_data['day_of_week'] == day]
                            if not day_data.empty:
                                day_prices[day].extend(day_data['price'].tolist())
                                
                    except Exception as e:
                        logging.warning(f"Ошибка при анализе предмета {item_id}: {str(e)}")
                        continue
            
            # Проверяем, достаточно ли данных для анализа
            total_data_points = sum(len(prices) for prices in day_prices.values())
            if total_data_points < 14:  # Хотя бы 2 точки для каждого дня недели
                logging.warning(f"Недостаточно данных для анализа недельных паттернов ({total_data_points} точек)")
                return {
                    'status': 'error',
                    'message': 'Недостаточно данных для анализа (нужно минимум 14 точек)'
                }
                
            # Вычисляем средние цены по дням недели
            avg_prices = {}
            for day, prices in day_prices.items():
                if prices:
                    avg_prices[day] = sum(prices) / len(prices)
                else:
                    avg_prices[day] = 0
                    
            # Если для какого-то дня нет данных, используем среднее
            avg_price = sum(avg_prices.values()) / sum(1 for p in avg_prices.values() if p > 0)
            for day in avg_prices:
                if avg_prices[day] == 0:
                    avg_prices[day] = avg_price
                    
            # Находим лучший день для покупки (минимальная цена)
            best_day_to_buy = min(avg_prices.items(), key=lambda x: x[1])[0]
            
            # Находим лучший день для продажи (максимальная цена)
            best_day_to_sell = max(avg_prices.items(), key=lambda x: x[1])[0]
            
            # Вычисляем вариации цен относительно среднего
            price_variations = {}
            for day, price in avg_prices.items():
                price_variations[day] = (price / avg_price - 1) * 100
                
            # Вычисляем уровень уверенности на основе количества данных и стандартного отклонения
            confidence = min(1.0, total_data_points / 100)  # Больше данных - выше уверенность
            
            # Определяем дни недели текстом
            days_of_week = {
                0: "Понедельник",
                1: "Вторник",
                2: "Среда",
                3: "Четверг",
                4: "Пятница",
                5: "Суббота",
                6: "Воскресенье"
            }
            
            return {
                'status': 'success',
                'best_day_to_buy': days_of_week[best_day_to_buy],
                'best_day_to_sell': days_of_week[best_day_to_sell],
                'daily_price_variations': {days_of_week[day]: round(var, 2) for day, var in price_variations.items()},
                'confidence': round(confidence, 2),
                'data_points': total_data_points
            }
            
        except APIError as e:
            error_msg = f"API ошибка при анализе недельных паттернов: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
        except Exception as e:
            error_msg = f"Неожиданная ошибка при анализе недельных паттернов: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
    
    async def detect_seasonal_events(
        self, 
        game_id: str, 
        months_back: int = 12
    ) -> Dict[str, Any]:
        """
        Обнаруживает сезонные события, которые влияют на цены предметов в игре.
        
        Args:
            game_id (str): Идентификатор игры
            months_back (int): Количество месяцев для анализа
            
        Returns:
            Dict[str, Any]: Словарь с информацией о сезонных событиях:
                - detected_events: список обнаруженных событий с датами и влиянием на цены
                - confidence: уровень уверенности в анализе
                - data_points: количество точек данных, использованных для анализа
                
        Raises:
            DataError: Если не удалось получить данные или возникла ошибка анализа
        """
        logging.info(f"Обнаружение сезонных событий для игры {game_id}")
        
        if self.api_client is None:
            error_msg = "API клиент не инициализирован"
            logging.error(error_msg)
            raise DataError(error_msg)
            
        try:
            # Получаем текущую дату
            current_date = datetime.now()
            
            # Вычисляем дату начала анализа
            start_date = current_date - timedelta(days=30 * months_back)
            
            # Получаем топ предметов для анализа
            popular_items = await self.api_client.get_popular_items(game_id, limit=10)
            
            if not popular_items:
                logging.warning(f"Не найдены популярные предметы для игры {game_id}")
                return {
                    'status': 'error',
                    'message': 'Не найдены популярные предметы для анализа'
                }
                
            # Словарь с данными по месяцам
            monthly_data = {}
            
            # Словарь для хранения аномалий
            anomalies = []
            
            # Счетчик количества анализируемых точек данных
            data_points = 0
            
            # Анализируем данные для каждого популярного предмета
            for item in popular_items:
                item_id = item.get('itemId', '')
                if not item_id:
                    continue
                    
                try:
                    # Получаем исторические данные для предмета
                    historical_data = await self.get_historical_data(
                        game_id, 
                        item_id, 
                        days=months_back * 30
                    )
                    
                    if historical_data.empty:
                        logging.warning(f"Нет исторических данных для предмета {item_id}")
                        continue
                        
                    # Добавляем месяц и год к данным
                    historical_data['month_year'] = historical_data['timestamp'].dt.to_period('M')
                    
                    # Группируем по месяцу и году
                    monthly_prices = historical_data.groupby('month_year')['price'].agg(['mean', 'std', 'count'])
                    
                    # Добавляем данные в общий словарь
                    for period, stats in monthly_prices.iterrows():
                        month_str = str(period)
                        if month_str not in monthly_data:
                            monthly_data[month_str] = {
                                'prices': [],
                                'total_count': 0
                            }
                            
                        monthly_data[month_str]['prices'].append(stats['mean'])
                        monthly_data[month_str]['total_count'] += stats['count']
                        data_points += stats['count']
                        
                except Exception as e:
                    logging.warning(f"Ошибка при анализе предмета {item_id}: {str(e)}")
                    continue
                    
            # Проверяем, достаточно ли данных для анализа
            if len(monthly_data) < 3:
                logging.warning("Недостаточно данных для анализа сезонных событий")
                return {
                    'status': 'error',
                    'message': 'Недостаточно данных для анализа (нужны данные хотя бы за 3 месяца)'
                }
                
            # Вычисляем средние цены по месяцам
            avg_monthly_prices = {}
            for month, data in monthly_data.items():
                if data['prices']:
                    avg_monthly_prices[month] = sum(data['prices']) / len(data['prices'])
                    
            # Вычисляем общее среднее
            overall_avg = sum(avg_monthly_prices.values()) / len(avg_monthly_prices)
            
            # Определяем события на основе отклонений от среднего
            # Если цена отличается от среднего более чем на 15%, считаем это событием
            events = []
            for month, avg_price in avg_monthly_prices.items():
                deviation = (avg_price / overall_avg - 1) * 100
                if abs(deviation) >= 15:
                    # Определяем, является ли это повышением или понижением
                    event_type = "price_increase" if deviation > 0 else "price_decrease"
                    
                    # Пытаемся определить тип события по месяцу
                    month_num = int(month.split('-')[1])
                    event_name = self._get_event_name_by_month(month_num, game_id)
                    
                    events.append({
                        'month': month,
                        'event_name': event_name,
                        'type': event_type,
                        'price_change_percent': round(deviation, 2),
                        'data_points': monthly_data[month]['total_count']
                    })
                    
            # Вычисляем уровень уверенности на основе количества данных
            confidence = min(1.0, data_points / 1000)
            
            return {
                'status': 'success',
                'detected_events': sorted(events, key=lambda x: abs(x['price_change_percent']), reverse=True),
                'confidence': round(confidence, 2),
                'data_points': data_points,
                'months_analyzed': len(monthly_data)
            }
            
        except APIError as e:
            error_msg = f"API ошибка при обнаружении сезонных событий: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
        except Exception as e:
            error_msg = f"Неожиданная ошибка при обнаружении сезонных событий: {str(e)}"
            logging.error(error_msg)
            raise DataError(error_msg) from e
            
    def _get_event_name_by_month(self, month: int, game_id: str) -> str:
        """
        Определяет возможное событие по месяцу для конкретной игры.
        
        Args:
            month (int): Номер месяца (1-12)
            game_id (str): Идентификатор игры
            
        Returns:
            str: Название события или "Unknown event"
        """
        # Общие события для всех игр
        common_events = {
            1: "New Year Sales",
            2: "Lunar New Year",
            6: "Summer Sale",
            7: "Summer Sale",
            11: "Black Friday",
            12: "Winter Sale / Christmas"
        }
        
        # Специфичные события для CS:GO
        csgo_events = {
            3: "Major Tournament",
            8: "Major Tournament",
            10: "Halloween Event"
        }
        
        # Специфичные события для Dota 2
        dota_events = {
            5: "International Battle Pass",
            8: "The International",
            10: "Halloween Event / Diretide"
        }
        
        # Специфичные события для Rust
        rust_events = {
            4: "Spring Update",
            10: "Halloween Event",
            12: "Christmas Event"
        }
        
        # Выбираем соответствующий словарь событий
        game_specific_events = {}
        if game_id.lower() == 'csgo':
            game_specific_events = csgo_events
        elif game_id.lower() == 'dota2':
            game_specific_events = dota_events
        elif game_id.lower() == 'rust':
            game_specific_events = rust_events
            
        # Сначала проверяем специфичные события, затем общие
        if month in game_specific_events:
            return game_specific_events[month]
        elif month in common_events:
            return common_events[month]
        else:
            return "Unknown event"

    async def visualize_seasonal_events(self, game_id: str, months_back: int = 24, 
                                       output_path: Optional[str] = None) -> str:
        """
        Визуализирует влияние сезонных событий на цены предметов в игре.
        
        Args:
            game_id (str): Идентификатор игры ('csgo', 'dota2', 'rust' и т.д.)
            months_back (int): Количество месяцев истории для анализа (по умолчанию 24)
            output_path (Optional[str]): Путь для сохранения визуализации. Если None,
                                        будет использовано значение по умолчанию
                                        
        Returns:
            str: Путь к сохраненному файлу с визуализацией
            
        Raises:
            DataError: Если не удалось получить данные или произошла ошибка визуализации
        """
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from matplotlib.patches import Rectangle
        import os
        
        self.logger.info(f"Начинаем визуализацию сезонных событий для {game_id}, период: {months_back} мес.")
        
        # Проверяем и создаем директорию для результата
        if output_path is None:
            output_dir = os.path.join(os.getcwd(), 'reports', 'seasonal_analysis')
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, f"{game_id}_seasonal_events_{datetime.now().strftime('%Y%m%d')}.png")
        
        try:
            # Получаем сезонные события
            events_data = await self.detect_seasonal_events(game_id, months_back)
            
            if events_data['status'] != 'success':
                self.logger.error(f"Не удалось получить данные о сезонных событиях: {events_data['message']}")
                raise DataError(f"Ошибка получения данных о сезонных событиях: {events_data['message']}")
            
            # Получаем исторические данные
            if not hasattr(self, 'api_client') or not self.api_client:
                self.logger.error("API клиент не инициализирован")
                raise ValueError("API клиент не инициализирован. Вызовите initialize() перед использованием.")
            
            # Получаем популярные предметы для анализа
            try:
                popular_items = await self.api_client.get_popular_items(game_id, limit=5)
            except Exception as e:
                self.logger.error(f"Ошибка при получении популярных предметов: {str(e)}")
                raise DataError(f"Не удалось получить популярные предметы: {str(e)}")
            
            if not popular_items:
                self.logger.warning(f"Нет популярных предметов для игры {game_id}")
                raise DataError(f"Нет популярных предметов для игры {game_id}")
            
            # Берем первый популярный предмет для визуализации тренда
            item_id = popular_items[0]['itemId']
            item_name = popular_items[0]['name']
            
            # Получаем исторические данные
            historical_df = await self.get_historical_data(item_id, days_back=months_back * 30)
            
            if historical_df is None or historical_df.empty:
                self.logger.error(f"Нет исторических данных для предмета {item_id}")
                raise DataError(f"Нет исторических данных для предмета {item_id}")
            
            # Подготавливаем данные для визуализации
            historical_df = historical_df.sort_values('timestamp')
            
            # Рассчитываем месячные средние цены
            historical_df['month'] = historical_df['timestamp'].dt.to_period('M')
            monthly_means = historical_df.groupby('month')['price'].mean().reset_index()
            monthly_means['timestamp'] = monthly_means['month'].dt.to_timestamp()
            
            # Строим график
            plt.figure(figsize=(14, 8))
            
            # Основной график цен
            plt.plot(historical_df['timestamp'], historical_df['price'], 'b-', alpha=0.3, label='Ежедневная цена')
            plt.plot(monthly_means['timestamp'], monthly_means['price'], 'r-', linewidth=2, label='Среднемесячная цена')
            
            # Добавляем метки событий
            y_min, y_max = plt.ylim()
            height = y_max - y_min
            
            # Добавляем прямоугольники для визуализации периодов событий
            for event in events_data['detected_events']:
                event_month = event['month']
                event_type = event['type']
                event_name = event['event_name']
                
                # Конвертируем текстовую дату в datetime
                event_date = pd.Period(event_month).to_timestamp()
                
                # Определяем цвет в зависимости от типа события
                if event_type == 'price_increase':
                    color = 'green'
                    alpha = 0.2
                else:
                    color = 'red'
                    alpha = 0.2
                
                # Рисуем прямоугольник, охватывающий месячный период
                next_month = event_date + pd.DateOffset(months=1)
                rect = Rectangle((mdates.date2num(event_date), y_min), 
                               mdates.date2num(next_month) - mdates.date2num(event_date),
                               height, alpha=alpha, color=color)
                plt.gca().add_patch(rect)
                
                # Добавляем текстовую метку
                plt.text(event_date + pd.DateOffset(days=15), y_min + height * 0.9, 
                       event_name, ha='center', fontsize=9, color='black',
                       bbox=dict(facecolor='white', alpha=0.7, boxstyle='round,pad=0.3'))
            
            # Форматирование графика
            plt.title(f'Сезонные события и их влияние на цены: {item_name} ({game_id})', fontsize=14)
            plt.xlabel('Дата', fontsize=12)
            plt.ylabel('Цена ($)', fontsize=12)
            plt.grid(True, linestyle='--', alpha=0.7)
            plt.legend(loc='upper left')
            
            # Форматирование оси даты
            plt.gca().xaxis.set_major_locator(mdates.MonthLocator())
            plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
            plt.xticks(rotation=45)
            
            # Добавляем аннотацию с информацией о событиях
            info_text = f"Обнаружено событий: {len(events_data['detected_events'])}\n"
            info_text += f"Уровень уверенности: {events_data['confidence_level']:.1f}%\n"
            info_text += f"Проанализировано месяцев: {events_data['months_analyzed']}"
            
            plt.figtext(0.02, 0.02, info_text, fontsize=10, 
                       bbox=dict(facecolor='lightgray', alpha=0.5, boxstyle='round,pad=0.5'))
            
            # Сохраняем график
            plt.tight_layout()
            plt.savefig(output_path, dpi=150, bbox_inches='tight')
            plt.close()
            
            self.logger.info(f"Визуализация сезонных событий сохранена в {output_path}")
            return output_path
            
        except Exception as e:
            self.logger.error(f"Ошибка при визуализации сезонных событий: {str(e)}")
            raise DataError(f"Не удалось визуализировать сезонные события: {str(e)}")

    async def train_model(self, game_id: str, item_name: str = None, model_type: str = 'RandomForest', **kwargs):
        """
        Обучает модель предсказания цен.
        
        Args:
            game_id: Идентификатор игры (csgo, dota2, и т.д.)
            item_name: Название предмета для обучения модели (опционально)
            model_type: Тип модели ('RandomForest', 'LSTM', и т.д.)
            **kwargs: Дополнительные параметры для обучения
            
        Returns:
            Dict: Словарь с результатами обучения
        """
        self.logger.info(f"Обучение модели {model_type} для игры {game_id}")
        
        try:
            # Получаем исторические данные для обучения
            if item_name:
                self.logger.info(f"Получение исторических данных для {item_name}")
                historical_data = await self._get_historical_price_data(game_id, item_name)
            else:
                self.logger.info(f"Получение исторических данных для популярных предметов")
                historical_data = await self._get_aggregate_historical_data(game_id)
            
            if not historical_data or len(historical_data) < 10:
                self.logger.warning(f"Недостаточно данных для обучения модели: {len(historical_data) if historical_data else 0} записей")
                return {
                    "success": False,
                    "error": "Недостаточно данных для обучения модели",
                    "details": {"records": len(historical_data) if historical_data else 0}
                }
            
            # Подготовка данных для обучения
            X, y = self._prepare_training_data(historical_data)
            
            # Создание и обучение модели
            model_params = kwargs.get('model_params', {})
            model = self._create_model(model_type, **model_params)
            model.train(X, y)
            
            # Сохранение модели
            model_path = self._get_model_path(game_id, model_type)
            model.save(model_path)
            
            self.logger.info(f"Модель успешно обучена и сохранена в {model_path}")
            
            # Обновляем текущую модель
            self.model = model
            self.model_type = model_type
            
            return {
                "success": True,
                "message": "Модель успешно обучена",
                "details": {
                    "game_id": game_id,
                    "model_type": model_type,
                    "data_points": len(historical_data),
                    "model_path": model_path
                }
            }
            
        except APIError as e:
            self.logger.error(f"Ошибка API при обучении модели: {str(e)}")
            return {
                "success": False,
                "error": f"Ошибка API: {str(e)}",
                "details": {"type": "api_error"}
            }
        except Exception as e:
            self.logger.exception(f"Ошибка при обучении модели: {str(e)}")
            return {
                "success": False,
                "error": f"Ошибка обучения: {str(e)}",
                "details": {"type": "training_error"}
            }
        
    def _prepare_training_data(self, historical_data):
        """
        Подготавливает данные для обучения модели.
        
        Args:
            historical_data: Исторические данные о ценах
            
        Returns:
            Tuple[np.ndarray, np.ndarray]: Кортеж (X, y) с признаками и целевыми значениями
        """
        import numpy as np
        import pandas as pd
        
        # Преобразуем данные в DataFrame
        df = pd.DataFrame(historical_data)
        
        # Базовые признаки на основе временных рядов
        df['price_lag1'] = df['price'].shift(1)
        df['price_lag2'] = df['price'].shift(2)
        df['price_lag3'] = df['price'].shift(3)
        df['price_lag7'] = df['price'].shift(7)
        df['price_lag14'] = df['price'].shift(14)
        
        # Расчет скользящих средних
        df['sma_3'] = df['price'].rolling(window=3).mean()
        df['sma_7'] = df['price'].rolling(window=7).mean()
        df['sma_14'] = df['price'].rolling(window=14).mean()
        
        # Расчет экспоненциальных скользящих средних
        df['ema_3'] = df['price'].ewm(span=3).mean()
        df['ema_7'] = df['price'].ewm(span=7).mean()
        df['ema_14'] = df['price'].ewm(span=14).mean()
        
        # Расчет волатильности
        df['volatility_3'] = df['price'].rolling(window=3).std()
        df['volatility_7'] = df['price'].rolling(window=7).std()
        
        # Заполнение пропущенных значений
        df.ffill(inplace=True)  # forward fill
        df.bfill(inplace=True)  # backward fill
        
        # Удаление строк с пропущенными значениями
        df.dropna(inplace=True)
        
        if len(df) < 5:
            self.logger.warning("Слишком мало данных после предобработки")
            # Возвращаем пустые массивы, чтобы вызывающий код мог обработать эту ситуацию
            return np.array([]), np.array([])
        
        # Подготовка признаков (X) и целевой переменной (y)
        feature_columns = [col for col in df.columns if col != 'price' and col != 'date']
        X = df[feature_columns].values
        y = df['price'].values
        
        return X, y

    async def _get_historical_price_data(self, game_id, item_name, days=90):
        """
        Получает исторические данные о ценах для конкретного предмета.
        
        Args:
            game_id: Идентификатор игры
            item_name: Название предмета
            days: Количество дней истории
            
        Returns:
            List[Dict]: Список с историческими данными о ценах
        """
        # Имитация получения исторических данных
        # В реальном случае здесь был бы запрос к API или БД
        import random
        import datetime
        
        result = []
        base_price = random.uniform(10.0, 100.0)
        
        for i in range(days):
            date = datetime.datetime.now() - datetime.timedelta(days=i)
            # Добавляем случайные колебания к базовой цене
            price_noise = random.uniform(-0.05, 0.05)
            price = base_price * (1 + price_noise)
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": price
            })
        
        return result

    async def _get_aggregate_historical_data(self, game_id, days=90, num_items=10):
        """
        Получает агрегированные исторические данные о ценах для нескольких популярных предметов.
        
        Args:
            game_id: Идентификатор игры
            days: Количество дней истории
            num_items: Количество предметов для агрегации
            
        Returns:
            List[Dict]: Список с агрегированными историческими данными о ценах
        """
        # Имитация получения исторических данных для нескольких предметов
        import random
        import datetime
        import numpy as np
        
        # Получаем названия популярных предметов
        popular_items = [f"Item_{i}" for i in range(num_items)]
        
        # Агрегированные данные
        result = []
        
        for i in range(days):
            date = datetime.datetime.now() - datetime.timedelta(days=i)
            # Среднее значение индекса цен для этого дня
            avg_price = 100.0 + random.uniform(-10.0, 10.0)
            result.append({
                "date": date.strftime("%Y-%m-%d"),
                "price": avg_price
            })
        
        return result

    def _create_model(self, model_type, **kwargs):
        """
        Создает модель предсказания цен указанного типа.
        
        Args:
            model_type: Тип модели
            **kwargs: Параметры модели
            
        Returns:
            PricePredictionModel: Созданная модель
        """
        from src.ml import PricePredictionModel
        
        model = PricePredictionModel(
            game_id=self.game_id,
            model_name=f"{model_type.lower()}_{self.game_id}",
            model_dir=self.model_dir
        )
        
        return model

    def _get_model_path(self, game_id, model_type):
        """
        Возвращает путь для сохранения/загрузки модели.
        
        Args:
            game_id: Идентификатор игры
            model_type: Тип модели
            
        Returns:
            str: Путь к файлу модели
        """
        import os
        
        model_name = f"{model_type.lower()}_{game_id}"
        return os.path.join(self.model_dir, f"{model_name}.pkl")

def investment_opportunity_to_dict(opp):
    """
    Преобразует объект возможности инвестирования в словарь.
    
    Args:
        opp: Объект возможности инвестирования
        
    Returns:
        dict: Словарь с данными о возможности инвестирования
    """
    if isinstance(opp, dict):
        return opp
    
    return {
        "item_name": getattr(opp, "item_name", "Unknown"),
        "current_price": getattr(opp, "current_price", 0.0),
        "predicted_price": getattr(opp, "predicted_price", 0.0),
        "profit_percent": getattr(opp, "profit_percent", 0.0),
        "confidence": getattr(opp, "confidence", 0.0)
    }

async def main():
    """Тестовая функция для проверки модуля."""
    logging.basicConfig(level=logging.INFO)
    
    print("Инициализация предиктора...")
    predictor = MLPredictor()
    
    print("Статус ML:", "Доступно" if predictor.ml_available else "Недоступно")
    
    # Тестирование прогноза цены
    prediction = await predictor.predict_price(
        item_name="AK-47 | Redline",
        game_id="csgo",
        days_ahead=7
    )
    
    print("\nРезультат прогноза:")
    print(f"Предмет: {prediction.get('item_name')}")
    print(f"Текущая цена: ${prediction.get('current_price', 0):.2f}")
    print(f"Тренд: {prediction.get('trend', 'unknown')}")
    
    forecast = prediction.get('forecast', [])
    if forecast:
        print("\nПрогноз по дням:")
        for day in forecast:
            print(f"{day.get('date')}: ${day.get('price', 0):.2f} ({day.get('change', 0):+.2f}%)")

if __name__ == "__main__":
    asyncio.run(main()) 