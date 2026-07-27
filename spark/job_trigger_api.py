# # import subprocess

# # from fastapi import FastAPI, HTTPException

# # app = FastAPI()

# # JOBS = {
# #     "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
# #     "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
# # }


# # @app.post("/jobs/{job_name}")
# # def trigger_job(job_name: str, source: str = "warehouse"):
# #     if job_name not in JOBS:
# #         raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

# #     cmd = ["docker","exec","shop-spark-worker","/opt/spark/bin/spark-submit","--master","spark://spark-master:7077", "--driver-memory","1g","--executor-memory","4g","--executor-cores", "4","--total-executor-cores","4",JOBS[job_name],]

# #     if job_name == "compute-rfm":
# #         cmd += ["--source", source]

# #     try:
# #         result = subprocess.run(
# #             cmd,
# #             capture_output=True,
# #             text=True,
# #             timeout=7200,
# #             check=True,
# #         )

# #         return {
# #             "status": "success",
# #             "job": job_name,
# #             "stdout": result.stdout[-500:],
# #         }

# #     except subprocess.CalledProcessError as e:
# #         print("COMMAND FAILED:", e.cmd)
# #         print("RETURN CODE:", e.returncode)
# #         print("STDOUT:", e.stdout)
# #         print("STDERR:", e.stderr)

# #         raise HTTPException(
# #             status_code=500,
# #             detail=e.stderr[-2000:] if e.stderr else str(e),
# #         )

# #     except subprocess.TimeoutExpired:
# #         raise HTTPException(
# #             status_code=504,
# #             detail="Le job Spark a dépassé le délai autorisé (30 min).",
# #         )

# import logging
# import subprocess

# from fastapi import FastAPI, HTTPException

# app = FastAPI()

# logging.basicConfig(level=logging.INFO)
# logger = logging.getLogger("spark-job-trigger")

# JOBS = {
#     "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
#     "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
# }


# def extract_relevant_error(stderr: str, max_lines: int = 40) -> str:
#     """
#     spark-submit produit énormément de logs INFO à l'arrêt (shutdown hooks,
#     BlockManager, etc.) qui masquent la vraie exception si on tronque
#     bêtement la fin du stderr. On cherche plutôt les lignes qui contiennent
#     une vraie erreur/exception/traceback.
#     """
#     if not stderr:
#         return "Aucune sortie stderr disponible."

#     lines = stderr.splitlines()
#     keywords = ("Exception", "Error", "Traceback", "FAILED", "failed")
#     error_lines = [l for l in lines if any(k in l for k in keywords)]

#     if error_lines:
#         return "\n".join(error_lines[-max_lines:])

#     # Si aucune ligne "erreur" identifiée, on retombe sur la fin du stderr
#     return "\n".join(lines[-max_lines:])


# @app.post("/jobs/{job_name}")
# def trigger_job(job_name: str, source: str = "warehouse"):
#     if job_name not in JOBS:
#         raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

#     cmd = [
#         "docker", "exec", "shop-spark-worker-batch",
#         "/opt/spark/bin/spark-submit",
#         "--master", "spark://spark-master:7077",
#         "--driver-memory", "2g",
#         "--executor-memory", "4g",
#         "--executor-cores", "4",
#         "--total-executor-cores", "4",
#         JOBS[job_name],
#     ]

#     if job_name == "compute-rfm":
#         cmd += ["--source", source]

#     logger.info("Lancement du job %s avec la commande : %s", job_name, " ".join(cmd))

#     try:
#         result = subprocess.run(
#             cmd,
#             capture_output=True,
#             text=True,
#             timeout=7200,
#             check=True,
#         )

#         logger.info("Job %s terminé avec succès (returncode=%s)", job_name, result.returncode)

#         return {
#             "status": "success",
#             "job": job_name,
#             "stdout": result.stdout[-500:],
#         }

#     except subprocess.CalledProcessError as e:
#         # On logge TOUT côté serveur pour debug (jamais tronqué ici)
#         logger.error("COMMAND FAILED: %s", e.cmd)
#         logger.error("RETURN CODE: %s", e.returncode)
#         logger.error("FULL STDOUT:\n%s", e.stdout)
#         logger.error("FULL STDERR:\n%s", e.stderr)

