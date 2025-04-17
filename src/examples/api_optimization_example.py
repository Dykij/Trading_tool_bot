import logging
import time
import os
import sys
from typing import Dict, Any

# Добавляем путь к корневой директории проекта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.utils.optimized_api_client import OptimizedDMarketAPI
from src.api.api_wrapper import DMarketAPI

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def compare_api_performance(api_key: str, api_secret: str, game: str = "csgo", iterations: int = 3):
    """
    Сравнивает производительность оригинального и оптимизированного API клиентов.
    
    Args:
        api_key: Ключ API DMarket
        api_secret: Секрет API DMarket
        game: Название игры для запросов (по умолчанию 'csgo')
        iterations: Количество итераций запросов
    """
    # Инициализация стандартного клиента
    standard_api = DMarketAPI(api_key, api_secret)
    
    # Инициализация оптимизированного клиента
    optimized_api = OptimizedDMarketAPI(api_key, api_secret)
    
    logger.info("Сравнение производительности API клиентов")
    logger.info("-" * 50)
    
    # Тест 1: Получение предметов с рынка
    test_get_market_items(standard_api, optimized_api, game, iterations)
    
    # Тест 2: Получение деталей предмета (повторяющиеся запросы)
    test_get_item_details(standard_api, optimized_api, game, iterations)
    
    # Вывод статистики оптимизированного API
    logger.info("-" * 50)
    logger.info("Статистика оптимизированного API:")
    stats = optimized_api.get_stats()
    for key, value in stats.items():
        if key == "average_response_time":
            logger.info(f"  {key}: {value:.4f} секунд")
        else:
            logger.info(f"  {key}: {value}")

def test_get_market_items(standard_api: DMarketAPI, optimized_api: OptimizedDMarketAPI, 
                         game: str, iterations: int):
    """Тестирует производительность метода get_market_items."""
    logger.info("\nТест: Получение предметов с рынка")
    
    # Тест стандартного API
    standard_time = time.time()
    for i in range(iterations):
        logger.info(f"Стандартный API: Итерация {i+1}/{iterations}")
        standard_api.get_market_items(game=game, limit=10)
    standard_elapsed = time.time() - standard_time
    
    # Тест оптимизированного API
    optimized_time = time.time()
    for i in range(iterations):
        logger.info(f"Оптимизированный API: Итерация {i+1}/{iterations}")
        optimized_api.get_market_items(game=game, limit=10)
    optimized_elapsed = time.time() - optimized_time
    
    # Вывод результатов
    logger.info(f"Стандартный API: {standard_elapsed:.2f} секунд")
    logger.info(f"Оптимизированный API: {optimized_elapsed:.2f} секунд")
    
    if standard_elapsed > 0:
        improvement = ((standard_elapsed - optimized_elapsed) / standard_elapsed) * 100
        logger.info(f"Улучшение производительности: {improvement:.2f}%")

def test_get_item_details(standard_api: DMarketAPI, optimized_api: OptimizedDMarketAPI, 
                         game: str, iterations: int):
    """Тестирует производительность получения деталей предмета с повторными запросами."""
    logger.info("\nТест: Повторные запросы деталей предмета")
    
    # Сначала получаем список предметов
    items = standard_api.get_market_items(game=game, limit=1)
    if not items or "objects" not in items or not items["objects"]:
        logger.error("Не удалось получить предметы для теста")
        return
    
    # Берем первый предмет для теста
    item_id = items["objects"][0]["itemId"]
    
    # Тест стандартного API
    standard_time = time.time()
    for i in range(iterations):
        logger.info(f"Стандартный API: Итерация {i+1}/{iterations}")
        standard_api.get_item_details(item_id=item_id)
    standard_elapsed = time.time() - standard_time
    
    # Тест оптимизированного API
    optimized_time = time.time()
    for i in range(iterations):
        logger.info(f"Оптимизированный API: Итерация {i+1}/{iterations}")
        optimized_api.get_item_details(item_id=item_id)
    optimized_elapsed = time.time() - optimized_time
    
    # Вывод результатов
    logger.info(f"Стандартный API: {standard_elapsed:.2f} секунд")
    logger.info(f"Оптимизированный API: {optimized_elapsed:.2f} секунд")
    
    if standard_elapsed > 0:
        improvement = ((standard_elapsed - optimized_elapsed) / standard_elapsed) * 100
        logger.info(f"Улучшение производительности: {improvement:.2f}%")

def test_cache_clearing(optimized_api: OptimizedDMarketAPI, game: str):
    """Тестирует очистку кэша."""
    logger.info("\nТест: Очистка кэша")
    
    # Делаем первый запрос (сохранится в кэш)
    logger.info("Первый запрос (будет кэширован)")
    first_result = optimized_api.get_market_items(game=game, limit=5)
    
    # Делаем второй запрос (должен быть из кэша)
    logger.info("Второй запрос (должен быть из кэша)")
    second_result = optimized_api.get_market_items(game=game, limit=5)
    
    # Проверяем статистику кэша
    stats_before = optimized_api.get_stats()
    logger.info(f"Количество обращений к кэшу до очистки: {stats_before['cache_hits']}")
    
    # Очищаем кэш
    logger.info("Очистка кэша...")
    optimized_api.clear_caches()
    
    # Делаем третий запрос (должен быть без кэша)
    logger.info("Третий запрос (после очистки кэша)")
    third_result = optimized_api.get_market_items(game=game, limit=5)
    
    # Проверяем, что кэш обновился после очистки
    stats_after = optimized_api.get_stats()
    logger.info(f"Количество запросов после очистки кэша: {stats_after['total_requests']}")
    logger.info(f"Количество обращений к кэшу после очистки: {stats_after['cache_hits']}")
    
    if stats_after['cache_hits'] > stats_before['cache_hits']:
        logger.info("Кэш успешно очищен и обновлен")
    else:
        logger.warning("Проблема с очисткой кэша!")

if __name__ == "__main__":
    # API ключи следует получить из конфигурации
    import os
    from dotenv import load_dotenv
    
    # Загрузка переменных окружения из .env файла
    load_dotenv()
    
    api_key = os.getenv("DMARKET_API_KEY")
    api_secret = os.getenv("DMARKET_API_SECRET")
    
    if not api_key or not api_secret:
        logger.error("Необходимо определить DMARKET_API_KEY и DMARKET_API_SECRET в .env файле")
        sys.exit(1)
    
    # Запуск сравнения
    compare_api_performance(api_key, api_secret, iterations=2)
    
    # Создаем клиент для теста очистки кэша
    optimized_api = OptimizedDMarketAPI(api_key, api_secret)
    test_cache_clearing(optimized_api, game="csgo") 