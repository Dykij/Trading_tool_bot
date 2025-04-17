"""
Модуль для торгового бота DMarket.

Этот модуль предоставляет основные функции и классы для
торгового бота на платформе DMarket, который анализирует
рыночные данные и ищет возможности для арбитража.
"""

import logging
import os
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from api_wrapper import DMarketAPI, APIError


class TradingBotConfig:
    """
    Класс для хранения конфигурационных параметров торгового бота.

    Централизует все настройки и константы, используемые в боте,
    позволяя легко менять параметры и поддерживать их в одном месте.

    Attributes:
        API_BASE_URL: Базовый URL для API DMarket.
        HEADERS: Заголовки для HTTP запросов к API.
        MAX_DEPTH: Максимальная глубина поиска при анализе графа цен.
        MIN_PROFIT_FACTOR: Минимальный коэффициент прибыли.
        REQUEST_DELAY: Задержка между запросами (в секундах).
        SUPPORTED_CURRENCIES: Список поддерживаемых валют для торговли.
        MIN_ITEMS: Минимальное количество предметов для анализа.
        MAX_ITEM_PRICE: Максимальная цена предмета для анализа (в USD).
        MIN_ITEM_PRICE: Минимальная цена предмета для анализа (в USD).
        API_KEY_FILE: Путь к файлу с ключом API.
        API_SECRET_FILE: Путь к файлу с секретным ключом API.
        LOG_FILE: Путь к файлу для сохранения логов.
        TIMEOUT: Время ожидания ответа от API (в секундах).
        MAX_RETRIES: Максимальное количество попыток повтора запроса.
        ITEM_CATEGORIES: Список категорий предметов для анализа.
        ITEM_TYPES: Список типов предметов для анализа.
    """

    # API и настройки запросов
    API_BASE_URL = "https://api.dmarket.com"
    HEADERS = {
        "content-type": "application/json",
        "accept": "application/json",
    }
    REQUEST_DELAY = 0.5
    TIMEOUT = 30
    MAX_RETRIES = 3

    # Параметры анализа рынка
    MAX_DEPTH = 3
    MIN_PROFIT_FACTOR = 1.1
    SUPPORTED_CURRENCIES = ['USD', 'EUR', 'BTC', 'ETH', 'USDT', 'USDC', 'DMARKET']
    MIN_ITEMS = 5
    MAX_ITEM_PRICE = 1000
    MIN_ITEM_PRICE = 1

    # Параметры торговли
    TRADING_ENABLED = False  # По умолчанию торговля отключена, только анализ
    MAX_TRADES_PER_HOUR = 5
    MAX_TRADES_PER_DAY = 20
    DAILY_BUDGET = 1000.0
    AUTO_BUY_ENABLED = False
    AUTO_SELL_ENABLED = False
    PRICE_UPDATE_INTERVAL = 300  # секунды
    MARKET_ANALYSIS_INTERVAL = 1800  # секунды (30 минут)
    SIMULATION_MODE = True  # Режим симуляции без реальных сделок

    # Файлы и пути
    CONFIG_DIR = 'config'
    API_KEY_FILE = os.path.join(CONFIG_DIR, 'api_key.txt')
    API_SECRET_FILE = os.path.join(CONFIG_DIR, 'api_secret.txt')
    LOG_FILE = 'logs/trading_bot.log'
    CONFIG_FILE = os.path.join(CONFIG_DIR, 'config.json')
    HISTORY_DIR = 'history'
    TRADES_LOG_FILE = os.path.join(HISTORY_DIR, 'trades.json')
    OPPORTUNITIES_LOG_FILE = os.path.join(HISTORY_DIR, 'opportunities.json')

    # Категории предметов
    ITEM_CATEGORIES = ['cs:go', 'dota_2', 'rust', 'tf2']
    ITEM_TYPES = ['weapon', 'knife', 'gloves', 'container', 'character', 'tool', 'misc']

    # Настройки безопасности
    MAX_LOSS_PER_TRADE_PERCENT = 2.0  # Максимальный убыток по сделке в процентах
    STOP_LOSS_ENABLED = True
    TAKE_PROFIT_PERCENT = 5.0  # Процент прибыли для автоматической продажи
    EMERGENCY_STOP_LOSS_PERCENT = 5.0  # Экстренный стоп-лосс для всего портфеля

    # Параметры интеграции с ML
    ML_PREDICTION_ENABLED = False
    ML_MODEL_PATH = 'models/price_predictor.pkl'
    FEATURES_TO_TRACK = ['volume', 'volatility', 'trend', 'seasonal_factor']

    # Настройки сети и многопоточности
    MAX_CONCURRENT_REQUESTS = 10
    MAX_THREAD_WORKERS = 5
    ASYNC_MODE = True  # использовать асинхронные запросы

    @classmethod
    def load_from_file(cls, file_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Загружает конфигурацию из JSON файла.

        Args:
            file_path: Путь к файлу конфигурации. Если None, используется CONFIG_FILE.

        Returns:
            Dict[str, Any]: Словарь с конфигурационными параметрами.

        Raises:
            FileNotFoundError: Если файл конфигурации не найден.
            json.JSONDecodeError: Если файл содержит некорректный JSON.
        """
        config_path = file_path or cls.CONFIG_FILE

        # Создаем директорию конфигурации, если она не существует
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        if not os.path.exists(config_path):
            # Если файл не существует, вернем значения по умолчанию
            default_config = {attr: getattr(cls, attr) for attr in dir(cls)
                             if not attr.startswith('_') and attr.isupper()}

            # Сохраним значения по умолчанию в файл для будущего использования
            try:
                with open(config_path, 'w', encoding='utf-8') as f:
                    json.dump(default_config, f, indent=4)
                    logger.info(f"Создан файл конфигурации по умолчанию: {config_path}")
            except Exception as e:
                logger.warning(f"Не удалось создать файл конфигурации: {e}")

            return default_config

        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                logger.info(f"Загружена конфигурация из {config_path}")
                return config
        except json.JSONDecodeError as e:
            logger.error(f"Ошибка при чтении конфигурации: {e}")
            # Возвращаем значения по умолчанию в случае ошибки
            return {attr: getattr(cls, attr) for attr in dir(cls)
                   if not attr.startswith('_') and attr.isupper()}
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при загрузке конфигурации: {e}")
            return {attr: getattr(cls, attr) for attr in dir(cls)
                   if not attr.startswith('_') and attr.isupper()}

    @classmethod
    def save_to_file(cls, config: Dict[str, Any], file_path: Optional[str] = None) -> bool:
        """
        Сохраняет конфигурацию в JSON файл.

        Args:
            config: Словарь с конфигурационными параметрами
            file_path: Путь к файлу конфигурации. Если None, используется CONFIG_FILE.

        Returns:
            bool: True, если сохранение прошло успешно, иначе False
        """
        config_path = file_path or cls.CONFIG_FILE

        # Создаем директорию конфигурации, если она не существует
        os.makedirs(os.path.dirname(config_path), exist_ok=True)

        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            logger.info(f"Конфигурация успешно сохранена в {config_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка при сохранении конфигурации: {e}")
            return False


class Logger:
    """
    Логгер для торгового бота с поддержкой различных форматов вывода.

    Этот класс обеспечивает единый интерфейс для логирования, совместимый
    с библиотекой Loguru, но использующий стандартный модуль logging.

    Attributes:
        log_file: Путь к файлу для сохранения логов.
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR).
        logger: Экземпляр logger из стандартной библиотеки logging.
    """

    def __init__(self, log_file: Optional[str] = None,
                 log_level: int = logging.INFO,
                 name: str = "trading_bot"):
        """
        Инициализирует логгер с заданными параметрами.

        Args:
            log_file: Путь к файлу для сохранения логов. Если None, используется TradingBotConfig.LOG_FILE
            log_level: Уровень логирования (по умолчанию INFO).
            name: Имя логгера
        """
        self.log_file = log_file or TradingBotConfig.LOG_FILE
        self.logger = logging.getLogger(name)
        self.logger.setLevel(log_level)

        # Очищаем хендлеры, если они уже были настроены
        if self.logger.handlers:
            self.logger.handlers.clear()

        # Настраиваем форматтер
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Консольный хендлер
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # Файловый хендлер
        try:
            # Создаем директорию для логов, если она не существует
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

            file_handler = logging.FileHandler(self.log_file, encoding='utf-8')
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)
            self.logger.info(f"Логирование в файл {self.log_file} настроено")
        except (IOError, PermissionError) as e:
            self.logger.warning(f"Не удалось создать файл лога {self.log_file}: {e}")

    def debug(self, message: str, *args, **kwargs):
        """
        Логирует сообщение на уровне DEBUG.

        Args:
            message: Сообщение для логирования.
            *args: Дополнительные аргументы.
            **kwargs: Дополнительные именованные аргументы.
        """
        self.logger.debug(message, *args)

    def info(self, message: str, *args, **kwargs):
        """
        Логирует сообщение на уровне INFO.

        Args:
            message: Сообщение для логирования.
            *args: Дополнительные аргументы.
            **kwargs: Дополнительные именованные аргументы.
        """
        self.logger.info(message, *args)

    def warning(self, message: str, *args, **kwargs):
        """
        Логирует сообщение на уровне WARNING.

        Args:
            message: Сообщение для логирования.
            *args: Дополнительные аргументы.
            **kwargs: Дополнительные именованные аргументы.
        """
        self.logger.warning(message, *args)

    def error(self, message: str, *args, **kwargs):
        """
        Логирует сообщение на уровне ERROR.

        Args:
            message: Сообщение для логирования.
            *args: Дополнительные аргументы.
            **kwargs: Дополнительные именованные аргументы.
        """
        self.logger.error(message, *args)

    def critical(self, message: str, *args, **kwargs):
        """
        Логирует сообщение на уровне CRITICAL.

        Args:
            message: Сообщение для логирования.
            *args: Дополнительные аргументы.
            **kwargs: Дополнительные именованные аргументы.
        """
        self.logger.critical(message, *args)

    def setup_file_handler(self, file_path: str, level: int = logging.INFO):
        """
        Добавляет дополнительный файловый обработчик для логирования.

        Args:
            file_path: Путь к файлу для логирования
            level: Уровень логирования для этого обработчика
        """
        try:
            # Создаем директорию для логов, если она не существует
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%М:%S'
            )

            file_handler = logging.FileHandler(file_path, encoding='utf-8')
            file_handler.setFormatter(formatter)
            file_handler.setLevel(level)
            self.logger.addHandler(file_handler)
            self.logger.info(f"Добавлен обработчик для логирования в {file_path}")
            return file_handler
        except Exception as e:
            self.logger.error(f"Не удалось настроить логирование в файл {file_path}: {e}")
            return None

    def add(self, handler):
        """
        Добавляет обработчик логов (для совместимости с Loguru).

        Args:
            handler: Обработчик логов для добавления.
        """
        if isinstance(handler, logging.Handler):
            self.logger.addHandler(handler)


class TradingBot:
    """
    Основной класс торгового бота для работы с DMarket.

    Предоставляет функциональность для анализа рынка, поиска
    арбитражных возможностей и выполнения торговых операций.

    Attributes:
        api: Экземпляр DMarketAPI для взаимодействия с API
        config: Словарь с конфигурационными параметрами
        logger: Логгер для записи событий
    """

    def __init__(self,
                 api_key: Optional[str] = None,
                 api_secret: Optional[str] = None,
                 config_path: Optional[str] = None,
                 simulation_mode: bool = True,
                 log_level: int = logging.INFO):
        """
        Инициализирует торгового бота.

        Args:
            api_key: API ключ DMarket. Если None, будет загружен из файла
            api_secret: API секрет DMarket. Если None, будет загружен из файла
            config_path: Путь к файлу конфигурации. Если None, используется путь по умолчанию
            simulation_mode: Если True, бот будет работать в режиме симуляции без реальных сделок
            log_level: Уровень логирования
        """
        # Инициализация логгера
        self.logger = Logger(log_level=log_level)
        self.logger.info("Инициализация торгового бота DMarket")

        # Загрузка конфигурации
        self.config = TradingBotConfig.load_from_file(config_path)

        # Обновляем режим симуляции из параметров
        if simulation_mode is not None:
            self.config['SIMULATION_MODE'] = simulation_mode

        # Создаем необходимые директории
        self._ensure_directories_exist()

        # Загрузка API ключей
        if api_key is None or api_secret is None:
            # Попытка загрузить ключи из файла конфигурации
            keys = load_api_keys()
            api_key = keys.get('api_key', '')
            api_secret = keys.get('api_secret', '')
            
            if not api_key or not api_secret:
                self.logger.error("API ключи не найдены. Укажите их явно или через файл конфигурации.")
                raise ValueError("API ключи не найдены")
        
        # Инициализация API клиента
        self.api = DMarketAPI(
            api_key=api_key,
            api_secret=api_secret,
            base_url=self.config['API_BASE_URL'],
            timeout=self.config['TIMEOUT']
        )

        # Состояние бота
        self.running = False
        self.last_market_update = datetime.now() - timedelta(days=1)
        self.last_trades_update = datetime.now() - timedelta(days=1)
        self.market_data = {}
        self.opportunities = []
        self.trade_history = []
        self.active_orders = []

        # Статистика работы
        self.stats = {
            'requests_made': 0,
            'errors_count': 0,
            'items_analyzed': 0,
            'opportunities_found': 0,
            'trades_executed': 0,
            'profit_total': 0.0,
            'start_time': datetime.now(),
            'last_opportunity_time': None,
            'last_trade_time': None
        }

        self.logger.info(f"Торговый бот инициализирован. Режим симуляции: {self.config['SIMULATION_MODE']}")

    def _ensure_directories_exist(self):
        """Создает все необходимые директории для работы бота."""
        directories = [
            os.path.dirname(self.config['LOG_FILE']),
            self.config['CONFIG_DIR'],
            self.config['HISTORY_DIR']
        ]

        for directory in directories:
            try:
                os.makedirs(directory, exist_ok=True)
                self.logger.debug(f"Проверена директория: {directory}")
            except Exception as e:
                self.logger.warning(f"Не удалось создать директорию {directory}: {e}")

    def start(self):
        """
        Запускает торгового бота.

        Начинает непрерывный цикл мониторинга рынка и выполнения торговых операций.
        """
        if self.running:
            self.logger.warning("Бот уже запущен")
            return

        self.running = True
        self.logger.info("Торговый бот запущен")

        try:
            # Проверка соединения с API
            if not self.config['SIMULATION_MODE']:
                if not self._check_api_connection():
                    self.logger.error("Ошибка соединения с API. Бот остановлен.")
                    self.running = False
                    return

            # Загружаем историю сделок и возможностей
            self._load_history()

            # Основной цикл работы бота
            while self.running:
                try:
                    # Обновление рыночных данных
                    self._update_market_data()

                    # Анализ рынка и поиск возможностей
                    self._analyze_market()

                    # Исполнение торговых операций
                    if self.config['TRADING_ENABLED'] and not self.config['SIMULATION_MODE']:
                        self._execute_trades()

                    # Обновление статистики и сохранение данных
                    self._update_stats()
                    self._save_history()

                    # Пауза между циклами
                    time.sleep(5)

                except APIError as e:
                    self.logger.error(f"Ошибка API: {e}")
                    self.stats['errors_count'] += 1
                    time.sleep(10)  # Увеличенная пауза при ошибке

                except Exception as e:
                    self.logger.error(f"Ошибка в главном цикле: {e}", exc_info=True)
                    self.stats['errors_count'] += 1
                    time.sleep(10)  # Увеличенная пауза при ошибке

        except KeyboardInterrupt:
            self.logger.info("Получен сигнал остановки. Завершение работы...")

        finally:
            self._save_history()
            self.running = False
            self.logger.info("Торговый бот остановлен")

    def stop(self):
        """Останавливает работу бота."""
        if not self.running:
            self.logger.warning("Бот не запущен")
            return

        self.logger.info("Остановка торгового бота...")
        self.running = False

    def _check_api_connection(self) -> bool:
        """
        Проверяет соединение с API DMarket.

        Returns:
            bool: True если соединение успешно, иначе False
        """
        try:
            self.logger.info("Проверка соединения с API DMarket...")
            result = self.api.ping()

            if result:
                self.logger.info("Соединение с API DMarket успешно установлено")
                return True
            else:
                self.logger.error("Не удалось подключиться к API DMarket")
                return False

        except Exception as e:
            self.logger.error(f"Ошибка при проверке соединения с API: {e}")
            return False

    def _load_history(self):
        """Загружает историю сделок и обнаруженных возможностей."""
        # Загрузка истории сделок
        trades_path = self.config['TRADES_LOG_FILE']
        try:
            if os.path.exists(trades_path):
                with open(trades_path, 'r', encoding='utf-8') as f:
                    self.trade_history = json.load(f)
                self.logger.info(f"Загружена история сделок: {len(self.trade_history)} записей")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке истории сделок: {e}")
            self.trade_history = []

        # Загрузка истории возможностей
        opps_path = self.config['OPPORTUNITIES_LOG_FILE']
        try:
            if os.path.exists(opps_path):
                with open(opps_path, 'r', encoding='utf-8') as f:
                    self.opportunities = json.load(f)
                self.logger.info(f"Загружена история возможностей: {len(self.opportunities)} записей")
        except Exception as e:
            self.logger.error(f"Ошибка при загрузке истории возможностей: {e}")
            self.opportunities = []

    def _save_history(self):
        """Сохраняет историю сделок и обнаруженных возможностей."""
        # Сохранение истории сделок
        trades_path = self.config['TRADES_LOG_FILE']
        try:
            # Создаем директорию, если не существует
            os.makedirs(os.path.dirname(trades_path), exist_ok=True)

            with open(trades_path, 'w', encoding='utf-8') as f:
                json.dump(self.trade_history, f, indent=4)
            self.logger.debug(f"История сделок сохранена: {len(self.trade_history)} записей")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении истории сделок: {e}")

        # Сохранение истории возможностей
        opps_path = self.config['OPPORTUNITIES_LOG_FILE']
        try:
            # Создаем директорию, если не существует
            os.makedirs(os.path.dirname(opps_path), exist_ok=True)

            # Ограничиваем размер истории возможностей
            max_opportunities = 1000
            if len(self.opportunities) > max_opportunities:
                self.opportunities = self.opportunities[-max_opportunities:]

            with open(opps_path, 'w', encoding='utf-8') as f:
                json.dump(self.opportunities, f, indent=4)
            self.logger.debug(f"История возможностей сохранена: {len(self.opportunities)} записей")
        except Exception as e:
            self.logger.error(f"Ошибка при сохранении истории возможностей: {e}")

    def _update_market_data(self):
        """Обновляет данные о рынке."""
        # Проверяем, не слишком ли рано для обновления
        now = datetime.now()
        elapsed = (now - self.last_market_update).total_seconds()
        if elapsed < self.config['PRICE_UPDATE_INTERVAL']:
            self.logger.debug(f"Пропуск обновления рынка (прошло {elapsed:.1f} сек.)")
            return

        self.logger.info("Обновление данных о рынке...")

        try:
            # Получение данных о предметах на рынке
            for category in self.config['ITEM_CATEGORIES'][:1]:  # ограничиваем для отладки
                result = self.api.get_market_items(
                    game_id=category,
                    limit=100,  # ограничиваем для отладки
                    currency="USD"
                )

                if 'objects' in result:
                    items = result.get('objects', [])
                    self.market_data[category] = items
                    self.logger.info(f"Получено {len(items)} предметов для {category}")
                    self.stats['items_analyzed'] += len(items)

                # Соблюдаем задержку между запросами
                time.sleep(self.config['REQUEST_DELAY'])

            self.last_market_update = now

        except Exception as e:
            self.logger.error(f"Ошибка при обновлении данных о рынке: {e}")
            self.stats['errors_count'] += 1

    def _analyze_market(self):
        """Анализирует рыночные данные и ищет арбитражные возможности."""
        if not self.market_data:
            self.logger.warning("Нет данных о рынке для анализа")
            return

        self.logger.info("Анализ рыночных данных...")

        # Очистка старых возможностей
        self.opportunities = [op for op in self.opportunities
                              if (datetime.now() - datetime.fromisoformat(op['detected_at'])).total_seconds() < 3600]

        new_opportunities = []

        for category, items in self.market_data.items():
            # Фильтрация предметов по цене
            filtered_items = [
                item for item in items
                if float(item.get('price', {}).get('USD', 0)) > self.config['MIN_ITEM_PRICE'] and
                float(item.get('price', {}).get('USD', 0)) < self.config['MAX_ITEM_PRICE']
            ]

            # Поиск потенциальных арбитражных возможностей
            for item in filtered_items:
                try:
                    # Здесь будет ваша логика поиска арбитражных возможностей
                    # Например, сравнение цен на разных рынках или в разных валютах

                    # Для демонстрации создаем тестовую возможность
                    if random.random() < 0.05:  # 5% шанс для демонстрации
                        opportunity = {
                            'id': str(random.randint(10000, 99999)),
                            'item_id': item.get('itemId', ''),
                            'name': item.get('title', ''),
                            'category': category,
                            'buy_price': float(item.get('price', {}).get('USD', 0)),
                            'potential_sell_price': float(item.get('price', {}).get('USD', 0)) * (1 + random.uniform(0.05, 0.15)),
                            'profit_percent': random.uniform(5, 15),
                            'detected_at': datetime.now().isoformat(),
                            'risk_level': random.choice(['low', 'medium', 'high']),
                            'executed': False
                        }

                        new_opportunities.append(opportunity)
                        self.logger.info(f"Найдена возможность: {opportunity['name']} с потенциальной прибылью {opportunity['profit_percent']:.2f}%")

                except Exception as e:
                    self.logger.error(f"Ошибка при анализе предмета {item.get('title', '')}: {e}")

        if new_opportunities:
            self.opportunities.extend(new_opportunities)
            self.stats['opportunities_found'] += len(new_opportunities)
            self.stats['last_opportunity_time'] = datetime.now().isoformat()
            self.logger.info(f"Найдено {len(new_opportunities)} новых арбитражных возможностей")
        else:
            self.logger.info("Новых арбитражных возможностей не найдено")

    def _execute_trades(self):
        """Выполняет торговые операции на основе найденных возможностей."""
        if not self.config['TRADING_ENABLED'] or self.config['SIMULATION_MODE']:
            return

        self.logger.info("Проверка возможностей для торговли...")

        # Фильтрация возможностей для торговли
        tradeable_opportunities = [
            op for op in self.opportunities
            if not op['executed']
            and op['profit_percent'] > self.config['MIN_PROFIT_FACTOR']
            and op['risk_level'] != 'high'
        ]

        if not tradeable_opportunities:
            self.logger.info("Нет подходящих возможностей для торговли")
            return

        # Проверка лимитов торговли
        now = datetime.now()

        # Подсчет сделок за последний час и день
        trades_last_hour = sum(1 for trade in self.trade_history
                              if (now - datetime.fromisoformat(trade['timestamp'])).total_seconds() < 3600)

        trades_last_day = sum(1 for trade in self.trade_history
                             if (now - datetime.fromisoformat(trade['timestamp'])).total_seconds() < 86400)

        if trades_last_hour >= self.config['MAX_TRADES_PER_HOUR']:
            self.logger.warning(f"Достигнут часовой лимит сделок ({self.config['MAX_TRADES_PER_HOUR']}). Ожидание...")
            return

        if trades_last_day >= self.config['MAX_TRADES_PER_DAY']:
            self.logger.warning(f"Достигнут дневной лимит сделок ({self.config['MAX_TRADES_PER_DAY']}). Ожидание...")
            return

        # Выбор наиболее прибыльной возможности для торговли
        best_opportunity = max(tradeable_opportunities, key=lambda x: x['profit_percent'])

        try:
            self.logger.info(f"Выполнение сделки для {best_opportunity['name']}...")

            # Здесь будет ваш код для выполнения реальной сделки
            # Например, вызов API для покупки предмета

            # Для демонстрации имитируем успешную сделку
            trade = {
                'id': str(random.randint(10000, 99999)),
                'opportunity_id': best_opportunity['id'],
                'item_id': best_opportunity['item_id'],
                'name': best_opportunity['name'],
                'buy_price': best_opportunity['buy_price'],
                'timestamp': now.isoformat(),
                'status': 'completed',
                'profit': best_opportunity['potential_sell_price'] - best_opportunity['buy_price']
            }

            # Обновляем историю сделок и статус возможности
            self.trade_history.append(trade)
            for op in self.opportunities:
                if op['id'] == best_opportunity['id']:
                    op['executed'] = True

            self.stats['trades_executed'] += 1
            self.stats['profit_total'] += trade['profit']
            self.stats['last_trade_time'] = now.isoformat()

            self.logger.info(f"Сделка выполнена: {trade['name']} за ${trade['buy_price']:.2f}")

        except Exception as e:
            self.logger.error(f"Ошибка при выполнении сделки: {e}")
            self.stats['errors_count'] += 1

    def _update_stats(self):
        """Обновляет статистику работы бота."""
        # Обновление времени работы
        uptime = (datetime.now() - self.stats['start_time']).total_seconds()
        hours, remainder = divmod(uptime, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.stats['uptime'] = f"{int(hours):02}:{int(minutes):02}:{int(seconds):02}"

        # Обновление статистики прибыли и эффективности
        total_trades = self.stats['trades_executed']
        if total_trades > 0:
            self.stats['avg_profit_per_trade'] = self.stats['profit_total'] / total_trades
        else:
            self.stats['avg_profit_per_trade'] = 0

        # Вывод статистики в лог периодически
        if random.random() < 0.05:  # ~5% шанс для периодического вывода
            self.logger.info(f"Статистика: Проанализировано {self.stats['items_analyzed']} "
                           f"предметов, найдено {self.stats['opportunities_found']} возможностей, "
                           f"выполнено {self.stats['trades_executed']} сделок, "
                           f"общая прибыль: ${self.stats['profit_total']:.2f}")

    async def run_async(self):
        """
        Асинхронная версия метода запуска бота.

        Использует асинхронные возможности API для более эффективной работы.
        """
        if self.running:
            self.logger.warning("Бот уже запущен")
            return

        self.running = True
        self.logger.info("Торговый бот запущен в асинхронном режиме")

        try:
            # Проверка соединения с API
            if not self.config['SIMULATION_MODE']:
                if not self._check_api_connection():
                    self.logger.error("Ошибка соединения с API. Бот остановлен.")
                    self.running = False
                    return

            # Загружаем историю сделок и возможностей
            self._load_history()

            # Основной цикл работы бота
            while self.running:
                try:
                    # Обновление рыночных данных асинхронно
                    await self._update_market_data_async()

                    # Анализ рынка и поиск возможностей
                    self._analyze_market()

                    # Исполнение торговых операций
                    if self.config['TRADING_ENABLED'] and not self.config['SIMULATION_MODE']:
                        await self._execute_trades_async()

                    # Обновление статистики и сохранение данных
                    self._update_stats()
                    self._save_history()

                    # Пауза между циклами
                    await asyncio.sleep(5)

                except APIError as e:
                    self.logger.error(f"Ошибка API: {e}")
                    self.stats['errors_count'] += 1
                    await asyncio.sleep(10)  # Увеличенная пауза при ошибке

                except Exception as e:
                    self.logger.error(f"Ошибка в главном цикле: {e}", exc_info=True)
                    self.stats['errors_count'] += 1
                    await asyncio.sleep(10)  # Увеличенная пауза при ошибке

        except asyncio.CancelledError:
            self.logger.info("Получен сигнал остановки. Завершение работы...")

        finally:
            self._save_history()
            self.running = False
            self.logger.info("Торговый бот остановлен")

    async def _update_market_data_async(self):
        """Асинхронно обновляет данные о рынке."""
        # Проверяем, не слишком ли рано для обновления
        now = datetime.now()
        elapsed = (now - self.last_market_update).total_seconds()
        if elapsed < self.config['PRICE_UPDATE_INTERVAL']:
            self.logger.debug(f"Пропуск обновления рынка (прошло {elapsed:.1f} сек.)")
            return

        self.logger.info("Асинхронное обновление данных о рынке...")

        try:
            tasks = []

            # Создаем задачи для каждой категории предметов
            for category in self.config['ITEM_CATEGORIES'][:1]:  # ограничиваем для отладки
                task = self.api.get_market_items_async(
                    game_id=category,
                    limit=100,  # ограничиваем для отладки
                    currency="USD"
                )
                tasks.append((category, task))

            # Ожидаем выполнения всех задач
            for category, task in tasks:
                try:
                    result = await task
                    if 'objects' in result:
                        items = result.get('objects', [])
                        self.market_data[category] = items
                        self.logger.info(f"Получено {len(items)} предметов для {category}")
                        self.stats['items_analyzed'] += len(items)
                except Exception as e:
                    self.logger.error(f"Ошибка при получении данных для {category}: {e}")

            self.last_market_update = now

        except Exception as e:
            self.logger.error(f"Ошибка при асинхронном обновлении данных о рынке: {e}")
            self.stats['errors_count'] += 1

    async def _execute_trades_async(self):
        """Асинхронно выполняет торговые операции."""
        # Реализация аналогична _execute_trades, но с использованием async/await


# Инициализация логгера
logger = Logger()


def get_config_from_parameters(param_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Получает конфигурацию из параметров и файла конфигурации.

    Объединяет параметры из файла конфигурации и переданные явно,
    с приоритетом отдавая последним. Отсутствующие параметры заполняются
    значениями по умолчанию из класса TradingBotConfig.

    Args:
        param_dict: Словарь параметров с настройками.

    Returns:
        Dict[str, Any]: Словарь с конфигурационными параметрами.
    """
    # Загружаем конфигурацию из файла
    config_file = param_dict.get('config_file', TradingBotConfig.CONFIG_FILE)
    config = TradingBotConfig.load_from_file(config_file)

    # Объединяем с параметрами, переданными явно (с приоритетом)
    for key, value in param_dict.items():
        config[key] = value

    # Логируем загруженную конфигурацию
    logger.info(f"Загружена конфигурация: {len(config)} параметров")
    logger.debug(f"Детали конфигурации: {config}")

    return config


