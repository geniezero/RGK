"""Petits outils partagés par les écrans : formats, filtres, import CSV, rapport Excel."""
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.exports import rapport_excel

EUR = "%,.2f €"
EUR0 = "%,.0f €"


def eur(v, dec=0):
    return f"{v:,.{dec}f} €".replace(",", " ").replace(".", ",")


def mois_txt():
    return f"{L.MOIS_LONG[L.mois_ref() - 1]} {L.annee()}"


def to_excel(dfs):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        for name, df in dfs.items():
            df.to_excel(w, sheet_name=name[:31], index=False)
    return buf.getvalue()


def filtres(prefix, avec_client=False):
    """Filtres pays / entité (/ client) ; renvoie l'ensemble des ID clients retenus."""
    cli = L.q("SELECT * FROM clients")
    c = st.columns(3 if avec_client else 2)
    pays = c[0].multiselect("Pays", L.liste("pays"), placeholder="Tous", key=f"{prefix}_p")
    ent = c[1].multiselect("Entité", L.liste("entite"), placeholder="Toutes", key=f"{prefix}_e")
    noms = c[2].multiselect("Client", sorted(cli.nom), placeholder="Tous", key=f"{prefix}_c") if avec_client else []
    masque = pd.Series(True, index=cli.index)
    if pays:
        masque &= cli.pays.isin(pays)
    if ent:
        masque &= cli.entite.isin(ent)
    if noms:
        masque &= cli.nom.isin(noms)
    return set(cli[masque].id)


def entetes_mois():
    return {i: L.MOIS[i - 1] + ("" if i <= L.mois_ref() else " (prév.)") for i in range(1, 13)}


def bouton_rapport(cle, ids=None, releves=False):
    """Bouton en deux temps : générer le classeur, puis le télécharger."""
    c1, c2 = st.columns([1, 2])
    if c1.button("📊 Générer le rapport Excel", type="primary", key=f"gen_{cle}"):
        with st.spinner("Génération du classeur…"):
            st.session_state[f"rap_{cle}"] = rapport_excel.generer_rapport(ids, releves)
    if st.session_state.get(f"rap_{cle}"):
        c2.download_button("⬇️ Télécharger le rapport", st.session_state[f"rap_{cle}"],
                           f"IA_Platform_rapport_{L.annee()}_{date.today():%Y%m%d}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{cle}")


def bloc_import(quoi):
    """Import CSV des assets ou des clients, avec modèle téléchargeable."""
    st.caption("Un ID existant est mis à jour, un nouvel ID est ajouté. Séparateur « ; », nombres avec virgule, dates jj/mm/aaaa.")
    if quoi == "assets":
        st.caption("Colonnes facultatives : vCPU ; RAM Go ; Stockage Go ; GPU ; Région ; Refacturation (vide, « entière », « part vcpu » ou « part gpu »). "
                   "Si les capacités sont vides, elles sont lues dans le nom du profil (ex. bx3d-128x640, gx3-24x120x1l40s).")
    modele = L.DATA_DIR / ("Import_Assets.csv" if quoi == "assets" else "Import_Clients.csv")
    if modele.exists():
        st.download_button("Télécharger le modèle / les données d'exemple", modele.read_bytes(), modele.name, "text/csv")
    f = st.file_uploader("Fichier CSV", type=["csv"], key=f"up_{quoi}")
    if f is not None:
        df = L.lire_csv(f)
        st.dataframe(df.head(15), hide_index=True, use_container_width=True)
        st.caption(f"{len(df)} lignes lues.")
        if st.button(f"Importer {len(df)} lignes", type="primary", key=f"imp_{quoi}"):
            rap = L.importer_assets(df) if quoi == "assets" else L.importer_clients(df)
            st.success(" · ".join(f"{k} : {v}" for k, v in rap.items() if k != "ignorés"))
            for x in rap["ignorés"]:
                st.warning(x)
