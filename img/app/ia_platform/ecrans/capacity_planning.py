"""Page Capacity planning : collecte des besoins des métiers pour une période donnée."""
from datetime import date, timedelta
from urllib.parse import quote

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.core import planning as P
from ia_platform.ui.theme import entete

VUES = ["Campagne", "Saisie des besoins"]
PASTILLE = {"En attente": "🟠", "En cours de saisie": "🔵", "Reçu": "🟢", "Rien à signaler": "⚪"}


def _toast():
    m = st.session_state.pop("cp_msg", None)
    if m:
        st.toast(m, icon="✅")


def _mois_options(autour=None):
    base = date.today().year
    ans = range(base - 1, base + 4)
    opts = [date(a, m, 1) for a in ans for m in range(1, 13)]
    if autour and autour not in opts:
        opts = sorted(opts + [autour])
    return opts


def _choix_mois(label, valeur, key, disabled=False, col=st):
    opts = _mois_options(valeur)
    return col.selectbox(label, opts, index=opts.index(valeur), format_func=L.mois_txt_court, key=key, disabled=disabled)


def _assets_libelles():
    a = L.assets_df()
    a = a[a.statut != "Retiré"]
    return {f"{r.id} · {r.nom}": r.id for r in a.itertuples()}


def _editeur_ressources(ressources, key, disabled=False):
    lib = _assets_libelles()
    inv = {v: k for k, v in lib.items()}
    df = pd.DataFrame([{"Ressource": r["nom"], "Unité": r["unite"], "Asset lié": inv.get(r.get("asset_id"))} for r in ressources],
                      columns=["Ressource", "Unité", "Asset lié"])
    out = st.data_editor(df, key=key, num_rows="dynamic", hide_index=True, use_container_width=True, disabled=disabled,
                         column_config={"Ressource": st.column_config.TextColumn(required=True, width="large"),
                                        "Unité": st.column_config.TextColumn(help="GPU, vCPU, To, licences…"),
                                        "Asset lié": st.column_config.SelectboxColumn(options=list(lib), width="medium",
                                                                                      help="Facultatif : sert au coût estimé.")})
    return [{"nom": r["Ressource"], "unite": r["Unité"], "asset_id": lib.get(r["Asset lié"])} for _, r in out.iterrows()]


# ------------------------------------------------------------------ nouvelle campagne
@st.dialog("Nouvelle campagne", width="large")
def dlg_nouvelle():
    camps = P.campagnes_df()
    prec = P.campagne(camps.id.iloc[0]) if len(camps) else None
    an = L.d(prec['fin']).year + 1 if prec else L.annee() + 1
    c1, c2 = st.columns([2, 1])
    nom = c1.text_input("Nom", f"Besoins {an}")
    dec = c2.selectbox("Découpage", P.DECOUPAGES, index=1, help="Granularité demandée aux métiers : une colonne par période.")
    c1, c2, c3 = st.columns(3)
    debut = _choix_mois("Début de la période", date(an, 1, 1), "cpn_deb", col=c1)
    fin = _choix_mois("Fin de la période", date(an, 12, 1), "cpn_fin", col=c2)
    limite = c3.date_input("Date limite de réponse", date.today() + timedelta(days=30), format="DD/MM/YYYY")
    entites = L.liste("entite")
    defaut = [m for m in P.metiers_df(prec["id"]).metier if m in entites] if prec else entites
    metiers = st.multiselect("Métiers sollicités", entites, default=defaut)
    st.markdown("**Ressources proposées aux métiers**")
    st.caption("Reprises de la campagne précédente" if prec else "Proposées à partir du catalogue des assets : retirez ou ajoutez des lignes.")
    ress = _editeur_ressources(prec["ressources"] if prec else P.ressources_suggerees(), "cpn_ress")
    reprendre = st.checkbox(f"Reprendre les contacts de « {prec['nom']} »", value=True) if prec else False
    if st.button("Créer la campagne", type="primary"):
        contacts = {}
        if reprendre:
            for r in P.metiers_df(prec["id"]).itertuples():
                contacts[r.metier] = (r.contact or "", r.email or "")
        try:
            if not metiers:
                raise ValueError("Choisissez au moins un métier.")
            cid = P.creer_campagne(nom, debut, fin, dec, limite, metiers, ress, contacts)
        except ValueError as e:
            st.error(str(e))
            return
        st.session_state.cp_camp = cid
        st.session_state.cp_vue = "Campagne"
        st.session_state.cp_msg = f"Campagne « {nom} » créée."
        st.rerun()


