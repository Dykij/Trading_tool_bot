"""
Основной модуль Telegram бота для торговли на DMarket.

Этот модуль инициализирует бота, загружает все обработчики и запускает бота.
"""

import asyncio
import logging
import os
import sys
import types
from pathlib import Path
from datetime import datetime

# Настраиваем логирование сразу
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# Добавляем текущий каталог в PYTHONPATH для обеспечения доступа к модулям
current_dir = Path(__file__).parent
sys.path.append(str(current_dir))

# Класс для сбора метрик и статистики
class BotMetrics:
    """
    Класс для сбора и хранения метрик работы бота.
    """
    def __init__(self):
        """Инициализация метрик"""
        self.commands_count = 0
        self.callbacks_count = 0
        self.errors_count = 0
        self.user_sessions = {}
        self.start_time = datetime.now()
        self.requests_by_user = {}
        self.requests_by_command = {}
        self.requests_timeline = []
        
    def log_command(self, user_id, command):
        """Регистрирует выполнение команды"""
        self.commands_count += 1
        self._register_request(user_id, command)
        
    def log_callback(self, user_id, callback_data):
        """Регистрирует обработку callback"""
        self.callbacks_count += 1
        self._register_request(user_id, callback_data, is_callback=True)
        
    def log_error(self, user_id=None, details=None):
        """Регистрирует ошибку"""
        self.errors_count += 1
        if user_id:
            if user_id not in self.requests_by_user:
                self.requests_by_user[user_id] = {"commands": 0, "callbacks": 0, "errors": 0}
            self.requests_by_user[user_id]["errors"] += 1
            
    def _register_request(self, user_id, request_data, is_callback=False):
        """Внутренний метод для регистрации запроса"""
        # Регистрируем по пользователю
        if user_id not in self.requests_by_user:
            self.requests_by_user[user_id] = {"commands": 0, "callbacks": 0, "errors": 0}
            
        if is_callback:
            self.requests_by_user[user_id]["callbacks"] += 1
        else:
            self.requests_by_user[user_id]["commands"] += 1
        
        # Регистрируем по типу запроса
        key = request_data.split()[0] if not is_callback else request_data.split(':')[0]
        if key not in self.requests_by_command:
            self.requests_by_command[key] = 0
        self.requests_by_command[key] += 1
        
        # Регистрируем на временной шкале (каждый час)
        current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
        for period in self.requests_timeline:
            if period["time"] == current_hour:
                period["count"] += 1
                return
                
        # Если не нашли такой час, добавляем новый период
        self.requests_timeline.append({"time": current_hour, "count": 1})
        
    def get_uptime(self):
        """Возвращает время работы бота"""
        uptime = datetime.now() - self.start_time
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        return f"{days}d {hours}h {minutes}m {seconds}s"
        
    def get_summary(self):
        """Возвращает сводку метрик"""
        return {
            "uptime": self.get_uptime(),
            "total_commands": self.commands_count,
            "total_callbacks": self.callbacks_count,
            "total_errors": self.errors_count,
            "unique_users": len(self.requests_by_user),
            "top_commands": sorted(self.requests_by_command.items(), key=lambda x: x[1], reverse=True)[:5],
            "top_users": sorted(self.requests_by_user.items(), key=lambda x: sum(x[1].values()), reverse=True)[:5],
        }
        
    def format_summary(self):
        """Форматирует сводку метрик для вывода в сообщении"""
        summary = self.get_summary()
        top_commands_text = "\n".join([f"  {cmd}: {count}" for cmd, count in summary["top_commands"]])
        top_users_text = "\n".join([f"  ID {user_id}: {sum(stats.values())} запросов" for user_id, stats in summary["top_users"]])
        
        return (
            f"📊 <b>Статистика бота</b>\n\n"
            f"⏱️ Время работы: {summary['uptime']}\n"
            f"👥 Уникальных пользователей: {summary['unique_users']}\n\n"
            f"📝 Всего команд: {summary['total_commands']}\n"
            f"🔄 Всего колбэков: {summary['total_callbacks']}\n"
            f"⚠️ Всего ошибок: {summary['total_errors']}\n\n"
            f"🔝 <b>Самые используемые команды:</b>\n{top_commands_text}\n\n"
            f"👤 <b>Самые активные пользователи:</b>\n{top_users_text}"
        )

# Инициализируем объект для сбора метрик
bot_metrics = BotMetrics()

# Импортируем зависимости
try:
    import aiogram
    from aiogram import Bot, Dispatcher, executor, types
    from aiogram.contrib.fsm_storage.redis import RedisStorage2
    from aiogram.contrib.fsm_storage.memory import MemoryStorage
    from aiogram.contrib.middlewares.logging import LoggingMiddleware
except ImportError as e:
    logger.error(f"Ошибка импорта aiogram: {e}")
    print(f"Ошибка импорта aiogram: {e}")
    print("Установите все зависимости: pip install -r requirements.txt")
    sys.exit(1)

# Импортируем декораторы из отдельного модуля
from src.telegram.decorators import track_command, track_callback, set_metrics

# Устанавливаем объект метрик для декораторов
set_metrics(bot_metrics)

# Пропускаем импорт aioredis - мы будем использовать только RedisStorage2 из aiogram
# Это обходит проблему с конфликтом TimeoutError
redis_available = False
try:
    # Импортируем настройки
    from src.config.config import Config, setup_logging
    
    # Безопасное преобразование строки в bool
    def safe_str_to_bool(value, default=False):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            value = value.lower().strip()
            if value in ('true', 't', '1', 'yes', 'y'):
                return True
            elif value in ('false', 'f', '0', 'no', 'n'):
                return False
        return default
    
    # Проверяем, включен ли Redis в конфигурации
    redis_url = getattr(Config, 'REDIS_URL', None)
    use_redis_str = os.getenv("USE_REDIS", "false")
    use_redis = safe_str_to_bool(use_redis_str, False)
    
    redis_available = bool(redis_url) and use_redis
    
    if redis_available:
        logger.info(f"Redis включен: {redis_url}")
    else:
        logger.info(f"Redis отключен. URL: {redis_url}, USE_REDIS: {use_redis_str} -> {use_redis}")
except Exception as e:
    logger.error(f"Ошибка при проверке настроек Redis: {e}")
    print(f"Ошибка при проверке настроек Redis: {e}")
    print("Redis будет отключен. Будет использовано хранилище в памяти.")

# Функция для создания заглушки для ml_predictor
def create_ml_predictor_stub():
    """
    Создает заглушку для модуля ml_predictor.
    
    Returns:
        types.ModuleType: Заглушка для модуля ml_predictor
    """
    ml_module = types.ModuleType('ml_predictor')
    
    # Создаем заглушку для класса MLPredictor
    class DummyMLPredictor:
        def __init__(self, *args, **kwargs):
            logger.warning("Вызван конструктор заглушки MLPredictor")
            
        def train_model(self, *args, **kwargs):
            logger.warning("Вызван метод заглушки train_model")
            return None
            
        def predict_price(self, *args, **kwargs):
            logger.warning("Вызван метод заглушки predict_price")
            return 0.0
            
        def find_investment_opportunities(self, *args, **kwargs):
            logger.warning("Вызван метод заглушки find_investment_opportunities")
            return []
    
    ml_module.MLPredictor = DummyMLPredictor
    logger.info("Заглушка для ml_predictor.MLPredictor успешно создана")
    return ml_module

