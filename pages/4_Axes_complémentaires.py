"""Page — Performance par axe (configurable) + croisements."""
import plotly.express as px
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_pct, fmt_int, DIMENSIONS, perf_par,
                   ORDRE_DELAI, ORDRE_SAISON_TOURISTIQUE)

setup_page("Performance par axe", icon="🧩")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

ORDRES = {"tranche_delai": ORDRE_DELAI, "saison_touristique": ORDRE_SAISON_TOURISTIQUE}

# ============ 0. Ville de départ & délai de réservation (vues dédiées) ============
st.subheader("Performance par ville de départ")
g_ville = perf_par(df_f, "ville_depart").sort_values("marge", ascending=False)
top_ville = g_ville.head(15)
cv1, cv2 = st.columns(2)
with cv1:
    st.markdown("**Marge nette**")
    fig = px.bar(top_ville.sort_values("marge"), x="marge", y="ville_depart", orientation="h",
                 labels={"marge": "Marge nette (€)", "ville_depart": ""})
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
with cv2:
    st.markdown("**Taux de marge**")
    fig = px.bar(top_ville.sort_values("marge_pct"), x="marge_pct", y="ville_depart",
                 orientation="h", color="marge_pct", color_continuous_scale="RdYlGn",
                 color_continuous_midpoint=0,
                 labels={"marge_pct": "Taux de marge", "ville_depart": ""})
    fig.update_xaxes(tickformat=".1%")
    fig.update_layout(height=380, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

st.divider()

st.subheader("Performance par délai de réservation")
g_delai = perf_par(df_f, "tranche_delai")
ordre_delai_present = [d for d in ORDRE_DELAI if d in g_delai["tranche_delai"].values]
g_delai = g_delai.set_index("tranche_delai").reindex(ordre_delai_present).reset_index()
cd1, cd2 = st.columns(2)
with cd1:
    st.markdown("**Marge nette**")
    fig = px.bar(g_delai, x="tranche_delai", y="marge",
                 category_orders={"tranche_delai": ordre_delai_present},
                 labels={"marge": "Marge nette (€)", "tranche_delai": ""})
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
with cd2:
    st.markdown("**Taux de marge**")
    fig = px.bar(g_delai, x="tranche_delai", y="marge_pct",
                 category_orders={"tranche_delai": ordre_delai_present},
                 color="marge_pct", color_continuous_scale="RdYlGn", color_continuous_midpoint=0,
                 labels={"marge_pct": "Taux de marge", "tranche_delai": ""})
    fig.update_yaxes(tickformat=".1%")
    fig.update_layout(height=360, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

st.divider()

# ============ 1. Performance sur un axe (configurable) ============
st.subheader("Performance sur un axe")
axe = st.selectbox("Axe d'analyse", list(DIMENSIONS.keys()),
                   format_func=lambda c: DIMENSIONS[c], key="_axe_comp")

g = perf_par(df_f, axe).sort_values("marge", ascending=False)
top = g.sort_values("ca", ascending=False).head(15)

c1, c2 = st.columns(2)
with c1:
    st.markdown("**Marge nette**")
    fig = px.bar(top.sort_values("marge"), x="marge", y=axe, orientation="h",
                 labels={"marge": "Marge nette (€)", axe: ""})
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0))
    st.plotly_chart(fig, width="stretch")
with c2:
    st.markdown("**Taux de marge**")
    fig = px.bar(top.sort_values("marge_pct"), x="marge_pct", y=axe, orientation="h",
                 color="marge_pct", color_continuous_scale="RdYlGn",
                 color_continuous_midpoint=0, labels={"marge_pct": "Taux de marge", axe: ""})
    fig.update_xaxes(tickformat=".1%")
    fig.update_layout(height=430, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
    st.plotly_chart(fig, width="stretch")

with st.expander("Tableau détaillé"):
    aff = g.copy()
    for c in ["ca", "marge", "commission", "prix_pax", "marge_par_dossier"]:
        aff[c] = aff[c].map(fmt_euro)
    for c in ["marge_pct", "taux_commission", "pct_deficit"]:
        aff[c] = aff[c].map(fmt_pct)
    aff["dossiers"] = aff["dossiers"].map(fmt_int)
    aff = aff[[axe, "dossiers", "ca", "marge", "marge_pct", "marge_par_dossier",
               "prix_pax", "taux_commission", "pct_deficit"]]
    aff.columns = [DIMENSIONS[axe], "Dossiers", "CA brut", "Marge nette", "Taux marge",
                   "Marge/dossier", "Prix moy./pax", "Taux comm.", "% déficit."]
    st.dataframe(aff, width="stretch", hide_index=True)

st.divider()

# ============ 2. Croisement configurable (heatmap) ============
st.subheader("Croisement de deux axes")
st.caption("Choisis les deux dimensions à croiser et la mesure. Idéal pour localiser où "
           "se crée et se détruit la marge (ex. Type de produit × Intensité de saison).")

col1, col2, col3 = st.columns(3)
with col1:
    dim_lignes = st.selectbox("Lignes", list(DIMENSIONS.keys()),
                              index=list(DIMENSIONS).index("type_produit"),
                              format_func=lambda c: DIMENSIONS[c], key="_hm_lignes")
with col2:
    dim_cols = st.selectbox("Colonnes", list(DIMENSIONS.keys()),
                            index=list(DIMENSIONS).index("saison_touristique"),
                            format_func=lambda c: DIMENSIONS[c], key="_hm_cols")
with col3:
    mesure = st.selectbox("Mesure", ["Taux de marge", "Marge nette", "Chiffre d'affaires",
                                     "% déficitaires"], key="_hm_mesure")

if dim_lignes == dim_cols:
    st.info("Choisis deux dimensions différentes pour le croisement.")
else:
    gg = perf_par(df_f, [dim_lignes, dim_cols])
    MES = {"Taux de marge": ("marge_pct", ".1%", "RdYlGn", 0),
           "Marge nette": ("marge", ",.0f", "RdYlGn", 0),
           "Chiffre d'affaires": ("ca", ",.0f", "Blues", None),
           "% déficitaires": ("pct_deficit", ".0%", "Reds", None)}
    col, tfmt, scale, mid = MES[mesure]
    table = gg.pivot(index=dim_lignes, columns=dim_cols, values=col)
    if dim_cols in ORDRES:
        table = table[[c for c in ORDRES[dim_cols] if c in table.columns]]
    if dim_lignes in ORDRES:
        table = table.reindex([r for r in ORDRES[dim_lignes] if r in table.index])
    fig = px.imshow(table, text_auto=tfmt, aspect="auto", color_continuous_scale=scale,
                    color_continuous_midpoint=mid, labels=dict(color=mesure))
    h = max(300, 60 + 34 * len(table.index))
    fig.update_layout(height=h, margin=dict(l=0, r=0, t=10, b=0), coloraxis_showscale=False)
    fig.update_xaxes(title=""); fig.update_yaxes(title="")
    st.plotly_chart(fig, width="stretch")
