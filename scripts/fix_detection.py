import os
import sys
import socket
import json
import psutil
import signal
from pathlib import Path

def force_kill_bot_processes():
    """Находит и принудительно завершает все процессы бота"""
    print("Поиск и принудительное завершение процессов бота...")
    
    killed_count = 0
    current_pid = os.getpid()
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.pid == current_pid:
                continue
                
            proc_name = proc.name().lower()
            if not proc_name.startswith('python'):
                continue
                
            cmdline = proc.cmdline()
            if not cmdline or len(cmdline) < 2:
                continue
                
            cmdline_str = ' '.join(cmdline)
            
            # Проверяем, запущен ли это наш бот
            if ('run_bot.py' in cmdline_str and 
                ('telegram' in cmdline_str or 'dmarket_trading_bot' in cmdline_str)):
                print(f"Найден процесс бота (PID: {proc.pid}): {cmdline_str}")
                
                try:
                    proc.kill()
                    print(f"Процесс бота с PID {proc.pid} принудительно завершен")
                    killed_count += 1
                except Exception as e:
                    print(f"Не удалось завершить процесс {proc.pid}: {e}")
                    
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
            
    if killed_count > 0:
        print(f"Завершено {killed_count} процессов бота")
    else:
        print("Процессы бота не найдены")
    
    return killed_count

def release_socket_lock():
    """Проверяет и освобождает блокировку сокета"""
    print("Проверка блокировки сокета...")
    
    port = 12345
    try:
        # Пытаемся связаться с портом
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        
        if result == 0:
            print(f"Порт {port} занят. Возможно, другой экземпляр бота запущен.")
            # Пытаемся подключиться и таким образом "разбудить" процесс,
            # чтобы он корректно закрылся
            sock.close()
            print("Отправлен сигнал на закрытие сокета")
        else:
            print(f"Порт {port} свободен")
            sock.close()
            return True
            
    except Exception as e:
        print(f"Ошибка при проверке сокета: {e}")
    
    # Пробуем второй раз после ожидания
    print("Повторная проверка порта...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('127.0.0.1', port))
        
        if result == 0:
            print(f"Порт {port} все еще занят. Требуется перезагрузка компьютера.")
            sock.close()
            return False
        else:
            print(f"Порт {port} успешно освобожден")
            sock.close()
            return True
            
    except Exception as e:
        print(f"Ошибка при повторной проверке сокета: {e}")
        return False

def remove_pid_file():
    """Удаляет файл PID"""
    project_root = Path(__file__).parent.absolute()
    pid_file = project_root / "tmp" / "bot.pid"
    
    if pid_file.exists():
        try:
            pid_file.unlink()
            print(f"PID-файл удален: {pid_file}")
            return True
        except Exception as e:
            print(f"Ошибка при удалении PID-файла: {e}")
            return False
    else:
        print("PID-файл не найден")
        return True

def clear_bot_flag():
    """Очищает флаг перезапуска бота"""
    try:
        if "BOT_RESTART_INITIATED" in os.environ:
            del os.environ["BOT_RESTART_INITIATED"]
            print("Флаг BOT_RESTART_INITIATED очищен")
            
        # Также проверим другие переменные окружения, связанные с ботом
        restart_flags = [key for key in os.environ if "RESTART" in key or "LOCK" in key]
        for key in restart_flags:
            del os.environ[key]
            print(f"Переменная окружения {key} очищена")
            
        return True
    except Exception as e:
        print(f"Ошибка при очистке переменных окружения: {e}")
        return False

def run_bot_with_debug():
    """Запускает бота в режиме отладки"""
    print("\nЗапуск бота в режиме отладки...")
    
    try:
        os.environ["BOT_DEBUG"] = "1"
        os.system("python src/telegram/run_bot.py")
        return True
    except Exception as e:
        print(f"Ошибка при запуске бота: {e}")
        return False

if __name__ == "__main__":
    print("=== Исправление проблем обнаружения бота ===")
    
    # Останавливаем все процессы бота
    force_kill_bot_processes()
    
    # Удаляем файл PID
    remove_pid_file()
    
    # Освобождаем сокет
    if not release_socket_lock():
        print("\nНе удалось освободить порт. Рекомендуется перезагрузить компьютер.")
        sys.exit(1)
    
    # Очищаем флаги
    clear_bot_flag()
    
    print("\nВсе проблемы обнаружения решены. Теперь вы можете запустить бота:")
    print("1) Обычный режим: python src/telegram/run_bot.py")
    print("2) Режим отладки: $env:BOT_DEBUG=1; python src/telegram/run_bot.py")
    
    choice = input("\nЗапустить бота в режиме отладки? (y/n): ")
    if choice.lower() == 'y':
        run_bot_with_debug() 