"""Page Offres : catalogue en cartes, éditeur avec date d'effet, comparateur, retrait d'une offre."""
import re
from datetime import date
from io import BytesIO

import pandas as pd
import streamlit as st

import affectations_ui as AU
import logic as L
from affectations_ui import choix_mois, eur, mois_lbl

PAGE_DEVIS = None  # renseignée par app.py (bouton « Créer un devis »)
COUL = {"GPU": "#0F6B5C", "Serveur": "#2E8B74", "Licence": "#C2702E", "Service": "#E3A66F", "RAM": "#9CC7BB",
        "CPU": "#4C9C8A", "Stockage": "#3A5BA0", "Réseau": "#7A8580"}
AUTRES = ["#B0B8B4", "#D9A5B3", "#8FA9D6", "#C9B458"]

CSS = """
<style>
.of-pill{display:inline-block;padding:2px 10px;border-radius:12px;font-size:.78rem;font-weight:700}
.of-Active{background:#DDEFE8;color:#0A4C41}.of-Brouillon{background:#EEF1EF;color:#55625C}.of-Retirée{background:#F8E1DF;color:#9C1C14}
.of-nom{font-size:1.2rem;font-weight:700;margin-top:6px}.of-prix{font-size:1.45rem;font-weight:700}.of-prix small{font-size:.85rem;font-weight:400;color:#55625C}
.of-bar{display:flex;height:10px;border-radius:5px;overflow:hidden;background:#EEF1EF;margin:8px 0}
.of-res{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:4px}.of-res span{background:#F2F5F3;border-radius:6px;padding:3px 8px;font-size:.78rem}
.of-dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle}
.of-leg{font-size:.8rem;color:#55625C}.of-leg span{margin-right:12px;white-space:nowrap}
.of-cost{background:#F4F7F5;border:1px solid #DCE6E2;border-radius:10px;padding:14px 16px}
.of-grid{display:grid;grid-template-columns:1fr 1fr;gap:3px 14px;font-size:.84rem;margin-top:8px}
table.of-cmp{width:100%;border-collapse:collapse;font-size:.92rem}
table.of-cmp td,table.of-cmp th{padding:9px 12px;border-bottom:1px solid #EEF1EF;text-align:left;vertical-align:top}
table.of-cmp td.l{color:#55625C;font-size:.85rem;width:210px}table.of-cmp th{font-size:1.05rem}
table.of-cmp td.best{background:#EAF5F0;font-weight:700;color:#0A4C41}
</style>"""


def couleur(t, types=None):
    if t in COUL:
        return COUL[t]
    types = types or L.liste("type")
    autres = [x for x in types if x not in COUL]
    return AUTRES[autres.index(t) % len(AUTRES)] if t in autres else "#B0B8B4"


def pill(s):
    return f"<span class='of-pill of-{s}'>{s}</span>"


def aller(vue, **kw):
    st.session_state["of_vue"] = vue
    st.session_state.update({f"of_{k}": v for k, v in kw.items()})
    for k in [k for k in st.session_state if str(k).startswith(("ofe_", "ofr_", "ofc_"))]:
        del st.session_state[k]
    st.rerun()


# ----------------------------------------------------------------------------- données
def detail_offres():
    """Composition chiffrée (prix du mois de référence) de toutes les offres."""
    m = L.mois_ref()
    cam = L.couts_assets_mensuels()
    comp = L.q("SELECT c.offre_id, c.asset_id, c.qte, a.nom, a.type FROM composition c LEFT JOIN assets a ON a.id=c.asset_id")
    comp["cout"] = comp.asset_id.map(cam[m]).fillna(0) * comp.qte
    return comp


def bar_html(rep):
    tot = sum(rep.values()) or 1
    return "<div class='of-bar'>" + "".join(f"<div style='width:{v / tot * 100:.2f}%;background:{couleur(k)}'></div>"
                                          for k, v in sorted(rep.items(), key=lambda x: -x[1]) if v > 0) + "</div>"


