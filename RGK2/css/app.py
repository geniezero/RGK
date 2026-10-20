"""IA Platform — application Streamlit (assets, offres, clients, affectations, consommation, dashboard).

Lancement :  streamlit run app.py
"""
from datetime import date
from io import BytesIO

import altair as alt
import pandas as pd
import streamlit as st

import logic as L
import rapport
import devis_pdf
import affectations_ui
import devis_ui
import offres_ui
import dashboard_ui

st.set_page_config(page_title="IA Platform", page_icon="🧮", layout="wide")
L.init_db()


def premier_lancement():
    """Au premier lancement : base vide (vos données) ou données de démonstration."""
    st.title("Bienvenue dans IA Platform")
    st.caption("Base de données neuve. Choisissez comment démarrer ; vous pourrez changer d'avis plus tard dans Paramètres › Données.")
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


if not L.est_initialise():
    premier_lancement()
    st.stop()

TEAL = "#0F6B5C"
PAYS_COL = ["#0F6B5C", "#4C9C8A", "#C2702E", "#E3A66F", "#7A8580", "#9CC7BB", "#3A5BA0", "#B0B8B4"]
TYPE_COL = ["#0F6B5C", "#2E8B74", "#9CC7BB", "#C9E0D8", "#C2702E", "#E3A66F", "#7A8580", "#BAC3BF"]
EUR = "%,.2f €"
EUR0 = "%,.0f €"

st.markdown("""
<style>
[data-testid="stMetricValue"] {font-size: 1.6rem;}
[data-testid="stMetric"] {background:#F4F7F5;border:1px solid #DCE6E2;border-top:3px solid #0F6B5C;padding:10px 14px;border-radius:6px;}
h1 {font-size: 1.9rem !important;}
</style>""", unsafe_allow_html=True)


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


def libelle_asset(aid, assets):
    r = assets[assets.id == aid]
    return f"{aid} — {r.nom.iloc[0]}" if len(r) else aid


# ======================================================================== ACCUEIL
def page_accueil():
    st.title("IA Platform — gestion des assets, offres et consommation")
    st.caption(f"Exercice {L.annee()} · mois de référence : {mois_txt()} (modifiable dans Paramètres)")
    if L.mode_donnees() == "demo":
        st.info("Vous utilisez les **données de démonstration** (fictives). Pour saisir vos propres données : Paramètres › Données › « Tout effacer ».")
    n_a, n_o, n_c = len(L.q("SELECT id FROM assets")), len(L.q("SELECT id FROM offres")), len(L.q("SELECT id FROM clients"))
    n_af = len(L.q("SELECT id FROM affectations"))
    if not (n_a and n_o and n_c and n_af):
        with st.container(border=True):
            st.subheader("Premiers pas")
            etapes = [(n_a, "Assets", "saisir vos ressources (prix, unité, quantité du parc) ou les importer en CSV — un modèle est téléchargeable dans l'onglet « Importer un CSV »", "assets"),
                      (n_o, "Offres", "composer vos offres à partir des assets", "offres"),
                      (n_c, "Clients", "créer vos clients (nom, entité, pays) ou les importer en CSV", "clients"),
                      (n_af, "Affectations", "donner une offre ou des options à un client, avec une date de début", "affectation")]
            cible = {"assets": 1, "offres": 3, "clients": 2, "affectation": 4}
            for i, (n, nom, txt, url) in enumerate(etapes, 1):
                g_, d_ = st.columns([5, 1], vertical_alignment="center")
                g_.markdown(f"{'✅' if n else '⬜'} **{i}. {nom}** — {txt}" + (f" · {n} saisi{'s' if n > 1 else ''}" if n else ""))
                d_.page_link(pages[cible[url]], label=f"Ouvrir {nom}", icon="➡️")
            st.caption("Le Dashboard, la consommation et les rapports se remplissent ensuite tout seuls.")
    assets = L.assets_df()
    cc = L.conso_clients()
    parc = assets.loc[assets.statut == "Actif", "cout_parc"].sum()
    refact = cc.mois_ref.sum()
    c = st.columns(5)
    c[0].metric("Coût du parc / mois", eur(parc))
    c[1].metric(f"Refacturé en {L.MOIS_LONG[L.mois_ref() - 1]}", eur(refact))
    c[2].metric("Taux de couverture", f"{refact / parc * 100:.1f} %".replace(".", ",") if parc else "-")
    c[3].metric("Clients consommateurs", int((cc.mois_ref > 0).sum()))
    c[4].metric("Offres actives", int((L.q("SELECT statut FROM offres").statut == "Active").sum()))
    st.subheader("Comment ça marche")
    st.markdown("""
1. **Assets** : chaque ressource avec son prix et son unité de facturation (heure, jour, semaine, mois, an). Le coût mensuel est calculé.
2. **Offres** : une offre regroupe plusieurs assets ; son coût mensuel est calculé automatiquement.
3. **Clients** : nom, entité et pays, pour suivre la consommation par pays et par entité.
4. **Affectations** : cliquer sur un client, lui ajouter une ou plusieurs offres et options datées (début / fin), remplacer une option, changer d'offre ou tout arrêter.
5. **Consommation** et **Dashboard** : se mettent à jour tout seuls.

Les mois après le mois de référence sont des **prévisions** (ce qui est affecté continue jusqu'à la fin de l'année).
""")


