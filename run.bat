@echo off

SET CMD=%1


IF "%CMD%"=="" SET CMD=all


IF "%CMD%"=="all" GOTO ALL
IF "%CMD%"=="kafka" GOTO KAFKA
IF "%CMD%"=="spark" GOTO SPARK
IF "%CMD%"=="infra" GOTO INFRA
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

docker compose up -d kafka zookeeper postgres  qdrant n8n

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