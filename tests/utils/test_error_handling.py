"""
Тесты для модуля utils.error_handling.

Модуль содержит тесты для классов исключений и функций-декораторов
обработки ошибок в приложении.
"""

import logging
import unittest
from unittest.mock import Mock, patch
import pytest
import time
import requests
from typing import Any, Dict, List, Optional

from src.utils.error_handling import (
    BaseBotError, ApiError, MLError, NetworkError, RateLimitError,
    retry, handle_errors, log_execution_time, validate_arguments,
    safe_execute, format_exception, ensure, ensure_not_none
)


class TestErrorClasses(unittest.TestCase):
    """Тесты для классов исключений."""
    
    def test_base_bot_error(self):
        """Тест базового класса исключения."""
        error = BaseBotError("Test error")
        self.assertEqual(str(error), "Test error")
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.details, {})
        
        # Проверка с деталями
        error_with_details = BaseBotError("Test error", details={"code": 404, "reason": "Not found"})
        self.assertIn("details", str(error_with_details))
        self.assertEqual(error_with_details.details, {"code": 404, "reason": "Not found"})
    
    def test_api_error(self):
        """Тест класса ApiError."""
        response_data = {"error": "Invalid token"}
        error = ApiError(
            "API call failed", 
            status_code=401, 
            response=response_data
        )
        
        self.assertEqual(error.status_code, 401)
        self.assertEqual(error.response, response_data)
        self.assertIn("401", str(error))
        self.assertEqual(error.details["status_code"], 401)
        self.assertEqual(error.details["response"], response_data)


class TestRetryDecorator:
    """Тесты для декоратора retry."""
    
    def test_successful_execution(self):
        """Тест успешного выполнения функции без повторов."""
        mock_function = Mock(return_value="success")
        decorated_function = retry(max_attempts=3)(mock_function)
        
        result = decorated_function()
        
        assert result == "success"
        mock_function.assert_called_once()
    
    def test_retry_on_exception(self):
        """Тест повторных попыток при возникновении исключения."""
        mock_function = Mock(side_effect=[NetworkError("Connection error"), "success"])
        decorated_function = retry(
            max_attempts=3, 
            delay=0.01, 
            exceptions=[NetworkError]
        )(mock_function)
        
        result = decorated_function()
        
        assert result == "success"
        assert mock_function.call_count == 2
    
    def test_max_retries_exceeded(self):
        """Тест превышения максимального количества попыток."""
        mock_function = Mock(side_effect=NetworkError("Connection error"))
        decorated_function = retry(
            max_attempts=3, 
            delay=0.01, 
            exceptions=[NetworkError]
        )(mock_function)
        
        with pytest.raises(NetworkError):
            decorated_function()
        
        assert mock_function.call_count == 3
    
    def test_different_exception_not_retried(self):
        """Тест, что при исключении другого типа повторы не выполняются."""
        mock_function = Mock(side_effect=ValueError("Wrong value"))
        decorated_function = retry(
            max_attempts=3, 
            delay=0.01, 
            exceptions=[NetworkError]
        )(mock_function)
        
        with pytest.raises(ValueError):
            decorated_function()
        
        mock_function.assert_called_once()


class TestHandleErrorsDecorator:
    """Тесты для декоратора handle_errors."""
    
    def test_successful_execution(self):
        """Тест успешного выполнения функции."""
        mock_function = Mock(return_value="success")
        decorated_function = handle_errors()(mock_function)
        
        result = decorated_function()
        
        assert result == "success"
        mock_function.assert_called_once()
    
    def test_error_handling_with_fallback(self):
        """Тест обработки ошибки с возвратом запасного значения."""
        mock_function = Mock(side_effect=ValueError("Error"))
        decorated_function = handle_errors(fallback_value="fallback", reraise=False)(mock_function)
        
        result = decorated_function()
        
        assert result == "fallback"
        mock_function.assert_called_once()
    
    def test_error_handler_function(self):
        """Тест обработчика ошибок."""
        def custom_handler(exc):
            return f"Handled: {str(exc)}"
        
        mock_function = Mock(side_effect=ValueError("Custom error"))
        decorated_function = handle_errors(
            error_handler=custom_handler, 
            reraise=False
        )(mock_function)
        
        result = decorated_function()
        
        assert result == "Handled: Custom error"
        mock_function.assert_called_once()
    
    def test_reraise_error(self):
        """Тест перевыбрасывания исключения."""
        mock_function = Mock(side_effect=ValueError("Error"))
        decorated_function = handle_errors(reraise=True)(mock_function)
        
        with pytest.raises(ValueError):
            decorated_function()
        
        mock_function.assert_called_once()


