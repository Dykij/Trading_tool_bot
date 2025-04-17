"""
Модуль алгоритма Беллмана-Форда для поиска арбитражных возможностей.

Реализует функции для создания графа обмена валют/предметов из данных рынка,
поиска отрицательных циклов и расчета арбитражных возможностей.

Арбитражные возможности возникают, когда существует цикл обменов, который приводит
к увеличению изначальной суммы. Алгоритм Беллмана-Форда используется для обнаружения
отрицательных циклов в графе, что соответствует прибыльным арбитражным цепочкам.

Основные компоненты:
- Создание взвешенного ориентированного графа из данных о рыночных курсах
- Поиск отрицательных циклов в графе с помощью алгоритма Беллмана-Форда
- Расчет прибыльности, ликвидности и рисков для каждой арбитражной возможности
- Фильтрация и ранжирование арбитражных возможностей по различным критериям

Пример использования:
    
    # Данные о курсах обмена
    exchange_data = {
        "USD": {"EUR": {"rate": 0.85, "liquidity": 1000.0, "fee": 0.002}},
        "EUR": {"USD": {"rate": 1.18, "liquidity": 1000.0, "fee": 0.002}}
    }
    
    # Создание графа
    edges = create_graph(exchange_data)
    
    # Поиск арбитражных возможностей
    opportunities = find_arbitrage(edges)
    
    # Фильтрация по минимальному проценту прибыли и ликвидности
    filtered = filter_arbitrage_opportunities(
        opportunities, 
        min_profit_percent=1.0,
        min_liquidity=5.0
    )
"""

import math
import logging
import time
from typing import List, Dict, Any, Tuple, Optional, Set
from dataclasses import dataclass

# Настройка логирования
logger = logging.getLogger('bellman_ford')

@dataclass
class Edge:
    """
    Ребро графа, представляющее обмен между валютами/предметами.
    
    Представляет возможную операцию обмена из одной валюты/предмета в другую
    с указанным курсом, ликвидностью и комиссией. Для работы алгоритма Беллмана-Форда
    курс обмена преобразуется в отрицательный логарифм и сохраняется как вес ребра.
    
    Attributes:
        from_node (str): Исходная валюта или предмет (узел графа)
        to_node (str): Целевая валюта или предмет (узел графа)
        weight (float): Вес ребра для алгоритма (отрицательный логарифм курса обмена)
        rate (float): Исходный курс обмена (сколько единиц to_node получается из одной единицы from_node)
        liquidity (float): Ликвидность обмена (оценка объема доступных сделок в единицу времени)
        fee (float): Комиссия за обмен в десятичном формате (0.01 = 1%)
        
    Note:
        Отрицательный вес ребра (weight) указывает на возможность получения прибыли.
        Чем меньше (более отрицательный) вес, тем более выгоден обмен.
    """
    from_node: str  # Исходная валюта/предмет
    to_node: str    # Целевая валюта/предмет
    weight: float   # Вес ребра (отрицательный логарифм курса обмена)
    rate: float     # Исходный курс обмена
    liquidity: float = 0.0  # Ликвидность (количество сделок в день)
    fee: float = 0.0        # Комиссия за обмен

@dataclass
class ArbitrageResult:
    """
    Результат поиска арбитражной возможности.
    
    Содержит информацию о найденном арбитражном цикле, включая последовательность 
    валют/предметов, расчет прибыли, оценку ликвидности и рисков.
    
    Attributes:
        cycle (List[str]): Последовательность валют/предметов, образующих цикл
        profit (float): Абсолютная прибыль при начальной инвестиции в 1 единицу
        profit_percent (float): Процент прибыли относительно начальной инвестиции
        liquidity (float): Минимальная ликвидность среди всех обменов в цикле
        total_fee (float): Суммарная комиссия за все обмены в цикле
        confidence (float): Оценка уверенности в возможности (от 0.0 до 1.0)
        recommended_volume (float): Рекомендуемый объем для торговли
        details (Dict[str, Any]): Детальная информация о каждом шаге цикла
        
    Example:
        ```
        ArbitrageResult(
            cycle=['USD', 'EUR', 'GBP', 'USD'],
            profit=0.023,
            profit_percent=2.3,
            liquidity=5.2,
            total_fee=0.006,
            confidence=0.85,
            recommended_volume=100.0
        )
        ```
        
    Note:
        Чем выше confidence и liquidity, тем надежнее арбитражная возможность.
        Низкие значения данных показателей могут указывать на высокий риск.
    """
    cycle: List[str]         # Цикл валют/предметов
    profit: float            # Абсолютная прибыль
    profit_percent: float    # Процент прибыли
    liquidity: float         # Минимальная ликвидность в цикле
    total_fee: float         # Общая комиссия в цикле
    confidence: float = 1.0  # Уверенность в возможности (0.0-1.0)
    recommended_volume: float = 1.0  # Рекомендуемый объем торговли
    details: Dict[str, Any] = None  # Детальная информация о каждом шаге

def create_graph(exchange_data: Dict[str, Dict[str, Dict[str, Any]]]) -> List[Edge]:
    """
    Создает граф обменных курсов из данных рынка.

    Args:
        exchange_data: Словарь с данными о курсах обмена
            Пример формата:
            {
                "USD": {
                    "EUR": {"rate": 0.85, "liquidity": 1000.0, "fee": 0.002},
                    "GBP": {"rate": 0.75, "liquidity": 800.0, "fee": 0.002}
                },
                "EUR": {
                    "USD": {"rate": 1.18, "liquidity": 1000.0, "fee": 0.002}
                }
            }

    Returns:
        Список ребер графа
    """
    edges = []
    
    # Проверяем тип входных данных
    if exchange_data is None:
        logger.error("Получены пустые данные обмена (None)")
        return edges
        
    if not isinstance(exchange_data, dict):
        logger.error(f"Неверный формат данных: ожидается словарь, получено {type(exchange_data)}")
        return edges
    
    # Обработка каждой пары валют/предметов
    for from_node, to_nodes in exchange_data.items():
        # Пропускаем пустые или невалидные узлы
        if not from_node or not isinstance(from_node, str):
            logger.warning(f"Пропуск невалидного узла: {from_node}")
            continue
            
        # Обработка различных форматов данных
        if isinstance(to_nodes, dict):
            # Стандартный формат словаря
            for to_node, data in to_nodes.items():
                edge = _create_edge_from_data(from_node, to_node, data)
                if edge is not None:
                    edges.append(edge)
        elif hasattr(to_nodes, 'items') and callable(to_nodes.items):
            # Поддержка других итерируемых объектов, реализующих метод items()
            for to_node, data in to_nodes.items():
                edge = _create_edge_from_data(from_node, to_node, data)
                if edge is not None:
                    edges.append(edge)
        elif isinstance(to_nodes, (list, tuple)) and all(isinstance(item, dict) for item in to_nodes):
            # Поддержка списка словарей
            for item in to_nodes:
                if 'to_node' in item and 'data' in item:
                    edge = _create_edge_from_data(from_node, item['to_node'], item['data'])
                    if edge is not None:
                        edges.append(edge)
                elif 'to' in item and ('rate' in item or 'price' in item or 'value' in item):
                    # Альтернативный формат с прямым указанием параметров
                    to_node = item.get('to')
                    if to_node:
                        edge = _create_edge_from_data(from_node, to_node, item)
                        if edge is not None:
                            edges.append(edge)
        else:
            logger.warning(f"Пропуск {from_node}: неверный формат данных для to_nodes: {type(to_nodes)}")
            continue
    
    if not edges:
        logger.warning("Не удалось создать ни одного ребра графа")
    else:
        logger.debug(f"Создан граф с {len(edges)} рёбрами")
        
    return edges

