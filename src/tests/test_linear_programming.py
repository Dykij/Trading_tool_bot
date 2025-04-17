"""
Тестирование модуля линейного программирования для оптимизации торговых стратегий.
"""

import time
import logging
import numpy as np
from typing import List, Dict, Any
from linear_programming import (
    optimize_trades,
    calculate_expected_returns,
    get_optimized_allocation
)
from models.trade_cycle import TradeCycle

# Настройка логгера
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test_linear_programming")

def create_test_cycles() -> List[TradeCycle]:
    """Создает список тестовых торговых циклов"""
    cycles = []
    
    # Создаем 10 тестовых циклов с разными параметрами
    for i in range(10):
        profit_percent = np.random.uniform(1, 10)  # от 1% до 10%
        cost = np.random.uniform(100, 1000)  # от 100 до 1000 денежных единиц
        risk_score = np.random.uniform(1, 20)  # от 1 до 20 (низкий-высокий риск)
        
        cycle = TradeCycle(
            cycle_id=f"cycle_{i}",
            items=[f"item_{j}" for j in range(3)],  # 3 предмета в цикле
            profit_percent=profit_percent,
            cost=cost,
            risk_score=risk_score,
            expected_duration=np.random.uniform(10, 60)  # от 10 до 60 секунд
        )
        
        cycles.append(cycle)
    
    # Добавляем один высокодоходный, но рискованный цикл
    cycles.append(TradeCycle(
        cycle_id="high_profit_high_risk",
        items=["item_a", "item_b", "item_c"],
        profit_percent=20,
        cost=800,
        risk_score=30,
        expected_duration=30
    ))
    
    # Добавляем один низкодоходный, но безопасный цикл
    cycles.append(TradeCycle(
        cycle_id="low_profit_low_risk",
        items=["item_x", "item_y", "item_z"],
        profit_percent=2,
        cost=500,
        risk_score=1,
        expected_duration=15
    ))
    
    return cycles

def test_optimize_trades():
    """Тестирует функцию optimize_trades с различными параметрами"""
    logger.info("Тестирование функции optimize_trades")
    
    cycles = create_test_cycles()
    total_budget = 2000.0
    
    # Тест базового случая
    allocations, metrics = optimize_trades(cycles, total_budget)
    
    # Проверяем, что выделения не пустые
    assert allocations, "Allocations should not be empty"
    
    # Проверяем, что общее выделение не превышает бюджет (с небольшим запасом на погрешность вычислений)
    total_allocated = sum(allocations.values())
    assert total_allocated <= total_budget + 0.01, f"Total allocated ({total_allocated}) exceeds budget ({total_budget})"
    
    # Тест с ограничением риска
    allocations_low_risk, metrics_low_risk = optimize_trades(cycles, total_budget, max_risk=10)
    
    # Проверяем, что риск-метрики не превышают ограничения
    # Примечание: невозможно напрямую проверить итоговый риск без доступа к внутренним механизмам расчета
    
    # Тест с минимальным выделением
    min_allocation = 200.0
    allocations_min, metrics_min = optimize_trades(cycles, total_budget, min_allocation=min_allocation)
    
    # Проверяем, что все выделения не меньше минимального
    for allocation in allocations_min.values():
        assert allocation >= min_allocation - 0.01, f"Allocation ({allocation}) is less than minimum ({min_allocation})"
    
    # Тест с максимальным выделением на цикл
    max_allocation_per_cycle = 300.0
    allocations_max, metrics_max = optimize_trades(cycles, total_budget, max_allocation_per_cycle=max_allocation_per_cycle)
    
    # Проверяем, что все выделения не больше максимального
    for allocation in allocations_max.values():
        assert allocation <= max_allocation_per_cycle + 0.01, f"Allocation ({allocation}) exceeds maximum per cycle ({max_allocation_per_cycle})"
    
    logger.info("Тест optimize_trades завершен успешно")

def test_calculate_expected_returns():
    """Тестирует функцию calculate_expected_returns"""
    logger.info("Тестирование функции calculate_expected_returns")
    
    cycles = create_test_cycles()
    
    # Создаем тестовые выделения
    allocations = {
        cycles[0].cycle_id: 100.0,
        cycles[1].cycle_id: 200.0,
        cycles[2].cycle_id: 300.0
    }
    
    # Вычисляем ожидаемые возвраты
    metrics = calculate_expected_returns(allocations, cycles)
    
    # Проверяем, что все ожидаемые метрики присутствуют
    assert 'total_profit' in metrics, "total_profit should be in metrics"
    assert 'roi' in metrics, "roi should be in metrics"
    assert 'risk_adjusted_return' in metrics, "risk_adjusted_return should be in metrics"
    assert 'allocated_budget' in metrics, "allocated_budget should be in metrics"
    
    # Проверяем, что значения разумны
    assert metrics['total_profit'] >= 0, "Total profit should be non-negative"
    assert metrics['allocated_budget'] == sum(allocations.values()), "Allocated budget should match sum of allocations"
    
    logger.info("Тест calculate_expected_returns завершен успешно")

