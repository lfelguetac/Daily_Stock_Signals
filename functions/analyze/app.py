import json
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

WEIGHTS = {
    "technical": 0.30,
    "fundamental": 0.30,
    "sentiment": 0.20,
    "insider": 0.20,
}


def calc_composite(item):
    tech = item.get("technical_score", 50)
    fund = item.get("fundamental_score", 50)
    sent = item.get("sentiment_score", 50)
    ins = item.get("insider_score", 50)

    composite = round(
        tech * WEIGHTS["technical"]
        + fund * WEIGHTS["fundamental"]
        + sent * WEIGHTS["sentiment"]
        + ins * WEIGHTS["insider"],
        1,
    )
    return composite


def classify_signal(item, composite):
    rsi = item.get("rsi")
    momentum = item.get("momentum_20d", 0)
    pe = item.get("pe")
    sector_pe = item.get("sector_pe_avg", 20)
    rev_growth = item.get("revenue_growth")
    sentiment_score = item.get("sentiment_score", 50)
    news_count = item.get("news_count", 0)
    price = item.get("price", 0)
    sma_50 = item.get("sma_50")
    sma_200 = item.get("sma_200")
    macd = item.get("macd", 0)
    macd_signal = item.get("macd_signal", 0)
    volume_ratio = item.get("volume_ratio", 1.0)

    if (momentum > 5 and price and sma_50 and price > sma_50
            and macd > macd_signal and composite >= 60):
        return "Momentum Breakout"

    if (price and sma_50 and sma_200 and price > sma_50 > sma_200
            and momentum > 0 and composite >= 55):
        return "Trending Up"

    if (sentiment_score > 65 and news_count > 3 and volume_ratio > 1.2
            and composite >= 50):
        return "Narrative Hot"

    drop_from_high = item.get("drop_from_high", 0)
    if (pe and sector_pe and pe < sector_pe * 0.85
            and rev_growth and rev_growth > 0
            and drop_from_high < -10
            and composite >= 45):
        return "Value Play"

    if rsi and rsi < 30 and composite >= 40:
        return "Oversold Bounce"

    if (pe and sector_pe and pe > sector_pe * 1.3
            and rev_growth is not None and rev_growth < 0
            and sentiment_score < 40):
        return "Avoid"

    return "Wait"


def calc_entry_price(item):
    price = item.get("price", 0)
    sma_50 = item.get("sma_50")
    sma_200 = item.get("sma_200")
    low_20d = item.get("low_20d")

    supports = []
    if sma_50 and sma_50 < price:
        supports.append(sma_50)
    if sma_200 and sma_200 < price:
        supports.append(sma_200)
    if low_20d and low_20d < price:
        supports.append(low_20d)

    if supports:
        return round(max(supports) * 1.01, 2)

    return round(price * 0.97, 2)


def determine_trend(item):
    price = item.get("price", 0)
    sma_50 = item.get("sma_50")
    sma_200 = item.get("sma_200")
    momentum = item.get("momentum_20d", 0)

    if price and sma_50 and sma_200:
        if price > sma_50 > sma_200 and momentum > 0:
            return "uptrend"
        elif price < sma_50 < sma_200 and momentum < 0:
            return "downtrend"
    return "sideways"


def build_reasons(item):
    all_reasons = []
    all_reasons.extend(item.get("technical_reasons", []))
    all_reasons.extend(item.get("fundamental_reasons", []))
    all_reasons.extend(item.get("sentiment_reasons", []))
    all_reasons.extend(item.get("insider_reasons", []))
    return all_reasons[:6]


def handler(event, context):
    scores = event.get("scores", [])
    date = datetime.utcnow().strftime("%Y-%m-%d")
    results = []

    for item in scores:
        if "error" in item:
            results.append({"ticker": item.get("ticker", "unknown"), "error": item["error"]})
            continue

        composite = calc_composite(item)
        signal_category = classify_signal(item, composite)
        trend = determine_trend(item)
        entry_price = calc_entry_price(item)
        reasons = build_reasons(item)

        results.append({
            "ticker": item.get("ticker"),
            "composite_score": composite,
            "signal_category": signal_category,
            "trend": trend,
            "entry_price": entry_price,
            "reasons": reasons,
            "technical_score": item.get("technical_score"),
            "fundamental_score": item.get("fundamental_score"),
            "sentiment_score": item.get("sentiment_score"),
            "insider_score": item.get("insider_score"),
            "price": item.get("price"),
            "change_pct": item.get("change_pct"),
            "sector": item.get("sector"),
            "market_cap": item.get("market_cap"),
            "rsi": item.get("rsi"),
            "volume_ratio": item.get("volume_ratio"),
            "sma_50": item.get("sma_50"),
            "sma_200": item.get("sma_200"),
            "macd": item.get("macd"),
            "macd_signal": item.get("macd_signal"),
            "momentum_20d": item.get("momentum_20d"),
            "pe": item.get("pe"),
            "sector_pe_avg": item.get("sector_pe_avg"),
            "revenue_growth": item.get("revenue_growth"),
            "drop_from_high": item.get("drop_from_high"),
            "date": date,
        })

    return {"signals": results, "count": len(results), "date": date}
