"""Premier lancement : base vide ou données de démonstration."""
import streamlit as st
from datetime import date

from ia_platform.core import logic as L


def page():
    """Au premier lancement : base vide (vos données) ou données de démonstration."""
    st.markdown("<div class='ia-hero'><h1>Bienvenue dans IA Platform</h1>"
                "<p>Base de données neuve. Choisissez comment démarrer ; vous pourrez changer d'avis plus tard dans Paramètres › Données.</p></div>",
                unsafe_allow_html=True)
    g, d = st.columns(2, gap="large")
    with g.container(border=True):
        st.subheader("🗂️ Commencer avec mes données")
        st.markdown("Une base **vide** : vous saisissez (ou importez en CSV) vos assets, vos offres et vos clients, puis vous affectez les offres.")
        c1, c2 = st.columns(2)
        an = c1.number_input("Exercice", min_value=2000, max_value=2100, value=date.today().year, step=1)
        mois = c2.selectbox("Dernier mois réel", range(1, 13), index=date.today().month - 1, format_func=lambda i: L.MOIS_LONG[i - 1],
                            help="Les mois suivants seront affichés comme prévision. Modifiable ensuite dans Paramètres.")
        if st.button("Commencer avec une base vide", type="primary", use_container_width=True):
            L.demarrer_vide(int(an), int(mois))
            st.rerun()
        st.markdown("**Ensuite :** 1. Assets (saisie ou import CSV) → 2. Offres → 3. Clients → 4. Affectations → Dashboard.")
    with d.container(border=True):
        st.subheader("🧪 Découvrir avec la démonstration")
        st.markdown("Des données **fictives** pour tester : 38 assets dont 3 instances IBM, 5 offres, 40 clients, affectations, devis, budgets "
                    "et mesures de supervision, sur l'exercice 2026 (réel jusqu'à octobre).")
        st.caption("Les prix et les mesures de la démonstration sont des exemples. Paramètres › Données permet de tout effacer pour repartir de zéro.")
        if st.button("Charger les données de démonstration", use_container_width=True):
            with st.spinner("Chargement…"):
                L.charger_demo()
            st.rerun()
