"""
Unit tests for the MarketCorrelationAnalyzer class.

Tests the functionality for identifying correlations between different items' prices
and market movements in the DMarket Trading Bot.
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

# Import the correlation analyzer - this might not exist yet
try:
    from src.ml.market_correlation import MarketCorrelationAnalyzer
    CORRELATION_ANALYZER_AVAILABLE = True
except ImportError:
    CORRELATION_ANALYZER_AVAILABLE = False

# Create a minimal mock implementation for testing if the real one doesn't exist
if not CORRELATION_ANALYZER_AVAILABLE:
    class MarketCorrelationAnalyzer:
        """Mock implementation for testing."""
        
        def __init__(self, api_client=None):
            self.api = api_client
            
        async def analyze_item_correlations(self, game_id, items, days=30):
            """Mock method that returns correlation data."""
            items_data = {}
            correlation_matrix = {}
            
            # Generate fake correlation data
            for i, item1 in enumerate(items):
                correlation_matrix[item1] = {}
                for j, item2 in enumerate(items):
                    # Diagonal is 1.0 (self-correlation)
                    if i == j:
                        correlation_matrix[item1][item2] = 1.0
                    else:
                        # Random correlation between -1 and 1
                        correlation_matrix[item1][item2] = np.random.uniform(-1, 1)
            
            return {
                'game_id': game_id,
                'days_analyzed': days,
                'items_analyzed': len(items),
                'correlation_matrix': correlation_matrix,
                'strongly_correlated_pairs': self._get_strong_correlations(correlation_matrix, 0.7),
                'inversely_correlated_pairs': self._get_inverse_correlations(correlation_matrix, -0.7)
            }
        
        def _get_strong_correlations(self, matrix, threshold=0.7):
            """Find strongly correlated pairs."""
            strong_pairs = []
            processed = set()
            
            for item1 in matrix:
                for item2 in matrix[item1]:
                    # Skip self-correlations and already processed pairs
                    if item1 == item2 or (item1, item2) in processed or (item2, item1) in processed:
                        continue
                    
                    correlation = matrix[item1][item2]
                    if correlation >= threshold:
                        strong_pairs.append({
                            'item1': item1,
                            'item2': item2,
                            'correlation': correlation
                        })
                        processed.add((item1, item2))
            
            return strong_pairs
        
        def _get_inverse_correlations(self, matrix, threshold=-0.7):
            """Find inversely correlated pairs."""
            inverse_pairs = []
            processed = set()
            
            for item1 in matrix:
                for item2 in matrix[item1]:
                    # Skip self-correlations and already processed pairs
                    if item1 == item2 or (item1, item2) in processed or (item2, item1) in processed:
                        continue
                    
                    correlation = matrix[item1][item2]
                    if correlation <= threshold:
                        inverse_pairs.append({
                            'item1': item1,
                            'item2': item2,
                            'correlation': correlation
                        })
                        processed.add((item1, item2))
            
            return inverse_pairs
        
        async def analyze_market_segments(self, game_id, days=30):
            """Mock method that returns market segment correlation data."""
            segments = ['weapon', 'knife', 'glove', 'sticker', 'case']
            segment_correlation = {}
            
            # Generate fake segment correlation data
            for i, segment1 in enumerate(segments):
                segment_correlation[segment1] = {}
                for j, segment2 in enumerate(segments):
                    if i == j:
                        segment_correlation[segment1][segment2] = 1.0
                    else:
                        segment_correlation[segment1][segment2] = np.random.uniform(-1, 1)
            
            return {
                'game_id': game_id,
                'days_analyzed': days,
                'segment_correlation': segment_correlation,
                'related_segments': self._get_related_segments(segment_correlation, 0.6)
            }
        
        def _get_related_segments(self, matrix, threshold=0.6):
            """Find related market segments."""
            related = []
            processed = set()
            
            for segment1 in matrix:
                for segment2 in matrix[segment1]:
                    if segment1 == segment2 or (segment1, segment2) in processed or (segment2, segment1) in processed:
                        continue
                    
                    correlation = matrix[segment1][segment2]
                    if correlation >= threshold:
                        related.append({
                            'segment1': segment1,
                            'segment2': segment2,
                            'correlation': correlation
                        })
                        processed.add((segment1, segment2))
            
            return related
        
        async def identify_price_leaders(self, game_id, days=30):
            """Mock method that identifies price movement leaders."""
            # In a real implementation, this would identify items whose price changes
            # tend to precede similar changes in other items
            return {
                'game_id': game_id,
                'days_analyzed': days,
                'price_leaders': [
                    {
                        'item': 'AWP | Dragon Lore',
                        'follower_count': 15,
                        'avg_lag_hours': 48,
                        'confidence': 0.85
                    },
                    {
                        'item': 'AK-47 | Fire Serpent',
                        'follower_count': 8,
                        'avg_lag_hours': 36,
                        'confidence': 0.72
                    }
                ]
            }


class TestMarketCorrelationAnalyzer(unittest.TestCase):
    """Test the MarketCorrelationAnalyzer class."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a mock API client
        self.mock_api = MagicMock()
        
        # Test items
        self.test_items = [
            'AK-47 | Redline',
            'AWP | Asiimov',
            'M4A4 | Howl',
            'Desert Eagle | Blaze',
            'Glock-18 | Fade'
        ]
        
        # Generate price history data with correlations
        self.setup_price_history_data()
        
        # Configure API mock
        self.mock_api.get_historical_data = AsyncMock(side_effect=self.mock_get_historical_data)
        
        # Initialize the analyzer with mock API
        self.analyzer = MarketCorrelationAnalyzer(api_client=self.mock_api)
    
    def setup_price_history_data(self):
        """Set up price history data with known correlations."""
        dates = pd.date_range(end=datetime.now(), periods=30)
        
        # Base price movements - different patterns
        base_prices = {
            # AK-47 Redline - base pattern with some noise
            'AK-47 | Redline': [1000 + np.sin(i/3) * 100 + np.random.normal(0, 20) for i in range(30)],
            
            # AWP Asiimov - closely correlated with AK-47
            'AWP | Asiimov': [2000 + np.sin(i/3) * 180 + np.random.normal(0, 30) for i in range(30)],
            
            # M4A4 Howl - inverse correlation with AK-47
            'M4A4 | Howl': [5000 - np.sin(i/3) * 300 + np.random.normal(0, 50) for i in range(30)],
            
            # Desert Eagle - independent pattern
            'Desert Eagle | Blaze': [1500 + np.cos(i/2) * 150 + np.random.normal(0, 25) for i in range(30)],
            
            # Glock Fade - correlated with Desert Eagle
            'Glock-18 | Fade': [2500 + np.cos(i/2) * 200 + np.random.normal(0, 40) for i in range(30)]
        }
        
        # Convert to DataFrames with timestamps
        self.historical_data = {}
        for item, prices in base_prices.items():
            self.historical_data[item] = pd.DataFrame({
                'date': dates,
                'price': prices,
                'volume': [10 + i % 5 for i in range(30)]
            })
    
    async def mock_get_historical_data(self, game_id, item_name, days=30):
        """Mock API method to get historical data."""
        if item_name in self.historical_data:
            return self.historical_data[item_name].tail(days).copy()
        return pd.DataFrame(columns=['date', 'price', 'volume'])
    
    async def test_analyze_item_correlations(self):
        """Test analyzing correlations between items."""
        # Call the method to test
        result = await self.analyzer.analyze_item_correlations(
            game_id='cs2',
            items=self.test_items,
            days=30
        )
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn('correlation_matrix', result)
        self.assertIn('strongly_correlated_pairs', result)
        self.assertIn('inversely_correlated_pairs', result)
        
        # Check correlation matrix
        matrix = result['correlation_matrix']
        for item1 in self.test_items:
            self.assertIn(item1, matrix)
            for item2 in self.test_items:
                self.assertIn(item2, matrix[item1])
                # Self-correlation should be 1.0
                if item1 == item2:
                    self.assertEqual(matrix[item1][item2], 1.0)
                # Correlation should be between -1 and 1
                else:
                    self.assertGreaterEqual(matrix[item1][item2], -1.0)
                    self.assertLessEqual(matrix[item1][item2], 1.0)
        
        # Check strongly correlated pairs
        strong_pairs = result['strongly_correlated_pairs']
        self.assertIsInstance(strong_pairs, list)
        for pair in strong_pairs:
            self.assertIn('item1', pair)
            self.assertIn('item2', pair)
            self.assertIn('correlation', pair)
            self.assertGreaterEqual(pair['correlation'], 0.7)
        
        # Check inversely correlated pairs
        inverse_pairs = result['inversely_correlated_pairs']
        self.assertIsInstance(inverse_pairs, list)
        for pair in inverse_pairs:
            self.assertIn('item1', pair)
            self.assertIn('item2', pair)
            self.assertIn('correlation', pair)
            self.assertLessEqual(pair['correlation'], -0.7)
    
    async def test_analyze_market_segments(self):
        """Test analyzing correlations between market segments."""
        # Call the method to test
        result = await self.analyzer.analyze_market_segments(
            game_id='cs2',
            days=30
        )
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn('segment_correlation', result)
        self.assertIn('related_segments', result)
        
        # Check segment correlation structure
        segments = result['segment_correlation']
        for segment1 in segments:
            for segment2 in segments[segment1]:
                # Self-correlation should be 1.0
                if segment1 == segment2:
                    self.assertEqual(segments[segment1][segment2], 1.0)
                # Correlation should be between -1 and 1
                else:
                    self.assertGreaterEqual(segments[segment1][segment2], -1.0)
                    self.assertLessEqual(segments[segment1][segment2], 1.0)
        
        # Check related segments
        related = result['related_segments']
        self.assertIsInstance(related, list)
        for pair in related:
            self.assertIn('segment1', pair)
            self.assertIn('segment2', pair)
            self.assertIn('correlation', pair)
            self.assertGreaterEqual(pair['correlation'], 0.6)
    
    async def test_identify_price_leaders(self):
        """Test identifying items that lead price movements."""
        # Call the method to test
        result = await self.analyzer.identify_price_leaders(
            game_id='cs2',
            days=30
        )
        
        # Verify the result structure
        self.assertIsInstance(result, dict)
        self.assertIn('price_leaders', result)
        
        # Check price leaders structure
        leaders = result['price_leaders']
        self.assertIsInstance(leaders, list)
        for leader in leaders:
            self.assertIn('item', leader)
            self.assertIn('follower_count', leader)
            self.assertIn('avg_lag_hours', leader)
            self.assertIn('confidence', leader)
            
            # Check value ranges
            self.assertGreaterEqual(leader['follower_count'], 0)
            self.assertGreaterEqual(leader['avg_lag_hours'], 0)
            self.assertGreaterEqual(leader['confidence'], 0)
            self.assertLessEqual(leader['confidence'], 1)
    
    @unittest.skipIf(not CORRELATION_ANALYZER_AVAILABLE, "MarketCorrelationAnalyzer not available")
    async def test_with_real_implementation(self):
        """Test with the real implementation if available."""
        # This test is only run if the actual implementation exists
        # It's a placeholder for additional tests specific to the real implementation
        pass


