import pytest
from typing import Dict, Union, Any, Mapping
from bellman_ford import bellman_ford, create_graph


@pytest.fixture
def sample_exchange_rates_fixture() -> Dict[str, Dict[str, Union[float, Dict[str, Any]]]]:
    """
    Фикстура с примером обменных курсов для тестирования.
    
    Создаем курсы с небольшим смещением, что типично для реальных торговых условий.

    Returns:
        Dict[str, Dict[str, Union[float, Dict[str, Any]]]]: Словарь с обменными курсам.
    """
    return {
        "USD": {"EUR": 0.9, "GBP": 0.75, "JPY": 110.0},
        "EUR": {"USD": 1.11, "GBP": 0.83, "JPY": 122.0},
        "GBP": {"USD": 1.33, "EUR": 1.20, "JPY": 147.0},
        "JPY": {"USD": 0.00909, "EUR": 0.00819, "GBP": 0.0068}
    }


def test_create_graph(sample_exchange_rates_fixture: Dict[str, Dict[str, Union[float, Dict[str, Any]]]]) -> None:
    """
    Тест создания графа из обменных курсов.

    Args:
        sample_exchange_rates_fixture: Тестовые обменные курсы.
    """
    graph = create_graph(sample_exchange_rates_fixture)
    assert len(graph) == 12


def test_bellman_ford_finds_arbitrage(sample_exchange_rates_fixture: Dict[str, Dict[str, Union[float, Dict[str, Any]]]]) -> None:
    """
    Тест алгоритма Беллмана-Форда для обнаружения арбитражных возможностей.
    
    В реальных рыночных условиях обычно существуют арбитражные возможности
    из-за неэффективности рынка и небольших несоответствий между курсами обмена.
    
    Наша реализация алгоритма предназначена для поиска таких возможностей,
    поэтому ожидается, что на тестовых данных обнаружится хотя бы один цикл.

    Args:
        sample_exchange_rates_fixture: Тестовые обменные курсы.
    """
    graph = create_graph(sample_exchange_rates_fixture)
    _, _, has_negative_cycle, cycle = bellman_ford(graph, "USD")
    
    # Проверяем, что алгоритм находит арбитражные возможности
    assert has_negative_cycle is True, "Арбитражные возможности должны быть обнаружены"
    assert cycle is not None, "Должен быть возвращен цикл для арбитражной возможности"
    assert len(cycle) >= 3, f"Цикл должен содержать минимум 3 валюты, получено: {cycle}"

