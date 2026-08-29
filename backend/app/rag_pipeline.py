# ============================================================
# rag_pipeline.py — Pipeline RAG à deux passes Ollama :
#   1. Routage : le LLM choisit un outil (tools.SYSTEM_TOOL_CALLING)
#   2. Génération : le LLM formule la réponse à partir du résultat de
#      l'outil (contexte injecté), comme django_api/history/rag_pipeline.py
#      le fait déjà pour les données visiteurs (CSV) — même principe,
#      appliqué ici à des outils structurés plutôt qu'à un CSV unique.
# ============================================================
from __future__ import annotations

import json

import ollama_client
from config import MAX_HISTORY_TURNS, OLLAMA_MODEL
from tools import SYSTEM_TOOL_CALLING, run_tool

SYSTEM_ANSWER = """\
Tu es l'assistant analytique de la plateforme H&M Retail Intelligence.
Réponds en français, de façon concise et claire.
Utilise UNIQUEMENT les données du CONTEXTE ci-dessous — ne fabrique jamais de
chiffre absent du contexte. Si le contexte indique qu'une information est
indisponible, dis-le clairement plutôt que d'inventer une réponse.
Les valeurs de dépense (total_spend, avg_basket_value, panier moyen, indice
de dépense...) sont des indices SANS UNITÉ, normalisés par le dataset Kaggle
H&M lui-même (le vrai prix n'est pas récupérable, ce n'est pas un secret que
tu peux "deviner" ou reconstituer) — CE NE SONT PAS des montants en devise.
Interdiction stricte, sur ces valeurs UNIQUEMENT :
- ne jamais ajouter un symbole monétaire ($, €, £...) ni une estimation du
  type "(soit environ X$)" — même entre parenthèses, même en approximation ;
- ne jamais les reformuler en pourcentage (0.649 n'est PAS "64,9%") ;
- ne jamais tenter de les convertir dans une autre unité.
Recopie ces indices tels quels (ex. "indice de dépense : 0.6490"), sans
aucune reformulation. Ceci ne s'applique PAS aux champs explicitement en %
dans le contexte (ex. part_CA_totale_%), qui restent des pourcentages.\
"""


def _clean_json(text: str) -> str:
    text = text.strip()
    if "```" in text:
        for part in text.split("```"):
            cleaned = part.strip()
            if cleaned.startswith("json"):
                cleaned = cleaned[4:].strip()
            if cleaned.startswith("{"):
                return cleaned
    start = text.find("{")
    end = text.rfind("}") + 1
    return text[start:end] if start != -1 and end > start else text


def _format_history(history: list[dict]) -> str:
    recent = history[-MAX_HISTORY_TURNS:]
    lines = [
        f"{'Utilisateur' if h['role'] == 'user' else 'Assistant'} : {h['content']}"
        for h in recent
    ]
    return "\n".join(lines)


def answer_question(
    question: str,
    customer_id: str | None,
    history: list[dict],
) -> dict:
    router_reply = ollama_client.chat(
        [{"role": "user", "content": question}],
        system=SYSTEM_TOOL_CALLING,
    )

    tool_name = None
    try:
        parsed = json.loads(_clean_json(router_reply))
        tool_name = parsed.get("tool")
        parameters = parsed.get("parameters") or {}
    except (json.JSONDecodeError, AttributeError):
        parameters = {}

    if tool_name is None:
        context = "Aucune donnée structurée disponible pour cette question."
    else:
        context = run_tool(
            tool_name,
            parameters,
            customer_id=customer_id,
            question=question,
        )

    history_block = _format_history(history)
    prompt = (
        (f"=== HISTORIQUE DE LA CONVERSATION ===\n{history_block}\n\n" if history_block else "")
        + f"=== CONTEXTE ===\n{context}\n\n"
        + f"=== QUESTION ===\n{question}"
    )

    answer = ollama_client.chat(
        [{"role": "user", "content": prompt}],
        system=SYSTEM_ANSWER,
    )

    return {"answer": answer, "model": OLLAMA_MODEL, "tool_used": tool_name}
