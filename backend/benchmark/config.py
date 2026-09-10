# ============================================================
# config.py — H&M Retail Intelligence — Benchmark LLM (RAG)
# Emplacement : backend/benchmark/config.py
# Configuration du benchmark : modèles, seuils et inférence.
# Le matériel réel est détecté par benchmark.py via Ollama.
# ============================================================

# Ollama host (override via env OLLAMA_HOST)
OLLAMA_HOST = "http://ollama:11434"


# ── Modèles candidats ────────────────────────────────────────
#
# Tous les modèles sont proposés au benchmark.
# Le benchmark ne filtre plus les modèles avec nvidia-smi :
# Ollama est la source de vérité pour le placement CPU/GPU.
#
CANDIDATE_MODELS = [
    # Modèles 7B commentés par défaut : sans GPU, chaque run (warmup + N_RUNS,
    # cf. get_n_runs) devient extrêmement lent sur ces tailles, et le job peut
    # prendre des heures pour les 5 modèles. Réactive-les si une machine avec
    # GPU NVIDIA (+ nvidia-container-toolkit) est disponible.
    # {
    #     "id": "qwen2.5:7b-instruct-q4_K_M",
    #     "label": "Qwen 2.5 7B (q4_K_M)",
    #     "params_b": 7,
    #     "notes": "Meilleur FR/AR, nécessite un GPU pour rester fluide",
    # },
    # {
    #     "id": "mistral:7b-instruct-v0.3-q4_K_M",
    #     "label": "Mistral 7B Instruct v0.3 (q4_K_M)",
    #     "params_b": 7,
    #     "notes": "Rapide sur GPU, bon JSON",
    # },
    # Qwen 3 4B testé et écarté (pas commenté pour du GPU comme les 7B
    # ci-dessus — un problème structurel différent, indépendant du matériel) :
    # son template de chat (nativement conçu pour le tool calling) fait
    # gonfler le même prompt système à ~7640 tokens une fois rendu, contre
    # largement moins pour les autres modèles testés à contenu texte égal.
    # Confirmé via les logs serveur Ollama : "request (7640 tokens) exceeds
    # the available context size (2048 tokens)". Le num_ctx du profil CPU
    # (INFERENCE_OPTIONS_CPU, voir plus bas) est délibérément réduit pour
    # rester rapide sur les autres modèles ; le relever assez pour Qwen 3 4B
    # (~12000+) ralentirait aussi tous les autres modèles et invaliderait la
    # comparaison avec les runs précédents. Combiné à un premier appel à froid
    # mesuré à ~55s (surtout du prompt-eval), pas un bon compromis ici face à
    # qwen2.5:3b-instruct-q4_K_M, déjà validé à 97/100 recommended=true.
    # {
    #     "id": "qwen3:4b-instruct-2507-q4_K_M",
    #     "label": "Qwen 3 4B Instruct (q4_K_M)",
    #     "params_b": 4,
    #     "notes": "Écarté : template chat trop verbeux pour num_ctx=2048 (CPU)",
    # },
    {
        "id": "qwen2.5:3b-instruct-q4_K_M",
        "label": "Qwen 2.5 3B (q4_K_M)",
        "params_b": 3,
        "notes": "Bon compromis, tourne correctement en CPU",
    },
    {
        "id": "llama3.2:3b-instruct-q4_K_M",
        "label": "Llama 3.2 3B (q4_K_M)",
        "params_b": 3,
        "notes": "Bon compromis vitesse/qualité en CPU",
    },
    {
        "id": "llama3.2:1b-instruct-q4_K_M",
        "label": "Llama 3.2 1B (q4_K_M)",
        "params_b": 1,
        "notes": "Le plus léger, baseline de vitesse en CPU",
    },
]


# ── Seuils de performance ────────────────────────────────────
#
# Les seuils dépendent du placement réel du modèle dans Ollama.
# Pour un modèle entièrement GPU : profil GPU.
# Pour CPU ou placement mixte : profil CPU conservateur.
#
THRESHOLDS_GPU = {
    "ttft_max_sec": 1.5,
    "throughput_min_tps": 20.0,
    "throughput_hard_min": 10.0,
    "json_success_min_pct": 95.0,
}

THRESHOLDS_CPU = {
    "ttft_max_sec": 5.0,
    "throughput_min_tps": 8.0,
    "throughput_hard_min": 3.0,
    "json_success_min_pct": 90.0,
}


def get_thresholds(hw_type: str) -> dict:
    """
    Retourne les seuils correspondant au profil d'inférence.

    "gpu" utilise les seuils GPU.
    Tout autre profil (cpu, mixed, unknown) utilise les seuils CPU
    de manière conservatrice.
    """
    return THRESHOLDS_GPU if hw_type == "gpu" else THRESHOLDS_CPU


# ── Paramètres d'inférence ───────────────────────────────────

INFERENCE_OPTIONS_GPU = {
    "temperature": 0.1,
    "top_p": 0.9,
    "num_ctx": 4096,
    "num_predict": 1024,
}

INFERENCE_OPTIONS_CPU = {
    "temperature": 0.1,
    "top_p": 0.9,
    "num_ctx": 2048,
    "num_predict": 512,
}


def get_inference_options(hw_type: str) -> dict:
    """
    Retourne les paramètres d'inférence adaptés au profil matériel.
    """
    return (
        INFERENCE_OPTIONS_GPU
        if hw_type == "gpu"
        else INFERENCE_OPTIONS_CPU
    )


# ── Nombre de répétitions ────────────────────────────────────

N_WARMUP = 1

N_RUNS_GPU = 3
N_RUNS_CPU = 2


def get_n_runs(hw_type: str) -> int:
    """
    Plus de répétitions lorsque l'inférence est entièrement GPU.
    CPU et mixed utilisent le profil conservateur.
    """
    return N_RUNS_GPU if hw_type == "gpu" else N_RUNS_CPU


# ── Fichiers de sortie ────────────────────────────────────────

RESULTS_DIR = "/workspace/results"

DATASET_PATH = "/workspace/dataset/tool_calling_queries.json"


# ── Nettoyage Ollama ──────────────────────────────────────────
#
# True  : garde uniquement le modèle gagnant.
# False : garde tous les modèles pullés.
#
KEEP_ONLY_BEST_MODEL = False