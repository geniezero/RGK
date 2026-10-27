"""Écran Paramètres : dernier mois réel, listes, données."""
from datetime import date

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.theme import entete


def page():
    entete("Paramètres", "L'exercice affiché se choisit dans la barre latérale ; la création et la clôture des exercices se font dans « Exercices ».",
           "⚙️", "Administration")
    c1, c2 = st.columns(2)
    c1.metric("Exercice affiché", f"{L.annee()} · {'clôturé' if L.est_cloture() else 'ouvert'}")
    m = c2.selectbox("Dernier mois réel de l'exercice", range(1, 13), index=L.mois_ref() - 1, format_func=lambda i: L.MOIS_LONG[i - 1],
                     disabled=L.est_cloture(), help="Les mois suivants sont affichés comme prévision.")
    if not L.est_cloture() and st.button("Enregistrer", type="primary"):
        L.set_mois_ref(int(m))
        st.success("Paramètres enregistrés.")
        st.rerun()
    st.subheader("Listes")
    cols = st.columns(3)
    for col, (cat, titre) in zip(cols, [("type", "Types d'asset"), ("entite", "Entités"), ("pays", "Pays")]):
        with col:
            ed = st.data_editor(pd.DataFrame({titre: L.liste(cat)}), num_rows="dynamic", hide_index=True, key=f"l_{cat}", use_container_width=True)
            if st.button(f"Enregistrer {titre.lower()}", key=f"s_{cat}"):
                L.remplacer_liste(cat, [v.strip() for v in ed[titre].dropna() if str(v).strip()])
                st.success("Liste enregistrée.")
    st.subheader("Unités de facturation")
    st.dataframe(pd.DataFrame({"Unité": L.UNITES, "Facteur mensuel": [round(v, 4) for v in L.FACTEURS.values()]}), hide_index=True)
    st.subheader("Données")
    mode = {"demo": "données de démonstration (fictives)", "vide": "vos données (démarrage sur base vide)",
            "existant": "vos données"}.get(L.mode_donnees(), "—")
    st.markdown(f"Base actuelle : **{mode}** · fichier `{L.DB_PATH.name}`")
    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**Tout effacer et repartir d'une base vide**")
        st.caption("Supprime assets, offres, clients, affectations, devis, budgets, exercices et mesures. Une copie de la base est d'abord "
                   "enregistrée dans le dossier « data/archives ». Les listes (types, entités, pays) sont conservées.")
        a1, a2 = st.columns(2)
        an = a1.number_input("Exercice de départ", min_value=2000, max_value=2100, value=date.today().year, step=1, key="raz_an")
        mo = a2.selectbox("Dernier mois réel", range(1, 13), index=date.today().month - 1, format_func=lambda i: L.MOIS_LONG[i - 1], key="raz_m")
        ok = st.checkbox("Je confirme vouloir tout effacer", key="raz_ok")
        if st.button("🗑️ Tout effacer", disabled=not ok, key="raz_go"):
            cible = L.tout_effacer(int(an), int(mo))
            st.success(f"Base vidée. Sauvegarde : {cible.name}")
            st.rerun()
    with c2.container(border=True):
        st.markdown("**Charger les données de démonstration**")
        st.caption("Possible seulement si la base est vide (aucun asset, offre ni client).")
        if st.button("🧪 Charger la démonstration", disabled=not L.base_vide(), key="demo_go"):
            L.charger_demo()
            st.success("Données de démonstration chargées.")
            st.rerun()
