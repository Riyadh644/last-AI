import os
import json
import logging
import asyncio
import schedule
import yfinance as yf
import requests
import nest_asyncio
from datetime import datetime

from telegram import Bot
from modules.analyze_performance import generate_report_summary
from modules.tv_data import (
    analyze_market, analyze_single_stock, 
    fetch_stocks_from_tradingview, analyze_high_movement_stocks
)
from modules.ml_model import train_model_daily
from modules.symbols_updater import fetch_all_us_symbols, save_symbols_to_csv
from modules.telegram_bot import (
    start_telegram_bot,
    compare_stock_lists_and_alert,
    send_performance_report,
    send_telegram_message
)
from modules.pump_detector import detect_pump_stocks
from modules.price_tracker import check_targets

# تفعيل دعم التزامن داخل التزامن
nest_asyncio.apply()

# إعدادات عامة
NEWS_API_KEY = "BpXXFMPQ3JdCinpg81kfn4ohvmnhGZOwEmHjLIre"
POSITIVE_NEWS_FILE = "data/positive_watchlist.json"
BOT_TOKEN = "7740179871:AAFYnS_QS595Gw5uRTMuW8N9ajUB4pK4tJ0"

# إنشاء مجلد السجلات إن لم يكن موجوداً
os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename="logs/bot.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def log(msg):
    print(msg)
    logging.info(msg)

def fetch_news_sentiment(symbol):
    try:
        url = f"https://api.marketaux.com/v1/news/all?symbols={symbol}&filter_entities=true&language=en&api_token={NEWS_API_KEY}"
        response = requests.get(url)
        if response.status_code == 200:
            articles = response.json().get("data", [])
            for article in articles:
                title = article.get("title", "").lower()
                if "bankruptcy" in title or "dilution" in title:
                    return "negative"
                if "record revenue" in title or "strong earnings" in title:
                    return "positive"
        return "neutral"
    except Exception as e:
        log(f"❌ خطأ في تحليل الأخبار لـ {symbol}: {e}")
        return "neutral"

def watch_positive_news_stocks():
    log("🟢 فحص الأسهم ذات الأخبار الإيجابية...")
    try:
        stocks = fetch_stocks_from_tradingview()
        positive_stocks = []

        old_symbols = []
        if os.path.exists(POSITIVE_NEWS_FILE):
            with open(POSITIVE_NEWS_FILE, "r", encoding="utf-8") as f:
                old_list = json.load(f)
            old_symbols = [s["symbol"] for s in old_list]

        for stock in stocks:
            symbol = stock["symbol"]
            sentiment = fetch_news_sentiment(symbol)
            if sentiment == "positive" and symbol not in old_symbols:
                message = f"📢 سهم جديد بأخبار إيجابية:\n📈 {symbol}\n✅ تم رصده في السوق"
                send_telegram_message(message)
                log(f"✅ {symbol} لديه أخبار إيجابية.")
                positive_stocks.append(stock)

        if positive_stocks:
            os.makedirs(os.path.dirname(POSITIVE_NEWS_FILE), exist_ok=True)
            with open(POSITIVE_NEWS_FILE, "w", encoding="utf-8") as f:
                json.dump(positive_stocks, f, indent=2, ensure_ascii=False)
            log(f"✅ تم حفظ {len(positive_stocks)} سهم في قائمة الأخبار الإيجابية.")
        else:
            log("⚠️ لا توجد أسهم إيجابية حالياً.")
    except Exception as e:
        log(f"❌ فشل في مراقبة الأخبار الإيجابية: {e}")

def is_market_weak():
    try:
        spy = yf.Ticker("SPY")
        hist = spy.history(period="2d")
        if len(hist) >= 2:
            prev_close = hist["Close"].iloc[-2]
            today_close = hist["Close"].iloc[-1]
            change_pct = (today_close - prev_close) / prev_close * 100
            return change_pct < -1
    except Exception as e:
        log(f"❌ خطأ في تحليل SPY: {e}")
    return False

