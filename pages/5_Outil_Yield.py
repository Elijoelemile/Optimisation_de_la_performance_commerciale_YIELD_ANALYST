"""Page — Outil Yield (segments à risque, opportunités de prix, simulateur)."""
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_pct, fmt_int, DIMENSIONS, perf_par)

setup_page("Outil Yield", icon="🎯")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

onglet1, onglet2, onglet3 = st.tabs(
    ["🔻 Segments à risque", "🔺 Opportunités de prix", "🧮 Simulateur"])

# ======================= 1. SEGMENTS À RISQUE =======================
with onglet1:
    st.caption("Croise les dimensions de ton choix et remonte les segments qui détruisent "
               "le plus de marge.")
    c1, c2 = st.columns([2, 1])
    with c1:
        dims = st.multiselect(
            "Dimensions à croiser", list(DIMENSIONS.keys()),
            default=["destination", "regroupement_reseau", "saison_touristique"],
            format_func=lambda c: DIMENSIONS[c], key="_risk_dims")
    with c2:
        seuil = st.slider("Min. dossiers / segment", 5, 100, 20, key="_risk_seuil")

    if not dims:
        st.info("Sélectionne au moins une dimension.")
    else:
        seg = perf_par(df_f, dims)
        seg = seg[seg["dossiers"] >= seuil].sort_values("marge")
        perte = seg.loc[seg["marge"] < 0, "marge"].sum()
        m1, m2 = st.columns(2)
        m1.metric("Perte cumulée (segments déficitaires)", fmt_euro(perte))
        m2.metric("Segments déficitaires", fmt_int(int((seg["marge"] < 0).sum())))

        aff = seg.head(20).copy()
        for c in ["ca", "marge"]:
            aff[c] = aff[c].map(fmt_euro)
        for c in ["marge_pct", "pct_deficit"]:
            aff[c] = aff[c].map(fmt_pct)
        aff["dossiers"] = aff["dossiers"].map(fmt_int)
        cols = dims + ["dossiers", "ca", "marge", "marge_pct", "pct_deficit"]
        aff = aff[cols]
        aff.columns = [DIMENSIONS[d] for d in dims] + \
            ["Dossiers", "CA brut", "Marge nette", "Taux marge", "% déficit."]
        st.dataframe(aff, width="stretch", hide_index=True)

# ======================= 2. OPPORTUNITÉS DE PRIX =======================
with onglet2:
    st.caption("Segments **rentables et solides** : bon taux de marge et peu de dossiers "
               "déficitaires. Ce sont les candidats naturels à une hausse de prix.")
    c1, c2, c3 = st.columns(3)
    with c1:
        dims2 = st.multiselect(
            "Dimensions", list(DIMENSIONS.keys()),
            default=["type_produit"],
            format_func=lambda c: DIMENSIONS[c], key="_opp_dims")
    with c2:
        seuil_marge = st.slider("Taux de marge minimum", 0, 20, 8, key="_opp_marge") / 100
    with c3:
        seuil_def = st.slider("% déficitaires maximum", 0, 50, 20, key="_opp_def") / 100
    min_dos = st.slider("Min. dossiers / segment", 5, 200, 30, key="_opp_mindos")

    if not dims2:
        st.info("Sélectionne au moins une dimension.")
    else:
        opp = perf_par(df_f, dims2)
        opp = opp[(opp["dossiers"] >= min_dos) &
                  (opp["marge_pct"] >= seuil_marge) &
                  (opp["pct_deficit"] <= seuil_def)].sort_values("ca", ascending=False)
        st.metric("Segments éligibles à un repricing", fmt_int(len(opp)))
        if len(opp) == 0:
            st.info("Aucun segment ne remplit ces critères. Assouplis les seuils.")
        else:
            aff = opp.head(20).copy()
            for c in ["ca", "marge", "prix_pax"]:
                aff[c] = aff[c].map(fmt_euro)
            for c in ["marge_pct", "pct_deficit"]:
                aff[c] = aff[c].map(fmt_pct)
            aff["dossiers"] = aff["dossiers"].map(fmt_int)
            cols = dims2 + ["dossiers", "ca", "marge", "marge_pct", "pct_deficit", "prix_pax"]
            aff = aff[cols]
            aff.columns = [DIMENSIONS[d] for d in dims2] + \
                ["Dossiers", "CA brut", "Marge nette", "Taux marge", "% déficit.",
                 "Prix moy./pax"]
            st.dataframe(aff, width="stretch", hide_index=True)

# ======================= 3. SIMULATEUR =======================
with onglet3:
    st.caption("Applique une hausse de prix à un périmètre ciblé et estime l'effet sur la "
               "marge. L'élasticité simule la perte de volume induite par la hausse.")
    c1, c2 = st.columns(2)
    with c1:
        dim_cible = st.selectbox("Cibler par", ["(Tout le périmètre filtré)"] +
                                 list(DIMENSIONS.keys()),
                                 format_func=lambda c: c if c.startswith("(")
                                 else DIMENSIONS[c], key="_sim_dim")
    with c2:
        if dim_cible.startswith("("):
            valeur = None
            perimetre = df_f
        else:
            valeurs = sorted(df_f[dim_cible].dropna().unique().tolist())
            valeur = st.selectbox("Valeur", valeurs, key="_sim_val")
            perimetre = df_f[df_f[dim_cible] == valeur]

    c3, c4 = st.columns(2)
    with c3:
        hausse = st.slider("Hausse de prix (%)", 0, 20, 5, key="_sim_hausse")
    with c4:
        elast = st.slider("Élasticité prix/demande", 0.0, 2.0, 0.0, 0.1, key="_sim_elast",
                          help="0 = pas de perte de volume. 1 = +1 % prix → −1 % volume.")

    ca0 = perimetre["ca_brut_ttc"].sum()
    achats0 = perimetre["achats_prev"].sum()
    comm0 = perimetre["commission"].sum()
    marge0 = perimetre["marge_nette"].sum()
    fv = max(0.0, 1 - elast * (hausse / 100))          # facteur de volume conservé
    ca1 = ca0 * (1 + hausse / 100) * fv
    marge1 = ca1 - achats0 * fv - comm0 * fv

    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Dossiers ciblés", fmt_int(len(perimetre)))
    d2.metric("Marge actuelle", fmt_euro(marge0))
    d3.metric("Marge simulée", fmt_euro(marge1), delta=fmt_euro(marge1 - marge0))
    d4.metric("Volume conservé", fmt_pct(fv))
    st.caption("Hypothèse simplifiée : achats et commissions proportionnels au volume. "
               "À affiner avec une vraie élasticité mesurée.")
