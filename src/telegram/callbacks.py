"""
Модуль с обработчиками колбэков для клавиатур Telegram бота.
"""

import logging
from typing import Optional, Union, Dict, Any, List
from datetime import datetime

from aiogram import Dispatcher, types
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode

# Импортируем декоратор для отслеживания колбэков
from src.telegram.decorators import track_callback

# Импортируем клавиатуры
from src.telegram.keyboards import (
    get_main_keyboard,
    get_menu_kb,
    get_cancel_kb,
    get_confirmation_kb,
    get_game_selection_keyboard,
    get_item_actions_keyboard,
    get_settings_keyboard,
    get_budget_input_keyboard,
    get_arbitrage_mode_keyboard
)

# Импортируем дополнительные клавиатуры
from src.telegram.custom_keyboards import (
    get_games_selection_keyboard,
    get_arbitrage_execution_keyboard,
    get_arbitrage_results_keyboard,
    get_arbitrage_settings_keyboard
)

# Импортируем менеджер арбитража
from src.arbitrage.arbitrage_modes import ArbitrageMode, ArbitrageManager

# Импортируем фасад для работы с торговыми данными
from src.trading.trading_facade import get_trading_service

# Определяем логгер
logger = logging.getLogger(__name__)

# Определяем состояния пользователя
class UserState(StatesGroup):
    waiting_for_item_name = State()
    waiting_for_price = State()
    waiting_for_confirmation = State()
    
    # Новые состояния для арбитража
    waiting_for_arbitrage_budget = State()
    waiting_for_arbitrage_mode = State()
    waiting_for_arbitrage_results = State()
    
    # Состояния для CS2
    waiting_for_cs2_category = State()
    waiting_for_cs2_price_range = State()

