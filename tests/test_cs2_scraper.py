import unittest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio
import logging
from datetime import datetime, timedelta

from src.scrapers.cs2_scraper import CS2Scraper

class TestCS2Scraper(unittest.TestCase):
    """Test suite for the CS2Scraper class."""

    def setUp(self):
        """Set up test fixtures, if any."""
        self.scraper = CS2Scraper(api_key="test_key")
        # Configure mock responses
        self.mock_popular_items = [
            {"name": "AWP | Dragon Lore", "price": 1500.0, "category": "Sniper Rifle", "rarity": "Covert"},
            {"name": "AK-47 | Redline", "price": 25.0, "category": "Rifle", "rarity": "Classified"}
        ]
        self.mock_search_results = [
            {"name": "Butterfly Knife | Fade", "price": 900.0, "category": "Knife", "rarity": "Covert"},
            {"name": "Glock-18 | Fade", "price": 350.0, "category": "Pistol", "rarity": "Covert"}
        ]
        self.mock_item_details = {
            "name": "AK-47 | Asiimov",
            "price": 80.0,
            "category": "Rifle",
            "rarity": "Classified",
            "collection": "Operation Phoenix",
            "wear": "Factory New",
            "volume": 120,
            "listings": 45
        }
        self.mock_price_history = [
            {"date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"), "price": 75.0},
            {"date": (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d"), "price": 77.5},
            {"date": (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d"), "price": 79.0},
            {"date": datetime.now().strftime("%Y-%m-%d"), "price": 80.0}
        ]

    @patch("src.scrapers.cs2_scraper.aiohttp.ClientSession")
    async def test_get_popular_items(self, mock_session):
        """Test get_popular_items method."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"items": self.mock_popular_items})
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Call the method
        result = await self.scraper.get_popular_items()
        
        # Assertions
        self.assertEqual(result, self.mock_popular_items)
        mock_session.return_value.__aenter__.return_value.get.assert_called_once()

    @patch("src.scrapers.cs2_scraper.aiohttp.ClientSession")
    async def test_get_popular_items_failure(self, mock_session):
        """Test get_popular_items method when API fails."""
        # Setup mock response for failure
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Call the method
        result = await self.scraper.get_popular_items()
        
        # Should return dummy data on failure
        self.assertIsNotNone(result)
        self.assertTrue(len(result) > 0)

    @patch("src.scrapers.cs2_scraper.aiohttp.ClientSession")
    async def test_search_items(self, mock_session):
        """Test search_items method."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"items": self.mock_search_results})
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Call the method
        result = await self.scraper.search_items("knife")
        
        # Assertions
        self.assertEqual(result, self.mock_search_results)
        mock_session.return_value.__aenter__.return_value.get.assert_called_once()

    @patch("src.scrapers.cs2_scraper.aiohttp.ClientSession")
    async def test_get_item_details(self, mock_session):
        """Test get_item_details method."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"item": self.mock_item_details})
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Call the method
        result = await self.scraper.get_item_details("AK-47 | Asiimov")
        
        # Assertions
        self.assertEqual(result, self.mock_item_details)
        mock_session.return_value.__aenter__.return_value.get.assert_called_once()

    @patch("src.scrapers.cs2_scraper.aiohttp.ClientSession")
    async def test_get_price_history(self, mock_session):
        """Test get_price_history method."""
        # Setup mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"history": self.mock_price_history})
        mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response

        # Call the method
        result = await self.scraper.get_price_history("AK-47 | Asiimov")
        
        # Assertions
        self.assertEqual(result, self.mock_price_history)
        mock_session.return_value.__aenter__.return_value.get.assert_called_once()

    def test_item_categories(self):
        """Test that item categories are properly defined."""
        self.assertIn("Knife", self.scraper.ITEM_CATEGORIES)
        self.assertIn("Pistol", self.scraper.ITEM_CATEGORIES)
        self.assertIn("Rifle", self.scraper.ITEM_CATEGORIES)
        self.assertIn("SMG", self.scraper.ITEM_CATEGORIES)

    def test_dummy_data_generation(self):
        """Test that dummy data generation works."""
        dummy_popular = self.scraper._get_dummy_popular_items()
        dummy_search = self.scraper._get_dummy_search_results("knife")
        dummy_details = self.scraper._get_dummy_item_details("AK-47 | Redline")
        dummy_history = self.scraper._generate_dummy_price_history()
        
        # Check structure of dummy data
        self.assertTrue(len(dummy_popular) > 0)
        self.assertTrue(len(dummy_search) > 0)
        self.assertIsInstance(dummy_details, dict)
        self.assertTrue(len(dummy_history) > 0)

def run_async_test(coro):
    """Helper function to run async tests."""
    return asyncio.run(coro)

# Make async tests run properly
for name, method in list(TestCS2Scraper.__dict__.items()):
    if name.startswith('test_') and asyncio.iscoroutinefunction(method):
        setattr(TestCS2Scraper, name, lambda self, method=method: run_async_test(method(self)))

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    unittest.main() 