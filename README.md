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

## 📊 Contenu de l'application

| Page | Contenu |
|---|---|
| **Accueil** | KPI globaux + CA par destination et marge par canal. |
| **Évolution temporelle** | Courbes mensuelles (mesure & axe au choix) + comparaison 2025 vs 2026. |
| **Destinations** | Tableau, CA / taux de marge, quadrant « pouvoir de prix », heatmap destination × saison. |
| **Réseaux** *(page phare)* | Créateurs / destructeurs de valeur, utilité (marge vs commission). |
| **Performance par axe** | Marge par dimension (dont type de produit) + croisement configurable de 2 axes. |
| **Outil Yield** | Segments à risque, opportunités de hausse de prix, simulateur avec élasticité. |
| **Recommandations** | Leviers calculés automatiquement + données bonus à demander. |

Toutes les pages partagent les mêmes **filtres** (saison, destination, canal,
intensité) et un **agrégateur de performance unique** (`perf_par`) pour des
indicateurs cohérents partout.

---

## 🔄 Chaîne ETL (dossiers `etl/`, `pipeline_etl/`, `data_preparation/`)

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
- **`pipeline_etl/pipeline_etl.py`** — enchaîne les trois étapes en un seul
  processus (orchestrateur).
- **`data_preparation/data_prep.py`** — variante autonome (E+T+L en un seul
  script) pour préparer rapidement la base sans passer par le pipeline complet.

Chaque sous-dossier de `etl/` est un package Python (`__init__.py`). Les
imports entre modules sont donc absolus (`from etl.extraction.Extraction
import extraction`, etc.) : **`pipeline_etl.py` et `Load.py` doivent être
lancés avec `-m`, depuis la racine du projet** — pas en exécution directe du
fichier.

Régénérer la base depuis un nouveau fichier source, puis alimenter l'app
(à lancer depuis la **racine** du projet) :

```bash
python -m pipeline_etl.pipeline_etl "/chemin/vers/base_de_données_NG_Travel.xlsx" --nom ng_travel_2025_2026
# puis publier la base pour l'app :
cp "Data Warehouse/ng_travel_2025_2026.parquet" data/
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
├── pages/                      # Les 6 pages d'analyse
│   ├── 1_Évolution_temporelle.py
│   ├── 2_Destinations.py
│   ├── 3_Réseaux.py
│   ├── 4_Axes_complémentaires.py
│   ├── 5_Outil_Yield.py
│   └── 6_Recommandations.py
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
├── pipeline_etl/
│   └── pipeline_etl.py               # Orchestrateur E→T→L
├── data_preparation/
│   └── data_prep.py                  # Variante autonome (préparation rapide)
├── docs/
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
- Le **simulateur de prix** utilise une élasticité paramétrable mais non mesurée,
  à calibrer avec des données réelles.
- **Données bonus** qui enrichiraient l'analyse : historique des prix, taux
  d'occupation hôtelière, prix concurrents, coûts aériens, budget marketing par
  réseau, statut d'annulation.

---

*Projet réalisé dans le cadre d'un cas pratique de Yield Management — NG Travel.*
