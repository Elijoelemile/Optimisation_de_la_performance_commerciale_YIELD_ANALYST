# 🧭 NG Travel — Analyse & Pilotage Yield

Application d'analyse des ventes et d'aide à la décision **Yield Management** pour
**NG Travel**, tour-opérateur spécialisé sur la Grèce (Rhodes, Crète, Corfou,
Grèce continentale, Thessalonique). Le projet couvre toute la chaîne : de la
donnée brute (**ETL** → Data Lake → Data Warehouse) jusqu'au **tableau de bord
interactif** déployable en ligne.

> Environ 18 600 réservations sur deux saisons (2025–2026). Taux de marge global
> mince (≈ 10 %) et ≈ 28 % de dossiers vendus à perte : comprendre et réduire
> cette destruction de valeur est le cœur de la mission.

---

## 📦 Livrables du projet

Trois documents complémentaires, chacun avec un rôle différent :

| Livrable | Rôle | Emplacement |
|---|---|---|
| **Application Streamlit** | Outil interactif, productisé, pour explorer les données et simuler des décisions au quotidien. | `streamlit_app.py` + `pages/` |
| **Rapport de synthèse (PDF)** | Vue d'ensemble condensée — architecture, traitement des données, KPIs, résultats — pour une lecture rapide. | `docs/Rapport_Projet_NG_Travel.pdf` |
| **Notebook d'analyse détaillé** | La démarche pas à pas, avec le code, les contrôles qualité et les visualisations commentées — pour comprendre *comment* on arrive aux résultats, pensé pour un public non technique. | `notebooks/Analyse_NG_Travel.ipynb` |

---

## 🚀 Déploiement sur Streamlit Community Cloud

Le dépôt est prêt à être déployé **sans configuration** (le fichier d'entrée
`streamlit_app.py`, le dossier `pages/` et le `requirements.txt` sont à la
racine, et la base de données est incluse dans `data/`).

1. **Créer un dépôt GitHub** et y pousser ce projet :
   ```bash
   git init
   git add .
   git commit -m "NG Travel — app Yield"
   git branch -M main
   git remote add origin https://github.com/<ton-compte>/<ton-repo>.git
   git push -u origin main
   ```
