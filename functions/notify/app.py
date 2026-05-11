import boto3
import json
import os
import logging
import base64
import requests
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses = boto3.client("ses", region_name="us-east-1")
SENDER_EMAIL = os.environ.get("SENDER_EMAIL", "lf.elgueta@gmail.com")
RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "lf.elgueta@gmail.com")
GITHUB_PAT = os.environ.get("GITHUB_PAT", "")
GITHUB_REPO = "lfelguetac/Daily_Stock_Signals"

SIGNAL_COLORS = {
    "Momentum Breakout": "#10b981",
    "Value Play": "#3b82f6",
    "Narrative Hot": "#8b5cf6",
    "Oversold Bounce": "#f59e0b",
    "Avoid": "#ef4444",
    "Trending Up": "#06b6d4",
    "Wait": "#6b7280",
}

SIGNAL_ORDER = [
    "Momentum Breakout",
    "Trending Up",
    "Narrative Hot",
    "Value Play",
    "Oversold Bounce",
    "Wait",
    "Avoid",
]

GLOSSARY = """
<div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:10px;padding:16px;margin-top:24px;">
<h3 style="margin:0 0 12px;color:#0c4a6e;font-size:15px;">Como leer este reporte</h3>

<div style="margin-bottom:14px;">
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">El Score Compuesto (0-100)</div>
<div style="font-size:12px;color:#475569;line-height:1.5;">Es una nota que resume todo: 30% analisis tecnico (patrones de precio), 30% fundamentals (salud de la empresa), 20% sentimiento (que dicen las noticias), y 20% insider (que hacen los ejecutivos de la empresa con sus propias acciones).</div>
<div style="display:flex;gap:8px;margin-top:6px;flex-wrap:wrap;">
<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#ef444422;color:#ef4444;">0-35 Vender</span>
<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#f59e0b22;color:#f59e0b;">36-49 Esperar</span>
<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#3b82f622;color:#3b82f6;">50-69 Neutral</span>
<span style="font-size:11px;padding:2px 8px;border-radius:4px;background:#10b98122;color:#10b981;">70-100 Comprar</span>
</div>
</div>

<div style="margin-bottom:14px;">
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">RSI (0-100)</div>
<div style="font-size:12px;color:#475569;line-height:1.5;">Mide que tan rapido y fuerte se mueve el precio. Piensalo asi: si corres muy rapido, eventualmente necesitas parar a descansar. Si el RSI esta muy alto (&gt;70), el precio "corrio mucho" y puede caer. Si esta muy bajo (&lt;30), "descanso mucho" y puede subir.</div>
</div>

<div style="margin-bottom:14px;">
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">Tendencia</div>
<div style="font-size:12px;color:#475569;line-height:1.5;">Indica la direccion general del precio. <b>Alcista</b> = subiendo (bueno para comprar), <b>Bajista</b> = cayendo (cuidado), <b>Lateral</b> = sin direccion clara (esperar). Se calcula comparando el precio actual con sus promedios de 50 y 200 dias.</div>
</div>

<div style="margin-bottom:14px;">
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">Volumen Relativo</div>
<div style="font-size:12px;color:#475569;line-height:1.5;">Compara cuantas acciones se negociaron hoy vs el promedio de los ultimos 20 dias. <b>&gt;1.5x</b> = mucho interes (la tendencia es confiable), <b>0.8-1.5x</b> = normal, <b>&lt;0.8x</b> = poco interes (desconfia del movimiento).</div>
</div>

<div style="margin-bottom:14px;">
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">Precio de Entrada Sugerido</div>
<div style="font-size:12px;color:#475569;line-height:1.5;">No es una recomendacion de compra exacta. Es un precio cercano a "soportes" (niveles donde historicamente el precio dejo de caer). Comprar cerca de soportes reduce tu riesgo porque si el precio cae, sabes donde poner tu limite de perdida.</div>
</div>

<div>
<div style="font-size:13px;font-weight:700;color:#0c4a6e;margin-bottom:6px;">Categorias de Senal</div>
<div style="font-size:12px;color:#475569;line-height:1.6;">
&#128640; <b>Momentum Breakout</b> — Rompiendo hacia arriba con fuerza<br>
&#128200; <b>Trending Up</b> — Tendencia alcista estable<br>
&#128293; <b>Narrative Hot</b> — Muy mencionada en noticias<br>
&#128142; <b>Value Play</b> — Barata respecto a su valor real<br>
&#128260; <b>Oversold Bounce</b> — Cayo demasiado, posible rebote<br>
&#9203; <b>Wait</b> — Sin senal clara, esperar<br>
&#9888;&#65039; <b>Avoid</b> — Mejor evitar por ahora
</div>
</div>
</div>
"""


