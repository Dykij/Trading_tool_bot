import os
import asyncio
import logging
from dotenv import load_dotenv
from aiohttp import ClientSession

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("remove_webhook")

async def remove_webhook():
    """Удаляет текущий вебхук бота"""
    # Загружаем переменные окружения
    load_dotenv()
    
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        logger.error("Токен бота не найден в переменных окружения")
        return False
    
    # API URL для удаления вебхука
    url = f"https://api.telegram.org/bot{token}/deleteWebhook"
    
    logger.info(f"Отправка запроса на удаление вебхука: {url}")
    
    try:
        async with ClientSession() as session:
            # Отправляем запрос на удаление вебхука
            async with session.post(url) as response:
                result = await response.json()
                if response.status == 200 and result.get("ok"):
                    logger.info("Вебхук успешно удален!")
                    
                    # Проверяем текущие настройки вебхука
                    check_url = f"https://api.telegram.org/bot{token}/getWebhookInfo"
                    async with session.get(check_url) as check_response:
                        webhook_info = await check_response.json()
                        if check_response.status == 200 and webhook_info.get("ok"):
                            webhook_data = webhook_info.get("result", {})
                            url = webhook_data.get("url", "")
                            if url:
                                logger.warning(f"Вебхук все еще активен: {url}")
                            else:
                                logger.info("Подтверждено: вебхук отсутствует")
                            
                            # Выводим полную информацию о вебхуке
                            logger.info(f"Информация о вебхуке: {webhook_data}")
                            
                    return True
                else:
                    logger.error(f"Ошибка при удалении вебхука: {result}")
                    return False
    except Exception as e:
        logger.error(f"Ошибка при выполнении запроса: {e}")
        return False

if __name__ == "__main__":
    # Запускаем функцию удаления вебхука
    result = asyncio.run(remove_webhook())
    print(f"Результат: {'Успешно' if result else 'Ошибка'}")
    
    # Инструкции для пользователя
    print("\nЧто делать дальше:")
    print("1. Убедитесь, что в .env установлено USE_WEBHOOK=0")
    print("2. Запустите бота через python src/telegram/run_bot.py")
    print("3. Если проблема сохраняется, используйте BOT_DEBUG=1") 