# ======================================================================== ASSETS
def page_assets():
    st.title("Assets — catalogue des ressources")
    st.caption("Saisir le prix et l'unité de facturation : le coût mensuel est calculé. Modifiez directement le tableau puis enregistrez.")
    t1, t6, t5, t2, t3, t4 = st.tabs(["Catalogue", "Nouvel asset", "Nouvelle instance cloud", "Changer un prix", "Historique des prix", "Importer un CSV"])
    assets = L.assets_df()
    with t1:
        types = sorted(set(assets.type.dropna()), key=lambda t: (L.liste("type").index(t) if t in L.liste("type") else 99, t))
        opts = [f"Tous ({len(assets)})"] + [f"{t} ({int((assets.type == t).sum())})" for t in types]
        filtre = st.segmented_control("Type", opts, default=opts[0], key="as_filtre", label_visibility="collapsed") or opts[0]
        df = assets.copy() if filtre.startswith("Tous") else assets[assets.type == filtre.rsplit(" (", 1)[0]].copy()
        df["date_effet"] = pd.to_datetime(df.date_effet).dt.date
        df["refac"] = df.refacturation.map(lambda x: L.REFACTURATIONS.get(x if isinstance(x, str) else None, "—"))
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
    with t5:
        form_instance_cloud(assets)
    with t2:
        st.caption("L'ancien prix est conservé dans l'historique : les mois passés restent calculés à l'ancien prix.")
        if assets.empty:
            st.info("Aucun asset pour l'instant : créez-en dans « Catalogue » (ligne vide en bas du tableau), « Nouvelle instance cloud » ou « Importer un CSV ».")
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
    st.caption("Une ressource du parc : GPU, serveur, licence, stockage, service… Le coût mensuel est calculé à partir du prix et de l'unité.")
    with st.form("nouvel_asset", clear_on_submit=True):
        nid = L.prochain_id("assets", "A-", 3)
        c = st.columns([.8, 1, 2, 1.3])
        aid = c[0].text_input("ID", nid)
        typ = c[1].selectbox("Type", L.liste("type"))
        nom = c[2].text_input("Nom *", placeholder="ex. GPU H100 80 Go, Licence MLOps (utilisateur)…")
        fourn = c[3].text_input("Fournisseur")
        c = st.columns(4)
        prix = c[0].number_input("Prix unitaire (€) *", min_value=0.0, step=0.01, format="%.3f")
        unite = c[1].selectbox("Unité de facturation", L.UNITES, index=L.UNITES.index("Mois"))
        parc = c[2].number_input("Quantité du parc", min_value=0.0, step=1.0, format="%g", help="Unités possédées ou réservées : sert au coût du parc et à l'occupation.")
        eff = c[3].date_input("Date d'effet", value=date(L.annee(), 1, 1), format="DD/MM/YYYY")
        with st.expander("Capacités (facultatif)"):
            c = st.columns(4)
            vcpu = c[0].number_input("vCPU", min_value=0.0, step=1.0, format="%g")
            ram = c[1].number_input("RAM (Go)", min_value=0.0, step=1.0, format="%g")
            gpu = c[2].number_input("GPU", min_value=0.0, step=1.0, format="%g")
            region = c[3].text_input("Région / site")
        if st.form_submit_button("💾 Créer l'asset", type="primary"):
            if not nom.strip():
                st.error("Le nom est obligatoire.")
            elif aid.strip() in set(assets.id):
                st.error(f"L'ID {aid} existe déjà.")
            else:
                L.enregistrer_asset(dict(id=aid.strip(), type=typ, nom=nom.strip(), fournisseur=fourn, prix=prix, unite=unite, qte_parc=parc,
                                         date_effet=L.iso(eff), statut="Actif", vcpu=vcpu or None, ram_go=ram or None, gpu=gpu or None,
                                         region=region or None))
                st.success(f"Asset {aid} créé : {nom} · {eur(prix * L.FACTEURS[unite], 2)} / mois par unité.")
                st.rerun()


