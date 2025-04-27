import json
import os
import yfinance as yf
from datetime import datetime
from modules.telegram_bot import notify_target_hit, notify_stop_loss

TRADE_HISTORY_FILE = "data/trade_history.json"

def is_market_open():
    """التأكد أن السوق الأمريكي مفتوح"""
    now = datetime.utcnow()
    return now.weekday() < 5 and 13 <= now.hour <= 20  # توقيت UTC للسوق الأمريكي

async def check_targets(bot):
    """فحص تحقيق الأهداف ووقف الخسارة لجميع الأسهم"""
    if not os.path.exists(TRADE_HISTORY_FILE):
        return

    # 🔒 تأكد أن السوق مفتوح قبل أي فحص
    if not is_market_open():
        print("⏸️ السوق مغلق، لن يتم متابعة الأهداف حالياً.")
        return

    with open(TRADE_HISTORY_FILE, "r", encoding="utf-8") as f:
        trades = json.load(f)

    for trade in trades:
        symbol = trade["symbol"]
        entry_price = float(trade["entry_price"])
        target1 = entry_price * 1.1
        target2 = entry_price * 1.25
        stop_loss = entry_price * 0.85

        try:
            stock = yf.Ticker(symbol)
            history = stock.history(period="1d")
            if history.empty:
                continue
            current_price = history["Close"].iloc[-1]

            # تأكد أن السعر الابتدائي ليس صفر لتجنب قسمة صفرية
            if entry_price == 0:
                continue

            # فحص تحقيق الأهداف
            if current_price >= target2 and not trade.get("target2_hit", False):
                await notify_target_hit(bot, {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "profit": ((current_price - entry_price) / entry_price) * 100
                }, "target2")
                trade["target2_hit"] = True

            elif current_price >= target1 and not trade.get("target1_hit", False):
                await notify_target_hit(bot, {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "profit": ((current_price - entry_price) / entry_price) * 100
                }, "target1")
                trade["target1_hit"] = True

            # فحص وقف الخسارة
            if current_price <= stop_loss and not trade.get("stop_loss_hit", False):
                await notify_stop_loss(bot, {
                    "symbol": symbol,
                    "entry_price": entry_price,
                    "current_price": current_price,
                    "stop_loss_price": stop_loss,
                    "distance_to_sl": ((current_price - stop_loss) / stop_loss) * 100
                })
                trade["stop_loss_hit"] = True

        except Exception as e:
            print(f"❌ خطأ في تتبع سعر {symbol}: {e}")

    # حفظ التحديثات
    with open(TRADE_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)
