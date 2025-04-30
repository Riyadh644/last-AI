# ✅ notifier.py
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
    def load_json_safe(path):
        return json.load(open(path, encoding='utf-8')) if os.path.exists(path) else []

    old_top = load_json_safe("data/top_stocks_old.json")
    new_top = load_json_safe("data/top_stocks.json")

    old_pump = load_json_safe("data/pump_stocks_old.json")
    new_pump = load_json_safe("data/pump_stocks.json")

    old_high = load_json_safe("data/high_movement_stocks_old.json")
    new_high = load_json_safe("data/high_movement_stocks.json")

    sections = [
        ("top", new_top, old_top),
        ("pump", new_pump, old_pump),
        ("high_movement", new_high, old_high),
    ]

    for list_type, new_list, old_list in sections:
        new_symbols = {x['symbol'] for x in new_list}
        old_symbols = {x['symbol'] for x in old_list}

        added_symbols = new_symbols - old_symbols
        for stock in new_list:
            if stock['symbol'] in added_symbols:
                await notify_new_stock(bot, stock, list_type)


async def notify_target_hit(bot, stock, target_type):
    if target_type == "target1":
        message = f"""
🎯 <b>✨ هدف أول محقق</b> 🎯

🏆 <code>{stock['symbol']}</code>
💰 <b>الدخول:</b> {stock['entry_price']:.2f} $
📈 <b>الحالي:</b> {stock['current_price']:.2f} $
📊 <b>الربح:</b> +{stock['profit']:.2f} %
⏱️ <b>المدة:</b> {stock.get('duration', 'N/A')}
"""
    elif target_type == "target2":
        message = f"""
🎯🎯 <b>🌟 هدف ثاني محقق</b> 🎯🎯

<code>{stock['symbol']}</code>
💰 <b>الدخول:</b> {stock['entry_price']:.2f} $
📈 <b>الحالي:</b> {stock['current_price']:.2f} $
📊 <b>الربح:</b> +{stock['profit']:.2f} %
⏳ <b>المدة:</b> {stock.get('duration', 'N/A')}
"""
    await broadcast_message(bot, message.strip())


async def notify_stop_loss(bot, stock):
    message = f"""
⚠️ <b>🌪️ إنذار وقف خسارة</b> ⚠️

🔻 <code>{stock['symbol']}</code>
📉 <b>انخفاض:</b> {stock['distance_to_sl']:.2f} %
💸 <b>الوقف:</b> {stock['stop_loss_price']:.2f} $

🚨 <b>الإجراء:</b> اخرج فورًا
🕒 <b>الوقت:</b> {datetime.now().strftime("%H:%M")}
"""
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
        symbol = stock.get("symbol")
        if symbol and symbol not in old_symbols and is_new_alert(symbol):
            print(f"🆕 سهم جديد: {symbol}")
            message = f"{label} <b>{symbol}</b>"
            send_telegram_message(message)
            alerts_sent += 1
        if not isinstance(stock, dict):
         continue  # تجاهل أي عنصر غير قاموس
    symbol = stock.get("symbol")
    print(f"🔔 تم إرسال {alerts_sent} تنبيه جديد.")
