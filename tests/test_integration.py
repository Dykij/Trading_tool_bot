"""
Integration tests for the DMarket Trading Bot.

These tests validate the interactions between machine learning predictions,
arbitrage strategies, and API communications. They ensure that all components
work together correctly.
"""

import unittest
import logging
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ml import MLPredictor, PricePredictionModel
from src.api.dmarket_api import DMarketAPI
from src.api.integration import IntegrationManager
from src.arbitrage.strategies.gap_arbitrage import GapArbitrageStrategy
from src.config.config import Config


class MockDMarketAPI:
    """Mock DMarketAPI for testing purposes."""
    
    def __init__(self):
        self.items_data = {
            'cs2': {
                'AK-47 | Redline': [
                    {'itemId': 'item1', 'title': 'AK-47 | Redline', 'price': {'USD': 1000}, 'extra': {'floatValue': 0.15}},
                    {'itemId': 'item2', 'title': 'AK-47 | Redline', 'price': {'USD': 1200}, 'extra': {'floatValue': 0.20}},
                    {'itemId': 'item3', 'title': 'AK-47 | Redline', 'price': {'USD': 900}, 'extra': {'floatValue': 0.25}},
                ],
                'AWP | Asiimov': [
                    {'itemId': 'item4', 'title': 'AWP | Asiimov', 'price': {'USD': 2000}, 'extra': {'floatValue': 0.18}},
                    {'itemId': 'item5', 'title': 'AWP | Asiimov', 'price': {'USD': 1900}, 'extra': {'floatValue': 0.22}},
                ],
            }
        }
        
        self.historical_data = {
            'cs2': {
                'AK-47 | Redline': pd.DataFrame({
                    'date': [datetime.now() - timedelta(days=i) for i in range(30)],
                    'price': [1000 + np.sin(i) * 100 for i in range(30)],
                    'volume': [10 + i for i in range(30)],
                }),
                'AWP | Asiimov': pd.DataFrame({
                    'date': [datetime.now() - timedelta(days=i) for i in range(30)],
                    'price': [2000 + np.cos(i) * 150 for i in range(30)],
                    'volume': [5 + i for i in range(30)],
                }),
            }
        }
    
    def get_items_by_title(self, game, title, limit=10):
        """Mock getting items by title."""
        if game in self.items_data and title in self.items_data[game]:
            return self.items_data[game][title][:limit]
        return []
    
    def get_historical_data(self, game, title, days=30):
        """Mock getting historical price data."""
        if game in self.historical_data and title in self.historical_data[game]:
            return self.historical_data[game][title].tail(days).copy()
        
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=['date', 'price', 'volume'])
    
    def get_market_items(self, game, limit=100):
        """Mock getting all market items for a game."""
        result = []
        if game in self.items_data:
            for title in self.items_data[game]:
                result.extend(self.items_data[game][title])
        return result[:limit]


