"""Page — Évolution temporelle."""
import plotly.express as px
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_int, COULEURS_CANAL)

setup_page("Évolution temporelle", icon="📈")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

col_gauche, col_droite = st.columns([1, 1])
with col_gauche:
    axe = st.radio("Axe temporel", ["Date de départ", "Date de réservation"],
                   horizontal=True, key="_axe_temps")
with col_droite:
    mesure = st.selectbox(
        "Mesure",
        ["Chiffre d'affaires", "Marge nette", "Taux de marge",
         "Nombre de passagers", "Nombre de dossiers", "Prix moyen / passager"],
        key="_mesure_temps")

col_periode = "mois_depart_periode" if axe == "Date de départ" else "mois_resa_periode"

MAP = {
    "Chiffre d'affaires": ("ca_brut_ttc", "sum"),
    "Marge nette": ("marge_nette", "sum"),
    "Nombre de passagers": ("nb_pax", "sum"),
    "Nombre de dossiers": ("ref_dossier", "count"),
    "Prix moyen / passager": ("prix_moyen_pax", "mean"),
}

base = df_f.dropna(subset=[col_periode]).copy()

st.subheader(f"{mesure} par mois")
if mesure == "Taux de marge":
    serie = (base.groupby(col_periode)
             .agg(ca=("ca_brut_ttc", "sum"), marge=("marge_nette", "sum"))
             .reset_index())
    serie["valeur"] = serie["marge"] / serie["ca"]
    fmt_y = ".1%"
else:
    col, agg = MAP[mesure]
    serie = (base.groupby(col_periode).agg(valeur=(col, agg)).reset_index())
    fmt_y = ",.0f"
serie = serie.sort_values(col_periode)

fig = px.line(serie, x=col_periode, y="valeur", markers=True,
              labels={col_periode: "", "valeur": mesure})
fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
fig.update_yaxes(tickformat=fmt_y)
st.plotly_chart(fig, width="stretch")

# --- Comparaison des deux saisons, mois par mois (uniquement sur axe départ) ---
if axe == "Date de départ" and base["saison"].nunique() > 1:
    st.subheader("Comparaison des saisons, mois par mois")
    st.caption("Superposition par numéro de mois pour comparer 2025 et 2026 au même stade "
               "de saison.")
    if mesure == "Taux de marge":
        comp = (base.groupby(["mois_depart", "saison"])
                .agg(ca=("ca_brut_ttc", "sum"), marge=("marge_nette", "sum"))
                .reset_index())
        comp["valeur"] = comp["marge"] / comp["ca"]
    else:
        col, agg = MAP[mesure]
        comp = (base.groupby(["mois_depart", "saison"])
                .agg(valeur=(col, agg)).reset_index())
    comp = comp.sort_values("mois_depart")
    fig2 = px.line(comp, x="mois_depart", y="valeur", color="saison", markers=True,
                   labels={"mois_depart": "Mois", "valeur": mesure, "saison": "Saison"})
    fig2.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
    fig2.update_yaxes(tickformat=fmt_y)
    fig2.update_xaxes(dtick=1)
    st.plotly_chart(fig2, width="stretch")

st.caption("⚠️ Certains mois de bord de saison (nov., mars) sont marginaux, et la saison "
           "2026 est encore en cours de remplissage : prudence dans l'interprétation des "
           "extrémités de courbe.")
