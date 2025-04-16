import os
import logging
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("debug_bot")

async def test_telegram_bot():
    """Проверяет подключение к Telegram API и валидность токена бота"""
    
    # Загружаем переменные окружения
    load_dotenv()
    print("\n=== Проверка переменных окружения ===")
    
    # Выводим доступные токены
    bot_token = os.getenv("BOT_TOKEN")
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    
    print(f"BOT_TOKEN: {'Установлен' if bot_token else 'Не установлен'}")
    if bot_token:
        print(f"Длина: {len(bot_token)} символов")
        print(f"Начало: {bot_token[:10]}...")
    
    print(f"TELEGRAM_BOT_TOKEN: {'Установлен' if telegram_bot_token else 'Не установлен'}")
    if telegram_bot_token:
        print(f"Длина: {len(telegram_bot_token)} символов")
        print(f"Начало: {telegram_bot_token[:10]}...")
    
    # Используем токен из BOT_TOKEN, если TELEGRAM_BOT_TOKEN не установлен
    if not telegram_bot_token and bot_token:
        print("Используем BOT_TOKEN вместо TELEGRAM_BOT_TOKEN")
        telegram_bot_token = bot_token
        # Также установим переменную окружения для будущих запусков
        os.environ["TELEGRAM_BOT_TOKEN"] = bot_token
    
    if not telegram_bot_token:
        print("\nОШИБКА: Токен бота Telegram не найден в переменных окружения")
        print("Пожалуйста, добавьте TELEGRAM_BOT_TOKEN=Ваш_токен в файл .env")
        return
    
    print("\n=== Проверка соединения с Telegram API ===")
    
    try:
        # Создаем экземпляр бота
        bot = Bot(token=telegram_bot_token)
        print("Бот успешно создан")
        
        # Получаем информацию о боте
        print("Получаем информацию о боте...")
        bot_info = await bot.get_me()
        print(f"Подключение успешно. Информация о боте:")
        print(f"ID: {bot_info.id}")
        print(f"Username: @{bot_info.username}")
        print(f"Имя: {bot_info.first_name}")
        
        # Проверяем права и разрешения
        print("\nПроверяем разрешения бота...")
        
        try:
            # Проверяем, можем ли мы получить обновления
            print("Тест получения обновлений...")
            updates = await bot.get_updates(limit=1, timeout=1)
            print(f"Получено обновлений: {len(updates)}")
            
            # Создаем и проверяем диспетчер
            dp = Dispatcher(bot)
            print("Диспетчер успешно создан")
            
            print("\nБот полностью функционален и готов к работе.")
        except Exception as e:
            print(f"Возникла ошибка при проверке разрешений: {e}")
            
        # Закрываем сессию бота
        await bot.session.close()
        
    except Exception as e:
        print(f"\nОШИБКА подключения к Telegram API: {e}")
        print("\nПроверьте следующее:")
        print("1. Токен бота корректен")
        print("2. Интернет-соединение активно")
        print("3. Telegram API доступен из вашей сети")
        
    print("\n=== Проверка завершена ===")

if __name__ == "__main__":
    asyncio.run(test_telegram_bot()) 