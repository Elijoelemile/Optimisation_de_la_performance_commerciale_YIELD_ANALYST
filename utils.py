"""
utils.py — Fonctions partagées de l'app Streamlit NG Travel
============================================================

Regroupe tout ce que les pages réutilisent :
  - chargement des données (depuis le Data Warehouse, avec cache),
  - barre latérale de filtres commune,
  - helpers de formatage (euros, %, entiers façon FR),
  - calcul des KPI.

Les pages importent simplement :
    from utils import setup_page, charger_donnees, filtres_lateraux, kpis, fmt_euro
"""

from __future__ import annotations
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from etl.transformation.Transformation import transformer_dataframe
from logger_config import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constantes d'affichage
# ---------------------------------------------------------------------------

APP_TITRE = "NG Travel — Pilotage Yield"
APP_ICON = "🧭"

# Ordre logique des intensités de saison (pour trier les graphiques)
ORDRE_SAISON_TOURISTIQUE = [
    "Basse saison (avr./mai/oct.)",
    "Épaule (juin/sept.)",
    "Haute saison (juil.-août)",
    "Hors saison",
    "NON RENSEIGNÉ",
]
ORDRE_DELAI = [
    "Last minute (0-14 j)",
    "Court (15-30 j)",
    "Moyen (31-60 j)",
    "Long (61-120 j)",
    "Très anticipé (>120 j)",
    "Anomalie (<0)",
    "NON RENSEIGNÉ",
]

# Couleurs par grand canal (cohérence visuelle sur toute l'app)
COULEURS_CANAL = {"B2B": "#2563eb", "B2C": "#16a34a", "GROUPES": "#d97706"}

# Couleur distincte par page de navigation (palette Méditerranée / Grèce),
# dans l'ordre d'apparition dans le menu latéral (après la page d'accueil).
COULEURS_NAV = [
    {"bg": "#DCEEFB", "text": "#0B5394"},  # 1. Évolution temporelle — bleu Égée
    {"bg": "#D6F5F0", "text": "#0F766E"},  # 2. Destinations — turquoise
    {"bg": "#FBE3D6", "text": "#B4502A"},  # 3. Réseaux — terracotta
    {"bg": "#E6F0D6", "text": "#4D6B1F"},  # 4. Axes complémentaires — olivier
    {"bg": "#FBEFD1", "text": "#92650B"},  # 5. Outil Yield — ocre/soleil
    {"bg": "#E0E7FB", "text": "#3730A3"},  # 6. Système de recommandation — indigo
    {"bg": "#DCE4F5", "text": "#31437A"},  # 7. Copilote IA — bleu nuit
    {"bg": "#FDECC8", "text": "#9A5B0F"},  # 8. Bonus — miel
]


