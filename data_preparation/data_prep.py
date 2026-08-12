"""
NG Travel — Couche de préparation des données (Yield Management)
================================================================

Ce module charge la base de ventes brute (Excel), la nettoie, et crée
l'ensemble des variables dérivées nécessaires aux analyses et au dashboard
Streamlit.

Utilisation :
    # En import (dans l'app Streamlit) :
    from data_prep import load_and_prepare
    df = load_and_prepare("base_de_données_NG_Travel.xlsx")

    # En ligne de commande (génère les fichiers + rapport qualité) :
    python data_prep.py base_de_données_NG_Travel.xlsx

Sorties CLI :
    - ng_travel_clean.parquet   (chargement rapide pour Streamlit)
    - ng_travel_clean.csv       (inspection / Power BI / Excel)
    - un rapport qualité imprimé dans la console
"""

from __future__ import annotations
import sys
import unicodedata
import pandas as pd
import numpy as np


# ---------------------------------------------------------------------------
# 1. Référentiels (mappings métier)
# ---------------------------------------------------------------------------

# Renommage des colonnes brutes -> noms propres (snake_case)
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

# Aéroports de départ (code IATA -> ville). Les codes absents restent tels quels.
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
    # Codes grecs apparaissant en départ (probables trajets retour / requalifications)
    "HER": "Héraklion", "ATH": "Athènes", "CFU": "Corfou",
    "SKG": "Thessalonique", "RHO": "Rhodes",
}

# Compagnies aériennes (code -> nom), pour des libellés lisibles.
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


# ---------------------------------------------------------------------------
# 2. Fonctions utilitaires
# ---------------------------------------------------------------------------

def _strip_accents(txt: str) -> str:
    """Retire les accents (utile pour homogénéiser d'éventuelles clés texte)."""
    if not isinstance(txt, str):
        return txt
    return "".join(
        c for c in unicodedata.normalize("NFKD", txt) if not unicodedata.combining(c)
    )


def _bucket_duree(n: float) -> str:
    """Regroupe la durée de séjour en catégories métier."""
    if pd.isna(n):
        return LABEL_MANQUANT
    if n <= 4:
        return "Court séjour (≤4 nuits)"
    if n <= 8:
        return "Semaine (5-8 nuits)"
    return "Long séjour (>8 nuits)"


def _bucket_delai(j: float) -> str:
    """Regroupe le délai de réservation (jours avant départ) en catégories."""
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


def _saison_touristique(mois: float) -> str:
    """Classe le mois de DÉPART en intensité de saison (marché grec avril->octobre)."""
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


MOIS_FR = {
    1: "janv.", 2: "févr.", 3: "mars", 4: "avr.", 5: "mai", 6: "juin",
    7: "juil.", 8: "août", 9: "sept.", 10: "oct.", 11: "nov.", 12: "déc.",
}


# ---------------------------------------------------------------------------
# 3. Pipeline principal
# ---------------------------------------------------------------------------