def rsi_explanation(rsi):
    if rsi is None:
        return None
    rsi = round(rsi, 1)
    if rsi < 30:
        return {
            "label": "Sobrevendido",
            "color": "#f59e0b",
            "meaning": "La accion cayo mucho y muy rapido. Historicamente, cuando el RSI esta tan bajo, el precio suele rebotar. Puede ser buena oportunidad de compra, pero verifica que la empresa este bien.",
            "icon": "🔵",
        }
    elif rsi < 45:
        return {
            "label": "Zona baja",
            "color": "#3b82f6",
            "meaning": "El precio esta relativamente bajo comparado con sus ultimos dias. No esta tan extremo como para ser sobrevendido, pero muestra debilidad. Podria ser punto de entrada si los fundamentals son buenos.",
            "icon": "🔵",
        }
    elif rsi < 55:
        return {
            "label": "Neutral",
            "color": "#6b7280",
            "meaning": "El precio no esta ni muy alto ni muy bajo respecto a su comportamiento reciente. No hay senal clara de compra ni venta por este indicador. Fijate en los otros datos.",
            "icon": "⚪",
        }
    elif rsi < 70:
        return {
            "label": "Zona alta",
            "color": "#10b981",
            "meaning": "El precio subio con fuerza en los ultimos dias. Es senal de fortaleza, pero si sigue subiendo puede acercarse a zona de sobrecompra (riesgo de correccion).",
            "icon": "🟢",
        }
    else:
        return {
            "label": "Sobrecomprado",
            "color": "#ef4444",
            "meaning": "La accion subio mucho y muy rapido. Es probable que venga una correccion o pausa. Si ya tienes acciones, considera tomar ganancias. No es buen momento para comprar.",
            "icon": "🔴",
        }


def rsi_display(rsi):
    if rsi is None:
        return '<span style="color:#94a3b8;">Sin datos</span>'
    rsi_rounded = round(rsi, 1)
    info = rsi_explanation(rsi_rounded)
    return (
        f'<div style="margin-bottom:4px;">'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
        f'<div style="flex:1;height:8px;background:#e2e8f0;border-radius:4px;overflow:hidden;">'
        f'<div style="width:{rsi_rounded}%;height:100%;background:{info["color"]};border-radius:4px;"></div></div>'
        f'<span style="font-size:13px;font-weight:700;color:{info["color"]};min-width:40px;">{rsi_rounded}</span>'
        f'<span style="font-size:11px;color:{info["color"]};font-weight:600;">{info["label"]}</span></div>'
        f'<div style="font-size:11px;color:#64748b;line-height:1.4;padding-left:2px;">{info["meaning"]}</div>'
        f'</div>'
    )


def trend_explanation(trend):
    if trend == "uptrend":
        return {
            "label": "Alcista",
            "color": "#10b981",
            "meaning": "El precio esta subiendo de forma consistente: esta por encima de sus promedios de 50 y 200 dias. Es la situacion ideal para mantener o comprar.",
            "arrow": "↑",
        }
    elif trend == "downtrend":
        return {
            "label": "Bajista",
            "color": "#ef4444",
            "meaning": "El precio esta cayendo de forma consistente: esta por debajo de sus promedios de 50 y 200 dias. Precaucion, no es buen momento para comprar.",
            "arrow": "↓",
        }
    return {
        "label": "Lateral",
        "color": "#6b7280",
        "meaning": "El precio no tiene direccion clara, se mueve de lado. El mercado esta indeciso sobre esta accion. Espera una senal mas clara antes de actuar.",
        "arrow": "→",
    }


def trend_display(trend):
    info = trend_explanation(trend)
    return (
        f'<div style="margin-bottom:4px;">'
        f'<div style="font-size:13px;font-weight:700;color:{info["color"]};margin-bottom:4px;">'
        f'{info["arrow"]} {info["label"]}</div>'
        f'<div style="font-size:11px;color:#64748b;line-height:1.4;">{info["meaning"]}</div>'
        f'</div>'
    )


