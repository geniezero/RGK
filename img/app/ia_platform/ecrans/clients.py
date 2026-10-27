"""Écran Clients : liste modifiable, nouveau client, import CSV."""
from datetime import date

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.commun import EUR, EUR0, bloc_import
from ia_platform.ui.theme import entete


# ======================================================================== CLIENTS
def page():
    entete("Clients", "Nom, entité et pays permettent de suivre la consommation par pays et par entité.", "👥", "Référentiel")
    t1, t2, t3 = st.tabs(["Liste", "Nouveau client", "Importer un CSV"])
    lignes = L.lignes_mensuelles()
    cc = L.conso_clients(lignes)
    cli = L.q("SELECT * FROM clients ORDER BY id")
    act = lignes[lignes.statut == "Active"]
    ao = act[act.element == "Offre"]
    offre = (ao.groupby("client_id").apply(lambda g: g.code.iloc[-1] + " " + str(g.libelle.iloc[-1]), include_groups=False)
             if len(ao) else pd.Series(dtype=str))
    nopt = act[act.element == "Option"].groupby("client_id").size() if len(act) else pd.Series(dtype=int)
    cli["offre"] = cli.id.map(offre).fillna("—") + cli.id.map(lambda x: " + options" if x in nopt.index else "")
    cli["cout"] = cli.id.map(cc.set_index("client_id").mois_ref).fillna(0)
    cli["reel"] = cli.id.map(cc.set_index("client_id").reel).fillna(0)
    bud = L.budgets_df().set_index("client_id").budget
    cli["budget"] = cli.id.map(bud).fillna(0)
    cli["pct"] = [(t / b_ * 100) if b_ else None for t, b_ in zip(cli.id.map(cc.set_index("client_id").total).fillna(0), cli.budget)]
    cli["date_entree"] = pd.to_datetime(cli.date_entree).dt.date
    with t1:
        left, right = st.columns([3, 1])
        with left:
            ed = st.data_editor(cli, key="ed_cli", num_rows="dynamic", hide_index=True, use_container_width=True, height=560,
                                column_config={
                                    "id": st.column_config.TextColumn("ID", required=True, width="small"),
                                    "nom": st.column_config.TextColumn("Nom du client", required=True),
                                    "entite": st.column_config.SelectboxColumn("Entité", options=L.liste("entite"), required=True),
                                    "pays": st.column_config.SelectboxColumn("Pays", options=L.liste("pays"), required=True),
                                    "responsable": "Responsable", "email": "E-mail",
                                    "statut": st.column_config.SelectboxColumn("Statut", options=L.STATUTS_CLIENT),
                                    "date_entree": st.column_config.DateColumn("Date d'entrée", format="DD/MM/YYYY"),
                                    "offre": st.column_config.TextColumn("Offre actuelle", disabled=True),
                                    "cout": st.column_config.NumberColumn("Coût / mois", format=EUR, disabled=True),
                                    "reel": st.column_config.NumberColumn("Conso réelle", format=EUR0, disabled=True),
                                    "budget": st.column_config.NumberColumn(f"Budget {L.annee()}", format=EUR0, disabled=True,
                                                                            help="Modifiable dans Exercices > Budgets"),
                                    "pct": st.column_config.ProgressColumn("Prévision / budget", format="%.0f %%", min_value=0, max_value=150)})
            if st.button("💾 Enregistrer les modifications", type="primary", key="save_cli"):
                ed = ed.dropna(subset=["id"])
                if ed.id.duplicated().any():
                    st.error("Des ID sont en double.")
                else:
                    lies = (set(L.q("SELECT client_id FROM affectations").client_id) | set(L.q("SELECT client_id FROM devis").client_id)
                            | set(L.q("SELECT client_id FROM conso_figee").client_id))
                    supprimes = (set(cli.id) - set(ed.id)) & lies
                    if supprimes:
                        st.error("Ces clients ont des affectations, des devis ou une consommation archivée et ne peuvent pas être supprimés : "
                                 + ", ".join(sorted(supprimes)) + ". Passez-les au statut « Inactif ».")
                    else:
                        with L.conn() as c:
                            c.execute("DELETE FROM clients")
                            c.executemany("INSERT INTO clients VALUES (?,?,?,?,?,?,?,?)", [
                                (r.id, r.nom, r.entite, r.pays, r.responsable, r.email, r.statut or "Actif", L.iso(r.date_entree))
                                for r in ed.itertuples()])
                        st.success("Clients enregistrés.")
                        st.rerun()
        with right:
            act_cli = cli[cli.statut == "Actif"]
            for col, titre in [("pays", "Par pays"), ("entite", "Par entité")]:
                g = act_cli.groupby(col).agg(Clients=("id", "count"), Conso=("reel", "sum")).reset_index().sort_values("Conso", ascending=False)
                st.markdown(f"**{titre}** (clients actifs)")
                st.dataframe(g.rename(columns={col: titre.split()[-1].capitalize()}), hide_index=True, use_container_width=True,
                             column_config={"Conso": st.column_config.NumberColumn("Conso réelle", format=EUR0)})
    with t2:
        with st.form("nouveau_client", clear_on_submit=True):
            st.caption(f"ID attribué : {L.prochain_id('clients', 'CL-', 3)}")
            c1, c2 = st.columns(2)
            nom = c1.text_input("Nom du client *")
            resp = c2.text_input("Responsable")
            ent = c1.selectbox("Entité *", L.liste("entite"))
            pays = c2.selectbox("Pays *", L.liste("pays"))
            mail = c1.text_input("E-mail")
            d_ent = c2.date_input("Date d'entrée", value=date.today(), format="DD/MM/YYYY")
            statut = c1.selectbox("Statut", L.STATUTS_CLIENT)
            if st.form_submit_button("Enregistrer le client", type="primary"):
                if not nom.strip():
                    st.error("Le nom est obligatoire.")
                elif nom.strip().lower() in set(cli.nom.str.lower()):
                    st.error("Un client porte déjà ce nom.")
                else:
                    nid = L.prochain_id("clients", "CL-", 3)
                    L.run("INSERT INTO clients VALUES (?,?,?,?,?,?,?,?)", (nid, nom.strip(), ent, pays, resp, mail, statut, L.iso(d_ent)))
                    st.success(f"Client {nid} enregistré : {nom}")
    with t3:
        bloc_import("clients")
