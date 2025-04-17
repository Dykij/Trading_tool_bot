"""
Обработчики для режима песочницы (sandbox) в Telegram боте.

Предоставляет команды и обработчики для тестирования торговых стратегий
в безопасном режиме без использования реальных средств.
"""

import os
import logging
import asyncio
import json
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

from utils.sandbox import sandbox
from utils.logging_config import setup_logger

# Настройка логирования
logger = setup_logger(__name__)

# Callback data для обработки интерактивных кнопок
if IS_AIOGRAM_V2:
    sandbox_callback = CallbackData("sandbox", "action", "param")
else:
    # В aiogram v3 мы будем использовать константы и парсить callback_data вручную
    SANDBOX_PREFIX = "sandbox:"

# Состояния для работы с режимом песочницы
class SandboxState(StatesGroup):
    waiting_for_balance = State()  # Ожидание ввода баланса
    waiting_for_item_id = State()  # Ожидание ввода ID предмета
    waiting_for_item_name = State()  # Ожидание ввода названия предмета
    waiting_for_price = State()  # Ожидание ввода цены
    waiting_for_quantity = State()  # Ожидание ввода количества
    waiting_for_days = State()  # Ожидание ввода количества дней
    waiting_for_speed = State()  # Ожидание ввода скорости симуляции
    waiting_for_volatility = State()  # Ожидание ввода волатильности

async def get_sandbox_keyboard() -> Union[InlineKeyboardMarkup, 'InlineKeyboardBuilder']:
    """
    Создает клавиатуру для режима песочницы.
    
    Returns:
        Клавиатура с кнопками для управления песочницей
    """
    if IS_AIOGRAM_V2:
        keyboard = InlineKeyboardMarkup(row_width=2)
        
        # Статус и управление
        if sandbox.is_active:
            keyboard.add(
                InlineKeyboardButton("🟢 Режим активен", callback_data=sandbox_callback.new(action="status", param="")),
                InlineKeyboardButton("🔴 Деактивировать", callback_data=sandbox_callback.new(action="deactivate", param=""))
            )
        else:
            keyboard.add(
                InlineKeyboardButton("🔴 Режим неактивен", callback_data=sandbox_callback.new(action="status", param="")),
                InlineKeyboardButton("🟢 Активировать", callback_data=sandbox_callback.new(action="activate", param=""))
            )
        
        # Симуляция
        if sandbox.simulation_active:
            keyboard.add(
                InlineKeyboardButton("⏹️ Остановить симуляцию", callback_data=sandbox_callback.new(action="stop_simulation", param=""))
            )
        else:
            keyboard.add(
                InlineKeyboardButton("▶️ Запустить симуляцию", callback_data=sandbox_callback.new(action="start_simulation", param=""))
            )
        
        # Операции
        keyboard.add(
            InlineKeyboardButton("💲 Купить предмет", callback_data=sandbox_callback.new(action="buy", param="")),
            InlineKeyboardButton("💱 Продать предмет", callback_data=sandbox_callback.new(action="sell", param=""))
        )
        
        # Информация
        keyboard.add(
            InlineKeyboardButton("💰 Баланс и инвентарь", callback_data=sandbox_callback.new(action="info", param="")),
            InlineKeyboardButton("📊 Отчет", callback_data=sandbox_callback.new(action="report", param=""))
        )
        
        # Настройки
        keyboard.add(
            InlineKeyboardButton("⚙️ Настройки", callback_data=sandbox_callback.new(action="settings", param="")),
            InlineKeyboardButton("🔄 Сброс", callback_data=sandbox_callback.new(action="reset", param=""))
        )
        
        # Возврат в главное меню
        keyboard.add(
            InlineKeyboardButton("« Назад", callback_data="back_to_main")
        )
        
        return keyboard
    else:
        # Для aiogram v3
        builder = InlineKeyboardBuilder()
        
        # Статус и управление
        if sandbox.is_active:
            builder.row(
                InlineKeyboardButton(text="🟢 Режим активен", callback_data=f"{SANDBOX_PREFIX}status:"),
                InlineKeyboardButton(text="🔴 Деактивировать", callback_data=f"{SANDBOX_PREFIX}deactivate:")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="🔴 Режим неактивен", callback_data=f"{SANDBOX_PREFIX}status:"),
                InlineKeyboardButton(text="🟢 Активировать", callback_data=f"{SANDBOX_PREFIX}activate:")
            )
        
        # Симуляция
        if sandbox.simulation_active:
            builder.row(
                InlineKeyboardButton(text="⏹️ Остановить симуляцию", callback_data=f"{SANDBOX_PREFIX}stop_simulation:")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="▶️ Запустить симуляцию", callback_data=f"{SANDBOX_PREFIX}start_simulation:")
            )
        
        # Операции
        builder.row(
            InlineKeyboardButton(text="💲 Купить предмет", callback_data=f"{SANDBOX_PREFIX}buy:"),
            InlineKeyboardButton(text="💱 Продать предмет", callback_data=f"{SANDBOX_PREFIX}sell:")
        )
        
        # Информация
        builder.row(
            InlineKeyboardButton(text="💰 Баланс и инвентарь", callback_data=f"{SANDBOX_PREFIX}info:"),
            InlineKeyboardButton(text="📊 Отчет", callback_data=f"{SANDBOX_PREFIX}report:")
        )
        
        # Настройки
        builder.row(
            InlineKeyboardButton(text="⚙️ Настройки", callback_data=f"{SANDBOX_PREFIX}settings:"),
            InlineKeyboardButton(text="🔄 Сброс", callback_data=f"{SANDBOX_PREFIX}reset:")
        )
        
        # Возврат в главное меню
        builder.row(
            InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
        )
        
        return builder.as_markup()

