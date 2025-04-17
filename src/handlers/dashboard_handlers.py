"""
Обработчики для аналитической панели (дашборда) в Telegram боте.

Предоставляет команды и обработчики для отображения аналитики и
статистики в интерфейсе Telegram бота.
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Union, Optional
from datetime import datetime, timedelta

# aiogram импорты
try:
    # Проверяем версию aiogram
    import pkg_resources
    AIOGRAM_VERSION = pkg_resources.get_distribution("aiogram").version
    IS_AIOGRAM_V2 = AIOGRAM_VERSION.startswith('2')
    
    if IS_AIOGRAM_V2:
        # Импорты для aiogram v2.x
        from aiogram import Bot, Dispatcher, types
        from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.callback_data import CallbackData
        from aiogram.dispatcher import FSMContext
        from aiogram.dispatcher.filters.state import State, StatesGroup
    else:
        # Импорты для aiogram v3.x
        from aiogram import Bot, Dispatcher, F, types
        from aiogram.types import ParseMode, InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.utils.keyboard import InlineKeyboardBuilder
        from aiogram.filters import Command
        from aiogram.fsm.context import FSMContext
        from aiogram.fsm.state import State, StatesGroup
except ImportError as e:
    print(f"Ошибка при импорте aiogram: {e}")
    raise

from utils.dashboard import dashboard_generator
from utils.logging_config import setup_logger

# Настройка логирования
logger = setup_logger(__name__)

# Callback data для обработки интерактивных кнопок
if IS_AIOGRAM_V2:
    dashboard_callback = CallbackData("dashboard", "action", "param")
else:
    # В aiogram v3 мы будем использовать константы и парсить callback_data вручную
    DASHBOARD_PREFIX = "dashboard:"

# Состояния для работы с дашбордом
class DashboardState(StatesGroup):
    waiting_for_period = State()  # Ожидание выбора периода
    waiting_for_report_type = State()  # Ожидание выбора типа отчета
    waiting_for_custom_days = State()  # Ожидание ввода пользовательского количества дней

async def get_dashboard_keyboard() -> Union[InlineKeyboardMarkup, 'InlineKeyboardBuilder']:
    """
    Создает клавиатуру для дашборда.
    
    Returns:
        Клавиатура с кнопками для дашборда
    """
    if IS_AIOGRAM_V2:
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Основные отчеты
        keyboard.add(
            InlineKeyboardButton("📊 Общая статистика", callback_data=dashboard_callback.new(action="overview", param="")),
            InlineKeyboardButton("💰 Торговые операции", callback_data=dashboard_callback.new(action="trading", param="7"))
        )
        
        # Графики и топы
        keyboard.add(
            InlineKeyboardButton("📈 График прибыли", callback_data=dashboard_callback.new(action="profit_chart", param="30")),
            InlineKeyboardButton("🏆 Топ предметов", callback_data=dashboard_callback.new(action="top_items", param="30"))
        )
        
        # Детальные отчеты
        keyboard.add(
            InlineKeyboardButton("⚙️ Системные метрики", callback_data=dashboard_callback.new(action="system", param="")),
            InlineKeyboardButton("🔄 Арбитраж", callback_data=dashboard_callback.new(action="arbitrage", param="7"))
        )
        
        # Периоды
        keyboard.add(
            InlineKeyboardButton("7 дней", callback_data=dashboard_callback.new(action="set_period", param="7")),
            InlineKeyboardButton("30 дней", callback_data=dashboard_callback.new(action="set_period", param="30")),
            InlineKeyboardButton("90 дней", callback_data=dashboard_callback.new(action="set_period", param="90"))
        )
        
        # Обновление и возврат
        keyboard.add(
            InlineKeyboardButton("🔄 Обновить данные", callback_data=dashboard_callback.new(action="refresh", param="")),
            InlineKeyboardButton("« Назад", callback_data="back_to_main")
        )
        
        return keyboard
    else:
        # Для aiogram v3
        builder = InlineKeyboardBuilder()
        
        # Основные отчеты
        builder.row(
            InlineKeyboardButton(text="📊 Общая статистика", callback_data=f"{DASHBOARD_PREFIX}overview:"),
            InlineKeyboardButton(text="💰 Торговые операции", callback_data=f"{DASHBOARD_PREFIX}trading:7")
        )
        
        # Графики и топы
        builder.row(
            InlineKeyboardButton(text="📈 График прибыли", callback_data=f"{DASHBOARD_PREFIX}profit_chart:30"),
            InlineKeyboardButton(text="🏆 Топ предметов", callback_data=f"{DASHBOARD_PREFIX}top_items:30")
        )
        
        # Детальные отчеты
        builder.row(
            InlineKeyboardButton(text="⚙️ Системные метрики", callback_data=f"{DASHBOARD_PREFIX}system:"),
            InlineKeyboardButton(text="🔄 Арбитраж", callback_data=f"{DASHBOARD_PREFIX}arbitrage:7")
        )
        
        # Периоды
        builder.row(
            InlineKeyboardButton(text="7 дней", callback_data=f"{DASHBOARD_PREFIX}set_period:7"),
            InlineKeyboardButton(text="30 дней", callback_data=f"{DASHBOARD_PREFIX}set_period:30"),
            InlineKeyboardButton(text="90 дней", callback_data=f"{DASHBOARD_PREFIX}set_period:90")
        )
        
        # Обновление и возврат
        builder.row(
            InlineKeyboardButton(text="🔄 Обновить данные", callback_data=f"{DASHBOARD_PREFIX}refresh:"),
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        )
        
        return builder.as_markup()

async def cmd_dashboard(message: Union[types.Message, types.CallbackQuery], state: Optional[FSMContext] = None):
    """
    Обрабатывает команду /dashboard.
    
    Args:
        message: Сообщение или колбэк
        state: Состояние FSM (опционально)
    """
    if isinstance(message, types.CallbackQuery):
        # Если вызвано через callback_query
        message = message.message
        await message.edit_text(
            "🔍 <b>Аналитическая панель DMarket Bot</b>\n\n"
            "Выберите опцию для просмотра данных:",
            reply_markup=await get_dashboard_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        # Если вызвано через команду
        await message.answer(
            "🔍 <b>Аналитическая панель DMarket Bot</b>\n\n"
            "Выберите опцию для просмотра данных:",
            reply_markup=await get_dashboard_keyboard(),
            parse_mode=ParseMode.HTML
        )

async def process_dashboard_callback(callback_query: types.CallbackQuery, action: str, param: str, state: Optional[FSMContext] = None):
    """
    Обрабатывает нажатия кнопок дашборда.
    
    Args:
        callback_query: Callback Query
        action: Действие (overview, trading, profit_chart и т.д.)
        param: Параметр (например, период в днях)
        state: Состояние FSM (опционально)
    """
    # Отображаем индикатор загрузки
    await callback_query.answer("Загрузка данных...")
    
    if action == "overview":
        # Общий обзор
        await show_dashboard_overview(callback_query)
    
    elif action == "trading":
        # Торговые операции
        days = int(param) if param else 7
        await show_trading_statistics(callback_query, days)
    
    elif action == "profit_chart":
        # График прибыли
        days = int(param) if param else 30
        await show_profit_chart(callback_query, days)
    
    elif action == "top_items":
        # Топ предметов
        days = int(param) if param else 30
        await show_top_items(callback_query, days)
    
    elif action == "system":
        # Системные метрики
        await show_system_metrics(callback_query)
    
    elif action == "arbitrage":
        # Метрики арбитража
        days = int(param) if param else 7
        await show_arbitrage_metrics(callback_query, days)
    
    elif action == "set_period":
        # Установка периода
        if state:
            # Сохраняем выбранный период в состоянии
            async def set_state_data(state_obj, key, value):
                if IS_AIOGRAM_V2:
                    await state_obj.update_data({key: value})
                else:
                    await state_obj.update_data({key: value})
            
            await set_state_data(state, "period", int(param))
            await callback_query.answer(f"Установлен период: {param} дней")
    
    elif action == "refresh":
        # Обновление данных
        dashboard_generator.invalidate_cache()
        await callback_query.answer("Данные обновлены")
        
        # Возвращаемся к главному меню дашборда
        await cmd_dashboard(callback_query)

async def show_dashboard_overview(callback_query: types.CallbackQuery):
    """
    Показывает общий обзор дашборда.
    
    Args:
        callback_query: Callback Query
    """
    # Получаем обзор системы
    system_data = await dashboard_generator.get_system_overview()
    
    # Получаем торговую статистику за 7 дней
    trading_data = await dashboard_generator.get_trading_statistics(days=7)
    
    # Формируем текст сообщения
    message_text = (
        "📊 <b>Обзор системы DMarket Bot</b>\n\n"
        f"<b>Системные ресурсы:</b>\n"
        f"CPU: {system_data['system_metrics']['cpu_usage']['current']}% (средн. {system_data['system_metrics']['cpu_usage']['average']:.1f}%)\n"
        f"Память: {system_data['system_metrics']['memory_usage']['current_percent']:.1f}% "
        f"({system_data['system_metrics']['memory_usage']['current_mb']:.1f} МБ)\n"
        f"Диск: {system_data['system_metrics']['disk_usage']:.1f}%\n\n"
        
        f"<b>API метрики:</b>\n"
        f"Всего вызовов: {system_data['api_metrics']['total_calls']}\n"
        f"Успешность: {system_data['api_metrics']['success_rate']:.1f}%\n"
        f"Среднее время ответа: {system_data['api_metrics']['avg_response_time']:.3f} сек\n"
        f"Запросов в минуту: {system_data['api_metrics']['calls_per_minute']:.1f}\n\n"
        
        f"<b>Торговая статистика (7 дней):</b>\n"
        f"Всего операций: {trading_data['total_operations']}\n"
        f"Успешных: {trading_data['successful_operations']} ({trading_data['success_rate']:.1f}%)\n"
        f"Общая прибыль: ${trading_data['total_profit']:.2f}\n"
        f"Средняя прибыль: ${trading_data['avg_profit_per_operation']:.2f}/операция\n\n"
        
        f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
    )
    
    # Отправляем сообщение с клавиатурой
    await callback_query.message.edit_text(
        message_text,
        reply_markup=await get_dashboard_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def show_trading_statistics(callback_query: types.CallbackQuery, days: int = 7):
    """
    Показывает статистику торговых операций.
    
    Args:
        callback_query: Callback Query
        days: Количество дней для анализа
    """
    # Получаем торговую статистику
    trading_data = await dashboard_generator.get_trading_statistics(days=days)
    
    # Если данных нет
    if trading_data.get("total_operations", 0) == 0:
        message_text = (
            f"📈 <b>Торговая статистика ({days} дней)</b>\n\n"
            "За выбранный период не найдено торговых операций."
        )
    else:
        # Формируем текст с операциями по дням
        days_summary = ""
        for day, count in sorted(trading_data.get("operations_by_day", {}).items()):
            days_summary += f"{day}: {count} операций\n"
        
        # Формируем текст с операциями по типам
        types_summary = ""
        for op_type, count in trading_data.get("operations_by_type", {}).items():
            types_summary += f"{op_type}: {count} операций\n"
        
        # Формируем текст сообщения
        message_text = (
            f"📈 <b>Торговая статистика ({days} дней)</b>\n\n"
            f"<b>Общие показатели:</b>\n"
            f"Всего операций: {trading_data['total_operations']}\n"
            f"Успешных: {trading_data['successful_operations']} ({trading_data['success_rate']:.1f}%)\n"
            f"Неудачных: {trading_data['failed_operations']}\n"
            f"Общая прибыль: ${trading_data['total_profit']:.2f}\n"
            f"Средняя прибыль: ${trading_data['avg_profit_per_operation']:.2f}/операция\n\n"
            
            f"<b>Операции по дням:</b>\n{days_summary}\n"
            f"<b>Операции по типам:</b>\n{types_summary}\n"
            
            f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
        )
    
    # Отправляем сообщение с клавиатурой
    await callback_query.message.edit_text(
        message_text,
        reply_markup=await get_dashboard_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def show_profit_chart(callback_query: types.CallbackQuery, days: int = 30):
    """
    Показывает график прибыли.
    
    Args:
        callback_query: Callback Query
        days: Количество дней для анализа
    """
    # Отправляем временное сообщение о генерации графика
    await callback_query.message.edit_text(
        f"⏳ Генерация графика прибыли за {days} дней...",
        parse_mode=ParseMode.HTML
    )
    
    # Генерируем график прибыли
    chart_buffer = await dashboard_generator.generate_profit_chart(days=days)
    
    # Отправляем изображение с графиком
    await callback_query.bot.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=chart_buffer,
        caption=f"📊 График прибыли за последние {days} дней"
    )
    
    # Восстанавливаем меню дашборда
    await cmd_dashboard(callback_query)

async def show_top_items(callback_query: types.CallbackQuery, days: int = 30):
    """
    Показывает топ предметов по прибыльности.
    
    Args:
        callback_query: Callback Query
        days: Количество дней для анализа
    """
    # Получаем данные о топ предметах
    top_items = await dashboard_generator.get_top_items(days=days, limit=10)
    
    # Если данных нет
    if not top_items:
        message_text = (
            f"🏆 <b>Топ предметов ({days} дней)</b>\n\n"
            "За выбранный период не найдено данных о предметах."
        )
    else:
        # Формируем текст со списком предметов
        items_list = ""
        for i, item in enumerate(top_items, 1):
            items_list += (
                f"{i}. <b>{item['item_name']}</b> ({item['game']})\n"
                f"   Прибыль: ${item['total_profit']:.2f} ({item['trades_count']} сделок)\n"
                f"   Средняя прибыль: ${item['avg_profit']:.2f}\n\n"
            )
        
        # Формируем текст сообщения
        message_text = (
            f"🏆 <b>Топ предметов по прибыльности ({days} дней)</b>\n\n"
            f"{items_list}"
            f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
        )
    
    # Отправляем сообщение с клавиатурой
    await callback_query.message.edit_text(
        message_text,
        reply_markup=await get_dashboard_keyboard(),
        parse_mode=ParseMode.HTML
    )

async def show_system_metrics(callback_query: types.CallbackQuery):
    """
    Показывает системные метрики.
    
    Args:
        callback_query: Callback Query
    """
    # Отправляем временное сообщение о генерации графика
    await callback_query.message.edit_text(
        "⏳ Генерация графика производительности...",
        parse_mode=ParseMode.HTML
    )
    
    # Генерируем график производительности
    chart_buffer = await dashboard_generator.generate_performance_chart()
    
    # Отправляем изображение с графиком
    await callback_query.bot.send_photo(
        chat_id=callback_query.message.chat.id,
        photo=chart_buffer,
        caption="📊 График производительности системы"
    )
    
    # Восстанавливаем меню дашборда
    await cmd_dashboard(callback_query)

async def show_arbitrage_metrics(callback_query: types.CallbackQuery, days: int = 7):
    """
    Показывает метрики арбитражных операций.
    
    Args:
        callback_query: Callback Query
        days: Количество дней для анализа
    """
    # Получаем метрики арбитража
    arbitrage_data = await dashboard_generator.get_arbitrage_metrics(days=days)
    
    # Формируем текст сообщения
    message_text = (
        f"🔄 <b>Метрики арбитража ({days} дней)</b>\n\n"
        f"<b>Общая статистика:</b>\n"
        f"Всего операций: {arbitrage_data['total_operations']}\n"
        f"Успешных: {arbitrage_data['success_operations']}\n"
        f"Ошибок: {arbitrage_data['error_operations']}\n"
        f"Успешность: {arbitrage_data['success_rate']:.1f}%\n"
        f"Среднее время операции: {arbitrage_data['avg_duration']:.3f} сек\n\n"
    )
    
    # Добавляем детали по типам метрик, если они есть
    if arbitrage_data.get('detailed_metrics'):
        message_text += "<b>Детальные метрики:</b>\n"
        for i, metric in enumerate(arbitrage_data['detailed_metrics'][:5], 1):  # Максимум 5 метрик
            message_text += (
                f"{i}. {metric.get('name', 'Unknown')}\n"
                f"   Запусков: {metric.get('total_count', 0)}\n"
                f"   Успешность: {100 - metric.get('error_rate', 0):.1f}%\n"
                f"   Среднее время: {metric.get('avg_duration', 0):.3f} сек\n\n"
            )
    
    message_text += f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
    
    # Отправляем сообщение с клавиатурой
    await callback_query.message.edit_text(
        message_text,
        reply_markup=await get_dashboard_keyboard(),
        parse_mode=ParseMode.HTML
    )

def register_dashboard_handlers(dp: Dispatcher):
    """
    Регистрирует обработчики команд дашборда.
    
    Args:
        dp: Диспетчер бота
    """
    if IS_AIOGRAM_V2:
        # Для aiogram v2
        dp.register_message_handler(cmd_dashboard, commands=["dashboard"])
        dp.register_callback_query_handler(
            lambda c, state: process_dashboard_callback(
                c, 
                dashboard_callback.parse(c.data)["action"], 
                dashboard_callback.parse(c.data)["param"],
                state
            ),
            lambda c: dashboard_callback.check(c.data)
        )
    else:
        # Для aiogram v3
        dp.message.register(cmd_dashboard, Command(commands=["dashboard"]))
        
        # Обработчик для callback_query
        async def process_v3_dashboard_callback(callback_query: types.CallbackQuery, state: FSMContext):
            if callback_query.data and callback_query.data.startswith(DASHBOARD_PREFIX):
                parts = callback_query.data[len(DASHBOARD_PREFIX):].split(":")
                action = parts[0]
                param = parts[1] if len(parts) > 1 else ""
                await process_dashboard_callback(callback_query, action, param, state)
        
        dp.callback_query.register(
            process_v3_dashboard_callback,
            lambda c: c.data and c.data.startswith(DASHBOARD_PREFIX)
        ) 