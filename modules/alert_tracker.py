import os
import json
from datetime import datetime

SEEN_FILE = "data/seen_today.json"

def load_seen_today():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen_today(data):
    os.makedirs(os.path.dirname(SEEN_FILE), exist_ok=True)
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_new_alert(symbol):
    today = datetime.now().strftime("%Y-%m-%d")

    seen_today = {}
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            try:
                seen_today = json.load(f)
            except Exception as e:
                print(f"⚠️ فشل قراءة {SEEN_FILE}: {e}")
                seen_today = {}

    if today not in seen_today:
        seen_today[today] = []

    if symbol in seen_today[today]:
        return False

    seen_today[today].append(symbol)
    try:
        with open(SEEN_FILE, "w", encoding="utf-8") as f:
            json.dump(seen_today, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ فشل حفظ {SEEN_FILE}: {e}")

    return True