# Обработчик для всех инлайн-запросов
@track_callback
async def process_callback_query(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает все инлайн-запросы от клавиатур бота.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
    """
    # Получаем данные callback_data
    callback_data = callback_query.data
    user_id = callback_query.from_user.id
    
    logger.info(f"Получен callback от пользователя {user_id}: {callback_data}")
    
    try:
        # Парсим callback_data в формате "действие:параметр" или "действие:параметр1:параметр2"
        parts = callback_data.split(":", 2)
        action = parts[0]
        param = parts[1] if len(parts) > 1 else ""
        param2 = parts[2] if len(parts) > 2 else ""
        
        # Словарь доступных обработчиков
        handlers = {
            "menu": handle_menu_callback,
            "cancel_action": handle_cancel_callback,
            "confirm": handle_confirmation_callback,
            "back_to_main": handle_back_to_main_callback,
            "game": handle_game_selection_callback,
            "item": handle_item_callback,
            "settings": handle_settings_callback,
            "arbitrage_mode": handle_arbitrage_mode_callback,
            "budget": handle_budget_callback,
            "toggle_game": handle_game_toggle_callback,
            "select_all_games": handle_select_all_games_callback,
            "save_game_selection": handle_save_game_selection_callback,
            "arbitrage_exec": handle_arbitrage_execution_callback,
            "arbitrage_page": handle_arbitrage_page_callback,
            "arbitrage_results": handle_arbitrage_results_callback,
            "back_to_arbitrage": None,  # Обработаем отдельно
            "back_to_arbitrage_settings": None,  # Обработаем отдельно
            "back_to_arbitrage_mode": None,  # Обработаем отдельно
            "back_to_arbitrage_execution": None  # Обработаем отдельно
        }
        
        # Проверяем, есть ли такой обработчик
        if action in handlers and handlers[action] is not None:
            # Вызываем соответствующий обработчик
            logger.debug(f"Вызов обработчика {action} с параметрами: {param}, {param2}")
            try:
                await handlers[action](callback_query, state, param, param2 if action == "item" else None)
            except TypeError:
                # Если не принимает param2, вызываем с одним параметром
                await handlers[action](callback_query, state, param)
        # Обработка специальных "back_to" действий
        elif action == "back_to_arbitrage":
            # Возврат к меню выбора режима арбитража
            try:
                await callback_query.message.edit_text(
                    "Выберите режим арбитража:",
                    reply_markup=get_arbitrage_mode_keyboard()
                )
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Ошибка при обработке back_to_arbitrage: {e}")
                await callback_query.answer("Произошла ошибка при возврате к меню арбитража")
        elif action == "back_to_arbitrage_settings":
            # Возврат к настройкам арбитража
            try:
                await callback_query.message.edit_text(
                    "Настройки арбитража:",
                    reply_markup=get_arbitrage_settings_keyboard()
                )
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Ошибка при обработке back_to_arbitrage_settings: {e}")
                await callback_query.answer("Произошла ошибка при возврате к настройкам арбитража")
        elif action == "back_to_arbitrage_mode":
            # Возврат к выбору режима арбитража
            try:
                await callback_query.message.edit_text(
                    "Выберите режим арбитража:",
                    reply_markup=get_arbitrage_mode_keyboard()
                )
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Ошибка при обработке back_to_arbitrage_mode: {e}")
                await callback_query.answer("Произошла ошибка при возврате к выбору режима арбитража")
        elif action == "back_to_arbitrage_execution":
            try:
                # Получаем данные из состояния
                async with state.proxy() as data:
                    arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
                    budget = data.get('arbitrage_budget', 100)
                    selected_games = data.get('selected_games', ["cs2", "dota2", "tf2", "rust"])
                
                # Форматируем список игр для отображения
                game_names = {
                    "cs2": "CS2",
                    "dota2": "Dota 2",
                    "tf2": "Team Fortress 2",
                    "rust": "Rust"
                }
                
                games_text = ", ".join(game_names.get(game, game) for game in selected_games)
                
                # Возврат к экрану запуска арбитража
                await callback_query.message.edit_text(
                    f"<b>🔍 Настройки арбитража</b>\n\n"
                    f"<b>Режим:</b> {get_mode_name(arbitrage_mode)}\n"
                    f"<b>Бюджет:</b> ${budget}\n"
                    f"<b>Игры:</b> {games_text}\n\n"
                    f"Выберите действие:",
                    parse_mode="HTML",
                    reply_markup=get_arbitrage_execution_keyboard()
                )
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Ошибка при обработке back_to_arbitrage_execution: {e}")
                await callback_query.answer("Произошла ошибка при возврате к настройкам запуска")
        else:
            # Неизвестная команда
            logger.warning(f"Неизвестная команда callback: {action}, параметр: {param}, от пользователя {callback_query.from_user.id}")
            await callback_query.answer(f"Неизвестная команда: {action}")
    
    except Exception as e:
        logger.error(f"Ошибка при обработке callback: {e}", exc_info=True)
        try:
            await callback_query.answer("Произошла ошибка при обработке запроса.")
        except Exception as answer_error:
            logger.error(f"Ошибка при отправке ответа о ошибке: {answer_error}")
            
        # Пытаемся вернуть пользователя в главное меню в случае серьезной ошибки
        try:
            # Завершаем все состояния
            await state.finish()
            # Отправляем сообщение с главным меню
            await callback_query.message.reply(
                "Произошла ошибка. Возврат в главное меню.",
                reply_markup=get_menu_kb()
            )
        except Exception as menu_error:
            logger.error(f"Не удалось вернуться в главное меню: {menu_error}")

# Отдельные обработчики для разных типов колбэков
async def handle_menu_callback(callback_query: CallbackQuery, state: FSMContext, action: str):
    """
    Обрабатывает колбэки от меню.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        action: Параметр действия
    """
    if action == "add_items":
        await callback_query.message.answer(
            "Введите название предмета:",
            reply_markup=get_cancel_kb()
        )
        await state.set_state("waiting_for_item_name")
    elif action == "my_items":
        # Здесь будет логика получения списка предметов
        await callback_query.message.answer("Получаю список ваших предметов...")
    elif action == "statistics":
        await callback_query.message.answer("📊 Статистика торговли:\n\nПока недоступно")
    
    await callback_query.answer()

async def handle_cancel_callback(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбэк отмены действия.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
    """
    await state.finish()
    await callback_query.message.answer(
        "Действие отменено",
        reply_markup=get_menu_kb()
    )
    await callback_query.answer()

async def handle_confirmation_callback(callback_query: CallbackQuery, state: FSMContext, answer: str):
    """
    Обрабатывает колбэк подтверждения действия.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        answer: Ответ (yes/no)
    """
    if answer == "yes":
        # Здесь будет логика подтверждения действия
        await callback_query.message.answer("Действие подтверждено")
    else:
        await callback_query.message.answer("Действие отменено")
    
    await state.finish()
    await callback_query.answer()

async def handle_back_to_main_callback(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбэк возврата в главное меню.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
    """
    await state.finish()
    await callback_query.message.answer(
        "Вы вернулись в главное меню",
        reply_markup=get_menu_kb()
    )
    await callback_query.answer()

async def handle_game_selection_callback(callback_query: CallbackQuery, state: FSMContext, game: str):
    """
    Обрабатывает колбэк выбора игры.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        game: Выбранная игра
    """
    async with state.proxy() as data:
        data["selected_game"] = game
    
    await callback_query.message.answer(
        f"Выбрана игра: {game}\nВведите название предмета:",
        reply_markup=get_cancel_kb()
    )
    await state.set_state("waiting_for_item_name")
    await callback_query.answer()

async def handle_item_callback(callback_query: CallbackQuery, state: FSMContext, action: str, item_id: str):
    """
    Обрабатывает колбэк действий с предметом.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        action: Действие с предметом
        item_id: Идентификатор предмета
    """
    if action == "buy":
        await callback_query.message.answer(f"Оформление покупки предмета с ID: {item_id}")
    elif action == "sell":
        await callback_query.message.answer(f"Оформление продажи предмета с ID: {item_id}")
    elif action == "analyze":
        await callback_query.message.answer(f"Анализ цены предмета с ID: {item_id}")
    elif action == "history":
        await callback_query.message.answer(f"История предмета с ID: {item_id}")
    elif action == "favorite":
        await callback_query.message.answer(f"Предмет с ID: {item_id} добавлен в избранное")
    elif action == "delete":
        await callback_query.message.answer(
            f"Вы действительно хотите удалить предмет с ID: {item_id}?",
            reply_markup=get_confirmation_kb("delete")
        )
        async with state.proxy() as data:
            data["item_to_delete"] = item_id
        await state.set_state("waiting_for_confirmation")
    
    await callback_query.answer()

async def handle_settings_callback(callback_query: CallbackQuery, state: FSMContext, setting: str):
    """
    Обрабатывает колбэк настроек.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        setting: Параметр настроек
    """
    if setting == "notifications":
        await callback_query.message.answer("Настройки уведомлений:\n\nПока недоступно")
    elif setting == "frequency":
        await callback_query.message.answer("Настройки частоты проверки:\n\nПока недоступно")
    
    await callback_query.answer()

# Обработчик колбэков режимов арбитража
async def handle_arbitrage_mode_callback(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбек выбора режима арбитража.
    
    Args:
        callback_query: Объект колбека
        state: Состояние пользователя
    """
    user_data = await state.get_data()
    mode = callback_query.data.split(':')[1]
    
    # Сохраняем выбранный режим в состоянии пользователя
    await state.update_data(arbitrage_mode=mode)
    
    # Получаем конфигурацию диапазонов для выбранного режима
    try:
        # Импортируем класс ArbitrageMode из нового модуля
        from src.arbitrage.arbitrage_modes import ArbitrageMode, ArbitrageParams
        
        # Преобразуем строковой режим в enum
        arb_mode = None
        if mode == "balance_boost":
            arb_mode = ArbitrageMode.BALANCE_BOOST
        elif mode == "medium_trader":
            arb_mode = ArbitrageMode.MEDIUM_TRADER
        elif mode == "trade_pro":
            arb_mode = ArbitrageMode.TRADE_PRO
        
        # Получаем параметры для режима
        if arb_mode:
            params = ArbitrageParams(mode=arb_mode)
        else:
            # Используем старую реализацию как fallback
            from src.arbitrage.dmarket_arbitrage_finder import ArbitrageFinderParams
            params = ArbitrageFinderParams(mode=mode)
            
    except ImportError:
        # Если не удалось импортировать новый модуль, используем старую реализацию
        from src.arbitrage.dmarket_arbitrage_finder import ArbitrageFinderParams
        params = ArbitrageFinderParams(mode=mode)
    
    # Формируем ответ в зависимости от выбранного режима
    if mode == "info":
        # Просто показываем информацию о режимах с учетом ML-оптимизации для Trade Pro
        text = (
            "<b>📊 Режимы арбитража</b>\n\n"
            "<b>🚀 Разгон баланса ($1-5)</b>\n"
            "• Быстрые сделки с небольшой прибылью\n"
            "• Фокус на ликвидные предметы\n"
            "• Низкий риск\n\n"
            "<b>💼 Средний трейдер ($5-20)</b>\n"
            "• Сбалансированный подход\n"
            "• Предметы среднего ценового диапазона\n"
            "• Умеренный риск\n\n"
            "<b>👑 Trade Pro ($20-100)</b>\n"
            "• Высокая потенциальная прибыль\n"
            "• ML-оптимизация выбора предметов\n"
            "• Анализ тренда и параллельная обработка\n"
            "• Расширенная аналитика рисков\n"
        )
        keyboard = create_arbitrage_mode_keyboard()
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    else:
        # Показываем описание выбранного режима и запрашиваем бюджет
        if mode == "balance_boost":
            text = (
                "<b>🚀 Режим \"Разгон баланса\"</b>\n\n"
                f"Диапазон прибыли: ${params.min_profit}-{params.max_profit}\n"
                f"Ценовой диапазон: ${params.min_price}-{params.max_price}\n\n"
                "Этот режим фокусируется на быстрых сделках с небольшой прибылью. "
                "Идеально подходит для новичков и тех, кто хочет быстро увеличить свой баланс "
                "с минимальным риском.\n\n"
                "<b>Укажите свой бюджет:</b>"
            )
        elif mode == "medium_trader":
            text = (
                "<b>💼 Режим \"Средний трейдер\"</b>\n\n"
                f"Диапазон прибыли: ${params.min_profit}-{params.max_profit}\n"
                f"Ценовой диапазон: ${params.min_price}-{params.max_price}\n\n"
                "Сбалансированный режим для опытных трейдеров. "
                "Фокусируется на предметах среднего ценового диапазона с хорошей ликвидностью "
                "и умеренным риском.\n\n"
                "<b>Укажите свой бюджет:</b>"
            )
        elif mode == "trade_pro":
            text = (
                "<b>👑 Режим \"Trade Pro\"</b>\n\n"
                f"Диапазон прибыли: ${params.min_profit}-{params.max_profit}\n"
                f"Ценовой диапазон: ${params.min_price}-{params.max_price}\n\n"
                "Премиум режим для профессиональных трейдеров с ML-оптимизацией. "
                "Нацелен на редкие и дорогие предметы с высокой потенциальной прибылью, "
                "использует анализ тренда и параллельную обработку для повышения точности. "
                "Требует больше терпения и принятия рассчитанного риска.\n\n"
                "<b>Укажите свой бюджет:</b>"
            )
        else:
            text = "<b>Выберите бюджет для поиска:</b>"
            
        # Создаем клавиатуру для выбора бюджета
        keyboard = create_budget_keyboard()
        await callback_query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
    # Отвечаем на колбек
    await callback_query.answer()

# Обработчик колбэков бюджета арбитража
async def handle_budget_callback(callback_query: CallbackQuery, state: FSMContext, budget_value: str):
    """
    Обрабатывает колбэк выбора бюджета для арбитража.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        budget_value: Выбранное значение бюджета
    """
    user_id = callback_query.from_user.id
    
    if budget_value == "custom":
        # Пользователь хочет ввести свое значение
        await callback_query.message.edit_text(
            "Введите сумму бюджета (в USD):",
            reply_markup=get_cancel_kb()
        )
        await state.set_state(UserState.waiting_for_arbitrage_budget)
    else:
        # Сохраняем выбранный бюджет
        try:
            budget = float(budget_value)
            async with state.proxy() as data:
                data['arbitrage_budget'] = budget
                arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
            
            # Переходим к выбору игр
            await callback_query.message.edit_text(
                f"<b>💰 Бюджет: ${budget}</b>\n\n"
                f"Выберите игры для поиска арбитража:",
                parse_mode="HTML",
                reply_markup=get_game_selection_keyboard()
            )
        except ValueError:
            # Ошибка преобразования в число
            await callback_query.message.edit_text(
                "❌ Ошибка: некорректное значение бюджета. Попробуйте снова:",
                reply_markup=get_budget_input_keyboard()
            )
    
    await callback_query.answer()

# Обработчик текстового ввода бюджета
async def process_arbitrage_budget(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод пользовательского бюджета для арбитража.
    
    Args:
        message: Сообщение от пользователя
        state: Состояние пользователя
    """
    user_id = message.from_user.id
    budget_text = message.text.strip().replace('$', '').replace(',', '.')
    
    try:
        budget = float(budget_text)
        if budget <= 0:
            raise ValueError("Бюджет должен быть положительным числом")
        
        # Сохраняем бюджет в состоянии
        async with state.proxy() as data:
            data['arbitrage_budget'] = budget
            arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
        
        # Показываем клавиатуру выбора игр
        await message.answer(
            f"<b>💰 Бюджет: ${budget}</b>\n\n"
            f"Выберите игры для поиска арбитража:",
            parse_mode="HTML",
            reply_markup=get_game_selection_keyboard()
        )
        
        # Сбрасываем состояние
        await state.reset_state(with_data=False)
        
    except ValueError as e:
        # Ошибка преобразования в число
        await message.answer(
            f"❌ Ошибка: {str(e)}. Введите корректную сумму бюджета (в USD):",
            reply_markup=get_cancel_kb()
        )

# Обработчик колбэков выбора игр
async def handle_game_toggle_callback(callback_query: CallbackQuery, state: FSMContext, game: str):
    """
    Обрабатывает колбэк переключения игры для арбитража.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        game: Код игры
    """
    # Получаем текущие выбранные игры
    async with state.proxy() as data:
        selected_games = data.get('selected_games', ["cs2", "dota2", "tf2", "rust"])
        
        # Переключаем состояние выбора
        if game in selected_games:
            selected_games.remove(game)
        else:
            selected_games.append(game)
        
        # Сохраняем обновленный список
        data['selected_games'] = selected_games
    
    # Обновляем клавиатуру
    await callback_query.message.edit_reply_markup(
        reply_markup=get_game_selection_keyboard(selected_games)
    )
    
    await callback_query.answer()

# Обработчик колбэка "Выбрать все игры"
async def handle_select_all_games_callback(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбэк выбора всех игр.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
    """
    # Выбираем все игры
    async with state.proxy() as data:
        data['selected_games'] = ["cs2", "dota2", "tf2", "rust"]
    
    # Обновляем клавиатуру
    await callback_query.message.edit_reply_markup(
        reply_markup=get_game_selection_keyboard(["cs2", "dota2", "tf2", "rust"])
    )
    
    await callback_query.answer()

# Обработчик колбэка сохранения выбора игр
async def handle_save_game_selection_callback(callback_query: CallbackQuery, state: FSMContext):
    """
    Обрабатывает колбэк сохранения выбора игр.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
    """
    # Получаем данные из состояния
    async with state.proxy() as data:
        selected_games = data.get('selected_games', ["cs2", "dota2", "tf2", "rust"])
        budget = data.get('arbitrage_budget', 100)
        arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
    
    # Форматируем список игр для отображения
    game_names = {
        "cs2": "CS2",
        "dota2": "Dota 2",
        "tf2": "Team Fortress 2",
        "rust": "Rust"
    }
    
    games_text = ", ".join(game_names[game] for game in selected_games)
    
    # Показываем экран запуска арбитража
    await callback_query.message.edit_text(
        f"<b>🔍 Настройки арбитража</b>\n\n"
        f"<b>Режим:</b> {get_mode_name(arbitrage_mode)}\n"
        f"<b>Бюджет:</b> ${budget}\n"
        f"<b>Игры:</b> {games_text}\n\n"
        f"Выберите действие:",
        parse_mode="HTML",
        reply_markup=get_arbitrage_execution_keyboard()
    )
    
    await callback_query.answer()

# Обработчик колбэков запуска арбитража
@track_callback
async def handle_arbitrage_execution_callback(callback_query: CallbackQuery, state: FSMContext, param: str):
    """
    Обрабатывает колбэки на экране запуска арбитража.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        param: Параметр (действие)
    """
    logger.info(f"Обработка колбэка запуска арбитража: {param}")
    
    if param == "start":
        # Запуск поиска арбитражных возможностей
        await start_arbitrage_search(callback_query, state)
    elif param == "start_cs2":
        # Запуск поиска арбитражных возможностей для CS2
        await start_cs2_arbitrage_search(callback_query, state)
    elif param == "edit_games":
        # Переход к выбору игр
        async with state.proxy() as data:
            await callback_query.message.edit_text(
                "Выберите игры для поиска арбитражных возможностей:",
                reply_markup=await get_games_selection_keyboard(data)
            )
            await callback_query.answer()
    elif param == "edit_mode":
        # Переход к выбору режима арбитража
        await callback_query.message.edit_text(
            "Выберите режим арбитража:",
            reply_markup=get_arbitrage_mode_keyboard()
        )
        await callback_query.answer()
    elif param == "edit_budget":
        # Переход к вводу бюджета
        await callback_query.message.edit_text(
            "Выберите бюджет для арбитража:",
            reply_markup=get_budget_input_keyboard()
        )
        await callback_query.answer()
    elif param == "back":
        # Возврат к настройкам арбитража
        await callback_query.message.edit_text(
            "Настройки арбитража:",
            reply_markup=get_arbitrage_settings_keyboard()
        )
        await callback_query.answer()
    else:
        await callback_query.answer("Неизвестное действие")

# Обработчик колбэков пагинации результатов арбитража
async def handle_arbitrage_page_callback(callback_query: CallbackQuery, state: FSMContext, page: str):
    """
    Обрабатывает колбэк пагинации результатов арбитража.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        page: Номер страницы или специальная команда (current)
    """
    if page == "current":
        # Игнорируем клик по текущей странице
        await callback_query.answer()
        return
    
    # Преобразуем страницу в число
    try:
        page_num = int(page)
        
        # Обновляем текущую страницу в состоянии
        async with state.proxy() as data:
            data['arbitrage_page'] = page_num
        
        # Отображаем результаты для выбранной страницы
        await display_arbitrage_results(callback_query.message, state)
        
    except ValueError:
        await callback_query.answer("Некорректный номер страницы")
    
    await callback_query.answer()

# Обработчик колбэков действий с результатами арбитража
async def handle_arbitrage_results_callback(callback_query: CallbackQuery, state: FSMContext, action: str):
    """
    Обрабатывает колбэк действий с результатами арбитража.
    
    Args:
        callback_query: Объект запроса колбэка
        state: Состояние пользователя
        action: Действие (execute, save, refresh)
    """
    # Получаем данные из состояния
    async with state.proxy() as data:
        results = data.get('arbitrage_results', [])
        arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
    
    # Создаем менеджер арбитража
    arbitrage_manager = ArbitrageManager()
    
    if action == "execute":
        # Проверяем наличие результатов
        if not results:
            await callback_query.message.edit_text(
                "❌ Нет результатов для выполнения. Сначала выполните поиск.",
                reply_markup=get_arbitrage_execution_keyboard()
            )
            await callback_query.answer()
            return
        
        # Запрашиваем подтверждение
        await callback_query.message.edit_text(
            f"<b>💰 Выполнение сделок</b>\n\n"
            f"Вы собираетесь выполнить <b>{len(results)}</b> сделок в режиме "
            f"{get_mode_name(arbitrage_mode)}.\n\n"
            f"Это приведет к реальным сделкам на DMarket.\n"
            f"Подтверждаете выполнение?",
            parse_mode="HTML",
            reply_markup=get_confirmation_kb("execute_arbitrage")
        )
    
    elif action == "refresh":
        # Запускаем новый поиск с теми же параметрами
        await callback_query.message.edit_text(
            f"<b>🔄 Обновление результатов</b>\n\n"
            f"Идет обновление в режиме {get_mode_name(arbitrage_mode)}...\n\n"
            f"Пожалуйста, подождите.",
            parse_mode="HTML"
        )
        
        # Получаем параметры из состояния
        async with state.proxy() as data:
            budget = data.get('arbitrage_budget', 100)
        
        try:
            # Запускаем поиск арбитража снова
            opportunities = await arbitrage_manager.find_arbitrage_opportunities(
                mode=arbitrage_mode,
                budget=budget
            )
            
            # Обновляем результаты в состоянии
            async with state.proxy() as data:
                data['arbitrage_results'] = opportunities.to_dict('records')
                data['arbitrage_found_count'] = len(opportunities)
                data['arbitrage_page'] = 1
            
            # Показываем обновленные результаты
            await display_arbitrage_results(callback_query.message, state)
            
        except Exception as e:
            logger.error(f"Ошибка при обновлении арбитража: {str(e)}")
            await callback_query.message.edit_text(
                f"❌ Ошибка при обновлении арбитража: {str(e)}",
                reply_markup=get_arbitrage_results_keyboard(1, 1)
            )
    
    await callback_query.answer()

# Вспомогательная функция для отображения результатов арбитража
async def display_arbitrage_results(message: types.Message, state: FSMContext):
    """
    Отображает результаты арбитража с пагинацией.
    
    Args:
        message: Сообщение, в котором нужно отобразить результаты
        state: Состояние пользователя
    """
    # Получаем данные из состояния
    async with state.proxy() as data:
        results = data.get('arbitrage_results', [])
        current_page = data.get('arbitrage_page', 1)
        arbitrage_mode = data.get('arbitrage_mode', 'balance_boost')
    
    # Проверяем наличие результатов
    if not results:
        await message.edit_text(
            "🔍 Поиск не дал результатов. Попробуйте изменить параметры.",
            reply_markup=get_arbitrage_execution_keyboard()
        )
        return
    
    # Рассчитываем общее количество страниц (10 предметов на страницу)
    items_per_page = 10
    total_pages = (len(results) + items_per_page - 1) // items_per_page
    
    # Ограничиваем текущую страницу
    current_page = max(1, min(current_page, total_pages))
    
    # Получаем элементы для текущей страницы
    start_idx = (current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(results))
    page_items = results[start_idx:end_idx]
    
    # Формируем сообщение с результатами
    mode_name = get_mode_name(arbitrage_mode)
    total_profit = sum(item.get('profit', 0) for item in results)
    
    message_text = f"<b>🔍 Результаты арбитража ({mode_name})</b>\n\n"
    message_text += f"Найдено предметов: <b>{len(results)}</b>\n"
    message_text += f"Потенциальная прибыль: <b>${total_profit:.2f}</b>\n\n"
    
    # Добавляем список предметов
    for i, item in enumerate(page_items, start=start_idx + 1):
        name = item.get('name', 'Неизвестный предмет')
        game = item.get('game', '').upper()
        price = item.get('price', 0)
        sell_price = item.get('recommended_price', 0)
        profit = item.get('profit', 0)
        profit_percent = item.get('profit_percent', 0)
        
        message_text += f"{i}. <b>{name}</b> [{game}]\n"
        message_text += f"   💰 ${price:.2f} ➡️ ${sell_price:.2f} (⭐ +${profit:.2f}, {profit_percent:.1f}%)\n"
    
    # Добавляем информацию о странице
    message_text += f"\nСтраница {current_page} из {total_pages}"
    
    # Отправляем сообщение с клавиатурой пагинации
    await message.edit_text(
        message_text,
        parse_mode="HTML",
        reply_markup=get_arbitrage_results_keyboard(current_page, total_pages)
    )

# Вспомогательная функция для получения названия режима
def get_mode_name(mode_code: str) -> str:
    """
    Возвращает название режима арбитража по коду.
    
    Args:
        mode_code: Код режима
        
    Returns:
        Название режима
    """
    mode_names = {
        "balance_boost": "🚀 Разгон баланса",
        "medium_trader": "💼 Средний трейдер",
        "trade_pro": "👑 Trade Pro"
    }
    
    return mode_names.get(mode_code, mode_code)

# Обновляем регистрацию обработчиков для включения новых функций
def register_callback_handlers(dp: Dispatcher):
    """
    Регистрирует обработчики колбэков в диспетчере.
    
    Args:
        dp: Диспетчер бота
    """
    # Регистрируем обработчик всех колбэков
    dp.register_callback_query_handler(process_callback_query, state="*")
    
    # Регистрируем обработчик ввода бюджета
    dp.register_message_handler(process_arbitrage_budget, state=UserState.waiting_for_arbitrage_budget)
    
    logger.info("Обработчики колбэков арбитража зарегистрированы")
    
    return dp 

def get_mode_display_name(mode: str) -> str:
    """
    Возвращает отображаемое имя режима арбитража.
    
    Args:
        mode: Код режима
        
    Returns:
        Отображаемое имя режима
    """
    mode_names = {
        "balance_boost": "🚀 Разгон баланса",
        "medium_trader": "💼 Средний трейдер",
        "trade_pro": "👑 Trade Pro"
    }
    return mode_names.get(mode, mode)

def format_arbitrage_results(results, mode: str) -> str:
    """
    Форматирует результаты поиска арбитражных возможностей.
    
    Args:
        results: Список арбитражных возможностей
        mode: Режим арбитража
        
    Returns:
        Отформатированная строка результатов
    """
    header = f"🎯 <b>Найдено {len(results)} арбитражных возможностей</b>\n\n"
    
    if not results:
        return header + "Нет доступных возможностей."
    
    details = []
    for idx, opportunity in enumerate(results[:10], 1):
        profit_pct = opportunity.profit_percentage
        profit_usd = opportunity.profit_usd
        
        item_name = opportunity.item_name
        buy_price = opportunity.buy_price
        sell_price = opportunity.sell_price
        marketplace = opportunity.marketplace
        
        detail = (f"{idx}. <b>{item_name}</b>\n"
                 f"💰 Прибыль: ${profit_usd:.2f} ({profit_pct:.2f}%)\n"
                 f"📈 Покупка: ${buy_price:.2f} → Продажа: ${sell_price:.2f}\n"
                 f"🏪 Площадка: {marketplace}\n")
        details.append(detail)
    
    if len(results) > 10:
        details.append(f"\n<i>...и ещё {len(results) - 10} возможностей</i>")
    
    return header + "\n".join(details)

def create_arbitrage_results_keyboard(mode: str, is_cs2: bool = False) -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для экрана результатов арбитража.
    
    Args:
        mode: Текущий режим арбитража
        is_cs2: Флаг, указывающий, что это результаты для CS2
        
    Returns:
        Инлайн-клавиатура
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Кнопки для сортировки
    keyboard.row(
        InlineKeyboardButton("💰 По прибыли", callback_data=f"arbitrage_results:sort:profit"),
        InlineKeyboardButton("📊 По %", callback_data=f"arbitrage_results:sort:profit_percentage")
    )
    keyboard.row(
        InlineKeyboardButton("⚡ По ликвидности", callback_data=f"arbitrage_results:sort:liquidity"),
        InlineKeyboardButton("🔄 Обновить", callback_data=f"arbitrage_results:refresh")
    )
    
    # Кнопки для навигации по страницам (если результатов много)
    # keyboard.row(
    #     InlineKeyboardButton("⬅️ Пред", callback_data=f"arbitrage_page:prev"),
    #     InlineKeyboardButton("След ➡️", callback_data=f"arbitrage_page:next")
    # )
    
    # Кнопка для возврата к настройкам
    if is_cs2:
        keyboard.add(InlineKeyboardButton("◀️ Назад к настройкам", callback_data="back_to_arbitrage_execution"))
    else:
        keyboard.add(InlineKeyboardButton("◀️ Назад к настройкам", callback_data="back_to_arbitrage_execution"))
    
    return keyboard

def create_arbitrage_mode_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора режима арбитража.
    
    Returns:
        Клавиатура
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопки выбора режима согласно перечислению ArbitrageMode
    keyboard.add(
        InlineKeyboardButton("🚀 Разгон баланса", callback_data="arbitrage_mode:balance_boost"),
        InlineKeyboardButton("💼 Средний трейдер", callback_data="arbitrage_mode:medium_trader"),
        InlineKeyboardButton("👑 Trade Pro", callback_data="arbitrage_mode:trade_pro"),
        InlineKeyboardButton("ℹ️ Информация", callback_data="arbitrage_mode:info")
    )
    
    # Кнопка возврата к меню
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="arbitrage_menu"))
    
    return keyboard

def create_budget_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для выбора бюджета.
    
    Returns:
        Клавиатура
    """
    keyboard = InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопки выбора бюджета
    keyboard.add(
        InlineKeyboardButton("100", callback_data="budget:100"),
        InlineKeyboardButton("200", callback_data="budget:200"),
        InlineKeyboardButton("300", callback_data="budget:300"),
        InlineKeyboardButton("400", callback_data="budget:400"),
        InlineKeyboardButton("500", callback_data="budget:500"),
        InlineKeyboardButton("1000", callback_data="budget:1000"),
        InlineKeyboardButton("Custom", callback_data="budget:custom")
    )
    
    # Кнопка возврата к меню
    keyboard.add(InlineKeyboardButton("🔙 Назад", callback_data="arbitrage_menu"))
    
    return keyboard 

async def start_arbitrage_search(callback_query: CallbackQuery, state: FSMContext):
    """
    Инициирует поиск арбитражных возможностей и отображает результаты пользователю.
    
    Args:
        callback_query: Объект запроса обратного вызова
        state: Объект состояния FSM
    """
    user_data = await state.get_data()
    mode = user_data.get('arbitrage_mode', 'profit')
    budget = user_data.get('arbitrage_budget', 100)
    selected_games = user_data.get('selected_games', [])
    
    # Проверка на выбор хотя бы одной игры
    if not selected_games:
        await callback_query.answer("Выберите хотя бы одну игру", show_alert=True)
        await callback_query.message.edit_text(
            "Пожалуйста, выберите игры для поиска арбитражных возможностей:",
            reply_markup=await get_games_selection_keyboard(user_data)
        )
        return
    
    # Отправляем сообщение о начале поиска
    game_names = get_game_display_names(selected_games)
    mode_display = get_mode_display_name(mode)
    
    await callback_query.message.edit_text(
        f"🔍 <b>Поиск арбитражных возможностей начат</b>\n\n"
        f"Режим: <b>{mode_display}</b>\n"
        f"Бюджет: <b>${budget:.2f}</b>\n"
        f"Игры: <b>{', '.join(game_names)}</b>\n\n"
        f"<i>Пожалуйста, подождите...</i>"
    )
    
    # Создаем параметры для поиска арбитража
    params = {
        'mode': mode,
        'budget': budget,
        'games': selected_games
    }
    
    results = []
    
    try:
        # Инициализируем API клиент и поисковик арбитража
        api_client = DMarketAPIClient()
        arbitrage_finder = DMarketArbitrageFinder(api_client)
        
        # Ищем арбитражные возможности для каждой выбранной игры
        for game_id in selected_games:
            try:
                game_results = await arbitrage_finder.find_arbitrage_opportunities(
                    game_id=game_id,
                    budget=budget,
                    mode=mode
                )
                results.extend(game_results)
            except Exception as e:
                logger.error(f"Ошибка при поиске арбитража для игры {game_id}: {e}")
        
        # Сортируем результаты в зависимости от режима
        if mode == 'profit':
            results.sort(key=lambda x: x.profit_usd, reverse=True)
        elif mode == 'profit_percentage':
            results.sort(key=lambda x: x.profit_percentage, reverse=True)
        elif mode == 'liquidity':
            results.sort(key=lambda x: x.liquidity * x.profit_percentage, reverse=True)
        
        # Ограничиваем количество результатов
        results = results[:30]
        
        # Форматируем и отправляем ответ
        response_message = format_arbitrage_results(results, mode)
        keyboard = create_arbitrage_results_keyboard(mode)
        
        await callback_query.message.edit_text(
            response_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при поиске арбитража: {e}", exc_info=True)
        await callback_query.message.edit_text(
            f"❌ <b>Произошла ошибка при поиске арбитражных возможностей</b>\n\n"
            f"Детали ошибки: {str(e)}",
            reply_markup=get_back_to_menu_keyboard()
        )

def get_game_display_names(game_ids: List[str]) -> List[str]:
    """
    Возвращает отображаемые имена игр по их ID.
    
    Args:
        game_ids: Список ID игр
        
    Returns:
        Список отображаемых имен игр
    """
    game_names = {
        "a8db": "CS2",
        "9a92": "Dota 2",
        "tf2": "Team Fortress 2",
        "rust": "Rust"
    }
    return [game_names.get(game_id, game_id) for game_id in game_ids]

async def start_cs2_arbitrage_search(callback_query: CallbackQuery, state: FSMContext):
    """
    Инициирует поиск арбитражных возможностей в CS2 с использованием скрапера.
    
    Args:
        callback_query: Объект запроса обратного вызова
        state: Объект состояния FSM
    """
    user_data = await state.get_data()
    mode = user_data.get('mode', 'profit')
    budget = user_data.get('arbitrage_budget', 100)
    
    # Отправляем сообщение о начале поиска
    await callback_query.message.edit_text(
        f"🔍 <b>Поиск арбитражных возможностей CS2 начат</b>\n\n"
        f"Режим: <b>{get_mode_display_name(mode)}</b>\n"
        f"Бюджет: <b>${budget:.2f}</b>\n\n"
        f"<i>Пожалуйста, подождите...</i>",
        parse_mode="HTML"
    )
    
    try:
        # Получаем сервис торговли
        trading_service = get_trading_service()
        
        # Ищем арбитражные возможности для CS2
        results = await trading_service.find_cs2_arbitrage_opportunities()
        
        if not results:
            await callback_query.message.edit_text(
                "⚠️ <b>Арбитражные возможности не найдены</b>\n\n"
                "Попробуйте изменить параметры поиска или повторить попытку позже.",
                parse_mode="HTML",
                reply_markup=get_back_to_execution_keyboard()
            )
            return
        
        # Сортируем результаты в зависимости от режима
        if mode == 'profit':
            results.sort(key=lambda x: x['profit_amount'], reverse=True)
        elif mode == 'profit_percentage':
            results.sort(key=lambda x: x['profit_percent'], reverse=True)
        elif mode == 'liquidity':
            # Используем значение ликвидности, если есть, или количество объявлений как аппроксимацию
            results.sort(key=lambda x: x.get('liquidity', 'Medium') == 'High' and x['profit_percent'], reverse=True)
        
        # Ограничиваем количество результатов
        results = results[:30]
        
        # Форматируем и отправляем ответ
        response_message = format_cs2_arbitrage_results(results, mode)
        keyboard = create_arbitrage_results_keyboard(mode, is_cs2=True)
        
        await callback_query.message.edit_text(
            response_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при поиске арбитража CS2: {e}", exc_info=True)
        await callback_query.message.edit_text(
            f"❌ <b>Произошла ошибка при поиске арбитражных возможностей</b>\n\n"
            f"Детали ошибки: {str(e)}",
            reply_markup=get_back_to_execution_keyboard()
        )

def format_cs2_arbitrage_results(results: List[Dict[str, Any]], mode: str) -> str:
    """
    Форматирует результаты поиска арбитражных возможностей CS2 для отображения пользователю.
    
    Args:
        results: Список результатов арбитража
        mode: Режим арбитража (profit, profit_percentage, liquidity)
        
    Returns:
        Отформатированное сообщение с результатами
    """
    if not results:
        return "⚠️ <b>Арбитражные возможности не найдены</b>"
    
    # Заголовок в зависимости от режима
    if mode == 'profit':
        header = "💰 <b>Найдены арбитражные возможности CS2 (сортировка по прибыли)</b>\n\n"
    elif mode == 'profit_percentage':
        header = "📊 <b>Найдены арбитражные возможности CS2 (сортировка по % прибыли)</b>\n\n"
    elif mode == 'liquidity':
        header = "⚡ <b>Найдены арбитражные возможности CS2 (сортировка по ликвидности)</b>\n\n"
    else:
        header = "🔍 <b>Найдены арбитражные возможности CS2</b>\n\n"
    
    # Форматируем каждый результат
    items = []
    for i, result in enumerate(results, 1):
        item_name = result.get('item_name', 'Неизвестный предмет')
        buy_market = result.get('buy_market', 'Неизвестно')
        buy_price = result.get('buy_price', 0.0)
        sell_market = result.get('sell_market', 'Неизвестно')
        sell_price = result.get('sell_price', 0.0)
        profit_amount = result.get('profit_amount', 0.0)
        profit_percent = result.get('profit_percent', 0.0)
        category = result.get('category', 'Другое')
        rarity = result.get('rarity', 'Обычный')
        liquidity = result.get('liquidity', 'Средняя')
        
        # Добавляем эмодзи в зависимости от категории
        category_emoji = {
            'knife': '🔪',
            'pistol': '🔫',
            'rifle': '🎯',
            'sniper': '🔭',
            'smg': '💨',
            'shotgun': '💥',
            'machinegun': '⚡',
            'gloves': '🧤',
            'container': '📦',
            'key': '🔑',
            'other': '🎮'
        }
        
        emoji = category_emoji.get(category.lower(), '🎮')
        
        # Добавляем цветовую индикацию для прибыли
        if profit_percent >= 15:
            profit_indicator = "🟢"  # Высокая прибыль
        elif profit_percent >= 8:
            profit_indicator = "🟡"  # Средняя прибыль
        else:
            profit_indicator = "🟠"  # Низкая прибыль
        
        # Форматируем результат
        item_text = (
            f"{i}. {emoji} <b>{item_name}</b>\n"
            f"   ↳ Покупка: {buy_market} - <b>${buy_price:.2f}</b>\n"
            f"   ↳ Продажа: {sell_market} - <b>${sell_price:.2f}</b>\n"
            f"   ↳ Прибыль: {profit_indicator} <b>${profit_amount:.2f}</b> ({profit_percent:.2f}%)\n"
            f"   ↳ Категория: {category}, Редкость: {rarity}, Ликвидность: {liquidity}\n"
        )
        
        items.append(item_text)
    
    # Объединяем все в одно сообщение
    results_text = "\n".join(items)
    
    footer = (
        f"\n<i>Найдено {len(results)} возможностей. "
        f"Данные обновлены {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>"
    )
    
    return header + results_text + footer

def get_back_to_execution_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для возврата к экрану запуска арбитража.
    
    Returns:
        Инлайн-клавиатура
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("◀️ Назад к настройкам запуска", callback_data="back_to_arbitrage_execution"))
    return keyboard

def get_arbitrage_execution_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для запуска арбитражного поиска.
    
    Returns:
        Инлайн-клавиатура с кнопками для запуска арбитража
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Добавляем кнопки для запуска поиска
    keyboard.add(
        InlineKeyboardButton("🚀 Запустить поиск арбитража", callback_data="arbitrage_exec:start")
    )
    
    # Добавляем кнопку для запуска поиска CS2
    keyboard.add(
        InlineKeyboardButton("🎮 Запустить поиск арбитража CS2", callback_data="arbitrage_exec:start_cs2")
    )
    
    # Добавляем кнопки для изменения параметров
    keyboard.row(
        InlineKeyboardButton("🎯 Изменить режим", callback_data="arbitrage_exec:edit_mode"),
        InlineKeyboardButton("💰 Изменить бюджет", callback_data="arbitrage_exec:edit_budget")
    )
    
    keyboard.add(
        InlineKeyboardButton("🎮 Выбрать игры", callback_data="arbitrage_exec:edit_games")
    )
    
    # Добавляем кнопку для возврата назад
    keyboard.add(
        InlineKeyboardButton("◀️ Назад", callback_data="arbitrage_exec:back")
    )
    
    return keyboard

def get_back_to_menu_keyboard() -> InlineKeyboardMarkup:
    """
    Создает клавиатуру для возврата в главное меню.
    
    Returns:
        Инлайн-клавиатура
    """
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(InlineKeyboardButton("⬅️ Вернуться в меню", callback_data="back_to_main_menu"))
    return keyboard 