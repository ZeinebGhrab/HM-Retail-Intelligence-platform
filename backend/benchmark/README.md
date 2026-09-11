# `backend/benchmark/` — Benchmark LLM (sélection du modèle Ollama)

Compare plusieurs modèles Ollama exécutables en local pour choisir celui utilisé par le chatbot
([`backend/app/`](../app/README.md)), sur deux critères : la précision du **tool-calling** (choisir
le bon outil pour une question donnée) et la résistance à l'**hallucination**. Appels REST directs à
Ollama (`/api/chat`, `/api/pull`, `/api/delete`) — pas de framework LangChain/LlamaIndex, disproportionné
pour ce besoin.

---

## Modèles candidats

Définis dans [`config.py`](./config.py) (`CANDIDATE_MODELS`) :

| Modèle | Notes |
|---|---|
| `qwen2.5:3b-instruct-q4_K_M` | Bon compromis, tourne correctement en CPU |
| `llama3.2:3b-instruct-q4_K_M` | Bon compromis vitesse/qualité en CPU |
| `llama3.2:1b-instruct-q4_K_M` | Le plus léger, sert de baseline de vitesse |

Des modèles 7B et `qwen3:4b-instruct-2507-q4_K_M` sont présents dans le fichier mais **commentés** :
les 7B nécessitent un GPU pour rester praticables (voir `config.py` pour les réactiver), et Qwen 3 4B
a été testé puis écarté — son template de chat fait gonfler le prompt système à ~7640 tokens, au-delà
du `num_ctx=2048` utilisé en profil CPU (voir le commentaire détaillé dans `config.py`).

## Méthodologie

1. [`pull_models.py`](./pull_models.py) télécharge chaque modèle candidat via Ollama.
2. [`benchmark.py`](./benchmark.py) exécute, pour chaque modèle, un appel de warmup puis plusieurs
   runs (2 en CPU, 3 en GPU — voir `get_n_runs`) contre le jeu de questions
   [`dataset/tool_calling_queries.json`](./dataset/tool_calling_queries.json), et mesure :

   | Critère | Poids |
   |---|---:|
   | Sélection du bon outil | 25 |
   | Résistance à l'hallucination | 15 |
   | Temps avant premier token (TTFT) | 20 |
   | Débit (tokens/s) | 20 |
   | Validité du JSON produit | 20 |

   Le profil de seuils appliqué (GPU vs CPU, plus permissif) dépend du placement réel du modèle,
   détecté via l'API Ollama — voir `THRESHOLDS_GPU`/`THRESHOLDS_CPU` dans `config.py`.
3. Le modèle au score le plus élevé devient le `winner`, à condition de valider tous les seuils
   obligatoires (sinon `recommended: false`, à vérifier manuellement avant déploiement).

**Nettoyage** : `KEEP_ONLY_BEST_MODEL` dans `config.py` contrôle si les modèles non retenus sont
supprimés d'Ollama après le run (`True`) ou conservés (`False`, valeur par défaut actuelle — tous les
modèles testés restent installés).

## Résultat actuel

Voir [`results/benchmark_report.json`](./results/benchmark_report.json) — gagnant :
**`qwen2.5:3b-instruct-q4_K_M`**, score 97/100, `recommended: true`. C'est le modèle utilisé par
défaut par le chatbot (`backend/app/config.py`, `OLLAMA_MODEL`).

⚠️ **Dérive avec le chatbot** : `dataset/tool_calling_queries.json` (et le prompt système utilisé ici
pour le routage) datent du palier d'outils précédent du chatbot (avant le retrait de
`predict_customer_spend`/`predict_customer_status`, voir `backend/app/tools/__init__.py`). Le
benchmark n'a pas été rejoué contre le palier actuel — le score 97/100 reste valable pour le choix du
modèle lui-même (capacité générale de tool-calling/anti-hallucination), mais le dataset ne couvre plus
exactement les outils tels qu'ils existent aujourd'hui.

## Lancement

Ne démarre **pas** avec un simple `docker compose up` (`profiles: benchmark`) :

```bash
docker compose --profile benchmark up --build benchmark
```

[`run_once.sh`](./run_once.sh) attend qu'Ollama réponde, puis ne relance **rien** si
`results/benchmark_report.json` existe déjà. Pour forcer une nouvelle exécution, supprime ce fichier
(ou tout `results/`) avant de relancer le conteneur.
