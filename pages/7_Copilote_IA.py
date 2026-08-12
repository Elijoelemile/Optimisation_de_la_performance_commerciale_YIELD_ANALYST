"""Page — Copilote IA (résumé en langage naturel de chaque page, via l'API Mistral)."""
import os

import streamlit as st

try:
    from mistralai.client import Mistral
    from mistralai.client.errors import SDKError
    MISTRAL_DISPONIBLE = True
except ImportError:
    MISTRAL_DISPONIBLE = False

from utils import setup_page, selecteur_source, filtres_lateraux, fmt_euro, fmt_pct, fmt_int, perf_par, kpis

setup_page("Copilote IA", icon="🤖")

df = selecteur_source()
if df is None:
    st.stop()
df_f, ctx = filtres_lateraux(df)
if len(df_f) == 0:
    st.warning("Aucun dossier ne correspond aux filtres.")
    st.stop()

st.caption(
    "Clique sur une page pour que le Copilote en génère un résumé en langage "
    "naturel, à partir des chiffres calculés sur le périmètre filtré actuel "
    "(via l'API Mistral)."
)

# ---------------------------------------------------------------------
# Constructeurs de contexte : un par page à résumer
# ---------------------------------------------------------------------

def contexte_accueil(base):
    k = kpis(base)
    par_dest = perf_par(base, "destination").sort_values("ca", ascending=False)
    par_canal = perf_par(base, "regroupement_reseau").sort_values("marge", ascending=False)
    lignes = [
        f"CA brut total : {fmt_euro(k['ca'])}",
        f"Marge nette totale : {fmt_euro(k['marge'])} ({fmt_pct(k['marge_pct'])} du CA)",
        f"Dossiers déficitaires : {fmt_pct(k['pct_deficit'])}",
        f"Nombre de dossiers : {fmt_int(k['nb_dossiers'])}, passagers : {fmt_int(k['nb_pax'])}",
        f"Prix moyen par passager : {fmt_euro(k['prix_pax'])}",
    ]
    if len(par_dest):
        lignes.append(f"Destination générant le plus de CA : {par_dest.iloc[0]['destination']} "
                       f"({fmt_euro(par_dest.iloc[0]['ca'])})")
    if len(par_canal):
        lignes.append(f"Canal générant le plus de marge : {par_canal.iloc[0]['regroupement_reseau']} "
                       f"({fmt_euro(par_canal.iloc[0]['marge'])})")
    return "\n".join(lignes)


def contexte_evolution(base):
    par_saison = perf_par(base, "saison").sort_values("saison")
    lignes = ["Comparaison par saison (année de départ) :"]
    for _, r in par_saison.iterrows():
        lignes.append(f"- {r['saison']} : CA {fmt_euro(r['ca'])}, marge {fmt_euro(r['marge'])} "
                       f"({fmt_pct(r['marge_pct'])}), {fmt_int(int(r['dossiers']))} dossiers")
    return "\n".join(lignes)


def contexte_destinations(base):
    g = perf_par(base, "destination").sort_values("marge_pct", ascending=False)
    if g.empty:
        return "Aucune donnée disponible sur ce périmètre."
    lignes = [
        f"{len(g)} destinations analysées.",
        f"Meilleure marge : {g.iloc[0]['destination']} ({fmt_pct(g.iloc[0]['marge_pct'])}, "
        f"CA {fmt_euro(g.iloc[0]['ca'])})",
        f"Marge la plus faible : {g.iloc[-1]['destination']} ({fmt_pct(g.iloc[-1]['marge_pct'])}, "
        f"CA {fmt_euro(g.iloc[-1]['ca'])})",
    ]
    return "\n".join(lignes)


def contexte_reseaux(base):
    par_canal = perf_par(base, "regroupement_reseau").sort_values("marge", ascending=False)
    par_reseau = perf_par(base, "reseau")
    par_reseau = par_reseau[par_reseau["dossiers"] >= 30]
    lignes = ["Performance par canal :"]
    for _, r in par_canal.iterrows():
        lignes.append(f"- {r['regroupement_reseau']} : marge {fmt_euro(r['marge'])} "
                       f"({fmt_pct(r['marge_pct'])}), commission {fmt_euro(r['commission'])}")
    if len(par_reseau):
        pire = par_reseau.sort_values("marge").iloc[0]
        lignes.append(f"Réseau individuel le moins rentable (≥30 dossiers) : {pire['reseau']} "
                       f"({fmt_euro(pire['marge'])} de marge)")
    return "\n".join(lignes)


def contexte_axes(base):
    par_ville = perf_par(base, "ville_depart")
    par_ville = par_ville[par_ville["dossiers"] >= 30].sort_values("marge_pct", ascending=False)
    par_delai = perf_par(base, "tranche_delai")
    lignes = []
    if len(par_ville):
        lignes.append(f"Meilleure ville de départ : {par_ville.iloc[0]['ville_depart']} "
                       f"({fmt_pct(par_ville.iloc[0]['marge_pct'])} de marge)")
        lignes.append(f"Ville de départ la moins rentable : {par_ville.iloc[-1]['ville_depart']} "
                       f"({fmt_pct(par_ville.iloc[-1]['marge_pct'])})")
    if len(par_delai):
        meilleur_delai = par_delai.sort_values("marge_pct", ascending=False).iloc[0]
        lignes.append(f"Délai de réservation le plus rentable : {meilleur_delai['tranche_delai']} "
                       f"({fmt_pct(meilleur_delai['marge_pct'])})")
    return "\n".join(lignes) if lignes else "Pas assez de données sur ce périmètre."


