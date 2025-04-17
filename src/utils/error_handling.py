"""
Модуль обработки ошибок для DMarket Trading Bot.

Этот модуль содержит классы исключений и утилиты для централизованной
обработки ошибок в приложении. Он предоставляет:
- Иерархию исключений для разных типов ошибок
- Функции-декораторы для обработки ошибок
- Утилиты для логирования ошибок
"""

import enum
import functools
import inspect
import logging
import sys
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar, Union, cast

# Настройка логгера
logger = logging.getLogger(__name__)

# Типы для декораторов
F = TypeVar('F', bound=Callable[..., Any])


class ErrorSeverity(enum.Enum):
    """Уровни серьезности ошибок."""
    LOW = 1      # Незначительная ошибка, не влияющая на основную функциональность
    MEDIUM = 2   # Ошибка, которая может повлиять на некоторые функции, но не критическая
    HIGH = 3     # Серьезная ошибка, блокирующая основную функциональность
    CRITICAL = 4  # Критическая ошибка, требующая немедленного внимания


class BaseBotError(Exception):
    """Базовое исключение для всех ошибок бота."""
    
    def __init__(self, message: str, *args: Any, **kwargs: Any) -> None:
        """
        Инициализация базового исключения.
        
        Args:
            message: Сообщение об ошибке
            *args: Дополнительные аргументы
            **kwargs: Дополнительные именованные аргументы
        """
        self.message = message
        self.details: Dict[str, Any] = kwargs.get('details', {})
        super().__init__(message, *args)
    
    def __str__(self) -> str:
        """
        Строковое представление исключения.
        
        Returns:
            str: Строковое представление исключения
        """
        if self.details:
            return f"{self.message} (details: {self.details})"
        return self.message


# Ошибки конфигурации
class ConfigError(BaseBotError):
    """Ошибка, связанная с конфигурацией бота."""
    pass


class ApiKeyError(ConfigError):
    """Ошибка, связанная с API-ключами."""
    pass


# Ошибки API и сети
class ApiError(BaseBotError):
    """Ошибка, связанная с взаимодействием с API."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None, 
        response: Optional[Dict[str, Any]] = None, 
        *args: Any, 
        **kwargs: Any
    ) -> None:
        """
        Инициализация ошибки API.
        
        Args:
            message: Сообщение об ошибке
            status_code: Код ответа HTTP
            response: Полный ответ от API
            *args: Дополнительные аргументы
            **kwargs: Дополнительные именованные аргументы
        """
        self.status_code = status_code
        self.response = response or {}
        details = {'status_code': status_code, 'response': response}
        super().__init__(message, *args, details=details, **kwargs)


class NetworkError(BaseBotError):
    """Ошибка сети."""
    pass


class RateLimitError(ApiError):
    """Ошибка превышения лимита запросов."""
    pass


# Ошибки базы данных
class DatabaseError(BaseBotError):
    """Ошибка, связанная с базой данных."""
    pass


# Ошибки машинного обучения
class MLError(BaseBotError):
    """Базовая ошибка машинного обучения."""
    pass


class ModelNotFoundError(MLError):
    """Ошибка отсутствия модели."""
    pass


class TrainingError(MLError):
    """Ошибка при обучении модели."""
    pass


class PredictionError(MLError):
    """Ошибка при предсказании."""
    pass


# Ошибки торговли
class TradingError(BaseBotError):
    """Ошибка в процессе торговли."""
    pass


class ArbitrageError(TradingError):
    """Ошибка в процессе арбитража."""
    pass


class InsufficientFundsError(TradingError):
    """Ошибка недостаточности средств."""
    pass


class ItemNotFoundError(TradingError):
    """Ошибка отсутствия предмета."""
    pass


def handle_errors(
    error_types: Optional[List[Type[Exception]]] = None,
    default_error_type: Type[BaseBotError] = BaseBotError,
    log_level: int = logging.ERROR,
    reraise: bool = True
) -> Callable[[F], F]:
    """
    Декоратор для стандартизированной обработки ошибок.
    
    Перехватывает указанные типы ошибок, логирует их и преобразует в BaseBotError.
    
    Args:
        error_types: Список типов ошибок для обработки
        default_error_type: Тип ошибки по умолчанию для оборачивания
        log_level: Уровень логирования
        reraise: Флаг, указывающий нужно ли повторно вызывать ошибку после обработки
        
    Returns:
        Декорированная функция
    """
    if error_types is None:
        error_types = [Exception]
    
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return func(*args, **kwargs)
            except tuple(error_types) as e:
                # Если ошибка уже является BaseBotError, используем её
                if isinstance(e, BaseBotError):
                    error = e
                else:
                    # Создаем контекст ошибки
                    context = get_error_context(func, args, kwargs, e)
                    
                    # Оборачиваем в наш тип ошибки
                    error = default_error_type(
                        message=str(e),
                        details=context,
                        original_error=e
                    )
                
                # Логируем ошибку
                log_msg = format_error_for_log(error, func.__name__)
                logger.log(log_level, log_msg)
                
                # Повторно вызываем ошибку, если нужно
                if reraise:
                    raise error
                
                # Возвращаем None, если не повторно вызываем ошибку
                return None
        
        return cast(F, wrapper)
    
    return decorator


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    retry_on: Type[Exception] = BaseBotError
) -> Callable[[F], F]:
    """
    Декоратор для повторного вызова функции при временных ошибках.
    
    Args:
        max_attempts: Максимальное количество попыток
        delay: Начальная задержка между попытками (в секундах)
        backoff_factor: Множитель для увеличения задержки с каждой попыткой
        retry_on: Тип ошибки, при котором выполнять повторные попытки
        
    Returns:
        Декорированная функция
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempts = 0
            current_delay = delay
            
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except retry_on as e:
                    attempts += 1
                    
                    # Проверяем, является ли ошибка временной
                    if isinstance(e, BaseBotError) and not e.is_temporary:
                        logger.warning(
                            f"Not retrying {func.__name__} due to permanent error: {e.message}"
                        )
                        raise
                    
                    # Если это последняя попытка, повторно возбуждаем ошибку
                    if attempts >= max_attempts:
                        logger.error(
                            f"Failed {func.__name__} after {attempts} attempts: {e}"
                        )
                        raise
                    
                    # Логируем повторную попытку
                    logger.warning(
                        f"Retrying {func.__name__} (attempt {attempts}/{max_attempts}) "
                        f"after error: {e}. Retrying in {current_delay:.2f}s"
                    )
                    
                    # Ждем перед следующей попыткой
                    time.sleep(current_delay)
                    
                    # Увеличиваем задержку для следующей попытки
                    current_delay *= backoff_factor
            
            # Этот код не должен выполниться, но нужен для типизации
            return None
        
        return cast(F, wrapper)
    
    return decorator