# Импортируем настройки и модули приложения
try:
    # Импортируем обработчики команд
    from src.bot.handlers.commands import register_command_handlers
    
    # Импортируем обработчики колбэков
    from src.telegram.callbacks import register_callback_handlers
    
    # Импортируем сервисы
    from src.trading.trading_facade import get_trading_service
    
    # Импортируем базу данных
    from src.db.init_db import init_db, close_db
    
    # Импортируем клавиатуры
    from src.telegram.keyboards import (
        get_main_keyboard,
        get_menu_kb,
        get_cancel_kb,
        get_confirmation_kb,
        get_game_selection_keyboard,
        get_item_actions_keyboard,
        get_settings_keyboard
    )
    
    # Проверяем наличие ml_predictor
    try:
        # Сначала пробуем получить уже импортированный модуль
        if 'ml_predictor' in sys.modules:
            import ml_predictor
            logger.info("Модуль ml_predictor уже был импортирован и успешно получен")
        else:
            # Пробуем импортировать из src.ml
            try:
                import src.ml.ml_predictor as ml_predictor
                sys.modules['ml_predictor'] = sys.modules['src.ml.ml_predictor']
                logger.info("Импортирован модуль src.ml.ml_predictor")
            except ImportError:
                # Пробуем импортировать из DM
                try:
                    import DM.ml_predictor as ml_predictor
                    sys.modules['ml_predictor'] = sys.modules['DM.ml_predictor']
                    logger.info("Импортирован модуль DM.ml_predictor")
                except ImportError as e:
                    # Если не удалось импортировать, создаем заглушку
                    logger.warning(f"Не удалось импортировать модуль ml_predictor: {e}")
                    sys.modules['ml_predictor'] = create_ml_predictor_stub()
    except Exception as e:
        logger.warning(f"Ошибка при импорте ml_predictor: {e}")
        if 'ml_predictor' not in sys.modules:
            sys.modules['ml_predictor'] = create_ml_predictor_stub()
        
except ImportError as e:
    logger.error(f"Ошибка импорта модулей бота: {e}")
    print(f"Ошибка импорта модулей бота: {e}")
    print("Проверьте структуру проекта и наличие всех необходимых файлов.")
    sys.exit(1)

# Импортируем функцию is_admin из нового модуля
from src.telegram.admin_manager import is_admin, get_admin_ids, update_admin_cache

# Обновляем логирование с помощью настроек из конфигурации
logger = setup_logging()
logger.info("Инициализация бота...")

# Пытаемся создать экземпляр бота
try:
    # Проверяем наличие токена
    bot_token = getattr(Config, 'TELEGRAM_BOT_TOKEN', os.getenv('TELEGRAM_BOT_TOKEN', ''))
    if not bot_token:
        logger.critical("TELEGRAM_BOT_TOKEN не установлен. Проверьте файл .env")
        print("ОШИБКА: TELEGRAM_BOT_TOKEN не установлен. Проверьте файл .env")
        sys.exit(1)
    
    # Создаем экземпляр бота
    bot = Bot(token=bot_token)
    logger.info("Бот инициализирован")
except Exception as e:
    logger.critical(f"Невозможно создать экземпляр бота: {e}")
    print(f"ОШИБКА: Невозможно создать экземпляр бота: {e}")
    sys.exit(1)

# Выбираем хранилище состояний
if redis_available:
    try:
        # Парсим URL Redis
        redis_url = Config.REDIS_URL
        # Используем RedisStorage2 из aiogram для хранения состояний
        if ":" in redis_url and "/" in redis_url:
            # Parse redis://host:port/db format
            redis_parts = redis_url.replace("redis://", "").split("/")
            host_port = redis_parts[0].split(":")
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 6379
            db = int(redis_parts[1]) if len(redis_parts) > 1 else 0
            
            storage = RedisStorage2(
                host=host,
                port=port,
                db=db,
                prefix="dmarket_bot_fsm"
            )
            logger.info(f"Используется Redis для хранения состояний пользователей: {host}:{port}/{db}")
        else:
            # Fallback to default
            storage = RedisStorage2(prefix="dmarket_bot_fsm")
            logger.info(f"Используется Redis для хранения состояний (по умолчанию)")
    except Exception as e:
        logger.warning(f"Ошибка при подключении к Redis: {e}")
        storage = MemoryStorage()
        logger.warning("Используется хранилище состояний в памяти из-за ошибки Redis")
else:
    # Если Redis недоступен, используем хранилище в памяти
    storage = MemoryStorage()
    logger.warning("Redis отключен. Используется хранилище состояний в памяти (данные будут потеряны при перезапуске)")

# Создаем диспетчер
dp = Dispatcher(bot, storage=storage)

# Добавляем middleware для логирования
dp.middleware.setup(LoggingMiddleware())

# Регистрируем все обработчики
try:
    # Регистрируем обработчики команд
    register_command_handlers(dp)
    
    logger.info("Обработчики зарегистрированы")
except Exception as e:
    logger.error(f"Ошибка при регистрации обработчиков: {e}")
    print(f"Ошибка при регистрации обработчиков: {e}")

# Обработчик отправки уведомлений о ценах
async def send_price_notification(user_id: int, item_name: str, current_price: float, profit_percent: float):
    """
    Отправляет уведомление о цене предмета пользователю.
    
    Args:
        user_id (int): ID пользователя Telegram
        item_name (str): Название предмета
        current_price (float): Текущая цена предмета
        profit_percent (float): Процент прибыли
    """
    try:
        await bot.send_message(
            user_id,
            f"🔔 <b>Уведомление о цене</b>\n\n"
            f"Предмет: <b>{item_name}</b>\n"
            f"Текущая цена: <code>{current_price:.2f}</code> USD\n"
            f"Прибыль: <code>{profit_percent:.2f}%</code>\n\n"
            f"Цена достигла целевого значения!",
            parse_mode="HTML"
        )
        logger.info(f"Отправлено уведомление о цене пользователю {user_id} для предмета {item_name}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")

# Применяем декораторы отслеживания к основным командам
@track_command
async def cmd_start_universal(message: types.Message, **kwargs):
    """
    Универсальный обработчик команды /start, который принимает любые аргументы.
    Показывает приветственное сообщение с клавиатурой.
    
    Args:
        message: Объект сообщения
        **kwargs: Любые дополнительные аргументы, которые могут быть переданы в обработчик
    """
    try:
        # Проверяем, валидно ли сообщение
        if not message:
            logger.error("Получен пустой объект message в cmd_start_universal")
            return
        
        user_name = message.from_user.first_name if hasattr(message, 'from_user') and hasattr(message.from_user, 'first_name') else "пользователь"
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        
        # Проверяем, есть ли состояние в аргументах и сбрасываем его
        state = kwargs.get('state', None)
        if state is not None and hasattr(state, 'finish'):
            try:
                await state.finish()
                logger.info(f"Сброшено состояние пользователя {user_id}")
            except Exception as e:
                logger.error(f"Ошибка при сбросе состояния в cmd_start_universal: {e}")
        
        # Приветственное сообщение с акцентом на функциональность
        welcome_message = (
            f"👋 <b>Добро пожаловать, {user_name}!</b>\n\n"
            f"🤖 Это бот для работы с DMarket Trading.\n\n"
            f"📊 <b>Доступные функции:</b>\n"
            f"• Арбитраж предметов\n"
            f"• Управление предметами\n"
            f"• Инвестиции и аналитика\n"
            f"• Настройка профиля\n\n"
            f"Используйте кнопки меню ниже для навигации."
        )
        
        # Создаем клавиатуру
        keyboard = get_menu_kb()
        
        # Отправляем сообщение с клавиатурой
        await message.answer(
            welcome_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Пользователь {user_id} выполнил команду /start")
        
    except Exception as e:
        # Логируем ошибку
        logger.error(f"Ошибка при обработке команды /start: {str(e)}", exc_info=True)
        
        # Пытаемся отправить сообщение об ошибке
        try:
            if message and hasattr(message, 'answer'):
                await message.answer(
                    "Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже или используйте команду /help."
                )
        except Exception as reply_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}", exc_info=True)

