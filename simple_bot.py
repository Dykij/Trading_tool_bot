import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                   format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("simple_bot")

# Загружаем переменные окружения
load_dotenv()

# Получаем токен бота из переменных окружения
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    logger.error("Токен бота не найден в переменных окружения")
    exit(1)

# Создаем экземпляры бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(bot)

# Обработчик команды /start
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(f"Привет, {message.from_user.first_name}! Я работающий бот.")

# Обработчик команды /status
@dp.message_handler(commands=['status'])
async def cmd_status(message: types.Message):
    await message.answer("Статус: 🟢 Работаю")

# Обработчик для всех текстовых сообщений
@dp.message_handler(content_types=types.ContentType.TEXT)
async def echo_message(message: types.Message):
    await message.answer(f"Вы написали: {message.text}")

# Функция запуска бота
async def on_startup(dp):
    logger.info("Бот запущен!")
    me = await bot.get_me()
    logger.info(f"Информация о боте: @{me.username} ({me.id})")

if __name__ == "__main__":
    try:
        logger.info("Запуск простого бота...")
        executor.start_polling(dp, on_startup=on_startup, skip_updates=True)
    except Exception as e:
        logger.exception(f"Ошибка при запуске бота: {e}") 