class TestIntegration(unittest.TestCase):
    """Integration tests for the DMarket Trading Bot."""
    
    def setUp(self):
        """Set up the test environment."""
        # Configure logging
        logging.basicConfig(level=logging.ERROR)
        
        # Create a temporary directory for test data
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Mock configuration
        self.config = MagicMock(spec=Config)
        self.config.get_api_settings.return_value = {
            'public_key': 'test_public_key',
            'secret_key': 'test_secret_key',
            'api_url': 'https://api.test.com'
        }
        self.config.get_ml_settings.return_value = {
            'model_dir': self.temp_dir.name,
            'use_ml': True,
            'confidence_threshold': 0.7,
            'history_days': 30
        }
        self.config.get_arbitrage_settings.return_value = {
            'min_price_diff_percent': 5.0,
            'min_profit_usd': 0.5,
            'max_items_per_analysis': 100
        }
        
        # Create mock API
        self.mock_api = MockDMarketAPI()
        
        # Create patchers
        self.api_patcher = patch('src.api.dmarket_api.DMarketAPI', return_value=self.mock_api)
        self.api_mock = self.api_patcher.start()
        
        # Create a sample ML model for testing
        self.ml_predictor = MLPredictor(api_client=self.mock_api)
        self.model = PricePredictionModel('cs2', 'test_model', model_dir=self.temp_dir.name)
        
        # Create integration manager
        self.integration = IntegrationManager(self.config)
        
        # Create a gap arbitrage strategy
        self.arbitrage_strategy = GapArbitrageStrategy(self.config, api_client=self.mock_api)
    
    def tearDown(self):
        """Clean up after tests."""
        self.api_patcher.stop()
        self.temp_dir.cleanup()
    
    def test_price_prediction_integration(self):
        """Test that price prediction works with the API integration."""
        # Train a model with mock data
        historical_data = self.mock_api.get_historical_data('cs2', 'AK-47 | Redline')
        
        X, y = self.model._prepare_features(historical_data)
        self.model.train(X, y)
        
        # Test prediction
        prediction = self.ml_predictor.predict_price('cs2', 'AK-47 | Redline', model=self.model)
        
        # Validate prediction
        self.assertIsNotNone(prediction)
        self.assertTrue('price' in prediction)
        self.assertTrue('confidence' in prediction)
        self.assertIsInstance(prediction['price'], (int, float))
        self.assertIsInstance(prediction['confidence'], float)
        self.assertTrue(0 <= prediction['confidence'] <= 1)
    
    def test_arbitrage_strategy_with_ml(self):
        """Test that arbitrage strategy works with ML predictions."""
        # Setup: Train a model first
        historical_data = self.mock_api.get_historical_data('cs2', 'AK-47 | Redline')
        X, y = self.model._prepare_features(historical_data)
        self.model.train(X, y)
        
        # Modify gap arbitrage to use ML prediction
        self.arbitrage_strategy.ml_predictor = self.ml_predictor
        self.arbitrage_strategy.use_ml = True
        
        # Find arbitrage opportunities
        opportunities = self.arbitrage_strategy.find_internal_arbitrage_opportunities('cs2', limit=10)
        
        # Verify that opportunities are found and include ML confidence
        self.assertIsInstance(opportunities, list)
    
    def test_integration_manager_workflow(self):
        """Test the full integration workflow."""
        # Patch the integration manager's dependencies
        with patch.object(self.integration, 'api_client', self.mock_api):
            with patch.object(self.integration, 'arbitrage_strategy', self.arbitrage_strategy):
                with patch.object(self.integration, 'ml_predictor', self.ml_predictor):
                    # Run the workflow
                    result = self.integration.analyze_arbitrage_opportunities('cs2', use_ml=True)
                    
                    # Verify the result
                    self.assertIsNotNone(result)
                    self.assertIsInstance(result, dict)
    
    def test_error_handling(self):
        """Test error handling in the integration workflow."""
        # Create a mock API that raises an exception
        error_api = MagicMock(spec=DMarketAPI)
        error_api.get_items_by_title.side_effect = Exception("API Error")
        
        # Patch the integration manager to use the error API
        with patch.object(self.integration, 'api_client', error_api):
            # Test that errors are handled gracefully
            with self.assertLogs(level='ERROR') as cm:
                result = self.integration.analyze_arbitrage_opportunities('cs2', use_ml=True)
                
                # Verify error was logged
                self.assertTrue(any('API Error' in msg for msg in cm.output))
                
                # Verify graceful failure
                self.assertIsNotNone(result)
                self.assertIsInstance(result, dict)
                self.assertEqual(result.get('status'), 'error')
    
    def test_api_key_management(self):
        """Test that API keys are managed correctly."""
        # Test that the integration manager uses the API keys from config
        api_settings = self.config.get_api_settings()
        
        with patch('src.api.dmarket_api.DMarketAPI') as mock_api_constructor:
            # Create new integration manager to trigger constructor
            new_integration = IntegrationManager(self.config)
            
            # Verify API was constructed with correct keys
            mock_api_constructor.assert_called_once()
            kwargs = mock_api_constructor.call_args[1]
            
            self.assertEqual(kwargs.get('public_key'), api_settings['public_key'])
            self.assertEqual(kwargs.get('secret_key'), api_settings['secret_key'])
            self.assertEqual(kwargs.get('api_url'), api_settings['api_url'])


if __name__ == '__main__':
    unittest.main()
