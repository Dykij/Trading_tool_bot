"""
Unit tests for the machine learning prediction components.

These tests validate the functionality of the MLPredictor, PricePredictionModel,
and related classes that handle price prediction and model management.
"""

import unittest
import os
import sys
import tempfile
import json
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.ml import MLPredictor, PricePredictionModel, ModelManager
from src.config.config import Config


class TestPricePredictionModel(unittest.TestCase):
    """Test the PricePredictionModel class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for model storage
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create test data
        dates = [datetime.now() - timedelta(days=i) for i in range(30)]
        prices = [1000 + np.sin(i) * 100 for i in range(30)]
        volumes = [10 + i for i in range(30)]
        volatility = [abs(np.sin(i) * 0.1) for i in range(30)]
        
        self.test_data = pd.DataFrame({
            'date': dates,
            'price': prices,
            'volume': volumes,
            'volatility': volatility
        })
        
        # Initialize model
        self.model = PricePredictionModel('cs2', 'test_model', model_dir=self.temp_dir.name)
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_model_initialization(self):
        """Test that the model initializes correctly."""
        self.assertEqual(self.model.game_id, 'cs2')
        self.assertEqual(self.model.model_name, 'test_model')
        self.assertEqual(str(self.model.model_dir), str(self.temp_dir.name))
        self.assertIsNone(self.model.model)
    
    def test_prepare_features(self):
        """Test feature preparation from historical data."""
        X, y = self.model._prepare_features(self.test_data)
        
        # Check that features and target were created correctly
        self.assertIsNotNone(X)
        self.assertIsNotNone(y)
        self.assertTrue(isinstance(X, np.ndarray) or isinstance(X, pd.DataFrame))
        self.assertTrue(isinstance(y, np.ndarray) or isinstance(y, pd.Series))
        
        # Check that feature count is appropriate (depends on implementation)
        # Typically includes lagged prices, moving averages, volume indicators
        self.assertTrue(X.shape[1] >= 1)
        
        # Check that length of features and target match
        self.assertEqual(len(X), len(y))
    
    def test_train_and_predict(self):
        """Test training and prediction."""
        # Prepare features
        X, y = self.model._prepare_features(self.test_data)
        
        # Train model
        self.model.train(X, y)
        
        # Check that model was created
        self.assertIsNotNone(self.model.model)
        
        # Test prediction on the same data
        prediction = self.model.predict(X[-1].reshape(1, -1))
        
        # Check prediction is a numeric value
        self.assertIsInstance(prediction, (float, np.float64, np.float32))
    
    def test_save_and_load_model(self):
        """Test saving and loading the model."""
        # Prepare features and train model
        X, y = self.model._prepare_features(self.test_data)
        self.model.train(X, y)
        
        # Save model
        model_path = self.model.save()
        
        # Check that file was created
        self.assertTrue(os.path.exists(model_path))
        
        # Create a new model instance
        new_model = PricePredictionModel('cs2', 'test_model', model_dir=self.temp_dir.name)
        
        # Load model
        new_model.load()
        
        # Check that model was loaded
        self.assertIsNotNone(new_model.model)
        
        # Ensure predictions are the same from both models
        original_prediction = self.model.predict(X[-1].reshape(1, -1))
        loaded_prediction = new_model.predict(X[-1].reshape(1, -1))
        
        # Check predictions are very close (they might not be identical due to serialization differences)
        self.assertAlmostEqual(original_prediction, loaded_prediction, places=5)
    
    def test_model_evaluation(self):
        """Test model evaluation metrics."""
        # Prepare features with an 80/20 train/test split
        X, y = self.model._prepare_features(self.test_data)
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]
        
        # Train model on training data
        self.model.train(X_train, y_train)
        
        # Evaluate model on test data
        metrics = self.model.evaluate(X_test, y_test)
        
        # Check that metrics were calculated
        self.assertIsNotNone(metrics)
        self.assertIn('mse', metrics)
        self.assertIn('rmse', metrics)
        self.assertIn('mae', metrics)
        self.assertIn('r2', metrics)
        
        # Check that metrics are within reasonable ranges
        self.assertGreaterEqual(metrics['r2'], -1.0)  # R² can be negative for poor models
        self.assertLessEqual(metrics['r2'], 1.0)      # R² is at most 1.0
        self.assertGreaterEqual(metrics['mse'], 0.0)  # MSE is non-negative
        self.assertGreaterEqual(metrics['rmse'], 0.0) # RMSE is non-negative
        self.assertGreaterEqual(metrics['mae'], 0.0)  # MAE is non-negative


class TestModelManager(unittest.TestCase):
    """Test the ModelManager class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for model storage
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Initialize the model manager
        self.manager = ModelManager(model_dir=self.temp_dir.name)
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_create_model(self):
        """Test creating a new model."""
        # Create a new model
        model = self.manager.create_model('cs2', 'test_model')
        
        # Check that model was created correctly
        self.assertIsNotNone(model)
        self.assertEqual(model.game_id, 'cs2')
        self.assertEqual(model.model_name, 'test_model')
        self.assertEqual(model.model_dir, self.temp_dir.name)
    
    def test_get_model(self):
        """Test getting an existing model."""
        # Create test data
        test_data = pd.DataFrame({
            'date': [datetime.now() - timedelta(days=i) for i in range(10)],
            'price': [1000 + i * 10 for i in range(10)],
            'volume': [5 + i for i in range(10)]
        })
        
        # Create and train a model
        model = self.manager.create_model('cs2', 'test_model')
        X, y = model._prepare_features(test_data)
        model.train(X, y)
        model.save()
        
        # Get the model
        retrieved_model = self.manager.get_model('cs2', 'test_model')
        
        # Check that model was retrieved correctly
        self.assertIsNotNone(retrieved_model)
        self.assertEqual(retrieved_model.game_id, 'cs2')
        self.assertEqual(retrieved_model.model_name, 'test_model')
        
        # Ensure model is loaded
        self.assertIsNotNone(retrieved_model.model)
    
    def test_list_models(self):
        """Test listing all available models."""
        # Create several models
        models = [
            ('cs2', 'ak47_model'),
            ('cs2', 'awp_model'),
            ('dota2', 'arcana_model')
        ]
        
        for game_id, model_name in models:
            model = self.manager.create_model(game_id, model_name)
            # Create a mock trained model
            model.model = MagicMock()
            model.save()
        
        # List all models
        all_models = self.manager.list_models()
        
        # Check that all created models are listed
        self.assertEqual(len(all_models), len(models))
        
        # Check that models are organized by game
        games = set(game for game, _ in models)
        for game in games:
            self.assertIn(game, all_models)
    
    def test_delete_model(self):
        """Test deleting a model."""
        # Create and save a model
        model = self.manager.create_model('cs2', 'test_model')
        model.model = MagicMock()  # Mock a trained model
        model_path = model.save()
        
        # Verify model file exists
        self.assertTrue(os.path.exists(model_path))
        
        # Delete the model
        result = self.manager.delete_model('cs2', 'test_model')
        
        # Check that deletion was successful
        self.assertTrue(result)
        
        # Verify model file no longer exists
        self.assertFalse(os.path.exists(model_path))
        
        # Verify model is no longer listed
        models = self.manager.list_models()
        if 'cs2' in models:
            self.assertNotIn('test_model', models['cs2'])


