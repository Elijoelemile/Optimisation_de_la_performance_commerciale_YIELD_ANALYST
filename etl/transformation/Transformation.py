"""
Transformation.py — Étape « T » (Transform) de l'ETL NG Travel
===============================================================

Rôle : aller lire la donnée BRUTE dans le Data Lake, la nettoyer et l'enrichir
(mêmes règles que le script de préparation initial), puis RETOURNER le résultat
sous forme de DataFrame conservé EN MÉMOIRE (variable Python en RAM).

Important — mémoire vs disque
-----------------------------
`transformation()` renvoie un DataFrame : tant qu'on reste dans le MÊME
processus Python, cet objet vit en mémoire et peut être passé directement à
l'étape Load. C'est ce que fait l'orchestrateur `pipeline_etl.py`.
(Deux exécutions séparées de `python X.py` ne partagent pas leur RAM : dans ce
cas il faudrait un fichier intermédiaire — voir pipeline_etl.py.)

Utilisation en import (dans le pipeline)
----------------------------------------
    from Transformation import transformation
    df = transformation(data_lake="Data Lake")   # <-- variable mémoire

Utilisation en ligne de commande (démo / contrôle qualité)
----------------------------------------------------------
    python Transformation.py --data-lake "Data Lake"
"""

from __future__ import annotations
import argparse
from pathlib import Path

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Référentiels métier
# ---------------------------------------------------------------------------

COLONNES = {
    "nom  hotel": "hotel",
    "Ref Dossier": "ref_dossier",
    "Date resa": "date_resa",
    "Date depart": "date_depart",
    "Réseau": "reseau",
    "Regroupement réseau": "regroupement_reseau",
    "Adu": "adultes",
    "Enf": "enfants",
    "Dep": "aeroport_depart",
    "Arr": "aeroport_arrivee",
    "Destination": "destination",
    "Nts": "nuits",
    "BRUT TTC": "ca_brut_ttc",
    "Cie": "compagnie",
    "ACHATS PREV": "achats_prev",
    "COMM.": "commission",
    "MARGE NET": "marge_nette",
}

VILLES_DEPART = {
    "PAR": "Paris", "ORY": "Paris", "CDG": "Paris",
    "NTE": "Nantes", "LYS": "Lyon", "MRS": "Marseille", "LIL": "Lille",
    "BOD": "Bordeaux", "TLS": "Toulouse", "NCE": "Nice", "MPL": "Montpellier",
    "BES": "Brest", "SXB": "Strasbourg", "DOL": "Dole", "CFE": "Clermont-Ferrand",
    "BRU": "Bruxelles", "CRL": "Bruxelles", "GVA": "Genève",
    "BSL": "Bâle-Mulhouse", "EAP": "Bâle-Mulhouse", "MLH": "Bâle-Mulhouse",
    "LUX": "Luxembourg", "ZRH": "Zurich",
    "MIL": "Milan", "MXP": "Milan", "LIN": "Milan", "BLQ": "Bologne",
    "ROM": "Rome", "FCO": "Rome", "NAP": "Naples", "VCE": "Venise",
    "PSA": "Pise", "TRN": "Turin", "BRI": "Bari", "CTA": "Catane",
    "BCN": "Barcelone", "MAD": "Madrid", "LON": "Londres",
    "FRA": "Francfort", "STR": "Stuttgart", "BER": "Berlin", "BEG": "Belgrade",
    "HER": "Héraklion", "ATH": "Athènes", "CFU": "Corfou",
    "SKG": "Thessalonique", "RHO": "Rhodes",
}

COMPAGNIES = {
    "TO": "Transavia France", "U2": "easyJet", "V7": "Volotea",
    "GQ": "Sky Express", "FR": "Ryanair", "A3": "Aegean",
    "LH": "Lufthansa", "AF": "Air France", "SN": "Brussels Airlines",
    "LX": "Swiss", "LG": "Luxair", "W4": "Wizz Air Malta", "AZ": "ITA Airways",
    "OS": "Austrian", "QS": "SmartWings", "TB": "TUI fly Belgium",
    "HV": "Transavia", "VY": "Vueling", "IB": "Iberia", "SK": "SAS",
    "DE": "Condor", "KL": "KLM", "LO": "LOT", "NO": "Neos",
    "E4": "Enter Air", "H1": "Hahn Air", "I2": "Iberia Express", "JU": "Air Serbia",
}

LABEL_MANQUANT = "NON RENSEIGNÉ"

MOIS_FR = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
    7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.",
}


# ---------------------------------------------------------------------------
# Petites fonctions de catégorisation
# ---------------------------------------------------------------------------

def _bucket_duree(n):
    if pd.isna(n):
        return LABEL_MANQUANT
    if n <= 4:
        return "Court séjour (≤4 nuits)"
    if n <= 8:
        return "Semaine (5-8 nuits)"
    return "Long séjour (>8 nuits)"