def load_api_keys() -> Dict[str, str]:
    """
    Загружает ключи API из файлов.

    Returns:
        Dict[str, str]: Словарь с ключами API {'api_key': '...', 'api_secret': '...'}

    Raises:
        FileNotFoundError: Если файлы с ключами не найдены.
    """
    keys = {}

    # Проверяем наличие файлов с ключами
    if not os.path.exists(TradingBotConfig.API_KEY_FILE):
        logger.error(f"Файл с API ключом не найден: {TradingBotConfig.API_KEY_FILE}")
        raise FileNotFoundError(f"Файл с API ключом не найден: {TradingBotConfig.API_KEY_FILE}")

    if not os.path.exists(TradingBotConfig.API_SECRET_FILE):
        logger.error(f"Файл с секретным ключом API не найден: {TradingBotConfig.API_SECRET_FILE}")
        raise FileNotFoundError(f"Файл с секретным ключом API не найден: {TradingBotConfig.API_SECRET_FILE}")

    # Читаем ключи из файлов
    try:
        with open(TradingBotConfig.API_KEY_FILE, 'r', encoding='utf-8') as f:
            keys['api_key'] = f.read().strip()

        with open(TradingBotConfig.API_SECRET_FILE, 'r', encoding='utf-8') as f:
            keys['api_secret'] = f.read().strip()

        logger.info("API ключи успешно загружены")
        return keys

    except Exception as e:
        logger.error(f"Ошибка при чтении файлов с ключами API: {e}")
        raise


