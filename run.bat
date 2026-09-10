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


docker compose up -d


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