def form_instance_cloud(assets):
    st.caption("Une instance cloud (ex. un profil IBM Cloud VPC) : capacités lues dans le nom, prix horaire du contrat, et mode de refacturation.")
    g, dr = st.columns([1.4, 1], gap="large")
    with g:
        c1, c2, c3 = st.columns([1.6, 1.2, 1])
        nom = c1.text_input("Nom (profil du fournisseur)", "IBM bx3d-128x640", key="ic_nom")
        fourn = c2.text_input("Fournisseur", "IBM Cloud", key="ic_f")
        region = c3.text_input("Région", "eu-de", key="ic_r")
        fl = L.lire_flavor(nom)
        if fl:
            st.caption(f"Lu dans « {fl['profil']} » : famille {fl['famille']}, {fl['vcpu']:g} vCPU, {fl['ram_go']:g} Go de RAM"
                       + (f", {fl['gpu']:g} GPU {fl.get('gpu_modele', '')}" if fl.get("gpu") else "")
                       + (", stockage local (d)" if fl.get("stockage_local") else "") + ". Les valeurs restent modifiables.")
        else:
            st.caption("Nom non reconnu : saisissez les capacités.")
        c = st.columns(5)
        cle = fl.get("profil", "x")
        vcpu = c[0].number_input("vCPU", min_value=0.0, step=1.0, format="%g", value=float(fl.get("vcpu", 0)), key=f"ic_v_{cle}")
        ram = c[1].number_input("RAM (Go)", min_value=0.0, step=1.0, format="%g", value=float(fl.get("ram_go", 0)), key=f"ic_ram_{cle}")
        sto = c[2].number_input("Stockage local (Go)", min_value=0.0, step=100.0, format="%g", value=0.0, key=f"ic_s_{cle}")
        gpu = c[3].number_input("GPU", min_value=0.0, step=1.0, format="%g", value=float(fl.get("gpu", 0)), key=f"ic_g_{cle}")
        res = c[4].number_input("Réseau (Gb/s)", min_value=0.0, step=1.0, format="%g", value=0.0, key=f"ic_n_{cle}")
        c = st.columns(4)
        prix = c[0].number_input("Prix unitaire (€)", min_value=0.0, value=0.0, step=0.1, format="%.3f", key="ic_p")
        unite = c[1].selectbox("Unité", L.UNITES, index=0, key="ic_u")
        eff = c[2].date_input("Date d'effet", value=date(L.annee(), 1, 1), format="DD/MM/YYYY", key="ic_d")
        parc = c[3].number_input("Instances (parc)", min_value=0.0, value=1.0, step=1.0, format="%g", key="ic_q")
        cm = prix * L.FACTEURS[unite]
        st.markdown(f"{prix:,.3f} € × {L.FACTEURS[unite]:g} = **{eur(cm)} / mois par instance** · parc : {eur(cm * parc)} / mois".replace(",", " "))
    with dr:
        modes = ["entiere", "part_vcpu"] + (["part_gpu"] if gpu else [])
        mode = st.radio("Comment la refacturer ?", modes, key="ic_mode", format_func={
            "entiere": "À l'instance entière — un client prend une machine complète",
            "part_vcpu": "À la part, par vCPU — machine partagée entre clients",
            "part_gpu": "À la part, par GPU — machine partagée entre clients"}.get)
        n = vcpu if mode == "part_vcpu" else gpu if mode == "part_gpu" else 0
        nid = L.prochain_id("assets", "A-", 3)
        with st.container(border=True):
            st.markdown("**Sera créé**")
            lignes = [dict(Asset=f"{nom} ({nid})", Rôle="coût du parc" if mode != "entiere" else "vendu aux clients", **{"Coût / mois": eur(cm)}, Parc=f"{parc:g}")]
            if n:
                lignes.append(dict(Asset=f"{'vCPU' if mode == 'part_vcpu' else 'GPU'} {L.lire_flavor(nom).get('profil', nom)} (part)", Rôle="vendu aux clients",
                                   **{"Coût / mois": eur(cm / n, 2)}, Parc=f"{parc * n:g}"))
            st.dataframe(pd.DataFrame(lignes), hide_index=True, use_container_width=True)
            if n:
                st.caption(f"Prix de la part = prix de l'instance ÷ {n:g}. Si le prix de l'instance change, la part suit à la même date. "
                           + (f"Chaque vCPU vendu inclut {ram / vcpu:g} Go de RAM." if mode == "part_vcpu" and vcpu else ""))
        if st.button("💾 Créer l'instance", type="primary", key="ic_ok"):
            if not nom.strip() or prix <= 0:
                st.error("Le nom et le prix sont obligatoires.")
            elif nom.strip().lower() in set(assets.nom.str.lower()):
                st.error("Un asset porte déjà ce nom.")
            elif mode != "entiere" and n <= 0:
                st.error("Indiquez le nombre de vCPU (ou de GPU) pour vendre à la part.")
            else:
                L.enregistrer_asset(dict(id=nid, type="Instance cloud", nom=nom.strip(), fournisseur=fourn, region=region, prix=prix, unite=unite,
                                         qte_parc=parc, date_effet=L.iso(eff), statut="Actif", vcpu=vcpu or None, ram_go=ram or None,
                                         stockage_go=sto or None, gpu=gpu, gpu_modele=fl.get("gpu_modele"), reseau_gbs=res or None, refacturation=mode))
                st.success(f"Instance {nid} créée" + (" avec sa part." if n else "."))
                st.rerun()


