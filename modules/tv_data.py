import requests
import json
import os
import numpy as np
from datetime import datetime
from modules.ml_model import load_model, predict_buy_signal
from modules.history_tracker import was_seen_recently, had_recent_losses
import asyncio

TOP_STOCKS_FILE = "data/top_stocks.json"
WATCHLIST_FILE = "data/watchlist.json"
PUMP_FILE = "data/pump_stocks.json"
HIGH_MOVEMENT_FILE = "data/high_movement_stocks.json"

TRADINGVIEW_SESSION = "s2jnbmdgwvazkt0smrddzcdlityywzfx"
TRADINGVIEW_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/json",
    "Referer": "https://www.tradingview.com",
    "Cookie": f"sessionid={TRADINGVIEW_SESSION};"
}

def fetch_stocks_from_tradingview():
    url = "https://scanner.tradingview.com/america/scan"
    payload = {
        "filter": [
            {"left": "volume", "operation": "greater", "right": 2_000_000},
            {"left": "close", "operation": "greater", "right": 0},
            {"left": "close", "operation": "less", "right": 15},
            {"left": "exchange", "operation": "equal", "right": "NASDAQ"},
            {"left": "type", "operation": "equal", "right": "stock"},
            {"left": "change", "operation": "greater", "right": 0}
        ],
        "symbols": {"query": {"types": []}, "tickers": []},
        "columns": ["name", "close", "volume", "market_cap_basic", "change"],
        "sort": {"sortBy": "volume", "sortOrder": "desc"},
        "options": {"lang": "en"},
        "range": [0, 500]
    }

    try:
        response = requests.post(url, json=payload, headers=TRADINGVIEW_HEADERS, timeout=10)
        data = response.json()
        stocks = []
        for item in data.get("data", []):
            s = item["d"]
            stocks.append({
                "symbol": s[0],
                "close": s[1],
                "vol": s[2],
                "market_cap": s[3],
                "change": s[4]
            })
        return stocks
    except Exception as e:
        print(f"\u274c فشل في جلب الأسهم من TradingView: {e}")
        return []

def filter_top_stocks_by_custom_rules(stock):
    try:
        price = stock.get("close", 0)
        market_cap = stock.get("market_cap", 0)
        volume = stock.get("vol", 0)
        change = stock.get("change", 0)
        if not (0 < price <= 5):
            return False
        if not (volume >= 2_000_000):
            return False
        if not (market_cap <= 3_207_060_000):
            return False
        if not (0 <= change <= 300):
            return False
        return True
    except Exception as e:
        print(f"\u274c خطأ في الفلترة: {e}")
        return False

def analyze_high_movement_stocks():
    print("\U0001f680 جاري تحليل الأسهم ذات الحركة العالية...")
    stocks = fetch_stocks_from_tradingview()
    high_movement = []

    for stock in stocks:
        try:
            symbol = stock["symbol"]
            vol = stock.get("vol", 0)
            market_cap = stock.get("market_cap", 0)
            change = stock.get("change", 0)
            price = stock.get("close", 0)

            if (vol > market_cap * 0.5 and change > 15 and price < 15 and vol > 5_000_000):
                high_movement.append(stock)

        except Exception as e:
            print(f"\u274c خطأ في تحليل سهم {stock.get('symbol')}: {e}")

    save_json(HIGH_MOVEMENT_FILE, high_movement[:5])
    save_daily_history(high_movement, "high_movement_stocks")

    print(f"\u2705 تم العثور على {len(high_movement)} سهم بحركة عالية.")
    print(f"\ud83d\udcc5 high_movement_stocks.json تم تحديثه في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return high_movement

async def analyze_high_movement_stocks_async():
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, analyze_high_movement_stocks)