def load_and_prepare(chemin_xlsx: str, feuille: str = "base de donnée") -> pd.DataFrame:
    """
    Charge, nettoie et enrichit la base NG Travel.

    Retourne un DataFrame prêt à l'analyse, avec :
      - colonnes renommées proprement,
      - variables dérivées (marge %, délai, saison, type de produit, etc.),
      - une colonne booléenne `valide` isolant les lignes techniquement invalides
        (sans les supprimer), pour pouvoir filtrer de façon transparente.
    """
    # --- Chargement ---
    df = pd.read_excel(chemin_xlsx, sheet_name=feuille)
    df = df.rename(columns=COLONNES)

    # --- Typage ---
    df["date_resa"] = pd.to_datetime(df["date_resa"], errors="coerce")
    df["date_depart"] = pd.to_datetime(df["date_depart"], errors="coerce")
    for col in ["adultes", "enfants", "nuits"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    for col in ["ca_brut_ttc", "achats_prev", "commission", "marge_nette"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Nettoyage des libellés texte ---
    for col in ["hotel", "reseau", "regroupement_reseau", "destination",
                "aeroport_depart", "aeroport_arrivee", "compagnie"]:
        df[col] = df[col].astype("string").str.strip()

    df["aeroport_depart"] = df["aeroport_depart"].fillna(LABEL_MANQUANT)
    df["compagnie"] = df["compagnie"].fillna(LABEL_MANQUANT)

    # --- Libellés lisibles (villes / compagnies) ---
    df["ville_depart"] = (
        df["aeroport_depart"].map(VILLES_DEPART).fillna(df["aeroport_depart"])
    )
    df["compagnie_nom"] = (
        df["compagnie"].map(COMPAGNIES).fillna(df["compagnie"])
    )

    # --- Variables voyageurs ---
    df["nb_pax"] = df["adultes"] + df["enfants"]
    df["a_enfants"] = df["enfants"] > 0

    # --- Variables temporelles (basées sur la DATE DE DÉPART = saison réelle) ---
    df["annee_depart"] = df["date_depart"].dt.year
    df["mois_depart"] = df["date_depart"].dt.month
    df["mois_depart_label"] = df["mois_depart"].map(MOIS_FR)
    # Clé mensuelle triable (1er du mois de départ)
    df["mois_depart_periode"] = df["date_depart"].dt.to_period("M").dt.to_timestamp()
    # Saison = année de départ (tous les départs sont avril->novembre)
    df["saison"] = df["annee_depart"].astype("Int64").astype("string")
    df["saison_touristique"] = df["mois_depart"].map(_saison_touristique)

    # Idem côté réservation (utile pour analyser le rythme de prise de commandes)
    df["annee_resa"] = df["date_resa"].dt.year
    df["mois_resa_periode"] = df["date_resa"].dt.to_period("M").dt.to_timestamp()

    # --- Délai de réservation (anticipation) ---
    df["delai_resa_jours"] = (df["date_depart"] - df["date_resa"]).dt.days
    df["tranche_delai"] = df["delai_resa_jours"].apply(_bucket_delai)

    # --- Durée / type de produit ---
    df["tranche_duree"] = df["nuits"].apply(_bucket_duree)
    df["type_produit"] = df["destination"].astype("string") + " · " + df["tranche_duree"]

    # --- Indicateurs financiers dérivés ---
    # Marge % = marge nette / CA brut (ratio comparable entre dossiers de tailles ≠)
    df["marge_pct"] = np.where(
        df["ca_brut_ttc"] > 0, df["marge_nette"] / df["ca_brut_ttc"], np.nan
    )
    # Taux de commission
    df["taux_commission"] = np.where(
        df["ca_brut_ttc"] > 0, df["commission"] / df["ca_brut_ttc"], np.nan
    )
    # Prix moyens
    df["prix_moyen_pax"] = np.where(
        df["nb_pax"] > 0, df["ca_brut_ttc"] / df["nb_pax"], np.nan
    )
    df["prix_moyen_pax_nuit"] = np.where(
        (df["nb_pax"] > 0) & (df["nuits"] > 0),
        df["ca_brut_ttc"] / (df["nb_pax"] * df["nuits"]), np.nan
    )
    # Dossier déficitaire (phénomène métier clé : destruction de valeur)
    df["dossier_deficitaire"] = df["marge_nette"] < 0

    # --- Contrôle de cohérence comptable ---
    # MARGE NET doit = CA BRUT - ACHATS - COMMISSION
    marge_recalc = df["ca_brut_ttc"] - df["achats_prev"] - df["commission"]
    df["ecart_comptable"] = (df["marge_nette"] - marge_recalc).abs()
    df["coherence_comptable"] = df["ecart_comptable"] <= 0.05

    # --- Drapeau de validité (on marque, on ne supprime pas) ---
    df["valide"] = (
        (df["ca_brut_ttc"] > 0)
        & (df["nb_pax"] > 0)
        & (df["nuits"] > 0)
        & (df["delai_resa_jours"] >= 0)
        & df["date_depart"].notna()
        & df["date_resa"].notna()
    )

    return df


# ---------------------------------------------------------------------------
# 4. Rapport qualité
# ---------------------------------------------------------------------------

def rapport_qualite(df: pd.DataFrame) -> str:
    """Génère un rapport texte synthétique sur la qualité des données."""
    n = len(df)
    n_valide = int(df["valide"].sum())
    lignes = []
    add = lignes.append

    add("=" * 62)
    add("RAPPORT QUALITÉ — BASE NG TRAVEL")
    add("=" * 62)
    add(f"Lignes totales ............................ {n:>8,}".replace(",", " "))
    add(f"Lignes valides (KPI) ...................... {n_valide:>8,}".replace(",", " "))
    add(f"Lignes écartées des KPI ................... {n - n_valide:>8,}".replace(",", " "))
    add("")
    add("Détail des lignes invalides :")
    add(f"  · CA brut = 0 ........................... {int((df['ca_brut_ttc'] <= 0).sum()):>6}")
    add(f"  · 0 passager ........................... {int((df['nb_pax'] <= 0).sum()):>6}")
    add(f"  · 0 nuit ............................... {int((df['nuits'] <= 0).sum()):>6}")
    add(f"  · Délai négatif (départ<résa) .......... {int((df['delai_resa_jours'] < 0).sum()):>6}")
    add(f"  · Date manquante ....................... {int(df['date_depart'].isna().sum() + df['date_resa'].isna().sum()):>6}")
    add("")
    add("Cohérence comptable (marge = brut - achats - comm.) :")
    add(f"  · Lignes cohérentes .................... {int(df['coherence_comptable'].sum()):>6} / {n}")
    add("")
    add("Valeurs manquantes étiquetées (conservées) :")
    add(f"  · Aéroport de départ manquant .......... {int((df['aeroport_depart'] == LABEL_MANQUANT).sum()):>6}")
    add(f"  · Compagnie manquante .................. {int((df['compagnie'] == LABEL_MANQUANT).sum()):>6}")
    add("")

    dfv = df[df["valide"]]
    add("-" * 62)
    add("APERÇU MÉTIER (sur lignes valides)")
    add("-" * 62)
    add(f"CA brut total ............ {dfv['ca_brut_ttc'].sum():>15,.0f} €".replace(",", " "))
    add(f"Marge nette totale ....... {dfv['marge_nette'].sum():>15,.0f} €".replace(",", " "))
    add(f"Marge nette moyenne % .... {dfv['marge_pct'].mean() * 100:>14.1f} %")
    add(f"Prix moyen / pax ......... {dfv['prix_moyen_pax'].mean():>15,.0f} €".replace(",", " "))
    add(f"Passagers (total) ........ {int(dfv['nb_pax'].sum()):>15,}".replace(",", " "))
    deficit = dfv["dossier_deficitaire"].mean() * 100
    add(f"Dossiers déficitaires .... {deficit:>14.1f} % des dossiers")
    add("")
    add("Répartition par saison (départ) :")
    for saison, grp in dfv.groupby("saison", dropna=True):
        add(f"  · {saison} : {len(grp):>6,} dossiers | "
            .replace(",", " ")
            + f"CA {grp['ca_brut_ttc'].sum()/1e6:>6.2f} M€ | "
            + f"marge {grp['marge_nette'].sum()/1e6:>5.2f} M€")
    add("=" * 62)
    return "\n".join(lignes)


# ---------------------------------------------------------------------------
# 5. Point d'entrée CLI
# ---------------------------------------------------------------------------

def main():
    chemin = sys.argv[1] if len(sys.argv) > 1 else "base_de_données_NG_Travel.xlsx"
    df = load_and_prepare(chemin)

    # Sorties
    df.to_parquet("ng_travel_clean.parquet", index=False)
    df.to_csv("ng_travel_clean.csv", index=False, encoding="utf-8-sig")

    print(rapport_qualite(df))
    print()
    print("Fichiers générés : ng_travel_clean.parquet | ng_travel_clean.csv")
    print(f"Colonnes finales ({len(df.columns)}) :")
    print("  " + ", ".join(df.columns))


if __name__ == "__main__":
    main()
