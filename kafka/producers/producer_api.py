from fastapi import FastAPI, HTTPException
from producers.transactions_producer import produce_day

app = FastAPI()


@app.post("/produce")
def produce(date: str):
    try:
        produce_day(date)
        return {
            "status": "ok",
            "date": date
        }

    except FileNotFoundError:
        raise HTTPException(
            404,
            f"Aucun fichier trouvé pour la date {date}"
        )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "producer_api:app",
        host="0.0.0.0",
        port=8090
    )