# ------------------------------------------------------------------ vue campagne
def _ouvrir_saisie(m):
    st.session_state.cp_vue = "Saisie des besoins"
    st.session_state.cp_metier = m


def vue_campagne(camp):
    cid = camp["id"]
    met = P.metiers_df(cid)
    nb = len(L.q("SELECT id FROM besoins WHERE campagne_id=?", (cid,)))
    rep = int(met.statut.isin(P.REPONDU).sum())
    sans = met[met.statut == "En attente"]
    limite = L.date_fr(camp["date_limite"])
    reste = (limite - date.today()).days

    k = st.columns(4)
    k[0].metric("Métiers sollicités", len(met), help=f"Campagne créée le {P.jour(camp['date_creation']):%d/%m/%Y}")
    k[1].metric("Réponses", f"{rep} / {len(met)}", help="« Reçu » et « Rien à signaler » comptent comme des réponses.")
    k[1].progress(rep / len(met) if len(met) else 0.0)
    k[2].metric("Besoins collectés", nb, help=f"sur {len(camp['ressources'])} ressources proposées")
    k[3].metric("Date limite de réponse", f"{limite:%d/%m/%Y}")
    k[3].caption((f"dans {reste} jour(s)" if reste >= 0 else f"⚠️ dépassée de {-reste} jour(s)")
                 + (f" · **{len(sans)} métier(s) sans réponse**" if len(sans) else " · tous les métiers ont répondu"))

    g, d_ = st.columns([1.7, 1], gap="large")
    with g:
        st.markdown("#### Suivi des réponses")
        vue = pd.DataFrame({
            "metier": met.metier, "Statut": [f"{PASTILLE.get(s, '')} {s}" for s in met.statut], "Besoins": met.n,
            "Mise à jour": [P.jour(x) for x in met.date_maj],
            "Relances": [f"{n} (le {P.jour(dr):%d/%m})" if n and P.jour(dr) else "—" for n, dr in zip(met.nb_relances, met.date_relance)],
            "contact": met.contact.fillna(""), "email": met.email.fillna("")})
        ed = st.data_editor(vue, key=f"cp_suivi_{cid}_{st.session_state.get('cp_n', 0)}", hide_index=True, use_container_width=True,
                            disabled=["metier", "Statut", "Besoins", "Mise à jour", "Relances"],
                            column_config={"metier": st.column_config.TextColumn("Métier"), "contact": st.column_config.TextColumn("Contact"),
                                           "email": st.column_config.TextColumn("Email", width="medium"),
                                           "Mise à jour": st.column_config.DateColumn(format="DD/MM/YYYY")})
        if not ed[["contact", "email"]].fillna("").equals(vue[["contact", "email"]]):
            P.enregistrer_contacts(cid, ed.fillna({"contact": "", "email": ""}))
            st.toast("Contacts enregistrés.", icon="✅")
        st.caption("Contact et email se modifient directement dans le tableau.")

        a1, a2, a3 = st.columns([1.3, 1, 1])
        m = a1.selectbox("Métier", list(met.metier), key="cp_m_suivi", label_visibility="collapsed")
        a2.button("Ouvrir la saisie ›", on_click=_ouvrir_saisie, args=(m,), use_container_width=True, disabled=not m)
        with a3.popover("Retirer de la campagne", use_container_width=True, disabled=not m):
            st.write(f"Retirer **{m}** et supprimer ses besoins saisis ?")
            if st.button("Retirer", type="primary", key="cp_retirer"):
                P.retirer_metier(cid, m)
                st.session_state.cp_msg = f"{m} retiré de la campagne."
                st.rerun()

        if len(sans) and camp["statut"] == "Ouverte":
            emails = [e for e in sans.email if e]
            sujet = f"Rappel : {camp['nom']} – besoins à transmettre avant le {limite:%d/%m/%Y}"
            corps = (f"Bonjour,\n\nNous n'avons pas encore reçu vos besoins pour la campagne « {camp['nom']} » "
                     f"({L.mois_txt_court(camp['debut'])} → {L.mois_txt_court(camp['fin'])}).\n"
                     f"Merci de compléter le fichier joint et de nous le renvoyer avant le {limite:%d/%m/%Y}, "
                     "ou de nous indiquer si vous n'avez pas de besoin supplémentaire.\n\nCordialement,\nÉquipe A")
            r1, r2 = st.columns([1.4, 1])
            r1.link_button(f"✉️ Relancer les {len(sans)} métier(s) sans réponse",
                           f"mailto:?bcc={quote(';'.join(emails))}&subject={quote(sujet)}&body={quote(corps)}", use_container_width=True,
                           disabled=not emails)
            if r2.button("✓ Noter la relance comme envoyée", use_container_width=True):
                P.noter_relance(cid, list(sans.metier))
                st.session_state.cp_msg = "Relance notée."
                st.rerun()
            if not emails:
                st.caption("Renseignez les emails des contacts pour préparer le message de relance.")

        autres = [e for e in L.liste("entite") if e not in set(met.metier)]
        if autres:
            with st.expander("＋ Ajouter des métiers"):
                ajout = st.multiselect("Métiers", autres, key="cp_ajout", label_visibility="collapsed")
                if st.button("Ajouter", disabled=not ajout):
                    P.ajouter_metiers(cid, ajout)
                    st.session_state.cp_msg = f"{len(ajout)} métier(s) ajouté(s)."
                    st.rerun()

    with d_:
        st.markdown("#### Fichiers Excel")
        st.download_button("📄 Modèles à envoyer aux métiers (.zip)", P.modeles_zip(cid), f"{camp['nom']} - modèles.zip",
                           "application/zip", use_container_width=True,
                           help="Un fichier par métier, pré-rempli avec ce qui est déjà saisi, avec listes déroulantes.")
        st.download_button("📊 Exporter toutes les données (.xlsx)", P.export_excel(cid), f"{camp['nom']} - export.xlsx",
                           use_container_width=True, type="primary",
                           help="Paramètres, suivi des réponses, besoins (une colonne par période) et format liste pour tableau croisé.")
        fichiers = st.file_uploader("Importer les fichiers reçus", type=["xlsx"], accept_multiple_files=True,
                                    key=f"cp_up_{st.session_state.get('cp_n', 0)}", disabled=camp["statut"] != "Ouverte",
                                    help="Le métier est reconnu automatiquement. Ses besoins sont remplacés par ceux du fichier et il passe à « Reçu ».")
        if fichiers and st.button("Importer", type="primary", use_container_width=True):
            ok, ko = [], []
            for f in fichiers:
                try:
                    m_, n_ = P.importer_modele(f, cid)
                    ok.append(f"{m_} : {n_} besoin(s)")
                except Exception as e:  # noqa: BLE001 — on rapporte l'erreur fichier par fichier
                    ko.append(f"**{f.name}** :\n" + "\n".join(f"- {x}" for x in str(e).split("\n")))
            st.session_state.cp_n = st.session_state.get("cp_n", 0) + 1
            if ok:
                st.session_state.cp_msg = "Importé — " + " · ".join(ok)
            if ko:
                st.session_state.cp_err = ko
            st.rerun()
        for e in st.session_state.pop("cp_err", []):
            st.error(e)

        st.markdown("#### Paramètres")
        verrou = nb > 0
        with st.container(border=True):
            nom = st.text_input("Nom", camp["nom"], key=f"cpp_nom_{cid}")
            c1, c2 = st.columns(2)
            debut = _choix_mois("Début", L.d(camp["debut"]), f"cpp_deb_{cid}", verrou, c1)
            fin = _choix_mois("Fin", L.d(camp["fin"]), f"cpp_fin_{cid}", verrou, c2)
            dec = st.segmented_control("Découpage", P.DECOUPAGES, default=camp["decoupage"], key=f"cpp_dec_{cid}", disabled=verrou) or camp["decoupage"]
            if verrou:
                st.caption("🔒 Période et découpage verrouillés : des besoins sont déjà saisis.")
            c1, c2 = st.columns(2)
            limite_n = c1.date_input("Date limite", limite, format="DD/MM/YYYY", key=f"cpp_lim_{cid}")
            statut = c2.selectbox("Statut", ["Ouverte", "Clôturée"], index=0 if camp["statut"] == "Ouverte" else 1, key=f"cpp_st_{cid}",
                                  help="Clôturée : plus aucune saisie ni import.")
            st.markdown("**Ressources proposées**")
            ress = _editeur_ressources(camp["ressources"], f"cpp_ress_{cid}_{st.session_state.get('cp_n', 0)}")
            if st.button("Enregistrer les paramètres", use_container_width=True):
                try:
                    P.modifier_campagne(cid, nom, debut, fin, dec, limite_n, statut, ress)
                    st.session_state.cp_msg = "Paramètres enregistrés."
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        with st.popover("🗑 Supprimer la campagne", use_container_width=True):
            st.write(f"Supprimer **{camp['nom']}**, ses métiers et ses {nb} besoin(s) ? Pensez à exporter les données avant.")
            if st.button("Supprimer définitivement", type="primary", key="cp_suppr"):
                P.supprimer_campagne(cid)
                st.session_state.pop("cp_camp", None)
                st.session_state.cp_msg = "Campagne supprimée."
                st.rerun()


