import requests
import json
import os
import asyncio
from telegram.error import NetworkError
from telegram import ReplyKeyboardMarkup
from datetime import datetime
from modules.alert_tracker import is_new_alert
from telegram.error import NetworkError
from datetime import datetime
import pytz

KSA = pytz.timezone("Asia/Riyadh")

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
        return users
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
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                response_data = response.json()
                if "error_code" in response_data and response_data["description"] == "Bad Request: chat not found":
                    print(f"⚠️ معرف غير صالح أو لم يبدأ المحادثة: {chat_id}")
                else:
                    print(f"⚠️ خطأ في الإرسال إلى {chat_id}: {response_data}")
        except Exception as e:
            print(f"❌ فشل إرسال الرسالة إلى {chat_id}: {e}")

async def broadcast_message(bot, text):
    users = get_all_user_ids()
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
⏳ <b>الوقت:</b> {datetime.now(KSA).strftime("%H:%M")}

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

async def notify_moved_stock(bot, symbol, from_list, to_list):
    message = f"""
🔁 <b>سهم انتقل إلى قائمة جديدة</b>
🔄 <code>{symbol}</code>
📥 <b>من:</b> {from_list}
📤 <b>إلى:</b> {to_list}
⏳ <b>الوقت:</b> {datetime.now(KSA).strftime("%H:%M")}
"""
    await broadcast_message(bot, message.strip())

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
🕒 <b>الوقت:</b> {datetime.now(KSA).strftime("%H:%M")
}
"""
    await broadcast_message(bot, message.strip())

def compare_stock_lists_and_alert(old_file, new_file, label):
    def load_symbols(path):
        if not os.path.exists(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return [x["symbol"] for x in data if isinstance(x, dict) and "symbol" in x]
                else:
                    print(f"⚠️ الملف {path} ليس قائمة كما هو متوقع.")
                    return []
        except Exception as e:
            print(f"⚠️ خطأ في قراءة {path}: {e}")
            return []

    old_symbols = set(load_symbols(old_file))
    try:
        with open(new_file, "r", encoding="utf-8") as f:
            new_data = json.load(f)
            if not isinstance(new_data, list):
                print(f"⚠️ الملف {new_file} ليس قائمة كما هو متوقع.")
                return
    except Exception as e:
        print(f"⚠️ خطأ في قراءة {new_file}: {e}")
        return

    alerts_sent = 0
    for stock in new_data:
        if not isinstance(stock, dict):
            continue
        symbol = stock.get("symbol")
        if symbol and symbol not in old_symbols:
            if is_new_alert(symbol):
                print(f"🆕 سهم جديد: {symbol}")
                message = f"{label} <b>{symbol}</b>"
                send_telegram_message(message)
                alerts_sent += 1
            else:
                print(f"📛 تم تجاهل {symbol} - تم التنبيه عنه مسبقًا اليوم.")
    print(f"🔔 تم إرسال {alerts_sent} تنبيه جديد.")

async def check_cross_list_movements(bot):
    def load_symbols_safe(path):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return {x["symbol"] for x in data if isinstance(x, dict) and "symbol" in x}
            except Exception as e:
                print(f"⚠️ خطأ أثناء قراءة {path}: {e}")
        return set()

    # ✅ قمنا بالفصل بين الرموز القديمة والجديدة
    old_symbols = {
        "🌀 أقوى": load_symbols_safe("data/top_stocks_old.json"),
        "💥 انفجار": load_symbols_safe("data/pump_stocks_old.json"),
        "🚀 حركة": load_symbols_safe("data/high_movement_stocks_old.json"),
    }

    new_symbols = {
        "🌀 أقوى": load_symbols_safe("data/top_stocks.json"),
        "💥 انفجار": load_symbols_safe("data/pump_stocks.json"),
        "🚀 حركة": load_symbols_safe("data/high_movement_stocks.json"),
    }

    # ✅ لا تستعمل .keys() ولا تعتمد على category structure القديم
    for to_label in new_symbols:
        for from_label in old_symbols:
            if from_label == to_label:
                continue
            moved = new_symbols[to_label] & old_symbols[from_label]
            for symbol in moved:
                await notify_moved_stock(bot, symbol, from_label, to_label)

async def safe_send_message(bot, chat_id, text, retries=3, delay=5):
    max_len = 4000
    parts = [text[i:i + max_len] for i in range(0, len(text), max_len)]
    for part in parts:
        for attempt in range(retries):
            try:
                await bot.send_message(chat_id=chat_id, text=part, reply_markup=markup, parse_mode='HTML')
                return
            except NetworkError as e:
                print(f"⚠️ فشل الإرسال (محاولة {attempt+1}/{retries}): {e}")
                await asyncio.sleep(delay)
        print("❌ فشل نهائي في إرسال الرسالة.")