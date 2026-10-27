"""Page Affectations : liste des clients, fiche client, ajout (panier), remplacement, arrêt, modification."""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.ui.theme import entete

TEAL = "#0F6B5C"
COULEURS = ["#0F6B5C", "#2E8B74", "#4C9C8A", "#9CC7BB", "#C2702E", "#E3A66F", "#3A5BA0", "#7A8580"]
MOTIFS = ["Fin du projet", "Le client n'en a plus besoin", "Budget", "Migration vers une autre offre", "Autre"]
SANS_FIN = "sans fin"

CSS = """
<style>
.aff-badge{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.04em;padding:1px 8px;border-radius:10px;margin-right:6px}
.aff-offre{background:#DDEFE8;color:#0A4C41}.aff-option{background:#EEF3F1;color:#2E6B5C}
.aff-avenir{background:#E4EAF6;color:#2F4A86}.aff-fin{background:#FDE3C8;color:#7A3F0E}
.aff-nom{font-weight:700;font-size:1.02rem}.aff-sub{color:#6B7772;font-size:.83rem}
.aff-prix{font-weight:700;font-size:1.05rem;text-align:right}.aff-prix small{display:block;font-weight:400;color:#6B7772;font-size:.75rem}
.aff-dates{font-size:.88rem;line-height:1.35}.aff-dates b{font-weight:700}
</style>"""


def eur(v, dec=0):
    return f"{v:,.{dec}f} €".replace(",", " ").replace(".", ",")


def mois_lbl(x):
    x = L.d(x)
    return SANS_FIN if x is None else f"{L.MOIS[x.month - 1].lower()} {x.year}"


def mois_options(depuis=None, n=36):
    """Liste de premiers du mois à partir de janvier de l'exercice (ou d'une date)."""
    dep = L.mois_debut(depuis) if depuis else date(L.annee(), 1, 1)
    return [L.ajouter_mois(dep, i) for i in range(n)]


def choix_mois(label, valeur, key, avec_sans_fin=False, depuis=None, disabled=False):
    opts = mois_options(depuis)
    valeur = L.d(valeur)
    if valeur is not None and L.mois_debut(valeur) not in opts:
        opts = sorted(set(opts) | {L.mois_debut(valeur)})
    if avec_sans_fin:
        opts = [None] + opts
    idx = opts.index(L.mois_debut(valeur) if valeur else None) if (valeur is None and avec_sans_fin) or (valeur and L.mois_debut(valeur) in opts) else 0
    return st.selectbox(label, opts, index=idx, key=key, format_func=mois_lbl, disabled=disabled)


def mois_suivant_ref():
    return L.ajouter_mois(date(L.annee(), L.mois_ref(), 1), 1)


def _rafraichir():
    for k in [k for k in st.session_state if str(k).startswith(("pan_", "rp_", "ar_", "md_", "ps_"))]:
        del st.session_state[k]
    st.session_state.pop("panier", None)
    st.rerun()


# ----------------------------------------------------------------------------- données
def _resume_clients():
    lm = L.lignes_mensuelles()
    cli = L.q("SELECT * FROM clients ORDER BY nom")
    ref = date(L.annee(), L.mois_ref(), 1)
    l_ = lm[lm.element.isin(["Offre", "Option"])].copy() if len(lm) else lm.iloc[0:0].copy()
    en_cours = pd.Series([(L.d(f) is None or L.d(f) >= ref) and L.d(d_) <= ref for d_, f in zip(l_.debut, l_.fin)], index=l_.index, dtype=bool)
    act = l_[en_cours]
    def resume(g):
        o = g[g.element == "Offre"]
        n_o, n_p = len(o), int((g.element == "Option").sum())
        txt = (o.libelle.iloc[0] if n_o == 1 else f"{n_o} offres") if n_o else "options seules"
        return txt + (f" + {n_p} option{'s' if n_p > 1 else ''}" if n_p else "")
    res = act.groupby("client_id").apply(resume, include_groups=False) if len(act) else pd.Series(dtype=str)
    cout = act.groupby("client_id").cout_ref.sum() if len(act) else pd.Series(dtype=float)
    cli["offre"] = cli.id.map(res).fillna("aucune offre")
    cli["cout"] = cli.id.map(cout).fillna(0.0)
    cli["avec"] = cli.id.isin(act.client_id)
    return cli