def _create_edge_from_data(from_node: str, to_node: str, data: Dict[str, Any]) -> Optional[Edge]:
    """
    Создает ребро графа из данных обмена.

    Args:
        from_node: Исходная валюта/предмет
        to_node: Целевая валюта/предмет
        data: Данные обмена (курс, ликвидность, комиссия)

    Returns:
        Ребро графа или None в случае ошибки
    """
    # Проверка входных параметров
    if not isinstance(from_node, str) or not isinstance(to_node, str):
        logger.warning(f"Пропуск ребра: невалидные узлы {from_node} -> {to_node}")
        return None
        
    # Проверка формата данных
    if data is None:
        logger.warning(f"Пропуск {from_node} -> {to_node}: пустые данные")
        return None
        
    if not isinstance(data, dict):
        logger.warning(f"Пропуск {from_node} -> {to_node}: неверный формат данных: {type(data)}")
        return None
    
    # Получаем данные о курсе
    rate = None
    # Проверяем разные возможные форматы хранения курса
    if 'rate' in data:
        rate = data.get('rate')
    elif 'price' in data:
        rate = data.get('price')
    elif 'value' in data:
        rate = data.get('value')
    elif 'amount' in data:
        rate = data.get('amount')
    
    # Проверка на валидный курс
    if rate is None:
        logger.debug(f"Пропуск {from_node} -> {to_node}: курс не найден в данных")
        return None
        
    # Обработка различных форматов курса
    if isinstance(rate, str):
        try:
            rate = float(rate)
        except (ValueError, TypeError):
            logger.warning(f"Пропуск {from_node} -> {to_node}: невозможно преобразовать строковый курс '{rate}' в число")
            return None
            
    if not isinstance(rate, (int, float)) or rate <= 0:
        logger.debug(f"Пропуск {from_node} -> {to_node}: недопустимый курс {rate}")
        return None
    
    # Получаем данные о ликвидности и комиссии с разными возможными ключами
    liquidity = data.get('liquidity', data.get('volume', data.get('amount', data.get('count', 0))))
    fee = data.get('fee', data.get('commission', data.get('tax', data.get('fee_percent', 0))))
    
    # Проверка типов данных
    try:
        rate = float(rate)
        
        # Преобразуем ликвидность в число
        if isinstance(liquidity, str):
            liquidity = float(liquidity)
        elif not isinstance(liquidity, (int, float)):
            liquidity = 0.0
            
        # Преобразуем комиссию в число
        if isinstance(fee, str):
            if fee.endswith('%'):
                fee = float(fee.rstrip('%')) / 100.0
            else:
                fee = float(fee)
        elif not isinstance(fee, (int, float)):
            fee = 0.0
            
        # Проверка и нормализация комиссии
        # Ожидаем, что комиссия передается в десятичном формате (0.05 для 5%)
        if fee > 1:
            # Если комиссия больше 1, считаем, что она в процентах и конвертируем
            logger.debug(f"Комиссия {fee} для {from_node} -> {to_node} слишком большая, конвертируем из процентов в десятичную долю")
            fee = fee / 100.0
            
        if fee < 0:
            logger.warning(f"Отрицательная комиссия {fee} для {from_node} -> {to_node}, установлено значение 0")
            fee = 0.0
            
        if fee >= 1:
            logger.warning(f"Комиссия {fee} для {from_node} -> {to_node} слишком высокая (100% или более), установлено максимальное значение 0.99")
            fee = 0.99  # Устанавливаем максимальную комиссию 99%
            
    except (ValueError, TypeError) as e:
        logger.warning(f"Пропуск {from_node} -> {to_node}: ошибка преобразования типов: {e}")
        return None
    
    # Учитываем комиссию в курсе обмена
    # Расчет эффективного курса с учетом комиссии
    effective_rate = rate * (1.0 - fee)
    
    # Проверка эффективного курса
    if effective_rate <= 0:
        logger.warning(f"Пропуск {from_node} -> {to_node}: эффективный курс после учета комиссии равен нулю или отрицателен: rate={rate}, fee={fee}, effective_rate={effective_rate}")
        return None
    
    # Расчет веса ребра (отрицательный логарифм курса обмена)
    # Для алгоритма Беллмана-Форда: чем меньше вес, тем выгоднее переход
    weight = -math.log(effective_rate)
    
    # Создаем ребро с нормализованными значениями
    return Edge(
        from_node=from_node,
        to_node=to_node,
        weight=weight,
        rate=rate,
        liquidity=liquidity,
        fee=fee
    )