def _bucket_delai(j):
    if pd.isna(j):
        return LABEL_MANQUANT
    if j < 0:
        return "Anomalie (<0)"
    if j <= 14:
        return "Last minute (0-14 j)"
    if j <= 30:
        return "Court (15-30 j)"
    if j <= 60:
        return "Moyen (31-60 j)"
    if j <= 120:
        return "Long (61-120 j)"
    return "Très anticipé (>120 j)"


def _saison_touristique(mois):
    if pd.isna(mois):
        return LABEL_MANQUANT
    mois = int(mois)
    if mois in (7, 8):
        return "Haute saison (juil.-août)"
    if mois in (6, 9):
        return "Épaule (juin/sept.)"
    if mois in (4, 5, 10):
        return "Basse saison (avr./mai/oct.)"
    return "Hors saison"


# ---------------------------------------------------------------------------
# Lecture du fichier brut depuis le Data Lake
# ---------------------------------------------------------------------------

def _trouver_dans_lake(data_lake: str, nom_fichier: str | None) -> Path:
    """Retourne le chemin du fichier brut à transformer dans le Data Lake."""
    dossier = Path(data_lake).expanduser()
    if not dossier.is_dir():
        raise FileNotFoundError(f"Data Lake introuvable : « {dossier} »")

    if nom_fichier:
        cible = dossier / nom_fichier
        if not cible.is_file():
            raise FileNotFoundError(f"Fichier « {nom_fichier} » absent du Data Lake.")
        return cible

    candidats = [f for f in dossier.iterdir()
                 if f.is_file() and f.suffix.lower() in {".csv", ".xlsx", ".xls"}]
    if not candidats:
        raise FileNotFoundError(f"Aucun fichier exploitable dans « {dossier} ».")
    return max(candidats, key=lambda f: f.stat().st_mtime)  # le plus récent


def _lire_brut(chemin: Path, feuille: str = "base de donnée") -> pd.DataFrame:
    """Lit le fichier brut (csv ou xlsx) sans le transformer."""
    if chemin.suffix.lower() == ".csv":
        return pd.read_csv(chemin)
    # Excel : on tente la feuille attendue, sinon la première
    try:
        return pd.read_excel(chemin, sheet_name=feuille)
    except (ValueError, KeyError):
        return pd.read_excel(chemin, sheet_name=0)


# ---------------------------------------------------------------------------
# Cœur de la transformation
# ---------------------------------------------------------------------------

