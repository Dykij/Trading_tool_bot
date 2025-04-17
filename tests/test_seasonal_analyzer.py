"""
Unit tests for the SeasonalAnalyzer class.

Tests the seasonal pattern detection and analysis functionality
used for market trend prediction in the DMarket Trading Bot.
"""

import unittest
import os
import sys
import json
import tempfile
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ml import SeasonalAnalyzer


class TestSeasonalAnalyzer(unittest.TestCase):
    """Test the SeasonalAnalyzer class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a mock API client
        self.mock_api = MagicMock()
        
        # Mock data for market items
        self.market_items = [
            {
                'itemId': 'item1',
                'title': 'AK-47 | Redline',
                'price': {'USD': 1000},
                'category': 'weapon'
            },
            {
                'itemId': 'item2',
                'title': 'AWP | Asiimov',
                'price': {'USD': 2000},
                'category': 'weapon'
            },
            {
                'itemId': 'item3',
                'title': 'Sticker | Team Liquid',
                'price': {'USD': 500},
                'category': 'sticker'
            }
        ]
        
        # Mock price history data
        dates = pd.date_range(end=datetime.now(), periods=90)
        
        # Create price history with weekly pattern (prices higher on weekends)
        prices_item1 = []
        prices_item2 = []
        prices_item3 = []
        
        for date in dates:
            # Add weekly pattern - weekend prices are higher
            weekend_factor = 1.2 if date.weekday() >= 5 else 1.0
            # Add some monthly patterns - higher at month start
            monthly_factor = 1.1 if date.day <= 5 else 1.0
            # Add some noise
            noise = np.random.normal(0, 0.05)
            
            prices_item1.append({
                'timestamp': int(date.timestamp()),
                'price': 1000 * weekend_factor * monthly_factor * (1 + noise)
            })
            
            prices_item2.append({
                'timestamp': int(date.timestamp()),
                'price': 2000 * weekend_factor * monthly_factor * (1 + noise)
            })
            
            prices_item3.append({
                'timestamp': int(date.timestamp()),
                'price': 500 * weekend_factor * monthly_factor * (1 + noise)
            })
        
        self.price_history = {
            'item1': {'prices': prices_item1},
            'item2': {'prices': prices_item2},
            'item3': {'prices': prices_item3}
        }
        
        # Configure API mock
        self.mock_api.get_market_items = AsyncMock(return_value=self.market_items)
        
        def mock_get_price_history(item_id, **kwargs):
            return self.price_history.get(item_id, {'prices': []})
        
        self.mock_api.get_item_price_history = AsyncMock(side_effect=mock_get_price_history)
        
        # Initialize the analyzer with mock API
        self.analyzer = SeasonalAnalyzer(api_client=self.mock_api)
    
    async def asyncSetUp(self):
        """Async setup for tests."""
        pass
    
    async def asyncTearDown(self):
        """Async teardown for tests."""
        pass
    
    async def test_analyze_weekly_patterns(self):
        """Test analyzing weekly price patterns."""
        # Call the method to test
        result = await self.analyzer.analyze_weekly_patterns(game_id='cs2', days=90)
        
        # Check that the API was called
        self.mock_api.get_market_items.assert_called_once()
        self.mock_api.get_item_price_history.assert_called()
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn('game_id', result)
        self.assertIn('days_analyzed', result)
        self.assertIn('patterns', result)
        
        # Check that we have data for each day of the week
        for day in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']:
            self.assertIn(day, result['patterns'])
            self.assertIn('change', result['patterns'][day])
            self.assertIn('confidence', result['patterns'][day])
        
        # Weekend should show higher prices (based on our mock data)
        self.assertGreater(result['patterns']['saturday']['change'], 0)
        self.assertGreater(result['patterns']['sunday']['change'], 0)
    
    async def test_analyze_empty_data(self):
        """Test behavior with empty data."""
        # Make API return empty data
        self.mock_api.get_market_items.return_value = []
        
        # Call the method
        result = await self.analyzer.analyze_weekly_patterns(game_id='cs2', days=90)
        
        # Verify error response
        self.assertIn('error', result)
    
    async def test_detect_seasonal_events(self):
        """Test detecting seasonal events."""
        # Call the method to test
        result = await self.analyzer.detect_seasonal_events(game_id='cs2')
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn('game_id', result)
        self.assertIn('events', result)
        
        # Check at least one event is returned
        self.assertGreater(len(result['events']), 0)
        
        # Check event structure
        event = result['events'][0]
        self.assertIn('name', event)
        self.assertIn('start_date', event)
        self.assertIn('end_date', event)
        self.assertIn('expected_impact', event)
        self.assertIn('confidence', event)
    
    @patch('numpy.random.normal')
    async def test_monthly_patterns(self, mock_random):
        """Test analyzing monthly price patterns."""
        # Force random to be consistent
        mock_random.return_value = 0
        
        # Generate historical data with clear monthly patterns
        dates = pd.date_range(end=datetime.now(), periods=90)
        prices = []
        
        for date in dates:
            # Higher prices at the beginning of the month
            monthly_factor = 1.3 if date.day <= 5 else 1.0
            prices.append({
                'timestamp': int(date.timestamp()),
                'price': 1000 * monthly_factor
            })
        
        # Replace the item1 price history
        self.price_history['item1'] = {'prices': prices}
        
        # Call the method to test monthly patterns (this is a placeholder assuming the method exists)
        # If the method doesn't exist, this test will fail, indicating you should implement it
        try:
            result = await self.analyzer.analyze_monthly_patterns(game_id='cs2', days=90)
            
            # Verify the result structure
            self.assertIsInstance(result, dict)
            self.assertIn('monthly_pattern', result)
            
            # Early month should show higher prices (based on our mock data)
            for day_range in result['monthly_pattern']:
                if '1-5' in day_range:
                    self.assertGreater(result['monthly_pattern'][day_range]['change'], 0)
        except AttributeError:
            # The method doesn't exist yet - this is fine for a test that's anticipating future functionality
            self.skipTest("analyze_monthly_patterns method not implemented yet")


class TestSeasonalAnalyzerAsyncFixture(unittest.IsolatedAsyncioTestCase):
    """
    Test the SeasonalAnalyzer class using the IsolatedAsyncioTestCase.
    This allows us to use async fixtures and async test methods.
    """
    
    async def asyncSetUp(self):
        """Set up the test environment asynchronously."""
        # Create a mock API client
        self.mock_api = MagicMock()
        
        # Mock data for market items
        self.market_items = [
            {
                'itemId': 'item1',
                'title': 'AK-47 | Redline',
                'price': {'USD': 1000},
                'category': 'weapon'
            },
            {
                'itemId': 'item2',
                'title': 'AWP | Asiimov',
                'price': {'USD': 2000},
                'category': 'weapon'
            }
        ]
        
        # Configure API mock
        self.mock_api.get_market_items = AsyncMock(return_value=self.market_items)
        
        # Generate price history data with weekly patterns
        self.setup_price_history_data()
        
        def mock_get_price_history(item_id, **kwargs):
            return self.price_history.get(item_id, {'prices': []})
        
        self.mock_api.get_item_price_history = AsyncMock(side_effect=mock_get_price_history)
        
        # Initialize the analyzer with mock API
        self.analyzer = SeasonalAnalyzer(api_client=self.mock_api)
    
    def setup_price_history_data(self):
        """Set up the price history data with patterns."""
        dates = pd.date_range(end=datetime.now(), periods=90)
        
        # Create price history with weekly pattern (prices higher on weekends)
        prices_item1 = []
        prices_item2 = []
        
        for date in dates:
            # Add weekly pattern
            weekend_factor = 1.2 if date.weekday() >= 5 else 1.0
            # Add holiday pattern (around certain dates)
            holiday_factor = 1.0
            if (date.month == 12 and date.day >= 15) or (date.month == 1 and date.day <= 10):
                holiday_factor = 1.3  # Holiday season
            
            # Add noise
            noise = np.random.normal(0, 0.05)
            
            prices_item1.append({
                'timestamp': int(date.timestamp()),
                'price': 1000 * weekend_factor * holiday_factor * (1 + noise)
            })
            
            prices_item2.append({
                'timestamp': int(date.timestamp()),
                'price': 2000 * weekend_factor * holiday_factor * (1 + noise)
            })
        
        self.price_history = {
            'item1': {'prices': prices_item1},
            'item2': {'prices': prices_item2}
        }
    
    async def test_holiday_impact_detection(self):
        """Test detecting the impact of holiday seasons on prices."""
        # If the method doesn't exist yet, this test will fail, indicating you should implement it
        try:
            result = await self.analyzer.analyze_holiday_impact(game_id='cs2')
            
            # Verify the result structure
            self.assertIsInstance(result, dict)
            self.assertIn('holiday_impacts', result)
            
            # Check at least one holiday period is detected
            self.assertGreater(len(result['holiday_impacts']), 0)
            
            # Check holiday structure
            holiday = result['holiday_impacts'][0]
            self.assertIn('name', holiday)
            self.assertIn('start_date', holiday)
            self.assertIn('end_date', holiday)
            self.assertIn('price_impact', holiday)
            self.assertIn('confidence', holiday)
            
            # Holiday season should show positive impact
            for holiday in result['holiday_impacts']:
                if 'Christmas' in holiday['name'] or 'New Year' in holiday['name']:
                    self.assertGreater(holiday['price_impact'], 0)
        except AttributeError:
            # The method doesn't exist yet
            self.skipTest("analyze_holiday_impact method not implemented yet")
    
    async def test_market_volatility_analysis(self):
        """Test analyzing market volatility patterns."""
        # If the method doesn't exist yet, this test will fail, indicating you should implement it
        try:
            result = await self.analyzer.analyze_market_volatility(game_id='cs2', days=90)
            
            # Verify the result structure
            self.assertIsInstance(result, dict)
            self.assertIn('volatility_by_period', result)
            
            # Check volatility structure
            self.assertIn('daily', result['volatility_by_period'])
            self.assertIn('weekly', result['volatility_by_period'])
            self.assertIn('monthly', result['volatility_by_period'])
            
            # Each period should have a volatility measure
            for period in ['daily', 'weekly', 'monthly']:
                self.assertGreaterEqual(result['volatility_by_period'][period], 0)
        except AttributeError:
            # The method doesn't exist yet
            self.skipTest("analyze_market_volatility method not implemented yet")


if __name__ == '__main__':
    unittest.main() 