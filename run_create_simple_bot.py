
import logging
logger = logging.getLogger('run_create_simple_bot')

def create_simple_bot_file():
    """Создает файл simple_telegram_bot.py с базовой реализацией бота"""
    from run import RunCreateSimpleBot
    RunCreateSimpleBot.create_simple_bot_file()
    
if __name__ == "__main__":
    create_simple_bot_file()
