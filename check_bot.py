import os
import sys
import psutil
import socket
from pathlib import Path

def check_processes():
    print("\n=== Проверка процессов Python ===")
    python_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.name().lower().startswith('python'):
                cmdline = ' '.join(proc.cmdline()) if proc.cmdline() else 'Unknown'
                python_processes.append({
                    'pid': proc.pid,
                    'name': proc.name(),
                    'cmdline': cmdline
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    
    if python_processes:
        print(f"Найдено {len(python_processes)} Python процессов:")
        for i, proc in enumerate(python_processes, 1):
            print(f"{i}. PID: {proc['pid']} - {proc['cmdline']}")
    else:
        print("Python процессы не найдены")
    
    # Проверяем PID из лога
    target_pid = 6732
    if psutil.pid_exists(target_pid):
        try:
            proc = psutil.Process(target_pid)
            print(f"\nПроцесс с PID {target_pid} существует:")
            print(f"Имя: {proc.name()}")
            print(f"Командная строка: {' '.join(proc.cmdline())}")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            print(f"\nПроцесс с PID {target_pid} существует, но нет доступа к информации")
    else:
        print(f"\nПроцесс с PID {target_pid} не существует")

def check_pid_file():
    print("\n=== Проверка PID-файла ===")
    project_root = Path(__file__).parent.absolute()
    pid_file = project_root / "tmp" / "bot.pid"
    
    if pid_file.exists():
        print(f"PID-файл найден: {pid_file}")
        with open(pid_file, 'r') as f:
            content = f.read()
            print(f"Содержимое: {content}")
            
        # Проверяем, существует ли процесс из PID-файла
        try:
            import json
            data = json.loads(content)
            pid = data.get('pid')
            if pid and psutil.pid_exists(pid):
                proc = psutil.Process(pid)
                print(f"Процесс из PID-файла (PID: {pid}) существует:")
                print(f"Имя: {proc.name()}")
                print(f"Командная строка: {' '.join(proc.cmdline())}")
            else:
                print(f"Процесс из PID-файла (PID: {pid}) не существует")
        except Exception as e:
            print(f"Ошибка при проверке процесса из PID-файла: {e}")
    else:
        print(f"PID-файл не найден: {pid_file}")

def check_socket():
    print("\n=== Проверка доступности сокета ===")
    port = 12345
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('127.0.0.1', port))
        print(f"Порт {port} свободен, другой экземпляр бота не запущен")
        sock.close()
    except socket.error as e:
        print(f"Порт {port} занят, возможно другой экземпляр бота уже запущен: {e}")

def check_temp_files():
    print("\n=== Проверка временных файлов ===")
    project_root = Path(__file__).parent.absolute()
    tmp_dir = project_root / "tmp"
    
    if tmp_dir.exists():
        print(f"Директория tmp существует: {tmp_dir}")
        files = list(tmp_dir.glob("*"))
        if files:
            print(f"Найдено {len(files)} файлов:")
            for file in files:
                print(f"- {file.name} (размер: {file.stat().st_size} байт, время изменения: {file.stat().st_mtime})")
        else:
            print("Директория tmp пуста")
    else:
        print(f"Директория tmp не существует: {tmp_dir}")

def check_environment():
    print("\n=== Проверка переменных окружения ===")
    bot_restart = os.getenv("BOT_RESTART_INITIATED")
    if bot_restart:
        print(f"BOT_RESTART_INITIATED = {bot_restart}")
    else:
        print("BOT_RESTART_INITIATED не установлен")
    
    print("\nВсе переменные, связанные с ботом:")
    for key, value in os.environ.items():
        if "BOT" in key or "TELEGRAM" in key:
            print(f"{key} = {value}")

if __name__ == "__main__":
    print("=== Диагностика Telegram бота ===")
    print(f"Текущая директория: {os.getcwd()}")
    print(f"Python версия: {sys.version}")
    
    check_processes()
    check_pid_file()
    check_socket()
    check_temp_files()
    check_environment()
    
    print("\n=== Диагностика завершена ===") 