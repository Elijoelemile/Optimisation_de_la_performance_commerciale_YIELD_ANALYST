"""Page — Performance par réseau (page phare : création vs destruction de valeur)."""
import plotly.express as px
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_pct, fmt_int, perf_par, COULEURS_CANAL)

setup_page("Performance par réseau", icon="🔗")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

st.caption("Page phare de l'analyse Yield : quels réseaux **créent** de la valeur, lesquels "
           "en **détruisent**, et leur **utilité** au regard de la commission versée.")

# --- Niveau 1 : synthèse par canal ---
st.subheader("Vue par canal (B2B / B2C / Groupes)")
canal = perf_par(df_f, "regroupement_reseau").sort_values("marge", ascending=False)
c1, c2 = st.columns([1.2, 1])
with c1:
    aff = canal.copy()
    for c in ["ca", "marge", "commission", "marge_par_dossier"]:
        aff[c] = aff[c].map(fmt_euro)
    for c in ["marge_pct", "taux_commission", "pct_deficit"]:
        aff[c] = aff[c].map(fmt_pct)
    aff["dossiers"] = aff["dossiers"].map(fmt_int)
    aff = aff[["regroupement_reseau", "dossiers", "ca", "marge", "marge_pct",
               "commission", "taux_commission", "pct_deficit"]]
    aff.columns = ["Canal", "Dossiers", "CA brut", "Marge nette", "Taux marge",
                   "Commissions", "Taux comm.", "% déficit."]
    st.dataframe(aff, width="stretch", hide_index=True)
with c2:
    fig = px.bar(canal, x="regroupement_reseau", y="marge", color="regroupement_reseau",
                 color_discrete_map=COULEURS_CANAL,
                 labels={"regroupement_reseau": "", "marge": "Marge nette (€)"})
    fig.update_layout(height=280, showlegend=False, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Niveau 2 : réseaux individuels ---
st.subheader("Réseaux : créateurs et destructeurs de valeur")
min_dossiers = st.slider("Nombre minimum de dossiers par réseau", 5, 200, 30,
                         key="_min_dos_reseau")
res = perf_par(df_f, ["reseau", "regroupement_reseau"])
res = res[res["dossiers"] >= min_dossiers].copy()
if len(res) == 0:
    st.info("Aucun réseau n'atteint ce seuil. Baisse le curseur.")
    st.stop()

top = res.sort_values("marge", ascending=False).head(12)
bottom = res.sort_values("marge", ascending=True).head(12)
g1, g2 = st.columns(2)
with g1:
    st.markdown("**Top créateurs de marge**")
    fig = px.bar(top.sort_values("marge"), x="marge", y="reseau", orientation="h",
                 color="regroupement_reseau", color_discrete_map=COULEURS_CANAL,
                 labels={"marge": "Marge nette (€)", "reseau": "", "regroupement_reseau": ""})
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")
with g2:
    st.markdown("**Principaux destructeurs de marge**")
    fig = px.bar(bottom.sort_values("marge", ascending=False), x="marge", y="reseau",
                 orientation="h", color="regroupement_reseau",
                 color_discrete_map=COULEURS_CANAL,
                 labels={"marge": "Marge nette (€)", "reseau": "", "regroupement_reseau": ""})
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0),
                      legend=dict(orientation="h", y=1.1))
    st.plotly_chart(fig, width="stretch")

st.divider()

# --- Niveau 3 : utilité (marge vs commission) ---
st.subheader("Utilité des réseaux : marge vs commission versée")
st.caption("Chaque point = un réseau. En bas à droite (beaucoup de commission, marge faible "
           "ou négative) = réseaux dont l'utilité est à questionner.")
fig = px.scatter(res, x="commission", y="marge", size="ca", color="regroupement_reseau",
                 color_discrete_map=COULEURS_CANAL, hover_name="reseau", size_max=45,
                 labels={"commission": "Commissions versées (€)", "marge": "Marge nette (€)",
                         "regroupement_reseau": ""})
fig.add_hline(y=0, line_dash="dash", line_color="grey")
fig.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0))
st.plotly_chart(fig, width="stretch")

# Réseaux à commission élevée ET marge négative : alerte utilité
alerte = res[(res["marge"] < 0) & (res["commission"] > 0)].sort_values("commission",
                                                                       ascending=False)
if len(alerte):
    st.markdown("**⚠️ Réseaux à commission versée mais marge négative :**")
    a = alerte.head(10)[["reseau", "regroupement_reseau", "dossiers", "commission", "marge"]].copy()
    a["commission"] = a["commission"].map(fmt_euro)
    a["marge"] = a["marge"].map(fmt_euro)
    a["dossiers"] = a["dossiers"].map(fmt_int)
    a.columns = ["Réseau", "Canal", "Dossiers", "Commissions", "Marge nette"]
    st.dataframe(a, width="stretch", hide_index=True)
