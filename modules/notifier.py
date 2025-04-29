# ✅ notifier.py
import requests
import json
import os
import asyncio
from telegram.error import NetworkError
from telegram import ReplyKeyboardMarkup

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
