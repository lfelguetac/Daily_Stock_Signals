import json
import os
import logging
import yfinance as yf
import requests
from datetime import datetime, timedelta

logger = logging.getLogger()
logger.setLevel(logging.INFO)

FINNHUB_API_KEY = os.environ["FINNHUB_API_KEY"]
SECTOR_PE = {
    "Technology": 30, "Healthcare": 25, "Financials": 15,
    "Energy": 12, "Industrials": 20, "Consumer Cyclical": 22,
    "Consumer Defensive": 20, "Real Estate": 35, "Utilities": 18,
    "Communication Services": 22, "Basic Materials": 15,
}

SEC_USER_AGENT = "DailyStockSignals/1.0 (lf.elgueta@gmail.com)"


def get_technical_data(ticker):
    stock = yf.Ticker(ticker)
    hist = stock.history(period="1y")

    if hist.empty:
        return None

    current_price = round(float(hist["Close"].iloc[-1]), 2)
    prev_close = round(float(hist["Close"].iloc[-2]), 2) if len(hist) > 1 else current_price
    change_pct = round((current_price - prev_close) / prev_close * 100, 2)

    close = hist["Close"]
    high_52w = round(float(hist["High"].max()), 2)
    low_52w = round(float(hist["Low"].min()), 2)
    drop_from_high = round((current_price - high_52w) / high_52w * 100, 2)

    sma_50 = round(float(close.rolling(50).mean().iloc[-1]), 2) if len(close) >= 50 else None
    sma_200 = round(float(close.rolling(200).mean().iloc[-1]), 2) if len(close) >= 200 else None

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
    rsi = round(100 - (100 / (1 + rs)), 2)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = round(float(ema_12.iloc[-1] - ema_26.iloc[-1]), 4)
    macd_signal = round(float(ema_12.ewm(span=9, adjust=False).mean().iloc[-1] - ema_26.ewm(span=9, adjust=False).mean().iloc[-1]), 4)

    momentum_20 = round((current_price / float(close.iloc[-20]) - 1) * 100, 2) if len(close) >= 20 else 0

    volume = int(hist["Volume"].iloc[-1])
    avg_volume = int(hist["Volume"].rolling(20).mean().iloc[-1])

    return {
        "ticker": ticker,
        "current_price": current_price,
        "prev_close": prev_close,
        "change_pct": change_pct,
        "high_52w": high_52w,
        "low_52w": low_52w,
        "drop_from_high": drop_from_high,
        "sma_50": sma_50,
        "sma_200": sma_200,
        "rsi": rsi,
        "macd": macd,
        "macd_signal": macd_signal,
        "momentum_20d": momentum_20,
        "volume": volume,
        "avg_volume": avg_volume,
        "close_history": [round(float(c), 2) for c in close.tolist()],
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def get_fundamentals(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info

    pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    revenue_growth = info.get("revenueGrowth")
    profit_margin = info.get("profitMargins")
    debt_to_equity = info.get("debtToEquity")
    current_ratio = info.get("currentRatio")
    sector = info.get("sector", "Unknown")
    market_cap = info.get("marketCap")
    eps = info.get("trailingEps")
    beta = info.get("beta")

    sector_pe = SECTOR_PE.get(sector, 20)

    return {
        "ticker": ticker,
        "pe": round(pe, 2) if pe else None,
        "forward_pe": round(forward_pe, 2) if forward_pe else None,
        "revenue_growth": round(revenue_growth, 4) if revenue_growth else None,
        "profit_margin": round(profit_margin, 4) if profit_margin else None,
        "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity else None,
        "current_ratio": round(current_ratio, 2) if current_ratio else None,
        "sector": sector,
        "sector_pe_avg": sector_pe,
        "market_cap": market_cap,
        "eps": round(eps, 2) if eps else None,
        "beta": round(beta, 2) if beta else None,
    }


def get_sentiment(ticker):
    try:
        today = datetime.utcnow().strftime("%Y-%m-%d")
        week_ago = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        url = f"https://finnhub.io/api/v1/company-news?symbol={ticker}&from={week_ago}&to={today}&token={FINNHUB_API_KEY}"
        resp = requests.get(url, timeout=10)

        if resp.status_code != 200:
            return {"ticker": ticker, "sentiment_score": 50, "news_count": 0, "error": f"HTTP {resp.status_code}"}

        news = resp.json()
        if not news:
            return {"ticker": ticker, "sentiment_score": 50, "news_count": 0}

        positive = sum(1 for n in news if n.get("sentiment") == "Positive")
        negative = sum(1 for n in news if n.get("sentiment") == "Negative")
        total = len(news)

        score = 50
        if total > 0:
            score = round(50 + (positive - negative) / total * 50, 2)
            score = max(0, min(100, score))

        headlines = [n.get("headline", "")[:80] for n in news[:3]]

        return {
            "ticker": ticker,
            "sentiment_score": score,
            "news_count": total,
            "positive": positive,
            "negative": negative,
            "recent_headlines": headlines,
        }
    except Exception as e:
        return {"ticker": ticker, "sentiment_score": 50, "news_count": 0, "error": str(e)}


def get_insider_activity(ticker):
    try:
        stock = yf.Ticker(ticker)
        insider = stock.insider_transactions

        if insider is None or insider.empty:
            return {"ticker": ticker, "insider_score": 50, "net_shares": 0, "recent_activity": "No data"}

        cutoff = datetime.utcnow() - timedelta(days=90)
        recent = insider[insider.index > cutoff]

        if recent.empty:
            return {"ticker": ticker, "insider_score": 50, "net_shares": 0, "recent_activity": "No recent activity"}

        buys = recent[recent["Shares"].str.contains("B", na=False)]["Shares"].str.replace("+", "").str.replace(",", "").astype(float).sum() if "Shares" in recent.columns else 0
        sells = recent[recent["Shares"].str.contains("S", na=False)]["Shares"].str.replace("-", "").str.replace(",", "").astype(float).sum() if "Shares" in recent.columns else 0

        net = buys - sells
        score = 50
        if buys + sells > 0:
            score = round(50 + (buys - sells) / (buys + sells) * 50, 2)
            score = max(0, min(100, score))

        return {
            "ticker": ticker,
            "insider_score": score,
            "net_shares": round(net, 0),
            "recent_activity": f"Buys: {int(buys)}, Sells: {int(sells)}",
        }
    except Exception as e:
        return {"ticker": ticker, "insider_score": 50, "net_shares": 0, "recent_activity": f"Error: {str(e)}"}


def handler(event, context):
    tickers = event.get("tickers", [])
    if not tickers:
        return {"error": "No tickers provided"}

    results = []
    for ticker in tickers:
        logger.info(f"Extracting data for {ticker}")
        try:
            tech = get_technical_data(ticker)
            if not tech:
                logger.warning(f"No data for {ticker}, skipping")
                continue

            fund = get_fundamentals(ticker)
            sent = get_sentiment(ticker)
            ins = get_insider_activity(ticker)

            results.append({
                "technical": tech,
                "fundamental": fund,
                "sentiment": sent,
                "insider": ins,
            })
        except Exception as e:
            logger.error(f"Error extracting {ticker}: {e}")
            results.append({"ticker": ticker, "error": str(e)})

    return {"data": results, "count": len(results)}
