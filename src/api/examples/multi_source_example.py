"""
Пример использования многоисточникового провайдера рыночных данных.

Этот скрипт демонстрирует основные возможности модуля multi_source_market_provider
для работы с данными из нескольких торговых площадок и анализа арбитражных возможностей.
"""

import asyncio
import logging
from datetime import datetime
from tabulate import tabulate
import sys
import os

# Добавляем родительскую директорию в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.api.multi_source_market_provider import (
    get_multi_source_provider, find_arbitrage_opportunities
)

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_item_search():
    """Демонстрирует поиск предметов на нескольких площадках."""
    logger.info("=== Демонстрация поиска предметов ===")
    
    provider = get_multi_source_provider()
    query = "AK-47 Redline"
    
    logger.info(f"Поиск предмета '{query}' на всех площадках...")
    results = await provider.search_across_sources(
        game_code="a8db",  # CS2
        query=query,
        merge_results=True
    )
    
    # Выводим результаты в виде таблицы
    if results["total_items"] > 0:
        table_data = []
        for item in results["items"][:10]:  # Ограничиваем вывод 10 предметами
            price = item.get("price", {}).get("USD", "N/A")
            table_data.append([
                item.get("title", "Unknown"),
                price if isinstance(price, str) else f"${price:.2f}",
                item.get("source", "Unknown"),
                item.get("category", ""),
                item.get("rarity", "")
            ])
        
        headers = ["Название", "Цена", "Источник", "Категория", "Редкость"]
        print("\nРезультаты поиска:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        print(f"\nВсего найдено: {results['total_items']} предметов на {len(results['sources'])} площадках")
    else:
        print(f"Предметы по запросу '{query}' не найдены")
    
    print("\n")


async def demo_item_details():
    """Демонстрирует получение детальной информации о предмете."""
    logger.info("=== Демонстрация получения детальной информации о предмете ===")
    
    provider = get_multi_source_provider()
    item_name = "AWP | Asiimov"
    
    logger.info(f"Получение информации о предмете '{item_name}' из всех источников...")
    details = await provider.get_item_details(
        game_code="a8db",
        item_name=item_name
    )
    
    # Выводим общую информацию
    print(f"\nИнформация о предмете: {item_name}")
    print(f"Игра: {details['game']}")
    print(f"Источники данных: {', '.join(details['sources'])}")
    print(f"Временная метка: {details['timestamp']}")
    
    # Выводим статистику
    stats = details['stats']
    print("\nСтатистика:")
    stats_table = [
        ["Средняя цена", f"${stats['mean_price']:.2f}"],
        ["Медианная цена", f"${stats['median_price']:.2f}"],
        ["Минимальная цена", f"${stats['min_price']:.2f} ({stats['best_source']})"],
        ["Максимальная цена", f"${stats['max_price']:.2f}"],
        ["Волатильность", f"{stats['price_volatility']:.2f}"],
        ["Тренд цены", stats['price_trend']],
        ["Полнота данных", f"{stats['data_completeness']*100:.0f}%"],
        ["Достоверность", f"{stats['confidence_score']*100:.0f}%"]
    ]
    print(tabulate(stats_table, tablefmt="simple"))
    
    # Выводим цены из разных источников
    prices_table = []
    for source, info in details['info'].items():
        price = info.get("price", {}).get("USD", "N/A")
        if "error" in info:
            prices_table.append([source, "Error", info["error"]])
        else:
            prices_table.append([
                source, 
                price if isinstance(price, str) else f"${price:.2f}",
                "✓"
            ])
    
    print("\nЦены по источникам:")
    print(tabulate(prices_table, headers=["Источник", "Цена", "Статус"], tablefmt="grid"))
    
    # Выводим краткую историю цен
    print("\nПоследние данные истории цен:")
    history_table = []
    
    for source, history in details['price_history'].items():
        if isinstance(history, list) and history and "error" not in history[0]:
            # Берем только последние 3 записи для краткости
            for entry in history[:3]:
                history_table.append([
                    source,
                    entry.get("date", "Unknown"),
                    f"${entry.get('price', 0):.2f}",
                    entry.get("volume", "N/A")
                ])
    
    if history_table:
        print(tabulate(history_table, 
                     headers=["Источник", "Дата", "Цена", "Объем"], 
                     tablefmt="simple"))
    else:
        print("История цен недоступна")
    
    print("\n")


async def demo_arbitrage():
    """Демонстрирует поиск арбитражных возможностей."""
    logger.info("=== Демонстрация поиска арбитражных возможностей ===")
    
    logger.info("Поиск арбитражных возможностей с разницей не менее 7%...")
    opportunities = await find_arbitrage_opportunities(
        game_code="a8db",
        min_price_diff=7.0,
        limit=5
    )
    
    if opportunities:
        # Выводим найденные возможности в виде таблицы
        table_data = []
        for opp in opportunities:
            table_data.append([
                opp['item_name'],
                f"${opp['buy_price']:.2f}",
                opp['buy_from'],
                f"${opp['sell_price']:.2f}",
                opp['sell_to'],
                f"${opp['price_diff']:.2f}",
                f"{opp['price_diff_percent']:.2f}%",
                opp['profit_potential']
            ])
        
        headers = ["Предмет", "Цена покупки", "Откуда", "Цена продажи", 
                  "Куда", "Разница", "Разница %", "Потенциал"]
        print("\nНайденные арбитражные возможности:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("\nАрбитражные возможности не найдены")
    
    print("\n")


async def main():
    """Основная функция для запуска демонстрации."""
    print("\n=== ДЕМОНСТРАЦИЯ МНОГОИСТОЧНИКОВОГО ПРОВАЙДЕРА РЫНОЧНЫХ ДАННЫХ ===\n")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Демонстрируем поиск предметов
        await demo_item_search()
        
        # Демонстрируем получение детальной информации
        await demo_item_details()
        
        # Демонстрируем поиск арбитражных возможностей
        await demo_arbitrage()
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении демонстрации: {e}", exc_info=True)
    
    print("=== ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА ===\n")


if __name__ == "__main__":
    # Запускаем демонстрацию
    asyncio.run(main()) 