def _injecter_css_nav():
    """Colore chaque bouton du menu latéral avec sa propre couleur (palette
    Méditerranée / Grèce). Ciblage par position (2e à 7e lien, la page
    d'accueil restant en position 1), car Streamlit ne permet pas de nommer
    ces liens individuellement en mode multipage implicite (dossier pages/).
    """
    regles = []
    for i, c in enumerate(COULEURS_NAV, start=2):  # position 1 = accueil
        regles.append(f"""
        [data-testid="stSidebarNavLinkContainer"]:nth-of-type({i}) a {{
            background-color: {c['bg']} !important;
            border-radius: 8px !important;
        }}
        [data-testid="stSidebarNavLinkContainer"]:nth-of-type({i}) a * {{
            color: {c['text']} !important;
            font-weight: 600 !important;
        }}
        """)
    st.markdown(f"<style>{''.join(regles)}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Configuration de page + en-tête commun
# ---------------------------------------------------------------------------

def setup_page(sous_titre: str, icon: str = APP_ICON):
    """À appeler EN PREMIER dans chaque page (contrainte Streamlit)."""
    st.set_page_config(page_title=f"{APP_TITRE}", page_icon=icon, layout="wide")
    _injecter_css_nav()
    st.title("Sales performance tool")
    st.subheader(f"{icon}  {sous_titre}")


# ---------------------------------------------------------------------------
# Chargement des données (depuis le Data Warehouse)
# ---------------------------------------------------------------------------

# Répertoire de ce fichier : sert d'ancre pour retrouver les données quel que
# soit le répertoire d'exécution (local OU Streamlit Community Cloud).
BASE_DIR = Path(__file__).resolve().parent

# Emplacements candidats pour trouver la base transformée, par ordre de priorité.
# Chemins ABSOLUS (ancrés sur BASE_DIR) pour être insensibles au dossier courant.
CHEMINS_CANDIDATS = [
    BASE_DIR / "data",            # dépôt GitHub / Streamlit Cloud
    BASE_DIR / "Data Warehouse",  # zone raffinée de l'ETL en local
    BASE_DIR,                     # à côté de l'app
]


def _lister_bases() -> list[Path]:
    """Liste les fichiers .parquet disponibles dans les zones candidates.

    Priorité aux dossiers dans l'ordre de CHEMINS_CANDIDATS : si une même base
    (même nom) existe dans plusieurs zones (ex. data/ ET Data Warehouse/), seule
    celle du dossier prioritaire (data/) est retenue. Comportement identique en
    local et en ligne.
    """
    trouves: list[Path] = []
    for base in CHEMINS_CANDIDATS:
        d = Path(base)
        if d.is_dir():
            trouves.extend(sorted(d.glob("*.parquet")))
    # Dédoublonnage par NOM de fichier, en gardant la 1re occurrence (prioritaire)
    vus_noms, uniques = set(), []
    for f in trouves:
        if f.name not in vus_noms:
            vus_noms.add(f.name)
            uniques.append(f)
    return uniques


@st.cache_data(show_spinner="Chargement de la base…")
def charger_donnees(chemin: str) -> pd.DataFrame:
    """Charge un .parquet du Data Warehouse (mis en cache par Streamlit)."""
    df = pd.read_parquet(chemin)
    # Sécurité : s'assurer que les colonnes datées sont bien des datetimes
    for col in ["date_resa", "date_depart", "mois_depart_periode", "mois_resa_periode"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    log.info("Base publiée chargée : %s (%d lignes).", chemin, len(df))
    return df


@st.cache_data(show_spinner="Transformation ETL du fichier importé…")
def _traiter_fichier_uploade(fichier) -> pd.DataFrame:
    """
    Lit un fichier brut importé (même format que la base NG Travel) et lui
    applique le même pipeline ETL (étape Transform) que le dossier `etl/`,
    entièrement en mémoire — sans écrire sur le Data Lake ni le Data Warehouse.
    Le cache est indexé sur le contenu du fichier (Streamlit hashe les
    UploadedFile par octets) : ré-uploader le même fichier ne retraite rien.
    """
    nom = fichier.name.lower()
    log.info("Fichier importé par l'utilisateur : %s", fichier.name)
    if nom.endswith(".csv"):
        brut = pd.read_csv(fichier)
    else:
        try:
            brut = pd.read_excel(fichier, sheet_name="base de donnée")
        except (ValueError, KeyError):
            fichier.seek(0)
            brut = pd.read_excel(fichier, sheet_name=0)

    df = transformer_dataframe(brut)  # log détaillé déjà émis dans _transformer()
    for col in ["date_resa", "date_depart", "mois_depart_periode", "mois_resa_periode"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def selecteur_source() -> pd.DataFrame | None:
    """
    Affiche (dans la sidebar) un import de fichier brut (traité par l'ETL en
    mémoire) OU un sélecteur parmi les bases déjà publiées, puis renvoie le
    DataFrame chargé. Renvoie None si aucune source disponible.
    """
    st.sidebar.subheader("Base de données")
    fichier_uploade = st.sidebar.file_uploader(
        "Importer votre base brute (.xlsx ou .csv, même format que la base NG Travel)",
        type=["xlsx", "xls", "csv"], key="_upload_base",
        help="Le fichier doit contenir les colonnes brutes attendues (Ref Dossier, "
             "Date resa, Date depart, BRUT TTC, MARGE NET, etc.). Il est nettoyé et "
             "enrichi automatiquement (pipeline ETL) sans quitter l'application.",
    )
    if fichier_uploade is not None:
        try:
            df = _traiter_fichier_uploade(fichier_uploade)
        except Exception as e:
            log.exception("Échec du traitement du fichier importé « %s ».", fichier_uploade.name)
            st.sidebar.error(f"❌ Impossible de traiter ce fichier : {e}")
            return None
        st.sidebar.success(
            f"✅ Base importée : {len(df):,} lignes traitées.".replace(",", " ")
        )

        nom_base = Path(fichier_uploade.name).stem
        st.sidebar.caption("Télécharger la base de données nettoyée :")
        col_dl1, col_dl2 = st.sidebar.columns(2)
        with col_dl1:
            csv_nettoye = df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "📥 .csv", data=csv_nettoye,
                file_name=f"{nom_base}_nettoyee.csv",
                mime="text/csv", key="_dl_base_nettoyee_csv",
                use_container_width=True,
            )
        with col_dl2:
            tampon_xlsx = BytesIO()
            with pd.ExcelWriter(tampon_xlsx, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="base_nettoyee")
            st.download_button(
                "📥 .xlsx", data=tampon_xlsx.getvalue(),
                file_name=f"{nom_base}_nettoyee.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="_dl_base_nettoyee_xlsx",
                use_container_width=True,
            )

        return df

    bases = _lister_bases()
    if not bases:
        log.warning("Aucune base disponible (ni fichier importé, ni base publiée trouvée).")
        st.sidebar.error(
            "Aucune base trouvée dans « Data Warehouse » et aucun fichier importé.\n\n"
            "Importe un fichier ci-dessus, ou lance d'abord le pipeline ETL :\n"
            "`python -m pipeline_orchestrator.pipeline_orchestrator <source> --nom ng_travel_2025_2026`"
        )
        return None

    libelles = {f.stem: str(f) for f in bases}
    choix = st.sidebar.selectbox(
        "Ou choisir une base déjà publiée", options=list(libelles.keys()),
        key="_source_base",
    )
    return charger_donnees(libelles[choix])


# ---------------------------------------------------------------------------
# Barre latérale de filtres (commune à toutes les pages)
# ---------------------------------------------------------------------------

def _multiselect_tries(label, options, key):
    """Multiselect trié, vide = 'tout' (pas de filtre)."""
    opts = sorted([o for o in options if pd.notna(o)])
    return st.sidebar.multiselect(label, opts, default=[], key=key,
                                  placeholder="Tout")


def filtres_lateraux(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Rend les filtres communs dans la sidebar et retourne (df_filtré, contexte).
    Les sélections sont mémorisées entre les pages via les `key` de session.
    """
    st.sidebar.header("Filtres")

    # Exclusion des lignes techniquement invalides (activé par défaut)
    exclure_invalides = st.sidebar.toggle(
        "Exclure les lignes invalides", value=True, key="_excl_invalides",
        help="Retire les 17 dossiers sans CA / sans passager / etc. Les marges "
             "négatives, elles, restent (phénomène métier).",
    )

    df_f = df.copy()
    if exclure_invalides and "valide" in df_f.columns:
        df_f = df_f[df_f["valide"]]

    # Saison (année de départ)
    if "saison" in df_f.columns:
        saisons = _multiselect_tries("Saison (année de départ)",
                                     df["saison"].dropna().unique(), "_f_saison")
        if saisons:
            df_f = df_f[df_f["saison"].isin(saisons)]

    # Destination
    if "destination" in df_f.columns:
        dests = _multiselect_tries("Destination",
                                   df["destination"].dropna().unique(), "_f_dest")
        if dests:
            df_f = df_f[df_f["destination"].isin(dests)]

    # Canal (regroupement réseau)
    if "regroupement_reseau" in df_f.columns:
        canaux = _multiselect_tries("Canal (B2B / B2C / Groupes)",
                                    df["regroupement_reseau"].dropna().unique(),
                                    "_f_canal")
        if canaux:
            df_f = df_f[df_f["regroupement_reseau"].isin(canaux)]

    # Intensité de saison
    if "saison_touristique" in df_f.columns:
        intens = _multiselect_tries("Intensité de saison",
                                    df["saison_touristique"].dropna().unique(),
                                    "_f_intens")
        if intens:
            df_f = df_f[df_f["saison_touristique"].isin(intens)]

    st.sidebar.divider()
    st.sidebar.caption(
        f"**{len(df_f):,}** dossiers sélectionnés "
        f"sur {len(df):,}".replace(",", " ")
    )

    contexte = {"exclure_invalides": exclure_invalides, "n": len(df_f)}
    return df_f, contexte


# ---------------------------------------------------------------------------
# Formatage (façon française : espace comme séparateur de milliers)
# ---------------------------------------------------------------------------

def fmt_euro(x, decimales=0) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:,.{decimales}f} €".replace(",", " ").replace(".", ",")


def fmt_int(x) -> str:
    if pd.isna(x):
        return "—"
    return f"{x:,.0f}".replace(",", " ")


def fmt_pct(x, decimales=1) -> str:
    if pd.isna(x):
        return "—"
    return f"{x*100:.{decimales}f} %".replace(".", ",")


# ---------------------------------------------------------------------------
# KPI
# ---------------------------------------------------------------------------

def kpis(df: pd.DataFrame) -> dict:
    """Calcule les indicateurs clés sur le DataFrame (déjà filtré)."""
    if len(df) == 0:
        return {k: float("nan") for k in
                ["ca", "marge", "marge_pct", "prix_pax", "nb_pax",
                 "nb_dossiers", "pct_deficit"]}
    ca = df["ca_brut_ttc"].sum()
    marge = df["marge_nette"].sum()
    return {
        "ca": ca,
        "marge": marge,
        "marge_pct": (marge / ca) if ca else float("nan"),
        "prix_pax": df["prix_moyen_pax"].mean(),
        "nb_pax": df["nb_pax"].sum(),
        "nb_dossiers": len(df),
        "pct_deficit": df["dossier_deficitaire"].mean(),
    }


# ---------------------------------------------------------------------------
# Dimensions analysables + agrégateur de performance unique
# ---------------------------------------------------------------------------

# Toutes les dimensions par lesquelles on peut évaluer la performance.
# Utilisées de façon cohérente par les pages Axes complémentaires et Outil Yield.
DIMENSIONS = {
    "destination": "Destination",
    "regroupement_reseau": "Canal (B2B / B2C / Groupes)",
    "reseau": "Réseau",
    "ville_depart": "Ville de départ",
    "compagnie_nom": "Compagnie aérienne",
    "type_produit": "Type de produit",
    "tranche_duree": "Durée de séjour",
    "tranche_delai": "Délai de réservation",
    "saison": "Saison (année)",
    "saison_touristique": "Intensité de saison",
}


def perf_par(df: pd.DataFrame, by) -> pd.DataFrame:
    """
    Agrégateur de performance CANONIQUE : renvoie les mêmes indicateurs quelle
    que soit la ou les dimension(s) `by`. Garantit que toutes les pages
    évaluent la performance de manière identique.

    Indicateurs : dossiers, CA, marge nette, commissions, taux de marge,
    taux de commission, prix moyen/pax, % de dossiers déficitaires,
    et marge nette moyenne par dossier.
    """
    if isinstance(by, str):
        by = [by]
    g = (df.groupby(by, dropna=False)
         .agg(dossiers=("ref_dossier", "count"),
              ca=("ca_brut_ttc", "sum"),
              marge=("marge_nette", "sum"),
              commission=("commission", "sum"),
              prix_pax=("prix_moyen_pax", "mean"),
              pct_deficit=("dossier_deficitaire", "mean"))
         .reset_index())
    g["marge_pct"] = g["marge"] / g["ca"].where(g["ca"] != 0)
    g["taux_commission"] = g["commission"] / g["ca"].where(g["ca"] != 0)
    g["marge_par_dossier"] = g["marge"] / g["dossiers"].where(g["dossiers"] != 0)
    return g