async def cmd_sandbox(message: Union[types.Message, types.CallbackQuery], state: Optional[FSMContext] = None):
    """
    Обрабатывает команду /sandbox.
    
    Args:
        message: Сообщение или колбэк
        state: Состояние FSM (опционально)
    """
    # Формируем информационный текст
    status_text = "🟢 Активен" if sandbox.is_active else "🔴 Неактивен"
    simulation_text = "▶️ Запущена" if sandbox.simulation_active else "⏹️ Остановлена"
    
    if sandbox.is_active:
        balance_text = f"${sandbox.virtual_balance:.2f}"
        items_count = len(sandbox.virtual_inventory)
        items_text = f"{items_count} предметов"
    else:
        balance_text = "N/A"
        items_text = "N/A"
    
    info_text = (
        "🎮 <b>Режим песочницы (Sandbox)</b>\n\n"
        "Тестируйте торговые стратегии без риска потери реальных средств.\n\n"
        f"<b>Статус:</b> {status_text}\n"
        f"<b>Симуляция:</b> {simulation_text}\n"
        f"<b>Баланс:</b> {balance_text}\n"
        f"<b>Инвентарь:</b> {items_text}\n\n"
        "Выберите действие:"
    )
    
    if isinstance(message, types.CallbackQuery):
        # Если вызвано через callback_query
        message = message.message
        await message.edit_text(
            info_text,
            reply_markup=await get_sandbox_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        # Если вызвано через команду
        await message.answer(
            info_text,
            reply_markup=await get_sandbox_keyboard(),
            parse_mode=ParseMode.HTML
        )

async def process_sandbox_callback(callback_query: types.CallbackQuery, action: str, param: str, state: Optional[FSMContext] = None):
    """
    Обрабатывает нажатия кнопок в режиме песочницы.
    
    Args:
        callback_query: Callback Query
        action: Действие (activate, deactivate, buy, sell и т.д.)
        param: Параметр (если есть)
        state: Состояние FSM (опционально)
    """
    # Обработка действий
    if action == "status":
        # Просто показываем текущий статус
        await callback_query.answer(
            f"Статус песочницы: {'Активна' if sandbox.is_active else 'Неактивна'}"
        )
    
    elif action == "activate":
        # Запрашиваем начальный баланс
        if state:
            async def set_state(state_obj, state_value):
                if IS_AIOGRAM_V2:
                    await state_obj.set_state(state_value)
                else:
                    await state_obj.set_state(state_value)
            
            await callback_query.message.edit_text(
                "💰 Введите начальный баланс для режима песочницы (в USD):",
                parse_mode=ParseMode.HTML
            )
            await set_state(state, SandboxState.waiting_for_balance)
        else:
            # Если нет state, активируем с балансом по умолчанию
            sandbox.activate()
            await cmd_sandbox(callback_query)
    
    elif action == "deactivate":
        # Деактивируем режим песочницы
        sandbox.deactivate()
        await callback_query.answer("Режим песочницы деактивирован")
        await cmd_sandbox(callback_query)
    
    elif action == "start_simulation":
        # Запрашиваем параметры симуляции
        if state:
            async def set_state(state_obj, state_value):
                if IS_AIOGRAM_V2:
                    await state_obj.set_state(state_value)
                else:
                    await state_obj.set_state(state_value)
            
            await callback_query.message.edit_text(
                "⏱️ Введите количество дней назад для начала симуляции (например, 30):",
                parse_mode=ParseMode.HTML
            )
            await set_state(state, SandboxState.waiting_for_days)
        else:
            # Если нет state, запускаем с параметрами по умолчанию
            result = sandbox.start_simulation()
            await callback_query.answer(
                f"Симуляция {'запущена' if result.get('success', False) else 'не запущена: ' + result.get('error', '')}"
            )
            await cmd_sandbox(callback_query)
    
    elif action == "stop_simulation":
        # Останавливаем симуляцию
        result = sandbox.stop_simulation()
        if result.get("success", False):
            profit_text = f"Итоговая прибыль: ${result.get('total_profit', 0):.2f}"
            await callback_query.answer(f"Симуляция остановлена. {profit_text}")
        else:
            await callback_query.answer(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        await cmd_sandbox(callback_query)
    
    elif action == "buy":
        # Запрашиваем данные для покупки
        if state and sandbox.is_active:
            async def set_state(state_obj, state_value):
                if IS_AIOGRAM_V2:
                    await state_obj.set_state(state_value)
                else:
                    await state_obj.set_state(state_value)
            
            await callback_query.message.edit_text(
                "🏷️ Введите ID предмета для покупки:",
                parse_mode=ParseMode.HTML
            )
            await set_state(state, SandboxState.waiting_for_item_id)
        else:
            await callback_query.answer("Режим песочницы должен быть активирован")
            await cmd_sandbox(callback_query)
    
    elif action == "sell":
        # Показываем инвентарь для выбора предмета для продажи
        if not sandbox.is_active:
            await callback_query.answer("Режим песочницы должен быть активирован")
            await cmd_sandbox(callback_query)
            return
        
        inventory = sandbox.get_inventory()
        if not inventory:
            await callback_query.answer("Инвентарь пуст. Сначала купите предметы.")
            await cmd_sandbox(callback_query)
            return
        
        # Создаем клавиатуру с предметами из инвентаря
        if IS_AIOGRAM_V2:
            keyboard = InlineKeyboardMarkup(row_width=1)
            for item in inventory:
                keyboard.add(
                    InlineKeyboardButton(
                        f"{item['item_name']} (${item['current_price']:.2f})",
                        callback_data=sandbox_callback.new(action="select_sell", param=item['item_id'])
                    )
                )
            keyboard.add(
                InlineKeyboardButton("« Назад", callback_data=sandbox_callback.new(action="back", param=""))
            )
        else:
            builder = InlineKeyboardBuilder()
            for item in inventory:
                builder.row(
                    InlineKeyboardButton(
                        text=f"{item['item_name']} (${item['current_price']:.2f})",
                        callback_data=f"{SANDBOX_PREFIX}select_sell:{item['item_id']}"
                    )
                )
            builder.row(
                InlineKeyboardButton(text="« Назад", callback_data=f"{SANDBOX_PREFIX}back:")
            )
            keyboard = builder.as_markup()
        
        await callback_query.message.edit_text(
            "🛒 <b>Выберите предмет для продажи:</b>",
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    elif action == "select_sell":
        # Выбран предмет для продажи
        if not sandbox.is_active:
            await callback_query.answer("Режим песочницы должен быть активирован")
            await cmd_sandbox(callback_query)
            return
        
        # Находим предмет в инвентаре
        item_id = param
        inventory = sandbox.get_inventory()
        item = next((item for item in inventory if item["item_id"] == item_id), None)
        
        if not item:
            await callback_query.answer("Предмет не найден в инвентаре")
            await cmd_sandbox(callback_query)
            return
        
        # Запрашиваем цену продажи
        if state:
            async def set_state_data(state_obj, key, value):
                if IS_AIOGRAM_V2:
                    await state_obj.update_data({key: value})
                else:
                    await state_obj.update_data({key: value})
            
            async def set_state(state_obj, state_value):
                if IS_AIOGRAM_V2:
                    await state_obj.set_state(state_value)
                else:
                    await state_obj.set_state(state_value)
            
            # Сохраняем ID предмета в состоянии
            await set_state_data(state, "item_id", item_id)
            await set_state_data(state, "current_price", item["current_price"])
            
            await callback_query.message.edit_text(
                f"💰 Введите цену продажи для предмета <b>{item['item_name']}</b>:\n\n"
                f"Текущая цена: ${item['current_price']:.2f}\n"
                f"Цена покупки: ${item['purchase_price']:.2f}",
                parse_mode=ParseMode.HTML
            )
            await set_state(state, SandboxState.waiting_for_price)
        else:
            # Если нет state, используем текущую цену
            result = await sandbox.sell_item(item_id, item["current_price"])
            if result.get("success", False):
                await callback_query.answer(f"Продано! Прибыль: ${result.get('profit', 0):.2f}")
            else:
                await callback_query.answer(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            await cmd_sandbox(callback_query)
    
    elif action == "info":
        # Показываем информацию о балансе и инвентаре
        if not sandbox.is_active:
            await callback_query.answer("Режим песочницы должен быть активирован")
            await cmd_sandbox(callback_query)
            return
        
        # Получаем данные
        balance = sandbox.get_balance()
        inventory = sandbox.get_inventory()
        total_inventory_value = sum(item.get("current_price", 0) for item in inventory)
        
        # Формируем текст с информацией об инвентаре
        inventory_text = ""
        for i, item in enumerate(inventory, 1):
            current_price = item.get("current_price", 0)
            purchase_price = item.get("purchase_price", 0)
            profit = current_price - purchase_price
            profit_percent = (profit / purchase_price * 100) if purchase_price > 0 else 0
            
            inventory_text += (
                f"{i}. <b>{item.get('item_name', 'Unknown')}</b>\n"
                f"   Купл: ${purchase_price:.2f} | Текущ: ${current_price:.2f}\n"
                f"   Прибыль: ${profit:.2f} ({profit_percent:+.1f}%)\n\n"
            )
        
        if not inventory:
            inventory_text = "Инвентарь пуст"
        
        # Формируем сообщение
        message_text = (
            "💰 <b>Информация о песочнице</b>\n\n"
            f"<b>Баланс:</b> ${balance:.2f}\n"
            f"<b>Стоимость инвентаря:</b> ${total_inventory_value:.2f}\n"
            f"<b>Всего активов:</b> ${(balance + total_inventory_value):.2f}\n\n"
            f"<b>Инвентарь ({len(inventory)} предметов):</b>\n\n{inventory_text}"
        )
        
        # Отправляем сообщение с клавиатурой возврата
        if IS_AIOGRAM_V2:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("« Назад", callback_data=sandbox_callback.new(action="back", param=""))
            )
        else:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="« Назад", callback_data=f"{SANDBOX_PREFIX}back:")
            )
            keyboard = builder.as_markup()
        
        await callback_query.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    elif action == "report":
        # Показываем отчет по песочнице
        if not sandbox.is_active:
            await callback_query.answer("Режим песочницы должен быть активирован")
            await cmd_sandbox(callback_query)
            return
        
        # Генерируем отчет
        report = sandbox.generate_sandbox_report()
        
        # Формируем текст отчета
        message_text = (
            "📊 <b>Отчет по работе в песочнице</b>\n\n"
            f"<b>Баланс:</b> ${report['balance']:.2f}\n"
            f"<b>Стоимость инвентаря:</b> ${report['inventory_value']:.2f}\n"
            f"<b>Всего активов:</b> ${report['total_assets']:.2f}\n\n"
            
            f"<b>Транзакции:</b>\n"
            f"Всего: {report['transactions']['total']}\n"
            f"Покупки: {report['transactions']['buys']}\n"
            f"Продажи: {report['transactions']['sells']}\n\n"
            
            f"<b>Финансы:</b>\n"
            f"Общая прибыль: ${report['financial']['total_profit']:.2f}\n"
            f"Потрачено: ${report['financial']['total_spent']:.2f}\n"
            f"Получено: ${report['financial']['total_received']:.2f}\n"
            f"ROI: {report['financial']['roi_percent']:.1f}%\n"
            f"Комиссии: ${report['financial']['fees_paid']:.2f}\n\n"
            
            f"<b>Настройки симуляции:</b>\n"
            f"Скорость: {report['simulation_settings']['speed']}x\n"
            f"Волатильность: {report['simulation_settings']['volatility']*100:.1f}%\n"
            f"Комиссия: {report['simulation_settings']['transaction_fee']*100:.1f}%\n\n"
            
            f"Последнее обновление: {datetime.now().strftime('%H:%M:%S')}"
        )
        
        # Отправляем сообщение с клавиатурой возврата
        if IS_AIOGRAM_V2:
            keyboard = InlineKeyboardMarkup()
            keyboard.add(
                InlineKeyboardButton("« Назад", callback_data=sandbox_callback.new(action="back", param=""))
            )
        else:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="« Назад", callback_data=f"{SANDBOX_PREFIX}back:")
            )
            keyboard = builder.as_markup()
        
        await callback_query.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    elif action == "settings":
        # Показываем настройки симуляции
        if IS_AIOGRAM_V2:
            keyboard = InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                InlineKeyboardButton("🔄 Скорость симуляции", callback_data=sandbox_callback.new(action="set_speed", param="")),
                InlineKeyboardButton("📊 Волатильность", callback_data=sandbox_callback.new(action="set_volatility", param="")),
                InlineKeyboardButton("💸 Комиссия", callback_data=sandbox_callback.new(action="set_fee", param="")),
                InlineKeyboardButton("« Назад", callback_data=sandbox_callback.new(action="back", param=""))
            )
        else:
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔄 Скорость симуляции", callback_data=f"{SANDBOX_PREFIX}set_speed:"),
                InlineKeyboardButton(text="📊 Волатильность", callback_data=f"{SANDBOX_PREFIX}set_volatility:")
            )
            builder.row(
                InlineKeyboardButton(text="💸 Комиссия", callback_data=f"{SANDBOX_PREFIX}set_fee:"),
                InlineKeyboardButton(text="« Назад", callback_data=f"{SANDBOX_PREFIX}back:")
            )
            keyboard = builder.as_markup()
        
        message_text = (
            "⚙️ <b>Настройки симуляции</b>\n\n"
            f"<b>Текущие параметры:</b>\n"
            f"Скорость: {sandbox.simulation_speed}x\n"
            f"Волатильность: {sandbox.market_volatility*100:.1f}%\n"
            f"Комиссия: {sandbox.transaction_fee*100:.1f}%\n\n"
            "Выберите параметр для изменения:"
        )
        
        await callback_query.message.edit_text(
            message_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )
    
    elif action == "reset":
        # Сбрасываем состояние песочницы
        sandbox.reset()
        await callback_query.answer("Состояние песочницы сброшено")
        await cmd_sandbox(callback_query)
    
    elif action == "back":
        # Возвращаемся в главное меню песочницы
        await cmd_sandbox(callback_query)

