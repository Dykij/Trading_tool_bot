"""
Market Item Model for DMarket Trading Bot

This module provides a standardized model for market items with utilities
for data validation, normalization, and conversion between different formats.
"""

import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime

# Set up logging
logger = logging.getLogger("market_item")

class MarketItem:
    """
    Represents a market item with standardized attributes and methods.
    """
    
    def __init__(
        self,
        item_id: str,
        market_id: str,
        title: str,
        game_id: str,
        prices: Dict[str, Union[int, float]],
        amount: int = 1,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        liquidity: float = 0.0,
        **kwargs
    ):
        """
        Initialize a market item with required attributes.
        
        Args:
            item_id: Unique identifier for the item
            market_id: Market identifier
            title: Item title/name
            game_id: Game identifier the item belongs to
            prices: Dictionary of prices in different currencies
            amount: Number of items available (default: 1)
            created_at: Timestamp when the item was created
            updated_at: Timestamp when the item was last updated
            liquidity: Liquidity score (0.0-1.0)
            **kwargs: Additional item attributes
        """
        self.item_id = item_id
        self.market_id = market_id
        self.title = title
        self.game_id = game_id
        self.prices = prices
        self.amount = amount
        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()
        self.liquidity = liquidity
        
        # Store additional attributes
        self.attributes = kwargs
    
    @staticmethod
    def from_api_response(
        response_item: Dict[str, Any], 
        currency: str = "USD"
    ) -> Optional['MarketItem']:
        """
        Create a MarketItem from an API response item.
        
        Args:
            response_item: Item data from API response
            currency: Currency code to extract price for
            
        Returns:
            MarketItem instance or None if conversion fails
        """
        try:
            # Extract required fields
            item_id = response_item.get("itemId", "")
            market_id = response_item.get("marketId", "")
            title = response_item.get("title", "")
            game_id = response_item.get("gameId", "")
            
            # Extract and normalize price information
            prices = {}
            price_data = response_item.get("price", {})
            
            # Handle price format variations
            if isinstance(price_data, dict):
                # Format: {"USD": 1000, "EUR": 900}
                for curr, value in price_data.items():
                    # Convert to float and normalize from cents
                    prices[curr] = float(value) / 100
            elif isinstance(price_data, (int, float, str)):
                # Format: 1000 (in specified currency)
                prices[currency] = float(price_data) / 100
            
            # Extract creation and update timestamps
            created_at = None
            if "createdAt" in response_item:
                try:
                    created_at_str = response_item["createdAt"]
                    created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse createdAt timestamp: {response_item.get('createdAt')}")
            
            updated_at = None
            if "updatedAt" in response_item:
                try:
                    updated_at_str = response_item["updatedAt"]
                    updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    logger.warning(f"Could not parse updatedAt timestamp: {response_item.get('updatedAt')}")
            
            # Extract amount and liquidity
            amount = int(response_item.get("amount", 1))
            
            # Calculate liquidity score (if available data)
            liquidity = 0.0
            if "salesHistory" in response_item:
                # Simple liquidity score based on sales frequency
                sales = response_item["salesHistory"]
                if isinstance(sales, list) and len(sales) > 0:
                    # More sales in history = higher liquidity
                    liquidity = min(len(sales) / 10, 1.0)  # cap at 1.0
            
            # Create the MarketItem
            return MarketItem(
                item_id=item_id,
                market_id=market_id,
                title=title,
                game_id=game_id,
                prices=prices,
                amount=amount,
                created_at=created_at,
                updated_at=updated_at,
                liquidity=liquidity,
                # Store raw data for potential future use
                raw_data=response_item
            )
            
        except Exception as e:
            logger.error(f"Error creating MarketItem from API response: {e}")
            logger.debug(f"Problematic response item: {response_item}")
            return None
    
    @classmethod
    def from_api_response_list(
        cls, 
        response_items: List[Dict[str, Any]], 
        currency: str = "USD"
    ) -> List['MarketItem']:
        """
        Create a list of MarketItems from an API response list.
        
        Args:
            response_items: List of item data from API response
            currency: Currency code to extract price for
            
        Returns:
            List of MarketItem instances (skipping any that fail to convert)
        """
        items = []
        for item_data in response_items:
            item = cls.from_api_response(item_data, currency)
            if item:
                items.append(item)
        
        return items
    
    def get_price(self, currency: str = "USD") -> Optional[float]:
        """
        Get the item price in the specified currency.
        
        Args:
            currency: Currency code
            
        Returns:
            Price in the specified currency or None if not available
        """
        return self.prices.get(currency)
    
    def set_price(self, price: float, currency: str = "USD"):
        """
        Set the item price in the specified currency.
        
        Args:
            price: New price value
            currency: Currency code
        """
        self.prices[currency] = price
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the MarketItem to a dictionary.
        
        Returns:
            Dictionary representation of the MarketItem
        """
        return {
            "item_id": self.item_id,
            "market_id": self.market_id,
            "title": self.title,
            "game_id": self.game_id,
            "prices": self.prices,
            "amount": self.amount,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "liquidity": self.liquidity,
            **self.attributes
        }
    
    def __repr__(self) -> str:
        """
        String representation of the MarketItem.
        
        Returns:
            String representation
        """
        prices_str = ", ".join([f"{curr}: {price:.2f}" for curr, price in self.prices.items()])
        return f"MarketItem(id={self.item_id}, title='{self.title}', prices={{{prices_str}}})" 