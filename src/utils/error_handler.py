"""
Модуль для централизованной обработки ошибок в приложении.

Этот модуль предоставляет функции и классы для обработки, логирования и отчетности об ошибках,
возникающих в разных компонентах приложения.
"""

import logging
import traceback
import sys
import json
import datetime
from enum import Enum
from typing import Dict, Any, Optional, List, Union, Callable

# Настраиваем логгер для ошибок
logger = logging.getLogger("error_handler")
handler = logging.FileHandler("errors.log")
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)
logger.setLevel(logging.ERROR)

# Типы ошибок
class ErrorType(Enum):
    """Типы ошибок в приложении"""
    API_ERROR = "api_error"              # Ошибки API
    NETWORK_ERROR = "network_error"      # Сетевые ошибки
    AUTH_ERROR = "auth_error"            # Ошибки аутентификации
    DATA_ERROR = "data_error"            # Ошибки данных
    VALIDATION_ERROR = "validation_error"  # Ошибки валидации
    TRADING_ERROR = "trading_error"      # Ошибки торговли
    SYSTEM_ERROR = "system_error"        # Системные ошибки
    TELEGRAM_ERROR = "telegram_error"    # Ошибки Telegram-бота
    ARBITRAGE_ERROR = "arbitrage_error"  # Ошибки арбитража
    UNKNOWN_ERROR = "unknown_error"      # Неизвестные ошибки

class TradingError(Exception):
    """
    Основной класс исключений для ошибок торговли.
    
    Атрибуты:
        message (str): Сообщение об ошибке
        error_type (ErrorType): Тип ошибки
        context (dict): Контекстная информация об ошибке
        original_exception (Exception): Исходное исключение, если есть
    """
    
    def __init__(
        self,
        message: str,
        error_type: ErrorType = ErrorType.UNKNOWN_ERROR,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        self.message = message
        self.error_type = error_type
        self.context = context or {}
        self.original_exception = original_exception
        self.timestamp = datetime.datetime.now()
        
        # Логируем ошибку при создании
        self.log_error()
        
        super().__init__(self.message)
    
    def log_error(self) -> None:
        """Логирует ошибку в файл"""
        error_info = {
            "message": self.message,
            "type": self.error_type.value,
            "timestamp": self.timestamp.isoformat(),
            "context": self.context
        }
        
        if self.original_exception:
            error_info["original_error"] = str(self.original_exception)
            error_info["traceback"] = traceback.format_exc()
        
        logger.error(f"[{self.error_type.value.upper()}] {self.message}")
        logger.error(f"Context: {json.dumps(error_info, default=str)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Преобразует ошибку в словарь для ответа API или сообщения бота
        
        Returns:
            Dict[str, Any]: Словарь с информацией об ошибке
        """
        return {
            "error": True,
            "error_type": self.error_type.value,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }
    
    def to_user_message(self) -> str:
        """
        Возвращает сообщение об ошибке в понятном для пользователя формате
        
        Returns:
            str: Сообщение для отображения пользователю
        """
        # Сообщения для разных типов ошибок
        user_messages = {
            ErrorType.API_ERROR: "Ошибка при обращении к API DMarket. Попробуйте позже.",
            ErrorType.NETWORK_ERROR: "Проблема с сетевым подключением. Проверьте интернет-соединение.",
            ErrorType.AUTH_ERROR: "Ошибка авторизации. Проверьте свои API-ключи.",
            ErrorType.DATA_ERROR: "Ошибка в данных. Пожалуйста, проверьте введенные значения.",
            ErrorType.VALIDATION_ERROR: f"Ошибка валидации: {self.message}",
            ErrorType.TRADING_ERROR: "Ошибка при выполнении торговой операции.",
            ErrorType.SYSTEM_ERROR: "Системная ошибка. Пожалуйста, сообщите администратору.",
            ErrorType.TELEGRAM_ERROR: "Ошибка в работе телеграм-бота. Попробуйте позже.",
            ErrorType.ARBITRAGE_ERROR: "Ошибка при поиске арбитража.",
            ErrorType.UNKNOWN_ERROR: "Произошла неизвестная ошибка. Попробуйте еще раз."
        }
        
        return user_messages.get(self.error_type, self.message)

# Специализированные исключения
class APIError(TradingError):
    """Ошибки при работе с API"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.API_ERROR,
            context=context,
            original_exception=original_exception
        )

class NetworkError(TradingError):
    """Сетевые ошибки"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.NETWORK_ERROR,
            context=context,
            original_exception=original_exception
        )

class AuthError(TradingError):
    """Ошибки аутентификации"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.AUTH_ERROR,
            context=context,
            original_exception=original_exception
        )

