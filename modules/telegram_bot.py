from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError
import asyncio
import json
import os
from datetime import datetime

from modules.handlers import (
    start,
    top_stocks,
    pump_stocks,
    high_movement_stocks,
    update_symbols_now,
    show_daily_report,
    analyze_stock,
)
from modules.tv_data import analyze_market, fetch_data_from_tradingview
from modules.ml_model import load_model, predict_buy_signal
from modules.user_manager import save_user, get_all_users
from modules.analyze_performance import generate_report_summary
from modules.notifier import send_telegram_message, broadcast_message, safe_send_message

BOT_TOKEN = "7326658749:AAFqhl8U5t_flhDhr2prAzfjZtEdcCKYdsg"

async def start_telegram_bot():
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.Regex("(?i)^🌀"), top_stocks))
        app.add_handler(MessageHandler(filters.Regex("(?i)^💥"), pump_stocks))
        app.add_handler(MessageHandler(filters.Regex("(?i)^🚀"), high_movement_stocks))
        app.add_handler(MessageHandler(filters.Regex("(?i)^🔄"), update_symbols_now))
        app.add_handler(MessageHandler(filters.Regex("(?i)^📊"), show_daily_report))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, analyze_stock))

        print("✨ بوت التليجرام يعمل الآن!")
        await app.run_polling()

    except Exception as e:
        print(f"⚠️ خطأ في البوت: {e}")
        await asyncio.sleep(10)