def ressources(c):
    ordre = {"GPU": 0, "CPU": 1, "RAM": 2, "Stockage": 3, "Serveur": 4, "Service": 5, "Réseau": 6}
    out = []
    for r in sorted(c.itertuples(), key=lambda r: (ordre.get(r.type, 9), -r.cout)):
        q = f"{r.qte:g}"
        if r.type == "GPU":
            out.append(f"{q} {' '.join(str(r.nom).split()[:2])}")
        elif r.type == "CPU":
            out.append(f"{q} vCPU" if "vcpu" in str(r.nom).lower() else f"{q} × {r.nom}")
        elif r.type == "RAM":
            out.append(f"{q} Go")
        elif r.type == "Stockage":
            out.append(f"{q} To")
        elif r.type in ("Serveur", "Service", "Réseau") and r.cout > 40:
            out.append(str(r.nom)[:22])
    return out[:5]


def memoire_gpu(c):
    tot = 0
    for r in c[c.type == "GPU"].itertuples():
        m = re.search(r"(\d+)\s*Go", str(r.nom))
        if m:
            tot += int(m.group(1)) * r.qte
    return tot


def clients_par_offre():
    lm = L.lignes_mensuelles()
    act = lm[(lm.element == "Offre") & (lm.statut == "Active")]
    return act, lm


