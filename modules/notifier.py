
import requests
import json
import os
import asyncio
from telegram.error import NetworkError
from telegram import ReplyKeyboardMarkup
from datetime import datetime
from modules.alert_tracker import is_new_alert

BOT_TOKEN = "7326658749:AAFqhl8U5t_flhDhr2prAzfjZtEdcCKYdsg"
USERS_FILE = "data/users.json"

keyboard = [
    ["🌀 أقوى الأسهم", "💥 أسهم انفجارية"],
    ["🚀 حركة عالية", "✨ تحليل سهم"],
    ["🔄 تحديث الآن", "📊 تقرير يومي"]
]
markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_all_user_ids():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)
        return list(users.keys())
    return []

def send_telegram_message(message):
    chat_ids = get_all_user_ids()
    print("📨 المحاولة لإرسال التنبيه إلى:", chat_ids)

    for chat_id in chat_ids:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        try:
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"❌ فشل إرسال الرسالة إلى {chat_id}: {e}")

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
    users = get_all_user_ids()
    for chat_id in users:
        await safe_send_message(bot, chat_id, text)

def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

async def notify_new_stock(bot, stock, list_type):
    if list_type == "top":
        message = f"""\n✨ <b>🌀 سهم قوي جديد</b> ✨\n🎯 <code>{stock['symbol']}</code>\n💰 <b>السعر:</b> {stock['close']:.2f} $\n📊 <b>القوة:</b> {stock.get('score', 0):.2f}%\n🔄 <b>الحجم:</b> {stock['vol']:,}\n🔼 <b>الهدف:</b> {stock['close']*1.1:.2f} $\n⏳ <b>الوقت:</b> {datetime.now().strftime("%H:%M")}\n"""
    elif list_type == "pump":
        message = f"""\n💥 <b>⚡ سهم انفجاري</b> 💥\n💣 <code>{stock['symbol']}</code>\n📈 <b>التغير:</b> +{stock['change']:.2f}%\n🔥 <b>الحجم:</b> {stock['vol']:,}\n🎯 <b>الأهداف:</b>\n🔼 1. {stock['close']*1.1:.2f} $\n🔼 2. {stock['close']*1.25:.2f} $\n🔻 <b>الوقف:</b> {stock['close']*0.85:.2f} $\n"""
    elif list_type == "high_movement":
        message = f"""\n🚀 <b>🌪️ حركة صاروخية</b> 🚀\n⚡ <code>{stock['symbol']}</code>\n📈 <b>التغير:</b> {stock['change']:.2f}%\n🔊 <b>الحجم:</b> {stock['vol']:,}\n📶 <b>المؤشرات:</b>\n🌀 RSI: {stock.get('rsi', 'N/A')}\n🌀 MACD: {stock.get('macd', 'N/A')}\n"""
    
    print(f"📡 إرسال تنبيه للسهم {stock['symbol']} من نوع {list_type}")
    await broadcast_message(bot, message.strip())

def compare_stock_lists_and_alert(old_file, new_file, label):
    def load_symbols(path):
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return [x["symbol"] for x in data]

    old_symbols = set(load_symbols(old_file))
    new_data = []
    if os.path.exists(new_file):
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)

    alerts_sent = 0
    for stock in new_data:
        if not isinstance(stock, dict):
            continue
        symbol = stock.get("symbol")
        if symbol and symbol not in old_symbols and is_new_alert(symbol):
            print(f"🆕 سهم جديد: {symbol}")
            message = f"{label} <b>{symbol}</b>"
            send_telegram_message(message)
            alerts_sent += 1

    print(f"🔔 تم إرسال {alerts_sent} تنبيه جديد.")
