import os
import sys
import json
import logging
import asyncio
import socket
import aiohttp
import ssl
from aiohttp import ClientSession
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("network_test")

# Telegram API endpoints
TELEGRAM_API_HOST = "api.telegram.org"
TELEGRAM_API_URL = f"https://{TELEGRAM_API_HOST}"

async def test_api_connection():
    """Проверяет доступность Telegram API через разные методы"""
    print(f"\n=== Проверка соединения с Telegram API ({TELEGRAM_API_URL}) ===")
    
    # 1. Проверяем разрешение DNS
    try:
        print(f"\nШаг 1: Проверка DNS-разрешения для {TELEGRAM_API_HOST}")
        ip_addresses = socket.gethostbyname_ex(TELEGRAM_API_HOST)
        print(f"DNS-разрешение успешно. IP-адреса: {ip_addresses[2]}")
    except Exception as e:
        print(f"Ошибка DNS-разрешения: {e}")
        return False
    
    # 2. Проверяем TCP-соединение на порту 443
    try:
        print(f"\nШаг 2: Проверка TCP-соединения с {TELEGRAM_API_HOST}:443")
        for ip in ip_addresses[2]:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            print(f"Попытка подключения к {ip}:443...")
            result = sock.connect_ex((ip, 443))
            if result == 0:
                print(f"TCP-соединение с {ip}:443 установлено успешно!")
                sock.close()
                break
            else:
                print(f"Не удалось установить TCP-соединение с {ip}:443. Код ошибки: {result}")
                sock.close()
        else:
            print("Не удалось установить TCP-соединение ни с одним из IP-адресов")
            return False
    except Exception as e:
        print(f"Ошибка при проверке TCP-соединения: {e}")
        return False
    
    # 3. Проверяем HTTP-запрос
    try:
        print(f"\nШаг 3: Выполнение HTTP-запроса к {TELEGRAM_API_URL}")
        async with ClientSession() as session:
            async with session.get(f"{TELEGRAM_API_URL}/") as response:
                print(f"HTTP-запрос выполнен. Статус: {response.status}")
                print(f"Заголовки ответа: {dict(response.headers)}")
                return response.status == 200
    except aiohttp.ClientError as e:
        print(f"Ошибка HTTP-запроса: {e}")
        return False
    except Exception as e:
        print(f"Неизвестная ошибка: {e}")
        return False

async def test_bot_token():
    """Проверяет валидность токена бота"""
    load_dotenv()
    
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        print("\nОШИБКА: Токен бота не найден в переменных окружения")
        return False
        
    print(f"\n=== Проверка токена бота ===")
    print(f"Токен: {token[:5]}...{token[-5:]} (скрыт)")
    
    try:
        # Проверяем токен через метод getMe
        async with ClientSession() as session:
            async with session.get(f"{TELEGRAM_API_URL}/bot{token}/getMe") as response:
                result = await response.json()
                if response.status == 200 and result.get("ok"):
                    bot_info = result.get("result", {})
                    print(f"Токен валиден! Информация о боте:")
                    print(f"ID: {bot_info.get('id')}")
                    print(f"Имя: {bot_info.get('first_name')}")
                    print(f"Username: @{bot_info.get('username')}")
                    return True
                else:
                    print(f"Ошибка проверки токена: {result}")
                    return False
    except Exception as e:
        print(f"Ошибка при проверке токена: {e}")
        return False

async def test_get_updates():
    """Тестирует получение обновлений от Telegram API"""
    load_dotenv()
    
    # Получаем токен из переменных окружения
    token = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN")
    if not token:
        print("\nОШИБКА: Токен бота не найден в переменных окружения")
        return False
        
    print(f"\n=== Тестирование метода getUpdates ===")
    
    try:
        # Проверяем с разными таймаутами
        for timeout in [1, 5, 30]:
            print(f"\nПопытка получения обновлений с таймаутом {timeout} сек...")
            
            # Создаем сессию с увеличенным таймаутом
            timeout_obj = aiohttp.ClientTimeout(total=timeout + 10)
            async with ClientSession(timeout=timeout_obj) as session:
                try:
                    async with session.get(
                        f"{TELEGRAM_API_URL}/bot{token}/getUpdates",
                        params={"timeout": timeout, "limit": 1, "offset": -1}
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            if result.get("ok"):
                                updates = result.get("result", [])
                                print(f"Успешно получены обновления (таймаут {timeout}с)")
                                print(f"Количество обновлений: {len(updates)}")
                                if updates:
                                    print(f"Пример обновления: {json.dumps(updates[0], indent=2)}")
                            else:
                                print(f"Ошибка в ответе API: {result}")
                        else:
                            print(f"Ошибка HTTP: {response.status}")
                except asyncio.TimeoutError:
                    print(f"Превышен таймаут запроса ({timeout + 10}с)")
                except Exception as e:
                    print(f"Ошибка при получении обновлений: {e}")
        
        return True
    except Exception as e:
        print(f"Неожиданная ошибка: {e}")
        return False

async def main():
    """Запускает все тесты последовательно"""
    print("=== Запуск диагностики сетевого подключения к Telegram API ===")
    
    # Проверяем базовое соединение с API
    if not await test_api_connection():
        print("\n❌ Проблемы с подключением к Telegram API")
        print("Рекомендации:")
        print("1. Проверьте интернет-соединение")
        print("2. Проверьте настройки брандмауэра")
        print("3. Попробуйте использовать VPN")
        return
    
    # Проверяем токен бота
    if not await test_bot_token():
        print("\n❌ Проблемы с токеном бота")
        print("Рекомендации:")
        print("1. Проверьте корректность токена в .env файле")
        print("2. Убедитесь, что бот не был удален или заблокирован")
        return
    
    # Проверяем получение обновлений
    await test_get_updates()
    
    print("\n=== Диагностика завершена ===")
    print("Рекомендации на основе результатов:")
    print("1. Если тесты пройдены успешно, проблема может быть в коде бота")
    print("2. Если тест getUpdates не удался, попробуйте использовать вебхуки")
    print("3. Если соединение нестабильно, попробуйте VPN или прокси")

if __name__ == "__main__":
    asyncio.run(main()) 