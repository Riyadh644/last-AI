from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ContextTypes
from modules.user_manager import save_user
from modules.analyze_performance import generate_report_summary
from modules.ml_model import load_model, predict_buy_signal
from modules.tv_data import fetch_data_from_tradingview
from modules.notifier import safe_send_message, compare_stock_lists_and_alert
import json
import os
from datetime import datetime

keyboard = [
    ["🌀 أقوى الأسهم", "💥 أسهم انفجارية"],
    ["🚀 حركة عالية", "✨ تحليل سهم"],
    ["🔄 تحديث الآن", "📊 تقرير يومي"]
]

USERS_FILE = "data/users.json"

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    save_user(chat_id)
    await update.get_bot().send_message(
        chat_id=chat_id,
        text="""
✨ <b>تداول بالذكاء الإصطناعي</b> ✨

🚀 هذا البوت يوفر:
🌀  الأسهم القوية
💥 تنبيهات الأسهم الانفجارية
⚡ تحليلات الحركة السعرية

 اختر من القائمة للبدء:
""",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True),
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
🌟 <b>الهدف 1:</b> {round(entry * 1.1, 2)} $
🌟 <b>الهدف 2:</b> {round(entry * 1.25, 2)} $
⚠ <b>الوقف:</b> {round(entry * 0.85, 2)} $
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
⚠ <b>الوقف:</b> {round(entry * 0.85, 2)} $
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
⚠ <b>الوقف:</b> {round(entry * 0.85, 2)} $
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
⚠ <b>الوقف:</b> {round(entry * 0.85, 2)} $
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
        await safe_send_message(update.get_bot(), update.effective_chat.id, f"⚠ فشل التحديث: {e}")