# ----------------------------------------------------------------------------- catalogue
def catalogue():
    offres = L.q("SELECT * FROM offres ORDER BY id")
    comp = detail_offres()
    act, lm = clients_par_offre()
    n_cli = act.groupby("code").client_id.nunique()
    h1, h2 = st.columns([3, 1.6], vertical_alignment="center")
    h1.title("Offres")
    h1.caption("Le catalogue de la plateforme : composition, coût et clients de chaque offre.")
    sel = st.session_state.setdefault("of_cmp", [])
    sel[:] = [x for x in sel if x in set(offres.id)]
    b1, b2 = h2.columns(2)
    if b1.button(f"⚖️ Comparer ({len(sel)})", use_container_width=True, disabled=len(sel) < 2, help="Cochez 2 à 4 offres"):
        aller("comparer")
    if b2.button("＋ Créer une offre", type="primary", use_container_width=True):
        nouvelle_offre()
        aller("edition")

    k = st.columns(4)
    nb = offres.statut.value_counts()
    k[0].metric("Offres actives", int(nb.get("Active", 0)))
    k[0].caption(f"{int(nb.get('Brouillon', 0))} brouillon · {int(nb.get('Retirée', 0))} retirée")
    k[1].metric("Clients sur une offre", int(act.client_id.nunique()))
    k[1].caption(f"{len(act)} lignes d'offre en cours")
    via = float(act.cout_ref.sum())
    tot = float(lm[lm.statut == "Active"].cout_ref.sum())
    k[2].metric(f"Refacturé via les offres ({L.MOIS[L.mois_ref() - 1].lower()})", eur(via))
    k[2].caption(f"{via / tot * 100:.0f} % du total refacturé" if tot else "")
    if len(n_cli):
        top = n_cli.idxmax()
        k[3].metric("La plus utilisée", offres.set_index("id").nom.get(top, top))
        k[3].caption(f"{int(n_cli.max())} clients · {eur(act[act.code == top].cout_ref.sum())} / mois")
    else:
        k[3].metric("La plus utilisée", "—")

    f1, f2 = st.columns([1.3, 2], vertical_alignment="center")
    opts = [f"{s}s ({int(nb.get(s, 0))})" if s != "Retirée" else f"Retirées ({int(nb.get(s, 0))})" for s in L.STATUTS_OFFRE]
    filtre = f1.segmented_control("Statut", opts, default=opts[0], key="of_filtre", label_visibility="collapsed") or opts[0]
    statut = L.STATUTS_OFFRE[opts.index(filtre)]
    types = L.liste("type")
    f2.markdown("<div class='of-leg' style='text-align:right'>" + "".join(
        f"<span><span class='of-dot' style='background:{couleur(t, types)}'></span>{t}</span>" for t in types) + "</div>", unsafe_allow_html=True)

    vue = offres[offres.statut == statut]
    if vue.empty:
        st.info(f"Aucune offre « {statut} ».")
    items = list(vue.itertuples()) + ([None] if statut == "Active" else [])
    for i in range(0, len(items), 3):
        cols = st.columns(3)
        for col, o in zip(cols, items[i:i + 3]):
            with col.container(border=True):
                if o is None:
                    st.markdown("<div style='text-align:center;padding:38px 0 8px;color:#55625C'><div style='font-size:2rem;color:#0F6B5C'>＋</div>"
                                "<b>Créer une offre</b><br><span style='font-size:.85rem'>à partir de zéro ou d'une offre existante</span></div>",
                                unsafe_allow_html=True)
                    if st.button("Créer", key="of_new2", use_container_width=True):
                        nouvelle_offre()
                        aller("edition")
                    continue
                c = comp[comp.offre_id == o.id]
                rep = c.groupby("type").cout.sum().to_dict()
                desc = (o.description or "").split("—")[-1].strip() if o.description else ""
                desc = desc[:1].upper() + desc[1:]
                a, b = st.columns([1, 1.2], vertical_alignment="center")
                a.markdown(pill(o.statut), unsafe_allow_html=True)
                coche = b.checkbox("comparer", value=o.id in sel, key=f"of_chk_{o.id}")
                if coche and o.id not in sel and len(sel) < 4:
                    sel.append(o.id)
                    st.rerun()
                if not coche and o.id in sel:
                    sel.remove(o.id)
                    st.rerun()
                eff = f" · composition depuis {mois_lbl(o.date_effet)}" if isinstance(getattr(o, "date_effet", None), str) and o.date_effet else ""
                st.markdown(f"<div class='of-nom'>{o.nom}</div><div class='aff-sub'>{o.id} · {desc}{eff}</div>"
                            f"<div class='of-prix' style='margin-top:6px'>{eur(c.cout.sum())} <small>/ mois</small></div>{bar_html(rep)}"
                            f"<div class='of-res'>{''.join(f'<span>{x}</span>' for x in ressources(c))}</div>", unsafe_allow_html=True)
                a, b, cc = st.columns([1.5, 1.2, .6], vertical_alignment="center")
                a.markdown(f"👥 **{int(n_cli.get(o.id, 0))} client{'s' if n_cli.get(o.id, 0) > 1 else ''}**")
                if b.button("Modifier", key=f"of_mod_{o.id}", use_container_width=True, disabled=L.est_cloture()):
                    charger_offre(o.id)
                    aller("edition")
                with cc.popover("⋯"):
                    if st.button("📋 Dupliquer", key=f"of_dup_{o.id}", use_container_width=True):
                        nid = L.dupliquer_offre(o.id)
                        st.session_state["of_msg"] = f"Copie créée : {nid} (brouillon)."
                        charger_offre(nid)
                        aller("edition")
                    if o.statut == "Active" and st.button("⛔ Retirer…", key=f"of_ret_{o.id}", use_container_width=True, disabled=L.est_cloture()):
                        dlg_retirer(o.id)
                    if o.statut != "Active" and st.button("✅ Activer", key=f"of_act_{o.id}", use_container_width=True):
                        L.run("UPDATE offres SET statut='Active' WHERE id=?", (o.id,))
                        st.session_state["of_msg"] = f"{o.nom} est de nouveau proposée."
                        st.rerun()
                    if o.statut != "Active" and st.button("🗑️ Supprimer", key=f"of_del_{o.id}", use_container_width=True):
                        try:
                            L.supprimer_offre(o.id)
                            st.session_state["of_msg"] = f"{o.nom} supprimée."
                            st.rerun()
                        except ValueError as e:
                            st.error(str(e))
    if len(sel) == 1:
        st.caption("Cochez au moins une autre offre pour comparer.")


# ----------------------------------------------------------------------------- éditeur
def nouvelle_offre():
    st.session_state["of_form"] = dict(id=L.prochain_id("offres", "OF-", 2), nom="", desc="", statut="Brouillon", lignes=[], orig={}, nouvelle=True)