#         # On renvoie à n8n une erreur lisible et pertinente, pas juste
#         # les 2000 derniers caractères du stderr (qui sont souvent des
#         # logs de shutdown normaux et masquent la vraie cause)
#         relevant_error = extract_relevant_error(e.stderr)

#         raise HTTPException(
#             status_code=500,
#             detail=(
#                 f"Le job Spark '{job_name}' a échoué avec le code de retour "
#                 f"{e.returncode}.\n\nErreur pertinente :\n{relevant_error}"
#             ),
#         )

#     except subprocess.TimeoutExpired as e:
#         logger.error("TIMEOUT pour le job %s après %s secondes", job_name, e.timeout)
#         raise HTTPException(
#             status_code=504,
#             detail=f"Le job Spark '{job_name}' a dépassé le délai autorisé ({e.timeout}s).",
#         )

#     except Exception as e:
#         # Filet de sécurité : on ne veut jamais un 500 générique sans détail
#         logger.exception("Erreur inattendue lors du lancement du job %s", job_name)
#         raise HTTPException(
#             status_code=500,
#             detail=f"Erreur inattendue : {type(e).__name__}: {str(e)}",
#         )
import logging
import subprocess
import time

from fastapi import FastAPI, HTTPException

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("spark-job-trigger")

JOBS = {
    "merge-stream": "/opt/spark/work-dir/batch_ml_pipeline/jobs/merge_stream_to_warehouse.py",
    "compute-rfm": "/opt/spark/work-dir/batch_ml_pipeline/jobs/pipeline_hm.py",
}

# Conteneur unique portant à la fois le worker streaming et batch
# (architecture à un seul spark-worker : 6 cores / 6G).
BATCH_EXEC_CONTAINER = "shop-spark-worker"

# Jobs qui doivent tourner en exclusivité sur le cluster (ils libèrent
# le streaming le temps de l'exécution). Avec un worker unique de
# 6 cores/6G, streaming (2 cores/1g) + batch (4 cores/4g) tiennent en
# théorie ensemble (6/5g) : ce mécanisme sert de filet de sécurité si
# tu augmentes les ressources demandées par le batch plus tard.
EXCLUSIVE_JOBS: set[str] = set()  # ex: {"compute-rfm"} pour réactiver

STREAMING_CONTAINER = "shop-spark-streaming"
STOP_TIMEOUT_S = 30          # délai de grâce laissé à `docker stop`
STATUS_POLL_TIMEOUT_S = 60   # temps max pour confirmer l'arrêt/démarrage
STATUS_POLL_INTERVAL_S = 2


def extract_relevant_error(stderr: str, max_lines: int = 40) -> str:
    if not stderr:
        return "Aucune sortie stderr disponible."
    lines = stderr.splitlines()
    keywords = ("Exception", "Error", "Traceback", "FAILED", "failed")
    error_lines = [l for l in lines if any(k in l for k in keywords)]
    if error_lines:
        return "\n".join(error_lines[-max_lines:])
    return "\n".join(lines[-max_lines:])


def _run_docker_cmd(args: list[str], timeout: int) -> subprocess.CompletedProcess:
    cmd = ["docker"] + args
    logger.info("Exécution : %s", " ".join(cmd))
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def container_is_running(container: str) -> bool:
    result = _run_docker_cmd(
        ["inspect", "-f", "{{.State.Running}}", container],
        timeout=10,
    )
    if result.returncode != 0:
        # Le conteneur n'existe pas ou erreur docker -> on considère "arrêté"
        logger.warning(
            "Impossible d'inspecter %s (code=%s, stderr=%s)",
            container, result.returncode, result.stderr.strip(),
        )
        return False
    return result.stdout.strip() == "true"


def wait_for_state(container: str, expected_running: bool, timeout_s: int) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if container_is_running(container) == expected_running:
            return True
        time.sleep(STATUS_POLL_INTERVAL_S)
    return False


