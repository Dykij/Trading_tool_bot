"""
Обработчики команд Telegram бота.

Этот модуль содержит обработчики команд, которые пользователи
могут отправлять в Telegram бот.
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from aiogram import Dispatcher, types
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command

# Импортируем декоратор для отслеживания команд
try:
    from src.telegram.decorators import track_command
    logger = logging.getLogger(__name__)
    logger.info("Декоратор track_command успешно импортирован")
except ImportError:
    # Если decorator не удалось импортировать из модуля telegram, 
    # создаем пустой декоратор, который не будет мешать работе
    logger = logging.getLogger(__name__)
    logger.error("Не удалось импортировать track_command из src.telegram.decorators")
    
    def track_command(func):
        """Заглушка декоратора track_command"""
        logger.warning(f"Используется заглушка декоратора track_command для {func.__name__}")
        return func
except Exception as e:
    # Обрабатываем любые другие ошибки при импорте или использовании декоратора
    logger = logging.getLogger(__name__)
    logger.error(f"Произошла ошибка с декоратором track_command: {e}")
    
    def track_command(func):
        """Заглушка декоратора track_command из-за ошибки"""
        logger.warning(f"Используется заглушка декоратора track_command для {func.__name__} из-за ошибки: {e}")
        return func

# Импортируем клавиатуры
from src.telegram.keyboards import (
    get_main_keyboard,
    get_menu_kb,
    get_cancel_kb,
    get_game_selection_keyboard,
    get_settings_keyboard,
    get_arbitrage_mode_keyboard
)

logger = logging.getLogger(__name__)

@track_command
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start.
    
    Args:
        message (types.Message): Сообщение от пользователя
        state (FSMContext): Состояние пользователя
    """
    try:
        # Проверяем, валидно ли сообщение
        if not message:
            logger.error("Получен пустой объект message в cmd_start")
            return
            
        # Завершаем текущее состояние пользователя
        await state.finish()
        
        # Получаем имя пользователя с проверкой
        user_name = message.from_user.first_name if hasattr(message, 'from_user') and hasattr(message.from_user, 'first_name') else "пользователь"
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        
        # Проверяем, новый ли это пользователь (это можно сделать через базу данных,
        # но для примера просто отправляем одинаковый ответ всем)
        logger.info(f"Пользователь {user_id} запустил команду /start")
        
        # Отправляем приветственное сообщение
        await message.answer(
            f"👋 Здравствуйте, {user_name}!\n\n"
            f"Это бот для работы с DMarket Trading.\n"
            f"Используйте /help, чтобы узнать доступные команды.",
            reply_markup=get_menu_kb()
        )
    except Exception as e:
        # Логируем ошибку
        logger.error(f"Ошибка при обработке команды /start: {str(e)}", exc_info=True)
        
        # Пытаемся отправить сообщение об ошибке
        try:
            if message and hasattr(message, 'answer'):
                await message.answer(
                    "Произошла ошибка при запуске бота. Пожалуйста, попробуйте позже или обратитесь к администратору."
                )
        except Exception as reply_error:
            logger.error(f"Не удалось отправить сообщение об ошибке: {reply_error}", exc_info=True)

@track_command
async def cmd_help(message: types.Message):
    """
    Обработчик команды /help.
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        help_text = (
            "📋 Доступные команды:\n\n"
            "/start - Начать работу с ботом\n"
            "/help - Показать это сообщение\n"
            "/menu - Показать главное меню\n"
            "/settings - Настройки бота\n"
            "/status - Проверить статус торговых операций\n"
        )
        await message.answer(help_text)
        
        # Безопасное логирование
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        logger.info(f"Пользователь {user_id} выполнил команду /help")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /help: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при обработке команды. Попробуйте позже.")
        except Exception:
            logger.error("Не удалось отправить сообщение об ошибке", exc_info=True)

@track_command
async def cmd_menu(message: types.Message):
    """
    Обработчик команды /menu.
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        await message.answer(
            "Главное меню:",
            reply_markup=get_menu_kb()
        )
        
        # Безопасное логирование
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        logger.info(f"Пользователь {user_id} выполнил команду /menu")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /menu: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при показе меню. Попробуйте позже.")
        except Exception:
            logger.error("Не удалось отправить сообщение об ошибке", exc_info=True)

@track_command
async def cmd_settings(message: types.Message):
    """
    Обработчик команды /settings.
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        await message.answer(
            "Настройки бота:",
            reply_markup=get_settings_keyboard()
        )
        
        # Безопасное логирование
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        logger.info(f"Пользователь {user_id} выполнил команду /settings")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /settings: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при показе настроек. Попробуйте позже.")
        except Exception:
            logger.error("Не удалось отправить сообщение об ошибке", exc_info=True)

@track_command
async def cmd_status(message: types.Message):
    """
    Обработчик команды /status.
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        # Здесь будет логика получения статуса торговых операций
        await message.answer(
            "🔄 Статус торговых операций:\n\n"
            "Система активна и работает нормально."
        )
        
        # Безопасное логирование
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        logger.info(f"Пользователь {user_id} выполнил команду /status")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /status: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при получении статуса. Попробуйте позже.")
        except Exception:
            logger.error("Не удалось отправить сообщение об ошибке", exc_info=True)

@track_command
async def cmd_arbitrage(message: types.Message):
    """
    Обработчик команды /arbitrage.
    Показывает меню выбора режима арбитража.
    
    Args:
        message (types.Message): Сообщение от пользователя
    """
    try:
        await message.answer(
            "🎯 <b>Арбитраж DMarket</b>\n\n"
            "Выберите режим работы:",
            parse_mode="HTML",
            reply_markup=get_arbitrage_mode_keyboard()
        )
        
        # Безопасное логирование
        user_id = message.from_user.id if hasattr(message, 'from_user') and hasattr(message.from_user, 'id') else "unknown"
        logger.info(f"Пользователь {user_id} выполнил команду /arbitrage")
    except Exception as e:
        logger.error(f"Ошибка при обработке команды /arbitrage: {str(e)}", exc_info=True)
        try:
            await message.answer("Произошла ошибка при показе меню арбитража. Попробуйте позже.")
        except Exception:
            logger.error("Не удалось отправить сообщение об ошибке", exc_info=True)

def register_command_handlers(dp: Dispatcher):
    """
    Регистрирует обработчики команд в диспетчере.
    
    Args:
        dp (Dispatcher): Диспетчер бота
    """
    # Регистрируем обработчик cmd_start с высоким приоритетом
    dp.register_message_handler(cmd_start, Command('start'), state='*')
    dp.register_message_handler(cmd_help, Command('help'))
    dp.register_message_handler(cmd_menu, Command('menu'))
    dp.register_message_handler(cmd_settings, Command('settings'))
    dp.register_message_handler(cmd_status, Command('status'))
    dp.register_message_handler(cmd_arbitrage, Command('arbitrage'))
    
    logger.info("Обработчики команд зарегистрированы")
    return dp 