def create_graph_from_data(exchange_data: Dict[str, Dict[str, Dict[str, Any]]]) -> 'nx.DiGraph':
    """
    Создает граф с использованием NetworkX из данных обмена.
    
    Args:
        exchange_data: Словарь с данными о курсах обмена
            
    Returns:
        Направленный граф NetworkX с весами ребер
    """
    try:
        import networkx as nx
    except ImportError:
        logger.error("Библиотека NetworkX не установлена. Установите ее с помощью 'pip install networkx'")
        # Создаем минимальную эмуляцию графа для дальнейшей работы
        class SimpleGraph:
            def __init__(self):
                self.nodes = set()
                self._edges = {}
                
            def add_node(self, node):
                self.nodes.add(node)
                
            def add_edge(self, u, v, **kwargs):
                if u not in self._edges:
                    self._edges[u] = {}
                self._edges[u][v] = kwargs
                
            def edges(self, source=None):
                if source is None:
                    return [(u, v) for u in self._edges for v in self._edges[u]]
                elif source in self._edges:
                    return [(source, v) for v in self._edges[source]]
                else:
                    return []
        
        graph = SimpleGraph()
    else:
        graph = nx.DiGraph()
    
    # Создаем граф из данных обмена
    for from_currency, to_currencies in exchange_data.items():
        graph.add_node(from_currency)
        
        for to_currency, data in to_currencies.items():
            graph.add_node(to_currency)
            
            # Получаем курс и комиссию
            rate = data.get('rate', 0)
            fee = data.get('fee', 0)
            liquidity = data.get('liquidity', 0)
            
            # Проверка валидности данных
            if rate <= 0:
                continue
                
            # Учитываем комиссию в курсе обмена
            effective_rate = rate * (1.0 - fee)
            
            # Рассчитываем вес ребра (отрицательный логарифм эффективного курса)
            # Для алгоритма Беллмана-Форда: чем меньше вес, тем выгоднее переход
            try:
                weight = -math.log(effective_rate)
            except (ValueError, TypeError):
                logger.warning(f"Невозможно рассчитать вес для ребра {from_currency} -> {to_currency}: rate={rate}, fee={fee}")
                continue
                
            # Добавляем ребро в граф
            graph.add_edge(
                from_currency, 
                to_currency, 
                weight=weight,
                rate=rate,
                effective_rate=effective_rate,
                fee=fee,
                liquidity=liquidity
            )
    
    return graph

def bellman_ford(edges: List[Edge], source: str = None) -> Tuple[bool, Dict[str, float], Dict[str, str]]:
    """
    Базовая реализация алгоритма Беллмана-Форда для поиска отрицательных циклов.

    Args:
        edges: Список ребер графа
        source: Исходный узел (если None, будет выбран первый узел)

    Returns:
        Кортеж (наличие_отрицательного_цикла, расстояния, предшественники)
    """
    # Строим множество всех узлов
    nodes = set()
    for edge in edges:
        nodes.add(edge.from_node)
        nodes.add(edge.to_node)
    
    if not nodes:
        logger.warning("Граф не содержит узлов")
        return False, {}, {}
    
    # Если исходный узел не указан, выбираем первый узел
    if source is None or source not in nodes:
        source = next(iter(nodes))
    
    # Инициализация расстояний и предшественников
    distances = {node: float('inf') for node in nodes}
    distances[source] = 0
    
    predecessors = {node: None for node in nodes}
    
    # Релаксация ребер |V| - 1 раз
    for _ in range(len(nodes) - 1):
        for edge in edges:
            if distances[edge.from_node] != float('inf') and distances[edge.from_node] + edge.weight < distances[edge.to_node]:
                distances[edge.to_node] = distances[edge.from_node] + edge.weight
                predecessors[edge.to_node] = edge.from_node
    
    # Проверка на наличие отрицательных циклов
    for edge in edges:
        if distances[edge.from_node] != float('inf') and distances[edge.from_node] + edge.weight < distances[edge.to_node]:
            logger.info("Обнаружен отрицательный цикл")
            return True, distances, predecessors
    
    return False, distances, predecessors

def bellman_ford_optimized(edges: List[Edge], source: str = None) -> Tuple[bool, Dict[str, float], Dict[str, str], List[str]]:
    """
    Оптимизированная реализация алгоритма Беллмана-Форда.
    
    Использует раннюю остановку, проверку на ошибки с плавающей точкой
    и эффективную структуру данных.

    Args:
        edges: Список ребер графа
        source: Исходный узел (если None, будет выбран первый узел)

    Returns:
        Кортеж (наличие_отрицательного_цикла, расстояния, предшественники, цикл)
    """
    # Строим множество всех узлов
    nodes = set()
    for edge in edges:
        nodes.add(edge.from_node)
        nodes.add(edge.to_node)

    if not nodes:
        logger.warning("Граф не содержит узлов")
        return False, {}, {}, []
    
    # Если исходный узел не указан, выбираем первый узел
    if source is None or source not in nodes:
        source = next(iter(nodes))
    
    # Инициализация расстояний и предшественников
    distances = {node: float('inf') for node in nodes}
    distances[source] = 0
    
    predecessors = {node: None for node in nodes}
    
    # Порог для обнаружения изменений с плавающей точкой
    epsilon = 1e-10
    
    # Флаг для отслеживания найденных циклов
    negative_cycle_found = False
    cycle_node = None
    
    # Релаксация ребер |V| - 1 раз с ранней остановкой
    for i in range(len(nodes)):
        relaxed = False
        for edge in edges:
            if distances[edge.from_node] == float('inf'):
                continue
                
            # Вычисляем новое расстояние
            new_distance = distances[edge.from_node] + edge.weight
            
            # Проверяем, является ли новое расстояние значительно меньше текущего
            if new_distance < distances[edge.to_node] - epsilon:
                # На последней итерации - обнаружен отрицательный цикл
                if i == len(nodes) - 1:
                    negative_cycle_found = True
                    cycle_node = edge.to_node
                    break
                    
                distances[edge.to_node] = new_distance
                predecessors[edge.to_node] = edge.from_node
                relaxed = True

        # Если на текущей итерации не было релаксаций, можно остановиться
        if not relaxed and i < len(nodes) - 1:
            logger.debug(f"Ранняя остановка на итерации {i+1} из {len(nodes)}")
            break

        # Если найден отрицательный цикл, выходим
        if negative_cycle_found:
            break
    
    # Если найден отрицательный цикл, восстанавливаем его
    cycle = []
    if negative_cycle_found and cycle_node:
        cycle = find_negative_cycle_path(cycle_node, predecessors)
    
    return negative_cycle_found, distances, predecessors, cycle