def daily_model_training():
    log("🔁 تدريب يومي للنموذج الذكي...")
    train_model_daily()

def update_market_data():
    log("📊 تحديث بيانات السوق...")
    try:
        if is_market_weak():
            log("⚠️ السوق ضعيف (SPY < -1%). تم إلغاء التوصيات.")
            return
        stocks = analyze_market()
        final_stocks = []
        for stock in stocks:
            sentiment = fetch_news_sentiment(stock["symbol"])
            if sentiment != "negative":
                final_stocks.append(stock)
            else:
                log(f"⚠️ تم تجاهل {stock['symbol']} بسبب أخبار سلبية.")
        log(f"✅ تحليل مكتمل: {len(final_stocks)} سهم بعد فلترة الأخبار.")
    except Exception as e:
        log(f"❌ فشل تحليل السوق: {e}")

def update_symbols():
    log("🔁 تحديث رموز السوق من NASDAQ الرسمي...")
    try:
        symbols = fetch_all_us_symbols()
        if symbols:
            save_symbols_to_csv(symbols)
            log(f"✅ تم تحديث {len(symbols)} رمز سوق.")
    except Exception as e:
        log(f"❌ فشل في تحديث الرموز: {e}")

def update_pump_stocks():
    log("💣 تحليل الانفجارات السعرية...")
    try:
        detect_pump_stocks()
        log("✅ تم تحديث أسهم الانفجار السعرية.")
    except Exception as e:
        log(f"❌ فشل تحليل الانفجارات: {e}")

def update_high_movement_stocks():
    log("🚀 تحليل الأسهم ذات الحركة العالية...")
    try:
        analyze_high_movement_stocks()
        log("✅ تم تحديث أسهم الحركة العالية.")
    except Exception as e:
        log(f"❌ فشل تحليل الأسهم ذات الحركة العالية: {e}")

async def track_targets(bot):
    log("🎯 متابعة لحظية للأسهم...")
    try:
        await check_targets(bot)
    except Exception as e:
        log(f"❌ خطأ في متابعة الأهداف: {e}")

async def run_smart_alerts(bot):
    log("🔔 فحص التغيرات في الأسهم...")
    try:
        await compare_stock_lists_and_alert(bot)
    except Exception as e:
        log(f"❌ فشل إرسال التنبيهات الذكية: {e}")

async def send_daily_report():
    log("📊 إرسال التقرير اليومي...")
    try:
        await send_performance_report()
    except Exception as e:
        log(f"❌ فشل إرسال التقرير اليومي: {e}")

async def run_scheduled_jobs(bot):
    while True:
        schedule.run_pending()
        await asyncio.sleep(1)

async def main():
    bot_instance = Bot(token=BOT_TOKEN)

    # جدولة المهام
    daily_model_training()
    update_market_data()
    update_pump_stocks()
    update_high_movement_stocks()

    schedule.every().day.at("00:00").do(daily_model_training)
    schedule.every().day.at("03:00").do(update_symbols)
    schedule.every(5).minutes.do(update_market_data)
    schedule.every(5).minutes.do(update_pump_stocks)
    schedule.every(5).minutes.do(update_high_movement_stocks)
    schedule.every(5).minutes.do(lambda: asyncio.create_task(track_targets(bot_instance)))
    schedule.every(5).minutes.do(lambda: asyncio.create_task(run_smart_alerts(bot_instance)))
    schedule.every(10).minutes.do(watch_positive_news_stocks)
    schedule.every().day.at("16:00").do(lambda: asyncio.create_task(send_daily_report()))

    # ✅ هنا التصحيح: انتظر البوت + الجدولة معاً بشكل نظيف
    await asyncio.gather(
        start_telegram_bot(),
        run_scheduled_jobs(bot_instance)
    )

if __name__ == "__main__":
    asyncio.run(main())
