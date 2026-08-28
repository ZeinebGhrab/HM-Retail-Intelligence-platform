#!/bin/sh
# run_once.sh — H&M Retail Intelligence
# Emplacement : rag/benchmark/run_once.sh
#
# Rôle :
#  1. Attend que Ollama réponde (utile car ce conteneur démarre en même
#     temps que le service "ollama" ; sans attente, le premier appel
#     échouerait).
#  2. Si un rapport existe déjà (results/benchmark_report.json), NE
#     RELANCE RIEN — le benchmark est considéré comme "déjà fait".
#  3. Sinon, lance pull_models.py puis benchmark.py.
#
# Pour forcer une ré-exécution : supprime rag/benchmark/results/benchmark_report.json
# (ou tout results/ si tu veux repartir de zéro) avant de relancer le conteneur.

set -e

HOST="${OLLAMA_HOST:-http://ollama:11434}"
REPORT="/workspace/results/benchmark_report.json"

# Nombre d'essais et délai entre essais pour attendre Ollama. Total par
# défaut : 60 x 10s = 10 minutes (au lieu de 30 x 5s = 2m30 avant).
# Surchargeable via variables d'environnement si besoin de plus.
WAIT_ATTEMPTS="${OLLAMA_WAIT_ATTEMPTS:-60}"
WAIT_SLEEP="${OLLAMA_WAIT_SLEEP:-10}"

echo "============================================================"
echo "  Attente de Ollama ($HOST) ..."
echo "============================================================"

ollama_ready=0
for i in $(seq 1 "$WAIT_ATTEMPTS"); do
  if (command -v wget >/dev/null 2>&1 && wget -q -T 10 -O /dev/null "$HOST/api/tags" 2>/dev/null) \
     || (command -v curl >/dev/null 2>&1 && curl -sS -f -o /dev/null --connect-timeout 10 "$HOST/api/tags" 2>/dev/null); then
    echo "  ✓ Ollama est prêt."
    ollama_ready=1
    break
  fi
  echo "  ... pas encore prêt (essai $i/$WAIT_ATTEMPTS), attente ${WAIT_SLEEP}s"
  sleep "$WAIT_SLEEP"
done

if [ "$ollama_ready" -ne 1 ]; then
  echo ""
  echo "============================================================"
  echo "  [ERREUR] Ollama ($HOST) ne répond toujours pas après"
  echo "  $WAIT_ATTEMPTS tentative(s). Arrêt — on ne lance PAS le pull."
  echo "  Vérifie que le conteneur 'ollama' est démarré et en bonne santé"
  echo "  (docker compose ps / docker logs shop-ollama)."
  echo "============================================================"
  exit 1
fi

if [ -f "$REPORT" ]; then
  echo ""
  echo "============================================================"
  echo "  Un rapport existe déjà : $REPORT"
  echo "  Le benchmark ne sera PAS relancé."
  echo "  Pour forcer une nouvelle exécution : supprime ce fichier"
  echo "  (ou tout le dossier rag/benchmark/results/) puis relance."
  echo "============================================================"
  exit 0
fi

echo ""
echo "============================================================"
echo "  Étape 1/2 — Téléchargement des modèles"
echo "============================================================"
python pull_models.py

echo ""
echo "============================================================"
echo "  Étape 2/2 — Benchmark"
echo "============================================================"
python benchmark.py