def find_negative_cycle_path(node: str, predecessors: Dict[str, str]) -> List[str]:
    """
    Находит путь отрицательного цикла, начиная с указанного узла.
    
    Args:
        node: Узел, являющийся частью отрицательного цикла
        predecessors: Словарь предшественников
        
    Returns:
        Список узлов в отрицательном цикле
    """
    # Множество посещенных узлов
    visited = set()
    cycle = []
    
    current = node
    
    # Находим цикл, двигаясь по предшественникам
    while current and current not in visited:
        visited.add(current)
        cycle.append(current)
        current = predecessors.get(current)
        
        # Защита от бесконечного цикла при отсутствии предшественника
        if not current:
            break
    
    # Если нашли цикл
    if current and current in cycle:
        # Находим начало цикла
        start_index = cycle.index(current)
        # Выделяем только цикл
        cycle = cycle[start_index:]
        # Переворачиваем для правильного порядка
        cycle.reverse()
        
    return cycle

def find_negative_cycles(graph, source: str, max_length: int = 8) -> List[List[str]]:
    """
    Находит все отрицательные циклы в графе, начинающиеся из указанного источника.
    
    Args:
        graph: Граф (NetworkX или SimpleGraph)
        source: Исходный узел
        max_length: Максимальная длина цикла
        
    Returns:
        Список отрицательных циклов (каждый цикл - список узлов)
    """
    # Реализуем простой поиск отрицательных циклов с помощью базового алгоритма Беллмана-Форда
    # и преобразования графа в список рёбер
    
    # Создаем список рёбер из графа
    edges = []
    for u, v, attrs in graph.edges(data=True):
        edge = Edge(
            from_node=u,
            to_node=v,
            weight=attrs.get('weight', 0),
            rate=attrs.get('rate', 0),
            liquidity=attrs.get('liquidity', 0),
            fee=attrs.get('fee', 0)
        )
        edges.append(edge)
    
    # Запускаем оптимизированный алгоритм Беллмана-Форда
    has_cycle, distances, predecessors, cycle = bellman_ford_optimized(edges, source)
    
    if not has_cycle or not cycle:
        return []
    
    # Если цикл слишком длинный, отклоняем его
    if len(cycle) > max_length:
        return []
    
    # Возвращаем найденный цикл
    return [cycle]

