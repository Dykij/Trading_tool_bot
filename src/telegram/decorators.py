"""
Модуль содержит декораторы для функций и обработчиков Telegram-бота.
"""

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Ссылка на объект метрик, будет установлена при инициализации бота
_bot_metrics = None

def set_metrics(metrics):
    """Устанавливает объект метрик, который будет использоваться декораторами"""
    global _bot_metrics
    _bot_metrics = metrics
    logger.info("Метрики успешно установлены в декораторах")

# Декоратор для сбора метрик команд
def track_command(handler):
    """Декоратор для отслеживания вызовов команд"""
    async def wrapper(message, *args, **kwargs):
        try:
            # Если метрики не инициализированы, просто выполняем обработчик
            if _bot_metrics is None:
                logger.warning(f"Метрики не инициализированы при выполнении track_command для {handler.__name__}")
                return await handler(message, *args, **kwargs)
                
            user_id = message.from_user.id if hasattr(message, 'from_user') else 'unknown'
            command = message.text if hasattr(message, 'text') else 'unknown'
            _bot_metrics.log_command(user_id, command)
            logger.info(f"Выполнение команды: {command} от пользователя {user_id}")
            
            # Вызываем оригинальный обработчик
            return await handler(message, *args, **kwargs)
        except Exception as e:
            # Логируем ошибку, но не пытаемся обращаться к message.from_user.id,
            # так как оно может быть недоступно из-за исключения
            logger.error(f"Ошибка при обработке команды: {str(e)}", exc_info=True)
            if _bot_metrics:
                _bot_metrics.log_error()
            
            # Если возможно, отправляем пользователю сообщение об ошибке
            try:
                if hasattr(message, 'answer'):
                    await message.answer("Произошла ошибка при обработке команды. Попробуйте позже или обратитесь к администратору.")
            except Exception:
                logger.error("Не удалось отправить сообщение об ошибке пользователю", exc_info=True)
            
            # Повторно вызываем исключение для дальнейшей обработки
            raise
    return wrapper

# Декоратор для сбора метрик колбэков
def track_callback(handler):
    """Декоратор для отслеживания колбэков"""
    async def wrapper(callback_query, *args, **kwargs):
        try:
            # Если метрики не инициализированы, просто выполняем обработчик
            if _bot_metrics is None:
                logger.warning(f"Метрики не инициализированы при выполнении track_callback для {handler.__name__}")
                return await handler(callback_query, *args, **kwargs)
                
            user_id = callback_query.from_user.id if hasattr(callback_query, 'from_user') else 'unknown'
            callback_data = callback_query.data if hasattr(callback_query, 'data') else 'unknown'
            _bot_metrics.log_callback(user_id, callback_data)
            logger.info(f"Обработка callback: {callback_data} от пользователя {user_id}")
            
            # Вызываем оригинальный обработчик
            return await handler(callback_query, *args, **kwargs)
        except Exception as e:
            # Логируем ошибку
            logger.error(f"Ошибка при обработке callback: {str(e)}", exc_info=True)
            if _bot_metrics:
                _bot_metrics.log_error()
            
            # Пытаемся ответить на callback
            try:
                if hasattr(callback_query, 'answer'):
                    await callback_query.answer("Произошла ошибка при обработке запроса.")
            except Exception:
                logger.error("Не удалось отправить ответ о колбэк-ошибке", exc_info=True)
            
            # Повторно вызываем исключение
            raise
    return wrapper 