def charger_offre(oid):
    o = L.q("SELECT * FROM offres WHERE id=?", (oid,)).iloc[0]
    comp = L.q("SELECT asset_id, qte FROM composition WHERE offre_id=?", (oid,))
    st.session_state["of_form"] = dict(id=oid, nom=o.nom, desc=o.description or "", statut=o.statut, nouvelle=False,
                                       lignes=[[a, float(x)] for a, x in zip(comp.asset_id, comp.qte)],
                                       orig={a: float(x) for a, x in zip(comp.asset_id, comp.qte)})


def edition():
    f = st.session_state.get("of_form")
    if not f:
        aller("catalogue")
    assets = L.assets_df()
    m = L.mois_ref()
    cam = L.couts_assets_mensuels()
    unit = cam[m]
    info = assets.set_index("id")
    if st.button("← Catalogue", key="ofe_back", type="tertiary"):
        aller("catalogue")
    h1, h2 = st.columns([3, 1.4], vertical_alignment="center")
    h1.markdown(f"<div style='font-size:1.9rem;font-weight:700'>{f['nom'] or 'Nouvelle offre'} {pill(f['statut'])}</div>", unsafe_allow_html=True)
    g, dr = st.columns([1.5, 1], gap="large")
    with g:
        c1, c2, c3 = st.columns([1.2, 2.4, 1])
        f["nom"] = c1.text_input("Nom", f["nom"], key="ofe_nom")
        f["desc"] = c2.text_input("Description", f["desc"], key="ofe_desc", placeholder="ex. 1 GPU L40S, 8 vCPU, 64 Go — prototypage")
        f["statut"] = c3.selectbox("Statut", L.STATUTS_OFFRE, index=L.STATUTS_OFFRE.index(f["statut"]), key="ofe_statut")
        st.markdown(f"##### Composition · {len(f['lignes'])} asset{'s' if len(f['lignes']) > 1 else ''}")
        for i, (aid, qte) in enumerate(list(f["lignes"])):
            if aid not in info.index:
                continue
            with st.container(border=True):
                a, b, c, d_ = st.columns([4, 1.6, 1.1, .75], vertical_alignment="center")
                t = info.type[aid]
                diff = ""
                if not f["nouvelle"]:
                    if aid not in f["orig"]:
                        diff = "<span class='aff-badge aff-fin' style='margin-left:8px'>nouveau</span>"
                    elif f["orig"][aid] != qte:
                        diff = f"<span class='aff-badge aff-fin' style='margin-left:8px'>{f['orig'][aid]:g} → {qte:g}</span>"
                a.markdown(f"<span class='of-dot' style='background:{couleur(t)}'></span><b>{info.nom[aid]}</b>{diff}<br>"
                           f"<span class='aff-sub'>{aid} · {t} · {eur(unit.get(aid, 0), 2)} / unité / mois</span>", unsafe_allow_html=True)
                f["lignes"][i][1] = b.number_input("Qté", min_value=0.0, step=1.0, format="%g", value=float(qte), key=f"ofe_q_{aid}",
                                                   label_visibility="collapsed")
                c.markdown(f"<div class='aff-prix'>{eur(unit.get(aid, 0) * f['lignes'][i][1])}</div>", unsafe_allow_html=True)
                if d_.button("✕", key=f"ofe_del_{aid}", help="Retirer de l'offre"):
                    f["lignes"].pop(i)
                    st.rerun()
        retires = [a for a in f["orig"] if a not in {x for x, _ in f["lignes"]}]
        if retires and not f["nouvelle"]:
            st.caption("Retirés de la composition : " + ", ".join(f"{info.nom.get(a, a)} × {f['orig'][a]:g}" for a in retires))
        with st.container(border=True):
            st.markdown("**Ajouter un asset**")
            types = [t for t in L.liste("type") if t in set(assets[assets.statut == 'Actif'].type)]
            t = st.segmented_control("Type", types, default=types[0] if types else None, key="ofe_type", label_visibility="collapsed")
            dispo = assets[(assets.statut == "Actif") & (assets.type == t)]
            dans = {x for x, _ in f["lignes"]}
            cols = st.columns(3)
            for j, r in enumerate(dispo.itertuples()):
                lab = f"{'✓' if r.id in dans else '＋'} {r.nom} · {eur(unit.get(r.id, 0))}"
                if cols[j % 3].button(lab, key=f"ofe_add_{r.id}", use_container_width=True, disabled=r.id in dans):
                    f["lignes"].append([r.id, 1.0])
                    st.rerun()

    lignes = [(a, q) for a, q in f["lignes"] if q > 0]
    cout = sum(unit.get(a, 0) * q for a, q in lignes)
    cout_orig = sum(unit.get(a, 0) * q for a, q in f["orig"].items())
    change = not f["nouvelle"] and {(a, float(q)) for a, q in lignes} != {(a, float(q)) for a, q in f["orig"].items()}
    rep = {}
    for a, q in lignes:
        rep[info.type.get(a, "?")] = rep.get(info.type.get(a, "?"), 0) + unit.get(a, 0) * q
    with dr:
        delta = cout - cout_orig
        avant = f"<span style='color:#7A8580;text-decoration:line-through;font-size:1rem'>{eur(cout_orig)}</span> " if change else ""
        badge = f" <span class='aff-badge aff-fin'>{'+' if delta >= 0 else '−'}{eur(abs(delta))} / mois</span>" if change and abs(delta) >= .5 else ""
        grille = "".join(f"<span><span class='of-dot' style='background:{couleur(k)}'></span>{k} · {eur(v)} · {v / cout * 100:.0f} %</span>"
                         for k, v in sorted(rep.items(), key=lambda x: -x[1])) if cout else ""
        st.markdown(f"<div class='of-cost'><div class='aff-sub'>Coût mensuel de l'offre</div>"
                    f"<div style='display:flex;align-items:baseline;gap:8px'>{avant}<span style='font-size:2rem;font-weight:700'>{eur(cout)}</span>{badge}</div>"
                    f"<div class='aff-sub'>{eur(cout * 12)} / an · prix des assets de {L.MOIS_LONG[m - 1]} {L.annee()}</div>"
                    f"{bar_html(rep) if rep else ''}<div class='of-grid'>{grille}</div></div>", unsafe_allow_html=True)
        date_effet = None
        lig = L.lignes_offre(f["id"]) if not f["nouvelle"] else pd.DataFrame()
        if change:
            st.markdown("##### Quand appliquer la modification ?")
            with st.container(border=True):
                o = L.q("SELECT date_effet FROM offres WHERE id=?", (f["id"],))
                eff = L.d(o.date_effet.iloc[0]) if len(o) else None
                dep = max(eff or date(L.annee(), 1, 1), date(L.annee(), 1, 1))
                date_effet = choix_mois("À partir de", max(AU.mois_suivant_ref(), dep), "ofe_eff", depuis=dep)
                st.caption(f"Les mois avant {mois_lbl(date_effet)} gardent l'ancienne composition : la consommation déjà facturée ne change pas.")
                lig = L.lignes_offre(f["id"], date_effet)
                if len(lig):
                    a_ = L.annee()
                    impact = 0.0
                    for r in lig.itertuples():
                        for mm in range(1, 13):
                            dm = date(a_, mm, 1)
                            if dm >= date_effet and L.d(r.debut) <= dm and (L.d(r.fin) is None or L.d(r.fin) >= dm):
                                impact += delta * float(r.qte)
                    noms = sorted(set(lig.client))
                    st.markdown(f"**{len(noms)} client{'s' if len(noms) > 1 else ''} ont cette offre** → {'+' if delta >= 0 else '−'}{eur(abs(delta))} / mois chacun  \n"
                                f"<span class='aff-sub'>{', '.join(noms)}</span>", unsafe_allow_html=True)
                    if date_effet.year == a_:
                        st.markdown(f"Impact {a_} ({mois_lbl(date_effet)} → déc.) : **{'+' if impact >= 0 else '−'}{eur(abs(impact))}**")
                else:
                    st.caption("Aucun client n'a cette offre à partir de ce mois.")
        elif not f["nouvelle"]:
            st.caption(f"{len(lig)} ligne(s) d'affectation utilisent cette offre.")
        hist = L.historique_composition(f["id"]) if not f["nouvelle"] else pd.DataFrame()
        if len(hist):
            with st.expander("Compositions précédentes"):
                for (du, au), grp in hist.groupby(["du", "au"], dropna=False, sort=False):
                    st.markdown(f"**{mois_lbl(du) if isinstance(du, str) else 'origine'} → {mois_lbl(au)}** : "
                                + ", ".join(f"{n} × {q_:g}" for n, q_ in zip(grp.nom, grp.qte)))
    st.divider()
    b1, _, b3 = st.columns([1, 2.5, 1.3])
    if b1.button("Annuler", use_container_width=True, key="ofe_cancel"):
        aller("catalogue")
    if b3.button("💾 Enregistrer l'offre", type="primary", use_container_width=True, key="ofe_save"):
        noms = L.q("SELECT id, nom FROM offres")
        if not f["nom"].strip():
            st.error("Le nom est obligatoire.")
        elif not lignes:
            st.error("Ajoutez au moins un asset.")
        elif f["nom"].strip().lower() in {n.lower() for i, n in zip(noms.id, noms.nom) if i != f["id"]}:
            st.error("Une autre offre porte déjà ce nom.")
        else:
            try:
                L.enregistrer_offre(f["id"], f["nom"].strip(), f["desc"], f["statut"], lignes, date_effet if change else None)
                st.session_state["of_msg"] = f"Offre {f['nom']} enregistrée" + (f", nouvelle composition à partir de {mois_lbl(date_effet)}." if change else ".")
                aller("catalogue")
            except ValueError as e:
                st.error(str(e))