def bloc_import(quoi):
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


# ======================================================================== CLIENTS
def page_clients():
    st.title("Clients")
    st.caption("Nom, entité et pays permettent de suivre la consommation par pays et par entité.")
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
                                    "cout": st.column_config.NumberColumn(f"Coût / mois", format=EUR, disabled=True),
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


# ======================================================================== OFFRES
def page_offres():
    offres_ui.page()


def donut(df, cat, val, titre, couleurs):
    return (alt.Chart(df, title=titre).mark_arc(innerRadius=60, stroke="#fff")
            .encode(theta=alt.Theta(f"{val}:Q"), color=alt.Color(f"{cat}:N", scale=alt.Scale(domain=L.liste("type"), range=couleurs), legend=alt.Legend(title=None)),
                    tooltip=[alt.Tooltip(f"{cat}:N", title="Type"), alt.Tooltip(f"{val}:Q", title="€", format=",.0f")])
            .properties(height=300))


# ======================================================================== AFFECTATIONS
def page_affectation():
    affectations_ui.page()


# ======================================================================== DEVIS
def page_devis():
    devis_ui.page()


# ======================================================================== CONSOMMATION
def filtres(prefix, avec_client=False):
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


def page_conso():
    st.title("Suivi de la consommation mensuelle")
    st.caption(f"Coût refacturé par client et par mois (offres + options). Réel jusqu'à {mois_txt()}, prévision ensuite.")
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