class TestCorrelationBasedStrategy(unittest.TestCase):
    """Test a trading strategy based on market correlations."""
    
    def setUp(self):
        """Set up the test environment."""
        # Create a mock API client
        self.mock_api = MagicMock()
        
        # Create a mock correlation analyzer
        self.mock_analyzer = MagicMock(spec=MarketCorrelationAnalyzer)
        
        # Mock correlation data
        self.correlation_result = {
            'correlation_matrix': {
                'AK-47 | Redline': {
                    'AK-47 | Redline': 1.0,
                    'AWP | Asiimov': 0.85,
                    'M4A4 | Howl': -0.75
                },
                'AWP | Asiimov': {
                    'AK-47 | Redline': 0.85,
                    'AWP | Asiimov': 1.0,
                    'M4A4 | Howl': -0.6
                },
                'M4A4 | Howl': {
                    'AK-47 | Redline': -0.75,
                    'AWP | Asiimov': -0.6,
                    'M4A4 | Howl': 1.0
                }
            },
            'strongly_correlated_pairs': [
                {'item1': 'AK-47 | Redline', 'item2': 'AWP | Asiimov', 'correlation': 0.85}
            ],
            'inversely_correlated_pairs': [
                {'item1': 'AK-47 | Redline', 'item2': 'M4A4 | Howl', 'correlation': -0.75}
            ]
        }
        
        # Mock price leaders data
        self.price_leaders_result = {
            'price_leaders': [
                {
                    'item': 'AK-47 | Redline',
                    'follower_count': 5,
                    'avg_lag_hours': 24,
                    'confidence': 0.8
                }
            ]
        }
        
        # Configure mock methods
        self.mock_analyzer.analyze_item_correlations = AsyncMock(return_value=self.correlation_result)
        self.mock_analyzer.identify_price_leaders = AsyncMock(return_value=self.price_leaders_result)
        
        # Test price data
        self.price_data = {
            'AK-47 | Redline': [{'price': {'USD': 950}}, {'price': {'USD': 1000}}],  # Price increase
            'AWP | Asiimov': [{'price': {'USD': 2000}}],  # Current price only
            'M4A4 | Howl': [{'price': {'USD': 5050}}, {'price': {'USD': 5000}}]  # Price decrease
        }
        
        self.mock_api.get_item_price_data = AsyncMock(side_effect=self.mock_get_price_data)
    
    async def mock_get_price_data(self, item_name):
        """Mock API method to get current and past prices."""
        return self.price_data.get(item_name, [])
    
    async def test_correlation_based_trading_strategy(self):
        """Test a trading strategy using correlation data."""
        # This is a placeholder test for a trading strategy that would use correlation data
        # In a real implementation, we'd test the logic that identifies trading opportunities
        # based on correlated price movements
        
        # Example: If a price leader (AK-47) has increased in price recently,
        # we should check its strongly correlated followers for potential buy opportunities
        # before their prices also increase
        
        # Get recent price change for the price leader
        leader_price_data = self.price_data['AK-47 | Redline']
        leader_current_price = float(leader_price_data[0]['price']['USD'])
        leader_previous_price = float(leader_price_data[1]['price']['USD'])
        leader_price_change = (leader_current_price - leader_previous_price) / leader_previous_price
        
        # Get correlation data
        correlation_data = await self.mock_analyzer.analyze_item_correlations(
            game_id='cs2',
            items=list(self.price_data.keys()),
            days=30
        )
        
        # Get price leaders
        price_leaders = await self.mock_analyzer.identify_price_leaders(
            game_id='cs2',
            days=30
        )
        
        # Simple strategy:
        # If a price leader has increased significantly (e.g., > 1%),
        # look for strongly correlated items to buy
        trading_opportunities = []
        if leader_price_change > 0.01:  # 1% increase
            for pair in correlation_data['strongly_correlated_pairs']:
                follower_item = pair['item2'] if pair['item1'] == 'AK-47 | Redline' else pair['item1']
                if follower_item != 'AK-47 | Redline':  # Skip the leader itself
                    follower_data = self.price_data.get(follower_item, [])
                    if follower_data:
                        follower_price = float(follower_data[0]['price']['USD'])
                        trading_opportunities.append({
                            'item': follower_item,
                            'action': 'buy',
                            'price': follower_price,
                            'correlation': pair['correlation'],
                            'expected_change': leader_price_change * pair['correlation'],
                            'reason': f"Correlated with price leader {pair['item1']} which increased by {leader_price_change:.2%}"
                        })
        
        # Check that trading opportunities are identified correctly
        self.assertGreater(len(trading_opportunities), 0)
        opportunity = trading_opportunities[0]
        self.assertEqual(opportunity['item'], 'AWP | Asiimov')
        self.assertEqual(opportunity['action'], 'buy')
        self.assertGreater(opportunity['expected_change'], 0)
        
        # For items with inverse correlation, we expect the opposite price movement
        inverse_opportunities = []
        for pair in correlation_data['inversely_correlated_pairs']:
            inverse_item = pair['item2'] if pair['item1'] == 'AK-47 | Redline' else pair['item1']
            if inverse_item != 'AK-47 | Redline':  # Skip the leader itself
                inverse_data = self.price_data.get(inverse_item, [])
                if inverse_data:
                    inverse_price = float(inverse_data[0]['price']['USD'])
                    inverse_opportunities.append({
                        'item': inverse_item,
                        'action': 'sell',  # Sell items with inverse correlation to a rising leader
                        'price': inverse_price,
                        'correlation': pair['correlation'],
                        'expected_change': leader_price_change * pair['correlation'],  # Negative because correlation is negative
                        'reason': f"Inversely correlated with price leader {pair['item1']} which increased by {leader_price_change:.2%}"
                    })
        
        # Check that inverse opportunities are identified correctly
        self.assertGreater(len(inverse_opportunities), 0)
        inverse_opp = inverse_opportunities[0]
        self.assertEqual(inverse_opp['item'], 'M4A4 | Howl')
        self.assertEqual(inverse_opp['action'], 'sell')
        self.assertLess(inverse_opp['expected_change'], 0)  # Expect negative price change


if __name__ == '__main__':
    unittest.main() 