def find_arbitrage_advanced(graph: Dict[str, Dict[str, Dict[str, Any]]], 
                     budget: float = 100.0, 
                     min_profit: float = 0.5,
                     min_liquidity: float = 0.1,
                     max_cycle_length: int = 8,
                     max_opportunities: int = 10) -> List[Dict[str, Any]]:
    """
    Улучшенная функция для поиска арбитражных возможностей в графе обменных курсов.
    
    Использует алгоритм Беллмана-Форда для поиска отрицательных циклов (арбитражных возможностей)
    с учетом минимальной прибыли, ликвидности, бюджета и длины цикла.
    
    Args:
        graph: Граф обменных курсов в формате {from_item: {to_item: {rate, liquidity, fee}}}
        budget: Бюджет для торговли (в USD)
        min_profit: Минимальный процент прибыли (0.5 = 0.5%)
        min_liquidity: Минимальная ликвидность предметов в цикле
        max_cycle_length: Максимальная длина цикла для поиска
        max_opportunities: Максимальное количество возвращаемых возможностей
        
    Returns:
        Список арбитражных возможностей в формате:
        [
            {
                'path': ['item1', 'item2', ..., 'item1'],
                'profit': profit_percent,
                'profit_value': profit_value,
                'initial_budget': budget,
                'final_budget': final_budget,
                'liquidity': min_liquidity_in_path,
                'details': [{from_item, to_item, rate, liquidity, fee}, ...]
            },
            ...
        ]
    """
    # Проверяем параметры
    if not graph:
        logger.warning("Пустой граф обменных курсов, поиск невозможен")
        return []
        
    # Проверка на отрицательные или нулевые параметры
    if budget <= 0:
        logger.warning(f"Недопустимый бюджет: {budget}, должен быть положительным")
        budget = 100.0
        
    if min_profit < 0:
        logger.warning(f"Недопустимый порог прибыли: {min_profit}, должен быть неотрицательным")
        min_profit = 0.1
        
    if min_liquidity <= 0:
        logger.warning(f"Недопустимый порог ликвидности: {min_liquidity}, должен быть положительным")
        min_liquidity = 0.1
        
    # Преобразуем min_profit из процентов в десятичную долю
    min_profit_ratio = min_profit / 100.0
    
    logger.debug(f"Поиск арбитражных возможностей: бюджет=${budget}, мин. прибыль={min_profit}%, "
                 f"мин. ликвидность={min_liquidity}, макс. длина цикла={max_cycle_length}")
                 
    # Создаем граф для алгоритма Беллмана-Форда
    bf_graph = create_graph_from_data(graph)
    
    # Список найденных возможностей
    opportunities = []
    
    # Набор уже найденных уникальных путей для избежания дубликатов
    found_paths = set()
    
    # Проверяем каждый узел как потенциальное начало цикла
    # Для оптимизации сортируем узлы по количеству исходящих ребер (нет смысла начинать с узла без ребер)
    nodes_by_edges = sorted(
        [(node, len(graph.get(node, {}))) for node in graph.keys()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Ограничиваем количество стартовых узлов для оптимизации
    start_nodes = [node for node, edges_count in nodes_by_edges 
                  if edges_count > 0][:min(100, len(nodes_by_edges))]
                  
    logger.debug(f"Выбрано {len(start_nodes)} стартовых узлов из {len(nodes_by_edges)} для поиска")
    
    for start_node in start_nodes:
        try:
            # Проверяем, что узел существует в графе
            if start_node not in bf_graph.nodes:
                continue
                
            # Проверяем, что у узла есть исходящие ребра
            if not list(bf_graph.edges(start_node)):
                continue
                
            # Находим отрицательные циклы с учетом ограничений
            cycles = find_negative_cycles(
                bf_graph, 
                source=start_node,
                max_length=max_cycle_length
            )
            
            for cycle in cycles:
                try:
                    # Проверяем, что цикл не слишком короткий (минимум 3 узла для цикла)
                    if len(cycle) < 3:
                        continue
                        
                    # Преобразуем цикл в путь (замыкаем)
                    path = cycle + [cycle[0]]
                    
                    # Проверяем уникальность пути (избегаем дубликатов)
                    path_key = tuple(sorted(path))
                    if path_key in found_paths:
                        continue
                    
                    # Вычисляем детали этого пути
                    details = []
                    current_budget = budget
                    min_path_liquidity = float('inf')
                    
                    # Проходим по всем переходам и собираем информацию
                    for i in range(len(path) - 1):
                        from_item = path[i]
                        to_item = path[i + 1]
                        
                        # Получаем данные о переходе
                        if from_item not in graph or to_item not in graph.get(from_item, {}):
                            # Если перехода нет в графе данных, пропускаем этот цикл
                            logger.warning(f"Пропуск цикла: переход {from_item} -> {to_item} отсутствует в данных")
                            current_budget = -1
                            break
                            
                        transition_data = graph[from_item][to_item]
                        rate = transition_data.get('rate', 0)
                        liquidity = transition_data.get('liquidity', 0)
                        fee = transition_data.get('fee', 0)
                        
                        # Проверяем ликвидность
                        if liquidity < min_liquidity:
                            current_budget = -1
                            break
                            
                        # Отслеживаем минимальную ликвидность в пути
                        min_path_liquidity = min(min_path_liquidity, liquidity)
                        
                        # Моделируем обмен (с учетом комиссии)
                        effective_rate = rate * (1.0 - fee)
                        current_budget *= effective_rate
                        
                        # Добавляем детали перехода
                        details.append({
                            'from_item': from_item,
                            'to_item': to_item,
                            'rate': rate,
                            'effective_rate': effective_rate,
                            'fee': fee,
                            'liquidity': liquidity
                        })
                    
                    # Если был пропуск из-за отсутствия данных или низкой ликвидности
                    if current_budget <= 0:
                        continue
                        
                    # Вычисляем итоговую прибыль
                    final_budget = current_budget
                    profit_value = final_budget - budget
                    profit_percent = (profit_value / budget) * 100
                    
                    # Проверяем, достаточно ли прибыли
                    if profit_percent < min_profit:
                        continue
                    
                    # Добавляем найденную возможность
                    opportunity = {
                        'path': path,
                        'profit': profit_percent,
                        'profit_value': profit_value,
                        'initial_budget': budget,
                        'final_budget': final_budget,
                        'liquidity': min_path_liquidity,
                        'details': details
                    }
                    
                    opportunities.append(opportunity)
                    found_paths.add(path_key)
                    
                    # Если достигли лимита возможностей, завершаем поиск
                    if len(opportunities) >= max_opportunities:
                        logger.debug(f"Достигнут лимит в {max_opportunities} возможностей, завершаем поиск")
                        break
                        
                except Exception as cycle_error:
                    logger.warning(f"Ошибка при обработке цикла: {cycle_error}")
                    continue
                    
            # Если достигли лимита возможностей, завершаем поиск
            if len(opportunities) >= max_opportunities:
                break
                
        except Exception as node_error:
            logger.warning(f"Ошибка при поиске циклов для узла {start_node}: {node_error}")
            continue
    
    # Сортируем возможности по убыванию прибыли
    opportunities.sort(key=lambda x: x['profit'], reverse=True)
    
    # Ограничиваем результат
    result = opportunities[:max_opportunities]
    
    # Логируем результаты
    if result:
        logger.info(f"Найдено {len(result)} арбитражных возможностей с прибылью от {result[-1]['profit']:.2f}% до {result[0]['profit']:.2f}%")
    else:
        logger.warning(f"Не найдено арбитражных возможностей с мин. прибылью {min_profit}% и мин. ликвидностью {min_liquidity}")
    
    return result

# Сохраняем исходную функцию для обратной совместимости
def get_single_arbitrage_result(
    edges: List[Edge], 
    source: str = None
) -> ArbitrageResult:
    """
    Ищет одну арбитражную возможность в графе и возвращает подробную информацию.
    Это исходная версия функции find_arbitrage_advanced для обратной совместимости.
    
    Args:
        edges: Список ребер графа
        source: Исходный узел (если None, будет выбран первый узел)
        
    Returns:
        Информация об арбитражной возможности
    """
    # Запускаем алгоритм Беллмана-Форда
    has_cycle, distances, predecessors, cycle = bellman_ford_optimized(edges, source)
    
    # Если цикл не найден, возвращаем пустой результат
    if not has_cycle or not cycle:
        return ArbitrageResult(
            cycle=[],
            profit=0.0,
            profit_percent=0.0,
            liquidity=0.0,
            total_fee=0.0,
            confidence=0.0,
            recommended_volume=0.0,
            details=None
        )
    
    # Словарь ребер для быстрого поиска
    edge_map = {}
    for edge in edges:
        edge_map[(edge.from_node, edge.to_node)] = edge
    
    # Вычисляем прибыль и детали цикла
    profit_factor = 1.0
    liquidity_values = []
    fees = []
    steps = []
    
    for i in range(len(cycle)):
        from_node = cycle[i]
        to_node = cycle[(i + 1) % len(cycle)]
        
        # Находим соответствующее ребро
        edge = edge_map.get((from_node, to_node))
        if not edge:
            logger.warning(f"Ребро ({from_node}, {to_node}) не найдено в графе")
            continue
        
        # Рассчитываем прибыль с учетом комиссии
        rate_with_fee = edge.rate * (1 - edge.fee)
        profit_factor *= rate_with_fee
        
        liquidity_values.append(edge.liquidity)
        fees.append(edge.fee)
        
        steps.append({
            "from": from_node,
            "to": to_node,
            "rate": edge.rate,
            "fee": edge.fee,
            "effective_rate": rate_with_fee
        })
    
    # Вычисляем минимальную ликвидность в цикле
    min_liquidity = min(liquidity_values) if liquidity_values else 0
    
    # Рассчитываем общую комиссию
    total_fee = sum(fees)
    
    # Вычисляем прибыль в процентах
    profit_percent = (profit_factor - 1) * 100
    
    # Рассчитываем рекомендуемый объем торговли (на основе ликвидности)
    # Используем эвристику: 10% от минимальной ликвидности, но не более $1000
    recommended_volume = min(min_liquidity * 0.1, 1000.0)
    
    # Рассчитываем уверенность (эвристика на основе прибыли и ликвидности)
    # Чем выше прибыль и ликвидность, тем выше уверенность
    profit_confidence = min(profit_percent / 10.0, 1.0)  # Нормализуем до 0-1
    liquidity_confidence = min(min_liquidity / 100.0, 1.0)  # Нормализуем до 0-1
    
    # Весовые коэффициенты для прибыли и ликвидности
    profit_weight = 0.7
    liquidity_weight = 0.3
    
    # Итоговая уверенность
    confidence = profit_weight * profit_confidence + liquidity_weight * liquidity_confidence
    
    # Формируем детальную информацию
    details = {
        "steps": steps,
        "min_liquidity": min_liquidity,
        "fees": fees,
        "total_fee": total_fee,
        "profit_factor": profit_factor,
        "confidence_score": confidence
    }
    
    return ArbitrageResult(
        cycle=cycle,
        profit=recommended_volume * (profit_factor - 1),
        profit_percent=profit_percent,
        liquidity=min_liquidity,
        total_fee=total_fee,
        confidence=confidence,
        recommended_volume=recommended_volume,
        details=details
    )

def find_arbitrage(edges: List[Edge]) -> List[ArbitrageResult]:
    """
    Находит арбитражные возможности в графе обмена.
    
    Args:
        edges: Список ребер графа
        
    Returns:
        Список объектов ArbitrageResult с параметрами арбитражных возможностей
    """
    # Выполняем алгоритм Беллмана-Форда
    has_negative_cycle, distances, predecessors = bellman_ford(edges)
    
    if not has_negative_cycle:
        logger.info("Арбитражные возможности не найдены")
        return []
    
    # Находим отрицательный цикл
    cycle = find_negative_cycle_path(next(iter(distances)), predecessors)
    
    if not cycle:
        logger.warning("Отрицательный цикл обнаружен, но не удалось восстановить его")
        return []
    
    # Получаем словарь с данными для create_graph
    # Нам нужен словарь формата {from_node: {to_node: {rate, liquidity, fee}}}
    exchange_data = {}
    for edge in edges:
        if edge.from_node not in exchange_data:
            exchange_data[edge.from_node] = {}
        
        exchange_data[edge.from_node][edge.to_node] = {
            'rate': edge.rate,
            'liquidity': edge.liquidity,
            'fee': edge.fee
        }
    
    # Рассчитываем параметры арбитражной возможности
    arbitrage = find_arbitrage_advanced(
        exchange_data,    # Передаем словарь обменных курсов вместо списка рёбер
        budget=100.0,     # Устанавливаем начальный бюджет
        min_profit=0.1    # Устанавливаем минимальный процент прибыли
    )
    
    if not arbitrage:
        logger.warning("Не удалось рассчитать параметры арбитражной возможности")
        return []
    
    return [arbitrage]

def find_multiple_arbitrage(edges: List[Edge], max_cycles: int = 5) -> List[ArbitrageResult]:
    """
    Находит несколько арбитражных возможностей, модифицируя граф после каждого найденного цикла.
    
    Args:
        edges: Список ребер графа
        max_cycles: Максимальное количество циклов для поиска
        
    Returns:
        Список объектов ArbitrageResult с параметрами арбитражных возможностей
    """
    # Копируем список ребер, чтобы не изменять оригинал
    current_edges = edges.copy()
    
    # Результаты арбитража
    arbitrage_results = []
    
    # Строим множество всех узлов для инициализации
    nodes = set()
    for edge in current_edges:
        nodes.add(edge.from_node)
        nodes.add(edge.to_node)
    
    if not nodes:
        return []

    # Выбираем стартовый узел
    source_node = next(iter(nodes))
    
    # Ищем арбитражные возможности, пока не найдем max_cycles или пока они не закончатся
    for _ in range(max_cycles):
        # Выполняем алгоритм Беллмана-Форда
        has_cycle, distances, predecessors, cycle = bellman_ford_optimized(current_edges, source_node)
        
        if not has_cycle:
            break
        
        # Преобразуем список рёбер в словарь обменных курсов
        exchange_data = {}
        for edge in current_edges:
            if edge.from_node not in exchange_data:
                exchange_data[edge.from_node] = {}
            
            exchange_data[edge.from_node][edge.to_node] = {
                'rate': edge.rate,
                'liquidity': edge.liquidity,
                'fee': edge.fee
            }
        
        # Находим арбитражные возможности
        arbitrage = find_arbitrage_advanced(
            exchange_data,   # Передаем словарь обменных курсов вместо списка рёбер
            budget=100.0,    # Устанавливаем начальный бюджет
            min_profit=0.1   # Устанавливаем минимальный процент прибыли
        )
        
        if not arbitrage:
            break
        
        # Добавляем найденные возможности в результаты
        arbitrage_results.extend(arbitrage)
        
        # Модифицируем граф, увеличивая веса ребер в найденных циклах
        # для поиска других арбитражных возможностей
        modified_edges = []
        for edge in current_edges:
            is_in_cycle = False
            for arb in arbitrage_results:
                # Проверяем, является ли arb объектом ArbitrageResult или словарем
                if isinstance(arb, ArbitrageResult):
                    cycle_path = arb.cycle
                elif isinstance(arb, dict) and 'path' in arb:
                    # Удаляем последний элемент, т.к. он повторяет первый
                    cycle_path = arb['path'][:-1] if arb['path'][0] == arb['path'][-1] else arb['path']
                else:
                    continue
                
                # Проверяем, входит ли ребро в цикл
                for i in range(len(cycle_path) - 1):
                    if edge.from_node == cycle_path[i] and edge.to_node == cycle_path[i + 1]:
                        is_in_cycle = True
                        break
                
                if is_in_cycle:
                    break
            
            if is_in_cycle:
                # Уменьшаем курс обмена на 10%, чтобы сделать цикл менее выгодным
                modified_edge = Edge(
                    from_node=edge.from_node,
                    to_node=edge.to_node,
                    weight=edge.weight + 0.1,  # Увеличиваем вес
                    rate=edge.rate * 0.9,      # Уменьшаем курс обмена
                    liquidity=edge.liquidity,
                    fee=edge.fee
                )
                modified_edges.append(modified_edge)
            else:
                modified_edges.append(edge)
        
        current_edges = modified_edges
    
    # Сортируем результаты по убыванию прибыли
    if all(isinstance(arb, ArbitrageResult) for arb in arbitrage_results):
        arbitrage_results.sort(key=lambda x: x.profit_percent, reverse=True)
    elif all(isinstance(arb, dict) for arb in arbitrage_results):
        arbitrage_results.sort(key=lambda x: x.get('profit', 0), reverse=True)
    
    return arbitrage_results

def find_best_starting_currency(market_items: List[Dict[str, Any]], currencies: List[str] = None) -> Dict[str, Any]:
    """
    Находит лучшую начальную валюту для арбитражных операций.
    
    Args:
        market_items: Список предметов с рынка
        currencies: Список валют для анализа (если None, используются USD, EUR, BTC)
        
    Returns:
        Словарь с результатами для каждой валюты
    """
    if currencies is None:
        currencies = ['USD', 'EUR', 'BTC']
    
    results = {}
    
    for currency in currencies:
        # Создаем граф с указанной валютой в качестве источника
        edges = create_graph(market_items)
        
        # Выполняем алгоритм Беллмана-Форда с указанной валютой в качестве источника
        has_cycle, distances, predecessors, cycle = bellman_ford_optimized(edges, currency)
        
        if has_cycle:
            # Преобразуем список рёбер в словарь обменных курсов
            exchange_data = {}
            for edge in edges:
                if edge.from_node not in exchange_data:
                    exchange_data[edge.from_node] = {}
                
                exchange_data[edge.from_node][edge.to_node] = {
                    'rate': edge.rate,
                    'liquidity': edge.liquidity,
                    'fee': edge.fee
                }
                
            # Находим арбитражные возможности
            arbitrage = find_arbitrage_advanced(
                exchange_data,   # Передаем словарь обменных курсов вместо списка рёбер
                budget=100.0,    # Устанавливаем начальный бюджет
                min_profit=0.1   # Устанавливаем минимальный процент прибыли
            )
            
            # Проверяем, есть ли арбитражные возможности
            if arbitrage:
                # Вычисляем максимальную прибыль
                max_profit = max(arb.get('profit', 0) for arb in arbitrage) if arbitrage else 0
                # Вычисляем среднюю прибыль
                avg_profit = sum(arb.get('profit', 0) for arb in arbitrage) / len(arbitrage) if arbitrage else 0
                
                # Сохраняем результаты для валюты
                results[currency] = {
                    'opportunities': len(arbitrage),
                    'max_profit': max_profit,
                    'avg_profit': avg_profit,
                    'most_profitable': arbitrage[0] if arbitrage else None
                }
            else:
                results[currency] = {
                    'opportunities': 0,
                    'max_profit': 0,
                    'avg_profit': 0,
                    'most_profitable': None
                }
        else:
            results[currency] = {
                'opportunities': 0,
                'max_profit': 0,
                'avg_profit': 0,
                'most_profitable': None
            }
    
    return results

def parallel_market_analysis(market_items: List[Dict[str, Any]], chunk_size: int = 100) -> List[ArbitrageResult]:
    """
    Параллельный анализ рынка для поиска арбитражных возможностей.
    
    Args:
        market_items: Список предметов с рынка
        chunk_size: Размер порции данных для параллельной обработки
        
    Returns:
        Список объектов ArbitrageResult с параметрами арбитражных возможностей
    """
    # Замечание: для реальной параллельной обработки требуется модуль concurrent.futures
    # или asyncio. Здесь приведен упрощенный вариант без реальной параллельности.
    
    # Разделяем данные на порции
    chunks = [market_items[i:i+chunk_size] for i in range(0, len(market_items), chunk_size)]
    
    # Результаты для всех порций
    all_results = []
    
    # Обрабатываем каждую порцию
    for chunk in chunks:
        # Создаем граф для текущей порции данных
        edges = create_graph(chunk)
        
        # Ищем арбитражные возможности
        arbitrage = find_multiple_arbitrage(edges)
        
        # Добавляем результаты
        all_results.extend(arbitrage)
    
    # Сортируем все результаты по убыванию прибыли
    all_results.sort(key=lambda x: x.profit_percent, reverse=True)
    
    return all_results

def filter_arbitrage_opportunities(opportunities: List[ArbitrageResult], 
                                  min_profit_percent: float = 0.5,
                                  min_liquidity: float = 5.0,
                                  min_confidence: float = 0.3) -> List[ArbitrageResult]:
    """
    Фильтрует список арбитражных возможностей по заданным критериям.
    
    Отбирает арбитражные возможности, удовлетворяющие требованиям по минимальному
    проценту прибыли, ликвидности и уровню уверенности. Отфильтрованные возможности
    сортируются по проценту прибыли в порядке убывания.
    
    Args:
        opportunities: Список арбитражных возможностей для фильтрации
        min_profit_percent: Минимальный процент прибыли для включения возможности (в %)
        min_liquidity: Минимальная ликвидность для включения возможности
        min_confidence: Минимальный уровень уверенности (от 0.0 до 1.0)
        
    Returns:
        Отфильтрованный и отсортированный список арбитражных возможностей
        
    Examples:
        >>> filtered = filter_arbitrage_opportunities(
        ...     opportunities,
        ...     min_profit_percent=1.0,  # Минимум 1% прибыли
        ...     min_liquidity=10.0,      # Хорошая ликвидность
        ...     min_confidence=0.7       # Высокая уверенность
        ... )
    
    Note:
        - Высокие значения min_profit_percent сильнее сокращают список возможностей, 
          но оставшиеся возможности будут более прибыльными
        - Высокие значения min_liquidity и min_confidence снижают риск, но могут
          отфильтровать прибыльные возможности на менее ликвидных рынках
    """
    if not opportunities:
        logger.debug("Пустой список возможностей для фильтрации")
        return []
    
    # Валидируем входные параметры
    min_profit_percent = max(0.0, float(min_profit_percent))
    min_liquidity = max(0.0, float(min_liquidity))
    min_confidence = max(0.0, min(1.0, float(min_confidence)))
    
    # Логирование параметров фильтрации
    logger.debug(
        f"Фильтрация арбитражных возможностей: "
        f"мин. прибыль={min_profit_percent}%, "
        f"мин. ликвидность={min_liquidity}, "
        f"мин. уверенность={min_confidence}"
    )
    
    # Применяем фильтры
    filtered = [
        op for op in opportunities
        if (op.profit_percent >= min_profit_percent and
            op.liquidity >= min_liquidity and
            op.confidence >= min_confidence)
    ]
    
    # Сортируем по проценту прибыли (от большего к меньшему)
    filtered.sort(key=lambda op: op.profit_percent, reverse=True)
    
    logger.debug(f"Отфильтровано {len(filtered)} возможностей из {len(opportunities)}")
    
    return filtered

async def find_all_arbitrage_opportunities_async(market_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Асинхронная функция для поиска всех арбитражных возможностей.
    
    Эта функция служит оболочкой для неасинхронных функций, чтобы 
    обеспечить поддержку асинхронного вызова из других модулей.
    
    Args:
        market_data: Данные рынка в формате словаря.
            Ожидается структура, содержащая информацию о доступных обменах.
            
    Returns:
        Список словарей, представляющих арбитражные возможности.
    """
    logger.info("Запуск асинхронного поиска арбитражных возможностей с алгоритмом Беллмана-Форда")
    
    # Преобразуем market_data в граф
    try:
        # Проверяем наличие данных
        if not market_data:
            logger.warning("Получены пустые данные рынка")
            return []
            
        # Создаем граф из данных рынка
        exchange_data = preprocess_market_data(market_data)
        edges = create_graph(exchange_data)
        
        if not edges:
            logger.warning("Не удалось создать граф из предоставленных данных рынка")
            return []
            
        # Ищем арбитражные возможности
        arbitrage_results = find_arbitrage(edges)
        
        # Фильтруем результаты по минимальной прибыли и ликвидности
        filtered_results = filter_arbitrage_opportunities(
            arbitrage_results,
            min_profit_percent=0.5,  # Минимум 0.5% прибыли
            min_liquidity=5.0        # Минимальная ликвидность
        )
        
        # Преобразуем результаты в словари для API
        opportunities = [result_to_dict(result) for result in filtered_results]
        
        logger.info(f"Найдено {len(opportunities)} арбитражных возможностей")
        return opportunities
        
    except Exception as e:
        logger.error(f"Ошибка при поиске арбитражных возможностей: {e}")
        return []

def preprocess_market_data(market_data: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """
    Преобразует данные рынка в формат, подходящий для создания графа.
    
    Args:
        market_data: Исходные данные рынка
        
    Returns:
        Структурированные данные в формате для функции create_graph
    """
    exchange_data = {}
    
    # Простая реализация - предполагаем, что market_data уже содержит
    # необходимую структуру или требует минимального преобразования
    if isinstance(market_data, dict) and "items" in market_data:
        items = market_data.get("items", [])
        
        for item in items:
            from_node = item.get("from_market", item.get("market"))
            to_node = item.get("to_market", item.get("target_market"))
            rate = item.get("rate", item.get("exchange_rate", 1.0))
            
            if from_node and to_node and rate:
                if from_node not in exchange_data:
                    exchange_data[from_node] = {}
                    
                exchange_data[from_node][to_node] = {
                    "rate": rate,
                    "liquidity": item.get("liquidity", 100.0),
                    "fee": item.get("fee", 0.0)
                }
    else:
        # Если формат не соответствует ожидаемому, возвращаем исходные данные
        return market_data
    
    return exchange_data

def result_to_dict(result: ArbitrageResult) -> Dict[str, Any]:
    """
    Преобразует объект ArbitrageResult в словарь для API.
    
    Args:
        result: Объект ArbitrageResult
        
    Returns:
        Словарь с данными об арбитражной возможности
    """
    return {
        "cycle": result.cycle,
        "profit": round(result.profit, 6),
        "profit_percent": round(result.profit_percent, 2),
        "liquidity": round(result.liquidity, 2),
        "total_fee": round(result.total_fee, 6),
        "confidence": round(result.confidence, 2),
        "recommended_volume": round(result.recommended_volume, 2),
        "details": result.details
    }

async def generate_dmarket_target_orders(
    game_id: str,
    min_profit_percent: float = 1.0,
    limit: int = 10,
    budget: float = 100.0,
    market_data: Dict[str, Any] = None,
    api_client = None
) -> List[Dict[str, Any]]:
    """
    Генерирует целевые ордера для арбитража на DMarket.
    
    Args:
        game_id: Идентификатор игры
        min_profit_percent: Минимальный процент прибыли
        limit: Максимальное количество возвращаемых предметов
        budget: Бюджет для торговли
        market_data: Данные рынка (если None, будут загружены с помощью API)
        api_client: Клиент API для загрузки данных (если None, используется встроенный)
        
    Returns:
        Список целевых ордеров для арбитража
    """
    logger.info(f"Генерация целевых ордеров для арбитража на DMarket (игра: {game_id})")
    
    try:
        # Загружаем данные рынка, если они не предоставлены
        if market_data is None:
            if api_client is None:
                logger.error("Не предоставлены данные рынка и API клиент")
                return []
            
            try:
                market_data = await api_client.get_market_items(game_id, limit=500)
            except Exception as e:
                logger.error(f"Ошибка загрузки данных рынка: {e}")
                return []
        
        # Находим арбитражные возможности
        arbitrage_opportunities = await find_all_arbitrage_opportunities_async(
            market_data,
            game_id=game_id,
            min_profit_percent=min_profit_percent,
            max_results=limit,
            budget=budget
        )
        
        if not arbitrage_opportunities:
            logger.info(f"Арбитражные возможности не найдены для игры {game_id}")
            return []
        
        # Преобразуем возможности в целевые ордера
        target_orders = []
        for opp in arbitrage_opportunities:
            # Извлекаем данные о цикле и прибыли
            cycle = opp.get('cycle', [])
            profit = opp.get('profit', 0)
            profit_percent = opp.get('profit_percent', 0)
            
            if not cycle or len(cycle) < 2:
                continue
                
            # Создаем ордера для каждого шага в цикле
            for i in range(len(cycle) - 1):
                from_item = cycle[i]
                to_item = cycle[i + 1]
                
                # Находим конкретный предмет в данных рынка
                item_data = None
                if isinstance(market_data, dict):
                    if from_item in market_data:
                        item_data = market_data[from_item]
                    elif 'items' in market_data and from_item in market_data['items']:
                        item_data = market_data['items'][from_item]
                
                if not item_data:
                    continue
                
                # Создаем целевой ордер
                order = {
                    'item_id': from_item,
                    'target_item': to_item,
                    'price': item_data.get('price', 0),
                    'estimated_profit': profit,
                    'profit_percent': profit_percent,
                    'cycle_position': i,
                    'cycle_length': len(cycle) - 1,
                    'cycle': cycle
                }
                
                target_orders.append(order)
        
        # Сортируем по проценту прибыли
        target_orders.sort(key=lambda x: x.get('profit_percent', 0), reverse=True)
        
        # Ограничиваем количество возвращаемых ордеров
        return target_orders[:limit]
    except Exception as e:
        logger.error(f"Ошибка генерации целевых ордеров: {e}")
        return []
