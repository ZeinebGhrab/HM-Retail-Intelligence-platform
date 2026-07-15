"""
Génère un rapport de dérive des données (data drift) avec Evidently AI, en
comparant une fenêtre de référence (données d'entraînement) à une fenêtre
"courante" (données récentes / trafic de production simulé).

Dans une plateforme temps réel comme celle-ci, la fenêtre "courante" est en
principe alimentée par les features recalculées périodiquement par
`spark/jobs/` à partir du flux Kafka. En l'absence de cette table de
production, ce script permet une comparaison exploratoire :
    - référence : table PostgreSQL `customers_features_train` (ou repli synthétique)
    - courante  : un fichier fourni en argument, ou un sous-échantillon
      bruité de la référence à des fins de démonstration.

Usage :
    python ml/monitoring/drift_report.py \\
        --current data/processed/customers_recent.csv \\
        --output ml/monitoring/reports/drift_report.html

Sans --current, un jeu "courant" est simulé (léger bruit + décalage de
distribution) pour illustrer un cas de dérive détectée.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import load_config, load_customer_features  # noqa: E402


def _simulate_current_data(reference: pd.DataFrame, config: dict, seed: int = 7) -> pd.DataFrame:
    """Simule un jeu "courant" avec une dérive volontaire sur quelques colonnes
    numériques (utile pour démontrer la détection de drift sans données de
    production réelles)."""
    rng = np.random.RandomState(seed)
    n = config["monitoring"]["current_sample_size"]
    sample = reference.sample(n=min(n, len(reference)), replace=len(reference) < n, random_state=seed).copy()

    # Dérive simulée : vieillissement de la base + baisse de la fréquence d'achat
    # (scénario plausible : ralentissement de l'acquisition, désengagement club).
    if "age" in sample.columns:
        sample["age"] = (sample["age"] + rng.normal(4, 2, size=len(sample))).clip(18, 99).round()
    if "purchase_frequency_per_month" in sample.columns:
        sample["purchase_frequency_per_month"] = (sample["purchase_frequency_per_month"] * 0.7).round(3)
    if "recency_days" in sample.columns:
        sample["recency_days"] = (sample["recency_days"] * 1.4).round()
    return sample


def generate_report(config_path: str | None = None, current_path: str | None = None, output_path: str | None = None) -> Path:
    config = load_config(config_path)
    reference = load_customer_features(config)

    ref_n = config["monitoring"]["reference_sample_size"]
    reference_sample = reference.sample(n=min(ref_n, len(reference)), random_state=42)

    if current_path:
        current = pd.read_csv(current_path)
    else:
        print("[INFO] --current non fourni : simulation d'un jeu de données courant à des fins de démonstration.")
        current = _simulate_current_data(reference, config)

    common_cols = [c for c in reference_sample.columns if c in current.columns]
    reference_sample = reference_sample[common_cols]
    current = current[common_cols]

    from evidently.report import Report
    from evidently.metric_preset import DataDriftPreset

    report = Report(metrics=[DataDriftPreset()])
    report.run(reference_data=reference_sample, current_data=current)

    out_path = Path(output_path) if output_path else Path(__file__).parent / "reports" / "drift_report.html"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report.save_html(str(out_path))

    # Résumé exploitable en CI (ex. pour décider d'un retraining automatique)
    result = report.as_dict()
    try:
        drift_summary = result["metrics"][0]["result"]
        share = drift_summary.get("share_of_drifted_columns")
        dataset_drift = drift_summary.get("dataset_drift")
        print(f"Part de colonnes en dérive : {share}")
        print(f"Dérive globale détectée : {dataset_drift}")
        threshold = config["monitoring"]["drift_share_threshold"]
        if share is not None and share >= threshold:
            print(f"[ALERTE] Part de colonnes en dérive ({share:.2f}) >= seuil ({threshold}). Un ré-entraînement est recommandé.")
    except (KeyError, IndexError, TypeError):
        pass

    print(f"Rapport HTML généré : {out_path}")
    return out_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=None)
    parser.add_argument("--current", default=None, help="CSV de données courantes (sinon simulation)")
    parser.add_argument("--output", default=None, help="Chemin du rapport HTML de sortie")
    args = parser.parse_args()
    generate_report(args.config, args.current, args.output)