def analyze_market():
    print("\U0001f4ca جاري تحليل السوق (مطابقة Webull)...")
    model = load_model()
    stocks = fetch_stocks_from_tradingview()

    top_stocks, pump_stocks = [], []

    for stock in stocks:
        try:
            symbol = stock["symbol"].upper()
            if not isinstance(stock["market_cap"], (int, float)) or stock["market_cap"] > 3_200_000_000:
                continue

            if not filter_top_stocks_by_custom_rules(stock):
                continue

            if had_recent_losses(symbol): continue
            if was_seen_recently(symbol): continue

            data = fetch_data_from_tradingview(symbol)
            if not data: continue

            is_green = data["close"] > data["open"]
            rsi_ok = data["RSI"] and data["RSI"] > 50
            macd_ok = data["MACD"] and data["MACD_signal"] and data["MACD"] > data["MACD_signal"]
            volume_ok = stock["vol"] > 1_000_000

            if not (is_green and rsi_ok and macd_ok and volume_ok):
                continue

            features = {
                "ma10": stock["close"],
                "ma30": stock["close"],
                "vol": stock["vol"],
                "avg_vol": stock["vol"],
                "change": stock["change"],
                "close": stock["close"]
            }

            score = predict_buy_signal(model, features)
            stock["score"] = score
            print(f"\U0001f50d {symbol} → Score: {score:.2f}%")

            if score >= 25:
                top_stocks.append(stock)

            if stock["change"] > 25 and stock["vol"] > stock["market_cap"]:
                pump_stocks.append(stock)

        except Exception as e:
            print(f"\u274c تحليل {stock.get('symbol', 'UNKNOWN')} فشل: {e}")

    top_stocks = sorted(top_stocks, key=lambda x: x["score"], reverse=True)[:3]
    pump_stocks = sorted(pump_stocks, key=lambda x: x["score"], reverse=True)[:3]

    save_json(TOP_STOCKS_FILE, top_stocks)
    save_json(PUMP_FILE, pump_stocks)

    save_daily_history(top_stocks, "top_stocks")
    save_daily_history(pump_stocks, "pump_stocks")

    print(f"\n\u2705 تحليل مكتمل: {len(top_stocks)} أقوى، {len(pump_stocks)} انفجار.")
    print(f"\ud83d\udcc5 top_stocks.json تم تحديثه في {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    return top_stocks + pump_stocks

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        try:
            json.dump(data, f, indent=2, ensure_ascii=False)
        except UnicodeEncodeError:
            print(f"⚠️ مشكلة في ترميز الرموز في {path}، سيتم الحفظ بدون رموز.")
            cleaned = json.loads(json.dumps(data))  # يعيد تحويل الرموز
            json.dump(cleaned, f, indent=2, ensure_ascii=True)


def convert_np(o):
    if isinstance(o, (np.integer, np.floating)):
        return o.item()
    raise TypeError

def save_daily_history(data, category):
    today = datetime.now().strftime("%Y-%m-%d")
    os.makedirs("history", exist_ok=True)
    filename = f"history/{category}_{today}.json"
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=convert_np)
        print(f"\ud83d\udcc5 تم حفظ {category} في {filename}")
    except Exception as e:
        print(f"\u274c فشل حفظ {category}: {e}")

def fetch_data_from_tradingview(symbol):
    try:
        payload = {
            "symbols": {"tickers": [f"NASDAQ:{symbol}"], "query": {"types": []}},
            "columns": [
                "close", "open", "volume", "change", "Recommend.All",
                "RSI", "MACD.macd", "MACD.signal", "Stoch.K", "Stoch.D"
            ]
        }
        response = requests.post(
            "https://scanner.tradingview.com/america/scan",
            headers=TRADINGVIEW_HEADERS,
            data=json.dumps(payload),
            timeout=10
        )
        result = response.json()
        if "data" not in result or not result["data"]:
            return None

        row = result["data"][0]["d"]
        return {
            "symbol": symbol,
            "close": row[0],
            "open": row[1],
            "vol": row[2],
            "change": row[3],
            "recommend": row[4],
            "RSI": row[5],
            "MACD": row[6],
            "MACD_signal": row[7],
            "Stoch_K": row[8],
            "Stoch_D": row[9]
        }
    except Exception as e:
        print(f"\u274c TradingView Error {symbol}: {e}")
        return None

def analyze_single_stock(symbol):
    print(f"\U0001f4ca تحليل سهم فردي: {symbol}")
    model = load_model()
    data = fetch_data_from_tradingview(symbol)

    if not data:
        print(f"\u274c لا يمكن تحليل {symbol}: لا توجد بيانات من TradingView")
        return None

    features = {
        "ma10": data["close"],
        "ma30": data["close"],
        "vol": data["vol"],
        "avg_vol": data["vol"],
        "change": data["change"],
        "close": data["close"]
    }

    score = predict_buy_signal(model, features)
    result = {
        "symbol": symbol,
        "score": score,
        "signal": "buy" if score >= 25 else "watch" if score >= 20 else "reject"
    }

    print(f"\u2705 {symbol} → Score: {score:.2f}% → {result['signal']}")
    return result
