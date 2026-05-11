import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def calc_technical_score(tech):
    score = 50
    reasons = []

    rsi = tech.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 20
            reasons.append(f"RSI {rsi} (oversold)")
        elif rsi < 40:
            score += 10
            reasons.append(f"RSI {rsi} (approaching oversold)")
        elif rsi > 70:
            score -= 20
            reasons.append(f"RSI {rsi} (overbought)")
        elif rsi > 60:
            score -= 10
            reasons.append(f"RSI {rsi} (approaching overbought)")
        else:
            reasons.append(f"RSI {rsi} (neutral)")

    sma_50 = tech.get("sma_50")
    sma_200 = tech.get("sma_200")
    price = tech.get("current_price")
    if sma_50 and price:
        if price > sma_50:
            score += 10
            reasons.append(f"Above SMA50 ({sma_50})")
        else:
            score -= 10
            reasons.append(f"Below SMA50 ({sma_50})")

    if sma_200 and price:
        if price > sma_200:
            score += 10
            reasons.append(f"Above SMA200 ({sma_200})")
        else:
            score -= 10
            reasons.append(f"Below SMA200 ({sma_200})")

    momentum = tech.get("momentum_20d", 0)
    if momentum > 5:
        score += 10
        reasons.append(f"Momentum +{momentum}%")
    elif momentum < -5:
        score -= 10
        reasons.append(f"Momentum {momentum}%")

    macd = tech.get("macd", 0)
    macd_signal = tech.get("macd_signal", 0)
    if macd > macd_signal:
        score += 5
        reasons.append("MACD bullish")
    elif macd < macd_signal:
        score -= 5
        reasons.append("MACD bearish")

    return max(0, min(100, round(score, 1))), reasons


def calc_fundamental_score(fund):
    score = 50
    reasons = []

    pe = fund.get("pe")
    sector_pe = fund.get("sector_pe_avg", 20)
    if pe and sector_pe:
        if pe < sector_pe * 0.7:
            score += 20
            reasons.append(f"P/E {pe} vs sector {sector_pe} (undervalued)")
        elif pe < sector_pe:
            score += 10
            reasons.append(f"P/E {pe} below sector avg {sector_pe}")
        elif pe > sector_pe * 1.5:
            score -= 15
            reasons.append(f"P/E {pe} vs sector {sector_pe} (overvalued)")
        elif pe > sector_pe:
            score -= 5
            reasons.append(f"P/E {pe} above sector avg {sector_pe}")

    rev_growth = fund.get("revenue_growth")
    if rev_growth is not None:
        if rev_growth > 0.20:
            score += 20
            reasons.append(f"Revenue growth +{rev_growth*100:.0f}%")
        elif rev_growth > 0.10:
            score += 10
            reasons.append(f"Revenue growth +{rev_growth*100:.0f}%")
        elif rev_growth < 0:
            score -= 15
            reasons.append(f"Revenue declining {rev_growth*100:.0f}%")

    margin = fund.get("profit_margin")
    if margin is not None:
        if margin > 0.20:
            score += 10
            reasons.append(f"Strong margins {margin*100:.0f}%")
        elif margin < 0:
            score -= 10
            reasons.append("Negative margins")

    de = fund.get("debt_to_equity")
    if de is not None:
        if de < 0.5:
            score += 5
            reasons.append(f"Low debt (D/E {de})")
        elif de > 2.0:
            score -= 10
            reasons.append(f"High debt (D/E {de})")

    cr = fund.get("current_ratio")
    if cr is not None:
        if cr > 1.5:
            score += 5
            reasons.append(f"Strong liquidity (CR {cr})")
        elif cr < 1.0:
            score -= 5
            reasons.append(f"Weak liquidity (CR {cr})")

    return max(0, min(100, round(score, 1))), reasons


def calc_sentiment_score(sentiment):
    score = sentiment.get("sentiment_score", 50)
    reasons = []
    news_count = sentiment.get("news_count", 0)

    if news_count == 0:
        reasons.append("No recent news")
    else:
        positive = sentiment.get("positive", 0)
        negative = sentiment.get("negative", 0)
        reasons.append(f"{news_count} news: {positive} pos, {negative} neg")

    return round(score, 1), reasons


def calc_insider_score(insider):
    score = insider.get("insider_score", 50)
    reasons = []
    activity = insider.get("recent_activity", "")
    reasons.append(activity)

    return round(score, 1), reasons


def handler(event, context):
    data = event.get("data", [])
    results = []

    for item in data:
        if "error" in item:
            results.append({"ticker": item.get("ticker", "unknown"), "error": item["error"]})
            continue

        tech = item.get("technical", {})
        fund = item.get("fundamental", {})
        sent = item.get("sentiment", {})
        ins = item.get("insider", {})

        tech_score, tech_reasons = calc_technical_score(tech)
        fund_score, fund_reasons = calc_fundamental_score(fund)
        sent_score, sent_reasons = calc_sentiment_score(sent)
        ins_score, ins_reasons = calc_insider_score(ins)

        volume = tech.get("volume", 0)
        avg_volume = tech.get("avg_volume", 1)
        volume_ratio = round(volume / avg_volume, 2) if avg_volume > 0 else 1.0

        close = tech.get("close_history", [])
        low_20d = min(close[-20:]) if len(close) >= 20 else None

        results.append({
            "ticker": tech.get("ticker"),
            "technical_score": tech_score,
            "fundamental_score": fund_score,
            "sentiment_score": sent_score,
            "insider_score": ins_score,
            "technical_reasons": tech_reasons,
            "fundamental_reasons": fund_reasons,
            "sentiment_reasons": sent_reasons,
            "insider_reasons": ins_reasons,
            "price": tech.get("current_price"),
            "change_pct": tech.get("change_pct"),
            "sector": fund.get("sector"),
            "market_cap": fund.get("market_cap"),
            "rsi": tech.get("rsi"),
            "volume_ratio": volume_ratio,
            "sma_50": tech.get("sma_50"),
            "sma_200": tech.get("sma_200"),
            "macd": tech.get("macd"),
            "macd_signal": tech.get("macd_signal"),
            "momentum_20d": tech.get("momentum_20d"),
            "pe": fund.get("pe"),
            "sector_pe_avg": fund.get("sector_pe_avg"),
            "revenue_growth": fund.get("revenue_growth"),
            "drop_from_high": tech.get("drop_from_high"),
            "news_count": sent.get("news_count", 0),
            "low_20d": low_20d,
        })

    return {"scores": results, "count": len(results)}
