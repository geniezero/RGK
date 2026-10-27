"""Écran Assets : catalogue, nouvel asset (dont instances cloud), prix datés, import CSV."""
from datetime import date

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.commun import EUR, EUR0, bloc_import, eur
from ia_platform.ui.theme import entete


def libelle_asset(aid, assets):
    r = assets[assets.id == aid]
    return f"{aid} — {r.nom.iloc[0]}" if len(r) else aid



# ======================================================================== ASSETS
def page():
    entete("Assets", "Le catalogue des ressources du parc. Saisissez le prix et l'unité de facturation : le coût mensuel est calculé. "
                     "Modifiez directement le tableau puis enregistrez.", "🖥️", "Référentiel")
    if "as_msg" in st.session_state:  # toast : ne décale pas la page (sinon les onglets reviennent sur « Catalogue »)
        st.toast(st.session_state.pop("as_msg"), icon="✅")
    t1, t6, t2, t3, t4 = st.tabs(["Catalogue", "Nouvel asset", "Changer un prix", "Historique des prix", "Importer un CSV"])
    assets = L.assets_df()
    with t1:
        types = sorted(set(assets.type.dropna()), key=lambda t: (L.liste("type").index(t) if t in L.liste("type") else 99, t))
        opts = [f"Tous ({len(assets)})"] + [f"{t} ({int((assets.type == t).sum())})" for t in types]
        filtre = st.segmented_control("Type", opts, default=opts[0], key="as_filtre", label_visibility="collapsed") or opts[0]
        df = assets.copy() if filtre.startswith("Tous") else assets[assets.type == filtre.rsplit(" (", 1)[0]].copy()
        df["date_effet"] = pd.to_datetime(df.date_effet).dt.date
        df["refac"] = df.refacturation.map(lambda x: L.REFACTURATIONS.get(x if isinstance(x, str) else None, "—"))
        for col in ("fournisseur", "region"):
            df[col] = df[col].where(df[col].notna(), "")
        df["lie"] = df.parent_id.where(df.parent_id.notna(), "")
        ed = st.data_editor(
            df[["id", "type", "nom", "fournisseur", "region", "prix", "unite", "cout_mois", "qte_parc", "cout_parc", "vcpu", "ram_go", "gpu",
                "refac", "lie", "date_effet", "statut"]],
            key=f"ed_assets_{filtre}", num_rows="dynamic", use_container_width=True, hide_index=True, height=520,
            column_config={
                "id": st.column_config.TextColumn("ID", required=True, width="small"),
                "type": st.column_config.SelectboxColumn("Type", options=L.liste("type"), required=True),
                "nom": st.column_config.TextColumn("Nom", width="medium"),
                "fournisseur": "Fournisseur",
                "region": st.column_config.TextColumn("Région"),
                "prix": st.column_config.NumberColumn("Prix unitaire", format="%,.3f €", min_value=0),
                "unite": st.column_config.SelectboxColumn("Unité", options=L.UNITES, required=True),
                "cout_mois": st.column_config.NumberColumn("Coût / mois (1 unité)", format=EUR, disabled=True,
                                                           help="Prix d'une unité ramené au mois : c'est lui qui sert à refacturer les clients."),
                "qte_parc": st.column_config.NumberColumn("Qté parc", format="%,d", min_value=0,
                                                          help="Nombre d'unités possédées ou réservées (instances pour une instance cloud)."),
                "cout_parc": st.column_config.NumberColumn("Coût total du parc / mois", format=EUR0, disabled=True,
                                                           help="Coût d'une unité × quantité du parc : ce que l'équipe A paie, vendu ou non. "
                                                                "Comparé au refacturé, il donne la couverture, la capacité inutilisée et l'écart à ventiler en fin d'année. "
                                                                "Une « part » d'instance n'a pas de coût propre : il est porté par l'instance."),
                "vcpu": st.column_config.NumberColumn("vCPU", format="%g", min_value=0),
                "ram_go": st.column_config.NumberColumn("RAM (Go)", format="%g", min_value=0),
                "gpu": st.column_config.NumberColumn("GPU", format="%g", min_value=0),
                "refac": st.column_config.SelectboxColumn("Refacturation", options=list(L.REFACTURATIONS.values()),
                                                          help="Instance entière, ou à la part (vCPU ou GPU) pour une machine partagée."),
                "lie": st.column_config.TextColumn("Part de", disabled=True, help="Asset « part » créé automatiquement à partir de cette instance."),
                "date_effet": st.column_config.DateColumn("Date d'effet", format="DD/MM/YYYY"),
                "statut": st.column_config.SelectboxColumn("Statut", options=L.STATUTS_ASSET),
            })
        c1, c2, c3 = st.columns([1, 1, 2])
        c1.metric("Coût total du parc / mois", eur(assets.loc[assets.statut == "Actif", "cout_parc"].sum()),
                  help="Somme des coûts de parc des assets actifs : le coût mensuel que l'équipe A doit couvrir.")
        c2.metric("Assets actifs", int((assets.statut == "Actif").sum()))
        with c3:
            st.write("")
            if st.button("💾 Enregistrer les modifications", type="primary", key="save_assets"):
                ed = ed.dropna(subset=["id"])
                ed = ed[ed.id.astype(str).str.strip() != ""]
                autres = set(assets.id) - set(df.id)
                if ed.id.duplicated().any() or (set(ed.id) & autres):
                    st.error("Des ID sont en double : " + ", ".join(sorted(set(ed.id[ed.id.duplicated()]) | (set(ed.id) & autres))))
                else:
                    utilises = set(L.q("SELECT asset_id FROM composition").asset_id) | set(
                        L.q("SELECT code FROM affectations WHERE element='Option'").code)
                    supprimes = set(df.id) - set(ed.id)
                    bloques = (supprimes & utilises) | {i for i in supprimes if i in set(assets.parent_id.dropna())}
                    if bloques:
                        st.error("Impossible de supprimer des assets utilisés dans une offre ou une option (ou qui portent une part) : "
                                 + ", ".join(sorted(bloques)) + ". Passez-les plutôt au statut « Retiré ».")
                    else:
                        inv = {v: k for k, v in L.REFACTURATIONS.items()}
                        for i in supprimes:
                            L.run("DELETE FROM assets WHERE id=?", (i,))
                        for r in ed.itertuples():
                            L.enregistrer_asset(dict(id=r.id, type=r.type, nom=r.nom, fournisseur=r.fournisseur, region=r.region,
                                                     prix=float(r.prix or 0), unite=r.unite, qte_parc=float(r.qte_parc or 0),
                                                     date_effet=L.iso(r.date_effet), statut=r.statut or "Actif",
                                                     vcpu=r.vcpu, ram_go=r.ram_go, gpu=r.gpu, refacturation=inv.get(r.refac)), synchro=False)
                        L.synchroniser_parts()
                        st.success("Catalogue enregistré.")
                        st.rerun()
        st.caption("Les « parts » (colonne « Part de » remplie) sont tenues à jour automatiquement à partir de leur instance : prix = prix de l'instance ÷ "
                   "nombre de vCPU (ou de GPU), parc = parts × instances.")
        with st.expander("Unités de facturation"):
            st.dataframe(pd.DataFrame({"Unité": L.UNITES, "Facteur mensuel": [round(v, 4) for v in L.FACTEURS.values()],
                                       "Règle": ["prix × 730 h", "prix × 30,42 j", "prix × 4,33", "prix", "prix ÷ 12"]}),
                         hide_index=True)
    with t6:
        form_asset(assets)
    with t2:
        st.caption("L'ancien prix est conservé dans l'historique : les mois passés restent calculés à l'ancien prix.")
        if assets.empty:
            st.info("Aucun asset pour l'instant : créez-en dans « Nouvel asset » ou « Importer un CSV ».")
    with t2:
        if not assets.empty:
          with st.form("prix"):
            aid = st.selectbox("Asset", assets.id, format_func=lambda x: libelle_asset(x, assets))
            r = assets[assets.id == aid].iloc[0]
            depuis = f" depuis le {L.d(r.date_effet):%d/%m/%Y}" if L.d(r.date_effet) else ""
            st.info(f"Prix actuel : {r.prix:,.3f} € / {r.unite}{depuis} → {eur(r.cout_mois, 2)} / mois")
            c1, c2, c3 = st.columns(3)
            prix = c1.number_input("Nouveau prix", min_value=0.0, value=float(r.prix), format="%.3f")
            unite = c2.selectbox("Unité", L.UNITES, index=L.UNITES.index(r.unite))
            eff = c3.date_input("Date d'effet", value=date(L.annee() + 1, 1, 1), format="DD/MM/YYYY")
            motif = st.text_input("Motif", "Revalorisation annuelle")
            if st.form_submit_button("Changer le prix", type="primary"):
                try:
                    L.changer_prix(aid, prix, unite, eff, motif)
                    st.success(f"Prix de {aid} mis à jour à partir du {eff:%d/%m/%Y}.")
                except ValueError as e:
                    st.error(str(e))
    with t3:
        h = L.q("SELECT h.asset_id, a.nom, h.prix, h.unite, h.du, h.au, h.motif FROM prix_hist h LEFT JOIN assets a ON a.id=h.asset_id ORDER BY h.asset_id, h.du")
        h["cout_mois"] = h.prix * h.unite.map(L.FACTEURS)
        st.dataframe(h, hide_index=True, use_container_width=True, column_config={
            "asset_id": "ID", "nom": "Asset", "prix": st.column_config.NumberColumn("Prix", format="%,.3f €"),
            "unite": "Unité", "cout_mois": st.column_config.NumberColumn("Coût / mois", format=EUR),
            "du": st.column_config.DateColumn("Du", format="DD/MM/YYYY"), "au": st.column_config.DateColumn("Au", format="DD/MM/YYYY"),
            "motif": "Motif"})
    with t4:
        bloc_import("assets")


