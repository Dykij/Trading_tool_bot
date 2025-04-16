#!/usr/bin/env python
"""
Тестовый скрипт для проверки работы скрапера CS2 и его интеграции с торговым фасадом.
"""

import asyncio
import logging
import sys
from pprint import pprint

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("test_cs2_scraper")

async def test_cs2_scraper():
    """Тестирует функциональность скрапера CS2."""
    logger.info("Запуск тестирования скрапера CS2")
    
    try:
        # Импортируем скрапер напрямую из модуля
        import src.scrapers.cs2_scraper as cs2_module
        CS2Scraper = cs2_module.CS2Scraper
        
        # Создаем экземпляр скрапера
        scraper = CS2Scraper(
            cache_ttl=3600,  # 1 час
            request_delay=0.5,
            max_retries=3
        )
        
        logger.info("Скрапер CS2 успешно создан")
        
        # Тестируем получение списка предметов
        logger.info("Получение популярных предметов CS2...")
        items = await scraper.get_popular_items(limit=5)
        
        if items:
            logger.info(f"Успешно получено {len(items)} популярных предметов:")
            for i, item in enumerate(items, 1):
                logger.info(f"  {i}. {item.get('name')} - ${item.get('price', 0):.2f} ({item.get('category', 'unknown')})")
        else:
            logger.warning("Не удалось получить популярные предметы")
        
        # Тестируем поиск по названию
        search_query = "AK-47"
        logger.info(f"Поиск предметов по запросу '{search_query}'...")
        search_results = await scraper.search_items(search_query, limit=3)
        
        if search_results:
            logger.info(f"Успешно найдено {len(search_results)} предметов по запросу '{search_query}':")
            for i, item in enumerate(search_results, 1):
                logger.info(f"  {i}. {item.get('name')} - ${item.get('price', 0):.2f}")
        else:
            logger.warning(f"Не удалось найти предметы по запросу '{search_query}'")
        
        # Если есть результаты поиска, тестируем получение деталей предмета
        if search_results:
            first_item = search_results[0]
            item_name = first_item.get('name')
            logger.info(f"Получение деталей предмета '{item_name}'...")
            
            details = await scraper.get_item_details(item_name)
            if details:
                logger.info(f"Успешно получены детали предмета '{item_name}'")
                if 'price_trend' in details:
                    trend = details['price_trend']
                    logger.info(f"  Тренд цены: {trend.get('change', 0):.2f} USD ({trend.get('change_percent', 0):.2f}%), направление: {trend.get('trend', 'unknown')}")
            else:
                logger.warning(f"Не удалось получить детали предмета '{item_name}'")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при тестировании скрапера CS2: {e}", exc_info=True)
        return False

async def test_trading_facade():
    """Тестирует интеграцию скрапера CS2 с торговым фасадом."""
    logger.info("Запуск тестирования интеграции с торговым фасадом")
    
    try:
        # Импортируем торговый фасад
        from src.trading.trading_facade import get_trading_service
        
        # Получаем экземпляр торгового фасада
        trading_service = get_trading_service()
        
        # Инициализируем торговый фасад
        logger.info("Инициализация торгового фасада...")
        await trading_service.initialize()
        
        # Тестируем получение данных рынка CS2
        logger.info("Получение данных рынка CS2...")
        market_data = await trading_service.get_cs2_market_data(limit=10)
        
        if market_data and 'items' in market_data:
            items = market_data['items']
            logger.info(f"Успешно получено {len(items)} предметов CS2:")
            for i, item in enumerate(items[:5], 1):  # Показываем только первые 5
                logger.info(f"  {i}. {item.get('name')} - ${item.get('price', 0):.2f} ({item.get('market', '')})")
        else:
            logger.warning("Не удалось получить данные рынка CS2")
        
        # Тестируем поиск арбитражных возможностей
        logger.info("Поиск арбитражных возможностей для CS2...")
        opportunities = await trading_service.find_cs2_arbitrage_opportunities()
        
        if opportunities:
            logger.info(f"Успешно найдено {len(opportunities)} арбитражных возможностей:")
            for i, op in enumerate(opportunities[:3], 1):  # Показываем только первые 3
                logger.info(f"  {i}. {op.get('item_name')} - Прибыль: ${op.get('profit_amount', 0):.2f} ({op.get('profit_percent', 0):.2f}%)")
                logger.info(f"     Покупка: {op.get('buy_market')} по ${op.get('buy_price', 0):.2f}")
                logger.info(f"     Продажа: {op.get('sell_market')} по ${op.get('sell_price', 0):.2f}")
        else:
            logger.warning("Не удалось найти арбитражные возможности для CS2")
        
        return True
    except Exception as e:
        logger.error(f"Ошибка при тестировании интеграции с торговым фасадом: {e}", exc_info=True)
        return False

async def main():
    """Основная функция для запуска тестов."""
    logger.info("=== Начало тестирования CS2 скрапера и интеграции ===")
    
    # Тестируем скрапер CS2
    scraper_success = await test_cs2_scraper()
    logger.info(f"Тестирование скрапера CS2: {'УСПЕШНО' if scraper_success else 'НЕУДАЧНО'}")
    
    # Тестируем интеграцию с торговым фасадом
    facade_success = await test_trading_facade()
    logger.info(f"Тестирование интеграции с торговым фасадом: {'УСПЕШНО' if facade_success else 'НЕУДАЧНО'}")
    
    logger.info("=== Тестирование завершено ===")
    
    return scraper_success and facade_success

if __name__ == "__main__":
    # Запускаем асинхронную функцию в событийном цикле
    success = asyncio.run(main())
    
    # Завершаем программу с соответствующим кодом
    sys.exit(0 if success else 1) 