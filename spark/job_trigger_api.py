# import subprocess

# from fastapi import FastAPI, HTTPException

# app = FastAPI()

# JOBS = {
#     "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
#     "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
# }


# @app.post("/jobs/{job_name}")
# def trigger_job(job_name: str, source: str = "warehouse"):
#     if job_name not in JOBS:
#         raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

#     cmd = ["docker","exec","shop-spark-worker","/opt/spark/bin/spark-submit","--master","spark://spark-master:7077", "--driver-memory","1g","--executor-memory","4g","--executor-cores", "4","--total-executor-cores","4",JOBS[job_name],]

#     if job_name == "compute-rfm":
#         cmd += ["--source", source]

#     try:
#         result = subprocess.run(
#             cmd,
#             capture_output=True,
#             text=True,
#             timeout=7200,
#             check=True,
#         )

#         return {
#             "status": "success",
#             "job": job_name,
#             "stdout": result.stdout[-500:],
#         }

#     except subprocess.CalledProcessError as e:
#         print("COMMAND FAILED:", e.cmd)
#         print("RETURN CODE:", e.returncode)
#         print("STDOUT:", e.stdout)
#         print("STDERR:", e.stderr)

#         raise HTTPException(
#             status_code=500,
#             detail=e.stderr[-2000:] if e.stderr else str(e),
#         )

#     except subprocess.TimeoutExpired:
#         raise HTTPException(
#             status_code=504,
#             detail="Le job Spark a dépassé le délai autorisé (30 min).",
#         )

import logging
import subprocess

from fastapi import FastAPI, HTTPException

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spark-job-trigger")

JOBS = {
    "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
    "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
}


def extract_relevant_error(stderr: str, max_lines: int = 40) -> str:
    """
    spark-submit produit énormément de logs INFO à l'arrêt (shutdown hooks,
    BlockManager, etc.) qui masquent la vraie exception si on tronque
    bêtement la fin du stderr. On cherche plutôt les lignes qui contiennent
    une vraie erreur/exception/traceback.
    """
    if not stderr:
        return "Aucune sortie stderr disponible."

    lines = stderr.splitlines()
    keywords = ("Exception", "Error", "Traceback", "FAILED", "failed")
    error_lines = [l for l in lines if any(k in l for k in keywords)]

    if error_lines:
        return "\n".join(error_lines[-max_lines:])

    # Si aucune ligne "erreur" identifiée, on retombe sur la fin du stderr
    return "\n".join(lines[-max_lines:])


@app.post("/jobs/{job_name}")
def trigger_job(job_name: str, source: str = "warehouse"):
    if job_name not in JOBS:
        raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

    cmd = [
        "docker", "exec", "shop-spark-worker-batch",
        "/opt/spark/bin/spark-submit",
        "--master", "spark://spark-master:7077",
        "--driver-memory", "2g",
        "--executor-memory", "4g",
        "--executor-cores", "4",
        "--total-executor-cores", "4",
        JOBS[job_name],
    ]

    if job_name == "compute-rfm":
        cmd += ["--source", source]

    logger.info("Lancement du job %s avec la commande : %s", job_name, " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            check=True,
        )

        logger.info("Job %s terminé avec succès (returncode=%s)", job_name, result.returncode)

        return {
            "status": "success",
            "job": job_name,
            "stdout": result.stdout[-500:],
        }

    except subprocess.CalledProcessError as e:
        # On logge TOUT côté serveur pour debug (jamais tronqué ici)
        logger.error("COMMAND FAILED: %s", e.cmd)
        logger.error("RETURN CODE: %s", e.returncode)
        logger.error("FULL STDOUT:\n%s", e.stdout)
        logger.error("FULL STDERR:\n%s", e.stderr)

        # On renvoie à n8n une erreur lisible et pertinente, pas juste
        # les 2000 derniers caractères du stderr (qui sont souvent des
        # logs de shutdown normaux et masquent la vraie cause)
        relevant_error = extract_relevant_error(e.stderr)

        raise HTTPException(
            status_code=500,
            detail=(
                f"Le job Spark '{job_name}' a échoué avec le code de retour "
                f"{e.returncode}.\n\nErreur pertinente :\n{relevant_error}"
            ),
        )

    except subprocess.TimeoutExpired as e:
        logger.error("TIMEOUT pour le job %s après %s secondes", job_name, e.timeout)
        raise HTTPException(
            status_code=504,
            detail=f"Le job Spark '{job_name}' a dépassé le délai autorisé ({e.timeout}s).",
        )

    except Exception as e:
        # Filet de sécurité : on ne veut jamais un 500 générique sans détail
        logger.exception("Erreur inattendue lors du lancement du job %s", job_name)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur inattendue : {type(e).__name__}: {str(e)}",
        )