def stop_streaming() -> None:
    if not container_is_running(STREAMING_CONTAINER):
        logger.info("%s déjà arrêté, rien à faire.", STREAMING_CONTAINER)
        return

    logger.info("Arrêt de %s avant le job exclusif...", STREAMING_CONTAINER)
    result = _run_docker_cmd(
        ["stop", "-t", str(STOP_TIMEOUT_S), STREAMING_CONTAINER],
        timeout=STOP_TIMEOUT_S + 15,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Échec de l'arrêt de {STREAMING_CONTAINER} : {result.stderr.strip()}"
        )

    if not wait_for_state(STREAMING_CONTAINER, expected_running=False,
                           timeout_s=STATUS_POLL_TIMEOUT_S):
        raise RuntimeError(
            f"{STREAMING_CONTAINER} ne s'est pas arrêté dans les "
            f"{STATUS_POLL_TIMEOUT_S}s impartis."
        )
    logger.info("%s arrêté avec succès.", STREAMING_CONTAINER)


def restart_streaming() -> None:
    """
    Best effort : on logge une erreur si ça échoue, mais on ne lève pas
    d'exception ici pour ne pas masquer un éventuel échec du job batch
    qui a appelé cette fonction dans son bloc finally.
    """
    try:
        logger.info("Redémarrage de %s...", STREAMING_CONTAINER)
        result = _run_docker_cmd(["start", STREAMING_CONTAINER], timeout=30)
        if result.returncode != 0:
            logger.error(
                "Échec du redémarrage de %s : %s",
                STREAMING_CONTAINER, result.stderr.strip(),
            )
            return

        if not wait_for_state(STREAMING_CONTAINER, expected_running=True,
                               timeout_s=STATUS_POLL_TIMEOUT_S):
            logger.error(
                "%s ne semble pas être reparti dans les %ss impartis.",
                STREAMING_CONTAINER, STATUS_POLL_TIMEOUT_S,
            )
            return

        logger.info("%s redémarré avec succès.", STREAMING_CONTAINER)
    except Exception:
        logger.exception("Erreur inattendue lors du redémarrage de %s",
                          STREAMING_CONTAINER)


@app.post("/jobs/{job_name}")
def trigger_job(job_name: str, source: str = "warehouse"):
    if job_name not in JOBS:
        raise HTTPException(status_code=404, detail=f"Job inconnu : {job_name}")

    exclusive = job_name in EXCLUSIVE_JOBS
    streaming_was_stopped = False

    cmd = [
        "docker", "exec", BATCH_EXEC_CONTAINER,
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

    try:
        if exclusive:
            stop_streaming()
            streaming_was_stopped = True

        logger.info("Lancement du job %s : %s", job_name, " ".join(cmd))
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7200, check=True,
        )
        logger.info("Job %s terminé avec succès (returncode=%s)",
                    job_name, result.returncode)

        return {
            "status": "success",
            "job": job_name,
            "stdout": result.stdout[-500:],
        }

    except RuntimeError as e:
        logger.error("Impossible de préparer l'exécution exclusive : %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    except subprocess.CalledProcessError as e:
        logger.error("COMMAND FAILED: %s", e.cmd)
        logger.error("RETURN CODE: %s", e.returncode)
        logger.error("FULL STDOUT:\n%s", e.stdout)
        logger.error("FULL STDERR:\n%s", e.stderr)
        relevant_error = extract_relevant_error(e.stderr)
        raise HTTPException(
            status_code=500,
            detail=(
                f"Le job Spark '{job_name}' a échoué avec le code de retour "
                f"{e.returncode}.\n\nErreur pertinente :\n{relevant_error}"
            ),
        )

    except subprocess.TimeoutExpired as e:
        logger.error("TIMEOUT pour le job %s après %s secondes",
                     job_name, e.timeout)
        raise HTTPException(
            status_code=504,
            detail=f"Le job Spark '{job_name}' a dépassé le délai autorisé "
                   f"({e.timeout}s).",
        )

    except Exception as e:
        logger.exception("Erreur inattendue lors du lancement du job %s", job_name)
        raise HTTPException(
            status_code=500,
            detail=f"Erreur inattendue : {type(e).__name__}: {str(e)}",
        )

    finally:
        if streaming_was_stopped:
            restart_streaming()