# ------------------------------------------------------------------ vue saisie
def vue_saisie(camp):
    cid = camp["id"]
    met = P.metiers_df(cid)
    if met.empty:
        st.info("Aucun métier dans cette campagne : ajoutez-en depuis la vue Campagne.")
        return
    liste = list(met.metier)
    if st.session_state.get("cp_metier") not in liste:
        st.session_state.cp_metier = liste[0]
    c1, c2, c3 = st.columns([1.2, 1, 2])
    metier = c1.selectbox("Métier", liste, key="cp_metier",
                          format_func=lambda m: f"{PASTILLE.get(met.set_index('metier').statut[m], '')} {m}")
    r = met.set_index("metier").loc[metier]
    maj = P.jour(r.date_maj)
    c2.markdown(f"<div style='padding-top:30px'><b>{r.statut}</b>{f' · le {maj:%d/%m/%Y}' if maj else ''}</div>", unsafe_allow_html=True)
    c3.markdown(f"<div style='padding-top:30px;color:#55625C'>Contact : {r.contact or '—'}{f' · {r.email}' if r.email else ''}</div>",
                unsafe_allow_html=True)

    deja = P.offres_en_cours(metier)
    with st.expander(f"Ce que le métier a déjà aujourd'hui ({len(deja)} ligne(s) en cours)"):
        if deja.empty:
            st.caption("Aucune offre ni option en cours pour les clients de ce métier.")
        else:
            st.dataframe(deja, hide_index=True, use_container_width=True)

    ouvert = camp["statut"] == "Ouverte"
    pers = P.libelles_periodes(camp)
    clients = list(P.clients_du_metier(metier).nom)
    ress = [x["nom"] for x in camp["ressources"]]
    df = P.tableau_saisie(cid, metier)
    st.markdown(f"#### Besoins supplémentaires · {L.mois_txt_court(camp['debut'])} → {L.mois_txt_court(camp['fin'])}")
    st.caption("Une ligne par projet et par ressource. Quantités **en plus** de ce qui est déjà alloué. L'unité se met à jour à l'enregistrement.")
    cfg = {"Client": st.column_config.SelectboxColumn(options=clients, help="Client existant du métier ; vide pour un nouveau projet."),
           "Projet / usage": st.column_config.TextColumn(width="medium"),
           "Ressource": st.column_config.SelectboxColumn(options=ress, required=True, width="medium"),
           "Unité": st.column_config.TextColumn(disabled=True, width="small"),
           "Priorité": st.column_config.SelectboxColumn(options=P.PRIORITES, default="Moyenne"),
           "Confiance": st.column_config.SelectboxColumn(options=P.CONFIANCES, default="Probable"),
           "Commentaire": st.column_config.TextColumn(width="medium")}
    for p in pers:
        cfg[p] = st.column_config.NumberColumn(p, min_value=0, step=1, format="%g", default=0)
    ed = st.data_editor(df, key=f"cp_ed_{cid}_{metier}_{st.session_state.get('cp_n', 0)}", num_rows="dynamic", hide_index=True,
                        use_container_width=True, column_config=cfg, disabled=not ouvert)
    if not ouvert:
        st.info("Campagne clôturée : consultation seule.")

    def sauver(statut=None):
        try:
            n = P.enregistrer_besoins(cid, metier, ed, statut)
        except ValueError as e:
            st.error("Le tableau contient des erreurs :\n\n" + "\n".join(f"- {x}" for x in str(e).split("\n")))
            return
        st.session_state.cp_n = st.session_state.get("cp_n", 0) + 1
        st.session_state.cp_msg = f"{metier} : {n} besoin(s) enregistré(s)" + (f", statut « {statut} »." if statut else ".")
        st.rerun()

    b1, b2, b3, b4 = st.columns([1, 1.2, 1.2, 1.4])
    if b1.button("Enregistrer", type="primary", disabled=not ouvert, use_container_width=True):
        sauver()
    if b2.button("Enregistrer et marquer reçu", disabled=not ouvert, use_container_width=True):
        sauver("Reçu")
    if b3.button("Rien à signaler", disabled=not ouvert or r.n > 0, use_container_width=True,
                 help="Le métier n'a pas de besoin supplémentaire (possible seulement sans besoin saisi)."):
        P.changer_statut(cid, metier, "Rien à signaler")
        st.session_state.cp_msg = f"{metier} : rien à signaler."
        st.rerun()
    b4.download_button("📄 Modèle Excel de ce métier", P.modele_excel(cid, metier), f"{camp['nom']} - {metier}.xlsx", use_container_width=True)

    rec = P.recap_metier(cid, metier)
    if not rec.empty:
        st.markdown("#### Ce que ce métier demande")
        cfg2 = {p: st.column_config.NumberColumn(format="%g") for p in pers}
        cfg2["Coût estimé"] = st.column_config.NumberColumn("Coût estimé sur la période", format="%.0f €")
        st.dataframe(rec, hide_index=True, use_container_width=True, column_config=cfg2)
        st.caption("Coût estimé au coût actuel des assets liés (quantité × nombre de mois de chaque période) : une indication, pas un devis. "
                   "Vide si la ressource n'est liée à aucun asset.")