# ----------------------------------------------------------------------------- dialogues
@st.dialog("Ajouter des offres et des options", width="large")
def dlg_ajouter(cid, nom, cout_actuel):
    st.markdown(f"**{nom}** — choisissez une ou plusieurs offres et options, puis datez chaque ligne.")
    cat = L.catalogue_df()
    panier = st.session_state.setdefault("panier", [])
    gauche, droite = st.columns([1.05, 1], gap="large")
    with gauche:
        types = ["Offres"] + [t for t in L.liste("type") if t in set(cat.type)]
        onglet = st.segmented_control("Catalogue", types, default="Offres", key="pan_onglet", label_visibility="collapsed") or "Offres"
        sel = cat[cat.element == "Offre"] if onglet == "Offres" else cat[(cat.element == "Option") & (cat.type == onglet)]
        dans = {p["code"] for p in panier}
        with st.container(height=430, border=False):
            for r in sel.itertuples():
                with st.container(border=True):
                    a, b, c = st.columns([5, 2, 2], vertical_alignment="center")
                    a.markdown(f"**{r.libelle}**  \n<span class='aff-sub'>{r.code}{(' · ' + r.detail) if r.detail else ''}</span>", unsafe_allow_html=True)
                    b.markdown(f"<div class='aff-prix'>{eur(r.cout)}<small>/ mois</small></div>", unsafe_allow_html=True)
                    if r.code in dans:
                        c.button("✓ Ajouté", key=f"pan_add_{r.code}", disabled=True, use_container_width=True)
                    elif c.button("＋ Ajouter", key=f"pan_add_{r.code}", use_container_width=True):
                        panier.append(dict(element=r.element, code=r.code, libelle=r.libelle, qte=1.0, debut=mois_suivant_ref(), fin=None))
                        st.rerun(scope="fragment")
    with droite:
        st.markdown(f"**Panier · {len(panier)} ligne{'s' if len(panier) > 1 else ''}**")
        if not panier:
            st.info("Ajoutez des offres ou des options depuis le catalogue (changez d'onglet pour les options).")
        else:
            with st.expander("📅 Même période pour toutes les lignes"):
                c1, c2 = st.columns(2)
                with c1:
                    gd = choix_mois("Du", mois_suivant_ref(), "pan_gdeb")
                with c2:
                    gf = choix_mois("Au", None, "pan_gfin", avec_sans_fin=True)
                if st.button("Appliquer à tout le panier", key="pan_gapp"):
                    for i, p in enumerate(panier):
                        p["debut"], p["fin"] = gd, gf
                        st.session_state.pop(f"pan_deb_{i}_{p['code']}", None)
                        st.session_state.pop(f"pan_fin_{i}_{p['code']}", None)
                    st.rerun(scope="fragment")
            with st.container(height=330, border=False):
                for i, p in enumerate(list(panier)):
                    with st.container(border=True):
                        h1, h2 = st.columns([6, 1], vertical_alignment="center")
                        badge = "aff-offre" if p["element"] == "Offre" else "aff-option"
                        h1.markdown(f"<span class='aff-badge {badge}'>{p['element'].upper()}</span><b>{p['libelle']}</b> "
                                    f"<span class='aff-sub'>· {eur(L.tarif(p['code'], p['debut']) * p['qte'])} / mois</span>", unsafe_allow_html=True)
                        if h2.button("✕", key=f"pan_del_{i}_{p['code']}", help="Retirer du panier"):
                            panier.pop(i)
                            st.rerun(scope="fragment")
                        c1, c2, c3 = st.columns([1, 1.3, 1.3])
                        p["qte"] = c1.number_input("Qté", min_value=1.0, step=1.0, format="%g", value=float(p["qte"]), key=f"pan_q_{i}_{p['code']}")
                        with c2:
                            p["debut"] = choix_mois("Du", p["debut"], f"pan_deb_{i}_{p['code']}")
                        with c3:
                            p["fin"] = choix_mois("Au", p["fin"], f"pan_fin_{i}_{p['code']}", avec_sans_fin=True, depuis=p["debut"])
            # capacité des instances cloud et parts concernées par le panier
            besoins = {}
            for p in panier:
                if p["element"] == "Option":
                    besoins[(p["code"], p["debut"])] = besoins.get((p["code"], p["debut"]), 0) + p["qte"]
                else:
                    for x in L.composition_au(p["code"], p["debut"]).itertuples():
                        besoins[(x.asset_id, p["debut"])] = besoins.get((x.asset_id, p["debut"]), 0) + x.qte * p["qte"]
            for (aid, deb), u in besoins.items():
                cap = L.capacite_geree(aid)
                if cap is None:
                    continue
                deja = float(L.allocations(aid, deb).unites.sum())
                nom_a = L.libelle_code(aid)
                taux = (deja + u) / cap if cap else 9
                txt = f"**{nom_a}** en {mois_lbl(deb)} : {deja:g} déjà alloués + {u:g} = **{deja + u:g} / {cap:g}**"
                if taux > 1:
                    st.error(txt + " — parc plein : ajoutez une instance dans Assets ou réduisez la quantité.")
                else:
                    st.progress(min(taux, 1.0), text=txt.replace("**", "") + (" · ⚠️ moins de 10 % libres" if taux > .9 else ""))
            ajout = sum(L.tarif(p["code"], p["debut"]) * p["qte"] for p in panier)
            st.markdown(f"Coût mensuel du client : {eur(cout_actuel)} → **{eur(cout_actuel + ajout)}**  "
                        f"<span class='aff-badge aff-fin'>+{eur(ajout)} / mois</span>", unsafe_allow_html=True)
            st.caption("Coût calculé sur le mois de début de chaque ligne (une fois toutes les lignes commencées).")
    b1, _, b3 = st.columns([1, 2, 1.4])
    if b1.button("Annuler", use_container_width=True, key="pan_cancel"):
        st.session_state.pop("panier", None)
        st.rerun()
    if b3.button(f"✓ Ajouter {len(panier)} ligne{'s' if len(panier) > 1 else ''}", type="primary", use_container_width=True,
                 disabled=not panier, key="pan_ok"):
        try:
            ids = L.ajouter_lignes(cid, [dict(element=p["element"], code=p["code"], qte=p["qte"], debut=p["debut"], fin=p["fin"]) for p in panier])
            st.session_state["aff_msg"] = f"{len(ids)} ligne(s) ajoutée(s) pour {nom}."
            _rafraichir()
        except ValueError as e:
            st.error(str(e))


