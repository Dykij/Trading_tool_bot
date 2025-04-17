"""
Модуль для программной модификации функций в исходном коде через AST.

Этот инструмент позволяет изменять функции в коде Python, не модифицируя их вручную.
Можно обновлять тело функций, аргументы, декораторы и возвращаемые типы.
"""

import ast
import textwrap
import logging

logger = logging.getLogger(__name__)

def parse_body(body_str):
    """
    Преобразует строку с кодом в AST-узлы тела функции.
    
    Args:
        body_str: Строка с кодом для тела функции
        
    Returns:
        list: Список AST-узлов для тела функции
    """
    dedented = textwrap.dedent(body_str).strip()
    tree = ast.parse(dedented)
    if len(tree.body) == 1 and isinstance(tree.body[0], ast.Expr):
        return [ast.Return(value=tree.body[0].value)]
    return tree.body

def parse_args(args_str):
    """
    Преобразует строку с аргументами в AST-узел аргументов функции.
    
    Args:
        args_str: Строка с объявлениями аргументов функции
        
    Returns:
        ast.arguments: AST-узел с аргументами функции
    """
    dummy_func = f"def dummy({args_str}): pass"
    tree = ast.parse(dummy_func)
    return tree.body[0].args

def parse_decorators(decorators_str):
    """
    Преобразует строку с декораторами в список AST-узлов.
    
    Args:
        decorators_str: Строка с объявлениями декораторов
        
    Returns:
        list: Список AST-узлов декораторов
    """
    if not decorators_str.strip():
        return []
    dummy_func = f"{decorators_str}\ndef dummy(): pass"
    tree = ast.parse(dummy_func)
    return tree.body[0].decorator_list

def parse_returns(returns_str):
    """
    Преобразует строку с возвращаемым типом в AST-узел.
    
    Args:
        returns_str: Строка с объявлением возвращаемого типа
        
    Returns:
        ast.expr: AST-узел возвращаемого типа
    """
    if not returns_str.strip():
        return None
    tree = ast.parse(returns_str, mode='eval')
    return tree.body

class FunctionOptimizer(ast.NodeTransformer):
    """
    AST-трансформер для оптимизации существующих функций на основе пользовательских обновлений.
    """
    def __init__(self, user_updates):
        """
        Инициализирует оптимизатор с обновлениями функций.
        
        Args:
            user_updates: Словарь с именами функций и их обновлениями
        """
        self.function_updates = {}
        self.modified_functions = set()
        
        for func_name, updates in user_updates.items():
            processed_updates = {}
            for key, value in updates.items():
                try:
                    if key == 'body':
                        if isinstance(value, str):
                            processed_updates['body'] = parse_body(value)
                        elif isinstance(value, list) and all(isinstance(stmt, ast.stmt) for stmt in value):
                            processed_updates['body'] = value
                        else:
                            raise ValueError(f"Недопустимая спецификация тела для {func_name}")
                    elif key == 'args':
                        if isinstance(value, str):
                            processed_updates['args'] = parse_args(value)
                        elif isinstance(value, ast.arguments):
                            processed_updates['args'] = value
                        else:
                            raise ValueError(f"Недопустимая спецификация аргументов для {func_name}")
                    elif key == 'decorator_list':
                        if isinstance(value, str):
                            processed_updates['decorator_list'] = parse_decorators(value)
                        elif isinstance(value, list) and all(isinstance(expr, ast.expr) for expr in value):
                            processed_updates['decorator_list'] = value
                        else:
                            raise ValueError(f"Недопустимая спецификация декораторов для {func_name}")
                    elif key == 'returns':
                        if isinstance(value, str):
                            processed_updates['returns'] = parse_returns(value)
                        elif isinstance(value, ast.expr) or value is None:
                            processed_updates['returns'] = value
                        else:
                            raise ValueError(f"Недопустимая спецификация возвращаемого типа для {func_name}")
                    else:
                        raise ValueError(f"Неподдерживаемый ключ обновления: {key}")
                except SyntaxError as e:
                    raise ValueError(f"Синтаксическая ошибка в {key} для {func_name}: {e}")
            self.function_updates[func_name] = processed_updates

    def visit_FunctionDef(self, node):
        """
        Посещает и обновляет определения функций, если они указаны в обновлениях.
        
        Args:
            node: AST-узел, представляющий определение функции
            
        Returns:
            AST-узел: Модифицированный или исходный узел определения функции
        """
        if node.name in self.function_updates:
            update_info = self.function_updates[node.name]
            logger.info(f"Оптимизирую функцию: {node.name}")
            
            new_node = ast.FunctionDef(
                name=node.name,
                args=update_info.get('args', node.args),
                body=update_info.get('body', node.body),
                decorator_list=update_info.get('decorator_list', node.decorator_list),
                returns=update_info.get('returns', node.returns),
                type_comment=node.type_comment
            )
            ast.copy_location(new_node, node)
            ast.fix_missing_locations(new_node)
            
            self.modified_functions.add(node.name)
            return new_node
        return self.generic_visit(node)

def optimize_functions(source_code, user_updates):
    """
    Оптимизирует существующие функции в исходном коде на основе пользовательских обновлений.

    Args:
        source_code (str): Исходный код Python.
        user_updates (dict): Словарь с именами функций и их обновлениями.
            Обновления могут включать 'body', 'args', 'decorator_list', 'returns'
            в виде строк или AST-узлов.

    Returns:
        str: Модифицированный исходный код с оптимизированными функциями.

    Raises:
        ValueError: Если обновления содержат ошибки синтаксиса или недопустимые данные.
    """
    try:
        tree = ast.parse(source_code)
        optimizer = FunctionOptimizer(user_updates)
        modified_tree = optimizer.visit(tree)
        
        if optimizer.modified_functions:
            logger.info(f"Успешно оптимизированы функции: {', '.join(optimizer.modified_functions)}")
        else:
            logger.warning("Не найдено функций для оптимизации")
            
        return ast.unparse(modified_tree)
    except SyntaxError as e:
        logger.error(f"Ошибка синтаксиса в исходном коде: {e}")
        raise ValueError(f"Ошибка синтаксиса в исходном коде: {e}")
    except Exception as e:
        logger.error(f"Ошибка при оптимизации функций: {e}")
        raise ValueError(f"Ошибка при оптимизации функций: {e}")

# Пример использования для DMarket Trading Bot
if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    # Пример исходного кода, типичного для торгового инструмента
    original_code = """
def calculate_profit(trades):
    total = 0
    for trade in trades:
        total += trade['profit']
    return total

def log_trade(trade):
    print(f"Trade: {trade}")
"""
    # Обновления для улучшения функций
    user_updates = {
        'calculate_profit': {
            'body': """
                total = sum(trade['profit'] for trade in trades)
                return total
            """,
            'args': 'trades: list',
            'returns': 'float',
            'decorator_list': '@staticmethod'
        },
        'log_trade': {
            'body': 'return f"Logged trade: {trade}"'
        }
    }
    # Применение оптимизаций
    optimized_code = optimize_functions(original_code, user_updates)
    print(optimized_code)
