import subprocess

from fastapi import FastAPI, HTTPException

app = FastAPI()

JOBS = {
    "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
    "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
}


@app.post("/jobs/{job_name}")
def trigger_job(job_name: str, source: str = "warehouse"):
    if job_name not in JOBS:
        raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

    cmd = ["docker","exec","shop-spark-worker","/opt/spark/bin/spark-submit","--master","spark://spark-master:7077", "--driver-memory","3g","--executor-memory","3g","--executor-cores", "2",JOBS[job_name],]

    if job_name == "compute-rfm":
        cmd += ["--source", source]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,
            check=True,
        )

        return {
            "status": "success",
            "job": job_name,
            "stdout": result.stdout[-500:],
        }

    except subprocess.CalledProcessError as e:
        print("COMMAND FAILED:", e.cmd)
        print("RETURN CODE:", e.returncode)
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)

        raise HTTPException(
            status_code=500,
            detail=e.stderr[-2000:] if e.stderr else str(e),
        )

    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail="Le job Spark a dépassé le délai autorisé (30 min).",
        )