"""Page — Performance par destination."""
import plotly.express as px
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_pct, fmt_int, ORDRE_SAISON_TOURISTIQUE)

setup_page("Performance par destination", icon="🗺️")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

synth = (df_f.groupby("destination")
         .agg(dossiers=("ref_dossier", "count"),
              ca=("ca_brut_ttc", "sum"),
              marge=("marge_nette", "sum"),
              prix_pax=("prix_moyen_pax", "mean"),
              pct_deficit=("dossier_deficitaire", "mean"))
         .reset_index())
synth["marge_pct"] = synth["marge"] / synth["ca"]
synth = synth.sort_values("marge", ascending=False)

# --- Tableau de synthèse ---
aff = synth.copy()
aff["ca"] = aff["ca"].map(fmt_euro)
aff["marge"] = aff["marge"].map(fmt_euro)
aff["marge_pct"] = aff["marge_pct"].map(fmt_pct)
aff["prix_pax"] = aff["prix_pax"].map(fmt_euro)
aff["pct_deficit"] = aff["pct_deficit"].map(fmt_pct)
aff["dossiers"] = aff["dossiers"].map(fmt_int)
aff.columns = ["Destination", "Dossiers", "CA brut", "Marge nette",
               "Prix moy./pax", "% déficitaires", "Taux marge"]
aff = aff[["Destination", "Dossiers", "CA brut", "Marge nette", "Taux marge",
           "Prix moy./pax", "% déficitaires"]]
st.dataframe(aff, width="stretch", hide_index=True)

# --- Deux graphiques ---
g1, g2 = st.columns(2)
with g1:
    st.subheader("Chiffre d'affaires")
    fig = px.bar(synth.sort_values("ca"), x="ca", y="destination", orientation="h",
                 labels={"ca": "CA brut (€)", "destination": ""})
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
with g2:
    st.subheader("Taux de marge")
    fig = px.bar(synth.sort_values("marge_pct"), x="marge_pct", y="destination",
                 orientation="h", labels={"marge_pct": "Taux de marge", "destination": ""})
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
    fig.update_xaxes(tickformat=".1%")
    st.plotly_chart(fig, width="stretch")

# --- Quadrant : pouvoir de prix (marge% vs volume) ---
st.subheader("Où se situe le pouvoir de prix ?")
st.caption("Marge % (axe Y) vs volume de dossiers (axe X). En haut = déjà rentable ; en bas = "
           "sous pression. La taille du point = chiffre d'affaires.")
fig = px.scatter(synth, x="dossiers", y="marge_pct", size="ca", text="destination",
                 labels={"dossiers": "Nombre de dossiers", "marge_pct": "Taux de marge"},
                 size_max=55)
fig.update_traces(textposition="top center")
fig.update_yaxes(tickformat=".1%")
fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, width="stretch")

# --- Heatmap destination x intensité de saison ---
st.subheader("Taux de marge par destination et intensité de saison")
piv = (df_f.groupby(["destination", "saison_touristique"])
       .agg(ca=("ca_brut_ttc", "sum"), marge=("marge_nette", "sum"))
       .reset_index())
piv["marge_pct"] = piv["marge"] / piv["ca"]
table = piv.pivot(index="destination", columns="saison_touristique", values="marge_pct")
ordre_cols = [c for c in ORDRE_SAISON_TOURISTIQUE if c in table.columns]
table = table[ordre_cols]
fig = px.imshow(table, text_auto=".1%", aspect="auto", color_continuous_scale="RdYlGn",
                color_continuous_midpoint=0,
                labels=dict(color="Taux de marge"))
fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
fig.update_xaxes(title="")
fig.update_yaxes(title="")
st.plotly_chart(fig, width="stretch")
