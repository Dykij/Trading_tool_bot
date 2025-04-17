"""
Market Correlation Analyzer

This module provides functionality for analyzing correlations between different items
in the market, identifying price leaders, and detecting market segment relationships.
These insights can be used to develop trading strategies based on market correlations.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
from scipy.stats import pearsonr
from scipy import stats
from scipy.cluster import hierarchy
import asyncio
import time
import matplotlib.pyplot as plt
import seaborn as sns
from statsmodels.tsa.stattools import grangercausalitytests, adfuller
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
from sklearn.cluster import KMeans, DBSCAN
from sklearn.preprocessing import StandardScaler
from joblib import Memory
from concurrent.futures import ThreadPoolExecutor
import warnings

# Configure logging
logger = logging.getLogger('market_correlation')

# Setup memory cache
cache_dir = '.correlation_cache'
memory = Memory(cache_dir, verbose=0)

class MarketCorrelationAnalyzer:
    """
    Analyzes correlations between different items and market segments to identify
    relationships that can be used for trading strategies.
    """
    
    def __init__(self, api_client=None, ml_predictor=None):
        """
        Initialize the market correlation analyzer.
        
        Args:
            api_client: Client for the market API
            ml_predictor: The machine learning predictor for additional analysis
        """
        self.api = api_client
        self.ml_predictor = ml_predictor
        self.correlation_cache = {}
        self._setup_logger()
        self.warning_shown = False
    
    def _setup_logger(self):
        """Configure the logger for this class."""
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
    
    async def analyze_item_correlations(self, game_id: str, items: List[str], 
                                        days: int = 30, min_correlation: float = 0.7,
                                        method: str = 'pearson', 
                                        preprocess: bool = True,
                                        preprocessing_methods: List[str] = None) -> Dict[str, Any]:
        """
        Analyze correlations between items.
        
        Args:
            game_id: The ID of the game (e.g., 'csgo', 'dota2')
            items: List of item names to analyze
            days: Number of days of historical data to use
            min_correlation: Minimum correlation coefficient to consider
            method: Correlation method ('pearson', 'spearman', 'kendall', 'distance', 'mutual_info')
            preprocess: Whether to preprocess the data
            preprocessing_methods: List of preprocessing methods to apply
            
        Returns:
            Dictionary with correlation analysis results
        """
        if not self.api:
            self.logger.warning("API client not initialized, unable to fetch data")
            return {
                'error': 'API client not initialized',
                'correlation_matrix': pd.DataFrame(),
                'strongly_correlated_pairs': [],
                'price_leaders': [],
                'market_segments': [],
                'volatility_analysis': {}
            }
            
        if not self.ml_predictor:
            if not self.warning_shown:
                self.logger.warning("ML predictor not initialized, some analyses will be limited")
                self.warning_shown = True
        
        self.logger.info(f"Analyzing correlations between {len(items)} items in {game_id}")
        
        # Get historical data for all items
        price_data = []
        failed_items = []
        
        for item in items:
            try:
                # Get historical data through MLPredictor if available
                if self.ml_predictor and hasattr(self.ml_predictor, 'get_historical_data'):
                    item_data = await self.ml_predictor.get_historical_data(game_id, item, days)
                    
                    if item_data is not None and not item_data.empty:
                        # Rename the 'price' column to the item name for clarity
                        if 'price' in item_data.columns:
                            item_data = item_data.rename(columns={'price': item})
                            price_data.append(item_data[[item]])
                    else:
                        failed_items.append(item)
                else:
                    # Fallback: direct API call if available
                    self.logger.warning("ML predictor not available, falling back to direct API calls")
                    # Implementation depends on API capabilities
                    failed_items.append(item)
                    
            except Exception as e:
                self.logger.error(f"Error fetching data for {item}: {str(e)}")
                failed_items.append(item)
                
        if not price_data:
            self.logger.warning(f"No historical data found for any items in {game_id}")
            return {
                'error': 'No historical data found',
                'failed_items': failed_items
            }
            
        # Combine all price data into a single DataFrame
        try:
            combined_df = pd.concat(price_data, axis=1)
            
            # Align all time series to common dates
            aligned_df = await self._align_time_series(combined_df)
            
            # Preprocess data if requested
            if preprocess:
                aligned_df = await self.preprocess_data(aligned_df, preprocessing_methods)
                
            # Calculate correlation matrix
            if method == 'pearson':
                corr_matrix = aligned_df.corr(method='pearson')
            elif method == 'spearman':
                corr_matrix = aligned_df.corr(method='spearman')
            elif method == 'kendall':
                corr_matrix = aligned_df.corr(method='kendall')
            elif method == 'distance':
                # Distance correlation (captures non-linear relationships)
                corr_matrix = await self._calculate_distance_correlation(aligned_df)
            elif method == 'mutual_info':
                # Mutual information (information theory based)
                corr_matrix = await self._calculate_mutual_information(aligned_df)
            else:
                corr_matrix = aligned_df.corr(method='pearson')
                
            # Extract strongly correlated pairs
            strong_pairs = await self._extract_correlated_pairs(corr_matrix, min_correlation)
            
            # Detect market segments using clustering
            segments = await self._detect_market_segments(corr_matrix, min_correlation)
            
            # Identify price leaders using Granger causality
            leaders = await self._identify_price_leaders(aligned_df)
            
            return {
                'correlation_matrix': corr_matrix.to_dict(),
                'strongly_correlated_pairs': strong_pairs,
                'market_segments': segments,
                'price_leaders': leaders,
                'failed_items': failed_items,
                'method': method,
                'item_count': len(aligned_df.columns)
            }
            
        except Exception as e:
            self.logger.error(f"Error analyzing correlations: {str(e)}")
            return {
                'error': f'Analysis failed: {str(e)}',
                'failed_items': failed_items
            }
    
    @memory.cache
    async def _align_time_series(self, price_data: Dict[str, pd.DataFrame], 
                                preprocess: bool = True) -> pd.DataFrame:
        """
        Align multiple time series to a common time index and preprocess the data.
        
        Args:
            price_data: Dictionary of {item_name: dataframe} with historical price data
            preprocess: Whether to apply preprocessing
            
        Returns:
            DataFrame with aligned time series for all items
        """
        # Extract price series from each DataFrame
        price_series = {}
        
        for item, df in price_data.items():
            if 'price' in df.columns:
                price_series[item] = df['price']
            elif 'median_price' in df.columns:
                price_series[item] = df['median_price']
            else:
                self.logger.warning(f"No price column found for {item}, using first numerical column")
                numeric_cols = df.select_dtypes(include=[np.number]).columns
                if not numeric_cols.empty:
                    price_series[item] = df[numeric_cols[0]]
                else:
                    self.logger.error(f"No numerical data found for {item}")
                    continue
        
        if not price_series:
            self.logger.error("No valid price series found")
            return pd.DataFrame()
        
        # Create a common DataFrame with all price series
        aligned_df = pd.DataFrame(price_series)
        
        # Handle missing values
        if preprocess:
            # Replace outliers with NaN (values more than 3 std devs from mean)
            for col in aligned_df.columns:
                mean = aligned_df[col].mean()
                std = aligned_df[col].std()
                outlier_mask = (aligned_df[col] - mean).abs() > 3 * std
                aligned_df.loc[outlier_mask, col] = np.nan
            
            # Fill missing values using forward fill then backward fill
            aligned_df = aligned_df.fillna(method='ffill').fillna(method='bfill')
            
            # Apply cubic interpolation for remaining NaN values
            aligned_df = aligned_df.interpolate(method='cubic', limit_direction='both')
            
            # Normalize data
            for col in aligned_df.columns:
                aligned_df[col] = (aligned_df[col] - aligned_df[col].min()) / (aligned_df[col].max() - aligned_df[col].min())
        else:
            # Simple missing value handling
            aligned_df = aligned_df.fillna(method='ffill').fillna(method='bfill')
        
        return aligned_df
    
    async def _calculate_distance_correlation(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate distance correlation matrix.
        
        Distance correlation can detect non-linear relationships.
        
        Args:
            data: DataFrame with price time series
            
        Returns:
            Distance correlation matrix
        """
        from scipy.spatial.distance import pdist, squareform
        import numpy as np
        
        # Initialize empty correlation matrix
        n = len(data.columns)
        corr_matrix = pd.DataFrame(np.zeros((n, n)), 
                                 index=data.columns, 
                                 columns=data.columns)
        
        # Fill diagonal with 1s
        np.fill_diagonal(corr_matrix.values, 1)
        
        # Calculate distance correlation for each pair
        for i in range(n):
            for j in range(i+1, n):
                col_i = data.columns[i]
                col_j = data.columns[j]
                
                # Get data for both columns, removing NaN rows
                pair_data = data[[col_i, col_j]].dropna()
                
                if len(pair_data) > 5:  # Need sufficient data
                    # Calculate distance matrices
                    X = pair_data[col_i].values.reshape(-1, 1)
                    Y = pair_data[col_j].values.reshape(-1, 1)
                    
                    # Distance matrices
                    dist_X = squareform(pdist(X))
                    dist_Y = squareform(pdist(Y))
                    
                    # Double centering
                    n = len(X)
                    H = np.eye(n) - np.ones((n, n)) / n
                    
                    dCovXY = np.sqrt(np.sum(np.multiply(H @ dist_X @ H, H @ dist_Y @ H)) / (n * n))
                    dVarX = np.sqrt(np.sum(np.multiply(H @ dist_X @ H, H @ dist_X @ H)) / (n * n))
                    dVarY = np.sqrt(np.sum(np.multiply(H @ dist_Y @ H, H @ dist_Y @ H)) / (n * n))
                    
                    # Distance correlation
                    if dVarX > 0 and dVarY > 0:
                        dCor = dCovXY / np.sqrt(dVarX * dVarY)
                    else:
                        dCor = 0
                    
                    corr_matrix.loc[col_i, col_j] = dCor
                    corr_matrix.loc[col_j, col_i] = dCor
        
        return corr_matrix
    
    async def _calculate_mutual_information(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate mutual information matrix.
        
        Mutual information measures how much knowing one variable 
        reduces uncertainty about the other.
        
        Args:
            data: DataFrame with price time series
            
        Returns:
            Mutual information matrix (normalized to [0, 1])
        """
        from sklearn.feature_selection import mutual_info_regression
        import numpy as np
        
        # Initialize empty matrix
        n = len(data.columns)
        mi_matrix = pd.DataFrame(np.zeros((n, n)), 
                               index=data.columns, 
                               columns=data.columns)
        
        # Fill diagonal with 1s
        np.fill_diagonal(mi_matrix.values, 1)
        
        # Calculate MI for each pair
        for i in range(n):
            for j in range(i+1, n):
                col_i = data.columns[i]
                col_j = data.columns[j]
                
                # Get data for both columns, removing NaN rows
                pair_data = data[[col_i, col_j]].dropna()
                
                if len(pair_data) > 5:  # Need sufficient data
                    X = pair_data[col_i].values.reshape(-1, 1)
                    y = pair_data[col_j].values
                    
                    # Calculate mutual information
                    mi = mutual_info_regression(X, y)[0]
                    
                    # Normalize using entropy
                    from sklearn.metrics import mutual_info_score
                    x_discrete = pd.qcut(X.flatten(), 10, labels=False, duplicates='drop')
                    y_discrete = pd.qcut(y, 10, labels=False, duplicates='drop')
                    
                    # Calculate entropies
                    x_counts = np.bincount(x_discrete)
                    x_probs = x_counts / len(x_discrete)
                    h_x = -np.sum(x_probs * np.log2(x_probs + 1e-10))
                    
                    y_counts = np.bincount(y_discrete)
                    y_probs = y_counts / len(y_discrete)
                    h_y = -np.sum(y_probs * np.log2(y_probs + 1e-10))
                    
                    # Normalized MI
                    if h_x > 0 and h_y > 0:
                        mi_norm = mutual_info_score(x_discrete, y_discrete) / min(h_x, h_y)
                    else:
                        mi_norm = 0
                    
                    mi_matrix.loc[col_i, col_j] = mi_norm
                    mi_matrix.loc[col_j, col_i] = mi_norm
        
        return mi_matrix
    
    async def preprocess_data(self, price_df: pd.DataFrame, methods: List[str] = None) -> pd.DataFrame:
        """
        Preprocess time series data with multiple options.
        
        Args:
            price_df: DataFrame with price time series
            methods: List of preprocessing methods to apply. Options include:
                     ['log_transform', 'diff', 'standardize', 'outlier_removal', 
                      'moving_average', 'fillna_interpolate']
                      
        Returns:
            Preprocessed DataFrame
        """
        if price_df.empty:
            self.logger.warning("Empty price data, cannot preprocess")
            return price_df
            
        # Default preprocessing methods if none specified
        if methods is None:
            methods = ['fillna_interpolate', 'outlier_removal']
            
        processed_df = price_df.copy()
        
        for method in methods:
            try:
                if method == 'log_transform':
                    # Apply log transform to handle skewed price distributions
                    processed_df = processed_df.apply(lambda x: np.log1p(x))
                    
                elif method == 'diff':
                    # Calculate first differences to make series stationary
                    processed_df = processed_df.diff().dropna()
                    
                elif method == 'standardize':
                    # Standardize values (z-score)
                    processed_df = (processed_df - processed_df.mean()) / processed_df.std()
                    
                elif method == 'outlier_removal':
                    # Remove outliers using IQR method
                    for col in processed_df.columns:
                        series = processed_df[col].dropna()
                        if len(series) > 10:  # Only apply if enough data points
                            Q1 = series.quantile(0.25)
                            Q3 = series.quantile(0.75)
                            IQR = Q3 - Q1
                            lower_bound = Q1 - 1.5 * IQR
                            upper_bound = Q3 + 1.5 * IQR
                            processed_df.loc[processed_df[col] < lower_bound, col] = np.nan
                            processed_df.loc[processed_df[col] > upper_bound, col] = np.nan
                            
                elif method == 'moving_average':
                    # Apply moving average smoothing (7-day window)
                    processed_df = processed_df.rolling(window=7, min_periods=3).mean()
                    
                elif method == 'fillna_interpolate':
                    # Fill missing values using interpolation
                    processed_df = processed_df.interpolate(method='time').fillna(method='bfill').fillna(method='ffill')
                    
                self.logger.info(f"Applied preprocessing method: {method}")
                
            except Exception as e:
                self.logger.error(f"Error applying preprocessing method {method}: {str(e)}")
                
        return processed_df
    
    async def _extract_correlated_pairs(self, corr_matrix: pd.DataFrame, min_correlation: float = 0.7) -> List[Dict[str, Any]]:
        """
        Extract item pairs with strong correlations.
        
        Args:
            corr_matrix: Correlation matrix as a DataFrame
            min_correlation: Minimum correlation coefficient to consider as significant
            
        Returns:
            List of dictionaries with item pairs and their correlation values
        """
        strong_correlations = []
        
        # Get unique item pairs with strong correlations
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                item1 = corr_matrix.columns[i]
                item2 = corr_matrix.columns[j]
                corr_value = corr_matrix.iloc[i, j]
                
                if abs(corr_value) >= min_correlation:
                    corr_type = "positive" if corr_value > 0 else "negative"
                    strong_correlations.append({
                        'item1': item1,
                        'item2': item2,
                        'correlation': corr_value,
                        'type': corr_type
                    })
        
        # Sort by absolute correlation value (descending)
        strong_correlations.sort(key=lambda x: abs(x['correlation']), reverse=True)
        
        return strong_correlations
    
    async def _detect_market_segments(self, corr_matrix: pd.DataFrame, min_correlation: float = 0.7) -> List[Dict[str, Any]]:
        """
        Automatically detect market segments using clustering algorithms.
        
        Args:
            corr_matrix: Correlation matrix between items
            min_correlation: Minimum correlation to consider
            
        Returns:
            List of detected market segments with their members
        """
        if corr_matrix.empty:
            self.logger.warning("Empty correlation matrix, cannot detect market segments")
            return []
        
        # Convert correlation matrix to distance matrix (1 - abs(corr))
        distance_matrix = 1 - corr_matrix.abs()
        
        items = corr_matrix.columns
        n_clusters = min(5, len(items) - 1)
        
        # Hierarchical clustering
        linkage = hierarchy.linkage(distance_matrix, method='ward')
        labels = hierarchy.fcluster(linkage, n_clusters, criterion='maxclust')
        
        # Create segments
        segments = []
        for i in range(1, max(labels) + 1):
            segment_items = [items[j] for j in range(len(items)) if labels[j] == i]
            if segment_items:
                # Calculate average correlation within segment
                within_corr = 0
                count = 0
                for idx1, item1 in enumerate(segment_items):
                    for item2 in segment_items[idx1+1:]:
                        within_corr += corr_matrix.loc[item1, item2]
                        count += 1
                
                avg_correlation = within_corr / max(1, count)
                
                segments.append({
                    'segment_id': i,
                    'items': segment_items,
                    'size': len(segment_items),
                    'avg_internal_correlation': avg_correlation
                })
        
        # Sort segments by size (descending)
        segments.sort(key=lambda x: x['size'], reverse=True)
        
        return segments
    
    async def _identify_price_leaders(self, price_df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Identify price leaders using Granger causality tests.
        
        A price leader is an item whose price movements tend to precede
        price movements of other items.
        
        Args:
            price_df: DataFrame with aligned price time series
            
        Returns:
            List of items identified as price leaders with influenced items
        """
        if price_df.empty or price_df.shape[1] < 2:
            self.logger.warning("Insufficient data for price leader analysis")
            return []
        
        # Ensure data is stationary for Granger test
        stationary_df = pd.DataFrame()
        
        for col in price_df.columns:
            # Check stationarity
            result = adfuller(price_df[col].dropna())
            if result[1] > 0.05:  # Not stationary
                # Take first difference to make stationary
                stationary_df[col] = price_df[col].diff().dropna()
            else:
                stationary_df[col] = price_df[col]
        
        # Drop any remaining NaN values
        stationary_df = stationary_df.dropna()
        
        if stationary_df.empty or stationary_df.shape[0] < 5:
            self.logger.warning("Insufficient data after stationarity transformation")
            return []
        
        # Dictionary to track causality relationships
        causality_results = {}
        items = stationary_df.columns
        
        # Use ThreadPoolExecutor for parallel processing
        def test_causality(item1, item2):
            try:
                # Granger test: does item1 Granger-cause item2?
                test_df = pd.DataFrame({
                    'x': stationary_df[item1],
                    'y': stationary_df[item2]
                })
                
                # Run Granger causality test
                result = grangercausalitytests(test_df, maxlag=5, verbose=False)
                
                # Check if any lag has significant p-value
                significant_lags = []
                for lag in range(1, 6):
                    p_value = result[lag][0]['ssr_ftest'][1]
                    if p_value < 0.05:
                        significant_lags.append((lag, p_value))
                
                if significant_lags:
                    return (item1, item2, significant_lags, min(p for _, p in significant_lags))
                return None
            except Exception as e:
                self.logger.warning(f"Error in Granger test for {item1} -> {item2}: {str(e)}")
                return None
        
        # Create list of item pairs to test
        pairs_to_test = [(item1, item2) for item1 in items for item2 in items if item1 != item2]
        
        # Run tests in parallel
        with ThreadPoolExecutor(max_workers=min(8, len(pairs_to_test))) as executor:
            futures = [executor.submit(test_causality, item1, item2) for item1, item2 in pairs_to_test]
            results = [future.result() for future in futures]
        
        # Filter out None results and organize by leader
        leader_influence = {}
        
        for result in results:
            if result:
                leader, influenced, lags, min_p = result
                if leader not in leader_influence:
                    leader_influence[leader] = []
                
                leader_influence[leader].append({
                    'influenced_item': influenced,
                    'significant_lags': lags,
                    'min_p_value': min_p
                })
        
        # Format results
        price_leaders = []
        for leader, influenced_items in leader_influence.items():
            # Sort influenced items by p-value
            influenced_items.sort(key=lambda x: x['min_p_value'])
            
            price_leaders.append({
                'leader': leader,
                'influenced_count': len(influenced_items),
                'influenced_items': influenced_items,
                'avg_p_value': sum(item['min_p_value'] for item in influenced_items) / len(influenced_items)
            })
        
        # Sort by number of influenced items (descending)
        price_leaders.sort(key=lambda x: x['influenced_count'], reverse=True)
        
        return price_leaders
    
    async def analyze_volatility(self, price_df: pd.DataFrame) -> Dict[str, Dict[str, float]]:
        """
        Analyze price volatility for each item.
        
        Args:
            price_df: DataFrame with aligned price time series
            
        Returns:
            Dictionary with volatility metrics for each item
        """
        if price_df.empty:
            self.logger.warning("Empty price data, cannot analyze volatility")
            return {}
        
        results = {}
        
        for item in price_df.columns:
            series = price_df[item].dropna()
            
            if len(series) < 3:
                self.logger.warning(f"Insufficient data points for {item}")
                continue
            
            # Calculate returns
            returns = series.pct_change().dropna()
            
            # Skip if we don't have enough return data
            if len(returns) < 2:
                continue
            
            # Calculate volatility metrics
            volatility = returns.std() * (252 ** 0.5)  # Annualized
            
            # Max drawdown
            cumulative = (1 + returns).cumprod()
            running_max = cumulative.cummax()
            drawdown = (cumulative / running_max) - 1
            max_drawdown = drawdown.min()
            
            # Range volatility (high-low spread)
            range_vol = (series.max() - series.min()) / series.mean()
            
            # Mean absolute deviation
            mad = returns.mad()
            
            # Analyze trends - simple linear regression
            x = np.arange(len(series))
            slope, intercept, r_value, p_value, std_err = stats.linregress(x, series)
            
            trend_strength = abs(r_value)
            trend_direction = "up" if slope > 0 else "down"
            
            results[item] = {
                'daily_volatility': volatility,
                'max_drawdown': max_drawdown,
                'range_volatility': range_vol,
                'mean_absolute_deviation': mad,
                'trend_strength': trend_strength,
                'trend_direction': trend_direction
            }
        
        return results
    
    async def analyze_market_segments(self, game_id: str, min_items: int = 5, 
                                    max_items: int = 50, days: int = 30,
                                    min_correlation: float = 0.6) -> Dict[str, Any]:
        """
        Analyze market segments for a specific game.
        
        This method fetches popular items, analyzes their correlations,
        and detects distinct market segments.
        
        Args:
            game_id: The ID of the game (e.g., 'csgo', 'dota2')
            min_items: Minimum number of items to analyze
            max_items: Maximum number of items to analyze
            days: Number of days of historical data to use
            min_correlation: Minimum correlation to consider
            
        Returns:
            Dictionary with market segment analysis results
        """
        if not self.api:
            self.logger.warning("API client not initialized, unable to fetch data")
            return {'error': 'API client not initialized'}
            
        # Get popular items from the market
        try:
            # This assumes there's a method to get popular items
            # If not, we need to adapt this to use appropriate API methods
            popular_items = await self._get_popular_items(game_id, limit=max_items)
            
            if not popular_items or len(popular_items) < min_items:
                self.logger.warning(f"Not enough popular items found for {game_id}")
                return {'error': 'Insufficient items for analysis'}
                
            # Analyze correlations between these items
            correlation_results = await self.analyze_item_correlations(
                game_id=game_id,
                items=popular_items,
                days=days,
                min_correlation=min_correlation,
                method='spearman',  # More robust to non-linear relationships
                preprocess=True
            )
            
            # Add segment metadata
            for segment in correlation_results.get('market_segments', []):
                segment['metadata'] = await self._analyze_segment_metadata(
                    game_id, segment['items']
                )
            
            return correlation_results
            
        except Exception as e:
            self.logger.error(f"Error analyzing market segments: {str(e)}")
            return {'error': f'Analysis failed: {str(e)}'}
    
    async def _get_popular_items(self, game_id: str, limit: int = 50) -> List[str]:
        """
        Get popular items from the market.
        
        Args:
            game_id: The ID of the game
            limit: Maximum number of items to return
            
        Returns:
            List of popular item names
        """
        # This is a placeholder - actual implementation depends on API capabilities
        try:
            if hasattr(self.api, 'get_popular_items'):
                items = await self.api.get_popular_items(game_id, limit=limit)
                return [item['name'] for item in items if 'name' in item]
            else:
                # Fallback: search for items
                items = await self.api.search_items(game_id, limit=limit)
                return [item.get('name') or item.get('title') 
                        for item in items if 'name' in item or 'title' in item]
        except Exception as e:
            self.logger.error(f"Error fetching popular items: {str(e)}")
            return []
    
    async def _analyze_segment_metadata(self, game_id: str, items: List[str]) -> Dict[str, Any]:
        """
        Analyze metadata for a market segment.
        
        Args:
            game_id: The ID of the game
            items: List of items in the segment
            
        Returns:
            Dictionary with segment metadata
        """
        metadata = {
            'avg_price': 0,
            'price_range': (0, 0),
            'common_tags': set(),
            'avg_volume': 0
        }
        
        if not items:
            return metadata
            
        try:
            # Fetch item details
            prices = []
            volumes = []
            all_tags = []
            
            for item in items:
                # This assumes there's a method to get item details
                # If not, we need to adapt this to use appropriate API methods
                details = await self._get_item_details(game_id, item)
                
                if details:
                    if 'price' in details:
                        prices.append(details['price'])
                    if 'volume' in details:
                        volumes.append(details['volume'])
                    if 'tags' in details:
                        all_tags.append(set(details['tags']))
            
            # Calculate metadata
            if prices:
                metadata['avg_price'] = sum(prices) / len(prices)
                metadata['price_range'] = (min(prices), max(prices))
            
            if volumes:
                metadata['avg_volume'] = sum(volumes) / len(volumes)
            
            # Find common tags
            if all_tags:
                common_tags = all_tags[0]
                for tags in all_tags[1:]:
                    common_tags &= tags
                metadata['common_tags'] = common_tags
            
            return metadata
            
        except Exception as e:
            self.logger.error(f"Error analyzing segment metadata: {str(e)}")
            return metadata
    
    async def _get_item_details(self, game_id: str, item_name: str) -> Dict[str, Any]:
        """
        Get details for a specific item.
        
        Args:
            game_id: The ID of the game
            item_name: The name of the item
            
        Returns:
            Dictionary with item details
        """
        # This is a placeholder - actual implementation depends on API capabilities
        try:
            if hasattr(self.api, 'get_item_details'):
                return await self.api.get_item_details(game_id, item_name)
            else:
                # Fallback: search for the specific item
                items = await self.api.search_items(game_id, query=item_name, limit=1)
                if items and len(items) > 0:
                    return items[0]
                return {}
        except Exception as e:
            self.logger.error(f"Error fetching item details: {str(e)}")
            return {}
    
    async def generate_correlation_report(self, game_id: str, items: List[str], 
                                        days: int = 30, output_format: str = 'dict') -> Dict[str, Any]:
        """
        Generate a comprehensive correlation report.
        
        Args:
            game_id: The ID of the game
            items: List of items to analyze
            days: Number of days of historical data to use
            output_format: Output format ('dict', 'json', 'html')
            
        Returns:
            Dictionary with the correlation report
        """
        # Analyze correlations
        correlation_results = await self.analyze_item_correlations(
            game_id=game_id,
            items=items,
            days=days,
            min_correlation=0.6,
            method='spearman',
            preprocess=True
        )
        
        if 'error' in correlation_results:
            return correlation_results
        
        # Generate report
        report = {
            'report_type': 'Market Correlation Analysis',
            'game_id': game_id,
            'timestamp': datetime.now().isoformat(),
            'analysis_period': f"{days} days",
            'items_analyzed': len(items),
            'summary': {
                'price_leaders': [leader['leader'] for leader in correlation_results.get('price_leaders', [])],
                'market_segments': len(correlation_results.get('market_segments', [])),
                'strongly_correlated_pairs': len(correlation_results.get('strongly_correlated_pairs', [])),
                'failed_items': correlation_results.get('failed_items', [])
            },
            'detailed_results': correlation_results
        }
        
        if output_format == 'html':
            return self._convert_report_to_html(report)
        elif output_format == 'json':
            return report
        else:
            return report
    
    def _convert_report_to_html(self, report: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert a report to HTML format.
        
        Args:
            report: The report dictionary
            
        Returns:
            Dictionary with HTML report
        """
        try:
            # Simple HTML conversion
            title = f"Market Correlation Report: {report['game_id']}"
            html = [
                f"<html><head><title>{title}</title>",
                "<style>body {font-family: Arial; max-width: 1200px; margin: 0 auto; padding: 20px;} ",
                "table {border-collapse: collapse; width: 100%;} ",
                "th, td {border: 1px solid #ddd; padding: 8px; text-align: left;} ",
                "th {background-color: #f2f2f2;}</style></head><body>",
                f"<h1>{title}</h1>",
                f"<p>Generated at: {report['timestamp']}</p>",
                f"<p>Analysis period: {report['analysis_period']}</p>",
                f"<p>Items analyzed: {report['items_analyzed']}</p>",
                "<h2>Summary</h2>"
            ]
            
            # Summary section
            summary = report['summary']
            html.append("<table><tr><th>Metric</th><th>Value</th></tr>")
            html.append(f"<tr><td>Price Leaders</td><td>{len(summary['price_leaders'])}</td></tr>")
            html.append(f"<tr><td>Market Segments</td><td>{summary['market_segments']}</td></tr>")
            html.append(f"<tr><td>Strongly Correlated Pairs</td><td>{summary['strongly_correlated_pairs']}</td></tr>")
            html.append(f"<tr><td>Failed Items</td><td>{len(summary['failed_items'])}</td></tr>")
            html.append("</table>")
            
            # Price leaders
            if 'price_leaders' in report['detailed_results']:
                html.append("<h2>Price Leaders</h2>")
                html.append("<table><tr><th>Leader</th><th>Influenced Items</th><th>Avg P-Value</th></tr>")
                for leader in report['detailed_results']['price_leaders']:
                    html.append(f"<tr><td>{leader['leader']}</td>")
                    html.append(f"<td>{leader['influenced_count']}</td>")
                    html.append(f"<td>{leader['avg_p_value']:.4f}</td></tr>")
                html.append("</table>")
            
            # Market segments
            if 'market_segments' in report['detailed_results']:
                html.append("<h2>Market Segments</h2>")
                html.append("<table><tr><th>Segment ID</th><th>Size</th><th>Avg Correlation</th><th>Items</th></tr>")
                for segment in report['detailed_results']['market_segments']:
                    html.append(f"<tr><td>{segment['segment_id']}</td>")
                    html.append(f"<td>{segment['size']}</td>")
                    html.append(f"<td>{segment.get('avg_internal_correlation', 0):.4f}</td>")
                    html.append(f"<td>{', '.join(segment['items'][:5])}")
                    if len(segment['items']) > 5:
                        html.append(f" and {len(segment['items']) - 5} more")
                    html.append("</td></tr>")
                html.append("</table>")
            
            html.append("</body></html>")
            
            report['html_report'] = ''.join(html)
            return report
            
        except Exception as e:
            self.logger.error(f"Error converting report to HTML: {str(e)}")
            report['html_report'] = f"<html><body><h1>Error generating report</h1><p>{str(e)}</p></body></html>"
            return report
    
    async def visualize_correlations(self, correlation_matrix: pd.DataFrame, 
                                   title: str = "Item Correlations") -> Dict[str, Any]:
        """
        Visualize the correlation matrix as a heatmap.
        
        Args:
            correlation_matrix: The correlation matrix to visualize
            title: The title for the plot
            
        Returns:
            Dictionary with visualization data
        """
        try:
            # Create a figure
            plt.figure(figsize=(12, 10))
            
            # Create a mask for the upper triangle
            mask = np.triu(np.ones_like(correlation_matrix, dtype=bool))
            
            # Generate a custom diverging colormap
            cmap = sns.diverging_palette(230, 20, as_cmap=True)
            
            # Draw the heatmap
            sns.heatmap(correlation_matrix, mask=mask, cmap=cmap, vmax=1, vmin=-1, center=0,
                        square=True, linewidths=.5, cbar_kws={"shrink": .5}, annot=True, fmt=".2f")
            
            plt.title(title)
            plt.tight_layout()
            
            # Save to a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                plt.savefig(tmp.name)
                tmp_filename = tmp.name
                
            plt.close()
            
            return {
                'status': 'success',
                'image_path': tmp_filename
            }
            
        except Exception as e:
            self.logger.error(f"Error visualizing correlations: {str(e)}")
            return {
                'status': 'error',
                'error': str(e)
            }