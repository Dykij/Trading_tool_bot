@dp.message_handler(commands=['cs2'], state="*")
@is_admin
async def cmd_cs2(message: types.Message, state: FSMContext):
    """
    Команда для запуска поиска арбитражных возможностей в CS2.
    
    Args:
        message: Сообщение пользователя
        state: Объект состояния FSM
    """
    user_id = message.from_user.id
    logger.info(f"Пользователь {user_id} запустил команду /cs2")
    
    try:
        # Сбрасываем предыдущие состояния
        await state.finish()
        
        # Устанавливаем значения по умолчанию
        async with state.proxy() as data:
            data['mode'] = 'profit'  # По умолчанию - режим максимальной прибыли
            data['arbitrage_budget'] = 100  # Бюджет по умолчанию - 100$
        
        # Отправляем сообщение с настройками по умолчанию
        await message.reply(
            "🎮 <b>Запуск арбитража CS2</b>\n\n"
            "Начинаю поиск арбитражных возможностей с настройками по умолчанию:\n"
            "- Режим: Максимальная прибыль\n"
            "- Бюджет: $100\n\n"
            "<i>Пожалуйста, подождите...</i>",
            parse_mode="HTML"
        )
        
        # Получаем бота из контекста
        bot = message.bot
        
        # Получаем сервис торговли
        from src.trading.trading_facade import get_trading_service
        trading_service = get_trading_service()
        
        # Отправляем сообщение о начале поиска
        status_message = await message.reply("⏳ Поиск арбитражных возможностей в CS2...")
        
        # Ищем арбитражные возможности для CS2
        results = await trading_service.find_cs2_arbitrage_opportunities()
        
        if not results:
            await status_message.edit_text(
                "⚠️ <b>Арбитражные возможности не найдены</b>\n\n"
                "Попробуйте изменить параметры поиска или повторить попытку позже.",
                parse_mode="HTML"
            )
            return
        
        # Сортируем результаты по прибыли
        results.sort(key=lambda x: x['profit_amount'], reverse=True)
        
        # Ограничиваем количество результатов
        results = results[:30]
        
        # Форматируем и отправляем ответ
        from src.telegram.callbacks import format_cs2_arbitrage_results, create_arbitrage_results_keyboard
        
        response_message = format_cs2_arbitrage_results(results, 'profit')
        keyboard = create_arbitrage_results_keyboard('profit', is_cs2=True)
        
        await status_message.edit_text(
            response_message,
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        
    except Exception as e:
        logger.error(f"Ошибка при запуске арбитража CS2: {e}", exc_info=True)
        await message.reply(
            f"❌ <b>Произошла ошибка при поиске арбитражных возможностей</b>\n\n"
            f"Детали ошибки: {str(e)}",
            parse_mode="HTML"
        ) 