"""Page — Système de recommandation (4 recommandateurs par filtrage collaboratif / benchmarking)."""
import numpy as np
import pandas as pd
import streamlit as st
from sklearn.metrics.pairwise import cosine_similarity

from utils import setup_page, selecteur_source, filtres_lateraux, fmt_euro, fmt_pct, fmt_int, perf_par

setup_page("Système de recommandation", icon="🧭")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

st.caption(
    "Quatre recommandateurs, tous basés sur la comparaison à des pairs "
    "similaires ou déjà performants (filtrage collaboratif / benchmarking) : "
    "réseau ↔ produit, prix cible par segment, hôtels de substitution et "
    "compagnies aériennes de substitution."
)

# =======================================================================
# 1. Réseau ↔ produit (filtrage collaboratif)
# =======================================================================
st.divider()
st.subheader("🧭 1. Réseau ↔ produit")
st.caption(
    "Filtrage collaboratif appliqué à la matrice réseau × produit : pour un "
    "réseau donné, identifie les produits que des réseaux au profil de vente "
    "similaire distribuent bien, mais que ce réseau vend peu ou pas — des "
    "candidats concrets à lui proposer. Ne recommande que des produits déjà "
    "rentables ailleurs dans le portefeuille."
)

min_dossiers_reseau = st.slider("Volume minimum par réseau", 10, 100, 30, key="_min_dos_rec")

volumes = df_f.groupby("reseau")["ref_dossier"].count()
reseaux_valides = sorted(volumes[volumes >= min_dossiers_reseau].index)
base_reseaux = df_f[df_f["reseau"].isin(reseaux_valides)]

matrice_ca = base_reseaux.pivot_table(
    index="reseau", columns="type_produit", values="ca_brut_ttc", aggfunc="sum", fill_value=0
)

if matrice_ca.shape[0] < 3 or matrice_ca.shape[1] < 2:
    st.info(
        "Pas assez de réseaux ou de produits distincts sur ce périmètre pour "
        "construire des recommandations. Baisse le volume minimum ou élargis "
        "les filtres."
    )
else:
    # Profil de vente normalisé (part de CA par produit, pour chaque réseau) —
    # nécessaire pour comparer des réseaux de tailles très différentes.
    profil = matrice_ca.div(matrice_ca.sum(axis=1), axis=0)

    # Similarité réseau x réseau (cosinus sur les profils de vente)
    similarite = pd.DataFrame(
        cosine_similarity(profil.values), index=profil.index, columns=profil.index
    )

    # Rentabilité globale par produit (pour ne recommander que du rentable)
    perf_produits = perf_par(df_f, "type_produit").set_index("type_produit")

    def recommandations_pour(reseau: str, k_voisins: int, seuil_marge: float) -> tuple[pd.DataFrame, pd.Series]:
        """Retourne (recommandations, réseaux voisins utilisés)."""
        sims = similarite[reseau].drop(reseau).sort_values(ascending=False)
        voisins = sims[sims > 0].head(k_voisins)
        if voisins.empty:
            return pd.DataFrame(), voisins

        poids = voisins / voisins.sum()
        profil_voisins = profil.loc[voisins.index].mul(poids, axis=0).sum(axis=0)
        ecart = (profil_voisins - profil.loc[reseau]).sort_values(ascending=False)

        candidats = []
        for produit, score_ecart in ecart.items():
            if score_ecart <= 0 or produit not in perf_produits.index:
                continue
            ligne = perf_produits.loc[produit]
            if ligne["dossiers"] < 10 or ligne["marge_pct"] < seuil_marge:
                continue
            candidats.append({
                "type_produit": produit,
                "ecart": score_ecart,
                "marge_pct_global": ligne["marge_pct"],
                "ca_global": ligne["ca"],
                "dossiers_global": ligne["dossiers"],
            })
        return pd.DataFrame(candidats), voisins

    c1, c2, c3 = st.columns(3)
    with c1:
        reseau_choisi = st.selectbox("Réseau", reseaux_valides, key="_reseau_choisi")
    with c2:
        k_voisins = st.slider("Réseaux similaires pris en compte", 3, 15, 5, key="_k_voisins")
    with c3:
        seuil_marge_reseau = st.slider("Taux de marge minimum recommandé", -10, 30, 0, key="_seuil_marge_rec") / 100

    recos, voisins = recommandations_pour(reseau_choisi, k_voisins, seuil_marge_reseau)

    if voisins.empty:
        st.info("Aucun réseau suffisamment similaire trouvé pour générer des recommandations.")
    elif recos.empty:
        st.info("Aucun produit rentable ne ressort comme sous-représenté pour ce réseau sur ce périmètre.")
    else:
        aff = recos.sort_values("ecart", ascending=False).head(10).copy()
        aff["ecart"] = (aff["ecart"] * 100).map(lambda x: f"+{x:.1f} pts")
        aff["marge_pct_global"] = aff["marge_pct_global"].map(fmt_pct)
        aff["ca_global"] = aff["ca_global"].map(fmt_euro)
        aff["dossiers_global"] = aff["dossiers_global"].map(fmt_int)
        aff.columns = ["Produit", "Écart vs réseaux similaires", "Taux de marge (portefeuille)",
                       "CA (portefeuille)", "Dossiers (portefeuille)"]
        st.dataframe(aff, width="stretch", hide_index=True)
        st.caption(
            "« Écart » = part de CA que ce produit représente chez les réseaux "
            "similaires, moins la part qu'il représente chez ce réseau. Plus "
            "l'écart est élevé, plus le produit est sous-exploité par ce réseau "
            "relativement à ses pairs."
        )

    if not voisins.empty:
        with st.expander(f"Réseaux les plus similaires à {reseau_choisi}"):
            vdf = voisins.reset_index()
            vdf.columns = ["Réseau", "Similarité"]
            vdf["Similarité"] = vdf["Similarité"].map(lambda x: f"{x:.2f}")
            st.dataframe(vdf, width="stretch", hide_index=True)

    with st.expander("Vue globale : opportunités les plus fréquentes"):
        st.caption(
            "Produits qui ressortent comme sous-représentés chez le plus grand "
            "nombre de réseaux — des candidats à une diffusion plus large dans "
            "le portefeuille."
        )
        compte_opportunites: dict[str, list[float]] = {}
        for reseau in reseaux_valides:
            recos_r, _ = recommandations_pour(reseau, k_voisins, seuil_marge_reseau)
            for _, ligne in recos_r.iterrows():
                compte_opportunites.setdefault(ligne["type_produit"], []).append(ligne["ecart"])

        if compte_opportunites:
            synth = pd.DataFrame([
                {"type_produit": p, "nb_reseaux": len(v), "ecart_moyen": np.mean(v)}
                for p, v in compte_opportunites.items()
            ]).sort_values(["nb_reseaux", "ecart_moyen"], ascending=False).head(10)
            synth["ecart_moyen"] = (synth["ecart_moyen"] * 100).map(lambda x: f"+{x:.1f} pts")
            synth.columns = ["Produit", "Nb. réseaux concernés", "Écart moyen"]
            st.dataframe(synth, width="stretch", hide_index=True)
        else:
            st.info("Pas d'opportunité commune détectée sur ce périmètre.")