def _transformer(df: pd.DataFrame) -> pd.DataFrame:
    """Applique nettoyage + variables dérivées sur un DataFrame brut."""
    # Renommage si les colonnes brutes (françaises) sont présentes
    colonnes_brutes_presentes = set(COLONNES) & set(df.columns)
    if colonnes_brutes_presentes:
        df = df.rename(columns=COLONNES)

    requises = {"ca_brut_ttc", "achats_prev", "commission", "marge_nette",
                "date_resa", "date_depart"}
    manquantes = requises - set(df.columns)
    if manquantes:
        raise ValueError(
            f"Colonnes attendues absentes après lecture : {sorted(manquantes)}. "
            "Le fichier du Data Lake n'a pas le schéma NG Travel attendu."
        )

    # Typage
    df["date_resa"] = pd.to_datetime(df["date_resa"], errors="coerce")
    df["date_depart"] = pd.to_datetime(df["date_depart"], errors="coerce")
    for col in ["adultes", "enfants", "nuits"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["ca_brut_ttc", "achats_prev", "commission", "marge_nette"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Nettoyage texte
    for col in ["hotel", "reseau", "regroupement_reseau", "destination",
                "aeroport_depart", "aeroport_arrivee", "compagnie"]:
        df[col] = df[col].astype("string").str.strip()
    df["aeroport_depart"] = df["aeroport_depart"].fillna(LABEL_MANQUANT)
    df["compagnie"] = df["compagnie"].fillna(LABEL_MANQUANT)

    # Libellés lisibles
    df["ville_depart"] = df["aeroport_depart"].map(VILLES_DEPART).fillna(df["aeroport_depart"])
    df["compagnie_nom"] = df["compagnie"].map(COMPAGNIES).fillna(df["compagnie"])

    # Voyageurs
    df["nb_pax"] = df["adultes"] + df["enfants"]
    df["a_enfants"] = df["enfants"] > 0

    # Temporel (basé sur la date de DÉPART = saison réelle)
    df["annee_depart"] = df["date_depart"].dt.year
    df["mois_depart"] = df["date_depart"].dt.month
    df["mois_depart_label"] = df["mois_depart"].map(MOIS_FR)
    df["mois_depart_periode"] = df["date_depart"].dt.to_period("M").dt.to_timestamp()
    df["saison"] = df["annee_depart"].astype("Int64").astype("string")
    df["saison_touristique"] = df["mois_depart"].map(_saison_touristique)
    df["annee_resa"] = df["date_resa"].dt.year
    df["mois_resa_periode"] = df["date_resa"].dt.to_period("M").dt.to_timestamp()

    # Délai de réservation
    df["delai_resa_jours"] = (df["date_depart"] - df["date_resa"]).dt.days
    df["tranche_delai"] = df["delai_resa_jours"].apply(_bucket_delai)

    # Durée / type de produit
    df["tranche_duree"] = df["nuits"].apply(_bucket_duree)
    df["type_produit"] = df["destination"].astype("string") + " · " + df["tranche_duree"]

    # Indicateurs financiers dérivés
    df["marge_pct"] = np.where(df["ca_brut_ttc"] > 0,
                               df["marge_nette"] / df["ca_brut_ttc"], np.nan)
    df["taux_commission"] = np.where(df["ca_brut_ttc"] > 0,
                                     df["commission"] / df["ca_brut_ttc"], np.nan)
    df["prix_moyen_pax"] = np.where(df["nb_pax"] > 0,
                                    df["ca_brut_ttc"] / df["nb_pax"], np.nan)
    df["prix_moyen_pax_nuit"] = np.where(
        (df["nb_pax"] > 0) & (df["nuits"] > 0),
        df["ca_brut_ttc"] / (df["nb_pax"] * df["nuits"]), np.nan)
    df["dossier_deficitaire"] = df["marge_nette"] < 0

    # Contrôle comptable
    marge_recalc = df["ca_brut_ttc"] - df["achats_prev"] - df["commission"]
    df["ecart_comptable"] = (df["marge_nette"] - marge_recalc).abs()
    df["coherence_comptable"] = df["ecart_comptable"] <= 0.05

    # Drapeau de validité (on marque, on ne supprime pas)
    df["valide"] = (
        (df["ca_brut_ttc"] > 0)
        & (df["nb_pax"] > 0)
        & (df["nuits"] > 0)
        & (df["delai_resa_jours"] >= 0)
        & df["date_depart"].notna()
        & df["date_resa"].notna()
    )
    return df


def transformer_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Version publique de `_transformer` : applique le nettoyage + enrichissement
    ETL à un DataFrame déjà chargé en mémoire (ex. fichier importé dans l'app
    Streamlit), sans passer par le Data Lake sur disque.
    """
    return _transformer(df)


def transformation(
    data_lake: str = "Data Lake",
    nom_fichier: str | None = None,
    feuille: str = "base de donnée",
) -> pd.DataFrame:
    """
    Lit le fichier brut du Data Lake, le transforme, et RETOURNE le DataFrame
    (conservé en mémoire).

    Paramètres
    ----------
    data_lake   : dossier source (zone brute).
    nom_fichier : fichier précis à transformer (défaut : le plus récent).
    feuille     : nom de la feuille si le fichier est un Excel.
    """
    chemin = _trouver_dans_lake(data_lake, nom_fichier)
    print(f"[TRANSFORMATION] Lecture brut : {chemin}")
    brut = _lire_brut(chemin, feuille=feuille)
    df = _transformer(brut)
    print(f"[TRANSFORMATION] Terminé : {len(df):,} lignes × {len(df.columns)} colonnes "
          f"(gardées en mémoire)".replace(",", " "))
    return df


def _cli():
    parser = argparse.ArgumentParser(
        description="Transformation ETL — nettoie/enrichit la donnée du Data Lake."
    )
    parser.add_argument("--data-lake", default="Data Lake")
    parser.add_argument("--nom-fichier", default=None,
                        help="Fichier précis du Data Lake (défaut : le plus récent).")
    parser.add_argument("--feuille", default="base de donnée")
    args = parser.parse_args()

    df = transformation(args.data_lake, args.nom_fichier, args.feuille)
    # Démo : aperçu (le DataFrame vit en mémoire le temps de ce processus)
    dfv = df[df["valide"]]
    print("\n--- Aperçu (contrôle) ---")
    print(f"Lignes valides ......... {len(dfv):,}".replace(",", " "))
    print(f"CA brut total .......... {dfv['ca_brut_ttc'].sum():,.0f} €".replace(",", " "))
    print(f"Marge nette totale ..... {dfv['marge_nette'].sum():,.0f} €".replace(",", " "))
    print(f"Dossiers déficitaires .. {dfv['dossier_deficitaire'].mean()*100:.1f} %")
    print("\nNote : lancé seul, ce script ne transmet rien à Load (processus séparé).")
    print("Pour l'enchaînement mémoire E→T→L, utilise pipeline_etl.py.")


if __name__ == "__main__":
    _cli()