# ----------------------------------------------------------------------------- comparateur
def comparer():
    sel = st.session_state.get("of_cmp", [])
    offres = L.q("SELECT * FROM offres").set_index("id")
    sel = [x for x in sel if x in offres.index]
    if st.button("← Catalogue", key="ofc_back", type="tertiary"):
        aller("catalogue")
    h1, h2, h3 = st.columns([3, 1.3, 1.1], vertical_alignment="bottom")
    h1.title("Comparer les offres")
    h1.caption("Côte à côte, pour choisir l'offre d'un client ou préparer un devis. La meilleure valeur de chaque ligne est surlignée.")
    reste = [x for x in offres.index if x not in sel and offres.statut[x] != "Retirée"]
    if len(sel) < 4 and reste:
        aj = h2.selectbox("Ajouter une offre", [None] + reste, format_func=lambda x: "＋ Ajouter une offre" if x is None else offres.nom[x], key="ofc_add")
        if aj:
            st.session_state["of_cmp"].append(aj)
            aller("comparer")
    if len(sel) < 2:
        st.info("Choisissez au moins deux offres.")
        return
    comp = detail_offres()
    act, _ = clients_par_offre()
    n_cli = act.groupby("code").client_id.nunique()
    data = {}
    for o in sel:
        c = comp[comp.offre_id == o]
        mem = memoire_gpu(c)
        cout = float(c.cout.sum())
        gpu = " · ".join(f"{r.qte:g} × {r.nom}" for r in c[c.type == "GPU"].itertuples()) or "—"
        vcpu = c[(c.type == "CPU")].qte.sum()
        ram = c[c.type == "RAM"].qte.sum()
        sto = c[c.type == "Stockage"].qte.sum()
        lic = " · ".join(f"{r.nom} × {r.qte:g}" for r in c[c.type == "Licence"].itertuples()) or "—"
        res = " · ".join(f"{r.nom}" for r in c[c.type == "Réseau"].itertuples()) or "—"
        srv = " · ".join(f"{r.nom}" for r in c[c.type.isin(["Service", "Serveur"])].itertuples()) or "—"
        data[o] = {"Coût mensuel": (cout, eur(cout)), "Coût annuel": (cout * 12, eur(cout * 12)), "GPU": (None, gpu),
                   "Mémoire GPU totale": (mem, f"{mem:g} Go" if mem else "—"),
                   "Coût par Go de mémoire GPU": (cout / mem if mem else None, eur(cout / mem, 1) if mem else "—"),
                   "vCPU": (vcpu, f"{vcpu:g}" if vcpu else "—"), "RAM": (ram, f"{ram:g} Go" if ram else "—"),
                   "Stockage": (sto, f"{sto:g} To" if sto else "—"), "Licences": (None, lic), "Serveur et services": (None, srv),
                   "Réseau": (None, res), "Clients actuels": (int(n_cli.get(o, 0)), str(int(n_cli.get(o, 0)))),
                   "Description": (None, offres.description[o] or "—"), "_rep": c.groupby("type").cout.sum().to_dict()}
    mini = {"Coût mensuel", "Coût annuel", "Coût par Go de mémoire GPU"}
    maxi = {"Mémoire GPU totale", "vCPU", "RAM", "Stockage", "Clients actuels"}
    lignes = [k for k in data[sel[0]] if k != "_rep"]
    head = "".join(f"<th>{offres.nom[o]} {pill(offres.statut[o])}<div class='aff-sub' style='font-weight:400'>{o}</div></th>" for o in sel)
    barres = "".join("<td>" + bar_html(data[o]["_rep"]) + "</td>" for o in sel)
    rows = f"<tr><td class='l'>Répartition du coût</td>{barres}</tr>"
    for k in lignes:
        vals = [data[o][k][0] for o in sel]
        num = [v for v in vals if isinstance(v, (int, float)) and v]
        best = (min(num) if k in mini else max(num) if k in maxi else None) if len(num) >= 2 else None
        rows += f"<tr><td class='l'>{k}</td>" + "".join(
            f"<td class='{'best' if best is not None and data[o][k][0] == best else ''}'>{data[o][k][1]}</td>" for o in sel) + "</tr>"
    with st.container(border=True):
        st.markdown(f"<table class='of-cmp'><tr><th></th>{head}</tr>{rows}</table>", unsafe_allow_html=True)
        cols = st.columns([1.15] + [1] * len(sel))
        for col, o in zip(cols[1:], sel):
            a, b = col.columns(2)
            if a.button("🧾 Devis", key=f"ofc_dv_{o}", help="Créer un devis avec cette offre", use_container_width=True, disabled=offres.statut[o] != "Active"):
                import devis_ui
                devis_ui.nouveau_formulaire()
                st.session_state["dv_form"]["lignes"] = [dict(code=o, element="Offre", libelle=offres.nom[o], qte=1.0, remplace=None)]
                st.session_state["dv_form"]["objet"] = f"Offre {offres.nom[o]}"
                st.session_state["dv_vue"] = "edition"
                if PAGE_DEVIS is not None:
                    st.switch_page(PAGE_DEVIS)
            if b.button("✕ Retirer", key=f"ofc_rm_{o}", use_container_width=True):
                st.session_state["of_cmp"].remove(o)
                aller("comparer")
    tab = pd.DataFrame({offres.nom[o]: [data[o][k][1] for k in lignes] for o in sel}, index=lignes)
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        tab.to_excel(w, sheet_name="Comparaison")
    h3.download_button("⬇️ Exporter (Excel)", buf.getvalue(), "Comparaison_offres.xlsx", use_container_width=True)


