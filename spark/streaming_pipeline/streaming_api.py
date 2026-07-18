"""
API REST pour piloter le job Spark Streaming (streaming_job.py) depuis n8n.

Endpoint principal (UN SEUL nœud n8n nécessaire) :
  POST /streaming   -> démarre le job s'il ne tourne pas déjà, sinon renvoie juste son statut

Endpoints optionnels (utiles pour debug, pas obligatoires) :
  POST /streaming/stop    -> arrête le process
  GET  /streaming/status  -> running / stopped + pid
  GET  /streaming/logs    -> dernières lignes du log

Lancement de l'API (dans le conteneur Spark, ou un conteneur à part avec accès au réseau/volume) :
  pip install fastapi uvicorn
  uvicorn streaming_api:app --host 0.0.0.0 --port 8000

Dans n8n : UN SEUL nœud "HTTP Request"
  - Method: POST
  - URL: http://<host>:8000/streaming
"""

import os
import signal
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="Spark Streaming Controller")

# --- Configuration (à adapter via variables d'env si besoin) ---
SPARK_SUBMIT_BIN = os.getenv("SPARK_SUBMIT_BIN", "spark-submit")
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
JOB_PATH = os.getenv(
    "STREAMING_JOB_PATH",
    "/opt/spark/work-dir/streaming_pipeline/jobs/streaming_job.py",
)
PID_FILE = Path("/tmp/streaming_job.pid")
LOG_FILE = Path("/tmp/streaming_job.log")


class StartOptions(BaseModel):
    executor_memory: str = "512m"
    executor_cores: str = "2"


def _read_pid() -> int | None:
    if PID_FILE.exists():
        try:
            return int(PID_FILE.read_text().strip())
        except ValueError:
            return None
    return None


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)  # signal 0 = juste vérifier l'existence du process
        return True
    except OSError:
        return False


@app.post("/streaming")
def run_streaming(opts: StartOptions = StartOptions()):
    """
    Endpoint unique pour n8n : un seul nœud HTTP Request qui appelle cette route.
    - Si le job tourne déjà -> renvoie juste son statut (rien ne casse).
    - Sinon -> le démarre puis renvoie son statut.
    """
    pid = _read_pid()
    if pid and _is_running(pid):
        return {"status": "already_running", "pid": pid}

    cmd = [
        SPARK_SUBMIT_BIN,
        "--master", SPARK_MASTER,
        "--conf", f"spark.executor.memory={opts.executor_memory}",
        "--conf", f"spark.executor.cores={opts.executor_cores}",
        JOB_PATH,
    ]

    log_fh = open(LOG_FILE, "w")
    process = subprocess.Popen(
        cmd,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    PID_FILE.write_text(str(process.pid))

    return {"status": "started", "pid": process.pid, "job_path": JOB_PATH}


@app.post("/streaming/stop")
def stop_streaming():
    pid = _read_pid()
    if not pid or not _is_running(pid):
        raise HTTPException(status_code=404, detail="Aucun job en cours.")

    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass

    PID_FILE.unlink(missing_ok=True)
    return {"status": "stopped", "pid": pid}


@app.get("/streaming/status")
def status_streaming():
    pid = _read_pid()
    running = bool(pid and _is_running(pid))
    return {"running": running, "pid": pid if running else None}


@app.get("/streaming/logs")
def get_logs(lines: int = 100):
    if not LOG_FILE.exists():
        return {"log": ""}
    with open(LOG_FILE, "r", errors="ignore") as f:
        content = f.readlines()
    return {"log": "".join(content[-lines:])}