def form_asset(assets):
    """Un seul formulaire pour tous les assets ; le type « Instance cloud » affiche en plus la lecture du profil et le mode de refacturation."""
    st.caption("Une ressource du parc : GPU, serveur, licence, stockage, service, instance cloud… Le coût mensuel est calculé à partir du prix et de l'unité.")
    types = L.liste("type")
    k = f"na{st.session_state.get('na_n', 0)}_"  # nouvelles clés après chaque création : le formulaire repart vide
    c = st.columns([.8, 1.1, 2, 1.3])
    aid = c[0].text_input("ID", L.prochain_id("assets", "A-", 3), key=k + "id")
    typ = c[1].selectbox("Type", types, key=k + "type")
    cloud = typ == "Instance cloud"
    nom = c[2].text_input("Nom *" if not cloud else "Nom (profil du fournisseur) *", key=k + "nom",
                          placeholder="ex. IBM bx3d-128x640" if cloud else "ex. GPU H100 80 Go, Licence MLOps (utilisateur)…")
    fourn = c[3].text_input("Fournisseur", key=k + "f")
    fl = L.lire_flavor(nom) if cloud else {}
    if cloud:
        if fl:
            st.caption(f"Lu dans « {fl['profil']} » : famille {fl['famille']}, {fl['vcpu']:g} vCPU, {fl['ram_go']:g} Go de RAM"
                       + (f", {fl['gpu']:g} GPU {fl.get('gpu_modele', '')}" if fl.get("gpu") else "")
                       + (", stockage local (d)" if fl.get("stockage_local") else "") + ". Les valeurs restent modifiables.")
        elif nom:
            st.caption("Nom de profil non reconnu : saisissez les capacités.")
    c = st.columns(4)
    prix = c[0].number_input("Prix unitaire (€) *", min_value=0.0, step=0.01, format="%.3f", key=k + "p")
    unite = c[1].selectbox("Unité de facturation", L.UNITES, index=L.UNITES.index("Heure" if cloud else "Mois"), key=f"{k}u_{cloud}")
    parc = c[2].number_input("Instances (parc)" if cloud else "Quantité du parc", min_value=0.0, value=1.0 if cloud else 0.0, step=1.0, format="%g",
                             key=f"{k}q_{cloud}", help="Unités possédées ou réservées : sert au coût du parc et à l'occupation.")
    eff = c[3].date_input("Date d'effet", value=date(L.annee(), 1, 1), format="DD/MM/YYYY", key=k + "d")
    cle = fl.get("profil", "x")
    with st.expander("Capacités", expanded=cloud):
        c = st.columns(6)
        vcpu = c[0].number_input("vCPU", min_value=0.0, step=1.0, format="%g", value=float(fl.get("vcpu", 0)), key=f"{k}v_{cle}")
        ram = c[1].number_input("RAM (Go)", min_value=0.0, step=1.0, format="%g", value=float(fl.get("ram_go", 0)), key=f"{k}ram_{cle}")
        sto = c[2].number_input("Stockage local (Go)", min_value=0.0, step=100.0, format="%g", key=f"{k}s_{cle}")
        gpu = c[3].number_input("GPU", min_value=0.0, step=1.0, format="%g", value=float(fl.get("gpu", 0)), key=f"{k}g_{cle}")
        res = c[4].number_input("Réseau (Gb/s)", min_value=0.0, step=1.0, format="%g", key=f"{k}n_{cle}")
        region = c[5].text_input("Région / site", key=k + "r")
    cm = prix * L.FACTEURS[unite]
    prix_txt = f"{prix:,.3f}".replace(",", " ").replace(".", ",")
    st.markdown(f"{prix_txt} € × {L.FACTEURS[unite]:g} = **{eur(cm, 2)} / mois par {'instance' if cloud else 'unité'}** · "
                f"coût total du parc : {eur(cm * parc)} / mois")
    mode, n = None, 0
    if cloud:
        g, d_ = st.columns([1, 1.2], gap="large")
        with g:
            modes = ["entiere", "part_vcpu"] + (["part_gpu"] if gpu else [])
            mode = st.radio("Comment la refacturer ?", modes, key=k + "mode", format_func={
                "entiere": "À l'instance entière — un client prend une machine complète",
                "part_vcpu": "À la part, par vCPU — machine partagée entre clients",
                "part_gpu": "À la part, par GPU — machine partagée entre clients"}.get)
        n = vcpu if mode == "part_vcpu" else gpu if mode == "part_gpu" else 0
        with d_.container(border=True):
            st.markdown("**Sera créé**")
            lignes = [dict(Asset=f"{nom or 'instance'} ({aid})", Rôle="coût du parc" if mode != "entiere" else "vendu aux clients",
                           **{"Coût / mois": eur(cm)}, Parc=f"{parc:g}")]
            if n:
                lignes.append(dict(Asset=f"{'vCPU' if mode == 'part_vcpu' else 'GPU'} {fl.get('profil', nom)} (part)", Rôle="vendu aux clients",
                                   **{"Coût / mois": eur(cm / n, 2)}, Parc=f"{parc * n:g}"))
            st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
            st.caption((f"Prix de la part = prix de l'instance ÷ {n:g} ; elle suit les changements de prix de l'instance. "
                        + (f"Chaque vCPU vendu inclut {ram / vcpu:g} Go de RAM. " if mode == "part_vcpu" and vcpu else "")) if n else
                       "Le nombre d'instances vendues ne pourra pas dépasser le parc (contrôle de capacité).")
    if st.button("💾 Créer l'asset", type="primary", key=k + "ok"):
        if not nom.strip() or prix <= 0:
            st.error("Le nom et le prix sont obligatoires.")
        elif aid.strip() in set(assets.id):
            st.error(f"L'ID {aid} existe déjà.")
        elif nom.strip().lower() in set(assets.nom.str.lower()):
            st.error("Un asset porte déjà ce nom.")
        elif cloud and mode != "entiere" and n <= 0:
            st.error("Indiquez le nombre de vCPU (ou de GPU) pour vendre à la part.")
        else:
            L.enregistrer_asset(dict(id=aid.strip(), type=typ, nom=nom.strip(), fournisseur=fourn, prix=prix, unite=unite, qte_parc=parc,
                                     date_effet=L.iso(eff), statut="Actif", vcpu=vcpu or None, ram_go=ram or None, stockage_go=sto or None,
                                     gpu=gpu or None, gpu_modele=fl.get("gpu_modele"), reseau_gbs=res or None, region=region or None,
                                     refacturation=mode))
            st.session_state["na_n"] = st.session_state.get("na_n", 0) + 1
            st.session_state["as_msg"] = f"Asset {aid} créé : {nom}" + (" avec sa part." if n else ".")
            st.rerun()