# ----------------------------------------------------------------------------- retrait
@st.dialog("Retirer une offre", width="large")
def dlg_retirer(oid):
    offres = L.q("SELECT * FROM offres").set_index("id")
    nom = offres.nom[oid]
    st.markdown(f"### Retirer l'offre {nom}")
    st.caption("Une offre retirée n'est plus proposée dans les devis ni dans les affectations.")
    g, dr = st.columns([1, 1.6], gap="large")
    with g:
        mode = st.radio("Que deviennent les clients ?", ["garder", "migrer", "arreter"], key="ofr_mode",
                        format_func={"garder": "Ils gardent l'offre jusqu'à la fin prévue de leur ligne",
                                     "migrer": "Ils passent sur une autre offre", "arreter": "Ils arrêtent"}.get)
        cible, debut = None, AU.mois_suivant_ref()
        autres = [o for o in offres.index if o != oid and offres.statut[o] == "Active"]
        if mode == "migrer":
            if not autres:
                st.error("Aucune autre offre active.")
                return
            cout_o = L.couts_offres_mensuels()[L.mois_ref()]
            cible = st.selectbox("Nouvelle offre", autres, key="ofr_cible", format_func=lambda o: f"{offres.nom[o]} · {eur(cout_o.get(o, 0))}")
        if mode != "garder":
            debut = choix_mois("À partir de" if mode == "migrer" else "Premier mois sans l'offre", debut, "ofr_deb")
            if mode == "migrer":
                st.caption(f"{nom} s'arrête fin {mois_lbl(L.mois_precedent(debut))}, {offres.nom[cible]} démarre en {mois_lbl(debut)} "
                           "(même mécanisme que « Changer » dans Affectations).")
    lig = L.lignes_offre(oid, debut if mode != "garder" else None)
    choisis = None
    with dr:
        st.markdown(f"**Clients concernés · {lig.client_id.nunique()}**")
        if lig.empty:
            st.caption("Aucun client n'a cette offre : elle peut être retirée sans effet.")
        else:
            av = L.tarif(oid, debut)
            ap = L.tarif(cible, debut) if cible else 0.0
            bud = L.q("SELECT client_id, montant FROM budgets WHERE annee=?", (debut.year,)).set_index("client_id").montant
            t = pd.DataFrame({"inclure": True, "client_id": lig.client_id, "Client": lig.client, "Qté": lig.qte,
                              "Aujourd'hui": av * lig.qte, "Après": ap * lig.qte if mode != "garder" else av * lig.qte})
            t["Écart / mois"] = t["Après"] - t["Aujourd'hui"]
            alerte = []
            if mode == "migrer" and debut.year == L.annee():
                prev = L.conso_clients().set_index("client_id").total
                mois_rest = 12 - debut.month + 1
                for _, r in t.iterrows():
                    b = bud.get(r["client_id"])
                    alerte.append("⚠️ dépassé" if b and prev.get(r["client_id"], 0) + r["Écart / mois"] * mois_rest > b else "")
            else:
                alerte = [""] * len(t)
            t["Budget"] = alerte
            ed = st.data_editor(t.drop(columns="client_id"), hide_index=True, use_container_width=True, key="ofr_tab",
                                disabled=[c for c in t.columns if c != "inclure"],
                                column_config={"inclure": st.column_config.CheckboxColumn("✓", width=40),
                                               "Aujourd'hui": st.column_config.NumberColumn(format="%,.0f €"),
                                               "Après": st.column_config.NumberColumn(format="%,.0f €"),
                                               "Écart / mois": st.column_config.NumberColumn(format="%+,.0f €")})
            choisis = list(t.client_id[ed.inclure.values])
            tot = float(ed[ed.inclure]["Écart / mois"].sum())
            if mode == "migrer":
                st.markdown(f"Écart total : **{'+' if tot >= 0 else '−'}{eur(abs(tot))} / mois** · sur 12 mois : **{eur(tot * 12)}**")
            if mode != "garder":
                st.caption("Décochez un client pour le traiter à part : il garde l'offre jusqu'à sa date de fin.")
    b1, _, b3 = st.columns([1, 1.5, 2])
    if b1.button("Annuler", use_container_width=True, key="ofr_cancel"):
        st.rerun()
    n_sel = len(choisis) if choisis is not None else 0
    lab = {"garder": "Retirer l'offre", "migrer": f"Retirer et migrer {n_sel} ligne(s)", "arreter": f"Retirer et arrêter {n_sel} ligne(s)"}[mode]
    if b3.button(lab, type="primary", use_container_width=True, key="ofr_ok"):
        try:
            n = L.retirer_offre(oid, mode, cible, debut, choisis)
            st.session_state["of_msg"] = f"{nom} retirée" + (f" · {n} ligne(s) traitée(s) à partir de {mois_lbl(debut)}" if n else "") + "."
            if oid in st.session_state.get("of_cmp", []):
                st.session_state["of_cmp"].remove(oid)
            aller("catalogue")
        except ValueError as e:
            st.error(str(e))


# ----------------------------------------------------------------------------- page
def page():
    st.markdown(AU.CSS + CSS, unsafe_allow_html=True)
    if "of_msg" in st.session_state:
        st.success(st.session_state.pop("of_msg"))
    vue = st.session_state.get("of_vue", "catalogue")
    if vue == "edition" and not L.est_cloture():
        edition()
    elif vue == "comparer":
        comparer()
    else:
        catalogue()
