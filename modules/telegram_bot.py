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
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from modules.tv_data import analyze_market, fetch_data_from_tradingview
from modules.ml_model import load_model, predict_buy_signal
from modules.user_manager import save_user, get_all_users
from modules.analyze_performance import generate_report_summary

BOT_TOKEN = "7740179871:AAFYnS_QS595Gw5uRTMuW8N9ajUB4pK4tJ0"
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

def send_telegram_message(message):
    chat_ids = get_all_user_ids()
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

async def notify_target_hit(bot, stock, target_type):
    if target_type == "target1":
        message = f"""
🎯 <b>✨ هدف أول محقق</b> 🎯

🏆 <code>{stock['symbol']}</code>
💰 <b>الدخول:</b> {stock['entry_price']:.2f} $
📈 <b>الحالي:</b> {stock['current_price']:.2f} $

📊 <b>الربح:</b> +{stock['profit']:.2f}%
⏱️ <b>المدة:</b> {stock.get('duration', 'N/A')}
"""
    elif target_type == "target2":
        message = f"""
🎯🎯 <b>🌟 هدف ثاني محقق</b> 🎯🎯

🌈 <code>{stock['symbol']}</code>
💰 <b>الدخول:</b> {stock['entry_price']:.2f} $
📈 <b>الحالي:</b> {stock['current_price']:.2f} $

📊 <b>الربح:</b> +{stock['profit']:.2f}%
⏳ <b>المدة:</b> {stock.get('duration', 'N/A')}
"""
    await broadcast_message(bot, message.strip())

async def notify_stop_loss(bot, stock):
    message = f"""
⚠️ <b>🌪️ إنذار وقف خسارة</b> ⚠️

🔻 <code>{stock['symbol']}</code>
📉 <b>انخفاض:</b> {stock['distance_to_sl']:.2f}%
💸 <b>الوقف:</b> {stock['stop_loss_price']:.2f} $

🚨 <b>الإجراء:</b> اخرج فورًا
🕒 <b>الوقت:</b> {datetime.now().strftime("%H:%M")}
"""
    await broadcast_message(bot, message.strip())

async def compare_stock_lists_and_alert(bot):
    print("🔔 جاري فحص التغيرات في الأسهم...")
    
    old_top = load_json("data/top_stocks.json")
    old_pump = load_json("data/pump_stocks.json")
    old_high = load_json("data/high_movement_stocks.json")
    
    new_top = load_json("data/top_stocks.json")
    new_pump = load_json("data/pump_stocks.json")
    new_high = load_json("data/high_movement_stocks.json")
    
    sections = [
        ("top", "أقوى الأسهم", old_top, new_top),
        ("pump", "الأسهم القابلة للانفجار", old_pump, new_pump),
        ("high_movement", "الأسهم ذات الحركة العالية", old_high, new_high)
    ]
    
    for list_type, list_name, old_list, new_list in sections:
        added = [s for s in new_list if s['symbol'] not in [x['symbol'] for x in old_list]]
        for stock in added:
            await notify_new_stock(bot, stock, list_type)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)
    await update.get_bot().send_message(
        chat_id=chat_id,
        text=f"""
✨ <b>تداول بالذكاء الإصطناعي</b> ✨

🚀 هذا البوت يوفر:
🌀  الأسهم القوية
💥 تنبيهات الأسهم الانفجارية
⚡ تحليلات الحركة السعرية

 اختر من القائمة للبدء:
""",
        reply_markup=markup,
        parse_mode='HTML'
    )

async def show_daily_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    summary = generate_report_summary()
    if summary:
        await safe_send_message(update.get_bot(), update.effective_chat.id, summary)
    else:
        await safe_send_message(update.get_bot(), update.effective_chat.id, "🌀 لا يوجد تقرير لهذا اليوم")

async def top_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("data/top_stocks.json")
    if not data:
        return await safe_send_message(update.get_bot(), update.effective_chat.id, "🌀 لا توجد أسهم قوية حالياً")

    data = sorted(data, key=lambda x: x.get("score", 0), reverse=True)[:3]

    msg = ""
    for stock in data:
        entry = round(stock.get("entry", stock.get("close", 0)), 2)
        msg += f"""
🌀 <b>{stock['symbol']}</b>
✨ <b>إشارة:</b> شراء قوي
💰 <b>الدخول:</b> {entry} $
🎯 <b>الهدف 1:</b> {round(entry * 1.1, 2)} $
🌟 <b>الهدف 2:</b> {round(entry * 1.25, 2)} $
⚠️ <b>الوقف:</b> {round(entry * 0.85, 2)} $
📊 <b>النسبة:</b> {stock.get('score', 0):.2f}%
"""
        save_trade_history(stock, category="top")

    await safe_send_message(update.get_bot(), update.effective_chat.id, msg.strip())

