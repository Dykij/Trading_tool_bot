"""
Основной модуль для запуска торгового бота DMarket.

Содержит точку входа в приложение, инициализацию основных компонентов и
запуск телеграм-бота для интерактивного взаимодействия с системой.

Модуль обеспечивает:
1. Парсинг аргументов командной строки для различных режимов работы
2. Анализ рыночных возможностей и поиск арбитража
3. Мониторинг рынка и оповещения о выгодных сделках
4. Управление отложенными ордерами (таргетами)
5. Запуск телеграм-бота для управления торговой системой

Для использования необходимо настроить переменные окружения в файле .env
"""

import os
import asyncio
import logging
import sys
from datetime import datetime
import argparse
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
import json
import time

from api_wrapper import DMarketAPI
from utils.api_adapter import DMarketAdapter
from bellman_ford import create_graph, find_arbitrage_advanced, ArbitrageResult, filter_arbitrage_opportunities
from linear_programming import get_optimized_allocation, optimize_portfolio
from utils.market_analyzer import find_arbitrage_opportunities, analyze_historical_trends, get_analyzer
import utils.market_analyzer  # Импортируем для доступа через utils.market_analyzer.get_analyzer()
from utils.database import get_most_profitable_items
from telegram_bot import dp, bot, on_startup
from utils.marketplace_integrator import MarketplaceIntegrator

# Загрузка переменных окружения
load_dotenv()

# Инициализация логирования напрямую
def setup_logging(logger_name, log_file=None):
    """Настраивает и возвращает логгер с заданным именем"""
    if log_file is None:
        # Создаем директорию для логов, если отсутствует
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        log_file = os.path.join(log_dir, f"{logger_name}.log")
    
    # Создаем логгер
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.INFO)
    
    # Очищаем обработчики, если они уже были добавлены
    if logger.handlers:
        logger.handlers.clear()
    
    # Форматирование сообщений лога
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый обработчик
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

# Инициализация логирования
logger = setup_logging('main', 'logs/main.log')

# Глобальный экземпляр API адаптера
api_adapter = None

