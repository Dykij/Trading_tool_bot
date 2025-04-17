"""
Модуль для управления статусом бота, включая блокировку запуска,
принудительный перезапуск и мониторинг состояния
"""

import os
import sys
import time
import json
import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

class BotStatus:
    """Класс для управления статусом Telegram бота"""
    
    def __init__(self):
        """Инициализация менеджера статуса бота"""
        self.project_root = Path(__file__).parent.parent.parent.absolute()
        self.pid_file = self.project_root / "tmp" / "bot.pid"
        self.status_file = self.project_root / "tmp" / "bot_status.json"
        
        # Создаем директорию tmp, если она не существует
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
    
    def get_current_pid(self):
        """Возвращает PID текущего процесса"""
        return os.getpid()
    
    def get_bot_pid_from_file(self):
        """Получает PID бота из файла pid"""
        if not self.pid_file.exists():
            return None
            
        try:
            with open(self.pid_file, 'r') as f:
                data = json.load(f)
                return data.get('pid')
        except Exception as e:
            logger.error(f"Ошибка при чтении PID файла: {e}")
            return None
    
    def is_process_running(self, pid):
        """Проверяет, запущен ли процесс с указанным PID"""
        try:
            import psutil
            if not psutil.pid_exists(pid):
                return False
                
            proc = psutil.Process(pid)
            return proc.is_running()
        except Exception:
            return False
    
    def set_restart_flag(self, value=True):
        """Устанавливает флаг перезапуска бота"""
        os.environ["BOT_RESTART_INITIATED"] = "1" if value else "0"
        return value
    
    def set_ignore_running_flag(self, value=True):
        """Устанавливает флаг игнорирования проверки на запущенные экземпляры"""
        os.environ["BOT_IGNORE_RUNNING"] = "1" if value else "0"
        return value
    
    def write_status(self, status):
        """Записывает статус бота в файл"""
        try:
            with open(self.status_file, 'w') as f:
                json.dump(status, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Ошибка при записи статуса: {e}")
            return False
    
    def read_status(self):
        """Читает статус бота из файла"""
        if not self.status_file.exists():
            return {}
            
        try:
            with open(self.status_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Ошибка при чтении статуса: {e}")
            return {}
    
    def clear_pid_file(self):
        """Удаляет файл PID"""
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
                logger.info(f"PID файл удален: {self.pid_file}")
                return True
            except Exception as e:
                logger.error(f"Ошибка при удалении PID файла: {e}")
                return False
        return True
    
    def force_restart_bot(self):
        """Принудительно перезапускает бота"""
        # Устанавливаем флаг перезапуска
        self.set_restart_flag(True)
        
        # Получаем текущую командную строку
        cmd = sys.executable
        args = sys.argv
        
        # Записываем статус перезапуска
        status = {
            "restart_requested": True,
            "restart_time": time.time(),
            "restart_by_pid": self.get_current_pid(),
            "command": [cmd] + args
        }
        self.write_status(status)
        
        # Удаляем PID файл
        self.clear_pid_file()
        
        # Запускаем новый процесс
        try:
            import subprocess
            subprocess.Popen([cmd] + args)
            logger.info(f"Бот перезапущен с командой: {cmd} {' '.join(args)}")
            
            # Завершаем текущий процесс после небольшой задержки
            time.sleep(2)
            sys.exit(0)
        except Exception as e:
            logger.error(f"Ошибка при перезапуске бота: {e}")
            return False
    
    def reset_bot_locks(self):
        """Сбрасывает все блокировки бота"""
        result = {
            "pid_file_removed": self.clear_pid_file(),
            "status_updated": False
        }
        
        # Обновляем статус
        status = self.read_status()
        status.update({
            "locks_reset": True,
            "reset_time": time.time()
        })
        result["status_updated"] = self.write_status(status)
        
        # Сбрасываем флаги
        self.set_restart_flag(False)
        self.set_ignore_running_flag(False)
        
        return result
        
    def get_bot_health(self):
        """Возвращает информацию о состоянии здоровья бота"""
        pid = self.get_bot_pid_from_file()
        is_running = self.is_process_running(pid) if pid else False
        status = self.read_status()
        
        return {
            "pid": pid,
            "is_running": is_running,
            "status": status,
            "pid_file_exists": self.pid_file.exists(),
            "status_file_exists": self.status_file.exists(),
            "restart_flag": os.getenv("BOT_RESTART_INITIATED") == "1",
            "ignore_running_flag": os.getenv("BOT_IGNORE_RUNNING") == "1"
        }


# Функция для использования из командной строки
def main():
    """Функция для управления ботом из командной строки"""
    import argparse
    
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Настройка парсера аргументов
    parser = argparse.ArgumentParser(description='Управление статусом Telegram бота')
    parser.add_argument('--status', action='store_true', help='Показать текущий статус бота')
    parser.add_argument('--restart', action='store_true', help='Перезапустить бота')
    parser.add_argument('--reset', action='store_true', help='Сбросить все блокировки бота')
    
    args = parser.parse_args()
    
    # Создаем экземпляр менеджера статуса
    bot_status = BotStatus()
    
    if args.status:
        health = bot_status.get_bot_health()
        print(json.dumps(health, indent=2))
        
    elif args.restart:
        print("Перезапуск бота...")
        result = bot_status.force_restart_bot()
        print(f"Результат: {'Успешно' if result else 'Ошибка'}")
        
    elif args.reset:
        print("Сброс блокировок бота...")
        result = bot_status.reset_bot_locks()
        print(f"Результат: {json.dumps(result, indent=2)}")
        
    else:
        parser.print_help()


if __name__ == "__main__":
    main() 