def contexte_yield(base):
    perte = base.loc[base["marge_nette"] < 0, "marge_nette"].sum()
    nb_deficit = int(base["dossier_deficitaire"].sum())
    seg = perf_par(base, ["destination", "regroupement_reseau"])
    seg = seg[seg["dossiers"] >= 20]
    opp = seg[(seg["marge_pct"] >= 0.08) & (seg["pct_deficit"] <= 0.2)].sort_values("ca", ascending=False)
    lignes = [f"{fmt_int(nb_deficit)} dossiers déficitaires, pour {fmt_euro(abs(perte))} de "
              "marge détruite au total."]
    if len(opp):
        top = opp.iloc[0]
        lignes.append(f"Segment le plus solide pour un repricing : {top['destination']} / "
                       f"{top['regroupement_reseau']} ({fmt_pct(top['marge_pct'])} de marge, "
                       f"{fmt_int(int(top['dossiers']))} dossiers)")
    return "\n".join(lignes)


def contexte_systeme_reco(base):
    nb_reseaux = base["reseau"].nunique()
    nb_produits = base["type_produit"].nunique()
    nb_hotels = base["hotel"].nunique()
    nb_compagnies = base["compagnie_nom"].nunique()
    return "\n".join([
        "Cette page propose 4 recommandateurs interactifs par filtrage collaboratif "
        "et benchmarking :",
        f"- {nb_reseaux} réseaux et {nb_produits} produits distincts pour le "
        "recommandateur réseau ↔ produit",
        f"- {nb_hotels} hôtels et {nb_compagnies} compagnies aériennes pour les "
        "recommandateurs de substitution",
        "Chaque outil compare une entité (réseau, hôtel, compagnie) à ses pairs "
        "les plus similaires ou les plus rentables.",
    ])


PAGES_A_RESUMER = {
    "Vue d'ensemble": ("🧭", contexte_accueil),
    "Évolution temporelle": ("📈", contexte_evolution),
    "Performance par destination": ("🗺️", contexte_destinations),
    "Performance par réseau": ("🔗", contexte_reseaux),
    "Performance par axe": ("🧩", contexte_axes),
    "Outil Yield": ("🎯", contexte_yield),
    "Système de recommandation": ("🧭", contexte_systeme_reco),
}


# ---------------------------------------------------------------------
# Appel Mistral
# ---------------------------------------------------------------------

def obtenir_client_mistral():
    cle = None
    try:
        cle = st.secrets.get("MISTRAL_API_KEY")
    except Exception:
        cle = None
    cle = cle or os.environ.get("MISTRAL_API_KEY")
    if not cle:
        return None
    return Mistral(api_key=cle)


def generer_resume(client, nom_page: str, contexte: str) -> str:
    reponse = client.chat.complete(
        model="mistral-large-latest",
        messages=[
            {"role": "system", "content": (
                "Tu es un analyste Yield Management pour NG Travel, tour-opérateur "
                "spécialisé sur la Grèce. On te donne les chiffres clés d'une page "
                "d'un tableau de bord. Rédige un résumé clair et actionnable en "
                "français, 2 à 3 paragraphes, sans puces, sans titre, ton "
                "professionnel et direct."
            )},
            {"role": "user", "content": f"Page à résumer : {nom_page}\n\nChiffres :\n{contexte}"},
        ],
    )
    return reponse.choices[0].message.content


# ---------------------------------------------------------------------
# Grille de boutons + résumé
# ---------------------------------------------------------------------

if not MISTRAL_DISPONIBLE:
    st.info("Le package `mistralai` n'est pas installé (ajouté à requirements.txt).")
else:
    cle_absente = obtenir_client_mistral() is None
    if cle_absente:
        st.info(
            "Aucune clé API Mistral configurée. Pour activer le Copilote : crée "
            "`.streamlit/secrets.toml` avec `MISTRAL_API_KEY = \"...\"` en local, "
            "ou ajoute-la dans les *Secrets* de l'app sur Streamlit Cloud."
        )

    if "_resume_titre" not in st.session_state:
        st.session_state["_resume_titre"] = None
        st.session_state["_resume_texte"] = None
        st.session_state["_resume_erreur"] = None

    noms = list(PAGES_A_RESUMER.keys())
    colonnes = st.columns(4)
    for i, nom in enumerate(noms):
        icone, constructeur_contexte = PAGES_A_RESUMER[nom]
        with colonnes[i % 4]:
            if st.button(f"{icone} {nom}", key=f"_btn_resume_{i}", width="stretch",
                        disabled=cle_absente):
                client = obtenir_client_mistral()
                st.session_state["_resume_titre"] = nom
                st.session_state["_resume_texte"] = None
                st.session_state["_resume_erreur"] = None
                try:
                    contexte = constructeur_contexte(df_f)
                    with st.spinner(f"Génération du résumé — {nom}…"):
                        texte = generer_resume(client, nom, contexte)
                    st.session_state["_resume_texte"] = texte
                except SDKError as e:
                    st.session_state["_resume_erreur"] = f"Erreur API Mistral : {e}"
                except Exception as e:
                    st.session_state["_resume_erreur"] = f"Erreur inattendue : {e}"

    if st.session_state.get("_resume_titre"):
        st.divider()
        icone_choisi, _ = PAGES_A_RESUMER[st.session_state["_resume_titre"]]
        st.subheader(f"📝 {icone_choisi} {st.session_state['_resume_titre']}")
        if st.session_state.get("_resume_erreur"):
            st.warning(st.session_state["_resume_erreur"])
        elif st.session_state.get("_resume_texte"):
            st.markdown(st.session_state["_resume_texte"])
            st.caption(
                "Résumé généré par l'API Mistral, à partir des chiffres du "
                "périmètre filtré au moment du clic — recharge le bouton après "
                "avoir changé les filtres pour un résumé à jour."
            )
