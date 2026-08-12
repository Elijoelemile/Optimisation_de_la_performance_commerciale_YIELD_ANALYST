"""Page — Recommandations & bonus (synthèse Yield auto + données à demander)."""
import streamlit as st

from utils import (setup_page, selecteur_source, filtres_lateraux,
                   fmt_euro, fmt_pct, fmt_int, perf_par)

setup_page("Recommandations & bonus", icon="💡")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()


def extreme(dim, col, ascending, min_dos=30):
    g = perf_par(df_f, dim)
    g = g[g["dossiers"] >= min_dos]
    if len(g) == 0:
        return None
    return g.sort_values(col, ascending=ascending).iloc[0]

st.subheader("Enseignements clés (calculés sur le périmètre filtré)")

# Ligne 1 : global
pct_def = df_f["dossier_deficitaire"].mean()
perte = df_f.loc[df_f["marge_nette"] < 0, "marge_nette"].sum()
ca = df_f["ca_brut_ttc"].sum()
marge = df_f["marge_nette"].sum()
a, b, c = st.columns(3)
a.metric("Taux de marge global", fmt_pct(marge / ca if ca else float("nan")))
b.metric("Dossiers déficitaires", fmt_pct(pct_def))
c.metric("Marge détruite (cumul)", fmt_euro(perte))

st.markdown("**Leviers identifiés automatiquement :**")

best_prod = extreme("type_produit", "marge_pct", ascending=False)
worst_prod = extreme("type_produit", "marge_pct", ascending=True)
best_delai = extreme("tranche_delai", "marge_pct", ascending=False, min_dos=50)
worst_res = extreme("reseau", "marge", ascending=True)
best_dest = extreme("destination", "marge_pct", ascending=False)

lignes = []
if best_prod is not None:
    lignes.append(f"🔺 **Produit le plus rentable** : *{best_prod['type_produit']}* "
                  f"({fmt_pct(best_prod['marge_pct'])} de marge) — candidat à un repricing "
                  "et à pousser commercialement.")
if worst_prod is not None:
    lignes.append(f"🔻 **Produit à corriger** : *{worst_prod['type_produit']}* "
                  f"({fmt_pct(worst_prod['marge_pct'])} de marge) — à repricer ou "
                  "restructurer.")
if best_delai is not None:
    lignes.append(f"⏱️ **Comportement de réservation le plus rentable** : "
                  f"*{best_delai['tranche_delai']}* ({fmt_pct(best_delai['marge_pct'])}) — "
                  "à favoriser dans la politique tarifaire.")
if worst_res is not None and worst_res["marge"] < 0:
    lignes.append(f"🔗 **Réseau destructeur de valeur** : *{worst_res['reseau']}* "
                  f"({fmt_euro(worst_res['marge'])} de marge) — utilité à renégocier.")
if best_dest is not None:
    lignes.append(f"🗺️ **Destination la plus rentable** : *{best_dest['destination']}* "
                  f"({fmt_pct(best_dest['marge_pct'])}).")
for l in lignes:
    st.markdown("- " + l)

st.divider()
st.subheader("Pistes de recommandations Yield")
st.markdown(
    "- **Repricing** ciblé des produits/segments rentables et stables "
    "(onglet « Opportunités de prix » de l'Outil Yield).\n"
    "- **Traitement des segments déficitaires** identifiés (onglet « Segments à risque »).\n"
    "- **Renégociation** des réseaux à commission élevée et marge négative (page Réseaux).\n"
    "- **Encadrement des comportements de réservation** les moins rentables (page par axe).\n"
    "- **Arbitrage saisonnier** : ajuster les prix selon l'intensité de saison par destination.\n"
)

st.divider()
st.subheader("Bonus — données supplémentaires à demander")
st.markdown(
    "- Historique des prix / date de mise en vente (mesurer le timing et le yield réel).\n"
    "- Taux d'occupation hôtelière et allotements (contrainte de capacité).\n"
    "- Prix des concurrents sur mêmes dates/destinations.\n"
    "- Disponibilités et coûts aériens dans le temps.\n"
    "- Budget marketing par réseau (ROI d'un canal).\n"
    "- Statut d'annulation / remboursement des dossiers.\n"
)