@st.dialog("Remplacer / changer", width="large")
def dlg_remplacer(ligne, nom, cout_client):
    est_offre = ligne["element"] == "Offre"
    st.markdown(f"### {'Changer d’offre' if est_offre else 'Remplacer une option'} · {nom}")
    cat = L.catalogue_df()
    if est_offre:
        choix = cat[(cat.element == "Offre") & (cat.code != ligne["code"])]
    else:
        typ = L.q("SELECT type FROM assets WHERE id=?", (ligne["code"],)).type
        typ = typ.iloc[0] if len(typ) else None
        autres = cat[(cat.element == "Option") & (cat.code != ligne["code"])]
        choix = pd.concat([autres[autres.type == typ], autres[autres.type != typ]])
    g, fl, dr = st.columns([1, .15, 1.35], vertical_alignment="center")
    with g:
        with st.container(border=True):
            st.caption("Actuellement")
            st.markdown(f"**{ligne['libelle']} × {ligne['qte']:g}**  \n<span class='aff-sub'>depuis {mois_lbl(ligne['debut'])} · "
                        f"{eur(ligne['cout_mois'])} / mois</span>", unsafe_allow_html=True)
    fl.markdown("<div style='font-size:2rem;color:#0F6B5C;text-align:center'>→</div>", unsafe_allow_html=True)
    with dr:
        with st.container(border=True):
            st.caption("Nouvelle offre" if est_offre else "Nouvelle option (même catégorie en premier)")
            code = st.selectbox("Par", choix.code, key="rp_code", label_visibility="collapsed",
                                format_func=lambda c: f"{choix.set_index('code').libelle[c]} · {eur(choix.set_index('code').cout[c])}"
                                                      + ("" if est_offre else f" ({choix.set_index('code').type[c]})"))
            c1, c2, c3 = st.columns([1, 1.3, 1.3])
            qte = c1.number_input("Quantité", min_value=1.0, step=1.0, format="%g", value=float(ligne["qte"]), key="rp_q")
            dep_min = L.ajouter_mois(ligne["debut"], 1)
            with c2:
                debut = choix_mois("À partir de", max(mois_suivant_ref(), dep_min), "rp_deb", depuis=dep_min)
            with c3:
                fin = choix_mois("Jusqu'à", ligne["fin"] if L.d(ligne["fin"]) and L.d(ligne["fin"]) >= debut else None, "rp_fin",
                                 avec_sans_fin=True, depuis=debut)
    nouveau = L.tarif(code, debut) * qte
    ancien = float(ligne["cout_mois"])
    a = L.annee()
    mois_impact = 0
    if debut.year == a:
        fin_eff = min(L.d(fin) or date(a, 12, 1), date(a, 12, 1))
        f_old = min(L.d(ligne["fin"]) or date(a, 12, 1), date(a, 12, 1))
        mois_impact = max(0, (min(fin_eff, f_old).month - debut.month + 1))
        bonus = max(0, fin_eff.month - f_old.month) if fin_eff > f_old else 0
    else:
        bonus = 0
    impact = (nouveau - ancien) * mois_impact + nouveau * bonus
    with st.container(border=True):
        m1, m2, m3, m4 = st.columns([1, 1, 1, 1.6])
        m1.metric("Coût de la ligne", eur(nouveau), delta=eur(nouveau - ancien), delta_color="inverse")
        m2.metric("Coût mensuel du client", eur(cout_client - ancien + nouveau))
        m3.metric(f"Impact {a}", eur(impact), help="Sur les mois restants de l'exercice")
        m4.markdown(f"**Sera enregistré**  \n• {ligne['libelle']} : fin en **{mois_lbl(L.mois_precedent(debut))}**  \n"
                    f"• {choix.set_index('code').libelle[code]} × {qte:g} : début en **{mois_lbl(debut)}**"
                    + (f", fin en **{mois_lbl(fin)}**" if fin else ""))
    b1, _, b3 = st.columns([1, 2, 1.4])
    if b1.button("Annuler", use_container_width=True, key="rp_cancel"):
        st.rerun()
    if b3.button("✓ " + ("Changer l'offre" if est_offre else "Remplacer l'option"), type="primary", use_container_width=True, key="rp_ok"):
        try:
            nid = L.remplacer_ligne(ligne["id"], code, qte, debut, fin)
            st.session_state["aff_msg"] = f"{ligne['libelle']} remplacée par {choix.set_index('code').libelle[code]} à partir de {mois_lbl(debut)} ({nid})."
            _rafraichir()
        except ValueError as e:
            st.error(str(e))


