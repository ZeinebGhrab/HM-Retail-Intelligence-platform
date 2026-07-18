import subprocess

from fastapi import FastAPI, HTTPException

app = FastAPI(title="Spark Streaming Controller")


STREAMING_JOB = "/opt/spark/work-dir/streaming_pipeline/jobs/streaming_job.py"


@app.post("/streaming")
def run_streaming():

    cmd = [
        "docker",
        "exec",
        "shop-spark-worker",
        "/opt/spark/bin/spark-submit",
        "--master",
        "spark://spark-master:7077",
        "--driver-memory",
        "1g",
        "--executor-memory",
        "4g",
        "--executor-cores",
        "4",
        "--total-executor-cores",
        "4",
        STREAMING_JOB,
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            check=True,
        )

        return {
            "status": "success",
            "job": "streaming_job",
            "stdout": result.stdout[-500:]
        }

    except subprocess.CalledProcessError as e:
        raise HTTPException(
            status_code=500,
            detail=e.stderr[-2000:]
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Le job Spark Streaming a dépassé le délai."
        )