def parse_arguments() -> argparse.Namespace:
    """
    Парсит аргументы командной строки для настройки работы приложения.
    
    Обрабатывает следующие группы аргументов:
    - Общие параметры запуска (телеграм-бот, анализ, мониторинг)
    - Параметры анализа рынка (уровень риска, бюджет)
    - Параметры автоматической торговли (игра, минимальная прибыль)
    - Управление отложенными ордерами (создание, мониторинг, исполнение)
    
    Returns:
        argparse.Namespace: Объект с аргументами командной строки
    
    Examples:
        $ python main.py --telegram
        $ python main.py --analyze --risk=medium --budget=1000
        $ python main.py --watch --interval=300
        $ python main.py --auto_trade --game=cs2 --min_profit=5.0
    """
    parser = argparse.ArgumentParser(description='DMarket Trading Bot')
    
    parser.add_argument('--telegram', '-t', action='store_true',
                      help='Запустить телеграм-бота')
    
    parser.add_argument('--analyze', '-a', action='store_true',
                      help='Выполнить анализ рынка и найти арбитражные возможности')
    
    parser.add_argument('--risk', '-r', choices=['low', 'medium', 'high'], default='medium',
                      help='Уровень риска для анализа (low, medium, high)')
    
    parser.add_argument('--budget', '-b', type=float, default=1000.0,
                      help='Бюджет для оптимизации торговых стратегий')
    
    parser.add_argument('--output', '-o', type=str, default='results',
                      help='Директория для сохранения результатов анализа')
    
    parser.add_argument('--watch', '-w', action='store_true',
                      help='Запустить непрерывный мониторинг рынка')
    
    parser.add_argument('--interval', '-i', type=int, default=300,
                      help='Интервал обновления данных в секундах при мониторинге')
    
    parser.add_argument('--verbose', '-v', action='count', default=0,
                      help='Уровень подробности вывода (чем больше -v, тем подробнее)')
    
    parser.add_argument('--auto_trade', action='store_true',
                      help='Запустить автоматическую арбитражную торговлю между площадками')
    
    parser.add_argument('--game', choices=['cs2', 'dota2', 'tf2'], default='cs2',
                      help='Игра для автоматической торговли (cs2, dota2, tf2)')
    
    parser.add_argument('--min_profit', type=float, default=5.0,
                      help='Минимальный процент прибыли для арбитражной торговли')
    
    parser.add_argument('--execute', action='store_true',
                      help='Выполнять реальные транзакции (по умолчанию только симуляция)')
    
    parser.add_argument('--max_executions', type=int, default=5,
                      help='Максимальное количество торговых операций')
    
    # Аргументы для работы с отложенными ордерами (таргетами)
    parser.add_argument('--target_create', action='store_true',
                      help='Создать отложенные ордера (таргеты) для арбитражной стратегии')
    
    parser.add_argument('--target_monitor', action='store_true',
                      help='Запустить мониторинг отложенных ордеров')
    
    parser.add_argument('--target_list', action='store_true',
                      help='Показать список отложенных ордеров')
    
    parser.add_argument('--target_cancel', type=str, metavar='TARGET_ID',
                      help='Отменить отложенный ордер по ID')
    
    parser.add_argument('--target_execute', type=str, metavar='TARGET_ID',
                      help='Выполнить отложенный ордер по ID')
    
    parser.add_argument('--max_targets', type=int, default=5,
                      help='Максимальное количество отложенных ордеров для создания')
    
    parser.add_argument('--max_wait_hours', type=int, default=24,
                      help='Максимальное время ожидания для отложенных ордеров в часах')
    
    parser.add_argument('--auto_execute', action='store_true',
                      help='Автоматически выполнять отложенные ордера по истечении срока')
    
    # Аргументы для распределенного анализа
    parser.add_argument('--distributed', action='store_true',
                      help='Использовать распределенный анализ для повышения производительности')
    
    parser.add_argument('--use_processes', action='store_true',
                      help='Использовать процессы вместо потоков для распределенного анализа')
    
    # Аргумент для указания категорий предметов
    parser.add_argument('--categories', type=str, nargs='+',
                      help='Категории предметов для анализа (например: knife, rifle, pistol)')
    
    return parser.parse_args()

def init_api_adapter() -> DMarketAdapter:
    """
    Инициализирует API адаптер для взаимодействия с DMarket.
    
    Функция создает и возвращает глобальный экземпляр API адаптера,
    который используется для всех взаимодействий с DMarket API.
    Загружает ключи API из переменных окружения (.env файла).
    
    Returns:
        DMarketAdapter: Экземпляр адаптера API для DMarket
        
    Raises:
        SystemExit: Если отсутствуют необходимые API ключи
        
    Note:
        Функция использует глобальную переменную api_adapter для кеширования
        экземпляра адаптера между вызовами.
    """
    global api_adapter
    
    # Возвращаем существующий адаптер, если он уже был инициализирован
    if api_adapter is not None:
        return api_adapter
    
    # Получаем API ключи из переменных окружения
    api_key = os.getenv('DMARKET_API_KEY')
    api_secret = os.getenv('DMARKET_API_SECRET')
    api_url = os.getenv('DMARKET_API_URL', 'https://api.dmarket.com')
    
    # Проверяем наличие обязательных ключей
    if not api_key or not api_secret:
        logger.error("Отсутствуют API ключи DMarket в .env файле")
        sys.exit(1)
    
    # Создаем экземпляр адаптера с настройками кеширования
    cache_ttl = int(os.getenv('CACHE_TTL', '300'))
    api_adapter = DMarketAdapter(api_key=api_key, api_secret=api_secret, use_cache=True)
    
    logger.info("API адаптер инициализирован")
    return api_adapter