class TestMLPredictor(unittest.TestCase):
    """Test the MLPredictor class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a temporary directory for model storage
        self.temp_dir = tempfile.TemporaryDirectory()
        
        # Create mock API client
        self.mock_api = MagicMock()
        
        # Set up historical data return value
        self.historical_data = pd.DataFrame({
            'date': [datetime.now() - timedelta(days=i) for i in range(30)],
            'price': [1000 + np.sin(i) * 100 for i in range(30)],
            'volume': [10 + i for i in range(30)]
        })
        
        self.mock_api.get_historical_data = MagicMock(return_value=self.historical_data)
        
        # Initialize the predictor with mock API
        self.predictor = MLPredictor(api_client=self.mock_api, model_dir=self.temp_dir.name)
    
    def tearDown(self):
        """Clean up after tests."""
        self.temp_dir.cleanup()
    
    def test_train_model(self):
        """Test training a new price prediction model."""
        # Train a model
        import asyncio
        model = asyncio.run(self.predictor.train_model('cs2', 'AK-47 | Redline', model_type='RandomForest'))
        
        # Check that model was created
        self.assertIsNotNone(model)
        self.assertEqual(model.game_id, 'cs2')
        self.assertIsNotNone(model.model)
        
        # Verify API was called to get historical data
        self.mock_api.get_historical_data.assert_called_once()
    
    def test_predict_price(self):
        """Test predicting the price of an item."""
        # Train a model first
        import asyncio
        model = asyncio.run(self.predictor.train_model('cs2', 'AK-47 | Redline', model_type='RandomForest'))
        
        # Predict price
        prediction = asyncio.run(self.predictor.predict_price('cs2', 'AK-47 | Redline'))
        
        # Check prediction structure
        self.assertIsNotNone(prediction)
        self.assertIn('price', prediction)
        self.assertIn('confidence', prediction)
        
        # Verify prediction values
        self.assertIsInstance(prediction['price'], (int, float))
        self.assertIsInstance(prediction['confidence'], float)
        self.assertTrue(0 <= prediction['confidence'] <= 1)
    
    def test_find_investment_opportunities(self):
        """Test finding investment opportunities."""
        # Mock market items
        market_items = [
            {'title': 'AK-47 | Redline', 'price': {'USD': 1000}},
            {'title': 'AWP | Asiimov', 'price': {'USD': 2000}},
            {'title': 'M4A4 | Howl', 'price': {'USD': 5000}}
        ]
        self.mock_api.get_market_items = MagicMock(return_value=market_items)
        
        # Mock price predictions to make one item an attractive investment
        def mock_predict_price(game, title, **kwargs):
            if title == 'AK-47 | Redline':
                return {'price': 1200, 'confidence': 0.8}  # 20% ROI
            elif title == 'AWP | Asiimov':
                return {'price': 2100, 'confidence': 0.7}  # 5% ROI
            else:
                return {'price': 5100, 'confidence': 0.6}  # 2% ROI
        
        # Patch the predict_price method
        with patch.object(self.predictor, 'predict_price', side_effect=mock_predict_price):
            # Find investment opportunities
            # Используем loop.run_until_complete для запуска асинхронного метода
            import asyncio
            opportunities = asyncio.run(self.predictor.find_investment_opportunities('cs2', min_roi=0.1))
            
            # Check opportunities
            self.assertIsInstance(opportunities, list)
            self.assertEqual(len(opportunities), 1)  # Only AK-47 should meet criteria
            
            # Check opportunity data
            opportunity = opportunities[0]
            self.assertEqual(opportunity['title'], 'AK-47 | Redline')
            self.assertIn('current_price', opportunity)
            self.assertIn('predicted_price', opportunity)
            self.assertIn('roi', opportunity)
            self.assertIn('confidence', opportunity)
            
            # Verify ROI calculation
            self.assertAlmostEqual(opportunity['roi'], 0.2, places=1)  # 20% ROI


if __name__ == '__main__':
    unittest.main() 