def create_keys_file(api_key: str, api_secret: str) -> bool:
    """
    Создает файлы с ключами API.

    Args:
        api_key: API ключ DMarket
        api_secret: API секрет DMarket

    Returns:
        bool: True если файлы успешно созданы, иначе False
    """
    try:
        # Создаем директорию конфигурации, если она не существует
        os.makedirs(TradingBotConfig.CONFIG_DIR, exist_ok=True)

        # Записываем ключи в файлы
        with open(TradingBotConfig.API_KEY_FILE, 'w', encoding='utf-8') as f:
            f.write(api_key)

        with open(TradingBotConfig.API_SECRET_FILE, 'w', encoding='utf-8') as f:
            f.write(api_secret)

        logger.info("Файлы с ключами API успешно созданы")
        return True

    except Exception as e:
        logger.error(f"Ошибка при создании файлов с ключами API: {e}")
        return False


async def run_bot_async():
    """
    Асинхронно запускает торгового бота.

    Эта функция может использоваться для интеграции бота с другими
    асинхронными компонентами, такими как веб-сервер или Telegram бот.
    """
    bot = TradingBot(simulation_mode=True)
    await bot.run_async()


# Для обратной совместимости
LoguruReplacement = Logger


if __name__ == "__main__":
    # Запуск бота при прямом вызове скрипта
    import argparse

    parser = argparse.ArgumentParser(description='DMarket Trading Bot')
    parser.add_argument('--simulation', action='store_true', help='Запуск в режиме симуляции (без реальных сделок)')
    parser.add_argument('--config', type=str, help='Путь к файлу конфигурации')
    parser.add_argument('--debug', action='store_true', help='Включить подробное логирование')
    parser.add_argument('--async', dest='async_mode', action='store_true', help='Запуск в асинхронном режиме')

    args = parser.parse_args()

    log_level = logging.DEBUG if args.debug else logging.INFO

    # Создаем и запускаем бота
    bot = TradingBot(
        config_path=args.config,
        simulation_mode=args.simulation,
        log_level=log_level
    )

    if args.async_mode:
        asyncio.run(bot.run_async())
    else:
        bot.start()