class DataError(TradingError):
    """Ошибки данных"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.DATA_ERROR,
            context=context,
            original_exception=original_exception
        )

class ValidationError(TradingError):
    """Ошибки валидации"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.VALIDATION_ERROR,
            context=context,
            original_exception=original_exception
        )

class ArbitrageError(TradingError):
    """Ошибки арбитража"""
    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            error_type=ErrorType.ARBITRAGE_ERROR,
            context=context,
            original_exception=original_exception
        )

# Функция-декоратор для обработки исключений
def handle_exceptions(error_type: ErrorType = ErrorType.UNKNOWN_ERROR):
    """
    Декоратор для обработки исключений в функциях и методах.
    
    Args:
        error_type: Тип ошибки для обработки
    
    Returns:
        Decorator: Декоратор для обработки исключений
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except TradingError as e:
                # Если это уже наша ошибка, просто перебрасываем
                raise
            except Exception as e:
                # Преобразуем в нашу ошибку
                context = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                raise TradingError(
                    message=str(e),
                    error_type=error_type,
                    context=context,
                    original_exception=e
                )
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except TradingError as e:
                # Если это уже наша ошибка, просто перебрасываем
                raise
            except Exception as e:
                # Преобразуем в нашу ошибку
                context = {
                    "function": func.__name__,
                    "args": str(args),
                    "kwargs": str(kwargs)
                }
                raise TradingError(
                    message=str(e),
                    error_type=error_type,
                    context=context,
                    original_exception=e
                )
        
        # Выбираем тип обертки в зависимости от типа функции
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Функция для глобальной обработки неперехваченных исключений
def setup_global_exception_handler():
    """
    Устанавливает глобальный обработчик исключений для перехвата 
    неожиданных ошибок на уровне приложения.
    """
    def handle_uncaught_exception(exc_type, exc_value, exc_traceback):
        """Функция-обработчик для неперехваченных исключений"""
        # Для обычных прерываний выполнения не делаем ничего
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        # Логируем неперехваченное исключение
        logger.critical(
            "Неперехваченное исключение",
            exc_info=(exc_type, exc_value, exc_traceback)
        )
    
    # Устанавливаем наш обработчик как глобальный
    sys.excepthook = handle_uncaught_exception
    
    # Для асинхронного кода нужно дополнительно настроить обработку
    import asyncio
    
    # В Python 3.8+ можно использовать set_exception_handler
    if hasattr(asyncio, "get_event_loop") and callable(getattr(asyncio, "get_event_loop", None)):
        loop = asyncio.get_event_loop()
        
        def async_exception_handler(loop, context):
            """Обработчик исключений для асинхронного кода"""
            # Получаем исключение из контекста
            exception = context.get("exception")
            
            if exception:
                # Логируем исключение
                logger.critical(
                    f"Неперехваченное асинхронное исключение: {str(exception)}",
                    exc_info=exception
                )
            else:
                # Если нет исключения, логируем контекст
                logger.critical(f"Асинхронная ошибка: {context}")
        
        # Устанавливаем обработчик
        loop.set_exception_handler(async_exception_handler)

# Инициализация модуля
def init_error_handler():
    """
    Инициализирует обработчик ошибок при запуске приложения.
    """
    # Устанавливаем глобальный обработчик исключений
    setup_global_exception_handler()
    
    logger.info("Обработчик ошибок инициализирован успешно")
    
    return True 