# =======================================================================
# 2. Prix cible par segment
# =======================================================================
st.divider()
st.subheader("💶 2. Prix cible par segment")
st.caption(
    "Pour un produit donné (destination × durée), compare ses sous-segments "
    "(canal × délai de réservation) entre eux : ceux qui vendent nettement "
    "moins cher que des sous-segments comparables et rentables du même "
    "produit sont des candidats à un ajustement de prix."
)

produits_disponibles = sorted(df_f["type_produit"].dropna().unique())
c4, c5 = st.columns(2)
with c4:
    produit_choisi = st.selectbox("Produit à analyser", produits_disponibles, key="_produit_prix")
with c5:
    min_dossiers_seg = st.slider("Volume minimum par sous-segment", 5, 50, 15, key="_min_dos_seg")


def analyser_prix_segment(base_produit: pd.DataFrame, min_dossiers: int):
    g = (
        base_produit.groupby(["regroupement_reseau", "tranche_delai"], dropna=False)
        .agg(dossiers=("ref_dossier", "count"),
             prix_moyen=("prix_moyen_pax", "mean"),
             ca=("ca_brut_ttc", "sum"),
             marge=("marge_nette", "sum"),
             pct_deficit=("dossier_deficitaire", "mean"))
        .reset_index()
    )
    g = g[g["dossiers"] >= min_dossiers]
    if len(g) < 2:
        return None
    g["marge_pct"] = g["marge"] / g["ca"].where(g["ca"] != 0)
    return g


base_produit = df_f[df_f["type_produit"] == produit_choisi]
g_seg = analyser_prix_segment(base_produit, min_dossiers_seg)

if g_seg is None:
    st.info(
        "Pas assez de sous-segments comparables (canal × délai) sur ce "
        "produit pour établir un benchmark. Baisse le volume minimum."
    )
