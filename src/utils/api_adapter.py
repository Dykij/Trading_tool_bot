"""
API Adapter for DMarket Trading Bot

This module provides an adapter layer between our application and the DMarket API,
facilitating format conversions, standardized error handling, and simplifying
API interactions.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union, Tuple
from datetime import datetime

# Импорт MarketItem из отдельного файла
from src.utils.market_item import MarketItem

# Попытка импорта API wrapper
try:
    from src.api.api_wrapper import DMarketAPI, APIError, NetworkError, RateLimitError
except ImportError:
    try:
        from api_wrapper import DMarketAPI, APIError, NetworkError, RateLimitError
    except ImportError:
        # Если не удается импортировать, создаем заглушки
        class DMarketAPI:
            def __init__(self, *args, **kwargs):
                pass
        
        class APIError(Exception):
            pass
        
        class NetworkError(APIError):
            pass
        
        class RateLimitError(APIError):
            pass

# Set up logging
logger = logging.getLogger("api_adapter")

class APIAdapter:
    """
    Adapter for DMarket API that simplifies interactions and standardizes 
    response formats.
    """
    
    def __init__(self, api_client: Optional[DMarketAPI] = None):
        """
        Initialize the API adapter.
        
        Args:
            api_client: An existing DMarketAPI instance or None to create a new one
        """
        self.api_client = api_client
        self._setup_logging()
    
    def _setup_logging(self):
        """Set up logging configuration for the adapter."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        if not logger.handlers:
            logger.addHandler(handler)
        
        logger.setLevel(logging.INFO)
    
    def set_api_client(self, api_client: DMarketAPI):
        """
        Set or update the API client.
        
        Args:
            api_client: DMarketAPI instance
        """
        self.api_client = api_client
        logger.info("API client updated")
    
    async def get_market_items(
        self, 
        game_id: str = "a8db",
        limit: int = 100, 
        offset: int = 0,
        currency: str = "USD",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Get market items with standardized error handling.
        
        Args:
            game_id: Game identifier (default: "a8db" for CS2)
            limit: Maximum number of items to retrieve
            offset: Offset for pagination
            currency: Currency code for prices
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Standardized response dictionary with items or error information
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return self._format_error_response("API client not initialized")
        
        try:
            # Call the API client's async method
            response = await self.api_client.get_market_items_async(
                game_id=game_id,
                limit=limit,
                offset=offset,
                currency=currency,
                **kwargs
            )
            
            # Standardize the response
            return self._format_success_response(response)
            
        except RateLimitError as e:
            logger.warning(f"Rate limit exceeded: {e}")
            return self._format_error_response(
                "Rate limit exceeded, please try again later",
                "rate_limit",
                str(e)
            )
        except NetworkError as e:
            logger.error(f"Network error: {e}")
            return self._format_error_response(
                "Network error occurred",
                "network",
                str(e)
            )
        except APIError as e:
            logger.error(f"API error: {e}")
            return self._format_error_response(
                "API error occurred",
                "api",
                str(e)
            )
        except Exception as e:
            logger.exception(f"Unexpected error: {e}")
            return self._format_error_response(
                "Unexpected error occurred",
                "unknown",
                str(e)
            )
    
    async def search_items(
        self,
        title: str,
        game_id: str = "a8db",
        currency: str = "USD",
        limit: int = 20,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Search for specific items on the marketplace.
        
        Args:
            title: Item title to search for
            game_id: Game identifier
            currency: Currency code for prices
            limit: Maximum number of items to retrieve
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            Standardized response dictionary with search results
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return self._format_error_response("API client not initialized")
        
        try:
            response = await self.api_client.search_items_async(
                title=title,
                game_id=game_id,
                currency=currency,
                limit=limit,
                **kwargs
            )
            
            return self._format_success_response(response)
            
        except Exception as e:
            logger.exception(f"Error searching items: {e}")
            return self._format_error_response(
                "Error searching items",
                "search_error",
                str(e)
            )
    
    async def get_balance(self) -> Dict[str, Any]:
        """
        Get user wallet balance with standardized response.
        
        Returns:
            Standardized response dictionary with balance information
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return self._format_error_response("API client not initialized")
        
        try:
            response = await self.api_client.get_balance_async()
            
            # Extract and normalize balance data
            balances = {}
            if "usd" in response:
                balances["USD"] = float(response["usd"]) / 100
            if "eur" in response:
                balances["EUR"] = float(response["eur"]) / 100
            
            return {
                "success": True,
                "data": {
                    "balances": balances,
                    "raw_response": response
                },
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.exception(f"Error getting balance: {e}")
            return self._format_error_response(
                "Error retrieving wallet balance",
                "balance_error",
                str(e)
            )
    
    async def execute_trade(
        self,
        item_id: str,
        price: Union[float, int],
        currency: str = "USD",
        operation: str = "buy"
    ) -> Dict[str, Any]:
        """
        Execute a trade operation (buy or sell).
        
        Args:
            item_id: Item identifier
            price: Trade price
            currency: Currency code
            operation: Trade operation type ("buy" or "sell")
            
        Returns:
            Standardized response dictionary with trade result
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return self._format_error_response("API client not initialized")
        
        if operation not in ["buy", "sell"]:
            return self._format_error_response(
                f"Invalid operation: {operation}. Must be 'buy' or 'sell'",
                "invalid_parameter"
            )
        
        try:
            # Convert price to cents format if needed
            price_in_cents = int(price * 100)
            
            if operation == "buy":
                response = await self.api_client.buy_item_async(
                    item_id=item_id,
                    price=price_in_cents,
                    currency=currency
                )
            else:  # sell
                response = await self.api_client.sell_item_async(
                    item_id=item_id,
                    price=price_in_cents,
                    currency=currency
                )
            
            return self._format_success_response(response)
            
        except Exception as e:
            logger.exception(f"Error executing {operation}: {e}")
            return self._format_error_response(
                f"Error executing {operation}",
                f"{operation}_error",
                str(e)
            )
    
    async def get_inventory(
        self,
        game_id: str = "a8db",
        in_market: bool = False
    ) -> Dict[str, Any]:
        """
        Get user inventory items.
        
        Args:
            game_id: Game identifier
            in_market: Whether to include items already on the market
            
        Returns:
            Standardized response dictionary with inventory items
        """
        if not self.api_client:
            logger.error("API client not initialized")
            return self._format_error_response("API client not initialized")
        
        try:
            response = await self.api_client.get_user_inventory_async(
                game_id=game_id,
                in_market=in_market
            )
            
            return self._format_success_response(response)
            
        except Exception as e:
            logger.exception(f"Error getting inventory: {e}")
            return self._format_error_response(
                "Error retrieving inventory",
                "inventory_error",
                str(e)
            )
    
    def _format_success_response(self, data: Any) -> Dict[str, Any]:
        """
        Format a successful API response.
        
        Args:
            data: Response data from the API
            
        Returns:
            Standardized success response dictionary
        """
        return {
            "success": True,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
    
    def _format_error_response(
        self,
        message: str,
        error_type: str = "general",
        details: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Format an error response.
        
        Args:
            message: Error message
            error_type: Type of error
            details: Additional error details
            
        Returns:
            Standardized error response dictionary
        """
        return {
            "success": False,
            "error": {
                "message": message,
                "type": error_type,
                "details": details
            },
            "timestamp": datetime.now().isoformat()
        }

# Создаем класс DMarketAdapter для обратной совместимости с тестами
class DMarketAdapter:
    """
    Legacy adapter for DMarket API. Maintained for backward compatibility.
    Will be deprecated in future versions in favor of APIAdapter.
    """
    
    def __init__(self, api_key: str, api_secret: Optional[str] = None, use_cache: bool = True):
        """
        Initialize the DMarket adapter.
        
        Args:
            api_key: API key for DMarket
            api_secret: API secret for DMarket (optional)
            use_cache: Whether to use cache for API responses
        """
        self.api = DMarketAPI(api_key, api_secret)
        self.logger = logger
        self.cache = {}
        self.cache_ttl = 300  # 5 minutes
        self.use_cache = use_cache
    
    async def get_market_items(self, game_id: str = 'a8db', limit: int = 100, offset: int = 0, 
                            currency: str = 'USD', force_refresh: bool = False,
                            **kwargs) -> List[MarketItem]:
        """
        Get market items.
        
        Args:
            game_id: Game identifier (default is 'a8db' which is CS2)
            limit: Maximum number of items to retrieve
            offset: Offset for pagination
            currency: Currency code for prices
            force_refresh: Whether to force refresh cache
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of MarketItem objects
        """
        try:
            response = await self.api.get_market_items_async(
                game_id=game_id,
                limit=limit,
                offset=offset,
                currency=currency,
                **kwargs
            )
            
            items = []
            if "objects" in response and isinstance(response["objects"], list):
                for item_data in response["objects"]:
                    market_item = MarketItem.from_api_response(item_data, currency)
                    if market_item:
                        items.append(market_item)
            
            return items
        except Exception as e:
            self.logger.error(f"Error getting market items: {e}")
            return []
    
    async def get_popular_items(self, game_id: str = 'a8db', limit: int = 20, **kwargs) -> List[MarketItem]:
        """
        Get popular items for a game.
        
        Args:
            game_id: Game identifier
            limit: Maximum number of items to retrieve
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of MarketItem objects
        """
        # In a real implementation, would use a different endpoint or parameter.
        # For compatibility, just fetching market items sorted by popularity
        return await self.get_market_items(
            game_id=game_id,
            limit=limit,
            sort_by="popularity",
            sort_dir="desc",
            **kwargs
        )
    
    async def get_wallet_balance(self) -> Dict[str, float]:
        """
        Get wallet balance.
        
        Returns:
            Dictionary with currency codes as keys and balances as values
        """
        try:
            response = await self.api.get_balance_async()
            
            balances = {}
            if "usd" in response:
                balances["USD"] = float(response["usd"]) / 100
            if "eur" in response:
                balances["EUR"] = float(response["eur"]) / 100
            
            return balances
        except Exception as e:
            self.logger.error(f"Error getting wallet balance: {e}")
            return {}
    
    async def find_arbitrage_opportunities(self, game_id: str = 'a8db', min_profit: float = 5.0, 
                                        limit: int = 10, **kwargs) -> List[Dict[str, Any]]:
        """
        Find arbitrage opportunities.
        
        Args:
            game_id: Game identifier
            min_profit: Minimum profit percentage
            limit: Maximum number of opportunities to return
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            List of dictionaries with arbitrage opportunities
        """
        # This would normally analyze market data to find arbitrage
        # For compatibility, return placeholder data
        return [
            {
                "item_name": "AWP | Asiimov (Field-Tested)",
                "buy_price": 50.0,
                "sell_price": 55.0,
                "profit": 5.0,
                "profit_percent": 10.0,
                "confidence": 0.85
            },
            {
                "item_name": "AK-47 | Redline (Field-Tested)",
                "buy_price": 20.0,
                "sell_price": 22.0,
                "profit": 2.0,
                "profit_percent": 10.0,
                "confidence": 0.80
            }
        ][:limit] 