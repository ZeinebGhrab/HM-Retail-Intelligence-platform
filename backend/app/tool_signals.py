# ============================================================
# tool_signals.py — marqueur explicite pour signaler qu'un outil n'a PAS pu
# produire de donnée réelle (client introuvable, service indisponible,
# profil incomplet...).
#
# Pourquoi : demander au LLM de génération (rag_pipeline.py) de DEVINER
# depuis le texte du contexte si une donnée est "disponible" ou non s'est
# montré non fiable en test réel (2026-08-31) — même contexte, deux essais
# consécutifs, une fois la vraie valeur restituée correctement, une fois
# une formule et un chiffre entièrement inventés. Le code Python sait déjà
# avec certitude si un outil a réussi ou non : ce marqueur permet à
# rag_pipeline.py de court-circuiter l'appel LLM de génération dans ce cas
# — zéro risque d'hallucination sur ce chemin, et plus rapide (un appel
# Ollama en moins), pas plus lent comme le serait un nouvel essai.
#
# Module séparé (pas dans tools/__init__.py) pour éviter tout import
# circulaire : chaque sous-module de tools/ (profile.py, history.py...) en
# a besoin, et tools/__init__.py importe lui-même depuis ces sous-modules.
# ============================================================
from __future__ import annotations

_PREFIX = "[INDISPONIBLE] "


def unavailable(message: str) -> str:
    """Enveloppe un message de type 'client introuvable'/'service down'/
    'profil incomplet' avec le marqueur d'indisponibilité."""
    return _PREFIX + message


def is_unavailable(text: str) -> bool:
    return text.startswith(_PREFIX)


def strip_marker(text: str) -> str:
    return text[len(_PREFIX):] if is_unavailable(text) else text
