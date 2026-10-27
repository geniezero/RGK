"""IA Platform — point d'entrée de l'application Streamlit.

Lancement : lancer.bat (Windows) ou ./lancer.sh (macOS / Linux), ou à la main : streamlit run app.py
Le code est dans le dossier ia_platform/ (voir README.md).
"""
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ecrans import (accueil, affectations, assets, capacity_planning, clients, consommation, dashboard, demarrage, devis,
                                exercices, offres, parametres, rapports)
from ia_platform.ui import theme
from ia_platform.ui.navigation import PAGES

st.set_page_config(page_title="IA Platform", page_icon="🧮", layout="wide")
L.init_db()
theme.appliquer()

if not L.est_initialise():
    demarrage.page()
    st.stop()

# ------------------------------------------------------------------ navigation, regroupée par section
SECTIONS = {
    "": [(accueil.page, "Accueil", ":material/home:", "accueil")],
    "Référentiel": [(assets.page, "Assets", ":material/dns:", "assets"),
                    (clients.page, "Clients", ":material/group:", "clients"),
                    (offres.page, "Offres", ":material/inventory_2:", "offres")],
    "Activité": [(affectations.page, "Affectations", ":material/swap_horiz:", "affectation"),
                 (devis.page, "Devis", ":material/request_quote:", "devis"),
                 (capacity_planning.page, "Capacity planning", ":material/trending_up:", "capacity-planning")],
    "Suivi": [(consommation.page, "Consommation", ":material/calendar_month:", "consommation"),
              (dashboard.page, "Dashboard", ":material/monitoring:", "dashboard"),
              (rapports.page, "Rapports Excel", ":material/table_view:", "rapports")],
    "Administration": [(exercices.page, "Exercices", ":material/event_note:", "exercices"),
                       (parametres.page, "Paramètres", ":material/settings:", "parametres")],
}
nav = {}
for section, items in SECTIONS.items():
    nav[section] = []
    for fn, titre, icone, url in items:
        p = st.Page(fn, title=titre, icon=icone, url_path=url, default=(url == "accueil"))
        PAGES[url] = p
        nav[section].append(p)

# liens entre écrans
devis.PAGE_AFF = PAGES["affectation"]
offres.PAGE_DEVIS = PAGES["devis"]
dashboard.PAGES.update(affectation=PAGES["affectation"], devis=PAGES["devis"])

pg = st.navigation(nav)

# ------------------------------------------------------------------ barre latérale : exercice affiché
ex = L.exercices_df()
if len(ex):
    annees = ex.annee.astype(int).tolist()
    statuts = ex.set_index("annee").statut
    sel = st.sidebar.selectbox("Exercice", annees, index=annees.index(L.annee()) if L.annee() in annees else len(annees) - 1,
                               format_func=lambda x: f"{x} · {'clôturé 🔒' if statuts[x] == 'Clôturé' else 'ouvert'}")
    if sel != L.annee():
        L.set_param("annee", int(sel))
        st.rerun()
    st.sidebar.markdown(
        f"<div class='ia-side'><b>Équipe A</b> · centre de coûts<br>Réel jusqu'à {L.MOIS_LONG[L.mois_ref() - 1]} {L.annee()}"
        + ("<br><span class='tag'>Démonstration</span>" if L.mode_donnees() == "demo" else "") + "</div>", unsafe_allow_html=True)
    if L.est_cloture():
        st.sidebar.info("Exercice clôturé : montants figés, consultation seule pour cette année.")

st.session_state["_page_prec"] = st.session_state.get("_page_cour")
st.session_state["_page_cour"] = pg.url_path
if pg.url_path != "affectation":
    st.session_state["_aff_vu"] = False
pg.run()
