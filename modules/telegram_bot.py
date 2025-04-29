from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import NetworkError
import asyncio
import json
import os
import yfinance as yf
import time
import numpy as np
from datetime import datetime
import requests

from modules.tv_data import fetch_data_from_tradingview
from modules.ml_model import load_model, predict_buy_signal
from modules.user_manager import save_user, get_all_users
from modules.analyze_performance import generate_report_summary
from modules.notifier import send_telegram_message, get_all_user_ids

BOT_TOKEN = "7326658749:AAFqhl8U5t_flhDhr2prAzfjZtEdcCKYdsg"
USERS_FILE = "data/users.json"

keyboard = [
    ["🌀 أقوى الأسهم", "💥 أسهم انفجارية"],
    ["🚀 حركة عالية", "✨ تحليل سهم"],
    ["🔄 تحديث الآن", "📊 تقرير يومي"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_trade_history(stock, category):
    path = "data/trade_history.json"
    os.makedirs("data", exist_ok=True)
    history = load_json(path)

    symbol = stock["symbol"]
    if any(x["symbol"] == symbol for x in history):
        return

    record = {
        "symbol": symbol,
        "entry_price": round(stock.get("entry", stock.get("close", 0)), 2),
        "score": round(stock.get("score", 0), 2),
        "category": category,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    history.append(record)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

async def safe_send_message(bot, chat_id, text, retries=3, delay=5):
    max_len = 4000
    parts = [text[i:i + max_len] for i in range(0, len(text), max_len)]

    for part in parts:
        for attempt in range(retries):
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=part,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
                break
            except NetworkError as e:
                print(f"⚠️ فشل الإرسال (محاولة {attempt+1}/{retries}): {e}")
                await asyncio.sleep(delay)
        else:
            print("❌ فشل نهائي في إرسال الرسالة.")

async def broadcast_message(bot, text):
    users = get_all_users()
    for chat_id in users:
        await safe_send_message(bot, chat_id, text)

async def notify_new_stock(bot, stock, list_type):
    if list_type == "top":
        message = f"""
✨ <b>🌀 سهم قوي جديد</b> ✨

🎯 <code>{stock['symbol']}</code>
💰 <b>السعر:</b> {stock['close']:.2f} $
📊 <b>القوة:</b> {stock.get('score', 0):.2f}%
🔄 <b>الحجم:</b> {stock['vol']:,}

🔼 <b>الهدف:</b> {stock['close']*1.1:.2f} $
⏳ <b>الوقت:</b> {datetime.now().strftime("%H:%M")}
"""
    elif list_type == "pump":
        message = f"""
💥 <b>⚡ سهم انفجاري</b> 💥

💣 <code>{stock['symbol']}</code>
📈 <b>التغير:</b> +{stock['change']:.2f}%
🔥 <b>الحجم:</b> {stock['vol']:,}

🎯 <b>الأهداف:</b>
🔼 1. {stock['close']*1.1:.2f} $
🔼 2. {stock['close']*1.25:.2f} $
🔻 <b>الوقف:</b> {stock['close']*0.85:.2f} $
"""
    elif list_type == "high_movement":
        message = f"""
🚀 <b>🌪️ حركة صاروخية</b> 🚀

⚡ <code>{stock['symbol']}</code>
📈 <b>التغير:</b> {stock['change']:.2f}%
🔊 <b>الحجم:</b> {stock['vol']:,}

📶 <b>المؤشرات:</b>
🌀 RSI: {stock.get('rsi', 'N/A')}
🌀 MACD: {stock.get('macd', 'N/A')}
"""
    await broadcast_message(bot, message.strip())

async def compare_stock_lists_and_alert(bot):
    print("🔔 جاري فحص التغيرات في الأسهم...")

    def read_or_empty(path):
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    old_top = read_or_empty("data/top_stocks_old.json")
    old_pump = read_or_empty("data/pump_stocks_old.json")
    old_high = read_or_empty("data/high_movement_stocks_old.json")

    new_top = read_or_empty("data/top_stocks.json")
    new_pump = read_or_empty("data/pump_stocks.json")
    new_high = read_or_empty("data/high_movement_stocks.json")

    sections = [
        ("top", "أقوى الأسهم", old_top, new_top),
        ("pump", "الأسهم القابلة للانفجار", old_pump, new_pump),
        ("high_movement", "الأسهم ذات الحركة العالية", old_high, new_high)
    ]

    for list_type, list_name, old_list, new_list in sections:
        added = [s for s in new_list if s['symbol'] not in [x['symbol'] for x in old_list]]
        for stock in added:
            await notify_new_stock(bot, stock, list_type)
