import yfinance as yf
import pandas as pd
import json
import numpy as np
from datetime import datetime, timedelta
from modules.tradingview_api import get_filtered_symbols
from modules.stock_utils import calculate_technical_indicators
import os

PUMP_FILE = "data/pump_stocks.json"

def load_existing_symbols():
    if os.path.exists(PUMP_FILE):
        with open(PUMP_FILE, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
                return {s["symbol"] for s in data}
            except:
                return set()
    return set()

def detect_pump_stocks(min_price_change=15, min_volume_spike=2.0, max_price=20):
    pump_candidates = []
    symbols = get_filtered_symbols()

    print(f"🔍 جاري تحليل {len(symbols)} سهم للكشف عن الانفجارات السعرية...")

    old_symbols = load_existing_symbols()

    for symbol in symbols:
        try:
            stock = yf.Ticker(symbol)
            hist = stock.history(period="3mo", interval="1d")

            if hist.empty or len(hist) < 20:
                continue

            hist = calculate_technical_indicators(hist)
            if hist is None:
                continue

            current = hist.iloc[-1]
            prev = hist.iloc[-2]

            price_change = ((current["Close"] - prev["Close"]) / prev["Close"]) * 100
            avg_vol = hist['Volume'].tail(60).mean()
            volume_spike = current["Volume"] > avg_vol * min_volume_spike
            rsi = current.get("RSI", 50)

            conditions = (
                price_change > min_price_change and
                volume_spike and
                current["Close"] < max_price and
                rsi < 70 and
                current["Close"] > current["MA10"] and
                current["Volume"] > 1_000_000
            )

            if conditions and symbol not in old_symbols:
                pump_candidates.append({
                    "symbol": symbol,
                    "price": round(current["Close"], 2),
                    "change%": round(price_change, 2),
                    "volume": int(current["Volume"]),
                    "avg_volume": int(avg_vol),
                    "rsi": round(rsi, 2),
                    "timestamp": datetime.now().isoformat()
                })

        except Exception as e:
            print(f"⚠️ خطأ في تحليل سهم {symbol}: {str(e)}")
            continue

    pump_candidates = sorted(pump_candidates, key=lambda x: x["change%"], reverse=True)

    os.makedirs(os.path.dirname(PUMP_FILE), exist_ok=True)
    with open(PUMP_FILE, "w", encoding="utf-8") as f:
        json.dump(pump_candidates[:20], f, indent=2, ensure_ascii=False)

    print(f"✅ تم اكتشاف {len(pump_candidates)} سهم محتمل للانفجار")
    if pump_candidates:
        print(f"📁 pump_stocks.json تم تحديثه في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    return pump_candidates[:20]

if __name__ == "__main__":
    results = detect_pump_stocks(
        min_price_change=20,
        min_volume_spike=2.5,
        max_price=15
    )
    print("أفضل 5 أسهم:")
    for stock in results[:5]:
        print(f"{stock['symbol']}: {stock['change%']}%")
