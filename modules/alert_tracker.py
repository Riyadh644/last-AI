import json
from datetime import datetime
import os
SEEN_TODAY_FILE = "data/seen_today.json"

def load_seen_today():
    if os.path.exists(SEEN_TODAY_FILE):
        with open(SEEN_TODAY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_seen_today(data):
    with open(SEEN_TODAY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def is_new_alert(symbol):
    today = datetime.now().strftime("%Y-%m-%d")
    seen = load_seen_today()
    if today not in seen:
        seen[today] = []

    if symbol in seen[today]:
        return False

    seen[today].append(symbol)
    save_seen_today(seen)
    return True