@st.dialog("Personnaliser l'offre", width="large")
def dlg_personnaliser(ligne, nom):
    """Le client garde moins de certains composants retirables de son offre ; seule sa ligne change."""
    code, aff_id, qte = ligne["code"], ligne["id"], float(ligne["qte"] or 1)
    actuels = L.retraits_ligne(aff_id)
    st.markdown(f"### Personnaliser {ligne['libelle']} · {nom}")
    st.caption("Choisissez ce que le client garde. Seule sa ligne change : l'offre et les autres clients ne bougent pas.")
    deb = L.mois_debut(ligne["debut"])
    defaut = max(mois_suivant_ref(), deb)
    c1, _ = st.columns([1, 2])
    with c1:
        depuis = choix_mois("À partir de", defaut, "ps_dep", depuis=min(defaut, max(deb, date(L.annee(), 1, 1))))
    comp = L.composition_au(code, max(depuis, deb))
    ret = L.retirables(code)
    a = L.assets_df().set_index("id")
    unit = {k: L.tarif(k, depuis) for k in comp.asset_id}
    lignes, retraits = [], {}
    h = st.columns([3.2, 1, 1.6, 1.2, 1.2])
    for col, t in zip(h, ["Composant", "Dans l'offre", "Gardé par le client", "Retiré", "Coût / mois"]):
        col.markdown(f"<span class='aff-sub'><b>{t}</b></span>", unsafe_allow_html=True)
    for r in sorted(comp.itertuples(), key=lambda x: (x.asset_id in ret, x.asset_id)):
        nom_a = a.nom.get(r.asset_id, r.asset_id)
        cols = st.columns([3.2, 1, 1.6, 1.2, 1.2], vertical_alignment="center")
        if r.asset_id not in ret:
            cols[0].markdown(f"<span style='color:#9AA6A0'>🔒 {nom_a}</span>", unsafe_allow_html=True)
            cols[1].markdown(f"<span style='color:#9AA6A0'>{r.qte:g}</span>", unsafe_allow_html=True)
            cols[2].markdown(f"<span style='color:#9AA6A0'>{r.qte:g}</span>", unsafe_allow_html=True)
            cols[3].markdown("<span style='color:#9AA6A0'>—</span>", unsafe_allow_html=True)
            cols[4].markdown(f"<span style='color:#9AA6A0'>{eur(unit[r.asset_id] * r.qte, 2)}</span>", unsafe_allow_html=True)
            continue
        cols[0].markdown(f"**{nom_a}**")
        cols[1].markdown(f"{r.qte:g}")
        garde = cols[2].number_input("Gardé", min_value=0.0, max_value=float(r.qte), step=1.0, format="%g", label_visibility="collapsed",
                                     value=float(r.qte) - min(actuels.get(r.asset_id, 0.0), float(r.qte)), key=f"ps_g_{aff_id}_{r.asset_id}")
        retire = float(r.qte) - garde
        if retire > 0:
            retraits[r.asset_id] = retire
        cols[3].markdown(f"<span style='color:#9C1C14'>− {eur(unit[r.asset_id] * retire, 2)}</span>" if retire else "—", unsafe_allow_html=True)
        cols[4].markdown(f"**{eur(unit[r.asset_id] * garde, 2)}**")
        lignes.append(r.asset_id)
    standard = L.tarif(code, depuis)
    moins = sum(unit[k] * v for k, v in retraits.items())
    g, d_ = st.columns([1.3, 1], gap="large")
    with g:
        if retraits:
            st.markdown("Rendu au parc : " + ", ".join(f"**{v * qte:g} × {a.nom.get(k, k)}**" for k, v in retraits.items()) + ".")
        if deb < depuis:
            st.caption(f"Les mois avant {mois_lbl(depuis)} restent calculés avec la personnalisation actuelle : la ligne est découpée à cette date.")
        if qte > 1:
            st.caption(f"Les retraits s'appliquent à chacun des {qte:g} exemplaires de l'offre.")
    d_.markdown(f"<div class='aff-recap' style='background:#F4F7F5;border:1px solid #DCE6E2;border-radius:10px;padding:10px 14px'>"
                f"<div style='display:flex;justify-content:space-between'><span>Offre standard{f' × {qte:g}' if qte > 1 else ''}</span><span>{eur(standard * qte, 2)}</span></div>"
                f"<div style='display:flex;justify-content:space-between;color:#9C1C14'><span>Retiré</span><span>− {eur(moins * qte, 2)}</span></div>"
                f"<div style='display:flex;justify-content:space-between;border-top:1px solid #DCE6E2;margin-top:4px;padding-top:4px;font-weight:700'>"
                f"<span>Coût mensuel de la ligne</span><span style='color:#0F6B5C'>{eur((standard - moins) * qte, 2)}</span></div></div>", unsafe_allow_html=True)
    b1, _, b3 = st.columns([1.4, 1, 1.6])
    if actuels and b1.button("↺ Revenir à l'offre standard", key="ps_std", use_container_width=True):
        try:
            L.personnaliser_ligne(aff_id, {}, depuis)
            st.session_state["aff_msg"] = f"{ligne['libelle']} : retour à l'offre standard à partir de {mois_lbl(depuis)}."
            _rafraichir()
        except ValueError as e:
            st.error(str(e))
    if b3.button("Enregistrer la personnalisation", type="primary", key="ps_ok", use_container_width=True):
        try:
            L.personnaliser_ligne(aff_id, retraits, depuis)
            st.session_state["aff_msg"] = (f"{ligne['libelle']} personnalisée à partir de {mois_lbl(depuis)} : {eur((standard - moins) * qte)} / mois."
                                           if retraits else f"{ligne['libelle']} : offre standard à partir de {mois_lbl(depuis)}.")
            _rafraichir()
        except ValueError as e:
            st.error(str(e))


@st.dialog("Arrêter", width="large")
def dlg_arreter(cid, nom, lignes, preselection, cout_client, prevision):
    tout = set(preselection) == set(lignes.id)
    st.markdown(f"### {'Arrêter la solution' if tout else 'Arrêter'} · {nom}")
    st.caption("Le client ne veut plus de la solution, ou seulement d'une partie. Les mois déjà facturés ne changent pas.")
    g, dr = st.columns([1.15, 1], gap="large")
    with g:
        st.markdown("**Que faut-il arrêter ?**")
        coches = []
        for r in lignes.itertuples():
            lab = f"**{r.libelle}** × {r.qte:g} · {r.element.lower()} · {mois_lbl(r.debut)} → {mois_lbl(r.fin)} · {eur(r.cout_mois)} / mois"
            if st.checkbox(lab, value=r.id in preselection, key=f"ar_chk_{r.id}"):
                coches.append(r.id)
        c1, c2 = st.columns(2)
        with c1:
            dernier = choix_mois("Dernier mois facturé", date(L.annee(), L.mois_ref(), 1), "ar_der")
        motif = c2.selectbox("Motif", MOTIFS, key="ar_motif")
        if motif == "Autre":
            motif = st.text_input("Précisez", key="ar_motif_txt") or "Autre"
        tout_coche = set(coches) == set(lignes.id) and len(coches) > 0
        inactif = st.toggle("Passer le client au statut « Inactif »", value=tout_coche, key=f"ar_inactif_{tout_coche}",
                            disabled=not tout_coche, help="Proposé quand toutes les lignes sont arrêtées")
    sel = lignes[lignes.id.isin(coches)]
    a = L.annee()
    eco_mois = float(sel[[L.d(x) <= dernier for x in sel.debut]].cout_mois.sum()) if len(sel) else 0.0
    eco_annee = 0.0
    if dernier.year == a and len(sel):
        eco_annee = float(sum(sel[m].sum() for m in range(dernier.month + 1, 13)))
    with dr:
        with st.container(border=True):
            st.markdown("**Effet**")
            m1, m2 = st.columns(2)
            m1.metric("Coût mensuel aujourd'hui", eur(cout_client))
            m2.metric(f"À partir de {mois_lbl(L.ajouter_mois(dernier, 1))}", eur(max(cout_client - eco_mois, 0)),
                      delta=eur(-eco_mois), delta_color="inverse")
            st.markdown(f"Prévision {a} : {eur(prevision)} → **{eur(prevision - eco_annee)}**")
            if len(sel):
                serie = pd.DataFrame({"Mois": L.MOIS, "n": range(1, 13),
                                      "Coût": [float(lignes[m].sum() - (sel[m].sum() if m > dernier.month and dernier.year == a else 0)) for m in range(1, 13)]})
                serie["État"] = ["Arrêté" if (n > dernier.month and dernier.year == a) else "Facturé" for n in serie.n]
                st.altair_chart(alt.Chart(serie).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3)
                                .encode(x=alt.X("Mois:N", sort=L.MOIS, title=None, axis=alt.Axis(labelAngle=0)), y=alt.Y("Coût:Q", title="€"),
                                        color=alt.Color("État:N", scale=alt.Scale(domain=["Facturé", "Arrêté"], range=["#9AA6A0", "#9C1C14"]), legend=None),
                                        tooltip=["Mois", alt.Tooltip("Coût:Q", format=",.0f")]).properties(height=170), use_container_width=True)
        a_venir = sel[[L.d(x) > dernier for x in sel.debut]]
        if len(a_venir):
            st.warning(f"{len(a_venir)} ligne(s) pas encore commencée(s) : elles seront annulées.")
        st.caption("« Arrêter » met une date de fin et garde l'historique. Pour effacer une erreur de saisie, utilisez le menu ⋯ de la ligne.")
    b1, _, b3 = st.columns([1, 2, 1.6])
    if b1.button("Annuler", use_container_width=True, key="ar_cancel"):
        st.rerun()
    if b3.button(f"⏹ Arrêter {len(coches)} ligne{'s' if len(coches) > 1 else ''} fin {mois_lbl(dernier)}", type="primary",
                 use_container_width=True, disabled=not coches, key="ar_ok"):
        try:
            n, k = L.arreter_lignes(coches, dernier, motif, inactif)
            st.session_state["aff_msg"] = f"{n} ligne(s) arrêtée(s) après {mois_lbl(dernier)}" + (f", {k} annulée(s)" if k else "") + \
                                          (" · client passé en Inactif" if inactif else "") + "."
            _rafraichir()
        except ValueError as e:
            st.error(str(e))