# ------------------------------------------------------------------ page
def page():
    _toast()
    entete("Capacity planning", "Collecte des besoins des métiers pour une période donnée.", "📈", "Activité")
    camps = P.campagnes_df()
    if camps.empty:
        st.info("Aucune campagne. Une campagne demande aux métiers leurs besoins supplémentaires pour une période (par exemple l'année prochaine), "
                "par mois, trimestre, semestre ou année.")
        if st.button("＋ Nouvelle campagne", type="primary"):
            dlg_nouvelle()
        return
    ids = list(camps.id)
    if st.session_state.get("cp_camp") not in ids:
        st.session_state.cp_camp = ids[0]
    lib = {r.id: f"{r.nom} · {L.mois_txt_court(r.debut)} → {L.mois_txt_court(r.fin)}{' · clôturée' if r.statut != 'Ouverte' else ''}"
           for r in camps.itertuples()}
    c1, c2, c3 = st.columns([2.2, 1.6, 1])
    cid = c1.selectbox("Campagne", ids, key="cp_camp", format_func=lib.get)
    if st.session_state.get("cp_vue") not in VUES:
        st.session_state.cp_vue = VUES[0]
    with c2:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        vue = st.segmented_control("Vue", VUES, key="cp_vue", label_visibility="collapsed") or VUES[0]
    with c3:
        st.markdown("<div style='height:28px'></div>", unsafe_allow_html=True)
        if st.button("＋ Nouvelle campagne", use_container_width=True):
            dlg_nouvelle()
    camp = P.campagne(cid)
    st.divider()
    if vue == "Campagne":
        vue_campagne(camp)
    else:
        vue_saisie(camp)
