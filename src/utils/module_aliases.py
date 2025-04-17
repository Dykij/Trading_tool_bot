"""
Модуль для настройки псевдонимов модулей между старой и новой структурой проекта.

Этот модуль упрощает переход между старой и новой структурой, создавая
псевдонимы для модулей, чтобы код, использующий старые импорты, 
продолжал работать с новой структурой.
"""

import sys
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Определяем соответствие между старыми и новыми путями к модулям
MODULE_ALIASES = {
    # Основные модули
    'api_wrapper': ['src.api.api_wrapper', 'DM.api_wrapper'],
    'bellman_ford': ['src.arbitrage.bellman_ford', 'DM.bellman_ford'],
    'linear_programming': ['src.arbitrage.linear_programming', 'DM.linear_programming'],
    'ml_predictor': ['src.ml.ml_predictor', 'DM.ml_predictor'],
    
    # Utils модули
    'utils.api_adapter': ['DM.utils.api_adapter'],
    'utils.api_client': ['DM.utils.api_client'],
    'utils.marketplace_api': ['DM.utils.marketplace_api'],
    'utils.marketplace_integrator': ['DM.utils.marketplace_integrator'],
    'utils.market_analyzer': ['DM.utils.market_analyzer'],
    'utils.error_reporting': ['DM.utils.error_reporting'],
    'utils.caching': ['DM.utils.common.caching', 'DM.utils.caching'],
    'utils.api_retry': ['DM.utils.api_retry'],
    'utils.common': ['DM.utils.common'],
    'utils.database': ['DM.utils.database'],
    'utils.market_graph': ['DM.utils.market_graph'],
    'utils.parallel_processor': ['DM.utils.parallel_processor'],
    'utils.performance_metrics': ['DM.utils.performance_metrics'],
    'utils.performance_monitor': ['DM.utils.performance_monitor'],
    'utils.rate_limiter': ['DM.utils.rate_limiter'],
    'utils.risk_assessment': ['DM.utils.risk_assessment'],
    'utils.pagination': ['DM.utils.ui.pagination', 'DM.utils.pagination'],
}

def setup_module_aliases(extra_aliases: Optional[Dict[str, List[str]]] = None) -> Tuple[int, int]:
    """
    Настраивает псевдонимы модулей в соответствии с картой соответствия.
    
    Args:
        extra_aliases: Дополнительные псевдонимы модулей
        
    Returns:
        Tuple[int, int]: Кортеж (количество успешных настроек, общее количество)
    """
    # Объединяем основные и дополнительные псевдонимы
    aliases = MODULE_ALIASES.copy()
    if extra_aliases:
        aliases.update(extra_aliases)
    
    success_count = 0
    total_count = len(aliases)
    
    for target_name, source_paths in aliases.items():
        success = False
        
        # Пробуем импортировать модуль из каждого источника по порядку
        for source_path in source_paths:
            try:
                module_name = source_path.split('.')[-1]
                logger.debug(f"Попытка импорта {source_path} как {target_name}")
                
                # Пытаемся импортировать модуль
                __import__(source_path)
                
                # Создаем псевдоним
                sys.modules[target_name] = sys.modules[source_path]
                logger.info(f"Настроен псевдоним: {source_path} -> {target_name}")
                
                success = True
                success_count += 1
                break
            except ImportError as e:
                logger.debug(f"Не удалось импортировать {source_path}: {e}")
            except Exception as e:
                logger.warning(f"Ошибка при настройке псевдонима {target_name}: {e}")
        
        if not success:
            logger.warning(f"Не удалось настроить псевдоним для {target_name}")
    
    logger.info(f"Настроено {success_count}/{total_count} псевдонимов модулей")
    return success_count, total_count 