# Обработчики состояний для ввода данных
async def process_sandbox_balance(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод начального баланса для песочницы.
    
    Args:
        message: Сообщение с балансом
        state: Состояние FSM
    """
    try:
        balance = float(message.text.strip())
        if balance <= 0:
            await message.reply("Баланс должен быть положительным числом. Попробуйте еще раз:")
            return
        
        # Активируем режим песочницы с указанным балансом
        sandbox.activate(initial_balance=balance)
        
        # Сбрасываем состояние
        if IS_AIOGRAM_V2:
            await state.finish()
        else:
            await state.clear()
        
        await message.reply(f"Режим песочницы активирован с балансом ${balance:.2f}")
        await cmd_sandbox(message)
        
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для баланса:")

async def process_sandbox_days(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод дней для симуляции.
    
    Args:
        message: Сообщение с количеством дней
        state: Состояние FSM
    """
    try:
        days = int(message.text.strip())
        if days <= 0:
            await message.reply("Количество дней должно быть положительным числом. Попробуйте еще раз:")
            return
        
        # Сохраняем в состоянии
        async def set_state_data(state_obj, key, value):
            if IS_AIOGRAM_V2:
                await state_obj.update_data({key: value})
            else:
                await state_obj.update_data({key: value})
        
        async def set_state(state_obj, state_value):
            if IS_AIOGRAM_V2:
                await state_obj.set_state(state_value)
            else:
                await state_obj.set_state(state_value)
        
        await set_state_data(state, "days", days)
        
        # Запрашиваем скорость симуляции
        await message.reply("🔄 Введите скорость симуляции (множитель, например 10):")
        await set_state(state, SandboxState.waiting_for_speed)
        
    except ValueError:
        await message.reply("Пожалуйста, введите корректное целое число для количества дней:")

async def process_sandbox_speed(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод скорости симуляции.
    
    Args:
        message: Сообщение со скоростью симуляции
        state: Состояние FSM
    """
    try:
        speed = float(message.text.strip())
        if speed <= 0:
            await message.reply("Скорость должна быть положительным числом. Попробуйте еще раз:")
            return
        
        # Получаем дни из состояния
        state_data = await state.get_data() if IS_AIOGRAM_V2 else await state.get_data()
        days = state_data.get("days", 30)
        
        # Запускаем симуляцию
        result = sandbox.start_simulation(days_ago=days, speed=speed)
        
        # Сбрасываем состояние
        if IS_AIOGRAM_V2:
            await state.finish()
        else:
            await state.clear()
        
        if result.get("success", False):
            await message.reply(f"Симуляция запущена! Начальная точка: {days} дней назад, скорость: {speed}x")
        else:
            await message.reply(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        await cmd_sandbox(message)
        
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для скорости симуляции:")

async def process_sandbox_item_id(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод ID предмета для покупки.
    
    Args:
        message: Сообщение с ID предмета
        state: Состояние FSM
    """
    item_id = message.text.strip()
    
    # Сохраняем в состоянии
    async def set_state_data(state_obj, key, value):
        if IS_AIOGRAM_V2:
            await state_obj.update_data({key: value})
        else:
            await state_obj.update_data({key: value})
    
    async def set_state(state_obj, state_value):
        if IS_AIOGRAM_V2:
            await state_obj.set_state(state_value)
        else:
            await state_obj.set_state(state_value)
    
    await set_state_data(state, "item_id", item_id)
    
    # Запрашиваем название предмета
    await message.reply("✏️ Введите название предмета:")
    await set_state(state, SandboxState.waiting_for_item_name)

async def process_sandbox_item_name(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод названия предмета для покупки.
    
    Args:
        message: Сообщение с названием предмета
        state: Состояние FSM
    """
    item_name = message.text.strip()
    
    # Сохраняем в состоянии
    async def set_state_data(state_obj, key, value):
        if IS_AIOGRAM_V2:
            await state_obj.update_data({key: value})
        else:
            await state_obj.update_data({key: value})
    
    async def set_state(state_obj, state_value):
        if IS_AIOGRAM_V2:
            await state_obj.set_state(state_value)
        else:
            await state_obj.set_state(state_value)
    
    await set_state_data(state, "item_name", item_name)
    
    # Запрашиваем цену предмета
    await message.reply("💰 Введите цену предмета (в USD):")
    await set_state(state, SandboxState.waiting_for_price)

async def process_sandbox_price(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод цены предмета.
    
    Args:
        message: Сообщение с ценой
        state: Состояние FSM
    """
    try:
        price = float(message.text.strip())
        if price <= 0:
            await message.reply("Цена должна быть положительным числом. Попробуйте еще раз:")
            return
        
        # Получаем данные из состояния
        state_data = await state.get_data() if IS_AIOGRAM_V2 else await state.get_data()
        
        # Проверяем, это покупка или продажа
        if "current_price" in state_data:
            # Это продажа
            item_id = state_data.get("item_id")
            
            # Выполняем продажу
            result = await sandbox.sell_item(item_id, price)
            
            # Сбрасываем состояние
            if IS_AIOGRAM_V2:
                await state.finish()
            else:
                await state.clear()
            
            if result.get("success", False):
                profit = result.get("profit", 0)
                profit_text = f"Прибыль: ${profit:.2f}"
                await message.reply(f"Предмет успешно продан! {profit_text}")
            else:
                await message.reply(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
            
            await cmd_sandbox(message)
            
        else:
            # Это покупка
            # Сохраняем в состоянии
            async def set_state_data(state_obj, key, value):
                if IS_AIOGRAM_V2:
                    await state_obj.update_data({key: value})
                else:
                    await state_obj.update_data({key: value})
            
            async def set_state(state_obj, state_value):
                if IS_AIOGRAM_V2:
                    await state_obj.set_state(state_value)
                else:
                    await state_obj.set_state(state_value)
            
            await set_state_data(state, "price", price)
            
            # Запрашиваем количество
            await message.reply("🔢 Введите количество предметов:")
            await set_state(state, SandboxState.waiting_for_quantity)
        
    except ValueError:
        await message.reply("Пожалуйста, введите корректное число для цены:")

async def process_sandbox_quantity(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод количества предметов для покупки.
    
    Args:
        message: Сообщение с количеством
        state: Состояние FSM
    """
    try:
        quantity = int(message.text.strip())
        if quantity <= 0:
            await message.reply("Количество должно быть положительным числом. Попробуйте еще раз:")
            return
        
        # Получаем данные из состояния
        state_data = await state.get_data() if IS_AIOGRAM_V2 else await state.get_data()
        item_id = state_data.get("item_id")
        item_name = state_data.get("item_name")
        price = state_data.get("price")
        
        # Выполняем покупку
        result = await sandbox.buy_item(item_id, item_name, price, quantity)
        
        # Сбрасываем состояние
        if IS_AIOGRAM_V2:
            await state.finish()
        else:
            await state.clear()
        
        if result.get("success", False):
            new_balance = result.get("new_balance", 0)
            await message.reply(f"Покупка успешно выполнена! Новый баланс: ${new_balance:.2f}")
        else:
            await message.reply(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        await cmd_sandbox(message)
        
    except ValueError:
        await message.reply("Пожалуйста, введите корректное целое число для количества:")

def register_sandbox_handlers(dp: Dispatcher):
    """
    Регистрирует обработчики команд режима песочницы.
    
    Args:
        dp: Диспетчер бота
    """
    if IS_AIOGRAM_V2:
        # Для aiogram v2
        dp.register_message_handler(cmd_sandbox, commands=["sandbox"])
        dp.register_callback_query_handler(
            lambda c, state: process_sandbox_callback(
                c, 
                sandbox_callback.parse(c.data)["action"], 
                sandbox_callback.parse(c.data)["param"],
                state
            ),
            lambda c: sandbox_callback.check(c.data)
        )
        
        # Обработчики состояний
        dp.register_message_handler(process_sandbox_balance, state=SandboxState.waiting_for_balance)
        dp.register_message_handler(process_sandbox_days, state=SandboxState.waiting_for_days)
        dp.register_message_handler(process_sandbox_speed, state=SandboxState.waiting_for_speed)
        dp.register_message_handler(process_sandbox_item_id, state=SandboxState.waiting_for_item_id)
        dp.register_message_handler(process_sandbox_item_name, state=SandboxState.waiting_for_item_name)
        dp.register_message_handler(process_sandbox_price, state=SandboxState.waiting_for_price)
        dp.register_message_handler(process_sandbox_quantity, state=SandboxState.waiting_for_quantity)
    else:
        # Для aiogram v3
        dp.message.register(cmd_sandbox, Command(commands=["sandbox"]))
        
        # Обработчик для callback_query
        async def process_v3_sandbox_callback(callback_query: types.CallbackQuery, state: FSMContext):
            if callback_query.data and callback_query.data.startswith(SANDBOX_PREFIX):
                parts = callback_query.data[len(SANDBOX_PREFIX):].split(":")
                action = parts[0]
                param = parts[1] if len(parts) > 1 else ""
                await process_sandbox_callback(callback_query, action, param, state)
        
        dp.callback_query.register(
            process_v3_sandbox_callback,
            lambda c: c.data and c.data.startswith(SANDBOX_PREFIX)
        )
        
        # Обработчики состояний
        dp.message.register(process_sandbox_balance, SandboxState.waiting_for_balance)
        dp.message.register(process_sandbox_days, SandboxState.waiting_for_days)
        dp.message.register(process_sandbox_speed, SandboxState.waiting_for_speed)
        dp.message.register(process_sandbox_item_id, SandboxState.waiting_for_item_id)
        dp.message.register(process_sandbox_item_name, SandboxState.waiting_for_item_name)
        dp.message.register(process_sandbox_price, SandboxState.waiting_for_price)
        dp.message.register(process_sandbox_quantity, SandboxState.waiting_for_quantity) 