def validate_args(**type_specs: Union[Type[Any], tuple]) -> Callable[[F], F]:
    """
    Декоратор для валидации типов аргументов функции.
    
    Пример использования:
        @validate_args(name=str, age=int, height=(int, float))
        def register_user(name, age, height):
            ...
    
    Args:
        **type_specs: Ожидаемые типы аргументов
        
    Returns:
        Декорированная функция
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Получаем информацию об аргументах функции
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Проверяем типы аргументов
            for param_name, expected_type in type_specs.items():
                if param_name in bound_args.arguments:
                    arg_value = bound_args.arguments[param_name]
                    
                    # Пропускаем None, если тип не является Optional
                    if arg_value is None:
                        continue
                    
                    # Проверяем, соответствует ли аргумент ожидаемому типу
                    if not isinstance(arg_value, expected_type):
                        raise TypeError(
                            f"Argument '{param_name}' must be of type {expected_type}, "
                            f"got {type(arg_value).__name__} instead"
                        )
            
            return func(*args, **kwargs)
        
        return cast(F, wrapper)
    
    return decorator


def log_execution(
    log_level: int = logging.DEBUG,
    log_args: bool = False,
    log_result: bool = False
) -> Callable[[F], F]:
    """
    Декоратор для логирования вызовов функции.
    
    Args:
        log_level: Уровень логирования
        log_args: Флаг, указывающий нужно ли логировать аргументы
        log_result: Флаг, указывающий нужно ли логировать результат
        
    Returns:
        Декорированная функция
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            func_name = func.__qualname__
            
            # Логируем начало выполнения
            start_msg = f"Executing {func_name}"
            if log_args:
                # Безопасное форматирование аргументов (без секретных данных)
                safe_args = [f"{arg}" for arg in args]
                safe_kwargs = {k: v if 'password' not in k.lower() and 'secret' not in k.lower() else '***'
                               for k, v in kwargs.items()}
                start_msg += f" with args: {safe_args}, kwargs: {safe_kwargs}"
            
            logger.log(log_level, start_msg)
            
            # Замеряем время выполнения
            start_time = time.time()
            
            try:
                # Выполняем функцию
                result = func(*args, **kwargs)
                
                # Вычисляем время выполнения
                execution_time = time.time() - start_time
                
                # Логируем успешное выполнение
                end_msg = f"Completed {func_name} in {execution_time:.4f}s"
                if log_result:
                    # Безопасное форматирование результата
                    safe_result = str(result)
                    if len(safe_result) > 1000:
                        safe_result = safe_result[:1000] + "... [truncated]"
                    end_msg += f" with result: {safe_result}"
                
                logger.log(log_level, end_msg)
                
                return result
                
            except Exception as e:
                # Вычисляем время до ошибки
                execution_time = time.time() - start_time
                
                # Логируем ошибку
                logger.log(
                    logging.ERROR,
                    f"Failed {func_name} after {execution_time:.4f}s with error: {e}"
                )
                
                # Повторно возбуждаем ошибку
                raise
        
        return cast(F, wrapper)
    
    return decorator