# ----------------------------------------------------------------------------- frise
def frise(lignes):
    a = L.annee()
    if lignes.empty:
        return None
    rows = []
    for r in lignes.itertuples():
        deb, fin = L.d(r.debut), L.d(r.fin)
        if (fin and fin.year < a) or deb.year > a:
            continue
        s = 1 if deb.year < a else deb.month
        e = 12 if (fin is None or fin.year > a) else fin.month
        rows.append(dict(ligne=f"{r.libelle} × {r.qte:g}", element=r.element, s=s - .45, e=e + .45,
                         txt=r.libelle, periode=f"{mois_lbl(deb)} → {mois_lbl(fin)}"))
    if not rows:
        return None
    df = pd.DataFrame(rows)
    ordre = df.ligne.tolist()
    axe = alt.Axis(values=list(range(1, 13)), labelExpr="['Janv.','Févr.','Mars','Avr.','Mai','Juin','Juil.','Août','Sept.','Oct.','Nov.','Déc.'][datum.value-1]",
                   grid=False, title=None, orient="top")
    base = alt.Chart(df).encode(y=alt.Y("ligne:N", sort=ordre, title=None, axis=alt.Axis(labelLimit=220)))
    bars = base.mark_bar(cornerRadius=5, height=22).encode(
        x=alt.X("s:Q", scale=alt.Scale(domain=[0.5, 12.5]), axis=axe), x2="e:Q",
        color=alt.Color("element:N", scale=alt.Scale(domain=["Offre", "Option"], range=[TEAL, "#7FB8A8"]), legend=None),
        tooltip=[alt.Tooltip("ligne:N", title="Ligne"), alt.Tooltip("periode:N", title="Période")])
    regle = alt.Chart(pd.DataFrame({"x": [L.mois_ref() + .45]})).mark_rule(color="#C2702E", strokeDash=[4, 3]).encode(x="x:Q")
    ch = (bars + regle).properties(height=38 * len(df) + 40).configure_axisY(minExtent=190, labelFontSize=12.5, labelColor="#16201C")
    serie = pd.DataFrame({"n": range(1, 13), "Coût": [float(lignes[m].sum()) for m in range(1, 13)]})
    serie["Période"] = ["Réel" if n <= L.mois_ref() else "Prévision" for n in serie.n]
    cout = alt.Chart(serie).mark_bar(cornerRadiusTopLeft=3, cornerRadiusTopRight=3, size=28).encode(
        x=alt.X("n:Q", scale=alt.Scale(domain=[0.5, 12.5]), axis=alt.Axis(values=list(range(1, 13)), labels=False, ticks=False, title=None, grid=False)),
        y=alt.Y("Coût:Q", title=None, axis=alt.Axis(format=",.0f", minExtent=190, titlePadding=0)),
        color=alt.Color("Période:N", scale=alt.Scale(domain=["Réel", "Prévision"], range=[TEAL, "#9CC7BB"]), legend=None),
        tooltip=[alt.Tooltip("n:Q", title="Mois"), alt.Tooltip("Coût:Q", format=",.0f")]).properties(height=150)
    return ch, cout


# ----------------------------------------------------------------------------- ligne de la fiche
@st.dialog("Frais ou avoir ponctuel")
def dlg_ponctuel(cid, nom):
    a = L.annee()
    st.markdown(f"**{nom}** · exercice {a}")
    st.caption("Un montant facturé une seule fois, le mois choisi : frais de mise en service, intervention, geste commercial… "
               "Un avoir est un montant négatif.")
    sens = st.segmented_control("Nature", ["Frais", "Avoir"], default="Frais", key="pc_sens")
    c1, c2 = st.columns(2)
    mois = c1.selectbox("Mois", range(1, 13), index=L.mois_ref() - 1, format_func=lambda i: L.MOIS_LONG[i - 1].capitalize(), key="pc_mois")
    mt = c2.number_input("Montant (€)", min_value=0.0, step=100.0, key="pc_mt")
    lib = st.text_input("Libellé", "Frais de mise en service" if sens != "Avoir" else "Avoir", key="pc_lib")
    if st.button("Enregistrer", type="primary", disabled=mt <= 0 or not lib.strip()):
        L.ajouter_ajustement(a, int(mois), cid, lib.strip(), -mt if sens == "Avoir" else mt)
        for k in ("pc_sens", "pc_mois", "pc_mt", "pc_lib"):
            st.session_state.pop(k, None)
        st.rerun()