def volume_display(vol_ratio):
    if vol_ratio is None:
        return '<span style="color:#94a3b8;">Sin datos</span>'
    vol = round(vol_ratio, 1)
    if vol > 1.5:
        color = "#10b981"
        label = "Alto"
        meaning = f"Se esta negociando {vol}x mas que lo normal. Cuando el volumen es alto, confirma que la tendencia es real (hay mucho interes). Si el precio sube con volumen alto, es buena senal."
    elif vol > 0.8:
        color = "#6b7280"
        label = "Normal"
        meaning = f"Volumen habitual ({vol}x del promedio). No hay nada excepcional. La tendencia actual tiene apoyo moderado."
    else:
        color = "#f59e0b"
        label = "Bajo"
        meaning = f"Se esta negociando poco ({vol}x del promedio). Cuando el volumen es bajo, la tendencia es debil y puede revertirse facilmente. Desconfia de movimientos con volumen bajo."
    return (
        f'<div style="margin-bottom:4px;">'
        f'<div style="font-size:13px;font-weight:700;color:{color};margin-bottom:4px;">{vol}x — {label}</div>'
        f'<div style="font-size:11px;color:#64748b;line-height:1.4;">{meaning}</div>'
        f'</div>'
    )


def score_display(score):
    score = round(score, 1)
    if score < 35:
        color = "#ef4444"
        label = "Muy bajo"
        meaning = "Casi todo apunta a venta:技术分析, fundamentals, sentimiento e insiders son negativos. Mejor evitar esta accion por ahora."
    elif score < 50:
        color = "#f59e0b"
        label = "Bajo"
        meaning = "La mayoria de los indicadores son debiles o negativos. No es buen momento para comprar, pero tampoco necesariamente para vender si ya la tienes."
    elif score < 65:
        color = "#3b82f6"
        label = "Moderado"
        meaning = "Indicadores mixtos: algunos positivos, otros negativos. La accion no tiene una direccion clara. Espera mas senales antes de actuar."
    elif score < 80:
        color = "#10b981"
        label = "Alto"
        meaning = "La mayoria de los indicadores son positivos. Es una accion con buena pinta para comprar o mantener. Revisa la entrada sugerida."
    else:
        color = "#059669"
        label = "Muy alto"
        meaning = "Casi todo apunta a compra:技术分析, fundamentals, sentimiento e insiders son positivos. Es de las mejores oportunidades del dia."
    return (
        f'<div style="margin-bottom:4px;">'
        f'<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
        f'<div style="flex:1;height:10px;background:#e2e8f0;border-radius:5px;overflow:hidden;">'
        f'<div style="width:{score}%;height:100%;background:{color};border-radius:5px;"></div></div>'
        f'<span style="font-size:15px;font-weight:700;color:{color};min-width:40px;">{score}</span>'
        f'<span style="font-size:11px;color:{color};font-weight:600;">{label}</span></div>'
        f'<div style="font-size:11px;color:#64748b;line-height:1.4;padding-left:2px;">{meaning}</div>'
        f'</div>'
    )


def signal_badge(category):
    color = SIGNAL_COLORS.get(category, "#6b7280")
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:12px;'
        f'background:{color}22;color:{color};font-size:12px;font-weight:600;'
        f'border:1px solid {color}44;">{category}</span>'
    )


def signal_explanation(category):
    explanations = {
        "Momentum Breakout": {
            "emoji": "🚀",
            "what": "La accion esta rompiendo hacia arriba con fuerza",
            "why": "El precio subio mas del 5% en 20 dias, esta por encima de su promedio de 50 dias, y el MACD (indicador de momentum) es positivo. Todo confirma que hay impulso alcista.",
            "action": "Si quieres comprar, usa el precio de entrada sugerido. Pon un stop loss por debajo del SMA50.",
        },
        "Trending Up": {
            "emoji": "📈",
            "what": "La accion esta en tendencia alcista estable",
            "why": "El precio esta por encima de sus promedios de 50 y 200 dias, y sigue subiendo. Es la configuracion mas saludable para una accion.",
            "action": "Buen momento para comprar o mantener. No necesitas apurarte, la tendencia te da tiempo.",
        },
        "Narrative Hot": {
            "emoji": "🔥",
            "what": "Todos estan hablando de esta accion",
            "why": "Hay muchas noticias positivas y el volumen de operaciones esta por encima del normal. El mercado esta prestando atencion.",
            "action": "Puede ser buena oportunidad, pero cuidado con entrar tarde. Verifica que los fundamentals respalden el hype.",
        },
        "Value Play": {
            "emoji": "💎",
            "what": "Accion barata respecto a su valor real",
            "why": "Cayo mas del 10% desde su maximo, su P/E es menor al promedio del sector, y sigue creciendo en ingresos. El mercado la esta castigando de mas.",
            "action": "Oportunidad para inversores pacientes. Puede tardar en recuperarse, pero los fundamentals son solidos.",
        },
        "Oversold Bounce": {
            "emoji": "🔄",
            "what": "Cayo demasiado, podria rebotar",
            "why": "El RSI esta por debajo de 30, lo que significa que vendieron de mas. Historicamente, estas acciones suelen tener un rebote tecnico.",
            "action": "Puede ser buena entrada rapida, pero es arriesgado. Espera confirmacion de que el precio deja de caer.",
        },
        "Wait": {
            "emoji": "⏳",
            "what": "No hay senal clara ahora",
            "why": "Los indicadores estan mixtos: algunos positivos, otros negativos. El mercado no sabe para donde ir.",
            "action": "No hagas nada con esta accion hoy. Espera a que se defina una direccion mas clara.",
        },
        "Avoid": {
            "emoji": "⚠️",
            "what": "Mejor mantenerse alejado",
            "why": "La accion esta cara para su sector, los ingresos estan cayendo, y el sentimiento de noticias es negativo. Todo apunta a que puede seguir bajando.",
            "action": "Si no la tienes, no la compres. Si la tienes y estas en perdida, considera si quieres seguir esperando.",
        },
    }
    return explanations.get(category, explanations["Wait"])


def build_stock_card(s):
    ticker = s.get("ticker", "?")
    price = s.get("price", 0)
    change = s.get("change_pct", 0)
    score = s.get("composite_score", 0)
    category = s.get("signal_category", "Wait")
    trend = s.get("trend", "sideways")
    rsi = s.get("rsi")
    vol_ratio = s.get("volume_ratio")
    entry = s.get("entry_price")
    sector = s.get("sector", "")
    reasons = s.get("reasons", [])[:3]

    change_color = "#10b981" if change >= 0 else "#ef4444"
    change_sign = "+" if change >= 0 else ""
    border_color = SIGNAL_COLORS.get(category, "#6b7280")

    signal_info = signal_explanation(category)

    sector_html = f'<div style="font-size:11px;color:#94a3b8;margin-top:2px;">Sector: {sector}</div>' if sector else ""

    entry_html = ""
    if entry and entry > 0:
        diff = round(((entry - price) / price) * 100, 1)
        diff_sign = "-" if diff < 0 else "+"
        entry_html = f"""
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:10px;margin-top:12px;">
        <div style="font-size:11px;color:#166534;font-weight:600;margin-bottom:4px;">💡 PRECIO DE ENTRADA SUGERIDO</div>
        <div style="font-size:18px;font-weight:700;color:#10b981;">${entry:.2f}</div>
        <div style="font-size:11px;color:#15803d;margin-top:2px;">{diff_sign}{diff}% vs precio actual (${price:.2f})</div>
        <div style="font-size:10px;color:#64748b;margin-top:4px;">Es un precio cercano a soportes tecnicos (SMA50, SMA200 o minimo reciente). Comprar cerca de soportes reduce el riesgo.</div>
        </div>"""

    indicators_html = f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px;">
    <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:600;">Score Compuesto</div>{score_display(score)}</div>
    <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:600;">RSI (fuerza del precio)</div>{rsi_display(rsi)}</div>
    <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:600;">Tendencia</div>{trend_display(trend)}</div>
    <div><div style="font-size:10px;color:#94a3b8;text-transform:uppercase;margin-bottom:6px;font-weight:600;">Volumen Relativo</div>{volume_display(vol_ratio)}</div>
    </div>"""

    reasons_html = ""
    if reasons:
        reasons_html = f"""
        <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:10px;margin-top:12px;">
        <div style="font-size:11px;color:#475569;font-weight:600;margin-bottom:6px;">Por que esta senal:</div>
        {''.join(f'<div style="font-size:11px;color:#64748b;line-height:1.5;margin-bottom:3px;">&#8226; {r}</div>' for r in reasons)}
        </div>"""

    return f"""
<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:14px;border-left:4px solid {border_color};box-shadow:0 1px 3px rgba(0,0,0,0.04);">
<div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px;">
<div>
<div style="display:flex;align-items:center;gap:8px;">
<span style="font-size:20px;font-weight:700;color:#0f172a;">{ticker}</span>
{signal_badge(category)}
</div>
{sector_html}
</div>
<div style="text-align:right;">
<div style="font-size:22px;font-weight:700;color:#0f172a;">${price:.2f}</div>
<div style="font-size:14px;font-weight:600;color:{change_color};">{change_sign}{change:.1f}% hoy</div>
</div>
</div>

<div style="background:{border_color}08;border:1px solid {border_color}22;border-radius:8px;padding:12px;margin-top:14px;">
<div style="font-size:13px;font-weight:700;color:#0f172a;margin-bottom:4px;">{signal_info["emoji"]} {signal_info["what"]}</div>
<div style="font-size:11px;color:#475569;line-height:1.5;margin-bottom:6px;"><b>Por que:</b> {signal_info["why"]}</div>
<div style="font-size:11px;color:#475569;line-height:1.5;"><b>Que hacer:</b> {signal_info["action"]}</div>
</div>

{indicators_html}
{entry_html}
{reasons_html}
</div>
"""


def format_email(signals, date):
    categories = {}
    for s in signals:
        cat = s.get("signal_category", "Wait")
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(s)

    for cat in categories:
        categories[cat].sort(key=lambda x: x.get("composite_score", 0), reverse=True)

    total = len(signals)
    bullish = sum(1 for s in signals if s.get("signal_category") in ["Momentum Breakout", "Trending Up", "Narrative Hot"])
    bearish = sum(1 for s in signals if s.get("signal_category") == "Avoid")

    cards_html = ""
    for cat in SIGNAL_ORDER:
        stocks = categories.get(cat, [])
        if not stocks:
            continue
        color = SIGNAL_COLORS.get(cat, "#6b7280")
        cards_html += f'<h2 style="font-size:16px;color:{color};margin:20px 0 10px;padding-bottom:6px;border-bottom:2px solid {color}44;">{cat} ({len(stocks)})</h2>'
        for s in stocks:
            cards_html += build_stock_card(s)

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:640px;margin:0 auto;padding:20px;">

<div style="background:linear-gradient(135deg,#0f172a,#1e293b);border-radius:12px;padding:20px;margin-bottom:20px;">
<h1 style="margin:0 0 6px;color:#fff;font-size:22px;">Daily Stock Signals</h1>
<div style="color:#94a3b8;font-size:13px;">{date} &middot; {total} acciones analizadas</div>
<div style="display:flex;gap:12px;margin-top:14px;flex-wrap:wrap;">
<div style="background:#10b98122;border:1px solid #10b98144;border-radius:8px;padding:8px 14px;flex:1;min-width:100px;text-align:center;">
<div style="color:#10b981;font-size:20px;font-weight:700;">{bullish}</div>
<div style="color:#10b981;font-size:11px;">Oportunidades</div>
</div>
<div style="background:#6b728022;border:1px solid #6b728044;border-radius:8px;padding:8px 14px;flex:1;min-width:100px;text-align:center;">
<div style="color:#9ca3af;font-size:20px;font-weight:700;">{total - bullish - bearish}</div>
<div style="color:#9ca3af;font-size:11px;">Sin senal clara</div>
</div>
<div style="background:#ef444422;border:1px solid #ef444444;border-radius:8px;padding:8px 14px;flex:1;min-width:100px;text-align:center;">
<div style="color:#ef4444;font-size:20px;font-weight:700;">{bearish}</div>
<div style="color:#ef4444;font-size:11px;">Evitar</div>
</div>
</div>
<div style="background:#ffffff11;border:1px solid #ffffff22;border-radius:8px;padding:10px;margin-top:12px;">
<div style="color:#cbd5e1;font-size:11px;line-height:1.5;">Este reporte analiza cada accion con 4 dimensiones y te dice <b style="color:#fff;">que significa cada indicador</b> en lenguaje simple. No necesitas experiencia previa para entenderlo.</div>
</div>
</div>

{cards_html}

{GLOSSARY}

<div style="text-align:center;margin-top:20px;padding:16px;color:#94a3b8;font-size:11px;border-top:1px solid #e2e8f0;">
Este reporte es educativo, no es asesoria financiera. Haz tu propia investigacion antes de invertir.<br>
Generado automaticamente &middot; Datos de yfinance y Finnhub
</div>

</div>
</body>
</html>
"""
    return html


def generate_readme(signals, date):
    signals_sorted = sorted(signals, key=lambda x: x.get("composite_score", 0), reverse=True)
    total = len(signals)
    top_picks = [s for s in signals_sorted if s.get("composite_score", 0) >= 70][:10]
    avoid_list = [s for s in signals_sorted if s.get("signal_category") == "Avoid"]
    value_plays = [s for s in signals_sorted if s.get("signal_category") == "Value Play"]
    momentum = [s for s in signals_sorted if s.get("signal_category") == "Momentum Breakout"]
    trending = [s for s in signals_sorted if s.get("signal_category") == "Trending Up"]
    bullish = sum(1 for s in signals if s.get("signal_category") in ["Momentum Breakout", "Trending Up", "Narrative Hot"])
    bearish = len(avoid_list)

    def stock_row(s):
        ticker = s.get("ticker", "?")
        price = s.get("price", 0)
        change = s.get("change_pct", 0)
        score = s.get("composite_score", 0)
        category = s.get("signal_category", "Wait")
        trend = s.get("trend", "sideways")
        rsi = s.get("rsi")
        entry = s.get("entry_price")
        sector = s.get("sector", "")
        signal_info = signal_explanation(category)
        emoji = signal_info.get("emoji", "")

        change_arrow = "🟢" if change >= 0 else "🔴"
        change_sign = "+" if change >= 0 else ""
        trend_emoji = {"uptrend": "📈", "downtrend": "📉", "sideways": "➡️"}.get(trend, "➡️")

        rsi_text = f"{rsi:.0f}" if rsi else "N/A"
        entry_text = f"${entry:.2f}" if entry and entry > 0 else "—"

        return f"| {emoji} **{ticker}** | ${price:.2f} | {change_arrow} {change_sign}{change:.1f}% | {score:.0f}/100 | {trend_emoji} | {rsi_text} | {entry_text} | {sector} |"

    top_table = ""
    if top_picks:
        rows = "\n".join(stock_row(s) for s in top_picks)
        top_table = f"""
### 🟢 Top Oportunidades (Score >= 70)

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}
"""

    momentum_table = ""
    if momentum:
        rows = "\n".join(stock_row(s) for s in momentum[:5])
        momentum_table = f"""
### 🚀 Momentum Breakout

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}
"""

    trending_table = ""
    if trending:
        rows = "\n".join(stock_row(s) for s in trending[:5])
        trending_table = f"""
### 📈 Trending Up

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}
"""

    value_table = ""
    if value_plays:
        rows = "\n".join(stock_row(s) for s in value_plays)
        value_table = f"""
### 💎 Value Plays (Baratas respecto a su valor)

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}
"""

    avoid_table = ""
    if avoid_list:
        rows = "\n".join(stock_row(s) for s in avoid_list)
        avoid_table = f"""
### 🔴 Evitar

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}
"""

    all_table = ""
    if signals_sorted:
        rows = "\n".join(stock_row(s) for s in signals_sorted)
        all_table = f"""
<details>
<summary><b>Ver todas las {total} acciones analizadas</b></summary>

| Accion | Precio | Cambio | Score | Tendencia | RSI | Entrada Sugerida | Sector |
|--------|--------|--------|-------|-----------|-----|-----------------|--------|
{rows}

</details>
"""

    return f"""# Daily Stock Signals — {date}

> **⚠️ Disclaimer:** Este reporte es educativo, no es asesoria financiera. Haz tu propia investigacion antes de invertir.

## Resumen del Mercado

| Metrica | Valor |
|---------|-------|
| Acciones analizadas | {total} |
| Oportunidades alcistas | {bullish} |
| Sin senal clara | {total - bullish - bearish} |
| Evitar | {bearish} |

---

{top_table}
{momentum_table}
{trending_table}
{value_table}
{avoid_table}

---

## Como interpretar los datos

### Score Compuesto (0-100)
Resume 4 dimensiones: 30% tecnico + 30% fundamental + 20% sentimiento + 20% insider.

| Rango | Significado |
|-------|-------------|
| 70-100 | **Comprar** — La mayoria de indicadores son positivos |
| 50-69 | Neutral — Indicadores mixtos, esperar |
| 36-49 | Bajo — No es buen momento para comprar |
| 0-35 | **Evitar** — Casi todo apunta a venta |

### RSI (Relative Strength Index)
Mide la fuerza del movimiento del precio (0-100).

| Rango | Significado |
|-------|-------------|
| < 30 | **Sobrevendido** — Cayo mucho, posible rebote |
| 30-45 | Zona baja — Relativamente bajo |
| 45-55 | Neutral — Sin senal clara |
| 55-70 | Zona alta — Subio con fuerza |
| > 70 | **Sobrecomprado** — Subio demasiado, posible correccion |

### Tendencia
- 📈 **Alcista**: Precio sobre SMA50 y SMA200 — bueno para comprar
- 📉 **Bajista**: Precio bajo SMA50 y SMA200 — precaucion
- ➡️ **Lateral**: Sin direccion clara — esperar

### Volumen Relativo
- **> 1.5x**: Mucho interes, la tendencia es confiable
- **0.8-1.5x**: Normal
- **< 0.8x**: Poco interes, desconfia del movimiento

### Categorias de Senal
| Categoria | Significado |
|-----------|-------------|
| 🚀 Momentum Breakout | Rompiendo hacia arriba con fuerza |
| 📈 Trending Up | Tendencia alcista estable |
| 🔥 Narrative Hot | Muy mencionada en noticias |
| 💎 Value Play | Barata respecto a su valor real |
| 🔄 Oversold Bounce | Cayo demasiado, posible rebote |
| ⏳ Wait | Sin senal clara |
| ⚠️ Avoid | Mejor evitar |

---

{all_table}

---
*Generado automaticamente | Datos: yfinance + Finnhub | Pipeline AWS Step Functions*
*Ultima actualizacion: {date}*
"""


def update_github_readme(content, date):
    if not GITHUB_PAT:
        logger.warning("GITHUB_PAT not set, skipping README update")
        return False

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/README.md"
    headers = {
        "Authorization": f"token {GITHUB_PAT}",
        "Accept": "application/vnd.github.v3+json",
    }

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            logger.error(f"Failed to get README sha: {resp.status_code} {resp.text}")
            return False

        sha = resp.json()["sha"]
        encoded = base64.b64encode(content.encode("utf-8")).decode("utf-8")

        update_resp = requests.put(url, headers=headers, json={
            "message": f"Update daily signals - {date}",
            "content": encoded,
            "sha": sha,
        }, timeout=10)

        if update_resp.status_code in [200, 201]:
            logger.info(f"README updated on GitHub for {date}")
            return True
        else:
            logger.error(f"Failed to update README: {update_resp.status_code} {update_resp.text}")
            return False
    except Exception as e:
        logger.error(f"Error updating GitHub README: {str(e)}")
        return False


def handler(event, context):
    signals = event.get("signals", [])
    date = event.get("date", "unknown")

    subject = f"Stock Signals - {date}"
    html_body = format_email(signals, date)

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = SENDER_EMAIL
    msg["To"] = RECIPIENT_EMAIL

    html_part = MIMEText(html_body, "html", "utf-8")
    msg.attach(html_part)

    raw_message = msg.as_string()

    ses.send_raw_email(
        Source=SENDER_EMAIL,
        Destinations=[RECIPIENT_EMAIL],
        RawMessage={"Data": raw_message},
    )

    logger.info(f"Email sent via SES for {date}")

    readme_content = generate_readme(signals, date)
    github_updated = update_github_readme(readme_content, date)

    return {"status": "notified", "date": date, "count": len(signals), "github_updated": github_updated}
