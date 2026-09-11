@echo off

SET CMD=%1


IF "%CMD%"=="" SET CMD=all


IF "%CMD%"=="all" GOTO ALL
IF "%CMD%"=="kafka" GOTO KAFKA
IF "%CMD%"=="spark" GOTO SPARK
IF "%CMD%"=="infra" GOTO INFRA
IF "%CMD%"=="ml" GOTO ML
IF "%CMD%"=="bench" GOTO BENCH
IF "%CMD%"=="logs" GOTO LOGS
IF "%CMD%"=="status" GOTO STATUS
IF "%CMD%"=="down" GOTO DOWN
IF "%CMD%"=="clean" GOTO CLEAN



echo Commande inconnue
EXIT /B 1



:ALL

echo ===============================
echo SHOP ANALYTICS DATA PLATFORM
echo ===============================

REM GPU si dispo (nvidia-smi present ET fonctionnel), CPU sinon -- voir
REM docker-compose.gpu.yml pour ce qui est ajoute et pourquoi.
SET GPU_FLAGS=

where nvidia-smi >nul 2>&1
IF %ERRORLEVEL%==0 (
    nvidia-smi >nul 2>&1
    IF %ERRORLEVEL%==0 SET GPU_FLAGS=-f docker-compose.yml -f docker-compose.gpu.yml
)

IF DEFINED GPU_FLAGS (
    echo GPU NVIDIA detecte -- activation de l'acceleration GPU pour Ollama.
    docker compose %GPU_FLAGS% up -d
) ELSE (
    docker compose up -d
)


GOTO END




:INFRA

docker compose up -d kafka zookeeper postgres adminer qdrant n8n mlflow

GOTO END




:ML

docker compose up -d mlflow ml-serving

GOTO END




:BENCH

REM Benchmark LLM (choix du modele Ollama) — voir backend/benchmark/
REM Ne demarre jamais via "run.bat all" (protege par profiles: benchmark
REM dans docker-compose.yml). Lancement one-shot : cree, execute, supprime
REM le conteneur (--rm), sans toucher aux volumes ni a backend/benchmark/results/.
REM Pour relancer un benchmark frais : supprime backend\benchmark\results\benchmark_report.json

echo ===============================
echo  Benchmark LLM (choix du modele)
echo ===============================

docker compose --profile benchmark run --rm --build benchmark

GOTO END




:KAFKA

docker compose up -d kafka zookeeper

GOTO END




:SPARK

docker compose up -d spark-master spark-worker

GOTO END




:LOGS

docker compose logs -f

GOTO END




:STATUS

docker compose ps

GOTO END




:DOWN

docker compose down

GOTO END




:CLEAN

docker compose down -v

GOTO END



:END
