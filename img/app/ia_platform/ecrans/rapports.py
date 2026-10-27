"""Écran Rapports Excel."""
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.commun import mois_txt, bouton_rapport, filtres
from ia_platform.ui.theme import entete


def page():
    entete("Rapports Excel", "Un classeur Excel mis en forme : référentiel clients et consommation par mois, avec totaux et graphique.", "📄", "Suivi")
    st.markdown(f"""
**Contenu du classeur**
- **Synthèse** : indicateurs, consommation mois par mois (réel / prévision) avec graphique, totaux par pays et par entité.
- **Clients** : référentiel (ID, nom, entité, pays, responsable, e-mail, statut), offre actuelle, coût mensuel, consommation.
- **Consommation** : un client par ligne, une colonne par mois de {L.annee()}, totaux (filtrables).
- **Par type d'asset** : GPU, CPU, licences… mois par mois.
- **Détail** : une ligne par client, offre ou option et mois — prêt pour un tableau croisé dynamique.
- **Relevés** (option) : une feuille par client consommateur.
""")
    ids = filtres("ra", True)
    tous = len(ids) == len(L.q("SELECT id FROM clients"))
    releves = st.checkbox("Ajouter un relevé par client (une feuille chacun)", value=False)
    st.caption(f"{'Tous les clients' if tous else str(len(ids)) + ' client(s) sélectionné(s)'} · exercice {L.annee()} · réel jusqu'à {mois_txt()}")
    bouton_rapport("ra", None if tous else ids, releves)
