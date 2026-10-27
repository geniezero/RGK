"""Page Devis : liste, création en 3 étapes, fiche du devis, envoi (PDF enregistré + brouillon de mail), note de suivi.

Le devis est informatif : il ne crée ni ne modifie aucune affectation.
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ia_platform.ecrans import affectations as AU
from ia_platform.exports import devis_pdf
from ia_platform.core import logic as L
from ia_platform.ecrans.affectations import choix_mois, eur, mois_lbl
from ia_platform.ui.theme import entete

PAGE_AFF = None  # page Affectations (renseignée par app.py) pour « Voir dans Affectations »
ICONES = {"Brouillon": "📝", "Envoyé": "📤", "Expiré": "⌛"}
STATUTS = ["Brouillon", "Envoyé", "Expiré"]
RETOURS = {"En discussion": "💬", "Accepté": "👍", "Refusé": "👎"}

CSS = """
<style>
.dv-pill{display:inline-block;padding:2px 11px;border-radius:12px;font-size:.8rem;font-weight:700;vertical-align:middle}
.dv-Brouillon{background:#EEF1EF;color:#55625C}.dv-Envoyé{background:#E4EAF6;color:#2F4A86}.dv-Accepté{background:#DDEFE8;color:#0A4C41}
.dv-Expiré{background:#FDE3C8;color:#7A3F0E}
.dv-rt{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.8rem;font-weight:600;vertical-align:middle;margin-left:6px}
.dv-rt-Accepté{background:#DDEFE8;color:#0A4C41}.dv-rt-Refusé{background:#F8E1DF;color:#9C1C14}.dv-rt-En{background:#E4EAF6;color:#2F4A86}
.dv-steps{display:flex;gap:10px;margin:4px 0 16px}
.dv-step{flex:1;display:flex;align-items:center;gap:9px;font-size:.92rem;color:#7A8580;border-bottom:3px solid #E3E8E5;padding-bottom:8px}
.dv-step b{width:24px;height:24px;border-radius:50%;background:#E3E8E5;display:inline-flex;align-items:center;justify-content:center;font-size:.8rem;color:#55625C}
.dv-step.on{color:#0F6B5C;border-color:#0F6B5C;font-weight:700}.dv-step.on b{background:#0F6B5C;color:#fff}
.dv-step.ok{color:#2B3330;border-color:#9CC7BB}.dv-step.ok b{background:#9CC7BB;color:#fff}
.dv-tl{position:relative;padding-left:24px;margin:4px 0}.dv-tl div{position:relative;padding-bottom:12px;font-size:.93rem}
.dv-tl div:before{content:'';position:absolute;left:-19px;top:5px;width:10px;height:10px;border-radius:50%;background:#0F6B5C}
.dv-tl div.w:before{background:#fff;border:2px solid #C2702E}.dv-tl div.n:before{background:#D6DDD9}.dv-tl div.r:before{background:#9C1C14}
.dv-tl:before{content:'';position:absolute;left:9px;top:8px;bottom:16px;width:2px;background:#DCE6E2}
.dv-act{display:flex;align-items:center;gap:12px;padding:8px 12px;border:1px solid #E3E8E5;border-radius:8px;margin-bottom:6px}
.dv-ico{width:28px;height:28px;border-radius:7px;color:#fff;display:inline-flex;align-items:center;justify-content:center;font-weight:700;flex:none}
.dv-recap{background:#F4F7F5;border:1px solid #DCE6E2;border-radius:10px;padding:12px 16px}
.dv-recap div{display:flex;justify-content:space-between;margin:3px 0}
.dv-doc{background:#EEF1EF;border-radius:10px;padding:14px}
</style>"""


def pill(statut):
    return f"<span class='dv-pill dv-{statut}'>{statut}</span>"


def pill_retour(retour):
    if not isinstance(retour, str) or not retour:
        return ""
    return f"<span class='dv-rt dv-rt-{retour.split()[0]}'>{RETOURS.get(retour, '')} {retour}</span>"


def a_traiter(r):
    """Devis envoyé sans retour définitif (ni accepté ni refusé)."""
    return r["retour"] not in ("Accepté", "Refusé")


def aller(vue, did=None):
    st.session_state["dv_vue"] = vue
    if did is not None:
        st.session_state["dv_id"] = did
    for k in [k for k in st.session_state if str(k).startswith(("dvf_", "dva_", "dvr_", "dv_tab_"))]:
        del st.session_state[k]
    st.rerun()


def echeance(r, auj=None):
    auj = auj or date.today()
    s = r["statut_aff"]
    if r.get("retour") in ("Accepté", "Refusé") and r.get("retour_date"):
        return f"{r['retour'].lower()} le {L.d(r['retour_date']):%d/%m}"
    if s == "Envoyé" and r["expire_le"]:
        n = (r["expire_le"] - auj).days
        return "expire aujourd'hui" if n == 0 else f"expire dans {n} j"
    if s == "Expiré":
        return f"expiré le {r['expire_le']:%d/%m}"
    return "—"


# =============================================================================== LISTE
def liste():
    h1, h2 = st.columns([4, 1], vertical_alignment="center")
    entete("Devis", "Des documents d'information : un devis ne modifie pas les affectations. Un devis envoyé est enregistré dans "
                    "<code>data/devis</code> et un brouillon de mail est préparé avec le PDF en pièce jointe.", "🧾", "Activité", conteneur=h1)
    if h2.button("＋ Nouveau devis", type="primary", use_container_width=True):
        nouveau_formulaire()
        aller("edition")
    dl = L.devis_liste()
    auj = date.today()
    if dl.empty:
        st.info("Aucun devis pour l'instant. Cliquez sur « ＋ Nouveau devis ».")
        return
    dl["echeance"] = [echeance(r, auj) for _, r in dl.iterrows()]
    ouverts = dl[[a_traiter(r) for _, r in dl.iterrows()]]
    att = ouverts[ouverts.statut_aff == "Envoyé"]
    relance = att[[(e - auj).days <= 7 for e in att.expire_le]]
    an = L.annee()
    dec = dl[dl.retour.isin(["Accepté", "Refusé"]) & dl.retour_date.astype(str).str.startswith(str(an))]
    k = st.columns(4)
    k[0].metric("En attente de réponse", f"{len(att)} devis", help="Devis envoyés, encore valables, sans retour définitif du client")
    k[0].caption(f"{eur(att.mensuel.sum())} / mois · {eur(att.total.sum())} d'engagement")
    k[1].metric("À relancer", len(relance), help="Validité qui se termine dans 7 jours ou moins")
    k[1].caption("expire dans moins de 7 jours" if len(relance) else "rien d'urgent")
    k[2].metric("Brouillons", int((dl.statut_aff == "Brouillon").sum()))
    k[2].caption("à finaliser et envoyer")
    n_acc = int((dec.retour == "Accepté").sum())
    k[3].metric(f"Retours clients {an}", f"{n_acc / len(dec) * 100:.0f} % d'accords" if len(dec) else "—",
                help="D'après les notes de suivi saisies sur les devis envoyés")
    k[3].caption(f"{n_acc} accepté(s) · {len(dec) - n_acc} refusé(s)")

    f1, f2 = st.columns([3, 1.2], vertical_alignment="center")
    options = [f"Tous ({len(dl)})"] + [f"{ICONES[s]} {s} ({int((dl.statut_aff == s).sum())})" for s in STATUTS]
    filtre = f1.segmented_control("Statut", options, default=options[0], key="dv_filtre", label_visibility="collapsed") or options[0]
    rech = f2.text_input("Rechercher", placeholder="🔎 Client, objet, n°…", label_visibility="collapsed", key="dv_rech")
    vue = dl.copy()
    if not filtre.startswith("Tous"):
        vue = vue[vue.statut_aff == filtre.split(" ")[1]]
    if rech:
        m = rech.lower()
        vue = vue[vue.id.str.lower().str.contains(m, regex=False) | vue.client.fillna("").str.lower().str.contains(m, regex=False)
                  | vue.objet.fillna("").str.lower().str.contains(m, regex=False)]
    vue = vue.reset_index(drop=True)
    tab = pd.DataFrame({
        "N°": vue.id, "Client": vue.client, "Objet": vue.objet,
        "Début · durée": [f"{mois_lbl(x)} · {int(n)} mois" for x, n in zip(vue.debut, vue.duree)],
        "Mensuel": vue.mensuel, "Engagement": vue.total,
        "Statut": [f"{ICONES[s]} {s}" for s in vue.statut_aff],
        "Retour client": [f"{RETOURS.get(x, '')} {x}" if isinstance(x, str) and x else "—" for x in vue.retour], "Échéance": vue.echeance})
    evt = st.dataframe(tab, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
                       key=f"dv_tab_{filtre}_{rech}", height=min(38 * (len(tab) + 1) + 3, 560),
                       column_config={"Mensuel": st.column_config.NumberColumn(format="%,.0f €"),
                                      "Engagement": st.column_config.NumberColumn(format="%,.0f €"),
                                      "Objet": st.column_config.TextColumn(width="small"),
                                      "Client": st.column_config.TextColumn(width="small"),
                                      "Retour client": st.column_config.TextColumn(width="small")})
    st.caption("Cliquez sur un devis pour ouvrir sa fiche : document, envoi par mail et note de suivi.")
    rows = evt.selection.rows if evt and evt.selection else []
    if rows:
        aller("fiche", vue.id.iloc[rows[0]])


# =============================================================================== ÉDITION (3 étapes)
def nouveau_formulaire(dv=None, lignes=None):
    if dv is None:
        cli = L.q("SELECT id FROM clients WHERE statut <> 'Inactif' ORDER BY nom")
        st.session_state["dv_form"] = dict(id=None, client_id=cli.id.iloc[0] if len(cli) else None, objet="", date_devis=date.today(),
                                           debut=L.ajouter_mois(date(L.annee(), L.mois_ref(), 1), 1), duree=12, validite=30,
                                           commentaire="", lignes=[], etape=1)
    else:
        st.session_state["dv_form"] = dict(id=dv.id, client_id=dv.client_id, objet=dv.objet or "", date_devis=L.d(dv.date_devis),
                                           debut=L.d(dv.debut), duree=int(dv.duree), validite=int(dv.validite or 30),
                                           commentaire=dv.commentaire or "", etape=1,
                                           lignes=[dict(code=r.code, element=r.element, libelle=L.libelle_code(r.code), qte=float(r.qte),
                                                        remplace=r.remplace, retraits=dict(r.retraits or {})) for r in lignes.itertuples()])


def prix_ligne(l_, debut):
    """Montant mensuel d'une ligne de devis (offre personnalisée : moins le coût des composants retirés)."""
    return (L.tarif(l_["code"], debut) - L.cout_retraits(l_["code"], l_.get("retraits") or {}, debut)) * float(l_["qte"])


def personnaliser_ligne_devis(l_, i, debut):
    """Contenu du menu ⚙️ d'une ligne d'offre : quantité gardée de chaque composant retirable."""
    comp = L.composition_au(l_["code"], debut)
    ret = L.retirables(l_["code"])
    noms = L.q("SELECT id, nom FROM assets").set_index("id").nom
    st.markdown(f"**Personnaliser {l_['libelle']}**")
    st.caption("Quantité gardée de chaque composant retirable (le socle 🔒 ne change pas).")
    rt = dict(l_.get("retraits") or {})
    for r in comp.itertuples():
        if r.asset_id not in ret:
            st.markdown(f"<span style='color:#9AA6A0'>🔒 {noms.get(r.asset_id, r.asset_id)} × {r.qte:g}</span>", unsafe_allow_html=True)
            continue
        garde = st.number_input(f"{noms.get(r.asset_id, r.asset_id)} (sur {r.qte:g})", min_value=0.0, max_value=float(r.qte), step=1.0, format="%g",
                                value=float(r.qte) - min(rt.get(r.asset_id, 0.0), float(r.qte)), key=f"dvf_ps_{i}_{l_['code']}_{r.asset_id}")
        if float(r.qte) - garde > 0:
            rt[r.asset_id] = float(r.qte) - garde
        else:
            rt.pop(r.asset_id, None)
    if rt != (l_.get("retraits") or {}):
        l_["retraits"] = rt
        st.rerun()
    st.caption(f"Prix : {eur(prix_ligne(l_, debut))} / mois" + (f" au lieu de {eur(L.tarif(l_['code'], debut) * float(l_['qte']))}" if rt else ""))


def stepper(etape):
    noms = ["Client et période", "Contenu", "Conditions et aperçu"]
    h = "".join(f"<div class='dv-step {'on' if i + 1 == etape else 'ok' if i + 1 < etape else ''}'><b>{'✓' if i + 1 < etape else i + 1}</b>{n}</div>"
                for i, n in enumerate(noms))
    st.markdown(f"<div class='dv-steps'>{h}</div>", unsafe_allow_html=True)


def sauver(f, statut="Brouillon"):
    if not f["client_id"]:
        raise ValueError("Choisissez un client.")
    if not f["lignes"]:
        raise ValueError("Ajoutez au moins une offre ou une option.")
    rem = [l_["remplace"] for l_ in f["lignes"] if l_["remplace"]]
    if len(rem) != len(set(rem)):
        raise ValueError("Une même ligne actuelle est remplacée deux fois.")
    f["id"] = L.enregistrer_devis(f["id"], f["date_devis"], f["client_id"], f["debut"], f["duree"], f["validite"], statut,
                                  f["objet"], f["commentaire"], [(l_["code"], l_["qte"], l_["remplace"], l_.get("retraits") or {}) for l_ in f["lignes"]])
    return f["id"]


def edition():
    f = st.session_state.get("dv_form")
    if not f:
        aller("liste")
    clients = L.q("SELECT * FROM clients ORDER BY nom")
    h1, h2, h3 = st.columns([3, 1, 1.2], vertical_alignment="center")
    h1.title(f"Modifier {f['id']}" if f["id"] else "Nouveau devis")
    if h2.button("← Annuler", use_container_width=True, key="dvf_annuler"):
        aller("fiche" if f["id"] else "liste", f["id"])
    if h3.button("💾 Enregistrer le brouillon", use_container_width=True, key="dvf_save_top"):
        try:
            did = sauver(f)
            st.session_state["dv_msg"] = f"Brouillon {did} enregistré."
            aller("fiche", did)
        except ValueError as e:
            st.error(str(e))
    stepper(f["etape"])
    ouvertes = L.lignes_ouvertes_au(f["client_id"], f["debut"]) if f["client_id"] else pd.DataFrame()
    cout_actuel = float(ouvertes.cout.sum()) if len(ouvertes) else 0.0

    if f["etape"] == 1:
        c1, c2 = st.columns([2, 1])
        ids = clients.id.tolist()
        f["client_id"] = c1.selectbox("Client", ids, index=ids.index(f["client_id"]) if f["client_id"] in ids else 0, key="dvf_cli",
                                      format_func=lambda x: f"{clients.set_index('id').nom[x]} · {clients.set_index('id').entite[x]} · {clients.set_index('id').pays[x]}")
        f["objet"] = c2.text_input("Objet", f["objet"], key="dvf_objet", placeholder="ex. Passage en production")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            f["debut"] = choix_mois("Début", f["debut"], "dvf_debut")
        f["duree"] = c2.number_input("Durée (mois)", min_value=1, max_value=60, value=int(f["duree"]), key="dvf_duree")
        f["date_devis"] = c3.date_input("Date du devis", f["date_devis"], format="DD/MM/YYYY", key="dvf_date")
        f["validite"] = c4.number_input("Validité (jours)", min_value=1, value=int(f["validite"]), key="dvf_valid")
        fin = L.ajouter_mois(f["debut"], int(f["duree"]) - 1)
        st.caption(f"Période : {mois_lbl(f['debut'])} → {mois_lbl(fin)} · valable jusqu'au {f['date_devis'] + timedelta(days=int(f['validite'])):%d/%m/%Y}")
        ouvertes = L.lignes_ouvertes_au(f["client_id"], f["debut"])
        with st.container(border=True):
            st.markdown(f"**Solution actuelle du client en {mois_lbl(f['debut'])}**")
            if ouvertes.empty:
                st.caption("Aucune offre ni option : ce devis sera une première souscription.")
            else:
                for r in ouvertes.itertuples():
                    st.markdown(f"- {r.element} **{L.libelle_affectation(r.id)}** · depuis {mois_lbl(r.debut)} · {eur(r.cout)} / mois")
                st.caption(f"Total : {eur(ouvertes.cout.sum())} / mois. À l'étape suivante, chaque ligne du devis pourra en remplacer une.")
        b1, _, b3 = st.columns([1, 2, 1.3])
        if b3.button("Suivant : contenu →", type="primary", use_container_width=True, key="dvf_n1"):
            ouv = set(ouvertes.id) if len(ouvertes) else set()
            for l_ in f["lignes"]:
                if l_["remplace"] not in ouv:
                    l_["remplace"] = None
            f["etape"] = 2
            st.rerun()

    elif f["etape"] == 2:
        nom = clients.set_index("id").nom[f["client_id"]]
        resume = " + ".join(L.libelle_affectation(i) for i in ouvertes.id) if len(ouvertes) else "aucune"
        st.markdown(f"<div class='dv-recap' style='display:flex;gap:24px;flex-wrap:wrap'><span><b>{nom}</b></span>"
                    f"<span>Solution actuelle : <b>{resume}</b> · {eur(cout_actuel)} / mois</span>"
                    f"<span style='margin-left:auto'>Période : <b>{mois_lbl(f['debut'])} → {mois_lbl(L.ajouter_mois(f['debut'], int(f['duree']) - 1))}</b> · {int(f['duree'])} mois</span></div>",
                    unsafe_allow_html=True)
        st.write("")
        cat = L.catalogue_df()
        g, dr = st.columns([1.05, 1], gap="large")
        with g:
            types = ["Offres"] + [t for t in L.liste("type") if t in set(cat.type)]
            onglet = st.segmented_control("Catalogue", types, default="Offres", key="dvf_onglet", label_visibility="collapsed") or "Offres"
            sel = cat[cat.element == "Offre"] if onglet == "Offres" else cat[(cat.element == "Option") & (cat.type == onglet)]
            dans = {l_["code"] for l_ in f["lignes"]}
            with st.container(height=470, border=False):
                for r in sel.itertuples():
                    with st.container(border=True):
                        a, b, c = st.columns([5, 2, 2], vertical_alignment="center")
                        a.markdown(f"**{r.libelle}**  \n<span class='aff-sub'>{r.code}{(' · ' + r.detail) if r.detail else ''}</span>", unsafe_allow_html=True)
                        b.markdown(f"<div class='aff-prix'>{eur(L.tarif(r.code, f['debut']))}<small>/ mois</small></div>", unsafe_allow_html=True)
                        if r.code in dans:
                            c.button("✓ Ajouté", key=f"dvf_add_{r.code}", disabled=True, use_container_width=True)
                        elif c.button("＋ Ajouter", key=f"dvf_add_{r.code}", use_container_width=True):
                            f["lignes"].append(dict(code=r.code, element=r.element, libelle=r.libelle, qte=1.0, remplace=None, retraits={}))
                            st.rerun()
        with dr:
            st.markdown(f"**Lignes du devis · {len(f['lignes'])}** <span class='aff-sub'>· tarifs de {mois_lbl(f['debut'])}</span>", unsafe_allow_html=True)
            if not f["lignes"]:
                st.info("Ajoutez des offres ou des options depuis le catalogue.")
            choix_rem = [None] + (ouvertes.id.tolist() if len(ouvertes) else [])
            lib_rem = {i: L.libelle_affectation(i) for i in choix_rem if i}
            for i, l_ in enumerate(list(f["lignes"])):
                with st.container(border=True):
                    a, p_, b = st.columns([5, 1.6, .7], vertical_alignment="center")
                    badge = "aff-offre" if l_["element"] == "Offre" else "aff-option"
                    rt = l_.get("retraits") or {}
                    a.markdown(f"<span class='aff-badge {badge}'>{l_['element'].upper()}</span>"
                               + ("<span class='aff-badge aff-fin'>PERSONNALISÉE</span>" if rt else "")
                               + f"<b>{l_['libelle']}</b> <span class='aff-sub'>· {eur(prix_ligne(l_, f['debut']))} / mois</span>"
                               + (f"<br><span class='aff-sub'>retiré : {L.texte_retraits(rt)}</span>" if rt else ""), unsafe_allow_html=True)
                    if l_["element"] == "Offre" and L.retirables(l_["code"]):
                        with p_.popover("⚙️", help="Personnaliser : le client garde moins de certains composants retirables"):
                            personnaliser_ligne_devis(l_, i, f["debut"])
                    if b.button("✕", key=f"dvf_del_{i}_{l_['code']}", help="Retirer"):
                        f["lignes"].pop(i)
                        st.rerun()
                    c1, c2 = st.columns([1, 2.4])
                    l_["qte"] = c1.number_input("Qté", min_value=1.0, step=1.0, format="%g", value=float(l_["qte"]), key=f"dvf_q_{i}_{l_['code']}")
                    idx = choix_rem.index(l_["remplace"]) if l_["remplace"] in choix_rem else 0
                    l_["remplace"] = c2.selectbox("Par rapport à la solution actuelle", choix_rem, index=idx, key=f"dvf_r_{i}_{l_['code']}",
                                                  format_func=lambda x: "＋ en plus" if x is None else f"⇄ remplace {lib_rem[x]}",
                                                  disabled=len(choix_rem) == 1)
            mensuel = sum(prix_ligne(l_, f["debut"]) for l_ in f["lignes"])
            rempl = float(ouvertes[ouvertes.id.isin([l_["remplace"] for l_ in f["lignes"]])].cout.sum()) if len(ouvertes) else 0.0
            st.markdown(f"<div class='dv-recap'><div><span>Montant mensuel du devis</span><b style='font-size:1.15rem'>{eur(mensuel)}</b></div>"
                        f"<div><span>Engagement {int(f['duree'])} mois</span><b>{eur(mensuel * int(f['duree']))}</b></div>"
                        f"<div style='border-top:1px solid #DCE6E2;padding-top:6px'><span>Coût mensuel du client</span>"
                        f"<span>{eur(cout_actuel)} → <b style='color:#0F6B5C'>{eur(cout_actuel - rempl + mensuel)}</b></span></div></div>",
                        unsafe_allow_html=True)
        b1, _, b3 = st.columns([1, 2, 1.3])
        if b1.button("← Client et période", use_container_width=True, key="dvf_p2"):
            f["etape"] = 1
            st.rerun()
        if b3.button("Suivant : conditions et aperçu →", type="primary", use_container_width=True, key="dvf_n2"):
            try:
                sauver(f)
                f["etape"] = 3
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    else:
        g, dr = st.columns([1, 1.1], gap="large")
        with g:
            f["objet"] = st.text_input("Objet", f["objet"], key="dvf_objet3")
            f["commentaire"] = st.text_area("Remarques (imprimées sur le devis)", f["commentaire"], height=110, key="dvf_comm")
            c1, c2 = st.columns(2)
            f["validite"] = c1.number_input("Validité (jours)", min_value=1, value=int(f["validite"]), key="dvf_valid3")
            c2.markdown(f"<br>valable jusqu'au **{f['date_devis'] + timedelta(days=int(f['validite'])):%d/%m/%Y}**", unsafe_allow_html=True)
            det = L.devis_detail([(l_["code"], l_["qte"], l_.get("retraits") or {}) for l_ in f["lignes"]], f["debut"])
            tot = L.devis_totaux(det, f["debut"], f["duree"])
            st.markdown(f"<div class='dv-recap'><div><span>Montant mensuel</span><b>{eur(tot['mensuel'])}</b></div>"
                        f"<div><span>Engagement {int(f['duree'])} mois</span><b>{eur(tot['total'])}</b></div>"
                        f"<div><span>Période</span><span>{mois_lbl(f['debut'])} → {mois_lbl(tot['fin'])}</span></div></div>", unsafe_allow_html=True)
            st.write("")
            if st.button("🔄 Mettre à jour l'aperçu", key="dvf_apercu"):
                sauver(f)
                st.rerun()
        with dr:
            if f["id"]:
                with st.container(border=True):
                    st.image(devis_pdf.devis_png(f["id"], 1.3), use_container_width=True)
        b1, _, b3, b4 = st.columns([1, 1.2, 1.2, 1.4])
        if b1.button("← Contenu", use_container_width=True, key="dvf_p3"):
            f["etape"] = 2
            st.rerun()
        if b3.button("💾 Enregistrer le brouillon", use_container_width=True, key="dvf_save3"):
            did = sauver(f)
            st.session_state["dv_msg"] = f"Brouillon {did} enregistré."
            aller("fiche", did)
        if b4.button("📤 Enregistrer et envoyer", type="primary", use_container_width=True, key="dvf_send"):
            did = sauver(f)
            envoyer(did)


# =============================================================================== ENVOI
def envoyer(did):
    """Passe en « Envoyé », enregistre le PDF dans data/devis/<année>/ ; le brouillon de mail se télécharge depuis la fiche."""
    dv = L.q("SELECT d.*, c.email FROM devis d LEFT JOIN clients c ON c.id=d.client_id WHERE d.id=?", (did,)).iloc[0]
    # le PDF est produit avec le statut « Envoyé » (sans filigrane BROUILLON)
    L.run("UPDATE devis SET statut='Envoyé' WHERE id=?", (did,))
    chemin = L.envoyer_devis(did, devis_pdf.devis_pdf(did))
    st.session_state["dv_envoye"] = did
    st.session_state["dv_msg"] = (f"Devis {did} envoyé : PDF enregistré dans data/{chemin.relative_to(L.DEVIS_DIR.parent).as_posix()}. "
                                  "Téléchargez maintenant le brouillon de mail (bouton « ✉️ Brouillon de mail »), ouvrez-le et cliquez sur Envoyer."
                                  + ("" if dv.email else " ⚠️ Le client n'a pas d'e-mail : ajoutez le destinataire dans le mail."))
    aller("fiche", did)


@st.dialog("Note de suivi")
def dlg_retour(did):
    dv = L.q("SELECT * FROM devis WHERE id=?", (did,)).iloc[0]
    opts = list(RETOURS)
    val = st.segmented_control("Retour du client", opts, default=dv.retour if dv.retour in opts else opts[0], key="dvr_ret",
                               format_func=lambda x: f"{RETOURS[x]} {x}") or opts[0]
    c1, c2 = st.columns([1, 2])
    quand = c1.date_input("Date", L.d(dv.retour_date) or date.today(), format="DD/MM/YYYY", key="dvr_date")
    note = c2.text_input("Note", dv.retour_note or "", placeholder="ex. BC-2026-118, budget non disponible, relancer le 15/11…", key="dvr_note")
    st.caption("Information seulement : aucune affectation n'est créée ni modifiée. Pour mettre en place l'offre, passez par Affectations.")
    if st.button("Enregistrer la note", type="primary", key="dvr_ok"):
        L.noter_retour(did, val, quand, note)
        st.session_state["dv_msg"] = f"Note de suivi enregistrée : {val}."
        aller("fiche", did)


# =============================================================================== FICHE
def timeline(did, statut, expire_le, retour=None):
    h = L.historique_devis(did)
    items = []
    for r in h.itertuples():
        dt = L.d(str(r.date)[:10])
        cls = "r" if "Refusé" in str(r.evenement) else ""
        items.append(f"<div class='{cls}'>{r.evenement}{(' · ' + str(r.detail)) if r.detail else ''} <span class='aff-sub'>· {dt:%d/%m/%Y}</span></div>")
    if statut == "Brouillon":
        items.append("<div class='n' style='color:#7A8580'>À envoyer au client</div>")
    elif retour in ("Accepté", "Refusé"):
        pass
    elif statut == "Envoyé":
        relance = expire_le - timedelta(days=7)
        items.append(f"<div class='w'><b>En attente de réponse</b> <span class='aff-sub'>· relance conseillée le {relance:%d/%m}</span></div>")
        items.append("<div class='n' style='color:#7A8580;padding-bottom:0'>Retour du client (note de suivi)</div>")
    elif statut == "Expiré":
        items.append(f"<div class='w'><b>Expiré le {expire_le:%d/%m/%Y}</b> <span class='aff-sub'>· faites une nouvelle version pour prolonger</span></div>")
    st.markdown(f"<div class='dv-tl'>{''.join(items)}</div>", unsafe_allow_html=True)


def effet_client(did):
    """Effet du devis pour le client s'il le signe : information seulement."""
    try:
        plan = L.plan_acceptation(did)
    except Exception as e:  # le calcul ne doit jamais bloquer l'affichage
        st.caption(f"Effet non calculable : {e}")
        return
    with st.container(border=True):
        e1, e2, e3 = st.columns([1.2, 1, 1.4])
        e1.markdown(f"<span class='aff-sub'>Coût mensuel ({mois_lbl(plan['debut'])})</span><br>"
                    f"<span style='font-size:1.15rem'>{eur(plan['avant'])} → <b style='color:#0F6B5C'>{eur(plan['apres'])}</b></span>",
                    unsafe_allow_html=True)
        e2.markdown(f"<span class='aff-sub'>Budget {plan['annee']}</span><br><b style='font-size:1.15rem'>"
                    f"{eur(plan['budget']) if plan['budget'] else '—'}</b>", unsafe_allow_html=True)
        pct = plan["prevision"] / plan["budget"] if plan["budget"] else None
        coul = "#9C1C14" if pct and pct > 1 else "#0F6B5C"
        e3.markdown(f"<span class='aff-sub'>Prévision {plan['annee']} avec ce devis</span><br><b style='font-size:1.15rem;color:{coul}'>"
                    f"{eur(plan['prevision'])}{f' · {pct * 100:.0f} %' if pct else ''}</b>", unsafe_allow_html=True)
        if pct:
            e3.progress(min(pct, 1.0))
        if plan["arrets"]:
            st.caption("Remplacements prévus : " + " ; ".join(f"{a['libelle']} → {a['par']}" for a in plan["arrets"]))
        st.caption("Information : rien n'est modifié dans Affectations.")


def fiche(did):
    dl = L.devis_liste()
    if did not in set(dl.id):
        aller("liste")
    r = dl.set_index("id").loc[did]
    dv = L.q("SELECT d.*, c.email FROM devis d LEFT JOIN clients c ON c.id=d.client_id WHERE d.id=?", (did,)).iloc[0]
    statut = r.statut_aff
    version = int(dv.version or 1)
    if st.button("← Tous les devis", key="dv_back"):
        aller("liste")
    h1, h2 = st.columns([2.2, 1.8], vertical_alignment="bottom")
    h1.markdown(f"<div style='font-size:1.75rem;font-weight:700;line-height:1.2'>{did} · {dv.objet or 'Sans objet'} {pill(statut)}{pill_retour(dv.retour)}</div>"
                f"<div class='aff-sub' style='font-size:.95rem'>{r.client} · {r.entite} · {r.pays} · version {version}</div>", unsafe_allow_html=True)
    # le PDF envoyé est celui enregistré ; un brouillon est régénéré à chaque affichage
    pdf = (L.pdf_version(did, version) if statut != "Brouillon" else None) or devis_pdf.devis_pdf(did)
    png = devis_pdf.devis_png(did, 1.5)
    b = h2.columns([1, 1.15, .85, .95])
    if b[0].button("✏️ Modifier", use_container_width=True, disabled=statut != "Brouillon",
                   help="Seul un brouillon se modifie. Sinon, faites une nouvelle version."):
        nouveau_formulaire(dv, L.devis_lignes_df(did))
        aller("edition")
    if b[1].button("📋 Dupliquer", use_container_width=True):
        lg = L.devis_lignes_df(did)
        nid = L.enregistrer_devis(None, date.today(), dv.client_id, dv.debut, dv.duree, dv.validite, "Brouillon", dv.objet, dv.commentaire,
                                  [(x.code, x.qte, x.remplace, x.retraits) for x in lg.itertuples()])
        st.session_state["dv_msg"] = f"Copie créée : {nid} (brouillon)."
        aller("fiche", nid)
    b[2].download_button("⬇️ PDF", pdf, L.chemin_devis(did, version).name, "application/pdf", use_container_width=True, on_click="ignore")
    b[3].download_button("🖼️ Image", png, f"Devis_{did}_v{version}.png", "image/png", use_container_width=True, on_click="ignore")

    g, dr = st.columns([1.05, 1.2], gap="large")
    with g:
        with st.container(border=True):
            st.image(png, use_container_width=True)
        vers = L.versions_devis(did)
        anciennes = vers[vers.version < version] if len(vers) else vers
        if len(anciennes):
            with st.expander(f"Versions précédentes · {len(anciennes)}"):
                for v in anciennes.itertuples():
                    st.download_button(f"⬇️ Version {v.version} · {L.d(v.date):%d/%m/%Y}", L.pdf_version(did, v.version),
                                       L.chemin_devis(did, v.version).name, "application/pdf", key=f"dv_v_{v.version}", on_click="ignore")
    with dr:
        k = st.columns(3)
        k[0].metric("Montant mensuel", eur(r.mensuel))
        k[0].caption(f"{len(L.devis_lignes_df(did))} ligne(s)")
        k[1].metric("Engagement", eur(r.total))
        k[1].caption(f"{mois_lbl(r.debut)} → {mois_lbl(r.fin)}")
        jours = (r.expire_le - date.today()).days
        if dv.retour in ("Accepté", "Refusé"):
            k[2].metric("Retour client", f"{RETOURS[dv.retour]} {dv.retour}")
            k[2].caption(f"le {L.d(dv.retour_date):%d/%m/%Y}" if dv.retour_date else "")
        elif statut == "Expiré":
            k[2].metric("Validité", "dépassée")
            k[2].caption(f"depuis le {r.expire_le:%d/%m/%Y}")
        else:
            k[2].metric("Validité", f"{jours} jour{'s' if abs(jours) > 1 else ''}")
            k[2].caption(f"jusqu'au {r.expire_le:%d/%m/%Y}")

        if statut == "Brouillon":
            st.markdown("##### Envoyer")
            with st.container(border=True):
                st.markdown(f"Le PDF sera enregistré dans <code>data/{L.chemin_devis(did, version).relative_to(L.DEVIS_DIR.parent).as_posix()}</code>, "
                            "puis un **brouillon de mail** avec le PDF en pièce jointe sera prêt à ouvrir.", unsafe_allow_html=True)
                if not dv.email:
                    st.warning("Ce client n'a pas d'adresse e-mail (fiche Clients) : il faudra saisir le destinataire dans le mail.")
                c1, c2 = st.columns([1.3, 1])
                if c1.button("📤 Envoyer le devis", type="primary", use_container_width=True):
                    envoyer(did)
                if c2.button("🗑️ Supprimer le brouillon", use_container_width=True):
                    L.supprimer_devis(did)
                    st.session_state["dv_msg"] = f"Brouillon {did} supprimé."
                    aller("liste")
        else:
            st.markdown("##### Envoi")
            with st.container(border=True):
                frais = st.session_state.get("dv_envoye") == did
                eml = L.brouillon_mail(did, pdf)
                c1, c2 = st.columns([1.3, 1])
                c1.download_button("✉️ Brouillon de mail (.eml)", eml, f"Devis_{did}_v{version}.eml", "message/rfc822",
                                   type="primary" if frais else "secondary", use_container_width=True, on_click="ignore",
                                   help="Ouvrez le fichier : Outlook, Apple Mail ou Thunderbird affiche le mail prêt à envoyer, avec le PDF joint.")
                if c2.button("↻ Nouvelle version", use_container_width=True,
                             help="Repasse le devis en brouillon (version suivante) ; la version envoyée reste enregistrée."):
                    v = L.nouvelle_version(did, pdf)
                    st.session_state["dv_msg"] = f"Version {v} créée en brouillon : modifiez-la puis renvoyez-la."
                    aller("fiche", did)
                envoye = L.d(dv.date_envoi)
                st.caption((f"Envoyé le {envoye:%d/%m/%Y} · " if envoye else "")
                           + (f"PDF enregistré : data/{dv.fichier}" if isinstance(dv.fichier, str) and dv.fichier else "PDF conservé dans l'application")
                           + (f" · destinataire : {dv.email}" if dv.email else " · aucun e-mail client : ajoutez le destinataire dans le mail"))

            st.markdown("##### Note de suivi")
            with st.container(border=True):
                if dv.retour:
                    st.markdown(f"{pill_retour(dv.retour)} <span class='aff-sub'>· {L.d(dv.retour_date):%d/%m/%Y}</span>"
                                + (f"<br>{dv.retour_note}" if dv.retour_note else ""), unsafe_allow_html=True)
                else:
                    st.caption("Aucun retour noté pour l'instant.")
                c1, c2, c3 = st.columns(3)
                if c1.button("✍️ Noter le retour", use_container_width=True, help="Retour du client : en discussion, accepté ou refusé"):
                    dlg_retour(did)
                if dv.retour and c2.button("Effacer la note", use_container_width=True):
                    L.effacer_retour(did)
                    st.session_state["dv_msg"] = "Note de suivi effacée."
                    aller("fiche", did)
                if PAGE_AFF is not None and c3.button("🔁 Affectations", use_container_width=True,
                                                      help="Pour mettre en place l'offre : les affectations se saisissent à la main."):
                    st.session_state["aff_goto"] = dv.client_id
                    st.switch_page(PAGE_AFF)

        st.markdown("##### Suivi")
        with st.container(border=True):
            timeline(did, statut, r.expire_le, dv.retour)
        st.markdown("##### Effet pour le client s'il signe")
        effet_client(did)


# =============================================================================== PAGE
def page():
    st.markdown(AU.CSS + CSS, unsafe_allow_html=True)
    if "dv_msg" in st.session_state:
        st.success(st.session_state.pop("dv_msg"))
    vue = st.session_state.get("dv_vue", "liste")
    if L.est_cloture() and vue == "edition":
        vue = "liste"
    if vue == "edition":
        edition()
    elif vue == "fiche" and st.session_state.get("dv_id"):
        fiche(st.session_state["dv_id"])
    else:
        liste()
