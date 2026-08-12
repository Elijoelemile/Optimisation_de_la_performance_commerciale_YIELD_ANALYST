"""Page — Bonus (données supplémentaires à demander)."""
import streamlit as st

from utils import setup_page, selecteur_source, filtres_lateraux

setup_page("Bonus — données à demander", icon="🎁")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

st.caption(
    "« Si vous aviez accès à d'autres données, lesquelles demanderiez-vous ? » "
    "— données qui enrichiraient l'analyse Yield au-delà de ce que la base "
    "actuelle permet."
)

DONNEES_BONUS = [
    ("Historique des prix / date de mise en vente",
     "Mesurer le timing et le yield réel — et, condition indispensable pour "
     "estimer une vraie élasticité prix/demande (voir le Système de "
     "recommandation, section Prix cible)."),
    ("Taux d'occupation hôtelière et allotements",
     "Connaître la contrainte de capacité réelle avant de recommander un "
     "repricing ou un transfert de volume vers un autre hôtel."),
    ("Prix des concurrents sur mêmes dates/destinations",
     "Situer les prix NG Travel par rapport au marché, pas seulement par "
     "rapport à l'historique interne."),
    ("Disponibilités et coûts aériens dans le temps",
     "Isoler le coût du vol de celui de l'hôtel dans ACHATS PREV — utile pour "
     "affiner les recommandations de compagnies aériennes."),
    ("Budget marketing par réseau",
     "Mesurer le ROI réel d'un canal, au-delà de la seule commission versée."),
    ("Statut d'annulation / remboursement des dossiers",
     "Distinguer une marge négative « normale » d'une marge négative due à "
     "une annulation tardive non répercutée."),
]

for titre, justification in DONNEES_BONUS:
    st.markdown(f"**{titre}**")
    st.caption(justification)
    st.write("")
