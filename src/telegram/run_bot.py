#!/usr/bin/env python
"""
Точка входа для запуска Telegram бота DMarket Trading Bot.
Основной функционал управления перенесен в модуль bot_manager.py
"""

from src.telegram.bot_manager import run_bot

if __name__ == "__main__":
    exit(run_bot()) 