else:
    reference = g_seg[(g_seg["marge_pct"] >= 0.05) & (g_seg["pct_deficit"] <= 0.3)] \
        .sort_values("prix_moyen", ascending=False)
    if reference.empty:
        st.info(
            "Aucun sous-segment de ce produit n'atteint le seuil de marge/déficit "
            "pour servir de référence."
        )
    else:
        top_reference = reference.head(3)
        prix_cible = float(np.average(top_reference["prix_moyen"], weights=top_reference["dossiers"]))
        st.metric("Prix cible suggéré (par passager)", fmt_euro(prix_cible))
        st.caption(
            "Moyenne pondérée du prix des sous-segments sains les plus chers "
            "(marge ≥ 5 %, ≤ 30 % de dossiers déficitaires) : "
            + ", ".join(f"{r.regroupement_reseau} / {r.tranche_delai}" for r in top_reference.itertuples())
        )

        sous_perf = g_seg[g_seg["prix_moyen"] < prix_cible * 0.9].sort_values("prix_moyen").copy()
        if sous_perf.empty:
            st.info("Aucun sous-segment n'est significativement en dessous du prix cible.")
        else:
            sous_perf["ecart_eur"] = prix_cible - sous_perf["prix_moyen"]
            sous_perf["gain_potentiel"] = sous_perf["ecart_eur"] * sous_perf["dossiers"]
            aff = sous_perf.copy()
            aff["prix_moyen"] = aff["prix_moyen"].map(fmt_euro)
            aff["marge_pct"] = aff["marge_pct"].map(fmt_pct)
            aff["pct_deficit"] = aff["pct_deficit"].map(fmt_pct)
            aff["ecart_eur"] = aff["ecart_eur"].map(fmt_euro)
            aff["gain_potentiel"] = aff["gain_potentiel"].map(fmt_euro)
            aff["dossiers"] = aff["dossiers"].map(fmt_int)
            aff = aff[["regroupement_reseau", "tranche_delai", "dossiers", "prix_moyen",
                       "marge_pct", "pct_deficit", "ecart_eur", "gain_potentiel"]]
            aff.columns = ["Canal", "Délai de réservation", "Dossiers", "Prix actuel/pax",
                           "Taux marge", "% déficit.", "Écart vs cible", "Gain potentiel (CA)"]
            st.dataframe(aff, width="stretch", hide_index=True)
            st.caption(
                "⚠️ Le « gain potentiel » suppose un volume inchangé au nouveau prix "
                "(pas d'élasticité appliquée) — c'est un plafond théorique, pas une "
                "prévision, à valider avant toute décision tarifaire."
            )

# =======================================================================
# 3. Hôtels de substitution
# =======================================================================
st.divider()
st.subheader("🏨 3. Hôtels de substitution")
st.caption(
    "Pour une destination donnée, identifie les hôtels au taux d'achat le "
    "plus élevé (le moins bien négocié) et propose des hôtels alternatifs "
    "dans la même destination, mieux négociés, comme candidats de "
    "substitution de volume."
)

destinations_disponibles = sorted(df_f["destination"].dropna().unique())
c6, c7 = st.columns(2)
with c6:
    destination_choisie = st.selectbox("Destination", destinations_disponibles, key="_dest_hotel")
with c7:
    min_dossiers_hotel = st.slider("Volume minimum par hôtel", 5, 50, 15, key="_min_dos_hotel")

base_dest = df_f[df_f["destination"] == destination_choisie]
gh = (
    base_dest.groupby("hotel")
    .agg(dossiers=("ref_dossier", "count"),
         ca=("ca_brut_ttc", "sum"),
         achats=("achats_prev", "sum"),
         marge=("marge_nette", "sum"))
    .reset_index()
)
gh = gh[gh["dossiers"] >= min_dossiers_hotel]

if len(gh) < 2:
    st.info(
        "Pas assez d'hôtels avec un volume suffisant sur cette destination "
        "pour comparer. Baisse le volume minimum."
    )
else:
    gh["taux_achat"] = gh["achats"] / gh["ca"].where(gh["ca"] != 0)
    gh["marge_pct"] = gh["marge"] / gh["ca"].where(gh["ca"] != 0)
    gh = gh.sort_values("taux_achat", ascending=False).reset_index(drop=True)

    hotel_a_examiner = st.selectbox(
        "Hôtel à examiner", gh["hotel"].tolist(), index=0, key="_hotel_source",
        help="Par défaut : l'hôtel au taux d'achat le plus élevé de la destination.",
    )
    source = gh[gh["hotel"] == hotel_a_examiner].iloc[0]

    m1, m2 = st.columns(2)
    m1.metric(f"Taux d'achat — {hotel_a_examiner}", fmt_pct(source["taux_achat"]))
    m2.metric("Marge nette actuelle", fmt_euro(source["marge"]))

    candidats = gh[
        (gh["hotel"] != hotel_a_examiner) & (gh["taux_achat"] < source["taux_achat"])
    ].sort_values("taux_achat").head(5).copy()

    if candidats.empty:
        st.info("Aucun hôtel mieux négocié trouvé dans cette destination pour ce volume minimum.")
    else:
        candidats["economie_estimee"] = source["ca"] * (source["taux_achat"] - candidats["taux_achat"])
        aff2 = candidats.copy()
        aff2["dossiers"] = aff2["dossiers"].map(fmt_int)
        aff2["taux_achat"] = aff2["taux_achat"].map(fmt_pct)
        aff2["marge_pct"] = aff2["marge_pct"].map(fmt_pct)
        aff2["economie_estimee"] = aff2["economie_estimee"].map(fmt_euro)
        aff2 = aff2[["hotel", "dossiers", "taux_achat", "marge_pct", "economie_estimee"]]
        aff2.columns = ["Hôtel alternatif", "Dossiers (actuel)", "Taux d'achat",
                        "Taux marge", "Économie estimée si volume transféré"]
        st.dataframe(aff2, width="stretch", hide_index=True)
        st.caption(
            "⚠️ « Économie estimée » suppose que le CA de l'hôtel examiné serait "
            "intégralement transféré à l'hôtel alternatif, au taux d'achat "
            "actuellement observé chez celui-ci — hypothèse simplifiée, à valider "
            "avec les acheteurs (capacité disponible, qualité comparable, etc.)."
        )

