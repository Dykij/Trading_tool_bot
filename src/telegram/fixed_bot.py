import logging
import os
import sys
from aiogram import Bot, Dispatcher, executor, types

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Get bot token from environment variable or use a placeholder for testing
bot_token = os.getenv('TELEGRAM_BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')

# Initialize bot and dispatcher
bot = Bot(token=bot_token)
dp = Dispatcher(bot)

# This is a tracker to demonstrate the order of handler registration
handler_calls = []

# High-priority handler (registered first, with state='*')
@dp.message_handler(commands=['start'], state='*')
async def cmd_start_universal(message: types.Message):
    """
    A high-priority start command handler that works in any state.
    Always checked first due to being registered first and having state='*'.
    """
    handler_calls.append("cmd_start_universal")
    await message.answer('Hello! I am a bot demonstrating handler priorities.\n'
                         'This response comes from the high-priority universal start handler.')
    logger.info(f'User {message.from_user.id} used the universal start command')
    
    # Log the handler call history to demonstrate priority
    await message.answer(f'Handler call history: {handler_calls}')

# Medium-priority handler (registered second)
@dp.message_handler(commands=['start'])
async def cmd_start_regular(message: types.Message):
    """
    A regular start command handler with medium priority.
    This should never be called when the universal handler exists.
    """
    handler_calls.append("cmd_start_regular")
    await message.answer('Hello! This response is from the regular start handler.\n'
                         'You should never see this message if the universal handler is working.')
    logger.info(f'User {message.from_user.id} used the regular start command')
    
    # Log the handler call history to demonstrate priority
    await message.answer(f'Handler call history: {handler_calls}')

# Help command handler
@dp.message_handler(commands=['help'])
async def cmd_help(message: types.Message):
    handler_calls.append("cmd_help")
    await message.answer('Available commands:\n'
                         '/start - Start the bot (has high-priority handler)\n'
                         '/help - Show this help message\n'
                         '/clear - Clear the handler call history\n'
                         '/priority - Explain message handler priority')
    logger.info(f'User {message.from_user.id} requested help')
    
    # Log the handler call history to demonstrate priority
    await message.answer(f'Handler call history: {handler_calls}')

# Clear history command
@dp.message_handler(commands=['clear'])
async def cmd_clear(message: types.Message):
    handler_calls.clear()
    await message.answer('Handler call history has been cleared.')
    logger.info(f'User {message.from_user.id} cleared handler history')

# Priority explanation command
@dp.message_handler(commands=['priority'])
async def cmd_priority(message: types.Message):
    handler_calls.append("cmd_priority")
    explanation = (
        "Message handler priority in aiogram works as follows:\n\n"
        "1. Handlers are checked in the order they are registered\n"
        "2. State filters have priority ('*' matches any state)\n"
        "3. The first matching handler processes the message\n\n"
        "Best practices:\n"
        "- Register important handlers first\n"
        "- Use state='*' for commands that should always be available\n"
        "- Be careful with generic handlers that might match too broadly"
    )
    await message.answer(explanation)
    logger.info(f'User {message.from_user.id} requested priority explanation')
    
    # Log the handler call history to demonstrate priority
    await message.answer(f'Handler call history: {handler_calls}')

# Low-priority general text handler (registered last)
@dp.message_handler(content_types=types.ContentTypes.TEXT)
async def process_text(message: types.Message):
    handler_calls.append("process_text")
    logger.info(f'Received message from {message.from_user.id}: {message.text}')
    await message.answer(f'You said: {message.text}')
    
    # Log the handler call history to demonstrate priority
    await message.answer(f'Handler call history: {handler_calls}')

# Main entry point
if __name__ == '__main__':
    logger.info('Starting the bot with priority demonstration...')
    
    try:
        # Start the bot
        executor.start_polling(dp, skip_updates=True)
        
    except Exception as e:
        logger.error(f'Critical error: {e}', exc_info=True)
        sys.exit(1) 