class TestLogExecutionTimeDecorator:
    """Тесты для декоратора log_execution_time."""
    
    @patch("logging.Logger.log")
    def test_execution_time_logging(self, mock_log):
        """Тест логирования времени выполнения."""
        @log_execution_time()
        def slow_function():
            time.sleep(0.01)
            return "done"
        
        result = slow_function()
        
        assert result == "done"
        mock_log.assert_called_once()
        # Проверяем, что в сообщении есть строка "executed in"
        assert "executed in" in mock_log.call_args[0][1]


class TestValidateArgumentsDecorator:
    """Тесты для декоратора validate_arguments."""
    
    def test_valid_arguments(self):
        """Тест с валидными аргументами."""
        def validator(a, b):
            return a > 0 and b > 0
        
        @validate_arguments(validator)
        def add_positive(a, b):
            return a + b
        
        result = add_positive(1, 2)
        assert result == 3
    
    def test_invalid_arguments(self):
        """Тест с невалидными аргументами."""
        def validator(a, b):
            return a > 0 and b > 0
        
        @validate_arguments(validator)
        def add_positive(a, b):
            return a + b
        
        with pytest.raises(ValueError):
            add_positive(-1, 2)


class TestUtilityFunctions:
    """Тесты для вспомогательных функций."""
    
    def test_format_exception(self):
        """Тест форматирования исключения."""
        try:
            raise ValueError("Test error")
        except ValueError as e:
            result = format_exception(e)
            assert "ValueError" in result
            assert "Test error" in result
    
    def test_safe_execute_success(self):
        """Тест успешного выполнения safe_execute."""
        def test_func(a, b):
            return a + b
        
        result = safe_execute(test_func, 1, 2)
        assert result == 3
    
    def test_safe_execute_error(self):
        """Тест обработки ошибки в safe_execute."""
        def failing_func():
            raise ValueError("Test error")
        
        result = safe_execute(failing_func, fallback="fallback")
        assert result == "fallback"
    
    def test_ensure_true_condition(self):
        """Тест ensure с истинным условием."""
        # Не должно вызывать исключение
        ensure(True, "This should not raise")
    
    def test_ensure_false_condition(self):
        """Тест ensure с ложным условием."""
        with pytest.raises(BaseBotError):
            ensure(False, "Error message")
    
    def test_ensure_not_none_with_value(self):
        """Тест ensure_not_none с непустым значением."""
        value = ensure_not_none("value", "Value is none")
        assert value == "value"
    
    def test_ensure_not_none_with_none(self):
        """Тест ensure_not_none с None."""
        with pytest.raises(BaseBotError):
            ensure_not_none(None, "Value is none")


class TestIntegrationCases:
    """Интеграционные тесты модуля error_handling."""
    
    def test_retry_with_api_error(self):
        """Тест интеграции retry с ApiError."""
        mock_function = Mock(side_effect=[
            ApiError("Rate limited", status_code=429),
            ApiError("Rate limited", status_code=429),
            "success"
        ])
        
        decorated = retry(
            max_attempts=3,
            delay=0.01,
            exceptions=[ApiError]
        )(mock_function)
        
        result = decorated()
        assert result == "success"
        assert mock_function.call_count == 3
    
    def test_error_chain(self):
        """Тест цепочки обработки ошибок."""
        @handle_errors(reraise=True)
        @retry(max_attempts=2, delay=0.01, exceptions=[NetworkError])
        def complex_function():
            raise NetworkError("Connection failed")
        
        with pytest.raises(NetworkError):
            complex_function()


if __name__ == "__main__":
    pytest.main(["-xvs", __file__]) 