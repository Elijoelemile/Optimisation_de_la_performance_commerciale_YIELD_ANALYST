"""
streamlit_app.py — Page d'accueil de l'app NG Travel (Vue d'ensemble / KPI)
============================================================================

Point d'entrée de l'application Streamlit. Lancer avec :
    streamlit run streamlit_app.py

Les autres pages se trouvent dans le dossier pages/ et apparaissent
automatiquement dans la navigation latérale.
"""

import plotly.express as px
import streamlit as st

from utils import (
    setup_page, selecteur_source, filtres_lateraux, kpis,
    fmt_euro, fmt_int, fmt_pct, COULEURS_CANAL,
)

setup_page("Vue d'ensemble")

# --- Chargement + filtres ---
df = selecteur_source()
if df is None:
    st.stop()

df_f, ctx = filtres_lateraux(df)

st.caption(
    "Tableau de bord de pilotage du Yield pour NG Travel — tour-opérateur "
    "spécialisé sur la Grèce. Utilise les filtres à gauche ; ils s'appliquent "
    "à toutes les pages."
)

if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres sélectionnés.")
    st.stop()

# --- Bandeau KPI ---
k = kpis(df_f)
c1, c2, c3, c4 = st.columns(4)
c1.metric("Chiffre d'affaires brut", fmt_euro(k["ca"]))
c2.metric("Marge nette", fmt_euro(k["marge"]))
c3.metric("Taux de marge", fmt_pct(k["marge_pct"]))
c4.metric("Dossiers déficitaires", fmt_pct(k["pct_deficit"]))

c5, c6, c7, c8 = st.columns(4)
c5.metric("Nombre de dossiers", fmt_int(k["nb_dossiers"]))
c6.metric("Passagers", fmt_int(k["nb_pax"]))
c7.metric("Prix moyen / passager", fmt_euro(k["prix_pax"]))
c8.metric("Panier moyen / dossier",
          fmt_euro(k["ca"] / k["nb_dossiers"] if k["nb_dossiers"] else float("nan")))

st.divider()

# --- Deux visuels de cadrage ---
g1, g2 = st.columns(2)

with g1:
    st.subheader("Chiffre d'affaires par destination")
    par_dest = (
        df_f.groupby("destination", as_index=False)
        .agg(ca=("ca_brut_ttc", "sum"))
        .sort_values("ca", ascending=True)
    )
    fig = px.bar(par_dest, x="ca", y="destination", orientation="h",
                 labels={"ca": "CA brut (€)", "destination": ""})
    fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

with g2:
    st.subheader("Marge nette par canal")
    par_canal = (
        df_f.groupby("regroupement_reseau", as_index=False)
        .agg(marge=("marge_nette", "sum"))
    )
    fig = px.bar(par_canal, x="regroupement_reseau", y="marge",
                 color="regroupement_reseau", color_discrete_map=COULEURS_CANAL,
                 labels={"regroupement_reseau": "", "marge": "Marge nette (€)"})
    fig.update_layout(height=340, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

st.divider()
st.info(
    "Les pages d'analyse détaillées (évolution, destinations, réseaux, axes "
    "complémentaires, outil Yield, recommandations) sont accessibles dans la "
    "barre de navigation à gauche.",
    icon="🧭",
)
