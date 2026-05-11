import boto3
import json
import os
import logging
from datetime import datetime
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
s3 = boto3.client("s3")
TABLE_NAME = os.environ["TABLE_NAME"]
BUCKET = os.environ["BUCKET"]


def float_to_decimal(obj):
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, list):
        return [float_to_decimal(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    return obj


def handler(event, context):
    signals = event.get("signals", [])
    date = datetime.utcnow().strftime("%Y-%m-%d")

    table = dynamodb.Table(TABLE_NAME)

    with table.batch_writer() as batch:
        for sig in signals:
            if "error" in sig:
                continue
            item = {
                "ticker": sig["ticker"],
                "date": date,
                "composite_score": float_to_decimal(sig.get("composite_score", 0)),
                "signal_category": sig.get("signal_category", "Wait"),
                "trend": sig.get("trend", "sideways"),
                "entry_price": float_to_decimal(sig.get("entry_price", 0)),
                "technical_score": float_to_decimal(sig.get("technical_score", 50)),
                "fundamental_score": float_to_decimal(sig.get("fundamental_score", 50)),
                "sentiment_score": float_to_decimal(sig.get("sentiment_score", 50)),
                "insider_score": float_to_decimal(sig.get("insider_score", 50)),
                "price": float_to_decimal(sig.get("price", 0)),
                "change_pct": float_to_decimal(sig.get("change_pct", 0)),
                "rsi": float_to_decimal(sig.get("rsi")) if sig.get("rsi") is not None else None,
                "volume_ratio": float_to_decimal(sig.get("volume_ratio")) if sig.get("volume_ratio") is not None else None,
                "sector": sig.get("sector", ""),
                "reasons": json.dumps(sig.get("reasons", [])),
            }
            batch.put_item(Item=item)
            logger.info(f"Saved {sig['ticker']} -> DynamoDB")

    s3_key = f"signals/{date}.json"
    s3.put_object(
        Bucket=BUCKET,
        Key=s3_key,
        Body=json.dumps({"date": date, "signals": signals}, indent=2),
        ContentType="application/json",
    )
    logger.info(f"Saved report to s3://{BUCKET}/{s3_key}")

    return {
        "loaded": len(signals),
        "date": date,
        "s3_key": s3_key,
    }