def test_get_optimized_allocation():
    """Тестирует функцию get_optimized_allocation"""
    logger.info("Тестирование функции get_optimized_allocation")
    
    cycles = create_test_cycles()
    total_budget = 2000.0
    
    # Запускаем оптимизацию
    allocations, metrics = get_optimized_allocation(
        cycles=cycles,
        total_budget=total_budget,
        max_risk=20,
        min_allocation=100.0,
        max_allocation_per_cycle=500.0
    )
    
    # Проверяем, что метрики содержат нужные поля
    assert 'total_profit' in metrics, "total_profit should be in metrics"
    assert 'roi' in metrics, "roi should be in metrics"
    assert 'risk_adjusted_return' in metrics, "risk_adjusted_return should be in metrics"
    assert 'allocated_budget' in metrics, "allocated_budget should be in metrics"
    assert 'execution_time' in metrics, "execution_time should be in metrics"
    
    # Проверяем, что сумма выделений не превышает бюджет (с небольшим запасом на погрешность вычислений)
    total_allocated = sum(allocations.values())
    assert total_allocated <= total_budget + 0.01, f"Total allocated ({total_allocated}) exceeds budget ({total_budget})"
    
    # Проверяем, что все выделения соответствуют ограничениям (с небольшим запасом на погрешность вычислений)
    for allocation in allocations.values():
        assert allocation >= 100.0 - 0.01, f"Allocation ({allocation}) is less than minimum (100.0)"
        assert allocation <= 500.0 + 0.01, f"Allocation ({allocation}) exceeds maximum per cycle (500.0)"
    
    logger.info("Тест get_optimized_allocation завершен успешно")

def test_performance():
    """Тестирует производительность алгоритма оптимизации"""
    logger.info("Тестирование производительности алгоритма оптимизации")
    
    # Создаем большое количество циклов
    large_cycles_list = []
    for i in range(100):
        cycle = TradeCycle(
            cycle_id=f"perf_cycle_{i}",
            items=[f"item_{j}" for j in range(3)],
            profit_percent=np.random.uniform(1, 10),
            cost=np.random.uniform(100, 1000),
            risk_score=np.random.uniform(1, 20),
            expected_duration=np.random.uniform(10, 60)
        )
        large_cycles_list.append(cycle)
    
    # Замеряем время выполнения
    total_budget = 10000.0
    start_time = time.time()
    
    allocations, metrics = optimize_trades(large_cycles_list, total_budget)
    
    execution_time = time.time() - start_time
    logger.info(f"Время выполнения оптимизации для {len(large_cycles_list)} циклов: {execution_time:.6f} сек.")
    
    # Проверяем, что оптимизация завершилась за разумное время
    assert execution_time < 10.0, f"Optimization took too long: {execution_time:.6f} seconds"
    
    logger.info("Тест производительности завершен успешно")

def test_extreme_cases():
    """Тестирует алгоритм оптимизации на крайних случаях"""
    logger.info("Тестирование алгоритма оптимизации на крайних случаях")
    
    # Тест 1: Пустой список циклов
    allocations, metrics = optimize_trades([], 1000.0)
    assert allocations == {}, "Empty cycles list should result in empty allocations"
    assert metrics['total_profit'] == 0, "Empty cycles list should result in zero profit"
    
    # Тест 2: Нулевой бюджет
    cycles = create_test_cycles()
    allocations, metrics = optimize_trades(cycles, 0.0)
    assert allocations == {}, "Zero budget should result in empty allocations"
    
    # Тест 3: Очень малый бюджет
    allocations, metrics = optimize_trades(cycles, 0.01)
    assert sum(allocations.values()) <= 0.01 + 0.001, "Allocations should not exceed tiny budget"
    
    # Тест 4: Очень большой бюджет
    large_budget = 1_000_000.0
    allocations, metrics = optimize_trades(cycles, large_budget)
    assert sum(allocations.values()) <= large_budget + 0.01, "Allocations should not exceed large budget"
    
    # Тест 5: Циклы с нулевым/отрицательным риском
    zero_risk_cycles = []
    for i in range(3):
        cycle = TradeCycle(
            cycle_id=f"zero_risk_{i}",
            items=[f"item_{j}" for j in range(2)],
            profit_percent=5.0,
            cost=100.0,
            risk_score=0.0 if i == 0 else -1.0,
            expected_duration=30.0
        )
        zero_risk_cycles.append(cycle)
    
    # Этот тест может вызвать деление на ноль, если алгоритм не обрабатывает нулевой риск
    try:
        allocations, metrics = optimize_trades(zero_risk_cycles, 1000.0)
        logger.info("Обработка циклов с нулевым/отрицательным риском успешна")
    except ZeroDivisionError:
        assert False, "Algorithm should handle zero/negative risk without ZeroDivisionError"
    
    logger.info("Тест экстремальных случаев завершен успешно")

def run_all_tests():
    """Запускает все тесты"""
    logger.info("Запуск всех тестов для модуля линейного программирования")
    
    test_optimize_trades()
    test_calculate_expected_returns()
    test_get_optimized_allocation()
    test_performance()
    test_extreme_cases()
    
    logger.info("Все тесты завершены успешно")

if __name__ == "__main__":
    run_all_tests() 