def bloc_ponctuels(cid, nom, fige):
    """Frais et avoirs ponctuels du client sur l'exercice, et la régularisation de décembre (lecture seule)."""
    aj = L.ajustements_client(cid)
    t_, b_ = st.columns([3, 1.3], vertical_alignment="center")
    t_.markdown(f"##### Frais et avoirs ponctuels {L.annee()}")
    if b_.button("＋ Frais ou avoir ponctuel", type="tertiary", disabled=fige, key="pc_ouvrir"):
        dlg_ponctuel(cid, nom)
    if aj.empty:
        st.caption("Aucun frais ni avoir ponctuel sur cet exercice.")
        return
    for r in aj.itertuples():
        regul = r.nature in (L.NATURE_REGUL, "Ventilation")
        with st.container(border=True):
            c1, c2, c3, c4 = st.columns([.9, 3.2, 1.3, .5], vertical_alignment="center")
            c1.markdown(f"**{L.MOIS[int(r.mois) - 1]}**")
            c2.markdown(r.libelle + ("  \n<span style='color:#5E6B65;font-size:.82rem'>calculée dans Exercices › Régularisation et clôture</span>"
                                     if regul else ""), unsafe_allow_html=True)
            c3.markdown(f"<div style='text-align:right;font-weight:700;color:{'#9C1C14' if r.montant < 0 else 'inherit'}'>"
                        f"{r.montant:+,.0f} €</div>".replace(",", " "), unsafe_allow_html=True)
            if not regul and c4.button("🗑️", key=f"pc_del_{r.id}", type="tertiary", disabled=fige, help="Supprimer"):
                L.supprimer_ajustement(r.id)
                st.rerun()


def carte_ligne(r, nom, cout_client, lignes_actives, fige):
    est_offre = r.element == "Offre"
    with st.container(border=True):
        c0, c1, c2, c3, c4 = st.columns([3.4, 1.6, 1.2, 3.3, .55], vertical_alignment="center")
        badges = f"<span class='aff-badge {'aff-offre' if est_offre else 'aff-option'}'>{r.element.upper()}</span>"
        rt = getattr(r, "retraits", None) if est_offre else None
        rt = rt if isinstance(rt, dict) and rt else None
        if rt:
            badges += "<span class='aff-badge aff-fin'>PERSONNALISÉE</span>"
        if r.etat == "À venir":
            badges += "<span class='aff-badge aff-avenir'>À VENIR</span>"
        elif L.d(r.fin) and str(getattr(r, "motif", "") or "").startswith("Personnalisation à partir de"):
            badges += f"<span class='aff-badge aff-avenir'>PERSONNALISÉE DÈS {mois_lbl(L.ajouter_mois(L.d(r.fin), 1)).upper()}</span>"
        elif L.d(r.fin):
            badges += "<span class='aff-badge aff-fin'>FIN PRÉVUE</span>"
        c0.markdown(f"{badges}<span class='aff-nom'>{r.libelle}{'' if r.qte == 1 and est_offre else f' × {r.qte:g}'}</span><br>"
                    f"<span class='aff-sub'>{r.code}{(' · ' + r.detail) if r.detail else ''}{(' · devis ' + r.ref) if isinstance(r.ref, str) and r.ref.startswith('DV') else ''}</span>"
                    + (f"<br><span class='aff-badge aff-fin' style='font-weight:600;letter-spacing:0'>retiré : {L.texte_retraits(rt)}</span>" if rt else ""),
                    unsafe_allow_html=True)
        c1.markdown(f"<div class='aff-dates'><span class='aff-sub'>du</span> <b>{mois_lbl(r.debut)}</b><br>"
                    f"<span class='aff-sub'>au</span> <b>{mois_lbl(r.fin)}</b></div>", unsafe_allow_html=True)
        std = float(getattr(r, "cout_standard", r.cout_unit) or 0) * float(r.qte or 0)
        barre = (f"<small style='text-decoration:line-through;color:#9AA6A0'>{eur(std)}</small>" if rt and std > r.cout_mois + .5 else "")
        c2.markdown(f"<div class='aff-prix'>{eur(r.cout_mois)}<small>/ mois</small>{barre}</div>", unsafe_allow_html=True)
        suite = str(getattr(r, "motif", "") or "").startswith("Personnalisation à partir de")  # la suite de cette ligne porte la personnalisation
        perso_ok = est_offre and bool(L.retirables(r.code)) and not suite
        if perso_ok and c0.button("⚙️ Personnaliser" if not rt else "⚙️ Modifier la personnalisation", key=f"bt_ps2_{r.id}", type="tertiary",
                                  disabled=fige, help="Le client garde moins de certains composants retirables ; seule sa ligne change."):
            dlg_personnaliser(r._asdict(), nom)
        b1, b2 = c3.columns(2)
        if b1.button("⇄ Changer" if est_offre else "⇄ Remplacer", key=f"bt_rp_{r.id}", use_container_width=True,
                     disabled=fige or r.etat == "À venir", help="Pour une ligne pas encore commencée, modifiez-la via ⋯"):
            dlg_remplacer(r._asdict(), nom, cout_client)
        if b2.button("⏹ Arrêter", key=f"bt_ar_{r.id}", use_container_width=True, disabled=fige):
            dlg_arreter(r.client_id, nom, lignes_actives, [r.id], cout_client, float(lignes_actives[list(range(1, 13))].sum().sum()))
        with c4.popover("⋯", disabled=fige):
            st.markdown(f"**{r.libelle}** · {r.id}")
            with st.form(f"md_form_{r.id}", border=False):
                f1, f2, f3 = st.columns([1, 1.4, 1.4])
                qte = f1.number_input("Qté", min_value=1.0, step=1.0, format="%g", value=float(r.qte), key=f"md_q_{r.id}")
                with f2:
                    deb = choix_mois("Début", r.debut, f"md_deb_{r.id}")
                with f3:
                    fin = choix_mois("Fin", r.fin, f"md_fin_{r.id}", avec_sans_fin=True)
                if st.form_submit_button("📅 Enregistrer les dates", type="primary"):
                    try:
                        L.modifier_dates(r.id, deb, fin, qte)
                        st.session_state["aff_msg"] = f"{r.libelle} : {mois_lbl(deb)} → {mois_lbl(fin)}, quantité {qte:g}."
                        _rafraichir()
                    except ValueError as e:
                        st.error(str(e))
            st.divider()
            forcer = True
            if r.facturee:
                st.caption("Cette ligne a déjà été comptée dans des mois réels. La supprimer modifie la consommation passée : "
                           "utilisez plutôt « Arrêter », sauf erreur de saisie.")
                forcer = st.checkbox("C'est une erreur de saisie, supprimer quand même", key=f"md_force_{r.id}")
            if st.button("🗑 Supprimer (erreur de saisie)", key=f"md_del_{r.id}", disabled=not forcer):
                try:
                    L.supprimer_ligne(r.id, forcer=True)
                    st.session_state["aff_msg"] = f"Ligne {r.id} ({r.libelle}) supprimée."
                    _rafraichir()
                except ValueError as e:
                    st.error(str(e))