def bouton_rapport(cle, ids=None, releves=False):
    """Bouton en deux temps : générer le classeur, puis le télécharger."""
    c1, c2 = st.columns([1, 2])
    if c1.button("📊 Générer le rapport Excel", type="primary", key=f"gen_{cle}"):
        with st.spinner("Génération du classeur…"):
            st.session_state[f"rap_{cle}"] = rapport.generer_rapport(ids, releves)
    if st.session_state.get(f"rap_{cle}"):
        c2.download_button("⬇️ Télécharger le rapport", st.session_state[f"rap_{cle}"],
                           f"IA_Platform_rapport_{L.annee()}_{date.today():%Y%m%d}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"dl_{cle}")


def page_rapports():
    st.title("Rapports Excel")
    st.caption("Génère un classeur Excel mis en forme : référentiel clients et consommation par mois, avec totaux et graphique.")
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


# ======================================================================== DASHBOARD
def page_dashboard():
    dashboard_ui.page()


# ======================================================================== EXERCICES
def page_exercices():
    st.title("Exercices")
    st.caption("Un exercice par année. La clôture fige les montants de l'année : ils ne seront plus recalculés, même si les prix ou les offres changent.")
    t1, t2, t3, t4, t5 = st.tabs(["Exercices et clôture", "Budgets", "Ajustements", "Archives", "Réinitialisation"])
    ex = L.exercices_df()
    a = L.annee()
    with t1:
        vue = ex.copy()
        st.dataframe(vue[["annee", "statut", "mois_ref", "date_ouverture", "date_cloture", "cout_parc", "refacture", "ecart"]], hide_index=True,
                     use_container_width=True, column_config={
                         "annee": st.column_config.NumberColumn("Exercice", format="%d"), "statut": "Statut", "mois_ref": "Dernier mois réel",
                         "date_ouverture": st.column_config.DateColumn("Ouvert le", format="DD/MM/YYYY"),
                         "date_cloture": st.column_config.DateColumn("Clôturé le", format="DD/MM/YYYY"),
                         "cout_parc": st.column_config.NumberColumn("Coût du parc", format=EUR0),
                         "refacture": st.column_config.NumberColumn("Refacturé", format=EUR0),
                         "ecart": st.column_config.NumberColumn("Écart", format=EUR0)})
        st.subheader(f"Exercice {a}")
        b = L.bilan_exercice(a)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Coût du parc (année)", eur(b["cout_parc"]))
        c2.metric("Refacturé (année)", eur(b["refacture"]))
        c3.metric("Écart refacturé − coût", eur(b["ecart"]))
        c4.metric("Taux de couverture", f"{b['refacture'] / b['cout_parc'] * 100:.1f} %".replace(".", ",") if b["cout_parc"] else "-")
        if L.est_cloture(a):
            st.success(f"Exercice {a} clôturé le {L.d(L.exercice(a).date_cloture):%d/%m/%Y} : les montants sont figés.")
            with st.expander("Rouvrir l'exercice (correction)"):
                st.warning("Rouvrir supprime les montants figés : l'année sera recalculée avec les prix et offres actuels. "
                           "Une copie de la base est archivée avant.")
                if st.checkbox("Je confirme vouloir rouvrir l'exercice", key="conf_rouvrir") and st.button("Rouvrir l'exercice"):
                    L.rouvrir_exercice(a)
                    st.rerun()
        else:
            st.markdown("**1. Ventiler l'écart (facultatif)**")
            st.caption("Répartit l'écart entre le coût du parc et le montant refacturé sur les clients consommateurs, "
                       "sous forme d'ajustements en décembre. Le centre de coûts finit alors l'année à zéro.")
            cle = st.radio("Clé de répartition", ["Consommation", "Parts égales"], horizontal=True)
            sim = L.simuler_ventilation(a, cle)
            det = sim["detail"].assign(total=lambda x: x.conso + x.quote_part, part=lambda x: x.part * 100)
            st.dataframe(det, hide_index=True, use_container_width=True, height=min(38 * (len(det) + 1), 320), column_config={
                "client_id": "ID", "client": "Client", "conso": st.column_config.NumberColumn("Refacturé", format=EUR0),
                "part": st.column_config.NumberColumn("Part", format="%.1f %%"),
                "quote_part": st.column_config.NumberColumn("Quote-part de l'écart", format=EUR0),
                "total": st.column_config.NumberColumn("Total après ventilation", format=EUR0)})
            if sim["refacture"]:
                st.caption(f"Écart à répartir : {eur(sim['ecart'])}, soit {sim['ecart'] / sim['refacture'] * 100:+.1f} % du montant refacturé.".replace(".", ","))
            if st.button("Appliquer la ventilation"):
                d2 = sim["detail"].copy()
                if cle == "Parts égales":
                    d2["part"] = d2["part"]
                L.appliquer_ventilation(a, d2)
                st.success("Ventilation enregistrée dans les ajustements (décembre).")
                st.rerun()
            st.markdown("**2. Clôturer l'exercice**")
            st.caption("Fige la consommation de chaque client mois par mois, archive une copie de la base et le rapport Excel de l'année.")
            if L.mois_ref(a) < 12:
                st.info(f"Le dernier mois réel est {L.MOIS_LONG[L.mois_ref(a) - 1]} : la clôture figera aussi les mois de prévision.")
            if st.checkbox(f"Je confirme la clôture de l'exercice {a}", key="conf_clot") and st.button(f"🔒 Clôturer {a}", type="primary"):
                with st.spinner("Clôture en cours…"):
                    r = L.cloturer_exercice(a)
                    L.archiver(a, f"IA_Platform_rapport_{a}_cloture.xlsx", rapport.generer_rapport(None, True))
                st.success(f"Exercice {a} clôturé : {r['lignes']} lignes figées.")
                st.rerun()
        st.divider()
        st.markdown("**Ouvrir un nouvel exercice**")
        suivant = int(ex.annee.max()) + 1 if len(ex) else date.today().year
        c1, c2, c3 = st.columns(3)
        n = c1.number_input("Année", value=suivant, step=1)
        copier = c2.checkbox(f"Reprendre les budgets {n - 1}", value=True)
        evo = c3.number_input("Évolution des budgets (%)", value=0.0, step=1.0, disabled=not copier)
        grille = st.file_uploader(f"Nouvelle grille de prix au 01/01/{n} (CSV, facultatif)", type=["csv"], key="grille")
        st.caption("Les clients, assets, offres et affectations en cours sont conservés : une affectation sans date de fin continue sur le nouvel exercice.")
        if st.button(f"Ouvrir l'exercice {int(n)}"):
            try:
                L.ouvrir_exercice(int(n), (int(n) - 1) if copier else None, evo)
                if grille is not None:
                    rap = L.appliquer_grille_prix(L.lire_csv(grille), int(n))
                    st.info("Grille de prix : " + " · ".join(f"{k} : {v}" for k, v in rap.items() if k != "ignorés"))
                st.success(f"Exercice {int(n)} ouvert et sélectionné.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
    with t2:
        st.caption(f"Budget annuel alloué à chaque client pour {a}, comparé à sa consommation.")
        bd = L.budgets_df(a)
        cc = L.conso_clients().set_index("client_id")
        bd["reel"] = bd.client_id.map(cc.reel).fillna(0)
        bd["prevision"] = bd.client_id.map(cc.total).fillna(0)
        bd["reste"] = bd.budget - bd.prevision
        bd["pct"] = [(p / b_ * 100) if b_ else None for p, b_ in zip(bd.prevision, bd.budget)]
        bd["alerte"] = ["Dépassement" if (p and p > 100) else "Seuil 80 %" if (p and p >= 80) else "" for p in bd.pct]
        ed = st.data_editor(bd, hide_index=True, use_container_width=True, key=f"bud_{a}", disabled=L.est_cloture(a), height=520,
                            column_config={"client_id": st.column_config.TextColumn("ID", disabled=True), "client": st.column_config.TextColumn("Client", disabled=True),
                                           "entite": st.column_config.TextColumn("Entité", disabled=True), "pays": st.column_config.TextColumn("Pays", disabled=True),
                                           "statut": st.column_config.TextColumn("Statut", disabled=True),
                                           "budget": st.column_config.NumberColumn(f"Budget {a}", format=EUR0, min_value=0, step=1000),
                                           "reel": st.column_config.NumberColumn("Consommé", format=EUR0, disabled=True),
                                           "prevision": st.column_config.NumberColumn("Prévision année", format=EUR0, disabled=True),
                                           "reste": st.column_config.NumberColumn("Reste (prévision)", format=EUR0, disabled=True),
                                           "pct": st.column_config.ProgressColumn("Prévision / budget", format="%.0f %%", min_value=0, max_value=150),
                                           "alerte": st.column_config.TextColumn("Alerte", disabled=True)})
        c1, c2, c3 = st.columns(3)
        c1.metric("Budgets alloués", eur(bd.budget.sum()))
        c2.metric("Prévision de consommation", eur(bd.prevision.sum()))
        c3.metric("Clients en dépassement", int((bd.alerte == "Dépassement").sum()))
        if not L.est_cloture(a) and st.button("💾 Enregistrer les budgets", type="primary"):
            L.enregistrer_budgets(a, ed)
            st.success("Budgets enregistrés.")
            st.rerun()
    with t3:
        st.caption("Frais ponctuels, avoirs (montant négatif) et ventilation de l'écart. Ils s'ajoutent à la consommation du mois indiqué.")
        aj = L.ajustements_df(a)
        st.dataframe(aj, hide_index=True, use_container_width=True, column_config={
            "id": "N°", "mois": "Mois", "client_id": "ID", "client": "Client", "libelle": "Libellé",
            "montant": st.column_config.NumberColumn("Montant", format=EUR), "nature": "Nature"})
        if not L.est_cloture(a):
            with st.form("aj"):
                clients = L.q("SELECT id, nom FROM clients ORDER BY id")
                c1, c2, c3 = st.columns([2, 1, 1])
                cid = c1.selectbox("Client", clients.id, format_func=lambda x: f"{x} — {clients.set_index('id').nom[x]}")
                mois = c2.selectbox("Mois", range(1, 13), format_func=lambda i: L.MOIS_LONG[i - 1])
                mt = c3.number_input("Montant (€)", value=0.0, step=100.0)
                lib = st.text_input("Libellé", "Frais de mise en service")
                if st.form_submit_button("Ajouter l'ajustement"):
                    L.ajouter_ajustement(a, mois, cid, lib, mt)
                    st.rerun()
            if len(aj):
                sup = st.selectbox("Supprimer un ajustement", aj.id, format_func=lambda x: f"N° {x} — {aj.set_index('id').libelle[x]}")
                if st.button("Supprimer"):
                    L.run("DELETE FROM ajustements WHERE id=?", (int(sup),))
                    st.rerun()
    with t4:
        st.caption("Copies de la base faites avant chaque clôture ou réouverture, et rapports Excel de clôture.")
        ar = L.archives_df()
        if ar.empty:
            st.info("Aucune archive pour le moment.")
        for r in ar.itertuples():
            c1, c2, c3 = st.columns([3, 2, 1])
            c1.write(f"**{r.nom}**")
            c2.caption(f"Exercice {r.annee} · {r.date.replace('T', ' ')} · {r.taille / 1024:.0f} Ko")
            c3.download_button("⬇️", L.archive_contenu(r.id), r.nom, key=f"ar_{r.id}")
        st.divider()
        st.download_button("⬇️ Sauvegarder la base actuelle", L.DB_PATH.read_bytes(), f"ia_platform_{date.today():%Y%m%d}.db")
    with t5:
        st.warning("La réinitialisation supprime les affectations, devis, budgets, ajustements, exercices et montants figés. "
                   "Une copie complète de la base est d'abord enregistrée dans le dossier « archives ».")
        c1, c2, c3 = st.columns(3)
        dep = c1.number_input("Exercice de départ", value=date.today().year + 1, step=1)
        garder_ref = c2.checkbox("Garder assets, prix et offres", value=True)
        garder_cli = c3.checkbox("Garder les clients", value=True)
        conf = st.text_input("Tapez RÉINITIALISER pour confirmer")
        if st.button("Repartir à zéro", disabled=conf.strip().upper() not in ("RÉINITIALISER", "REINITIALISER")):
            cible = L.reinitialiser(int(dep), garder_ref, garder_cli)
            st.success(f"Base réinitialisée. Copie de sauvegarde : archives/{cible.name}")
            st.rerun()
        st.divider()
        if st.button("Recharger les données d'exemple (efface tout)"):
            L.sauvegarde_fichier()
            L.DB_PATH.unlink(missing_ok=True)
            L.init_db()
            st.rerun()


# ======================================================================== PARAMÈTRES
def page_parametres():
    st.title("Paramètres")
    st.caption("L'exercice affiché se choisit dans la barre latérale ; la création et la clôture des exercices se font dans « Exercices ».")
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
                   "enregistrée dans le dossier « archives ». Les listes (types, entités, pays) sont conservées.")
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


pages = [
    st.Page(page_accueil, title="Accueil", icon="🏠", url_path="accueil", default=True),
    st.Page(page_assets, title="Assets", icon="🖥️", url_path="assets"),
    st.Page(page_clients, title="Clients", icon="👥", url_path="clients"),
    st.Page(page_offres, title="Offres", icon="📦", url_path="offres"),
    st.Page(page_affectation, title="Affectations", icon="🔁", url_path="affectation"),
    st.Page(page_devis, title="Devis", icon="🧾", url_path="devis"),
    st.Page(page_conso, title="Consommation", icon="📅", url_path="consommation"),
    st.Page(page_dashboard, title="Dashboard", icon="📊", url_path="dashboard"),
    st.Page(page_rapports, title="Rapports Excel", icon="📄", url_path="rapports"),
    st.Page(page_exercices, title="Exercices", icon="🗓️", url_path="exercices"),
    st.Page(page_parametres, title="Paramètres", icon="⚙️", url_path="parametres"),
]
st.sidebar.markdown("### IA Platform")
st.sidebar.caption("Équipe A · centre de coûts")
_ex = L.exercices_df()
if len(_ex):
    _annees = _ex.annee.astype(int).tolist()
    _sel = st.sidebar.selectbox("Exercice", _annees, index=_annees.index(L.annee()) if L.annee() in _annees else len(_annees) - 1,
                                format_func=lambda x: f"{x} · {'clôturé 🔒' if _ex.set_index('annee').statut[x] == 'Clôturé' else 'ouvert'}")
    if _sel != L.annee():
        L.set_param("annee", int(_sel))
        st.rerun()
    if L.est_cloture():
        st.sidebar.info("Exercice clôturé : montants figés, consultation seule pour cette année.")
devis_ui.PAGE_AFF = pages[4]
offres_ui.PAGE_DEVIS = pages[5]
dashboard_ui.PAGES.update(affectation=pages[4], devis=pages[5])
_pg = st.navigation(pages)
st.session_state["_page_prec"] = st.session_state.get("_page_cour")
st.session_state["_page_cour"] = _pg.url_path
if _pg.url_path != "affectation":
    st.session_state["_aff_vu"] = False
_pg.run()
