import argparse
import json
import time
import pandas as pd
from confluent_kafka import Producer

def make_producer():
    return Producer({"bootstrap.servers": "kafka:29092"})

def delivery_report(err, msg):
    if err is not None:
        print(f"Échec livraison : {err}")

def produce_day(date_str, delay_ms=50):
    path = f"/data/daily/transactions_{date_str}.csv"
    df = pd.read_csv(path, dtype={"article_id": str})
    producer = make_producer()

    for _, row in df.iterrows():
        message = {
            "t_dat": row["t_dat"],
            "customer_id": row["customer_id"],
            "article_id": int(row["article_id"]),
            "price": float(row["price"]),
            "sales_channel_id": int(row["sales_channel_id"]),
        }
        producer.produce(
            "transactions.raw",
            key=row["customer_id"],
            value=json.dumps(message),
            callback=delivery_report,
        )
        producer.poll(0)
        time.sleep(delay_ms / 1000)  # espace les messages pour simuler un flux réel, pas un déversement instantané

    producer.flush()
    print(f"{len(df)} transactions du {date_str} envoyées sur transactions.raw")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Format YYYY-MM-DD")
    parser.add_argument("--delay-ms", type=int, default=50)
    args = parser.parse_args()
    produce_day(args.date, args.delay_ms)