def accueil(cli):
    """Vue d'ensemble affichée tant qu'aucun client n'est sélectionné."""
    ref = date(L.annee(), L.mois_ref(), 1)
    st.markdown("<div style='font-size:1.45rem;font-weight:700'>Choisissez un client dans la liste</div>"
                "<div class='aff-sub'>Sa fiche s'ouvrira ici : offres et options datées, ajout, remplacement, arrêt.</div>",
                unsafe_allow_html=True)
    st.write("")
    lm = L.lignes_mensuelles()
    l_ = lm[lm.element.isin(["Offre", "Option"])].copy()
    l_["deb"] = l_.debut.map(L.d)
    l_["fin_"] = l_.fin.map(L.d)
    horizon = L.ajouter_mois(ref, 3)
    a_venir = l_[(l_.deb > ref) & (l_.deb <= horizon)]
    fins_ = set(zip(l_.client_id, l_.code, l_.fin_))
    # la suite d'une ligne d'offre personnalisée (même client, même offre, le mois suivant) n'est pas un nouveau démarrage
    a_venir = a_venir[[(c_, k_, L.mois_precedent(d_)) not in fins_ for c_, k_, d_ in zip(a_venir.client_id, a_venir.code, a_venir.deb)]]
    fins = l_[l_.fin_.notna() & (l_.fin_ >= ref) & (l_.fin_ < horizon)]
    suites = set(zip(l_.client_id, l_.deb))  # une ligne remplacée a une suite le mois d'après : pas une vraie fin
    fins = fins[[(c_, L.ajouter_mois(f_, 1)) not in suites for c_, f_ in zip(fins.client_id, fins.fin_)]]
    k = st.columns(4)
    k[0].metric("Clients équipés", int(cli.avec.sum()), help="Clients avec au moins une offre ou option au mois de référence")
    k[0].caption(f"sur {len(cli)} clients")
    k[1].metric(f"Refacturé en {L.MOIS_LONG[L.mois_ref() - 1]}", eur(cli.cout.sum()))
    k[2].metric("Démarrages à venir", len(a_venir), help="Lignes qui commencent dans les 3 prochains mois")
    k[3].metric("Fins prévues", len(fins), help="Lignes qui se terminent d'ici 3 mois")

    def tableau(df, titre, col_date, cle):
        st.markdown(f"##### {titre}")
        if df.empty:
            st.caption("Rien sur les 3 prochains mois.")
            return
        t = df.sort_values(col_date)
        t = pd.DataFrame({"client_id": t.client_id, "Client": t.client, "Ligne": t.libelle + " × " + t.qte.map(lambda x: f"{x:g}"),
                          "Type": t.element, "Mois": t[col_date].map(mois_lbl)}).reset_index(drop=True)
        ev = st.dataframe(t.drop(columns="client_id"), hide_index=True, use_container_width=True, on_select="rerun",
                          selection_mode="single-row", key=f"{cle}_{st.session_state.get('aff_tab_n', 0)}")
        rows = ev.selection.rows if ev and ev.selection else []
        if rows:
            st.session_state["aff_client"] = t.client_id.iloc[rows[0]]
            st.rerun()

    tableau(a_venir, "Prochains démarrages", "deb", "aff_av")
    tableau(fins, "Fins prévues (à confirmer ou à prolonger)", "fin_", "aff_fp")
    st.caption("Cliquez sur une ligne pour ouvrir la fiche du client.")


