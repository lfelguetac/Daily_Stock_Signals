# Daily Stock Signals

Pipeline ETL diario que analiza ~28 acciones en semiconductores, energía, nuclear y emergentes. Genera scores compuestos y señales de inversión para ayudarte a tomar mejores decisiones.

## Qué Analiza

| Dimensión | Peso | Indicadores |
|-----------|------|-------------|
| **Técnico** | 30% | RSI, MACD, distancia SMA 50/200, momentum 20d |
| **Fundamental** | 30% | P/E vs sector, revenue growth, márgenes, debt/equity |
| **Sentimiento** | 20% | Noticias positivas/negativas (Finnhub) |
| **Insider** | 20% | Compra/venta de insiders (SEC Form 4 via yfinance) |

Además detecta **Value Opportunities**: acciones vendidas con fuerza pero con fundamentales sólidas.

## Watchlist

### Semiconductores
NVDA, AMD, AVGO, QCOM, MU, ON, MPWR, ALAB

### Energía
XOM, OXY, SLB, VTLE, NOG, ARIS, PUMP

### Nuclear
CCJ, UUUU, DNN, LEU, OKLO, LTBR

### Emergentes / Narrativas Futuras
PLTR, RKLB, IONQ, SOUN, RGTI, ASTS, HIMS

## Arquitectura

```
EventBridge (9:00 AM Chile, Mon-Fri)
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  Step Functions: daily-signals-pipeline                  │
│                                                          │
│  1. Extract                                              │
│     ├─ yfinance: precios, fundamentals, indicadores      │
│     ├─ Finnhub: sentiment de noticias                    │
│     └─ SEC EDGAR: insider trading (Form 4)               │
│                                                          │
│  2. Transform                                            │
│     ├─ Technical Score (0-100)                           │
│     ├─ Fundamental Score (0-100)                         │
│     ├─ Sentiment Score (0-100)                           │
│     └─ Insider Score (0-100)                             │
│                                                          │
│  3. Analyze                                              │
│     ├─ Composite = 30%+30%+20%+20%                       │
│     ├─ Señal: BUY (>=70) / SELL (<=35) / HOLD (36-69)   │
│     ├─ Value Opportunity flag                            │
│     └─ Razones clave                                     │
│                                                          │
│  4. Load → DynamoDB (histórico) + S3 (JSON diario)       │
│  5. Notify → SNS email con top picks                     │
└──────────────────────────────────────────────────────────┘
```

## Email Output

```
Daily Stock Signals - 2026-05-10
========================================

VALUE OPPORTUNITIES:
  MSFT: 72/100 - BUY @ $420.50
    Down 18% from 52w high; P/E 28 < sector avg 35; Revenue growing +15%

TOP BUYS:
  NVDA: 85/100 - $890.25 (+2.3%)
    RSI 62 (neutral); Above SMA50; Momentum +8%

  CCJ: 78/100 - $95.40 (+1.1%)
    P/E 12 below sector avg 18; Revenue growth +22%

TOP SELLS:
  OKLO: 28/100 - $12.30 (-3.5%)
    RSI 82 (overbought); MACD bearish

WATCH:
  PLTR: 55/100 - $22.10 (+0.5%)
  AMD: 52/100 - $165.80 (-1.2%)

Total analyzed: 28 stocks
```

## Prerrequisitos

- Python 3.12+
- Terraform >= 1.0
- AWS CLI configurado (`aws configure`)
- [Finnhub API key](https://finnhub.io/register) (gratis)

## Despliegue

### 1. Build
```bash
./build.sh
```

### 2. Deploy
```bash
cd infra
terraform init
terraform apply -auto-approve \
  -var="finnhub_api_key=TU_FINNHUB_KEY"
```

### 3. Confirmar email
Revisa tu bandeja de entrada y confirma la suscripción SNS.

### 4. Test manual
```bash
aws stepfunctions start-execution \
  --state-machine-arn <state_machine_arn> \
  --region us-east-1
```

## Costos

| Servicio | Costo mensual estimado |
|----------|----------------------|
| Lambda + Step Functions | ~$0.40 |
| DynamoDB | ~$0.05 |
| S3 | ~$0.01 |
| SNS | Gratis |
| EventBridge | Gratis (primer 1M) |
| APIs externas | Gratis |
| **Total** | **~$0.66/mes** |

## Limpieza

```bash
cd infra
terraform destroy -auto-approve
```