def format_error_for_user(error: Exception) -> str:
    """
    Форматирует ошибку для отображения пользователю.
    
    Args:
        error: Объект ошибки
        
    Returns:
        Отформатированное сообщение об ошибке
    """
    if isinstance(error, BaseBotError):
        # Для пользовательских ошибок возвращаем сообщение и рекомендации
        if error.severity == ErrorSeverity.LOW:
            recommendation = "Вы можете продолжить работу."
        elif error.severity == ErrorSeverity.MEDIUM:
            recommendation = "Некоторые функции могут быть недоступны."
        elif error.severity == ErrorSeverity.HIGH:
            recommendation = "Рекомендуется перезапустить приложение."
        else:  # CRITICAL
            recommendation = "Требуется немедленное вмешательство."
        
        return f"Ошибка: {error.message}. {recommendation}"
    else:
        # Для стандартных ошибок возвращаем общее сообщение
        return f"Произошла ошибка: {str(error)}"


def format_error_for_log(error: Exception, context: str = "") -> str:
    """
    Форматирует ошибку для логирования.
    
    Args:
        error: Объект ошибки
        context: Контекст, в котором произошла ошибка
        
    Returns:
        Отформатированное сообщение для лога
    """
    if isinstance(error, BaseBotError):
        # Для пользовательских ошибок включаем детальную информацию
        details_str = ", ".join(f"{k}: {v}" for k, v in error.details.items()
                              if k != "traceback")
        
        return (
            f"[{context}] {error.__class__.__name__}: {error.message} "
            f"(Severity: {error.severity.name}, Temporary: {error.is_temporary}) "
            f"Details: {details_str}"
        )
    else:
        # Для стандартных ошибок включаем тип и сообщение
        return f"[{context}] {error.__class__.__name__}: {str(error)}"


def is_temporary_error(error: Exception) -> bool:
    """
    Проверяет, является ли ошибка временной.
    
    Args:
        error: Объект ошибки
        
    Returns:
        True, если ошибка временная, иначе False
    """
    if isinstance(error, BaseBotError):
        return error.is_temporary
    
    # Некоторые стандартные ошибки считаем временными
    temporary_error_types = [
        ConnectionError,
        TimeoutError,
        OSError
    ]
    
    return any(isinstance(error, err_type) for err_type in temporary_error_types)


def get_error_context(
    func: Callable[..., Any],
    args: tuple,
    kwargs: Dict[str, Any],
    error: Exception
) -> Dict[str, Any]:
    """
    Собирает контекст ошибки для логирования.
    
    Args:
        func: Функция, в которой произошла ошибка
        args: Аргументы функции
        kwargs: Именованные аргументы функции
        error: Объект ошибки
        
    Returns:
        Словарь с контекстом ошибки
    """
    # Получаем информацию о функции и её аргументах
    sig = inspect.signature(func)
    
    try:
        # Привязываем аргументы к параметрам функции
        bound_args = sig.bind(*args, **kwargs)
        bound_args.apply_defaults()
        
        # Создаем безопасную версию аргументов (без паролей и секретов)
        safe_args = {}
        for param_name, param_value in bound_args.arguments.items():
            if any(secret_key in param_name.lower() for secret_key in ['password', 'secret', 'key']):
                safe_args[param_name] = '***'
            else:
                safe_args[param_name] = str(param_value)
    except Exception:
        # В случае ошибки при анализе аргументов, используем безопасный вариант
        safe_args = {"args": f"{len(args)} positional args", "kwargs": f"{len(kwargs)} keyword args"}
    
    # Собираем контекст
    context = {
        "function": func.__qualname__,
        "module": func.__module__,
        "args": safe_args,
        "error_type": error.__class__.__name__,
        "error_message": str(error),
        "timestamp": time.time()
    }
    
    return context


def setup_error_handling(
    log_file: Optional[str] = None, 
    console_level: int = logging.INFO, 
    file_level: int = logging.DEBUG
) -> None:
    """
    Настраивает глобальную обработку исключений и логирование.
    
    Args:
        log_file: Путь к файлу для логирования
        console_level: Уровень логирования для консоли
        file_level: Уровень логирования для файла
    """
    # Настраиваем корневой логгер
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Форматтер для логов
    formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s - %(message)s'
    )
    
    # Консольный обработчик
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Файловый обработчик (если задан файл)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    # Обработчик неперехваченных исключений
    def handle_uncaught_exception(exc_type: type, exc_value: Exception, exc_traceback: Any) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            # Стандартная обработка для KeyboardInterrupt
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Логируем неперехваченное исключение
        logger.critical(
            "Uncaught exception",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Устанавливаем обработчик
    sys.excepthook = handle_uncaught_exception 