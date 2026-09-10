#!/usr/bin/env python3
"""
pull_models.py — H&M Retail Intelligence

Prépare les modèles candidats dans Ollama avant le benchmark.

Important :
    Le conteneur benchmark n'essaie plus de détecter le GPU avec nvidia-smi.
    Le placement CPU/GPU est déterminé par Ollama au moment où chaque
    modèle est réellement chargé pendant le benchmark.
"""

import os
import sys
import time
import json
import requests

from config import CANDIDATE_MODELS, OLLAMA_HOST


HOST = os.environ.get("OLLAMA_HOST", OLLAMA_HOST)


# Nombre de tentatives par modèle en cas de coupure réseau.
MAX_PULL_ATTEMPTS = 3

# Délai entre deux tentatives, avec backoff progressif.
RETRY_BASE_DELAY_SEC = 10

# Timeout pour joindre l'API Ollama.
TAGS_TIMEOUT_SEC = 30

# Timeout d'inactivité par tentative de pull (pas une durée totale : `requests`
# relance ce délai à chaque paquet reçu — voir doc `requests`, "timeout is not
# a time limit on the entire response download"). Une valeur de 3600s laissait
# un pull réellement bloqué (connexion coupée en silence, souvent tout à la
# fin du transfert) attendre une heure avant le retry automatique ci-dessous,
# alors que le blob est déjà quasi complet et repris quasi instantanément au
# retry suivant (blobs partiels conservés par Ollama). 120s suffit largement
# pour un transfert réellement actif, quelle que soit sa taille totale.
PULL_TIMEOUT_SEC = 120


def print_header(text: str):
    print(f"\n{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}")


def get_already_pulled() -> set:
    """
    Retourne les modèles déjà présents dans Ollama.
    """
    try:
        r = requests.get(
            f"{HOST}/api/tags",
            timeout=TAGS_TIMEOUT_SEC,
        )
        r.raise_for_status()

        tags = r.json().get("models", [])

        return {m["name"] for m in tags}

    except Exception as e:
        print(
            f"[WARN] Impossible de lister les modèles existants : {e}"
        )
        return set()


def _pull_attempt(model_id: str) -> bool:
    """
    Une seule tentative de pull.

    Retourne False sur erreur réseau ou erreur explicite
    renvoyée par Ollama.
    """
    with requests.post(
        f"{HOST}/api/pull",
        json={
            "name": model_id,
            "stream": True,
        },
        stream=True,
        timeout=PULL_TIMEOUT_SEC,
    ) as r:

        r.raise_for_status()

        last_status = ""

        for line in r.iter_lines():

            if not line:
                continue

            data = json.loads(line)

            status = data.get("status", "")

            if status != last_status:
                print(f"     {status}")
                last_status = status

            if data.get("error"):
                print(f"  [ERROR] {data['error']}")
                return False

    return True


def pull_model(model_id: str) -> bool:
    """
    Pull un modèle avec plusieurs tentatives en cas de problème réseau.
    """
    for attempt in range(
        1,
        MAX_PULL_ATTEMPTS + 1,
    ):

        print(
            f"\n  → Pull en cours : {model_id} "
            f"(tentative {attempt}/{MAX_PULL_ATTEMPTS}) ..."
        )

        try:

            if _pull_attempt(model_id):

                print(
                    f"  ✓ {model_id} prêt."
                )

                return True

        except Exception as e:

            print(
                f"  [ERROR] Pull échoué pour {model_id} : {e}"
            )

        if attempt < MAX_PULL_ATTEMPTS:

            delay = RETRY_BASE_DELAY_SEC * attempt

            print(
                f"  ... nouvelle tentative dans {delay}s "
                "(reprend les blobs déjà téléchargés)"
            )

            time.sleep(delay)

        else:

            print(
                f"  [ERREUR] {model_id} : échec après "
                f"{MAX_PULL_ATTEMPTS} tentatives, abandon."
            )

    return False


def main():

    print_header(
        "H&M Retail Intelligence — Pull des modèles LLM"
    )

    print(f"  Ollama host : {HOST}")

    print(
        "  Matériel    : déterminé par Ollama pendant "
        "l'inférence"
    )

    print(
        "  Filtrage matériel : désactivé"
    )

    print(
        "  → Tous les modèles candidats seront préparés."
    )


    already_pulled = get_already_pulled()

    # Aucun modèle n'est éliminé ici sur la base du matériel.
    #
    # La raison est importante :
    #
    # benchmark -> nvidia-smi
    #
    # ne permet pas de savoir si Ollama utilise réellement le GPU,
    # puisque Ollama tourne dans un autre conteneur.
    #
    # Ollama décidera lui-même du placement CPU/GPU lorsque le modèle
    # sera chargé.

    eligible = CANDIDATE_MODELS.copy()


    print("\n  Modèles candidats :")

    for model in eligible:

        print(
            f"  ✓ {model['label']}"
        )


    print(
        f"\n  → {len(eligible)} modèle(s) à préparer."
    )


    # Pull des plus petits modèles en premier.
    pull_order = sorted(
        eligible,
        key=lambda m: m["params_b"],
    )


    pulled_ok = []

    for model in pull_order:

        model_id = model["id"]

        if model_id in already_pulled:

            print(
                f"\n  ✓ {model_id} déjà présent, skip."
            )

            pulled_ok.append(model_id)

        else:

            if pull_model(model_id):

                pulled_ok.append(model_id)


    print_header("Résumé des pulls")


    for model_id in pulled_ok:

        print(
            f"  ✓ {model_id}"
        )


    if not pulled_ok:

        print(
            "[ERREUR] Aucun modèle disponible pour le benchmark."
        )

        sys.exit(1)


    os.makedirs(
        "/workspace/results",
        exist_ok=True,
    )


    # Le matériel réel sera détecté par benchmark.py après
    # chargement effectif du modèle dans Ollama.
    hardware_info = {
        "source": "ollama_runtime",
        "type": "deferred",
    }


    with open(
        "/workspace/results/hardware_info.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            hardware_info,
            f,
            indent=2,
            ensure_ascii=False,
        )


    with open(
        "/workspace/results/eligible_models.json",
        "w",
        encoding="utf-8",
    ) as f:

        json.dump(
            [
                model
                for model in eligible
                if model["id"] in pulled_ok
            ],
            f,
            indent=2,
            ensure_ascii=False,
        )


    print(
        "\n  Modèles sauvegardés → "
        "/workspace/results/eligible_models.json"
    )

    print(
        "  Matériel : détection différée → "
        "benchmark.py / Ollama API"
    )


if __name__ == "__main__":
    main()