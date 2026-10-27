"""Écran Consommation : client × mois, par pays, par type d'asset."""
import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.commun import eur, mois_txt, bouton_rapport, entetes_mois, filtres
from ia_platform.ui.theme import entete


def page():
    entete("Consommation", f"Coût refacturé par client et par mois (offres + options). Réel jusqu'à {mois_txt()}, prévision ensuite.", "📅", "Suivi")
    ids = filtres("co", True)
    lignes = L.lignes_mensuelles()
    cc = L.conso_clients(lignes)
    cc = cc[cc.client_id.isin(ids) & (cc.total > 0)].copy()
    ordre = {p: i for i, p in enumerate(L.liste("pays"))}
    cc = cc.sort_values(["pays", "client"], key=lambda s: s.map(ordre) if s.name == "pays" else s)
    noms = entetes_mois()
    t = cc[["pays", "entite", "client"] + list(range(1, 13)) + ["total"]].rename(columns=noms)
    tot = pd.DataFrame([["TOTAL", "", ""] + [cc[i].sum() for i in range(1, 13)] + [cc.total.sum()]], columns=t.columns)
    t = pd.concat([tot, t], ignore_index=True)
    cfg = {n: st.column_config.NumberColumn(n, format="%,.0f") for n in list(noms.values()) + ["total"]}
    cfg.update({"pays": "Pays", "entite": "Entité", "client": "Client", "total": st.column_config.NumberColumn("Total", format="%,.0f")})
    c1, c2, c3 = st.columns(3)
    c1.metric("Consommation réelle", eur(cc.reel.sum()))
    c2.metric("Prévision fin d'année", eur(cc.total.sum()))
    c3.metric("Clients", len(cc))
    st.dataframe(t, hide_index=True, use_container_width=True, column_config=cfg, height=min(38 * (len(t) + 1), 600))
    st.subheader("Par pays")
    pp = cc.groupby("pays")[list(range(1, 13)) + ["total"]].sum().reset_index().rename(columns=noms)
    st.dataframe(pp, hide_index=True, use_container_width=True, column_config=cfg)
    st.subheader("Par type d'asset")
    ty = L.conso_par_type(lignes, ids).reset_index().rename(columns={"index": "type"})
    ty["total"] = ty[list(range(1, 13))].sum(axis=1)
    ty = ty.rename(columns=noms)
    st.dataframe(ty, hide_index=True, use_container_width=True, column_config={**cfg, "type": "Type"})
    st.divider()
    bouton_rapport("co", ids if len(ids) < len(L.q("SELECT id FROM clients")) else None)
