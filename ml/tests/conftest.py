"""Configuration pytest partagée pour ml/tests/."""
import os
import sys
import tempfile
from pathlib import Path

ML_DIR = Path(__file__).resolve().parent.parent
for p in (ML_DIR, ML_DIR / "training", ML_DIR / "serving"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Filet de sécurité : si aucune MLFLOW_TRACKING_URI n'est définie (ex. hors CI),
# on pointe vers un backend SQLite local temporaire plutôt que le défaut
# "http://localhost:5000" de config.yaml, qui peut faire pendre les tests
# de longues secondes si le port est filtré plutôt que refusé.
os.environ.setdefault("MLFLOW_TRACKING_URI", f"sqlite:///{tempfile.mkdtemp()}/mlflow.db")