# ----------------------------------------------------------------------------- page
def page():
    st.markdown(CSS, unsafe_allow_html=True)
    entete("Affectations", "Cliquez sur un client : ses offres et options s'affichent avec leurs dates. Tout se modifie depuis sa fiche.",
           "🔁", "Activité")
    if "aff_msg" in st.session_state:
        st.success(st.session_state.pop("aff_msg"))
    fige = L.est_cloture()
    if fige:
        st.info(f"L'exercice {L.annee()} est clôturé : les affectations sont en lecture seule. Choisissez un exercice ouvert dans la barre latérale pour les modifier.")
    cli = _resume_clients()
    # à l'arrivée sur la page : aucun client sélectionné (sauf si on vient d'un lien « Voir dans Affectations »)
    if st.session_state.get("_page_prec") != "affectation" and not st.session_state.get("_aff_vu"):
        st.session_state.pop("aff_client", None)
        st.session_state["aff_tab_n"] = st.session_state.get("aff_tab_n", 0) + 1
    st.session_state["_aff_vu"] = True
    if "aff_goto" in st.session_state:
        st.session_state["aff_client"] = st.session_state.pop("aff_goto")
    tab_n = st.session_state.get("aff_tab_n", 0)

    gauche, droite = st.columns([1.3, 2.6], gap="medium")
    with gauche:
        rech = st.text_input("Rechercher", placeholder="🔎 Nom, entité, pays…", label_visibility="collapsed", key="aff_rech")
        n_avec = int(cli.avec.sum())
        filtre = st.segmented_control("Filtre", [f"Tous ({len(cli)})", f"Avec offre ({n_avec})", f"Sans ({len(cli) - n_avec})"],
                                      default=f"Tous ({len(cli)})", key="aff_filtre", label_visibility="collapsed") or "Tous"
        vue = cli.copy()
        if rech:
            m = rech.lower()
            vue = vue[vue.nom.str.lower().str.contains(m, regex=False) | vue.entite.str.lower().str.contains(m, regex=False)
                       | vue.pays.str.lower().str.contains(m, regex=False) | vue.id.str.lower().str.contains(m, regex=False)]
        if filtre.startswith("Avec"):
            vue = vue[vue.avec]
        elif filtre.startswith("Sans"):
            vue = vue[~vue.avec]
        vue = vue.sort_values(["avec", "cout"], ascending=[False, False]).reset_index(drop=True)
        tab = vue[["nom", "offre", "cout"]]
        evt = st.dataframe(tab, hide_index=True, use_container_width=True, height=min(660, 35 * (len(tab) + 1) + 3),
                           on_select="rerun", selection_mode="single-row", key=f"aff_tab_{tab_n}_{filtre}_{rech}",
                           column_config={"nom": st.column_config.TextColumn("Client", width=140),
                                          "offre": st.column_config.TextColumn("Offre actuelle", width=125),
                                          "cout": st.column_config.NumberColumn("€ / mois", format="%,.0f €", width=70)})
        rows = evt.selection.rows if evt and evt.selection else []
        if rows:
            st.session_state["aff_client"] = vue.id.iloc[rows[0]]
        if st.session_state.get("aff_client") not in set(cli.id):
            st.session_state.pop("aff_client", None)
        st.caption(f"{len(vue)} client(s) affiché(s). Cliquez sur une ligne pour ouvrir la fiche.")

    cid = st.session_state.get("aff_client")
    if cid is None:
        with droite:
            accueil(cli)
        return
    c = cli.set_index("id").loc[cid]
    lignes = L.lignes_client(cid)
    ouvertes = lignes[lignes.etat != "Terminée"]
    en_cours = lignes[lignes.etat == "En cours"]
    cout = float(en_cours.cout_mois.sum())
    prevision = float(lignes[list(range(1, 13))].sum().sum()) if len(lignes) else 0.0
    prevision += float(L.ajustements_client(cid).montant.sum())  # frais, avoirs et régularisation
    budget = float(L.budgets_df().set_index("client_id").budget.get(cid, 0))

    with droite:
        if st.button("✕ Fermer la fiche", key="aff_fermer", type="tertiary"):
            st.session_state.pop("aff_client", None)
            st.session_state["aff_tab_n"] = tab_n + 1
            st.rerun()
        h1, h2 = st.columns([1.6, 2.4], vertical_alignment="center")
        h1.markdown(f"<div style='font-size:1.6rem;font-weight:700'>{c.nom}</div>"
                    f"<div class='aff-sub'>{cid} · {c.entite} · {c.pays}{(' · ' + c.responsable) if c.responsable else ''}"
                    f" · statut {c.statut}</div>", unsafe_allow_html=True)
        b1, b2 = h2.columns(2)
        if b1.button("＋ Ajouter offres / options", type="primary", use_container_width=True, disabled=fige):
            st.session_state.pop("panier", None)
            dlg_ajouter(cid, c.nom, cout)
        if b2.button("⏹ Arrêter la solution", use_container_width=True, disabled=fige or ouvertes.empty):
            dlg_arreter(cid, c.nom, ouvertes, list(ouvertes.id), cout, prevision)
        k1, k2, k3 = st.columns(3)
        n_o, n_p = int((en_cours.element == "Offre").sum()), int((en_cours.element == "Option").sum())
        k1.metric(f"Coût mensuel ({L.MOIS_LONG[L.mois_ref() - 1]})", eur(cout), help="Lignes en cours au mois de référence")
        k1.caption(f"{n_o} offre(s) · {n_p} option(s)")
        k2.metric(f"Prévision {L.annee()}", eur(prevision), help="Mois réels + mois restants")
        k3.metric(f"Budget {L.annee()}", eur(budget) if budget else "—")
        if budget:
            pct = prevision / budget
            k3.progress(min(pct, 1.0), text=f"{pct * 100:.0f} % du budget".replace(".", ","))
        st.markdown("##### Offres et options en cours")
        if ouvertes.empty:
            st.info("Aucune offre ni option en cours pour ce client. Cliquez sur « ＋ Ajouter offres / options ».")
        for r in ouvertes.itertuples():
            carte_ligne(r, c.nom, cout, ouvertes, fige)
        bloc_ponctuels(cid, c.nom, fige)
        st.markdown(f"##### L'année {L.annee()}")
        ch = frise(lignes)
        if ch is None:
            st.caption("Rien sur cet exercice.")
        else:
            st.altair_chart(ch[0], use_container_width=True)
            st.caption("Coût du mois · foncé = réel, clair = prévision")
            st.altair_chart(ch[1], use_container_width=True)
        term = lignes[lignes.etat == "Terminée"]
        with st.expander(f"Historique · {len(term)} ligne(s) terminée(s)"):
            if term.empty:
                st.caption("Aucune ligne terminée.")
            else:
                st.dataframe(term[["id", "element", "libelle", "qte", "debut", "fin", "operation", "motif", "total"]], hide_index=True,
                             use_container_width=True, column_config={
                                 "id": "Ligne", "element": "Type", "libelle": "Libellé", "qte": "Qté",
                                 "debut": st.column_config.DateColumn("Début", format="MMM YYYY"),
                                 "fin": st.column_config.DateColumn("Fin", format="MMM YYYY"), "operation": "Opération", "motif": "Motif",
                                 "total": st.column_config.NumberColumn(f"Total {L.annee()}", format="%,.0f €")})
