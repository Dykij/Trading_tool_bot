"""
Модуль CLI-интерфейса для DMarket Trading Bot.

Этот модуль предоставляет удобный интерфейс командной строки
для запуска различных функций торгового бота.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv

# Для запуска из любой директории
# Add project root to path
# Assuming the script is in src/cli, the project root is two levels up.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Import project modules
from config import load_config  # noqa: E402
from src.api.integration import IntegrationManager  # noqa: E402
# Импортируем модули машинного обучения
from src.ml.ml_predictor import MLPredictor  # noqa: E402


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join("logs", "cli.log"), "a")
    ]
)
logger = logging.getLogger("cli")

# Создаем директории для логов и результатов, если они не существуют
os.makedirs("logs", exist_ok=True)
os.makedirs("results", exist_ok=True)


def save_result_to_file(result: Dict[str, Any], filename: Optional[str] = None) -> str:
    """
    Сохраняет результат выполнения в JSON-файл.

    Args:
        result: Результат выполнения команды
        filename: Имя файла (опционально)

    Returns:
        str: Путь к созданному файлу
    """
    if filename is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"result_{timestamp}.json"

    filepath = os.path.join("results", filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Результат сохранен в файл: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Ошибка при сохранении результата: {str(e)}")
        return ""


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="DMarket Trading Bot CLI")

    # Add subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Run trading bot
    run_parser = subparsers.add_parser("run", help="Run the trading bot")
    run_parser.add_argument("--api-key", type=str, help="DMarket API key (overrides config)")
    run_parser.add_argument("--api-secret", type=str, help="DMarket API secret (overrides config)")
    run_parser.add_argument("--simulate", action="store_true",
                            help="Simulate trades without executing them")
    run_parser.add_argument("--budget", type=float, default=100.0, help="Budget for trading")
    run_parser.add_argument("--update-interval", type=int, default=3600,
                            help="Update interval in seconds")
    run_parser.add_argument("--max-trades", type=int, default=3,
                            help="Maximum number of trades per update")
    run_parser.add_argument("--use-ml", action="store_true",
                            help="Use machine learning predictions for trading")

    # Analyze opportunities
    analyze_parser = subparsers.add_parser("analyze", help="Analyze market opportunities")
    analyze_parser.add_argument("--limit", type=int, default=200,
                                help="Limit number of items to analyze")
    analyze_parser.add_argument("--filter", type=str, help="Filter items by name")
    analyze_parser.add_argument("--min-price", type=float, help="Minimum item price")
    analyze_parser.add_argument("--max-price", type=float, help="Maximum item price")
    analyze_parser.add_argument("--use-ml", action="store_true",
                                help="Use machine learning to enhance analysis")

    # Train price prediction model
    train_parser = subparsers.add_parser("train", help="Train price prediction model")
    train_parser.add_argument("--game", type=str, default="cs2",
                              help="Game code to train model for (cs2, dota2, rust)")
    train_parser.add_argument("--item", type=str, help="Item name to train specific model for")
    train_parser.add_argument("--days", type=int, default=30, help="Days of history to use")
    train_parser.add_argument("--model-type", type=str, default="random_forest",
                              choices=["random_forest", "gradient_boosting", "linear"],
                              help="Type of ML model to train")
    train_parser.add_argument("--force-retrain", action="store_true",
                              help="Force retraining even if model exists")

    # Predict price for item
    predict_parser = subparsers.add_parser("predict", help="Predict price for an item")
    predict_parser.add_argument("--game", type=str, default="cs2",
                                help="Game code (cs2, dota2, rust)")
    predict_parser.add_argument("--item", type=str, required=True,
                                help="Item name to predict price for")
    predict_parser.add_argument("--days", type=int, default=7,
                                help="Days to predict ahead")
    predict_parser.add_argument("--model", type=str, default="random_forest",
                                choices=["random_forest", "gradient_boosting", "linear"],
                                help="Model type to use for prediction")

    # Find investment opportunities
    invest_parser = subparsers.add_parser("invest", help="Find investment opportunities")
    invest_parser.add_argument("--game", type=str, default="cs2",
                               help="Game code (cs2, dota2, rust)")
    invest_parser.add_argument("--min-price", type=float, default=1.0,
                               help="Minimum item price")
    invest_parser.add_argument("--max-price", type=float, default=100.0,
                               help="Maximum item price")
    invest_parser.add_argument("--min-roi", type=float, default=5.0,
                               help="Minimum ROI percentage")
    invest_parser.add_argument("--min-confidence", type=float, default=0.7,
                               help="Minimum prediction confidence (0-1)")
    invest_parser.add_argument("--limit", type=int, default=20,
                               help="Maximum number of opportunities to show")

    return parser.parse_args()


def get_api_keys() -> Dict[str, Optional[str]]:
    """Get API keys from environment or config."""
    # Load environment variables
    load_dotenv()

    # Load configuration
    config = load_config()

    # Get API keys from environment variables or config
    api_key = os.getenv("DMARKET_API_KEY")
    api_secret = os.getenv("DMARKET_API_SECRET")

    if not api_key and hasattr(config, 'api'):
        api_key = getattr(config.api, "DMARKET_API_KEY", None)

    if not api_secret and hasattr(config, 'api'):
        api_secret = getattr(config.api, "DMARKET_API_SECRET", None)

    return {
        "api_key": api_key,
        "api_secret": api_secret
    }


async def main():
    """Main entry point for the CLI."""
    # Parse command line arguments
    args = parse_args()

    # Get API keys
    keys = get_api_keys()

    if not keys["api_key"] or not keys["api_secret"]:
        logger.error("API key and secret are required. Set them in .env file or config.")
        return 1

    # Execute command
    if args.command == "run":
        logger.info("Running trading bot")

        # Create integration manager
        manager = IntegrationManager()

        # Run the trading bot workflow
        try:
            await manager.run_trading_bot_workflow(
                api_key=keys["api_key"],
                api_secret=keys["api_secret"],
                update_interval=getattr(args, 'update_interval', 3600),
                max_trades_per_run=getattr(args, 'max_trades', 3),
                time_horizon=3,
                use_ml=getattr(args, 'use_ml', False)
            )
            return 0
        except Exception as e:
            logger.error(f"Error running trading bot: {str(e)}")
            return 1

    elif args.command == "analyze":
        logger.info("Analyzing market opportunities")

        # Create integration manager
        manager = IntegrationManager()

        # Collect market data
        market_data = manager.collect_market_data()

        # Get item count
        item_count = len(market_data.get("items", {})) if market_data else 0
        logger.info(f"Collected data for {item_count} items")

        # Analyze arbitrage opportunities
        opportunities = manager.analyze_arbitrage_opportunities(
            use_ml=getattr(args, 'use_ml', False)
        )
        logger.info(f"Found {len(opportunities)} arbitrage opportunities")

        # Export opportunities if any found
        if opportunities:
            export_path = manager.stat_arbitrage.export_opportunities(opportunities)
            logger.info(f"Opportunities exported to {export_path}")

        return 0

    elif args.command == "train":
        game_id = getattr(args, 'game', 'cs2')
        item = getattr(args, 'item', None)
        days = getattr(args, 'days', 30)
        model_type = getattr(args, 'model_type', 'random_forest')
        force_retrain = getattr(args, 'force_retrain', False)

        logger.info(
            f"Training price prediction model for game {game_id} using {days} days of history"
        )

        try:
            # Инициализируем предиктор
            predictor = MLPredictor()

            # Обучаем модель
            result = await predictor.train_model(
                game_id=game_id,
                model_name="price_predictor" if not item else f"{item}_predictor",
                model_type=model_type,
                items_limit=500,
                history_days=days,
                force_retrain=force_retrain
            )

            if result and result.get('success', False):
                metrics = result.get('metrics', {})
                logger.info("Model training completed successfully. Metrics:")
                for metric, value in metrics.items():
                    logger.info(f"  {metric}: {value}")

                # Сохраняем результат в файл
                save_result_to_file(result, f"train_result_{game_id}_{model_type}.json")
                return 0
            else:
                logger.error(f"Model training failed: {result.get('error', 'Unknown error')}")
                return 1

        except Exception as e:
            logger.error(f"Error training model: {str(e)}")
            return 1

    elif args.command == "predict":
        game_id = getattr(args, 'game', 'cs2')
        item = getattr(args, 'item', None)
        days = getattr(args, 'days', 7)
        model_type = getattr(args, 'model', 'random_forest')

        if not item:
            logger.error("Item name is required for prediction")
            return 1

        logger.info(f"Predicting price for {item} in {game_id} for {days} days ahead")

        try:
            # Инициализируем предиктор
            predictor = MLPredictor()

            # Получаем прогноз
            prediction = await predictor.predict_price(
                game_id=game_id,  # Changed from game_code
                item_name=item,
                days_ahead=days,
                model_type=model_type
            )

            if prediction:
                current_price = prediction.get('current_price', 0)
                forecast = prediction.get('forecast', [])
                trend = prediction.get('trend', 'unknown')
                confidence = prediction.get('confidence', 0)

                logger.info(f"Price prediction results for {item}:")
                logger.info(f"Current price: ${current_price:.2f}")
                logger.info(f"Price trend: {trend}")
                logger.info(f"Prediction confidence: {confidence:.2f}")

                if forecast:
                    logger.info("Price forecast:")
                    for day in forecast:
                        date = day.get('date', 'unknown')
                        price = day.get('price', 0)
                        change = day.get('change', 0)
                        logger.info(f"  {date}: ${price:.2f} ({change:+.2f}%)")

                # Сохраняем результат в файл
                save_result_to_file(
                    prediction, f"prediction_{game_id}_{item.replace(' ', '_')}.json"
                )
                return 0
            else:
                logger.error("Failed to get prediction")
                return 1

        except Exception as e:
            logger.error(f"Error predicting price: {str(e)}")
            return 1

    elif args.command == "invest":
        game_id = getattr(args, 'game', 'cs2')
        min_price = getattr(args, 'min_price', 1.0)
        max_price = getattr(args, 'max_price', 100.0)
        min_roi = getattr(args, 'min_roi', 5.0)
        min_confidence = getattr(args, 'min_confidence', 0.7)
        limit = getattr(args, 'limit', 20)

        logger.info(f"Finding investment opportunities for {game_id}")

        try:
            # Инициализируем предиктор
            predictor = MLPredictor()

            # Находим инвестиционные возможности
            opportunities = await predictor.find_investments(
                game_id=game_id,
                min_confidence=min_confidence,
                min_percent_gain=min_roi,
                price_range=(min_price, max_price),
                limit=limit
            )

            if opportunities:
                logger.info(f"Found {len(opportunities)} investment opportunities:")

                for i, opp in enumerate(opportunities, 1):
                    item_name = opp.get('title', 'Unknown')
                    current_price = opp.get('current_price', 0)
                    predicted_price = opp.get('predicted_price', 0)
                    percent_change = opp.get('percent_change', 0)
                    confidence = opp.get('confidence', 0)

                    logger.info(f"{i}. {item_name}")
                    logger.info(f"   Current price: ${current_price:.2f}")
                    logger.info(
                        f"   Predicted price: ${predicted_price:.2f} ({percent_change:+.2f}%)"
                    )
                    logger.info(f"   Confidence: {confidence:.2f}")
                    logger.info("")

                # Сохраняем результат в файл
                save_result_to_file(opportunities, f"investments_{game_id}.json")
                return 0
            else:
                logger.info("No investment opportunities found matching criteria")
                return 0

        except Exception as e:
            logger.error(f"Error finding investment opportunities: {str(e)}")
            return 1

    else:
        logger.error("No command specified. Use --help for usage information.")
        return 1


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(result)