async def pump_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("data/pump_stocks.json")
    if not data:
        return await safe_send_message(update.get_bot(), update.effective_chat.id, "💥 لا توجد أسهم انفجارية حالياً")

    data = sorted(data, key=lambda x: x.get("score", 0), reverse=True)[:3]

    msg = ""
    for stock in data:
        entry = round(stock.get("price", stock.get("close", 0)), 2)
        msg += f"""
💣 <b>{stock.get('symbol', 'رمز غير معروف')}</b>
⚡ <b>إشارة:</b> انفجار محتمل
💰 <b>الدخول:</b> {entry} $
🎯 <b>الهدف 1:</b> {round(entry * 1.1, 2)} $
🌟 <b>الهدف 2:</b> {round(entry * 1.25, 2)} $
⚠️ <b>الوقف:</b> {round(entry * 0.85, 2)} $
📊 <b>النسبة:</b> {stock.get('score', 0):.2f}%
"""
        save_trade_history(stock, category="pump")

    await safe_send_message(update.get_bot(), update.effective_chat.id, msg.strip())

async def high_movement_stocks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_json("data/high_movement_stocks.json")
    if not data:
        return await safe_send_message(update.get_bot(), update.effective_chat.id, "🚀 لا توجد أسهم متحركة بقوة حالياً")

    msg = ""
    for stock in data[:3]:
        entry = round(stock.get("close", 0), 2)
        msg += f"""
⚡ <b>{stock['symbol']}</b>
💰 <b>السعر:</b> {entry} $
🎯 <b>الهدف 1:</b> {round(entry * 1.1, 2)} $
🌟 <b>الهدف 2:</b> {round(entry * 1.25, 2)} $
⚠️ <b>الوقف:</b> {round(entry * 0.85, 2)} $
📈 <b>التغير:</b> {stock.get('change', 0):.2f}%
"""
        save_trade_history(stock, category="high_movement")

    await safe_send_message(update.get_bot(), update.effective_chat.id, msg.strip())

async def analyze_stock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    symbol = update.message.text.strip().upper()
    if not symbol.isalpha() or len(symbol) > 5:
        return await safe_send_message(update.get_bot(), update.effective_chat.id, "🌀 أرسل رمز سهم صحيح مثل: TSLA أو PLUG")

    model = load_model()
    data = fetch_data_from_tradingview(symbol)
    if not data:
        return await safe_send_message(update.get_bot(), update.effective_chat.id, f"🌀 لا يمكن تحليل السهم: {symbol}")

    features = {
        "ma10": data["close"],
        "ma30": data["close"],
        "vol": data["vol"],
        "avg_vol": data["vol"],
        "change": data["change"],
        "close": data["close"]
    }

    score = predict_buy_signal(model, features)
    close = round(float(data["close"]), 2)

    if score >= 90:
        entry = close
        msg = f"""
✨ <b>{symbol}</b>
✅ <b>إشارة:</b> شراء قوي
💰 <b>الدخول:</b> {entry} $
🎯 <b>الهدف 1:</b> {round(entry * 1.1, 2)} $
🌟 <b>الهدف 2:</b> {round(entry * 1.25, 2)} $
⚠️ <b>الوقف:</b> {round(entry * 0.85, 2)} $
📊 <b>النسبة:</b> {score:.2f}%
"""
    elif score >= 80:
        msg = f"""
🌀 <b>{symbol}</b>
🕵️ <b>الحالة:</b> تحت المراقبة
📊 <b>النسبة:</b> {score:.2f}%
"""
    else:
        msg = f"""
🌀 <b>{symbol}</b>
❌ <b>الحالة:</b> غير موصى به
📊 <b>النسبة:</b> {score:.2f}%
"""

    await safe_send_message(update.get_bot(), update.effective_chat.id, msg.strip())

async def update_symbols_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await safe_send_message(update.get_bot(), update.effective_chat.id, "🔄 جاري تحديث البيانات...")
    try:
        await compare_stock_lists_and_alert(update.get_bot())
        await safe_send_message(update.get_bot(), update.effective_chat.id, "✨ تم التحديث بنجاح!")
    except Exception as e:
        await safe_send_message(update.get_bot(), update.effective_chat.id, f"⚠️ فشل التحديث: {e}")

async def send_performance_report():
    from telegram import Bot
    bot = Bot(BOT_TOKEN)
    users = get_all_users()
    
    summary = generate_report_summary()
    if not summary:
        print("🌀 لا يوجد تقرير يومي")
        return

    max_len = 4000
    parts = [summary[i:i + max_len] for i in range(0, len(summary), max_len)]

    for user_id in users:
        for part in parts:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text=part,
                    reply_markup=markup,
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"⚠️ فشل إرسال التقرير: {e}")

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
        await app.run_polling()  # هنا لازم "await"
    except Exception as e:
        print(f"⚠️ خطأ في البوت: {e}")
        await asyncio.sleep(10)  # هنا await برضو
if __name__ == "__main__":
    asyncio.run(start_telegram_bot())