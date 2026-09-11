#!/usr/bin/env bash
# Équivalent Linux/Mac de run.bat
set -e

CMD="${1:-all}"

case "$CMD" in
  all)
    echo "==============================="
    echo "SHOP ANALYTICS DATA PLATFORM"
    echo "==============================="
    # GPU si dispo (nvidia-smi présent ET fonctionnel), CPU sinon — voir
    # docker-compose.gpu.yml pour ce qui est ajouté et pourquoi.
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi >/dev/null 2>&1; then
      echo "GPU NVIDIA détecté — activation de l'accélération GPU pour Ollama."
      docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d
    else
      docker compose up -d
    fi
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