"""
Item Validator for DMarket Trading Bot

This module provides validation utilities for market items to ensure
they meet specific criteria before being processed for trading.
"""

import logging
import re
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime

# Set up logging
logger = logging.getLogger("item_validator")

class ValidationResult:
    """
    Represents the result of a validation operation.
    """
    
    def __init__(self, valid: bool, message: str = "", reason: str = ""):
        """
        Initialize a validation result.
        
        Args:
            valid: Whether the validation passed
            message: A descriptive message about the validation
            reason: Reason for validation failure (if applicable)
        """
        self.valid = valid
        self.message = message
        self.reason = reason
    
    def __bool__(self) -> bool:
        """
        Boolean representation of the validation result.
        
        Returns:
            True if valid, False otherwise
        """
        return self.valid
    
    def __str__(self) -> str:
        """
        String representation of the validation result.
        
        Returns:
            String representation
        """
        if self.valid:
            return f"Valid: {self.message}"
        return f"Invalid: {self.message} - {self.reason}"


class ItemValidator:
    """
    Validates market items against a set of rules.
    """
    
    def __init__(self):
        """
        Initialize the item validator with default validation rules.
        """
        # Dictionary of validation rules, each with a callable that returns a ValidationResult
        self.rules: Dict[str, Callable[[Dict[str, Any]], ValidationResult]] = {
            "required_fields": self._validate_required_fields,
            "price_range": self._validate_price_range,
            "title_format": self._validate_title_format,
            "item_age": self._validate_item_age,
        }
        
        # Default validation parameters
        self.params = {
            "min_price": 0.5,  # Minimum price in USD
            "max_price": 5000.0,  # Maximum price in USD
            "required_fields": ["itemId", "title", "price", "gameId"],
            "title_min_length": 3,
            "title_max_length": 100,
            "max_item_age_days": 365,  # Maximum item age in days
        }
    
    def set_parameters(self, **kwargs):
        """
        Set validation parameters.
        
        Args:
            **kwargs: Parameter key-value pairs
        """
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value
            else:
                logger.warning(f"Ignoring unknown validation parameter: {key}")
    
    def validate(self, item: Dict[str, Any]) -> ValidationResult:
        """
        Validate an item against all rules.
        
        Args:
            item: Item data to validate
            
        Returns:
            ValidationResult with the overall validation result
        """
        for rule_name, rule_func in self.rules.items():
            result = rule_func(item)
            if not result.valid:
                return result
        
        return ValidationResult(True, "Item passed all validation rules")
    
    def validate_bulk(self, items: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Validate a list of items and group them by validation status.
        
        Args:
            items: List of item data to validate
            
        Returns:
            Dictionary with "valid" and "invalid" lists of items
        """
        result = {
            "valid": [],
            "invalid": []
        }
        
        for item in items:
            validation = self.validate(item)
            if validation.valid:
                result["valid"].append(item)
            else:
                item["_validation_reason"] = validation.reason
                result["invalid"].append(item)
        
        return result
    
    def _validate_required_fields(self, item: Dict[str, Any]) -> ValidationResult:
        """
        Validate that an item has all required fields.
        
        Args:
            item: Item data to validate
            
        Returns:
            ValidationResult
        """
        required_fields = self.params["required_fields"]
        
        for field in required_fields:
            if field not in item or item[field] is None:
                return ValidationResult(
                    False,
                    f"Missing required field: {field}",
                    "missing_field"
                )
            
            # Check for empty values
            if isinstance(item[field], str) and not item[field].strip():
                return ValidationResult(
                    False,
                    f"Required field is empty: {field}",
                    "empty_field"
                )
        
        return ValidationResult(True, "All required fields are present")
    
    def _validate_price_range(self, item: Dict[str, Any]) -> ValidationResult:
        """
        Validate that an item's price is within the acceptable range.
        
        Args:
            item: Item data to validate
            
        Returns:
            ValidationResult
        """
        min_price = self.params["min_price"]
        max_price = self.params["max_price"]
        
        # Handle different price formats
        price_data = item.get("price", None)
        
        if price_data is None:
            return ValidationResult(
                False,
                "Item has no price data",
                "missing_price"
            )
        
        # Extract price in USD
        price_usd = None
        
        if isinstance(price_data, dict):
            # Format: {"USD": 1000, "EUR": 900}
            if "USD" in price_data:
                price_usd = float(price_data["USD"]) / 100  # Convert cents to dollars
        elif isinstance(price_data, (int, float, str)):
            # Format: 1000 (assumed to be in USD cents)
            price_usd = float(price_data) / 100
        
        if price_usd is None:
            return ValidationResult(
                False,
                "Could not determine price in USD",
                "price_format"
            )
        
        # Check price range
        if price_usd < min_price:
            return ValidationResult(
                False,
                f"Price too low: ${price_usd:.2f} (minimum: ${min_price:.2f})",
                "price_too_low"
            )
        
        if price_usd > max_price:
            return ValidationResult(
                False,
                f"Price too high: ${price_usd:.2f} (maximum: ${max_price:.2f})",
                "price_too_high"
            )
        
        return ValidationResult(True, "Price is within acceptable range")
    
    def _validate_title_format(self, item: Dict[str, Any]) -> ValidationResult:
        """
        Validate that an item's title meets formatting requirements.
        
        Args:
            item: Item data to validate
            
        Returns:
            ValidationResult
        """
        title = item.get("title", "")
        
        if not isinstance(title, str):
            return ValidationResult(
                False,
                "Title is not a string",
                "title_type"
            )
        
        # Check title length
        min_length = self.params["title_min_length"]
        max_length = self.params["title_max_length"]
        
        if len(title) < min_length:
            return ValidationResult(
                False,
                f"Title too short: {len(title)} characters (minimum: {min_length})",
                "title_too_short"
            )
        
        if len(title) > max_length:
            return ValidationResult(
                False,
                f"Title too long: {len(title)} characters (maximum: {max_length})",
                "title_too_long"
            )
        
        # Check for invalid characters
        # Allow alphanumeric characters, spaces, hyphens, and some special characters
        if not re.match(r'^[\w\s\-\|\(\)\[\]\{\}\.,;:!?%&\+\*/\'"\$#@=<>]+$', title):
            return ValidationResult(
                False,
                "Title contains invalid characters",
                "title_invalid_chars"
            )
        
        return ValidationResult(True, "Title format is valid")
    
    def _validate_item_age(self, item: Dict[str, Any]) -> ValidationResult:
        """
        Validate that an item's age is within acceptable limits.
        
        Args:
            item: Item data to validate
            
        Returns:
            ValidationResult
        """
        max_age_days = self.params["max_item_age_days"]
        
        # Check created_at timestamp
        created_at = item.get("createdAt", None)
        
        if not created_at:
            # If no creation date, assume item is new
            return ValidationResult(True, "Item has no creation date, assuming new")
        
        try:
            # Parse timestamp
            if isinstance(created_at, str):
                created_timestamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            elif isinstance(created_at, (int, float)):
                created_timestamp = datetime.fromtimestamp(created_at)
            else:
                return ValidationResult(
                    False,
                    "Invalid creation timestamp format",
                    "invalid_timestamp"
                )
            
            # Calculate item age in days
            now = datetime.now()
            age_days = (now - created_timestamp).days
            
            if age_days > max_age_days:
                return ValidationResult(
                    False,
                    f"Item too old: {age_days} days (maximum: {max_age_days} days)",
                    "item_too_old"
                )
            
            return ValidationResult(True, "Item age is acceptable")
            
        except (ValueError, TypeError) as e:
            return ValidationResult(
                False,
                f"Could not parse item creation date: {e}",
                "date_parse_error"
            )
    
    def add_custom_rule(self, name: str, rule_func: Callable[[Dict[str, Any]], ValidationResult]):
        """
        Add a custom validation rule.
        
        Args:
            name: Rule name
            rule_func: Function that takes an item and returns a ValidationResult
        """
        self.rules[name] = rule_func
    
    def remove_rule(self, name: str) -> bool:
        """
        Remove a validation rule.
        
        Args:
            name: Rule name
            
        Returns:
            True if the rule was removed, False if it did not exist
        """
        if name in self.rules:
            del self.rules[name]
            return True
        return False 