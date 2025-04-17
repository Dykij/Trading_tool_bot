import inspect
import logging
import time
import functools
from typing import Callable, Dict, Any, Optional, List, Union, Tuple

logger = logging.getLogger(__name__)

class FunctionOptimizer:
    """
    Utility class for optimizing and monitoring function performance.
    
    This class provides tools for:
    - Performance profiling and timing
    - Function caching/memoization
    - Debugging and logging function calls
    - Rate limiting function execution
    """
    
    def __init__(self):
        self.performance_logs = {}
        self.cache = {}
        self.call_counts = {}
    
    @staticmethod
    def timer(func: Callable) -> Callable:
        """
        Decorator to measure and log function execution time.
        
        Args:
            func: The function to time
            
        Returns:
            Wrapped function with timing capabilities
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            execution_time = end_time - start_time
            
            # Log execution time
            logger.debug(f"Function '{func.__name__}' executed in {execution_time:.4f} seconds")
            
            return result
        return wrapper
    
    @staticmethod
    def memoize(func: Callable) -> Callable:
        """
        Decorator to cache function results based on input parameters.
        
        Args:
            func: The function to memoize
            
        Returns:
            Wrapped function with caching capabilities
        """
        cache = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Create a hashable key from the arguments
            key_args = tuple(args)
            key_kwargs = tuple(sorted(kwargs.items()))
            cache_key = (key_args, key_kwargs)
            
            # Return cached result if available
            if cache_key in cache:
                return cache[cache_key]
            
            # Otherwise compute, cache and return result
            result = func(*args, **kwargs)
            cache[cache_key] = result
            return result
        
        # Add a method to clear the cache
        wrapper.clear_cache = lambda: cache.clear()
        
        return wrapper
    
    @staticmethod
    def debug_log(func: Callable) -> Callable:
        """
        Decorator to log function calls with parameters and return values.
        
        Args:
            func: The function to debug
            
        Returns:
            Wrapped function with logging capabilities
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Log function call with parameters
            args_repr = [repr(a) for a in args]
            kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
            signature = ", ".join(args_repr + kwargs_repr)
            
            logger.debug(f"Calling {func.__name__}({signature})")
            
            try:
                result = func(*args, **kwargs)
                logger.debug(f"Function {func.__name__} returned {result!r}")
                return result
            except Exception as e:
                logger.exception(f"Function {func.__name__} raised {e.__class__.__name__}: {e}")
                raise
        
        return wrapper
    
    @staticmethod
    def rate_limit(calls: int, period: float = 1.0) -> Callable:
        """
        Decorator to limit how often a function can be called.
        
        Args:
            calls: Number of calls allowed per period
            period: Time period in seconds
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            timestamps = []
            
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                now = time.time()
                
                # Remove timestamps outside the current period
                while timestamps and now - timestamps[0] > period:
                    timestamps.pop(0)
                
                # Check if we've exceeded the rate limit
                if len(timestamps) >= calls:
                    wait_time = period - (now - timestamps[0])
                    if wait_time > 0:
                        logger.warning(f"Rate limit exceeded for {func.__name__}. Waiting {wait_time:.2f}s")
                        time.sleep(wait_time)
                        now = time.time()  # Update current time after waiting
                
                # Add current timestamp and call function
                timestamps.append(now)
                return func(*args, **kwargs)
            
            return wrapper
        return decorator
    
    @staticmethod
    def retry(max_attempts: int = 3, delay: float = 1.0, 
              backoff: float = 2.0, exceptions: Tuple = (Exception,)) -> Callable:
        """
        Decorator to retry a function execution on failure.
        
        Args:
            max_attempts: Maximum number of attempts
            delay: Initial delay between retries in seconds
            backoff: Backoff multiplier (how much to increase delay after each failure)
            exceptions: Tuple of exceptions to catch and retry on
            
        Returns:
            Decorator function
        """
        def decorator(func: Callable) -> Callable:
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                mtries, mdelay = max_attempts, delay
                
                while mtries > 1:
                    try:
                        return func(*args, **kwargs)
                    except exceptions as e:
                        logger.warning(f"Function {func.__name__} failed: {str(e)}. "
                                      f"Retrying in {mdelay:.2f} seconds... ({mtries-1} attempts left)")
                        time.sleep(mdelay)
                        mtries -= 1
                        mdelay *= backoff
                
                # Last attempt
                return func(*args, **kwargs)
            
            return wrapper
        return decorator

# Create a global instance for easy access
optimizer = FunctionOptimizer()