async def analyze_market(risk_level: str = "medium", budget: float = 1000.0, output_dir: str = "results", use_distributed: bool = False, use_processes: bool = False, categories: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Анализирует рынок и оптимизирует торговые стратегии.

    Выполняет комплексный анализ рыночных данных для выявления арбитражных возможностей
    в соответствии с заданным уровнем риска и бюджетом. Результаты анализа
    сохраняются в указанной директории в формате JSON.

    Args:
        risk_level: Уровень риска для анализа ("low", "medium", "high")
        budget: Бюджет для оптимизации торговой стратегии в USD
        output_dir: Директория для сохранения результатов анализа
        use_distributed: Использовать распределенный анализ
        use_processes: Использовать процессы вместо потоков
        categories: Список категорий предметов для анализа

    Returns:
        Dict[str, Any]: Словарь с результатами анализа, содержащий:
            - status: Статус выполнения ("success", "warning", "error")
            - message: Сообщение о результате (при наличии ошибок)
            - timestamp: Время выполнения анализа
            - opportunities_count: Количество найденных возможностей
            - top_opportunities: Список наиболее выгодных возможностей
            - optimization: Результаты оптимизации торговой стратегии

    Raises:
        Exception: При возникновении ошибок анализа или оптимизации
    """
    logger.info(f"Начало анализа рынка с уровнем риска '{risk_level}' и бюджетом {budget}" + 
                (", используя распределенный анализ" if use_distributed else ""))
    if categories:
        logger.info(f"Выбранные категории предметов: {', '.join(categories)}")
    
    # Инициализируем API адаптер
    adapter = init_api_adapter()
    if not adapter:
        return {
            "status": "error",
            "message": "Не удалось инициализировать API адаптер",
            "timestamp": datetime.now().isoformat()
        }
    
    # Настройка параметров в зависимости от уровня риска
    risk_settings = {
        "low": {"min_profit": 3.0, "min_liquidity": 5.0, "max_items": 300},
        "medium": {"min_profit": 1.5, "min_liquidity": 2.0, "max_items": 500},
        "high": {"min_profit": 0.5, "min_liquidity": 1.0, "max_items": 800}
    }
    
    settings = risk_settings.get(risk_level, risk_settings["medium"])
    
    try:
        # Создаем директорию для результатов, если её нет
        os.makedirs(output_dir, exist_ok=True)
        
        # Получаем анализатор рынка
        analyzer = get_analyzer()
        
        # Если api_key и api_secret еще не установлены в анализаторе, устанавливаем их
        if not analyzer.api:
            api_key = os.getenv('DMARKET_API_KEY')
            api_secret = os.getenv('DMARKET_API_SECRET')
            if api_key and api_secret:
                analyzer.init_api(api_key, api_secret)
                logger.info("API ключи установлены в анализаторе")
        
        # Установка параметров анализатора
        analyzer.params.load_from_dict({
            "min_profit": settings["min_profit"] / 100.0,  # Конвертируем проценты в доли
            "min_liquidity": settings["min_liquidity"],
            "max_opportunities": 50,  # Количество возможностей для анализа
            "cache_ttl_base": 600,  # Базовое время жизни кэша (10 минут)
            "min_price": 1.0,  # Минимальная цена предмета для анализа
            "max_price": 1000.0,  # Максимальная цена предмета для анализа
            "analyze_time": 60.0  # Ожидаемое время анализа (для адаптивного кэширования)
        })
        
        # Анализируем рынок
        logger.info("Запуск анализа рынка с параметрами: " + 
                   f"min_profit={settings['min_profit']}%, min_liquidity={settings['min_liquidity']}")
        
        start_time = time.time()
        
        # Используем find_best_opportunities для поиска арбитражных возможностей
        opportunities = await analyzer.find_best_opportunities(
            game_id='a8db',  # CS2 по умолчанию
            limit=settings["max_items"],
            budget=budget,
            min_profit=settings["min_profit"],
            force_refresh=True,  # Принудительное обновление для анализа
            use_distributed=use_distributed,  # Распределенный анализ
            categories=categories  # Добавляем передачу категорий
        )
        
        analysis_time = time.time() - start_time
        logger.info(f"Анализ рынка завершен за {analysis_time:.2f} секунд")
        
        if not opportunities:
            return {
                "status": "warning",
                "message": "Не найдено арбитражных возможностей при текущих параметрах",
                "timestamp": datetime.now().isoformat(),
                "analysis_time": analysis_time,
                "parameters": {
                    "risk_level": risk_level,
                    "budget": budget,
                    "min_profit": settings["min_profit"],
                    "min_liquidity": settings["min_liquidity"],
                    "categories": categories
                },
                "opportunities_count": 0,
                "top_opportunities": []
            }
        
        # Сортируем возможности по прибыли
        opportunities.sort(key=lambda x: x.get("profit_percent", 0), reverse=True)
        
        # Добавляем описание пути для удобства
        for opp in opportunities:
            path = opp.get("path", [])
            opp["path_description"] = " -> ".join(path) if path else ""
        
        # Оптимизируем портфель с использованием линейного программирования
        try:
            # Подготавливаем данные для оптимизации
            items_data = [{
                "id": opp.get("id", str(i)),
                "name": opp.get("path_description", f"Opportunity {i}"),
                "price": budget / 10,  # Предполагаем, что используем 1/10 бюджета на каждую возможность
                "expected_return": opp.get("profit_percent", 0) / 100.0,  # Конвертируем проценты в доли
                "risk": 1.0 - min(opp.get("liquidity", 1.0) / 10.0, 0.9),  # Оценка риска на основе ликвидности
                "min_amount": 0,  # Минимальное количество (0 = не обязательно включать)
                "max_amount": int(budget / (budget / 10))  # Максимальное количество ограничено бюджетом
            } for i, opp in enumerate(opportunities[:20])]  # Берем только топ-20 для оптимизации
            
            # Запускаем оптимизацию
            portfolio = optimize_portfolio(
                items=items_data,
                total_budget=budget,
                risk_tolerance={"low": 0.2, "medium": 0.5, "high": 0.8}.get(risk_level, 0.5)
            )
            
            # Формируем результат анализа
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "analysis_time": analysis_time,
                "parameters": {
                    "risk_level": risk_level,
                    "budget": budget,
                    "min_profit": settings["min_profit"],
                    "min_liquidity": settings["min_liquidity"],
                    "categories": categories
                },
                "opportunities_count": len(opportunities),
                "top_opportunities": opportunities[:10],  # Возвращаем только топ-10 для отображения
                "optimization": {
                    "expected_return": portfolio.get("expected_return", 0) * 100,  # В процентах
                    "risk_level": portfolio.get("portfolio_risk", 0),
                    "allocated_budget": portfolio.get("allocated_budget", 0),
                    "items": portfolio.get("items", [])
                }
            }
        except Exception as e:
            logger.error(f"Ошибка при оптимизации портфеля: {str(e)}")
            
            # Возвращаем результат без оптимизации
            return {
                "status": "success",
                "timestamp": datetime.now().isoformat(),
                "analysis_time": analysis_time,
                "parameters": {
                    "risk_level": risk_level,
                    "budget": budget,
                    "min_profit": settings["min_profit"],
                    "min_liquidity": settings["min_liquidity"],
                    "categories": categories
                },
                "opportunities_count": len(opportunities),
                "top_opportunities": opportunities[:10],
                "optimization": None,
                "error": str(e)
            }
    
    except Exception as e:
        logger.error(f"Ошибка при анализе рынка: {str(e)}")
        return {
            "status": "error",
            "message": f"Ошибка при анализе рынка: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

async def watch_market(interval: int = 300, risk_level: str = "medium", budget: float = 1000.0, output_dir: str = "results"):
    """
    Запускает непрерывный мониторинг рынка с заданным интервалом.
    
    Args:
        interval: Интервал обновления данных в секундах
        risk_level: Уровень риска для анализа
        budget: Бюджет для оптимизации
        output_dir: Директория для сохранения результатов
    """
    logger.info(f"Запуск непрерывного мониторинга рынка с интервалом {interval} секунд")
    
    # Создаем директорию для результатов, если она не существует
    os.makedirs(output_dir, exist_ok=True)
    
    try:
        while True:
            # Выполняем анализ рынка
            result = await analyze_market(risk_level, budget, output_dir)
            
            if result["status"] == "success":
                logger.info(f"Анализ рынка успешно завершен, найдено {result['opportunities_count']} возможностей")
                
                # Если есть прибыльные возможности и настроены уведомления, отправляем их
                if result.get("opportunities_count", 0) > 0 and os.getenv('ENABLE_NOTIFICATIONS', 'false').lower() == 'true':
                    await send_notifications(result)
            else:
                logger.warning(f"Анализ рынка завершен с предупреждением: {result.get('message', 'Неизвестная ошибка')}")
            
            # Ожидаем заданный интервал перед следующим обновлением
            logger.debug(f"Ожидание {interval} секунд до следующего обновления")
            await asyncio.sleep(interval)
    
    except KeyboardInterrupt:
        logger.info("Мониторинг остановлен пользователем")
    except Exception as e:
        logger.error(f"Ошибка при мониторинге рынка: {e}", exc_info=True)

async def send_notifications(analysis_result: Dict[str, Any]):
    """
    Отправляет уведомления о найденных арбитражных возможностях.
    
    Args:
        analysis_result: Результаты анализа рынка
    """
    # Проверяем наличие необходимых данных
    if analysis_result.get("status") != "success" or not analysis_result.get("top_opportunities"):
        return
    
    try:
        # Получаем ID чата администратора из переменных окружения
        admin_chat_id = os.getenv('ADMIN_CHAT_ID')
        if not admin_chat_id:
            logger.warning("ADMIN_CHAT_ID не указан, уведомления не будут отправлены")
            return
        
        # Формируем сообщение с найденными возможностями
        message = "🔍 <b>Найдены новые арбитражные возможности:</b>\n\n"
        
        for i, opp in enumerate(analysis_result["top_opportunities"][:3], 1):
            risk_indicator = "🟢" if opp.get('risk_score', 50) < 30 else "🟡" if opp.get('risk_score', 50) < 60 else "🔴"
            cycle_str = " → ".join(opp.get('cycle', []))
            
            message += (
                f"{i}. {risk_indicator} <b>{cycle_str}</b>\n"
                f"   Прибыль: {opp.get('profit_percent', 0):.2f}%\n"
                f"   Ликвидность: {opp.get('liquidity', 0):.1f} продаж/день\n"
                f"   Риск: {opp.get('risk_score', 0):.1f}/100\n\n"
            )
        
        # Добавляем информацию об оптимизации
        optimization = analysis_result.get("optimization", {})
        if optimization and optimization.get("status") == "success":
            total_profit = optimization.get("total_profit", 0)
            expected_return = optimization.get("expected_return_percent", 0)
            
            message += (
                f"<b>Оптимизация:</b>\n"
                f"Ожидаемая прибыль: ${total_profit:.2f} ({expected_return:.2f}%)\n"
                f"Распределено средств: {len(optimization.get('allocations', {}))}/{len(analysis_result.get('top_opportunities', []))}"
            )
        
        # Отправляем уведомление администратору
        from telegram_bot import bot
        await bot.send_message(
            chat_id=admin_chat_id,
            text=message,
            parse_mode="HTML"
        )
        
        logger.info(f"Уведомление о новых арбитражных возможностях отправлено")
    
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления: {e}")

async def auto_trade(
    game: str = "cs2",
    risk_level: str = "medium",
    budget: float = 1000.0,
    min_profit_percent: float = 5.0,
    interval: int = 300,
    execute: bool = False,
    max_executions: int = 5,
    output_dir: str = "results"
):
    """
    Запускает автоматическую арбитражную торговлю между DMarket и другими площадками.
    
    Args:
        game: Тип игры (cs2, dota2, tf2)
        risk_level: Уровень риска для анализа
        budget: Бюджет для торговли
        min_profit_percent: Минимальный процент прибыли
        interval: Интервал обновления данных в секундах
        execute: Флаг выполнения реальных транзакций
        max_executions: Максимальное количество торговых операций
        output_dir: Директория для сохранения результатов
    """
    from models.item_models import GameType
    
    logger.info(f"Запуск автоматической арбитражной торговли для {game.upper()}")
    logger.info(f"Параметры: риск={risk_level}, бюджет=${budget}, мин. прибыль={min_profit_percent}%, интервал={interval}с")
    logger.info(f"Режим выполнения: {'реальный' if execute else 'симуляция'}")
    
    # Создаем директорию для результатов, если она не существует
    os.makedirs(output_dir, exist_ok=True)
    
    # Инициализируем API адаптер
    adapter = init_api_adapter()
    
    # Создаем интегратор торговых площадок
    marketplace_integrator = MarketplaceIntegrator(dmarket_adapter=adapter)
    
    # Определяем тип игры
    game_type_map = {
        "cs2": GameType.CS2,
        "dota2": GameType.DOTA2,
        "tf2": GameType.TF2
    }
    game_type = game_type_map.get(game.lower(), GameType.CS2)
    
    # Функция обратного вызова для сохранения результатов
    async def save_trade_results(game_type, result):
        if not result["success"]:
            logger.warning(f"Ошибка при выполнении торговой операции: {result.get('errors', ['Неизвестная ошибка'])[0]}")
            return
        
        # Сохраняем результаты в файл
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        result_file = os.path.join(output_dir, f"trade_result_{game_type.value}_{timestamp}.json")
        
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, default=str)
        
        logger.info(f"Результаты торговой операции сохранены в файл {result_file}")
        
        # Формируем отчет
        operations_count = len(result["executed_operations"])
        total_profit = result["total_profit"]
        total_spent = result["total_spent"]
        
        logger.info(f"Выполнено операций: {operations_count}")
        logger.info(f"Общая прибыль: ${total_profit:.2f}")
        logger.info(f"Общие затраты: ${total_spent:.2f}")
        
        if result["errors"]:
            logger.warning(f"Ошибки: {len(result['errors'])}")
            for error in result["errors"]:
                logger.warning(f"  - {error}")
    
    try:
        # Настраиваем уровень риска
        max_risk = {
            "low": 30.0,    # Консервативный подход
            "medium": 50.0,  # Средний подход
            "high": 70.0    # Агрессивный подход
        }.get(risk_level, 50.0)
        
        # Запускаем мониторинг и выполнение арбитражных стратегий
        await marketplace_integrator.monitor_and_execute_arbitrage(
            games=[game_type],
            min_profit_percent=min_profit_percent,
            budget=budget,
            max_risk=max_risk,
            interval=interval,
            execute=execute,
            max_executions=max_executions,
            callback=save_trade_results
        )
        
        logger.info("Автоматическая арбитражная торговля успешно завершена")
        
    except Exception as e:
        logger.error(f"Ошибка при автоматической арбитражной торговле: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

async def manage_targets(
    args,
    api_adapter = None,
    output_dir: str = "results"
):
    """
    Управляет отложенными ордерами (таргетами) на DMarket.
    
    Args:
        args: Аргументы командной строки
        api_adapter: Адаптер для взаимодействия с DMarket API
        output_dir: Директория для сохранения результатов
    """
    from models.item_models import GameType
    
    if api_adapter is None:
        api_adapter = init_api_adapter()
    
    # Инициализируем интегратор торговых площадок
    marketplace_integrator = MarketplaceIntegrator(dmarket_adapter=api_adapter)
    
    # Определяем тип игры
    game_type_map = {
        "cs2": GameType.CS2,
        "dota2": GameType.DOTA2,
        "tf2": GameType.TF2
    }
    game_type = game_type_map.get(args.game.lower(), GameType.CS2)
    
    # Создаем директорию для результатов, если она не существует
    os.makedirs(output_dir, exist_ok=True)
    
    # Список всех отложенных ордеров
    if args.target_list:
        logger.info("Получение списка отложенных ордеров...")
        
        try:
            target_orders = await marketplace_integrator.get_all_target_orders()
            
            if not target_orders:
                logger.info("Отложенных ордеров не найдено")
                return
            
            logger.info(f"Найдено {len(target_orders)} отложенных ордеров:")
            
            for i, target in enumerate(target_orders, 1):
                target_id = target.get("target_id", "Unknown")
                item_name = target.get("item_name", "Unknown Item")
                target_price = target.get("target_price", 0.0)
                status = target.get("status", "unknown")
                
                logger.info(f"{i}. {item_name} - {status.upper()} - Цель: ${target_price:.2f} (ID: {target_id})")
            
            # Сохраняем результаты в файл
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            result_file = os.path.join(output_dir, f"target_orders_{timestamp}.json")
            
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(target_orders, f, indent=2, default=str)
            
            logger.info(f"Список отложенных ордеров сохранен в файл {result_file}")
            
        except Exception as e:
            logger.error(f"Ошибка при получении списка отложенных ордеров: {e}")
    
    # Отмена отложенного ордера
    elif args.target_cancel:
        target_id = args.target_cancel
        logger.info(f"Отмена отложенного ордера с ID {target_id}...")
        
        try:
            result = await marketplace_integrator.cancel_target_order(target_id)
            
            if result.get("success", False):
                logger.info(f"Отложенный ордер {target_id} успешно отменен")
            else:
                logger.error(f"Не удалось отменить отложенный ордер: {result.get('error', 'Неизвестная ошибка')}")
        
        except Exception as e:
            logger.error(f"Ошибка при отмене отложенного ордера: {e}")
    
    # Выполнение отложенного ордера
    elif args.target_execute:
        target_id = args.target_execute
        logger.info(f"Выполнение отложенного ордера с ID {target_id}...")
        
        try:
            result = await marketplace_integrator.execute_target_order(target_id)
            
            if result.get("success", False):
                logger.info(f"Отложенный ордер {target_id} успешно выполнен")
                logger.info(f"Цена покупки: ${result.get('price', 0.0):.2f}")
            else:
                logger.error(f"Не удалось выполнить отложенный ордер: {result.get('error', 'Неизвестная ошибка')}")
        
        except Exception as e:
            logger.error(f"Ошибка при выполнении отложенного ордера: {e}")
    
    # Создание отложенных ордеров
    elif args.target_create:
        logger.info(f"Создание отложенных ордеров для {args.game.upper()}...")
        logger.info(f"Параметры: бюджет=${args.budget}, мин. прибыль={args.min_profit}%, макс. ордеров={args.max_targets}")
        
        try:
            result = await marketplace_integrator.create_arbitrage_target_strategy(
                game=game_type,
                min_profit_percent=args.min_profit,
                budget=args.budget,
                max_targets=args.max_targets,
                max_wait_hours=args.max_wait_hours
            )
            
            if result.get("success", False) and result.get("created_targets"):
                logger.info(f"Создано отложенных ордеров: {len(result['created_targets'])}")
                logger.info(f"Потенциальная прибыль: ${result['total_potential_profit']:.2f}")
                
                # Выводим информацию о созданных ордерах
                for i, target in enumerate(result["created_targets"], 1):
                    logger.info(
                        f"{i}. {target['item_name']} - Цель: ${target['target_price']:.2f} - "
                        f"Потенц. прибыль: ${target['potential_profit']:.2f} ({target['profit_percent']:.1f}%)"
                    )
                
                # Сохраняем результаты в файл
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                result_file = os.path.join(output_dir, f"created_targets_{timestamp}.json")
                
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump(result, f, indent=2, default=str)
                logger.info(f"Результаты создания отложенных ордеров сохранены в файл {result_file}")
                
            else:
                errors = result.get("errors", ["Неизвестная ошибка"])
                logger.error(f"Не удалось создать отложенные ордера: {', '.join(errors[:3])}")
        
        except Exception as e:
            logger.error(f"Ошибка при создании отложенных ордеров: {e}")
    
    # Мониторинг отложенных ордеров
    elif args.target_monitor:
        logger.info(f"Запуск мониторинга отложенных ордеров...")
        logger.info(f"Интервал проверки: {args.interval} секунд")
        logger.info(f"Автоматическое выполнение: {'Включено' if args.auto_execute else 'Отключено'}")
        
        try:
            # Функция обратного вызова для логирования результатов
            async def monitor_callback(target, execute_result):
                target_id = target.get("target_id", "Unknown")
                item_name = target.get("item_name", "Unknown Item")
                
                if execute_result.get("success", False):
                    price = execute_result.get("price", 0.0)
                    logger.info(f"Автоматическое выполнение ордера {target_id} для {item_name} с ценой ${price:.2f}")
                    
                    # Сохраняем результаты в файл
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    result_file = os.path.join(output_dir, f"executed_target_{target_id}_{timestamp}.json")
                    
                    with open(result_file, 'w', encoding='utf-8') as f:
                        json.dump(execute_result, f, indent=2, default=str)
                else:
                    error = execute_result.get("error", "Неизвестная ошибка")
                    logger.error(f"Ошибка при выполнении ордера {target_id} для {item_name}: {error}")
            
            # Запускаем мониторинг (блокирующий вызов)
            await marketplace_integrator.monitor_target_orders(
                interval=args.interval,
                auto_execute_expired=args.auto_execute,
                callback=monitor_callback
            )
        
        except asyncio.CancelledError:
            logger.info("Мониторинг отложенных ордеров остановлен пользователем")
        except Exception as e:
            logger.error(f"Ошибка при мониторинге отложенных ордеров: {e}")

async def main():
    """
    Основная точка входа в приложение.
    
    Обрабатывает аргументы командной строки и запускает соответствующий режим работы:
    - Анализ рынка
    - Запуск телеграм-бота
    - Мониторинг рынка
    - Автоматическая торговля
    """
    args = parse_arguments()
    
    # Настраиваем уровень логирования в зависимости от verbose
    log_levels = [logging.WARNING, logging.INFO, logging.DEBUG]
    log_level = log_levels[min(args.verbose, len(log_levels) - 1)]
    logger.setLevel(log_level)
    
    # Анализ рынка по запросу
    if args.analyze:
        logger.info("Запуск анализа рынка")
        analyze_result = await analyze_market(
            risk_level=args.risk,
            budget=args.budget,
            output_dir=args.output,
            use_distributed=args.distributed,
            use_processes=args.use_processes,
            categories=args.categories
        )
        
        # Отображаем результаты анализа
        if analyze_result["status"] == "success":
            print(f"\nНайдено {analyze_result['opportunities_count']} арбитражных возможностей")
            
            if analyze_result['top_opportunities']:
                print("\nТоп возможности:")
                for i, opp in enumerate(analyze_result['top_opportunities'][:5], 1):
                    print(f"{i}. Прибыль: {opp['profit_percent']:.2f}% - {opp['path_description']}")
            
            # Сохраняем результаты в файл
            output_file = os.path.join(args.output, f"analysis_{int(time.time())}.json")
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(analyze_result, f, ensure_ascii=False, indent=2)
            
            print(f"\nРезультаты сохранены в: {output_file}")
        else:
            print(f"\nОшибка анализа: {analyze_result['message']}")
        
        return
    
    # Проверяем, запрашивается ли мониторинг рынка
    if args.watch:
        logger.info(f"Запуск мониторинга рынка с интервалом {args.interval} секунд")
        await watch_market(args.interval, args.risk, args.budget, args.output)
    
    # Проверяем, запрашивается ли автоматическая торговля
    if args.auto_trade:
        logger.info("Запуск автоматической арбитражной торговли")
        await auto_trade(
            game=args.game,
            risk_level=args.risk,
            budget=args.budget,
            min_profit_percent=args.min_profit,
            interval=args.interval,
            execute=args.execute,
            max_executions=args.max_executions,
            output_dir=args.output
        )
    
    # Проверяем, запрашивается ли работа с отложенными ордерами
    if any([args.target_list, args.target_cancel, args.target_execute, 
            args.target_create, args.target_monitor]):
        logger.info("Запуск управления отложенными ордерами")
        await manage_targets(args, output_dir=args.output)
    
    # Проверяем, требуется ли запустить телеграм-бота
    if args.telegram:
        logger.info("Запуск Telegram-бота")
        
        # Регистрируем обработчик запуска
        dp.startup.register(on_startup)
        
        # Нет обработчика on_shutdown, поэтому не регистрируем его
        
        # Запускаем поллинг бота
        await dp.start_polling(bot)
        
        return
    else:
        # Если не указаны флаги, выводим справку
        if not any([args.analyze, args.watch, args.auto_trade, args.telegram,
                    args.target_list, args.target_cancel, args.target_execute,
                    args.target_create, args.target_monitor]):
            logger.info("Не указаны параметры запуска. Используйте --help для получения справки.")
        return 0
    
    return 0

if __name__ == "__main__":
    # Запускаем основную функцию в асинхронном контексте
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
