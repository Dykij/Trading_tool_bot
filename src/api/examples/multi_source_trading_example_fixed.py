"""
Пример использования многоисточникового трейдера.

Этот скрипт демонстрирует, как использовать MultiSourceTrader для автоматизации
арбитражной торговли между разными маркетплейсами.
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Добавляем родительскую директорию в PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tabulate import tabulate

from src.api.multi_source_trading import find_and_execute_trades, get_multi_source_trader

# Настраиваем логирование
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def demo_scan_for_opportunities():
    """Демонстрирует поиск арбитражных возможностей."""
    logger.info("=== Демонстрация поиска арбитражных возможностей ===")
    
    # Получаем экземпляр трейдера
    trader = get_multi_source_trader(min_profit_percent=5.0)
    
    # Сканируем рынок
    logger.info("Сканирование рынка на наличие арбитражных возможностей...")
    opportunities = await trader.scan_for_opportunities(
        game_code="a8db",  # CS2
        max_items=20,
        min_price=10.0,    # Минимальная цена предмета
        max_price=100.0    # Максимальная цена предмета
    )
    # Выводим результаты
    if opportunities:
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
                f"{opp['risk_level']} ({opp['risk_score']:.2f})"
            ])
        
        headers = ["Предмет", "Цена покупки", "Откуда", "Цена продажи",
                   "Куда", "Разница", "Разница %", "Риск"]
        
        print("\nНайденные арбитражные возможности:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print(f"\nВсего найдено: {len(opportunities)} возможностей")
    else:
        print("\nАрбитражные возможности не найдены")
    
    print("\n")


async def demo_trade_execution(auto_execute: bool = False):
    """
    Демонстрирует выполнение сделок.
    
    Args:
        auto_execute: Автоматически выполнять сделки без подтверждения
    """
    logger.info("=== Демонстрация выполнения сделок ===")
    
    # Выполняем сделки (в демо-режиме они будут только имитироваться)
    logger.info("Поиск и выполнение выгодных сделок...")
    trades = await find_and_execute_trades(
        game_code="a8db",
        min_profit=7.0,      # Минимальный процент прибыли
        max_trades=2,        # Максимальное количество сделок
        auto_execute=auto_execute  # Автоматическое выполнение или с подтверждением
    )
    
    # Выводим результаты
    if trades:
        table_data = []
        for trade in trades:
            if trade.get("status") == "failed":
                table_data.append([
                    trade['item_name'],
                    "ОШИБКА",
                    "-",
                    "-",
                    "-",
                    trade.get('error', 'Неизвестная ошибка'),
                    trade['timestamp']
                ])
            else:
                table_data.append([
                    trade['item_name'],
                    f"${trade['buy_price']:.2f} ({trade['buy_source']})",
                    f"${trade['sell_price']:.2f} ({trade['sell_source']})",
                    f"${trade['profit']:.2f}",
                    f"{trade['profit_percent']:.2f}%",
                    trade['status'],
                    trade['timestamp']
                ])
        
        headers = ["Предмет", "Покупка", "Продажа", "Прибыль", "Прибыль %", "Статус", "Время"]
        
        print("\nВыполненные сделки:")
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        
        # Получаем статистику
        trader = get_multi_source_trader()
        stats = await trader.get_trading_statistics()
        
        print("\nСтатистика торговли:")
        stats_table = [
            ["Всего сделок", f"{stats['total_trades']}"],
            ["Успешных сделок", f"{stats['successful_trades']} ({stats['success_rate']:.1f}%)"],
            ["Общая прибыль", f"${stats['total_profit']:.2f}"],
            ["Средняя прибыль", f"${stats['average_profit_per_trade']:.2f} за сделку"],
            ["Сделок за 24ч", f"{stats['last_24h_trades']} (${stats['last_24h_profit']:.2f})"],
            ["Последняя сделка", f"{stats['last_trade_time']}"]
        ]
        print(tabulate(stats_table, tablefmt="simple"))
        
        if stats['top_profitable_items']:
            print("\nСамые прибыльные предметы:")
            top_items = []
            for item in stats['top_profitable_items']:
                top_items.append([item['item'], f"${item['profit']:.2f}"])
            print(tabulate(top_items, headers=["Предмет", "Общая прибыль"], tablefmt="simple"))
    else:
        print("\nНе было выполнено ни одной сделки")
    
    print("\n")


async def main():
    """Основная функция для запуска демонстрации."""
    print("\n=== ДЕМОНСТРАЦИЯ МНОГОИСТОЧНИКОВОГО ТРЕЙДЕРА ===\n")
    print(f"Время запуска: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    try:
        # Демонстрируем поиск возможностей
        await demo_scan_for_opportunities()
        
        # Демонстрируем выполнение сделок
        # В интерактивном режиме (с подтверждением каждой сделки)
        await demo_trade_execution(auto_execute=False)
        
        # В автоматическом режиме
        # await demo_trade_execution(auto_execute=True)
        
    except Exception as e:
        logger.error(f"Ошибка при выполнении демонстрации: {e}", exc_info=True)
    
    print("=== ДЕМОНСТРАЦИЯ ЗАВЕРШЕНА ===\n")


if __name__ == "__main__":
    # Запускаем демонстрацию
    asyncio.run(main())
