#!/usr/bin/env bash
# Équivalent Linux/Mac de run.bat
set -e

CMD="${1:-all}"

case "$CMD" in
  all)
    echo "==============================="
    echo "SHOP ANALYTICS DATA PLATFORM"
    echo "==============================="
    docker compose up -d
    ;;
  infra)
    docker compose up -d kafka zookeeper postgres adminer qdrant n8n mlflow
    ;;
  ml)
    docker compose up -d mlflow ml-serving
    ;;
  kafka)
    docker compose up -d kafka zookeeper
    ;;
  spark)
    docker compose up -d spark-master spark-worker
    ;;
  logs)
    docker compose logs -f
    ;;
  status)
    docker compose ps
    ;;
  down)
    docker compose down
    ;;
  clean)
    docker compose down -v
    ;;
  *)
    echo "Commande inconnue : $CMD"
    echo "Usage : ./run.sh [all|infra|ml|kafka|spark|logs|status|down|clean]"
    exit 1
    ;;
esac