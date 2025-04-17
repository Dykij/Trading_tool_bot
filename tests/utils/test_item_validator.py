"""
Tests for the item_validator module.
"""

import unittest
import pytest
from datetime import datetime, timedelta

from src.utils.item_validator import ItemValidator, ValidationResult


class TestValidationResult(unittest.TestCase):
    """Test cases for ValidationResult class."""
    
    def test_validation_result_bool(self):
        """Test boolean representation of ValidationResult."""
        valid_result = ValidationResult(True, "Success")
        invalid_result = ValidationResult(False, "Failure", "error")
        
        self.assertTrue(bool(valid_result))
        self.assertFalse(bool(invalid_result))
    
    def test_validation_result_str(self):
        """Test string representation of ValidationResult."""
        valid_result = ValidationResult(True, "Success")
        invalid_result = ValidationResult(False, "Failure", "error")
        
        self.assertEqual(str(valid_result), "Valid: Success")
        self.assertEqual(str(invalid_result), "Invalid: Failure - error")


class TestItemValidator(unittest.TestCase):
    """Test cases for ItemValidator class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.validator = ItemValidator()
        self.valid_item = {
            "itemId": "123456",
            "title": "AWP | Dragon Lore (Factory New)",
            "price": 100000,  # $1000.00 in cents
            "gameId": "csgo",
            "createdAt": datetime.now().isoformat()
        }
    
    def test_validate_valid_item(self):
        """Test validation of a valid item."""
        result = self.validator.validate(self.valid_item)
        self.assertTrue(result.valid)
    
    def test_validate_missing_required_field(self):
        """Test validation of an item with a missing required field."""
        # Create a copy of the valid item and remove a required field
        invalid_item = self.valid_item.copy()
        del invalid_item["title"]
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "missing_field")
    
    def test_validate_empty_required_field(self):
        """Test validation of an item with an empty required field."""
        # Create a copy of the valid item and set a required field to empty
        invalid_item = self.valid_item.copy()
        invalid_item["title"] = ""
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "empty_field")
    
    def test_validate_price_too_low(self):
        """Test validation of an item with a price that is too low."""
        # Create a copy of the valid item and set price too low
        invalid_item = self.valid_item.copy()
        invalid_item["price"] = 10  # $0.10 in cents
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "price_too_low")
    
    def test_validate_price_too_high(self):
        """Test validation of an item with a price that is too high."""
        # Create a copy of the valid item and set price too high
        invalid_item = self.valid_item.copy()
        invalid_item["price"] = 1000000  # $10,000.00 in cents
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "price_too_high")
    
    def test_validate_price_dictionary(self):
        """Test validation of an item with a price dictionary."""
        # Create a copy of the valid item and set price as dictionary
        valid_item_dict_price = self.valid_item.copy()
        valid_item_dict_price["price"] = {"USD": 100000, "EUR": 90000}  # $1000.00 USD in cents
        
        result = self.validator.validate(valid_item_dict_price)
        self.assertTrue(result.valid)
    
    def test_validate_title_too_short(self):
        """Test validation of an item with a title that is too short."""
        # Create a copy of the valid item and set title too short
        invalid_item = self.valid_item.copy()
        invalid_item["title"] = "AB"  # 2 characters (minimum is 3)
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "title_too_short")
    
    def test_validate_title_too_long(self):
        """Test validation of an item with a title that is too long."""
        # Create a copy of the valid item and set title too long
        invalid_item = self.valid_item.copy()
        invalid_item["title"] = "A" * 101  # 101 characters (maximum is 100)
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "title_too_long")
    
    def test_validate_title_invalid_chars(self):
        """Test validation of an item with a title that has invalid characters."""
        # Create a copy of the valid item and set title with invalid characters
        invalid_item = self.valid_item.copy()
        invalid_item["title"] = "Invalid Title ☢"  # Contains emoji/special character
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "title_invalid_chars")
    
    def test_validate_item_too_old(self):
        """Test validation of an item that is too old."""
        # Create a copy of the valid item and set creation date too old
        invalid_item = self.valid_item.copy()
        too_old_date = datetime.now() - timedelta(days=366)  # 366 days old (maximum is 365)
        invalid_item["createdAt"] = too_old_date.isoformat()
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "item_too_old")
    
    def test_validate_bulk(self):
        """Test bulk validation of items."""
        # Create a valid and an invalid item
        valid_item = self.valid_item.copy()
        invalid_item = self.valid_item.copy()
        del invalid_item["title"]
        
        items = [valid_item, invalid_item]
        result = self.validator.validate_bulk(items)
        
        self.assertEqual(len(result["valid"]), 1)
        self.assertEqual(len(result["invalid"]), 1)
        self.assertEqual(result["invalid"][0]["_validation_reason"], "missing_field")
    
    def test_set_parameters(self):
        """Test setting validation parameters."""
        # Change the minimum price parameter
        self.validator.set_parameters(min_price=1.0)
        
        # Create a copy of the valid item and set price to $0.75
        borderline_item = self.valid_item.copy()
        borderline_item["price"] = 75  # $0.75 in cents
        
        # Should now be invalid with the new minimum price
        result = self.validator.validate(borderline_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "price_too_low")
    
    def test_custom_rule(self):
        """Test adding a custom validation rule."""
        # Define a custom rule to check if the title contains "Dragon"
        def validate_dragon_title(item):
            title = item.get("title", "")
            if "Dragon" in title:
                return ValidationResult(True, "Title contains 'Dragon'")
            return ValidationResult(False, "Title should contain 'Dragon'", "no_dragon")
        
        # Add the custom rule
        self.validator.add_custom_rule("dragon_title", validate_dragon_title)
        
        # Test with a valid item (contains "Dragon")
        result = self.validator.validate(self.valid_item)
        self.assertTrue(result.valid)
        
        # Test with an invalid item (doesn't contain "Dragon")
        invalid_item = self.valid_item.copy()
        invalid_item["title"] = "AWP | Asiimov (Factory New)"
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "no_dragon")
    
    def test_remove_rule(self):
        """Test removing a validation rule."""
        # First ensure the rule exists and will cause validation to fail
        invalid_item = self.valid_item.copy()
        invalid_item["price"] = 10  # $0.10 in cents
        
        result = self.validator.validate(invalid_item)
        self.assertFalse(result.valid)
        self.assertEqual(result.reason, "price_too_low")
        
        # Remove the rule
        removed = self.validator.remove_rule("price_range")
        self.assertTrue(removed)
        
        # Now the validation should pass because the rule is gone
        result = self.validator.validate(invalid_item)
        self.assertTrue(result.valid)
        
        # Try to remove a non-existent rule
        removed = self.validator.remove_rule("non_existent_rule")
        self.assertFalse(removed)


if __name__ == "__main__":
    unittest.main() 