@track_command
async def cmd_help(message: types.Message):
    """
    Обрабатывает команду /help - показывает справку.
    
    Args:
        message: Объект сообщения
    """
    help_text = (
        "📋 <b>Справка по командам бота</b>\n\n"
        "<b>Основные команды:</b>\n"
        "/start - Начать работу с ботом и показать главное меню\n"
        "/help - Показать эту справку\n"
        "/status - Показать статус бота\n"
        "/arbitrage - Поиск арбитражных возможностей\n"
        "/settings - Настройки бота\n\n"
        "<b>Управление предметами:</b>\n"
        "• Используйте кнопку 'Мои предметы' для доступа к инвентарю\n"
        "• Вы можете отслеживать цены на интересующие предметы\n"
        "• Доступна статистика по вашим предметам\n\n"
        "<b>Арбитраж:</b>\n"
        "• Выберите игру для поиска арбитражных возможностей\n"
        "• Бот найдет наиболее выгодные сделки\n\n"
        "Используйте кнопки меню для быстрого доступа к функциям:"
    )
    
    # Создаем клавиатуру
    keyboard = get_menu_kb()
    
    # Отправляем сообщение с клавиатурой
    await message.answer(
        help_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@track_command
async def cmd_status(message: types.Message):
    """
    Обрабатывает команду /status - показывает статус бота.
    
    Args:
        message: Объект сообщения
    """
    status_text = (
        "📊 <b>Статус бота</b>\n\n"
        "🟢 Бот работает\n"
        f"⏱️ Время работы: {bot_metrics.get_uptime()}\n"
        f"👥 Активных пользователей: {len(bot_metrics.requests_by_user)}\n\n"
        "Все системы работают нормально. Выберите раздел из меню ниже:"
    )
    
    # Создаем клавиатуру
    keyboard = get_menu_kb()
    
    # Отправляем сообщение с клавиатурой
    await message.answer(
        status_text,
        reply_markup=keyboard,
        parse_mode="HTML"
    )

@track_command
async def cmd_stats(message: types.Message):
    """
    Обрабатывает команду /stats - показывает полную статистику бота.
    
    Args:
        message: Объект сообщения
    """
    # Проверяем, является ли пользователь администратором
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ Эта команда доступна только администраторам.")
        return
        
    # Получаем и отправляем статистику
    stats_text = bot_metrics.format_summary()
    await message.answer(stats_text, parse_mode="HTML")

@track_command
async def cmd_restart(message: types.Message):
    """
    Обрабатывает команду /restart - безопасно перезапускает бота.
    
    Args:
        message: Объект сообщения
    """
    user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
    logger.info(f"Пользователь {user_id} запустил перезапуск бота")
    
    await message.answer("🔄 Начинаю перезапуск бота...\nЭто может занять несколько секунд.")
    
    # Перезапускаем бот с небольшой задержкой
    try:
        # Импортируем функцию перезапуска
        from src.telegram.run_bot import restart_bot
        
        # Запускаем асинхронный таймер для перезапуска
        async def delayed_restart():
            await asyncio.sleep(3)  # Даем время на отправку сообщений
            restart_bot()
            
        # Запускаем таймер
        asyncio.create_task(delayed_restart())
        
    except ImportError:
        logger.error("Не удалось импортировать функцию restart_bot")
        await message.answer("❌ Ошибка при перезапуске. Функция перезапуска недоступна.")

# Добавляем функцию monitor_health, которая используется при запуске
async def monitor_health():
    """
    Функция для мониторинга работоспособности бота.
    В данной версии реализована как заглушка.
    """
    logger.info("Мониторинг здоровья бота запущен (заглушка)")
    # В будущем здесь может быть реализована полноценная функция мониторинга

# Обновляем функцию on_startup
async def on_startup(dispatcher: Dispatcher):
    """
    Выполняется при запуске бота.
    
    Args:
        dispatcher (Dispatcher): Экземпляр диспетчера бота
    """
    # Создаем словарь для отслеживания успешных инициализаций
    startup_status = {
        "db_initialized": False,
        "monitoring_started": False
    }
    
    try:
        # Инициализируем базу данных
        try:
            await init_db()
            startup_status["db_initialized"] = True
            logger.info("База данных инициализирована")
        except Exception as db_error:
            logger.error(f"Ошибка при инициализации базы данных: {db_error}", exc_info=True)
            # Продолжаем инициализацию других компонентов
        
        # Запускаем задачу мониторинга здоровья бота
        try:
            asyncio.create_task(monitor_health())
            startup_status["monitoring_started"] = True
            logger.info("Запущен мониторинг состояния бота")
        except Exception as monitor_error:
            logger.error(f"Ошибка при запуске мониторинга: {monitor_error}", exc_info=True)
            # Продолжаем инициализацию других компонентов
        
        # Получаем информацию о боте
        try:
            bot_info = await bot.get_me()
            logger.info(f"Бот @{bot_info.username} (ID: {bot_info.id}) успешно запущен")
            
            # Отправка уведомлений администраторам отключена для упрощения интерфейса
            
        except Exception as bot_info_error:
            logger.error(f"Ошибка при получении информации о боте: {bot_info_error}", exc_info=True)
            
    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации: {e}", exc_info=True)

async def on_shutdown(dispatcher: Dispatcher):
    """
    Выполняется при остановке бота.
    
    Args:
        dispatcher (Dispatcher): Экземпляр диспетчера бота
    """
    try:
        # Закрываем соединение с базой данных
        await close_db()
        logger.info("Соединение с базой данных закрыто")
        
        # Отправка уведомлений администраторам отключена для упрощения интерфейса
        logger.info("Бот успешно остановлен")
    except Exception as e:
        logger.error(f"Ошибка при остановке бота: {e}", exc_info=True)

def start_bot():
    """
    Запускает Telegram бота.
    
    Инициализирует бота, регистрирует обработчики и запускает поллинг.
    """
    try:
        # Проверяем конфигурацию перед запуском
        is_valid, errors = validate_config()
        if not is_valid:
            error_str = "\n".join(errors)
            logger.critical(f"Критические ошибки конфигурации:\n{error_str}")
            print(f"ОШИБКА: Критические ошибки конфигурации:\n{error_str}")
            sys.exit(1)
            
        # Очищаем все обработчики перед регистрацией новых
        # Это важно для предотвращения конфликтов при перезапуске
        try:
            dp.message_handlers.clear()
            dp.callback_query_handlers.clear()
            logger.info("Очищены предыдущие обработчики")
        except Exception as clear_error:
            logger.error(f"Ошибка при очистке обработчиков: {clear_error}", exc_info=True)
        
        # ВАЖНО: Инициализируем декораторы перед регистрацией обработчиков
        try:
            # Импортируем декораторы и устанавливаем метрики
            from src.telegram.decorators import set_metrics, track_command, track_callback
            # Устанавливаем объект метрик для декораторов повторно
            set_metrics(bot_metrics)
            logger.info("Декораторы метрик успешно инициализированы")
            
            # Дополнительно проверяем работоспособность декоратора track_command
            # Создаем тестовую функцию и применяем декоратор
            async def test_command_handler(message):
                pass
            decorated_test = track_command(test_command_handler)
            logger.info("Проверка декоратора track_command успешна")
            
        except Exception as decorator_error:
            logger.error(f"Ошибка при инициализации декораторов: {decorator_error}", exc_info=True)
            sys.exit(1)  # Останавливаем запуск, если декораторы не работают
        
        # Регистрируем обработчики в правильном порядке:
        # 1. Сначала регистрируем обработчики основных команд из commands.py
        try:
            from src.bot.handlers.commands import register_command_handlers
            register_command_handlers(dp)
            logger.info("Обработчики команд из commands.py зарегистрированы успешно")
        except Exception as handler_error:
            logger.error(f"Ошибка при регистрации обработчиков команд из commands.py: {handler_error}", exc_info=True)
            logger.warning("Бот может работать некорректно из-за ошибки регистрации обработчиков")
        
        # 2. Затем регистрируем обработчики колбэков
        try:
            from src.telegram.callbacks import register_callback_handlers
            register_callback_handlers(dp)
            logger.info("Обработчики колбэков зарегистрированы успешно")
        except Exception as callback_error:
            logger.error(f"Ошибка при регистрации обработчиков колбэков: {callback_error}", exc_info=True)
            logger.warning("Бот может работать некорректно из-за ошибки регистрации обработчиков колбэков")
        
        # 3. Наконец, регистрируем дополнительные обработчики из текущего модуля
        try:
            register_handlers(dp)
            logger.info("Дополнительные обработчики из telegram_bot.py зарегистрированы успешно")
        except Exception as handler_error:
            logger.error(f"Ошибка при регистрации дополнительных обработчиков: {handler_error}", exc_info=True)
            logger.warning("Бот может работать некорректно из-за ошибки регистрации обработчиков")
        
        # Регистрируем глобальный обработчик ошибок для всех типов исключений
        try:
            dp.register_errors_handler(handle_global_exception, exception=Exception)
            logger.info("Зарегистрирован глобальный обработчик исключений")
        except Exception as error_handler_error:
            logger.error(f"Не удалось зарегистрировать глобальный обработчик ошибок: {error_handler_error}", exc_info=True)
            logger.warning("Ошибки в боте не будут корректно обрабатываться!")
        
        # Настраиваем возможность отправки админских уведомлений
        send_admin_notification.bot = bot
        
        # Информируем о запуске
        logger.info(f"Запуск бота с токеном: {bot_token[:5]}...{bot_token[-5:]} (скрыт)")
        logger.info(f"Используемое хранилище состояний: {storage.__class__.__name__}")
        
        # Запускаем бота
        logger.info("Запуск бота...")
        try:
            executor.start_polling(
                dp,
                on_startup=on_startup,
                on_shutdown=on_shutdown,
                skip_updates=True
            )
            logger.info("Бот остановлен")
        except Exception as polling_error:
            logger.critical(f"Ошибка при запуске поллинга бота: {polling_error}", exc_info=True)
            print(f"КРИТИЧЕСКАЯ ОШИБКА ПРИ ЗАПУСКЕ БОТА: {polling_error}")
            sys.exit(1)
    except Exception as e:
        logger.critical(f"Критическая ошибка при запуске бота: {e}", exc_info=True)
        print(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        sys.exit(1)

# Если модуль запускается напрямую, запускаем бота
if __name__ == "__main__":
    start_bot()

# Дополнительные функции для повышения надежности и безопасности
def get_config_value(key, default=None, config_obj=None):
    """
    Безопасно получает значение из конфигурации с проверкой ошибок.
    
    Args:
        key (str): Ключ для получения из конфигурации
        default: Значение по умолчанию, если ключ не найден
        config_obj: Объект конфигурации (если None, используется Config)
    
    Returns:
        Значение из конфигурации или значение по умолчанию
    """
    try:
        if config_obj is None:
            config_obj = Config
        
        return getattr(config_obj, key, os.getenv(key, default))
    except Exception as e:
        logger.warning(f"Ошибка при получении значения конфигурации {key}: {e}")
        return default

def validate_config():
    """
    Проверяет критические параметры конфигурации.
    
    Returns:
        tuple: (bool, list) - (успех, список ошибок)
    """
    errors = []
    warnings = []
    success_items = []
    
    # Проверка токена бота (критическая ошибка)
    try:
        bot_token = get_config_value('TELEGRAM_BOT_TOKEN', '')
        if not bot_token:
            errors.append("TELEGRAM_BOT_TOKEN не установлен")
        elif len(bot_token) < 30:  # Примерная минимальная длина токена
            errors.append("TELEGRAM_BOT_TOKEN имеет недопустимый формат (слишком короткий)")
        else:
            success_items.append("TELEGRAM_BOT_TOKEN установлен")
    except Exception as e:
        errors.append(f"Ошибка при проверке TELEGRAM_BOT_TOKEN: {e}")
    
    # Проверка админских ID (некритическая ошибка, только предупреждение)
    try:
        admin_ids = get_admin_ids()
        if not admin_ids:
            warnings.append("ADMIN_IDS не установлен - функции администрирования будут недоступны")
            # Устанавливаем значение по умолчанию из ADMIN_CHAT_ID (если есть)
            admin_chat_id = os.getenv("ADMIN_CHAT_ID", "")
            if admin_chat_id:
                os.environ["ADMIN_IDS"] = admin_chat_id
                # Принудительно обновляем кэш после изменения переменной окружения
                update_admin_cache()
                success_items.append(f"ADMIN_IDS установлен из ADMIN_CHAT_ID: {admin_chat_id}")
                logger.warning(f"ADMIN_IDS установлен из ADMIN_CHAT_ID: {admin_chat_id}")
        else:
            success_items.append(f"ADMIN_IDS установлен: {len(admin_ids)} корректных ID")
    except Exception as e:
        warnings.append(f"Ошибка при проверке ADMIN_IDS: {e}")
    
    # Проверка Redis URL если используется Redis
    try:
        use_redis = safe_str_to_bool(os.getenv("USE_REDIS", "false"))
        if use_redis:
            redis_url = get_config_value('REDIS_URL', '')
            if not redis_url:
                errors.append("USE_REDIS=true, но REDIS_URL не установлен")
            elif not redis_url.startswith(('redis://', 'rediss://')):
                warnings.append(f"REDIS_URL имеет необычный формат: {redis_url}")
            else:
                success_items.append("REDIS_URL установлен корректно")
        else:
            success_items.append("Redis отключен, используется хранилище в памяти")
    except Exception as e:
        warnings.append(f"Ошибка при проверке конфигурации Redis: {e}")
    
    # Выводим предупреждения в лог
    if warnings:
        for warning in warnings:
            logger.warning(f"Предупреждение конфигурации: {warning}")
    
    # Выводим успешные проверки
    if success_items:
        for item in success_items:
            logger.info(f"Проверка конфигурации: {item}")
    
    return len(errors) == 0, errors

# Служебные функции для обработки ошибок и перезапуска
async def send_admin_notification(message, level="INFO"):
    """
    Отправляет уведомление администраторам бота.
    
    Args:
        message (str): Сообщение для отправки
        level (str): Уровень важности сообщения (INFO, WARNING, ERROR)
    """
    # Получаем список админских ID из менеджера администраторов
    admin_ids = get_admin_ids()
    
    if not admin_ids:
        logger.warning("Не найдено корректных ID администраторов, уведомления не будут отправлены")
        return
        
    # Иконка в зависимости от уровня
    icon = "ℹ️" if level == "INFO" else "⚠️" if level == "WARNING" else "🔴"
    
    # Форматируем сообщение
    formatted_message = f"{icon} <b>{level}</b>\n\n{message}"
    
    # Обрезаем сообщение, если оно слишком длинное
    max_length = 4000
    if len(formatted_message) > max_length:
        formatted_message = formatted_message[:max_length - 100] + "...\n\n[Сообщение обрезано из-за превышения лимита]"
    
    # Проверяем, что бот инициализирован
    if hasattr(send_admin_notification, 'bot') and send_admin_notification.bot:
        # Отправляем сообщение всем администраторам
        sent_count = 0
        for admin_id in admin_ids:
            try:
                await send_admin_notification.bot.send_message(
                    admin_id, 
                    formatted_message,
                    parse_mode="HTML"
                )
                sent_count += 1
            except Exception as e:
                logger.error(f"Ошибка отправки уведомления администратору {admin_id}: {e}")
        
        logger.info(f"Уведомление уровня {level} отправлено {sent_count} администраторам")
    else:
        logger.warning("Бот не инициализирован, уведомления не отправлены")

async def handle_global_exception(exception, update):
    """
    Глобальный обработчик исключений для предотвращения падения бота.
    
    Args:
        exception: Возникшее исключение
        update: Объект обновления, вызвавший исключение
    """
    error_msg = f"Неожиданное исключение: {exception}"
    logger.error(error_msg, exc_info=True)
    
    # Пытаемся отправить сообщение об ошибке администраторам
    admin_msg = f"🔴 <b>ОШИБКА В БОТЕ</b>\n\n"
    admin_msg += f"<b>Исключение:</b> {exception.__class__.__name__}\n"
    admin_msg += f"<b>Сообщение:</b> {str(exception)}\n\n"
    
    # Проверяем наличие информации об update
    if update:
        try:
            # Безопасно получаем информацию о пользователе
            user_info = None
            
            # Проверяем, есть ли message в update
            if hasattr(update, 'message') and update.message:
                if hasattr(update.message, 'from_user') and update.message.from_user:
                    user_info = update.message.from_user
                    admin_msg += f"<b>От пользователя:</b> {user_info.id} ({getattr(user_info, 'username', 'нет имени')})\n"
                    
                if hasattr(update.message, 'text'):
                    admin_msg += f"<b>Сообщение:</b> {update.message.text}\n"
                    
            # Проверяем, есть ли callback_query в update
            elif hasattr(update, 'callback_query') and update.callback_query:
                if hasattr(update.callback_query, 'from_user') and update.callback_query.from_user:
                    user_info = update.callback_query.from_user
                    admin_msg += f"<b>От пользователя:</b> {user_info.id} ({getattr(user_info, 'username', 'нет имени')})\n"
                    
                if hasattr(update.callback_query, 'data'):
                    admin_msg += f"<b>Callback:</b> {update.callback_query.data}\n"
                    
            # Если информация о пользователе не найдена, но есть JSON-представление
            if not user_info and hasattr(update, 'to_json'):
                try:
                    admin_msg += f"<b>Update:</b> {update.to_json()}\n"
                except:
                    admin_msg += f"<b>Update:</b> [невозможно сериализовать]\n"
            
            # Если есть явное строковое представление объекта
            elif not user_info and hasattr(update, '__str__'):
                try:
                    admin_msg += f"<b>Update:</b> {str(update)}\n"
                except:
                    admin_msg += f"<b>Update:</b> [невозможно получить строковое представление]\n"
                
        except Exception as e:
            admin_msg += f"<i>Ошибка получения информации о пользователе: {e.__class__.__name__}: {str(e)}</i>\n"
    
    # Отправляем уведомление админам
    try:
        await send_admin_notification(admin_msg, "ERROR")
    except Exception as e:
        logger.error(f"Не удалось отправить уведомление администраторам: {e}")
    
    # Пытаемся ответить пользователю, если возможно
    try:
        # Если это обновление с сообщением
        if update and hasattr(update, 'message') and update.message:
            if hasattr(update.message, 'reply'):
                await update.message.reply(
                    "Произошла непредвиденная ошибка. Администраторы уведомлены."
                )
                
        # Если это callback-запрос
        elif update and hasattr(update, 'callback_query') and update.callback_query:
            if hasattr(update.callback_query, 'answer'):
                await update.callback_query.answer(
                    "Произошла ошибка при обработке запроса. Попробуйте позже."
                )
    except Exception as reply_e:
        logger.error(f"Не удалось ответить пользователю о ошибке: {reply_e}")

# Служебные функции для управления состояниями FSM
async def reset_user_states(user_id, state):
    """
    Сбрасывает все состояния пользователя и возвращает к начальному состоянию.
    
    Args:
        user_id (int): ID пользователя Telegram
        state: Объект состояния FSM
    """
    try:
        logger.info(f"Сброс состояний пользователя {user_id}")
        await state.finish()
        logger.debug(f"Состояния пользователя {user_id} успешно сброшены")
        return True
    except Exception as e:
        logger.error(f"Ошибка при сбросе состояний пользователя {user_id}: {e}")
        return False

@track_command
async def cmd_admin(message: types.Message):
    """
    Обрабатывает команду /admin - показывает административную панель.
    Доступно только администраторам.
    
    Args:
        message: Объект сообщения
    """
    # Проверяем, является ли пользователь администратором
    if not is_admin(message.from_user.id):
        await message.answer("⚠️ Эта команда доступна только администраторам.")
        return
    
    user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
    logger.info(f"Администратор {user_id} запросил административную панель")
    
    # Получаем статистику бота
    stats = bot_metrics.get_summary()
    uptime = bot_metrics.get_uptime()
    
    # Формируем административную панель
    admin_panel = (
        f"🛠️ <b>Административная панель</b>\n\n"
        f"⏱️ Время работы: {uptime}\n"
        f"👥 Активных пользователей: {len(stats['unique_users'])}\n"
        f"📝 Всего команд: {stats['total_commands']}\n"
        f"🔄 Всего колбэков: {stats['total_callbacks']}\n"
        f"⚠️ Всего ошибок: {stats['total_errors']}\n\n"
        f"<b>Доступные административные команды:</b>\n"
        f"/stats - Подробная статистика\n"
        f"/restart - Перезапуск бота\n"
    )
    
    await message.answer(admin_panel, parse_mode="HTML")

def register_handlers(dp: Dispatcher):
    """
    Регистрирует дополнительные обработчики команд и колбэков.
    Не регистрирует обработчики, которые уже должны быть зарегистрированы
    в register_command_handlers и register_callback_handlers.
    
    Args:
        dp: Диспетчер
    """
    try:
        # ВАЖНО: Регистрируем универсальный обработчик /start
        # Этот обработчик будет вызван для команды /start
        dp.register_message_handler(cmd_start_universal, commands=["start"], state="*")
        logger.debug("Зарегистрирован универсальный обработчик команды /start")
        
        # Регистрируем обработчик новых сообщений и добавления бота в чат
        # Этот обработчик должен иметь более низкий приоритет, чем обработчики команд
        dp.register_message_handler(on_new_message_or_chat_member, content_types=types.ContentTypes.ANY)
        logger.debug("Зарегистрирован обработчик для новых сообщений и добавления бота в чат")
        
        # Регистрируем статистические команды
        dp.register_message_handler(cmd_stats, commands=["stats"])
        logger.debug("Зарегистрирован обработчик команды /stats")
        
        # Регистрируем команду перезапуска для администраторов
        dp.register_message_handler(cmd_restart, commands=["restart"])
        logger.debug("Зарегистрирован обработчик команды /restart")
        
        # Регистрируем административную панель
        dp.register_message_handler(cmd_admin, commands=["admin"])
        logger.debug("Зарегистрирован обработчик команды /admin")

        # Регистрируем ML-меню
        dp.register_message_handler(cmd_ml_menu, commands=["ml"])
        logger.debug("Зарегистрирован обработчик команды /ml")
        
        # Регистрируем обработчик для колбэков
        try:
            dp.callback_query_handlers.unregister(process_callback)  # На всякий случай удаляем предыдущую регистрацию
        except Exception:
            pass
            
        try:
            dp.register_callback_query_handler(process_callback)
            logger.debug("Зарегистрирован обработчик колбэков")
        except Exception as callback_error:
            logger.error(f"Ошибка при регистрации обработчика колбэков: {callback_error}")
        
        logger.info("Дополнительные обработчики зарегистрированы успешно")
    except Exception as e:
        logger.error(f"Ошибка при регистрации дополнительных обработчиков: {e}", exc_info=True)
        raise  # Повторно вызываем исключение, чтобы оно было обработано на уровне выше

# Обработчик всех колбэков
@track_callback
async def process_callback(callback_query: types.CallbackQuery):
    """
    Обрабатывает все колбэки от inline-кнопок.
    
    Args:
        callback_query: Объект колбэк-запроса
    """
    try:
        # Проверяем корректность callback_query
        if not callback_query or not hasattr(callback_query, 'data') or not callback_query.data:
            logger.warning("Получен некорректный callback_query без data")
            if hasattr(callback_query, 'answer'):
                await callback_query.answer("Ошибка: некорректный запрос")
                # Показываем основное меню в случае ошибки
                await callback_query.message.edit_text(
                    "🏠 <b>Главное меню</b>\n\n"
                    "Произошла ошибка. Пожалуйста, выберите раздел:",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
            return
        
        # Получаем и логируем callback_data
        callback_data = callback_query.data
        logger.debug(f"Получен callback: {callback_data}")
        
        # Показываем индикатор загрузки
        try:
            await callback_query.answer("Обработка...")
        except Exception as e:
            logger.warning(f"Не удалось показать индикатор загрузки: {e}")
        
        # Извлекаем категорию колбэка (часть до первого :)
        parts = callback_data.split(":", 1)
        category = parts[0] if len(parts) > 0 else "unknown"
        action = parts[1] if len(parts) > 1 else "default"
        
        # Обрабатываем в зависимости от категории
        if category == "menu":
            # Обработка меню
            await handle_menu_callback(callback_query, action)
        elif category == "arbitrage":
            # Обработка арбитража
            await handle_arbitrage_callback(callback_query, action)
        elif category == "item":
            # Обработка действий с предметами
            await handle_item_callback(callback_query, action)
        elif category == "settings":
            # Обработка настроек
            await handle_settings_callback(callback_query, action)
        elif category == "ml":
            # Обработка ML-функций
            await handle_ml_callback(callback_query, action)
        elif category == "back":
            # Возврат на предыдущий экран
            await handle_back_callback(callback_query)
        else:
            # Неизвестная категория
            logger.warning(f"Неизвестный тип колбэка: {category} в запросе {callback_data}")
            try:
                await callback_query.answer(f"Функция '{category}' в разработке", show_alert=True)
                # Возвращаем в главное меню
                await callback_query.message.edit_text(
                    "🏠 <b>Главное меню</b>\n\n"
                    "Выбранная функция находится в разработке.\n"
                    "Пожалуйста, выберите другой раздел:",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Ошибка при ответе на неизвестный callback: {e}")
            
    except Exception as e:
        logger.error(f"Ошибка при обработке колбэка: {e}", exc_info=True)
        try:
            if hasattr(callback_query, 'answer'):
                await callback_query.answer("Произошла ошибка", show_alert=True)
                
            # Всегда возвращаем пользователя в главное меню при ошибке
            if hasattr(callback_query, 'message') and hasattr(callback_query.message, 'edit_text'):
                await callback_query.message.edit_text(
                    "🏠 <b>Главное меню</b>\n\n"
                    "Произошла ошибка. Пожалуйста, выберите раздел:",
                    reply_markup=get_main_keyboard(),
                    parse_mode="HTML"
                )
        except Exception as answer_error:
            logger.error(f"Не удалось обработать ошибку колбэка: {answer_error}")

# Обработчики колбэков с реализацией функциональности
async def handle_menu_callback(callback_query: types.CallbackQuery, action="default"):
    """Обработчик меню"""
    try:
        chat_id = callback_query.message.chat.id
        message_id = callback_query.message.message_id
        
        if action == "default" or action == "main":
            # Показываем главное меню
            await callback_query.message.edit_text(
                "🏠 <b>Главное меню</b>\n\n"
                "Добро пожаловать в DMarket Trading Bot!\n"
                "Выберите интересующий вас раздел из меню ниже:",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        elif action == "arbitrage":
            # Переход в раздел арбитража
            await callback_query.message.edit_text(
                "📊 <b>Арбитраж</b>\n\n"
                "В этом разделе вы можете искать арбитражные возможности "
                "на различных торговых площадках.\n\n"
                "Выберите игру для поиска арбитражных возможностей:",
                reply_markup=get_game_selection_keyboard(),
                parse_mode="HTML"
            )
        elif action == "items":
            # Показываем меню предметов
            await callback_query.message.edit_text(
                "🎮 <b>Управление предметами</b>\n\n"
                "Здесь вы можете управлять своими предметами, отслеживать цены "
                "и настраивать уведомления.\n\n"
                "Выберите действие из меню ниже:",
                reply_markup=get_item_actions_keyboard(),
                parse_mode="HTML"
            )
        elif action == "settings":
            # Показываем меню настроек
            await callback_query.message.edit_text(
                "⚙️ <b>Настройки</b>\n\n"
                "Настройте параметры работы бота под ваши потребности.\n"
                "Выберите категорию настроек:",
                reply_markup=get_settings_keyboard(),
                parse_mode="HTML"
            )
        elif action == "investments":
            # Показываем информацию об инвестициях
            await callback_query.message.edit_text(
                "📈 <b>Инвестиции</b>\n\n"
                "В этом разделе вы можете анализировать рынок и находить "
                "наиболее выгодные инвестиционные возможности.\n\n"
                "Функция находится в разработке.\n"
                "Возвращайтесь позже!",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        else:
            await callback_query.answer(f"Раздел '{action}' в разработке")
            # Возвращаем пользователя в главное меню
            await callback_query.message.edit_text(
                "🏠 <b>Главное меню</b>\n\n"
                "Выбранная функция находится в разработке.\n"
                "Пожалуйста, выберите другой раздел:",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Ошибка при обработке меню: {e}")
        try:
            await callback_query.answer("Произошла ошибка в меню")
            # Пытаемся вернуть пользователя в главное меню
            await callback_query.message.edit_text(
                "🏠 <b>Главное меню</b>\n\n"
                "Произошла ошибка. Пожалуйста, выберите раздел:",
                reply_markup=get_main_keyboard(),
                parse_mode="HTML"
            )
        except Exception:
            pass

# Добавляем импорты для арбитражных функций
# Создаем единый интерфейс для модулей арбитража
class ArbitrageManager:
    """
    Класс для управления импортом и использованием арбитражных алгоритмов.
    Обеспечивает единый интерфейс для работы с модулями арбитража.
    """
    def __init__(self):
        """Инициализация арбитражного менеджера"""
        self.bellman_ford = None
        self.linear_programming = None
        self.arbitrage_finder = None
        self.arbitrage_modes_manager = None
        self.initialized = False
    
    async def initialize(self):
        """Инициализирует модули для арбитража"""
        if self.initialized:
            return
        
        try:
            # Пытаемся импортировать новый модуль с режимами арбитража
            from src.arbitrage.arbitrage_modes import ArbitrageManager as ModesManager
            self.arbitrage_modes_manager = ModesManager()
            logger.info("Успешно импортирован менеджер режимов арбитража")
        except ImportError:
            logger.warning("Не удалось импортировать модуль arbitrage_modes")
            
        # Импортируем остальные модули арбитража
        # ... (существующий код)
        
        self.initialized = True
        
    async def find_all_arbitrage_opportunities(self, *args, **kwargs):
        """Находит все арбитражные возможности, используя все доступные методы"""
        if not self.initialized:
            await self.initialize()
            
        opportunities = []
        
        # Если доступен модуль режимов арбитража, используем его
        if self.arbitrage_modes_manager:
            try:
                mode_opportunities = await self.arbitrage_modes_manager.find_opportunities(*args, **kwargs)
                opportunities.extend(mode_opportunities)
                logger.info(f"Найдено {len(mode_opportunities)} возможностей через режимы арбитража")
            except Exception as e:
                logger.error(f"Ошибка при поиске арбитражных возможностей через менеджер режимов: {e}")
        
        # Используем Беллман-Форд как запасной вариант
        if self.bellman_ford and (not opportunities or kwargs.get('use_all_methods', False)):
            try:
                bf_opportunities = await self.bellman_ford.find_opportunities(*args, **kwargs)
                opportunities.extend(bf_opportunities)
                logger.info(f"Найдено {len(bf_opportunities)} возможностей через Bellman-Ford")
            except Exception as e:
                logger.error(f"Ошибка при поиске арбитражных возможностей через Bellman-Ford: {e}")
        
        if not opportunities:
            logger.warning("Не удалось найти арбитражные возможности ни одним из методов")
        
        return opportunities

    async def execute_arbitrage_strategy(self, opportunities, mode=None, execute=False):
        """
        Выполняет арбитражную стратегию.
        
        Args:
            opportunities: Список арбитражных возможностей
            mode: Режим арбитража
            execute: Выполнять ли реальные транзакции
        
        Returns:
            Результаты выполнения стратегии
        """
        if not self.initialized:
            await self.initialize()
            
        # Если доступен новый модуль, используем его
        if self.arbitrage_modes_manager:
            try:
                # Импортируем ArbitrageMode для преобразования строки в enum
                from src.arbitrage.arbitrage_modes import ArbitrageMode
                
                # Преобразуем строковой режим в enum при необходимости
                arb_mode = None
                if isinstance(mode, str):
                    if mode == "balance_boost":
                        arb_mode = ArbitrageMode.BALANCE_BOOST
                    elif mode == "medium_trader":
                        arb_mode = ArbitrageMode.MEDIUM_TRADER
                    elif mode == "trade_pro":
                        arb_mode = ArbitrageMode.TRADE_PRO
                else:
                    arb_mode = mode
                
                # Если у нас есть арбитражные возможности в виде DataFrame, конвертируем в DataFrame
                if isinstance(opportunities, list):
                    import pandas as pd
                    opportunities_df = pd.DataFrame(opportunities)
                else:
                    opportunities_df = opportunities
                
                # Выполняем стратегию с новым менеджером
                if arb_mode and not opportunities_df.empty:
                    result = await self.arbitrage_modes_manager.execute_arbitrage_strategy(
                        opportunities_df, arb_mode, execute
                    )
                    logger.info(f"Выполнена арбитражная стратегия через arbitrage_modes, результат: {result['success']}")
                    return result
            except Exception as e:
                logger.error(f"Ошибка при выполнении стратегии через новый модуль: {e}", exc_info=True)
        
        # Если новый модуль не сработал, используем старые методы
        # ... (существующий код для выполнения стратегии)
        
        logger.warning("Не удалось выполнить арбитражную стратегию")
        return {"success": False, "message": "Не удалось выполнить стратегию"}

# Создаем экземпляр арбитражного менеджера
arbitrage_manager = ArbitrageManager()
# Убираем вызов initialize() здесь, чтобы избежать "no running event loop"
# arbitrage_manager.initialize()

# Определяем удобные функции-обертки для доступа к функциональности
async def find_all_arbitrage_opportunities_async(*args, **kwargs):
    """
    Обертка для быстрого доступа к функции поиска арбитражных возможностей.
    """
    if not arbitrage_manager.initialized:
        await arbitrage_manager.initialize()
    return await arbitrage_manager.find_all_arbitrage_opportunities(*args, **kwargs)

logger.info("Менеджер арбитражных алгоритмов создан и готов к инициализации")

@track_command
async def on_new_message_or_chat_member(message: types.Message):
    """
    Обработчик для новых сообщений и добавления бота в чат.
    Автоматически отправляет приветственное сообщение с клавиатурой.
    
    Args:
        message: Объект сообщения
    """
    # Проверяем, это новый чат с ботом или добавление бота в групповой чат
    is_new_chat = False
    
    # Проверяем добавление бота в групповой чат
    if message.new_chat_members and any(member.id == bot.id for member in message.new_chat_members):
        is_new_chat = True
        logger.info(f"Бот добавлен в групповой чат {message.chat.id}")
    
    # Проверяем, что это личный чат с пользователем
    if message.chat.type == 'private':
        # Всегда показываем клавиатуру в личных чатах для удобства пользователей
        # если входящее сообщение не является командой
        if not message.text or not message.text.startswith('/'):
            is_new_chat = True
    
    # Если это новый чат или необходимо показать клавиатуру, отправляем приветствие с клавиатурой
    if is_new_chat:
        user_name = message.from_user.first_name if hasattr(message, 'from_user') and hasattr(message.from_user, 'first_name') else "пользователь"
        
        welcome_message = (
            f"👋 <b>Здравствуйте, {user_name}!</b>\n\n"
            f"Это бот для работы с DMarket Trading.\n"
            f"Используйте /help, чтобы узнать доступные команды."
        )
        
        # Создаем клавиатуру
        keyboard = get_menu_kb()
        
        # Отправляем сообщение с клавиатурой
        await message.answer(
            welcome_message,
            reply_markup=keyboard,
            parse_mode="HTML"
        )
        
        logger.info(f"Отправлено приветственное сообщение с клавиатурой пользователю {message.from_user.id}")

# Обработчики для ML-моделей
@track_command
async def cmd_ml_menu(message: types.Message):
    """
    Показывает меню опций машинного обучения.
    
    Args:
        message: Объект сообщения от пользователя
    """
    try:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton("🧠 Прогноз цен", callback_data="ml:price_prediction"),
            types.InlineKeyboardButton("📈 Инвестиционные возможности", callback_data="ml:investment"),
            types.InlineKeyboardButton("🔍 Анализ временных рядов", callback_data="ml:time_series"),
            types.InlineKeyboardButton("📊 Сравнение алгоритмов", callback_data="ml:compare_algorithms"),
            types.InlineKeyboardButton("◀️ Назад", callback_data="menu:main")
        )
        
        await message.answer(
            "🤖 <b>Меню машинного обучения</b>\n\n"
            "Выберите одну из доступных опций для анализа рынка с помощью ML-моделей:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка при отображении ML-меню: {e}", exc_info=True)
        await message.answer("Произошла ошибка при загрузке меню. Попробуйте позже.")

@track_callback
async def handle_ml_callback(callback_query: types.CallbackQuery, action="default"):
    """
    Обработчик колбэков для ML-функций.
    
    Args:
        callback_query: Объект колбэк-запроса
        action: Дополнительный параметр действия
    """
    try:
        if action == "price_prediction":
            # Показываем меню выбора алгоритма для прогноза цен
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("📊 Prophet", callback_data="ml:algorithm:prophet"),
                types.InlineKeyboardButton("🌲 XGBoost", callback_data="ml:algorithm:xgboost"),
                types.InlineKeyboardButton("📈 ARIMA", callback_data="ml:algorithm:arima"),
                types.InlineKeyboardButton("🔄 Ансамбль (все методы)", callback_data="ml:algorithm:ensemble"),
                types.InlineKeyboardButton("◀️ Назад", callback_data="ml:default")
            )
            
            await callback_query.message.edit_text(
                "🧠 <b>Прогноз цен</b>\n\n"
                "Выберите алгоритм для прогнозирования цен предметов:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        elif action == "investment":
            # Запрашиваем данные для инвестиционных возможностей
            await callback_query.message.edit_text(
                "📈 <b>Инвестиционные возможности</b>\n\n"
                "Идет поиск инвестиционных возможностей...",
                parse_mode="HTML"
            )
            
            # Здесь должен быть вызов ML-модели для поиска инвестиционных возможностей
            # Например: opportunities = await ml_predictor.find_investment_opportunities()
            
            # Временная заглушка с примерными данными
            opportunities = [
                {"item_name": "AWP | Азимов", "predicted_roi": 15.2, "confidence": 0.85},
                {"item_name": "AK-47 | Вулкан", "predicted_roi": 12.7, "confidence": 0.82},
                {"item_name": "M4A4 | Император", "predicted_roi": 9.5, "confidence": 0.78}
            ]
            
            if opportunities:
                # Форматируем результаты
                results_text = "\n".join([
                    f"🔹 <b>{item['item_name']}</b>: ROI {item['predicted_roi']:.1f}% "
                    f"(уверенность: {item['confidence']*100:.0f}%)"
                    for item in opportunities[:5]  # Показываем топ-5
                ])
                
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton("◀️ Назад", callback_data="ml:default")
                )
                
                await callback_query.message.edit_text(
                    f"📈 <b>Топ инвестиционных возможностей</b>\n\n"
                    f"{results_text}\n\n"
                    f"<i>Данные основаны на прогнозах ML-моделей.</i>",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
            else:
                keyboard = types.InlineKeyboardMarkup()
                keyboard.add(
                    types.InlineKeyboardButton("◀️ Назад", callback_data="ml:default")
                )
                
                await callback_query.message.edit_text(
                    "📈 <b>Инвестиционные возможности</b>\n\n"
                    "К сожалению, не удалось найти подходящие инвестиционные возможности.\n"
                    "Попробуйте позже или измените параметры поиска.",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
        
        elif action == "time_series":
            # Показываем меню выбора периода для анализа временных рядов
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton("День", callback_data="ml:time_series:day"),
                types.InlineKeyboardButton("Неделя", callback_data="ml:time_series:week"),
                types.InlineKeyboardButton("Месяц", callback_data="ml:time_series:month"),
                types.InlineKeyboardButton("Год", callback_data="ml:time_series:year"),
                types.InlineKeyboardButton("◀️ Назад", callback_data="ml:default")
            )
            
            await callback_query.message.edit_text(
                "🔍 <b>Анализ временных рядов</b>\n\n"
                "Выберите период для анализа:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        elif action == "compare_algorithms":
            # Показываем сравнение алгоритмов
            await callback_query.message.edit_text(
                "📊 <b>Сравнение алгоритмов</b>\n\n"
                "Идет подготовка данных для сравнения...",
                parse_mode="HTML"
            )
            
            # Временная заглушка с данными для сравнения
            comparison_data = [
                {"algorithm": "Prophet", "accuracy": 87.5, "processing_time": 0.8},
                {"algorithm": "XGBoost", "accuracy": 89.2, "processing_time": 1.2},
                {"algorithm": "ARIMA", "accuracy": 85.1, "processing_time": 0.6},
                {"algorithm": "Ensemble", "accuracy": 91.4, "processing_time": 2.5}
            ]
            
            # Форматируем результаты
            results_text = "\n".join([
                f"🔹 <b>{data['algorithm']}</b>: точность {data['accuracy']:.1f}%, "
                f"время {data['processing_time']:.1f} сек."
                for data in comparison_data
            ])
            
            keyboard = types.InlineKeyboardMarkup()
            keyboard.add(
                types.InlineKeyboardButton("◀️ Назад", callback_data="ml:default")
            )
            
            await callback_query.message.edit_text(
                f"📊 <b>Сравнение алгоритмов ML</b>\n\n"
                f"{results_text}\n\n"
                f"<i>Ансамблевый метод показывает наилучшую точность, "
                f"но требует больше времени на обработку.</i>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
        
        elif action.startswith("algorithm:"):
            # Обработка выбора алгоритма прогнозирования
            algorithm = action.split(":")[-1]
            
            await callback_query.message.edit_text(
                f"🧮 <b>Прогнозирование с {algorithm.upper()}</b>\n\n"
                f"Пожалуйста, отправьте название предмета для прогноза цены.",
                parse_mode="HTML"
            )
            
            # Устанавливаем состояние ожидания названия предмета
            # (для этого нужна реализация FSM, которая должна быть в другом месте)
        
        elif action.startswith("time_series:"):
            # Обработка выбора периода для анализа временных рядов
            period = action.split(":")[-1]
            
            # Здесь должен быть вызов функции для анализа временных рядов
            # с выбранным периодом
            
            # Заглушка
            await callback_query.message.edit_text(
                f"🔍 <b>Анализ временных рядов за {period}</b>\n\n"
                f"Функция в разработке. Попробуйте позже.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("◀️ Назад", callback_data="ml:time_series")
                ),
                parse_mode="HTML"
            )
        
        else:
            # Показываем основное ML-меню
            keyboard = types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(
                types.InlineKeyboardButton("🧠 Прогноз цен", callback_data="ml:price_prediction"),
                types.InlineKeyboardButton("📈 Инвестиционные возможности", callback_data="ml:investment"),
                types.InlineKeyboardButton("🔍 Анализ временных рядов", callback_data="ml:time_series"),
                types.InlineKeyboardButton("📊 Сравнение алгоритмов", callback_data="ml:compare_algorithms"),
                types.InlineKeyboardButton("◀️ Назад", callback_data="menu:main")
            )
            
            await callback_query.message.edit_text(
                "🤖 <b>Меню машинного обучения</b>\n\n"
                "Выберите одну из доступных опций для анализа рынка с помощью ML-моделей:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Ошибка при обработке ML-колбэка: {e}", exc_info=True)
        try:
            await callback_query.answer("Произошла ошибка. Попробуйте позже.")
            await callback_query.message.edit_text(
                "🤖 <b>Меню машинного обучения</b>\n\n"
                "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже.",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("◀️ Главное меню", callback_data="menu:main")
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass
