# AGENTS.md — Daily Stock Signals ETL

## Project Overview

Pipeline ETL diario orquestado con AWS Step Functions que analiza ~28 tickers en semiconductores, energía, nuclear y emergentes. Genera un score compuesto (0-100) y señales BUY/SELL/HOLD para ayudar en decisiones de inversión.

## Arquitectura

```
EventBridge (9:00 AM Chile = 13:00 UTC, Mon-Fri)
    │
    ▼
Step Functions: daily-signals-pipeline
    ├── Extract: yfinance + Finnhub + SEC EDGAR
    ├── Transform: Technical (30%) + Fundamental (30%) + Sentiment (20%) + Insider (20%)
    ├── Analyze: Composite Score + Value Opportunity Flag + Señal
    ├── Load: DynamoDB (histórico) + S3 (JSON diario)
    └── Notify: SNS → Email
```

## Watchlist

### Semiconductores (8)
NVDA, AMD, AVGO, QCOM, MU, ON, MPWR, ALAB

### Energía (7)
XOM, OXY, SLB, VTLE, NOG, ARIS, PUMP

### Nuclear (6)
CCJ, UUUU, DNN, LEU, OKLO, LTBR

### Emergentes / Narrativas (7)
PLTR, RKLB, IONQ, SOUN, RGTI, ASTS, HIMS

## Score Ponderation

| Dimensión | Peso | Fuente |
|-----------|------|--------|
| Técnico | 30% | yfinance (RSI, MACD, SMA 50/200, momentum) |
| Fundamental | 30% | yfinance (P/E, revenue growth, margins, debt/equity) |
| Sentimiento | 20% | Finnhub (news sentiment) |
| Insider | 20% | yfinance insider_transactions (Form 4 SEC) |

## Value Opportunity Flag

Se activa cuando cumple >= 3 de:
- Caída > 15% desde máximo 52 semanas
- P/E < promedio del sector
- Revenue growth > 0
- Current ratio > 1.5

## APIs

| API | Uso | Free tier |
|-----|-----|-----------|
| yfinance | Precios, fundamentals, indicadores, insider | Ilimitado |
| Finnhub | Sentimiento de noticias | 60 calls/min |
| SEC EDGAR | Insider trading (Form 4) | Ilimitado |

## Estructura del Repo

```
Daily_Stock_Signals/
├── functions/
│   ├── extract/      # yfinance + Finnhub
│   ├── transform/    # Scores por dimensión
│   ├── analyze/      # Composite + señales + value flag
│   ├── load/         # DynamoDB + S3
│   └── notify/       # SNS email
├── infra/
│   ├── main.tf       # Step Functions, Lambdas, DynamoDB, S3, SNS, EventBridge
│   ├── variables.tf
│   └── terraform.tfvars  # API keys (gitignored)
├── build.sh
├── AGENTS.md
└── README.md
```

## Costo

~$0.03/día × 22 días hábiles = ~$0.66/mes

## Infra Actual

- **Región**: us-east-1
- **Email SNS**: lf.elgueta@gmail.com
- **Runtime**: Python 3.12 para todas las Lambdas
- **Timeout Extract**: 180s (yfinance puede ser lento con 28 tickers)
- **Timeout resto**: 60s
- **Memory**: 512MB para Extract, 256MB para el resto
- **DynamoDB**: PK=ticker (S), SK=date (S), on-demand
- **EventBridge**: cron(0 13 ? * MON-FRI *) = 9:00 AM Chile (UTC-4)

## Señales

- BUY: composite_score >= 70
- SELL: composite_score <= 35
- HOLD: 36-69