2. Aller sur **[share.streamlit.io](https://share.streamlit.io)** et se connecter
   avec GitHub.
3. Cliquer **« Create app »** → **« Deploy a public app from GitHub »**.
4. Renseigner :
   - **Repository** : `<ton-compte>/<ton-repo>`
   - **Branch** : `main`
   - **Main file path** : `streamlit_app.py`
5. Cliquer **« Deploy »**. Au bout de 1–2 minutes, l'app est en ligne avec une
   URL publique partageable (idéale pour un rendu de cas pratique).

> Streamlit Cloud installe automatiquement les dépendances depuis
> `requirements.txt` et relance l'app à chaque `git push`.

---

## 💻 Lancer l'application en local

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

L'app s'ouvre sur **http://localhost:8501**. Pour l'arrêter : `Ctrl + C`.

Prérequis : **Python 3.9+** (`python --version` ; sinon
[python.org/downloads](https://www.python.org/downloads/), et sur Windows cocher
« Add Python to PATH »).

---

## 🔑 Configuration — Copilote IA (optionnel)

La page **Copilote IA** génère des résumés en langage naturel via l'**API
Mistral**. C'est une fonctionnalité **optionnelle** : sans clé configurée, le
reste de l'application fonctionne normalement — les boutons du Copilote sont
simplement désactivés, avec un message explicatif.

**En local** — créer `.streamlit/secrets.toml` (déjà exclu par `.gitignore`,
ne jamais le versionner) :

```toml
MISTRAL_API_KEY = "ta_clé_api_mistral"
```

**Sur Streamlit Cloud** — ajouter la même clé dans les *Secrets* de l'app
(page de gestion de l'app → **Settings** → **Secrets**), avec la même syntaxe
TOML. `secrets.toml` étant local et non versionné, cette étape est nécessaire
séparément pour que le Copilote fonctionne en ligne.

---

## 📊 Contenu de l'application

| Page | Contenu |
|---|---|
| **Accueil** | KPI globaux + CA par destination et marge par canal. |
| **Évolution temporelle** | Courbes mensuelles (mesure & axe au choix) + comparaison 2025 vs 2026. |
| **Performance par destination** | Tableau, CA / taux de marge, quadrant « pouvoir de prix », heatmap destination × saison. |
| **Performance par réseau** *(page phare)* | Créateurs / destructeurs de valeur, utilité (marge vs commission). |
| **Performance par axe** | Ville de départ et délai de réservation (vues dédiées), marge par dimension au choix, croisement configurable de 2 axes. |
| **Outil Yield** | Segments à risque, opportunités de hausse de prix, simulateur avec élasticité. |
| **Système de recommandation** | 4 recommandateurs : réseau ↔ produit (filtrage collaboratif), prix cible par segment, hôtels et compagnies aériennes de substitution (benchmarking). |
| **Copilote IA** | Résumé en langage naturel de chaque page, généré à la demande via l'API Mistral (voir Configuration ci-dessus). |
| **Bonus** | Données supplémentaires qui enrichiraient l'analyse (historique des prix, taux d'occupation, etc.). |

Toutes les pages partagent les mêmes **filtres** (saison, destination, canal,
intensité) et un **agrégateur de performance unique** (`perf_par`) pour des
indicateurs cohérents partout.

---

## 📤 Importer vos propres données

Dans la barre latérale (« Base de données »), il est possible d'**importer un
fichier brut** (`.xlsx` ou `.csv`, même schéma que la base NG Travel) à la
place de la base publiée par défaut :

- le fichier est nettoyé et enrichi **en mémoire**, avec exactement la même
  fonction de transformation que le pipeline ETL (`transformer_dataframe`,
  partagée avec `etl/transformation/Transformation.py`) — pas de logique
  dupliquée ni divergente ;
- rien n'est écrit sur le serveur (compatible avec un déploiement en ligne,
  dont le système de fichiers est éphémère) ;
- la base nettoyée peut ensuite être **téléchargée** directement depuis le
  navigateur, en `.csv` ou `.xlsx`, via les boutons prévus à cet effet.

---

## 🔄 Chaîne ETL (dossiers `etl/`, `pipeline_orchestrator/`)

Architecture classique : **Data Lake** (brut) → **Data Warehouse** (raffiné).

```
Source .xlsx ──[etl/extraction/Extraction.py]──▶ Data Lake ──[etl/transformation/Transformation.py]──▶ DataFrame (mémoire)
                                                                                                             │
                                                                          [etl/load/Load.py] ────────────────┘──▶ Data Warehouse (.parquet)
```

- **`etl/extraction/Extraction.py`** — localise le fichier source (n'importe
  où) et le copie dans le Data Lake.
- **`etl/transformation/Transformation.py`** — nettoie et enrichit
  (17 → 41 colonnes), renvoie un DataFrame en mémoire.
- **`etl/load/Load.py`** — écrit la base transformée dans le Data Warehouse
  (nom au choix).
- **`pipeline_orchestrator/pipeline_orchestrator.py`** — **orchestrateur** :
  enchaîne les trois briques de `etl/` ci-dessus en un seul processus, en
  gardant la donnée en mémoire entre Transform et Load.

Chaque sous-dossier de `etl/` est un package Python (`__init__.py`). Les
imports entre modules sont donc absolus (`from etl.extraction.Extraction
import extraction`, etc.) : **`pipeline_orchestrator.py` et `Load.py` doivent
être lancés avec `-m`, depuis la racine du projet** — pas en exécution directe
du fichier.

Régénérer la base depuis un nouveau fichier source, puis alimenter l'app
(à lancer depuis la **racine** du projet) :

```bash
python -m pipeline_orchestrator.pipeline_orchestrator "/chemin/vers/base_de_données_NG_Travel.xlsx" --nom ng_travel_2025_2026
# puis publier la base pour l'app :
cp "Data Warehouse/ng_travel_2025_2026.parquet" data/
```

### 📝 Journalisation (`logger_config.py`)

Chaque étape du pipeline (et l'application Streamlit) journalise ses
événements via un gestionnaire de log centralisé : `logger_config.py`
(racine du projet). Deux fichiers, dans `log/` (non versionné, généré à
l'exécution) :

- **`log/ng_travel.log`** — log technique, horodaté et classé par niveau
  (`INFO` / `WARNING` / `ERROR`), écrit sur la console **et** sur disque
  (fichier **tournant** : 5 Mo par fichier, 3 fichiers d'historique
  conservés, les plus anciens purgés automatiquement).
- **`log/historique_orchestration.log`** — historique **permanent** des
  exécutions du pipeline ETL (démarrage / succès / échec, une ligne par
  exécution), jamais tourné ni purgé — notamment alimenté par la tâche
  planifiée quotidienne (voir ci-dessous).

```python
from logger_config import get_logger, log_historique
log = get_logger(__name__)
log.info("...")
log_historique("Orchestration terminée avec succès.")
```

### ⏰ Rafraîchissement automatique quotidien (8h00)

Une tâche planifiée Windows relance le pipeline **tous les jours à 8h00**,
sans intervention manuelle :

- **`pipeline_orchestrator/tache_quotidienne.py`** — retransforme le fichier
  déjà présent dans le Data Lake (Transform → Load, pas de nouvelle
  extraction) et republie le résultat dans `data/` (copie **locale**
  uniquement — aucun commit/push Git automatique, ça reste une action
  manuelle et volontaire, comme partout ailleurs dans ce projet).
- **`pipeline_orchestrator/installer_tache_planifiee.ps1`** — installe la
  tâche dans le Planificateur de tâches Windows (à exécuter une seule fois) :
  ```powershell
  powershell -ExecutionPolicy Bypass -File pipeline_orchestrator\installer_tache_planifiee.ps1
  ```

Cette tâche ne fonctionne que **localement** (le PC doit être allumé, session
ouverte, à 8h00 — elle se rattrape au démarrage suivant sinon) : Streamlit
Cloud n'a pas de mécanisme de tâche planifiée. Chaque exécution — automatique
ou manuelle (`python -m pipeline_orchestrator.tache_quotidienne`) — est
journalisée dans `log/historique_orchestration.log`.

Vérifier que la tâche est active :
```powershell
Get-ScheduledTask -TaskName "NG Travel - Rafraichissement quotidien"
```

### Les trois emplacements de données (important)

| Dossier | Contenu | Versionné sur Git ? | Rôle |
|---|---|---|---|
| **`Data Lake/`** | Base **brute** (`.xlsx`), copie fidèle de la source | ❌ ignoré | Zone d'atterrissage du pipeline (local). |
| **`Data Warehouse/`** | Base **transformée** (`.parquet`), sortie du pipeline | ❌ ignoré | Zone raffinée du pipeline (local). |
| **`data/`** | Copie **publiée** de la base transformée | ✅ versionné | Base lue par l'app, y compris **en ligne**. |

**Pourquoi cette distinction ?** Les zones `Data Lake/` et `Data Warehouse/` sont
des sorties du pipeline : par convention, on ne les versionne pas sur Git (ce
sont des données générées). Elles sont présentes en local pour refléter
l'architecture, mais **ignorées par Git** (voir `.gitignore`).

Or, un fichier ignoré par Git **n'est pas envoyé sur GitHub** — donc l'app
déployée sur Streamlit Cloud ne pourrait pas lire une base située dans un dossier
ignoré. C'est pourquoi la base transformée est **publiée** dans `data/` (dossier
versionné) : c'est cette copie que l'app utilise, en local comme en ligne.

> Conséquence assumée : la base **brute** et la sortie **Data Warehouse** restent
> sur ta machine et n'apparaissent pas sur GitHub. Seule la copie publiée dans
> `data/` y figure. Si tu souhaites au contraire montrer la base brute sur
> GitHub (pour la reproductibilité du jury), retire les lignes correspondantes
> du `.gitignore`.

---

## 📁 Structure du dépôt

```
.
├── streamlit_app.py            # Point d'entrée de l'app (Accueil / KPI)
├── utils.py                    # Fonctions partagées (chargement, filtres, perf)
├── pages/                      # Les 8 pages d'analyse
│   ├── 1_Évolution_temporelle.py
│   ├── 2_Destinations.py
│   ├── 3_Réseaux.py
│   ├── 4_Axes_complémentaires.py
│   ├── 5_Outil_Yield.py
│   ├── 6_Système_de_recommandation.py
│   ├── 7_Copilote_IA.py
│   └── 8_Bonus.py
├── .streamlit/
│   ├── config.toml             # Thème visuel (versionné)
│   └── secrets.toml            # Clé API Mistral (local, ignoré par Git)
├── data/
│   └── ng_travel_2025_2026.parquet   # Base PUBLIÉE, lue par l'app (versionnée)
├── Data Lake/                        # Base BRUTE (local, ignoré par Git)
│   └── base_de_données_NG_Travel.xlsx
├── Data Warehouse/                   # Base TRANSFORMÉE (local, ignoré par Git)
│   └── ng_travel_2025_2026.parquet
├── etl/
│   ├── extraction/
│   │   └── Extraction.py
│   ├── transformation/
│   │   └── Transformation.py
│   └── load/
│       └── Load.py
├── pipeline_orchestrator/
│   ├── pipeline_orchestrator.py        # Orchestrateur E→T→L (enchaîne etl/)
│   ├── tache_quotidienne.py            # Rafraîchissement quotidien (Transform→Load, 8h)
│   └── installer_tache_planifiee.ps1   # Installe la tâche planifiée Windows
├── logger_config.py                   # Gestionnaire de log centralisé (ETL + app)
├── log/                               # Fichiers de log générés (local, ignoré par Git)
├── notebooks/
│   └── Analyse_NG_Travel.ipynb        # Notebook d'exploration détaillée (livrable)
├── docs/
│   ├── Rapport_Projet_NG_Travel.pdf          # Rapport de synthèse (livrable)
│   └── Dictionnaire_donnees_NG_Travel.xlsx   # Dictionnaire des 41 variables
├── requirements.txt
├── .gitignore
└── README.md
```

> Les dossiers `Data Lake/` et `Data Warehouse/` sont présents localement pour
> refléter l'architecture ETL, mais **ignorés par Git**. L'app lit la copie
> publiée dans `data/`. Voir la section « Les trois emplacements de données ».

---

## 📖 Dictionnaire de données

Le fichier `docs/Dictionnaire_donnees_NG_Travel.xlsx` décrit les **41 variables**
de la base transformée : nature (Origine / Dérivée), type, description, exemple,
complétude et nombre de valeurs distinctes. Il constitue le **contrat de
données** en sortie du Data Warehouse.

---

## ⚠️ Limites & pistes

- La saison **2026 est encore en cours de remplissage** : comparer 2025 vs 2026
  à stade équivalent.
- Le **simulateur de prix** (Outil Yield) et les **prix cibles** (Système de
  recommandation) utilisent des hypothèses simplifiées (élasticité non mesurée,
  volumes supposés intégralement transférables) — des plafonds théoriques à
  valider avant toute décision, pas des prévisions.
- Le **Copilote IA** nécessite une clé API Mistral (facultative, coût à la
  requête) — l'app fonctionne normalement sans elle.
- **Données bonus** qui enrichiraient l'analyse : historique des prix, taux
  d'occupation hôtelière, prix concurrents, coûts aériens, budget marketing par
  réseau, statut d'annulation.

---

*Projet réalisé dans le cadre d'un cas pratique de Yield Management.*