# =======================================================================
# 4. Compagnies aériennes de substitution
# =======================================================================
st.divider()
st.subheader("✈️ 4. Compagnies aériennes de substitution")
st.caption(
    "Même principe que les hôtels : pour une destination donnée, identifie la "
    "compagnie aérienne à la marge nette la plus faible et propose des "
    "alternatives mieux positionnées sur la même destination. "
    "⚠️ `ACHATS PREV` regroupe le coût hôtel **et** vol sans les distinguer — "
    "l'écart de marge entre compagnies peut donc aussi refléter des "
    "différences d'hôtel plutôt que la compagnie seule."
)

c8, c9 = st.columns(2)
with c8:
    destination_cie = st.selectbox("Destination", destinations_disponibles, key="_dest_cie")
with c9:
    min_dossiers_cie = st.slider("Volume minimum par compagnie", 5, 50, 15, key="_min_dos_cie")

base_dest_cie = df_f[df_f["destination"] == destination_cie]
gc = (
    base_dest_cie.groupby("compagnie_nom")
    .agg(dossiers=("ref_dossier", "count"),
         ca=("ca_brut_ttc", "sum"),
         marge=("marge_nette", "sum"),
         commission=("commission", "sum"))
    .reset_index()
)
gc = gc[gc["dossiers"] >= min_dossiers_cie]

if len(gc) < 2:
    st.info(
        "Pas assez de compagnies avec un volume suffisant sur cette destination "
        "pour comparer. Baisse le volume minimum."
    )
else:
    gc["marge_pct"] = gc["marge"] / gc["ca"].where(gc["ca"] != 0)
    gc = gc.sort_values("marge_pct").reset_index(drop=True)

    cie_a_examiner = st.selectbox(
        "Compagnie à examiner", gc["compagnie_nom"].tolist(), index=0, key="_cie_source",
        help="Par défaut : la compagnie à la marge nette la plus faible sur cette destination.",
    )
    source_cie = gc[gc["compagnie_nom"] == cie_a_examiner].iloc[0]

    m3, m4 = st.columns(2)
    m3.metric(f"Taux de marge — {cie_a_examiner}", fmt_pct(source_cie["marge_pct"]))
    m4.metric("Dossiers concernés", fmt_int(int(source_cie["dossiers"])))

    candidats_cie = gc[
        (gc["compagnie_nom"] != cie_a_examiner) & (gc["marge_pct"] > source_cie["marge_pct"])
    ].sort_values("marge_pct", ascending=False).head(5).copy()

    if candidats_cie.empty:
        st.info("Aucune compagnie plus rentable trouvée dans cette destination pour ce volume minimum.")
    else:
        candidats_cie["gain_estime"] = source_cie["ca"] * (candidats_cie["marge_pct"] - source_cie["marge_pct"])
        aff3 = candidats_cie.copy()
        aff3["dossiers"] = aff3["dossiers"].map(fmt_int)
        aff3["marge_pct"] = aff3["marge_pct"].map(fmt_pct)
        aff3["gain_estime"] = aff3["gain_estime"].map(fmt_euro)
        aff3 = aff3[["compagnie_nom", "dossiers", "marge_pct", "gain_estime"]]
        aff3.columns = ["Compagnie alternative", "Dossiers (actuel)", "Taux marge",
                        "Gain estimé si volume transféré"]
        st.dataframe(aff3, width="stretch", hide_index=True)
        st.caption(
            "⚠️ « Gain estimé » suppose que le CA de la compagnie examinée serait "
            "intégralement transféré à l'alternative, au taux de marge "
            "actuellement observé chez celle-ci — hypothèse simplifiée (dispo "
            "vols, accords commerciaux) à valider avec les acheteurs."
        )
