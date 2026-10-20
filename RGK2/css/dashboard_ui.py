"""Dashboard : vue d'ensemble, consommation par asset, par client, budget et couverture du parc."""
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

import logic as L
from affectations_ui import eur, mois_lbl
from offres_ui import couleur

PAGES = {}  # renseigné par app.py : {"affectation": page, "devis": page}
TEAL = "#0F6B5C"
MOIS_EXPR = "['Janv.','Févr.','Mars','Avr.','Mai','Juin','Juil.','Août','Sept.','Oct.','Nov.','Déc.'][datum.value-1]"

CSS = """
<style>
.db-tile{border:1px solid #DCE6E2;border-radius:10px;padding:9px 11px;background:#fff;height:100%}
.db-tile.on{border:2px solid #0F6B5C;background:#F4FAF7}
.db-tile .t{font-size:.8rem;color:#55625C}.db-tile .v{font-size:1.15rem;font-weight:700;margin-top:2px}.db-tile .p{font-size:.75rem;color:#7A8580}
.db-al{display:flex;gap:10px;padding:8px 0;border-bottom:1px solid #EEF1EF;font-size:.88rem;align-items:flex-start}
.db-al b.i{width:26px;height:26px;border-radius:7px;display:flex;align-items:center;justify-content:center;flex:none;color:#fff;font-size:.8rem}
.db-dot{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:5px;vertical-align:middle}
</style>"""


def pct(x, d=0):
    return f"{x * 100:.{d}f} %".replace(".", ",")


def spark(vals, col, w=110, h=26):
    vals = [float(v) for v in vals] or [0]
    mx = max(vals) or 1
    if len(vals) == 1:
        vals = vals * 2
    pts = " ".join(f"{i * w / (len(vals) - 1):.1f},{h - v / mx * (h - 3) - 1:.1f}" for i, v in enumerate(vals))
    return f"<svg width='{w}' height='{h}'><polyline points='{pts}' fill='none' stroke='{col}' stroke-width='2'/></svg>"


def fr(v, suffixe=" €"):
    return f"{v:,.0f}".replace(",", " ") + suffixe


def hbar(df, cat, val, titre, coul, h=None, suffixe=" €"):
    df = df.sort_values(val, ascending=False).copy()
    df["_lab"] = [fr(v, suffixe) if suffixe == " €" else f"{v:g}{suffixe}" for v in df[val]]
    base = alt.Chart(df, title=alt.Title(titre, anchor="start", fontSize=14)).encode(
        y=alt.Y(f"{cat}:N", sort="-x", title=None, axis=alt.Axis(labelLimit=170, labelFontSize=12, labelOverlap=False, ticks=False, domain=False)))
    bars = base.mark_bar(color=coul, cornerRadiusEnd=3, height=16).encode(
        x=alt.X(f"{val}:Q", title=None, axis=None, scale=alt.Scale(domain=[0, float(df[val].max() or 1) * 1.35])),
        tooltip=[alt.Tooltip(f"{cat}:N", title=""), alt.Tooltip("_lab:N", title="Montant")])
    txt = base.mark_text(align="left", dx=4, fontSize=11.5, color="#333").encode(x=f"{val}:Q", text="_lab:N")
    return (bars + txt).properties(height=h or max(28 * len(df) + 10, 110))


def filtres():
    cli = L.q("SELECT * FROM clients")
    c = st.columns([1, 1, 1.4, 1.6])
    pays = c[0].multiselect("Pays", L.liste("pays"), placeholder="Tous", key="db_p")
    ent = c[1].multiselect("Entité", L.liste("entite"), placeholder="Toutes", key="db_e")
    noms = c[2].multiselect("Client", sorted(cli.nom), placeholder="Tous", key="db_c")
    c[3].markdown(f"<div style='text-align:right;color:#55625C;padding-top:30px;font-size:.88rem'>Exercice {L.annee()} · réel jusqu'à "
                  f"{L.MOIS_LONG[L.mois_ref() - 1]} · prévision ensuite</div>", unsafe_allow_html=True)
    m = pd.Series(True, index=cli.index)
    if pays:
        m &= cli.pays.isin(pays)
    if ent:
        m &= cli.entite.isin(ent)
    if noms:
        m &= cli.nom.isin(noms)
    return set(cli[m].id), bool(pays or ent or noms)


def lien(page_cle, label, **etat):
    p = PAGES.get(page_cle)
    if p is None:
        return
    if st.button(label, key=f"db_go_{page_cle}_{label}", type="tertiary"):
        st.session_state.update(etat)
        st.switch_page(p)


# =============================================================================== VUE D'ENSEMBLE
def vue_ensemble(d):
    cc, ids, mr = d["cc"], d["ids"], d["mr"]
    prec = float(cc[mr - 1].sum()) if mr > 1 else 0.0
    bud = L.budgets_df().set_index("client_id").budget
    bud_tot = float(bud[bud.index.isin(ids)].sum())
    parc = L.cout_parc_mensuel()[mr]
    k = st.columns(4)
    k[0].metric(f"Consommation réelle (janv. → {L.MOIS[mr - 1].lower()})", eur(cc.reel.sum()))
    k[0].caption(f"{int((cc.reel > 0).sum())} clients consommateurs")
    k[1].metric("Prévision fin d'année", eur(cc.total.sum()))
    if bud_tot:
        k[1].progress(min(cc.total.sum() / bud_tot, 1.0), text=f"{pct(cc.total.sum() / bud_tot)} du budget ({eur(bud_tot)})")
    k[2].metric(L.MOIS_LONG[mr - 1].capitalize(), eur(cc.mois_ref.sum()),
                delta=f"{(cc.mois_ref.sum() / prec - 1) * 100:+.1f} % vs {L.MOIS_LONG[mr - 2]}".replace(".", ",") if prec else None)
    k[3].metric(f"{'Part' if d['filtre'] else 'Couverture'} du parc ({L.MOIS[mr - 1].lower()})", pct(cc.mois_ref.sum() / parc) if parc else "—",
                help="Montant refacturé du mois / coût mensuel de tous les assets actifs du parc")
    k[3].caption(f"{eur(cc.mois_ref.sum())} refacturés / {eur(parc)} de coût")

    g, dr = st.columns([2.3, 1], gap="medium")
    with g.container(border=True):
        ty = d["types"]
        long = ty.rename_axis("Type").reset_index().melt(id_vars="Type", var_name="n", value_name="€")
        long["n"] = long.n.astype(int)
        long["Période"] = ["Réel" if n <= mr else "Prévision" for n in long.n]
        types = [t for t in ty.sum(axis=1).sort_values(ascending=False).index if ty.loc[t].sum() > 0]
        long = long[long.Type.isin(types)]
        ch = (alt.Chart(long, title=alt.Title("Consommation mensuelle par type d'asset", anchor="start", fontSize=14))
              .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
              .encode(x=alt.X("n:O", title=None, axis=alt.Axis(labelExpr=MOIS_EXPR, labelAngle=0)),
                      y=alt.Y("€:Q", title=None, axis=alt.Axis(labelExpr="format(datum.value / 1000, ',.0f') + ' k'")),
                      color=alt.Color("Type:N", sort=types, scale=alt.Scale(domain=types, range=[couleur(t) for t in types]),
                                      legend=alt.Legend(orient="top", title=None, columns=8)),
                      order=alt.Order("ordre:Q"),
                      opacity=alt.Opacity("Période:N", scale=alt.Scale(domain=["Réel", "Prévision"], range=[1, .45]), legend=None),
                      tooltip=[alt.Tooltip("n:O", title="Mois"), "Type", "Période", alt.Tooltip("€:Q", format=",.0f")])
              .transform_calculate(ordre=f"indexof({types}, datum.Type)").properties(height=330))
        st.altair_chart(ch, use_container_width=True)
        st.caption("Les mois après le mois de référence (plus clairs) sont des prévisions.")
    with dr.container(border=True):
        st.markdown("**À surveiller**")
        alertes(d)

    c1, c2, c3 = st.columns(3)
    with c1.container(border=True):
        st.altair_chart(hbar(cc.groupby("pays").reel.sum().reset_index().query("reel > 0"), "pays", "reel", "Par pays (réel)", TEAL), use_container_width=True)
    with c2.container(border=True):
        st.altair_chart(hbar(cc.groupby("entite").reel.sum().reset_index().query("reel > 0"), "entite", "reel", "Par entité (réel)", "#4C9C8A"),
                        use_container_width=True)
    with c3.container(border=True):
        st.altair_chart(hbar(cc.nlargest(8, "reel")[["client", "reel"]].query("reel > 0"), "client", "reel", "Top clients (réel)", "#C2702E"),
                        use_container_width=True)


def alertes(d):
    cc, ids, mr = d["cc"], d["ids"], d["mr"]
    items = []
    bud = L.budgets_df().set_index("client_id").budget
    x = cc.assign(b=cc.client_id.map(bud))
    x = x[(x.b > 0) & (x.total > x.b)].assign(p=lambda t: t.total / t.b).sort_values("p", ascending=False)
    if len(x):
        noms = ", ".join(f"{n} ({pct(p)})" for n, p in zip(x.client.head(3), x.p.head(3)))
        items.append(("#9C1C14", "!", f"<b>{len(x)} client{'s' if len(x) > 1 else ''} au-delà du budget</b> en prévision : {noms}", "affectation"))
    occ = d["occ"]
    gpu0 = occ[(occ.type == "GPU") & (occ.parc > 0) & (occ.utilises == 0) & (occ.statut == "Actif")]
    if len(gpu0):
        items.append(("#C2702E", "GPU", f"<b>{len(gpu0)} modèle{'s' if len(gpu0) > 1 else ''} de GPU inutilisé{'s' if len(gpu0) > 1 else ''}</b> : "
                      f"{', '.join(n.replace('GPU ', '') for n in gpu0.nom)} — {eur(gpu0.cout_parc.sum())} / mois de parc non refacturé", None))
    if not L.est_cloture():
        pleins = [p for p in L.pools_capacite() if p["etat"] in ("Plein", "Bientôt plein")]
        if pleins:
            items.append(("#9C1C14", "▮", f"<b>{len(pleins)} pool{'s' if len(pleins) > 1 else ''} plein{'s' if len(pleins) > 1 else ''} ou presque</b> : "
                          + ", ".join(p["label"] for p in pleins[:3]) + " (onglet Capacité)", None))
        dl = L.devis_liste()
        att = dl[(dl.statut_aff == "Envoyé") & dl.client_id.isin(ids)]
        if len(att):
            rel = sum((e - date.today()).days <= 7 for e in att.expire_le)
            items.append(("#3A5BA0", "🧾", f"<b>{len(att)} devis en attente</b> : {eur(att.mensuel.sum())} / mois" + (f", dont {rel} à relancer" if rel else ""), "devis"))
        ref = date(L.annee(), mr, 1)
        h = L.ajouter_mois(ref, 3)
        l_ = d["lignes"][d["lignes"].element.isin(["Offre", "Option"]) & d["lignes"].client_id.isin(ids)].copy()
        l_["deb"], l_["fin_"] = l_.debut.map(L.d), l_.fin.map(L.d)
        suites = set(zip(l_.client_id, l_.deb))
        fins = l_[l_.fin_.notna() & (l_.fin_ >= ref) & (l_.fin_ < h)]
        fins = fins[[(c_, L.ajouter_mois(f_, 1)) not in suites for c_, f_ in zip(fins.client_id, fins.fin_)]]
        if len(fins):
            det = " · ".join(f"{c_} : {lb} ({mois_lbl(f_)})" for c_, lb, f_ in zip(fins.client.head(2), fins.libelle.head(2), fins.fin_.head(2)))
            items.append(("#7A8580", "⏹", f"<b>{len(fins)} fin{'s' if len(fins) > 1 else ''} prévue{'s' if len(fins) > 1 else ''}</b> d'ici 3 mois : {det}", "affectation"))
    if not items:
        st.caption("Rien à signaler.")
    for col, ic, txt, page in items:
        st.markdown(f"<div class='db-al'><b class='i' style='background:{col}'>{ic}</b><div>{txt}</div></div>", unsafe_allow_html=True)
    cibles = {p for *_, p in items if p}
    if "affectation" in cibles:
        lien("affectation", "→ Ouvrir Affectations")
    if "devis" in cibles:
        lien("devis", "→ Ouvrir Devis", dv_vue="liste")


# =============================================================================== PAR ASSET
def par_asset(d):
    det, mr, occ = d["detail"], d["mr"], d["occ"]
    if L.est_cloture():
        st.info("Exercice clôturé : seuls les montants par type d'asset ont été figés. Le détail par asset est disponible pour les exercices ouverts.")
        ty = d["types"]
        st.dataframe(ty.assign(Total=ty.sum(axis=1)).rename(columns={m: L.MOIS[m - 1] for m in range(1, 13)}), use_container_width=True,
                     column_config={c: st.column_config.NumberColumn(format="%,.0f €") for c in L.MOIS + ["Total"]})
        return
    detf = det[det.client_id.isin(d["ids"])]
    reel = detf[detf.m <= mr]
    par_type = reel.groupby("type").montant.sum().sort_values(ascending=False)
    tot = float(par_type.sum()) or 1
    types = [t for t in par_type.index if par_type[t] > 0]
    if not types:
        st.info("Aucune consommation pour cette sélection.")
        return
    choix = st.session_state.get("db_type") if st.session_state.get("db_type") in types else ("GPU" if "GPU" in types else types[0])
    for i in range(0, len(types), 8):
        cols = st.columns(8)
        for col, t in zip(cols, types[i:i + 8]):
            serie = [reel[(reel.type == t) & (reel.m == m)].montant.sum() for m in range(1, mr + 1)]
            col.markdown(f"<div class='db-tile {'on' if t == choix else ''}'><div class='t'><span class='db-dot' style='background:{couleur(t)}'></span>{t}</div>"
                         f"<div class='v'>{f'{par_type[t] / 1000:,.0f}'.replace(',', ' ')} k€</div><div class='p'>{pct(par_type[t] / tot)}</div>{spark(serie, couleur(t))}</div>",
                         unsafe_allow_html=True)
    choix = st.segmented_control("Type d'asset", types, default=choix, key="db_type", label_visibility="collapsed") or choix

    o = occ[(occ.type == choix) & ((occ.parc > 0) | (occ.utilises > 0))].copy()
    r_asset = reel[reel.type == choix].groupby("asset_id").montant.sum()
    o["reel"] = r_asset.reindex(o.index).fillna(0)
    o = o.sort_values(["refacture", "cout_parc"], ascending=False)
    g, dr = st.columns([2.5, 1], gap="medium")
    with g.container(border=True):
        st.markdown(f"**{choix} · utilisation du parc en {L.MOIS_LONG[mr - 1]}** <span class='aff-sub'>· unités affectées (offres + options, tous clients) / unités du parc</span>",
                    unsafe_allow_html=True)
        t = pd.DataFrame({"Asset": o.nom, "Utilisés": [f"{u:g} / {p:g}" for u, p in zip(o.utilises, o.parc)],
                          "Occupation": [x * 100 if x is not None else None for x in o.occupation],
                          "Refacturé": o.refacture, "Coût parc": o.cout_parc, "Inutilisé": o.inutilise,
                          "Réel cumulé": o.reel})
        st.dataframe(t, hide_index=True, use_container_width=True, height=min(36 * (len(t) + 1) + 3, 420),
                     column_config={"Asset": st.column_config.TextColumn(width=190),
                                    "Utilisés": st.column_config.TextColumn("Utilisés / parc", width="small"),
                                    "Occupation": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100, width="small"),
                                    "Refacturé": st.column_config.NumberColumn("Refacturé / mois", format="%,.0f €"),
                                    "Coût parc": st.column_config.NumberColumn("Coût parc / mois", format="%,.0f €"),
                                    "Inutilisé": st.column_config.NumberColumn("Inutilisé / mois", format="%,.0f €", help="Coût des unités du parc non affectées"),
                                    "Réel cumulé": st.column_config.NumberColumn("Réel cumulé", format="%,.0f €",
                                                                                 help=f"Consommation de janvier à {L.MOIS_LONG[mr - 1]} (sélection des filtres)")})
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Unités utilisées", f"{o.utilises.sum():g} / {o.parc.sum():g}")
        m2.metric("Refacturé / mois", eur(o.refacture.sum()))
        m3.metric("Coût du parc / mois", eur(o.cout_parc.sum()), help="Assets actifs uniquement")
        m4.metric("Capacité inutilisée", eur(o.inutilise.sum()), help="Coût des unités du parc non affectées")
        st.caption("Occupation : rouge à surveiller à partir de 90 % (risque de saturation), 0 % = asset acheté mais non affecté.")
    with dr.container(border=True):
        top = reel[reel.type == choix].groupby("client").montant.sum().nlargest(8).reset_index()
        st.altair_chart(hbar(top, "client", "montant", f"Qui consomme ({choix}) ?", couleur(choix)), use_container_width=True)
        pa = reel[reel.type == choix].groupby("nom").montant.sum().reset_index()
        st.altair_chart(hbar(pa, "nom", "montant", "Par asset (réel)", "#4C9C8A"), use_container_width=True)
    with st.container(border=True):
        ev = detf[detf.type == choix].groupby(["nom", "m"]).montant.sum().reset_index()
        ev["Période"] = ["Réel" if m <= mr else "Prévision" for m in ev.m]
        st.altair_chart(alt.Chart(ev, title=alt.Title(f"{choix} : consommation mensuelle par asset", anchor="start", fontSize=14)).mark_bar()
                        .encode(x=alt.X("m:O", title=None, axis=alt.Axis(labelExpr=MOIS_EXPR, labelAngle=0)),
                                y=alt.Y("montant:Q", title=None, axis=alt.Axis(labelExpr="format(datum.value / 1000, ',.0f') + ' k'")),
                                color=alt.Color("nom:N", title=None, legend=alt.Legend(orient="top"),
                                                scale=alt.Scale(range=["#0F6B5C", "#4C9C8A", "#9CC7BB", "#C2702E", "#E3A66F", "#3A5BA0", "#7A8580", "#B0B8B4"])),
                                opacity=alt.Opacity("Période:N", scale=alt.Scale(domain=["Réel", "Prévision"], range=[1, .45]), legend=None),
                                tooltip=[alt.Tooltip("nom:N", title="Asset"), alt.Tooltip("m:O", title="Mois"), alt.Tooltip("montant:Q", format=",.0f")])
                        .properties(height=240), use_container_width=True)


# =============================================================================== CAPACITÉ
ETATS = {"Plein": "🔴 Plein", "Bientôt plein": "🟠 Bientôt plein", "Sur-dimensionné": "🟡 Sur-dimensionné", "Inutilisé": "⚪ Inutilisé", "OK": "🟢 OK"}
PALETTE = ["#0F6B5C", "#4C9C8A", "#9CC7BB", "#C2702E", "#E3A66F", "#3A5BA0", "#7A8580", "#B0B8B4", "#2E8B74", "#D9A5B3", "#8FA9D6", "#C9B458"]


def capacite(d):
    if L.est_cloture():
        st.info("Exercice clôturé : la capacité se suit sur l'exercice ouvert.")
        return
    pools = L.pools_capacite()
    if not pools:
        st.info("Aucune ressource à capacité suivie : ajoutez des GPU ou des instances cloud (avec une quantité de parc) dans Assets.")
        return
    vc = [p for p in pools if p["vcpu_unite"] and p["kind"] in ("part", "entiere")]
    gp = [p for p in pools if p["gpu_unite"]]
    k = st.columns(4)
    cap_v = sum(p["capacite"] * p["vcpu_unite"] for p in vc)
    al_v = sum(p["alloue"] * p["vcpu_unite"] for p in vc)
    rs_v = sum(p["reserve"] * p["vcpu_unite"] for p in vc)
    k[0].metric("vCPU cloud alloués", f"{al_v:g} / {cap_v:g}" if cap_v else "—")
    if cap_v:
        k[0].caption(f"{pct(al_v / cap_v)} · + {rs_v:g} demandés par des devis")
    cap_g = sum(p["capacite"] * p["gpu_unite"] for p in gp)
    al_g = sum(p["alloue"] * p["gpu_unite"] for p in gp)
    k[1].metric("GPU alloués", f"{al_g:g} / {cap_g:g}" if cap_g else "—")
    inut = [p for p in gp if p["etat"] == "Inutilisé"]
    if cap_g:
        k[1].caption(f"{pct(al_g / cap_g)}" + (f" · {sum(p['capacite'] * p['gpu_unite'] for p in inut):g} GPU jamais affectés" if inut else ""))
    pleins = [p for p in pools if p["etat"] in ("Plein", "Bientôt plein")]
    k[2].metric("Pools pleins ou presque", len(pleins))
    k[2].caption(" · ".join(p["label"].split(" · ")[-1] for p in pleins[:3]) or "aucun")
    sats = [(p, p["saturation_date"]) for p in pools if p["saturation_date"] and p["saturation"] != "déjà plein"]
    deja = [p for p in pools if p["saturation"] == "déjà plein"]
    if deja:
        k[3].metric("Saturation", "déjà atteinte")
        k[3].caption(" · ".join(p["label"] for p in deja[:2]))
    elif sats:
        p0, m0 = min(sats, key=lambda x: x[1])
        k[3].metric("Prochaine saturation", mois_lbl(m0))
        k[3].caption(p0["label"])
    else:
        k[3].metric("Prochaine saturation", "aucune sur 12 mois")
        k[3].caption("avec les affectations et devis en cours")

    t = pd.DataFrame([dict(id=p["id"], Pool=p["label"], Détail=p["detail"], Capacité=p["capacite"], Alloué=p["alloue"], Réservé=p["reserve"],
                           Libre=p["libre"], Occupation=min(p["alloue"] / p["capacite"] * 100, 100),
                           **{"Avec devis": min((p["alloue"] + p["reserve"]) / p["capacite"] * 100, 120)},
                           **{"Utilisation réelle": float(p["utilisation"]) if p["utilisation"] is not None else float("nan")}, État=ETATS[p["etat"]],
                           Saturation=p["saturation"]) for p in pools])
    ordre = {"Plein": 0, "Bientôt plein": 1, "Sur-dimensionné": 2, "OK": 3, "Inutilisé": 4}
    t["_o"] = [ordre[p["etat"]] for p in pools]
    t = t.sort_values(["_o", "Occupation"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    with st.container(border=True):
        st.markdown(f"**Capacité par pool** <span class='aff-sub'>· un pool = une flavor cloud ou un modèle de GPU · alloué = affectations de "
                    f"{L.MOIS_LONG[d['mr'] - 1]} · réservé = devis envoyés en attente · utilisation réelle = moyenne 30 jours de la supervision</span>",
                    unsafe_allow_html=True)
        ev = st.dataframe(t.drop(columns="id"), hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
                          key="db_cap_tab", height=36 * (len(t) + 1) + 3,
                          column_config={"Pool": st.column_config.TextColumn(width="medium"), "Détail": st.column_config.TextColumn(width="small"),
                                         "Capacité": st.column_config.NumberColumn(format="%g", width="small"),
                                         "Alloué": st.column_config.NumberColumn(format="%g", width="small"),
                                         "Réservé": st.column_config.NumberColumn(format="%g", width="small"),
                                         "Libre": st.column_config.NumberColumn(format="%g", width="small"),
                                         "Occupation": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
                                         "Avec devis": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=100),
                                         "Utilisation réelle": st.column_config.NumberColumn(format="%.0f %%", help="Mesurée par la supervision (import)")})
        st.caption("Cliquez sur un pool pour voir sa projection, ses instances et l'utilisation par client.")
    rows = ev.selection.rows if ev and ev.selection else []
    sel_id = t.id.iloc[rows[0]] if rows else st.session_state.get("db_pool", t.id.iloc[0])
    st.session_state["db_pool"] = sel_id
    p = next(x for x in pools if x["id"] == sel_id)

    g, dr = st.columns([1.6, 1], gap="medium")
    with g.container(border=True):
        pj = pd.DataFrame([dict(m=m, mois=mois_lbl(m), Alloué=v[0], Réservé=v[1]) for m, v in p["projection"].items()])
        long = pj.melt(id_vars=["m", "mois"], value_vars=["Alloué", "Réservé"], var_name="Nature", value_name="u")
        bars = alt.Chart(long).mark_bar().encode(
            x=alt.X("mois:N", sort=pj.mois.tolist(), title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("u:Q", title=p["unite"], scale=alt.Scale(domain=[0, max(p["capacite"], float((pj.Alloué + pj.Réservé).max())) * 1.15])),
            color=alt.Color("Nature:N", scale=alt.Scale(domain=["Alloué", "Réservé"], range=[TEAL, "#E3A66F"]), legend=alt.Legend(orient="top", title=None)),
            order=alt.Order("Nature:N", sort="ascending"), tooltip=["mois", "Nature", alt.Tooltip("u:Q", format="g")])
        cap = alt.Chart(pd.DataFrame({"y": [p["capacite"]], "t": [f"capacité {p['capacite']:g} {p['unite']}"]}))
        regle = cap.mark_rule(color="#9C1C14", strokeWidth=2.5).encode(y="y:Q")
        txt = cap.mark_text(align="left", dx=4, dy=-7, color="#9C1C14", x=0).encode(y="y:Q", text="t:N")
        st.markdown(f"**Projection · {p['label']}** <span class='aff-sub'>· 12 prochains mois · état : {ETATS[p['etat']]} · saturation : {p['saturation']}</span>",
                    unsafe_allow_html=True)
        st.altair_chart((bars + regle + txt).properties(height=260), use_container_width=True)
        st.caption("Alloué = lignes en cours et à venir (Affectations) · réservé = devis envoyés · ligne rouge = capacité du parc "
                   "(ajoutez une instance dans Assets pour voir l'effet d'un achat).")
    with dr.container(border=True):
        st.markdown("**Recommandations**")
        coul = {"Acheter": "#9C1C14", "Anticiper": "#C2702E", "Réduire": "#7A3F0E", "Revoir": "#55625C"}
        fond = {"Acheter": "#F8E1DF", "Anticiper": "#FDE3C8", "Réduire": "#FFF1DC", "Revoir": "#EEF1EF"}
        rec = L.recommandations(pools)
        if not rec:
            st.caption("Rien à signaler.")
        for tag, txt_ in rec[:7]:
            st.markdown(f"<div class='db-al'><span style='background:{fond[tag]};color:{coul[tag]};font-weight:700;border-radius:10px;padding:1px 9px;"
                        f"font-size:.75rem;white-space:nowrap'>{tag}</span><div>{txt_}</div></div>", unsafe_allow_html=True)

    s_ = L.seuils_capacite()
    g, dr = st.columns([1, 1.15], gap="medium")
    al = L.allocations(p["id"], date(L.annee(), d["mr"], 1))
    clients = sorted(set(al.client))
    couleurs = {c_: PALETTE[i % len(PALETTE)] for i, c_ in enumerate(clients)}
    with g.container(border=True):
        if p["kind"] == "part":
            st.markdown(f"**Instances** <span class='aff-sub'>· placement des parts ({p['unite']}) par client, calculé dans l'ordre des dates de début</span>",
                        unsafe_allow_html=True)
            for i in L.placement(p["id"]):
                occ = i["taille"] - i["libre"]
                barre = "".join(f"<div title='{x['client']} · {x['unites']:g}' style='width:{x['unites'] / i['taille'] * 100:.2f}%;background:{couleurs[x['client']]};"
                                f"border-right:2px solid #fff'></div>" for x in i["parts"])
                leg = " ".join(f"<span style='white-space:nowrap;margin-right:8px'><span class='db-dot' style='background:{couleurs[x['client']]}'></span>"
                               f"{x['client']} · {x['unites']:g}{' (réparti)' if x['partage'] else ''}</span>" for x in i["parts"])
                vide = f"<span class='aff-sub'>vide · {fr(p['cout_instance'])} / mois sans refacturation</span>" if not i["parts"] else ""
                st.markdown(f"<div style='margin:6px 0 12px'><div style='display:flex;justify-content:space-between;font-size:.9rem'><b>Instance {i['num']}</b>"
                            f"<span class='aff-sub'>{occ:g} / {i['taille']:g} {p['unite']}</span></div>"
                            f"<div style='display:flex;height:22px;border-radius:6px;overflow:hidden;background:#EEF1EF;margin-top:4px'>{barre}</div>"
                            f"<div style='font-size:.78rem;margin-top:4px'>{leg}{vide}</div></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"**Répartition par client** <span class='aff-sub'>· {p['alloue']:g} / {p['capacite']:g} {p['unite']}</span>", unsafe_allow_html=True)
            if al.empty:
                st.caption("Rien d'alloué.")
            else:
                gq = al.groupby("client").unites.sum().reset_index()
                st.altair_chart(hbar(gq.rename(columns={"unites": "u"}), "client", "u", "", TEAL, suffixe=f" {p['unite']}"), use_container_width=True)
    with dr.container(border=True):
        st.markdown(f"**Alloué vs utilisé, par client** <span class='aff-sub'>· moyenne 30 jours</span>", unsafe_allow_html=True)
        if al.empty:
            st.caption("Aucune allocation.")
        else:
            a2 = al.groupby(["client_id", "client"]).unites.sum().reset_index()
            a2["util"] = a2.client_id.map(p["par_client"])

            def etat(u):
                if u is None or pd.isna(u):
                    return "— pas de mesure"
                if u >= s_["sature"]:
                    return "🔴 Saturé"
                if u < s_["inactif"]:
                    return "⚪ Inactif ?"
                if u < s_["sous"]:
                    return "🟡 Sur-dimensionné"
                return "🟢 OK"

            def sugg(r):
                u = r.util
                if u is None or pd.isna(u):
                    return ""
                if u >= s_["sature"]:
                    return f"proposer + {max(1, round(r.unites * .5)):g}"
                if u < s_["sous"]:
                    return f"proposer − {max(1, round(r.unites * (1 - max(u, 1) / 50))):g}"
                return ""
            a2["État"] = a2.util.map(etat)
            a2["Suggestion"] = a2.apply(sugg, axis=1)
            st.dataframe(a2[["client", "unites", "util", "État", "Suggestion"]].sort_values("unites", ascending=False), hide_index=True, use_container_width=True,
                         column_config={"client": "Client", "unites": st.column_config.NumberColumn("Alloué", format="%g", width="small",
                                                                                                     help=f"en {p['unite']}"),
                                        "util": st.column_config.ProgressColumn("Utilisation", format="%.0f %%", min_value=0, max_value=100, width="small"),
                                        "État": st.column_config.TextColumn(width="small")})
            st.caption(f"Seuils : saturé ≥ {s_['sature']:g} % · sur-dimensionné < {s_['sous']:g} % · inactif < {s_['inactif']:g} %.")

    with st.expander("Mesures de supervision et seuils"):
        nb = L.q("SELECT COUNT(*) AS n, MAX(date) AS dmax FROM mesures").iloc[0]
        st.markdown(f"**{int(nb.n)} mesures** importées" + (f" · dernière date : {L.d(nb.dmax):%d/%m/%Y}" if nb.dmax else ""))
        st.caption("Format CSV (séparateur « ; ») : Date ; Asset (ID ou nom de l'instance) ; Client (ID ou nom) ; CPU moyen % ; CPU max % ; GPU moyen %. "
                   "Export quotidien d'IBM Cloud Monitoring, de Prometheus ou de NVIDIA DCGM (une ligne par instance, client et jour).")
        modele = L.DATA_DIR / "Import_Mesures_exemple.csv"
        if modele.exists():
            st.download_button("Télécharger un fichier d'exemple", modele.read_bytes(), modele.name, "text/csv")
        f = st.file_uploader("Fichier de mesures", type=["csv"], key="db_mes")
        if f is not None and st.button("Importer les mesures", type="primary"):
            rap = L.importer_mesures(L.lire_csv(f))
            st.success(f"{rap['importées']} mesures importées" + (f", {len(rap['ignorées'])} lignes ignorées" if rap["ignorées"] else ""))
        c1, c2, c3, c4 = st.columns(4)
        v1 = c1.number_input("Saturé à partir de (%)", 50, 100, int(s_["sature"]))
        v2 = c2.number_input("Sur-dimensionné sous (%)", 1, 80, int(s_["sous"]))
        v3 = c3.number_input("Inactif sous (%)", 0, 50, int(s_["inactif"]))
        v4 = c4.number_input("Alerte parc à partir de (%)", 50, 100, int(s_["alerte"]))
        if st.button("Enregistrer les seuils"):
            for k_, v in (("seuil_sature", v1), ("seuil_sous", v2), ("seuil_inactif", v3), ("seuil_alerte_parc", v4)):
                L.set_param(k_, v)
            st.rerun()


# =============================================================================== PAR CLIENT
def par_client(d):
    cc, mr = d["cc"].copy(), d["mr"]
    bud = L.budgets_df().set_index("client_id").budget
    cc["budget"] = cc.client_id.map(bud).fillna(0)
    cc["pct"] = [t / b * 100 if b else None for t, b in zip(cc.total, cc.budget)]
    avant = cc[max(mr - 3, 1)]
    cc["croissance"] = [(x / y - 1) * 100 if y else (100.0 if x else 0.0) for x, y in zip(cc.mois_ref, avant)]
    cc = cc[cc.total > 0]
    if cc.empty:
        st.info("Aucune consommation pour cette sélection.")
        return
    c1, c2 = st.columns([2, 1], vertical_alignment="center")
    tri = c1.segmented_control("Trier par", ["Total", "% du budget", "Croissance (3 mois)"], default="Total", key="db_tri") or "Total"
    n = c2.slider("Clients affichés", 5, max(5, len(cc)), min(15, len(cc)), key="db_n") if len(cc) > 5 else len(cc)
    col = {"Total": "total", "% du budget": "pct", "Croissance (3 mois)": "croissance"}[tri]
    cc = cc.sort_values(col, ascending=False, na_position="last").head(n)
    ordre = cc.client.tolist()
    long = cc.melt(id_vars=["client"], value_vars=list(range(1, 13)), var_name="m", value_name="v")
    long["k€"] = (long.v / 1000).round(1)
    long["Période"] = ["Réel" if m <= mr else "Prévision" for m in long.m]
    vmax = float(long.v.max()) or 1
    base = alt.Chart(long).encode(x=alt.X("m:O", title=None, axis=alt.Axis(labelExpr=MOIS_EXPR, labelAngle=0, orient="top")),
                                  y=alt.Y("client:N", sort=ordre, title=None, axis=alt.Axis(labelLimit=200, labelFontSize=12)))
    heat = base.mark_rect(stroke="#fff", strokeWidth=1.5).encode(
        color=alt.condition("datum.v > 0", alt.Color("v:Q", scale=alt.Scale(range=["#DDEFE8", TEAL]), legend=None), alt.value("#F4F6F5")),
        opacity=alt.Opacity("Période:N", scale=alt.Scale(domain=["Réel", "Prévision"], range=[1, .55]), legend=None),
        tooltip=["client", alt.Tooltip("m:O", title="Mois"), "Période", alt.Tooltip("v:Q", format=",.0f", title="€")])
    txt = base.mark_text(fontSize=11).encode(text=alt.condition("datum.v > 0", alt.Text("k€:Q", format=".1f"), alt.value("—")),
                                             color=alt.condition(f"datum.v > {vmax * .55}", alt.value("#fff"), alt.value("#16201C")))
    g, dr = st.columns([2.3, 1], gap="medium")
    with g.container(border=True):
        st.markdown(f"**Consommation mensuelle par client (k€)** <span class='aff-sub'>· plus c'est foncé, plus le mois coûte cher · "
                    f"après {L.MOIS_LONG[mr - 1]} = prévision</span>", unsafe_allow_html=True)
        st.altair_chart((heat + txt).properties(height=30 * len(cc) + 30), use_container_width=True)
    with dr.container(border=True):
        st.markdown(f"**Prévision {L.annee()} et budget**")
        t = pd.DataFrame({"client_id": cc.client_id, "Client": cc.client, "Prévision": cc.total,
                          "% budget": cc.pct}).reset_index(drop=True)
        ev = st.dataframe(t.drop(columns="client_id"), hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
                          key=f"db_cli_{tri}_{n}", height=30 * len(cc) + 70,
                          column_config={"Prévision": st.column_config.NumberColumn(format="%,.0f €"),
                                         "% budget": st.column_config.ProgressColumn(format="%.0f %%", min_value=0, max_value=120,
                                                                                     help="Prévision de l'année / budget du client")})
        rows = ev.selection.rows if ev and ev.selection else []
        st.caption("Cliquez sur un client pour ouvrir sa fiche dans Affectations.")
        if rows and PAGES.get("affectation") is not None:
            st.session_state["aff_goto"] = t.client_id.iloc[rows[0]]
            st.switch_page(PAGES["affectation"])


# =============================================================================== BUDGET ET COUVERTURE
def budget_couverture(d):
    mr = d["mr"]
    bil = L.bilan_exercice()
    bud = L.budgets_df()
    cc_all = d["cc_all"]
    k = st.columns(4)
    k[0].metric(f"Coût du parc {L.annee()}", eur(bil["cout_parc"]))
    k[0].caption("assets actifs, prix de chaque mois")
    k[1].metric(f"Refacturé {L.annee()} (prévision)", eur(bil["refacture"]))
    k[1].caption(f"couverture {pct(bil['refacture'] / bil['cout_parc'])}" if bil["cout_parc"] else "")
    k[2].metric("Écart à ventiler en fin d'année", eur(-bil["ecart"]) if bil["ecart"] < 0 else eur(bil["ecart"]),
                help="Coût du parc − refacturé : à répartir entre les entités à la clôture (page Exercices)")
    if bil["refacture"]:
        k[2].caption(f"au prorata de la consommation : {(-bil['ecart'] / bil['refacture']) * 100:+.0f} %")
    k[3].metric(f"Budgets clients {L.annee()}", eur(bud.budget.sum()))
    if bud.budget.sum():
        k[3].caption(f"prévision à {pct(cc_all.total.sum() / bud.budget.sum())}")
    g, dr = st.columns([2.1, 1], gap="medium")
    with g.container(border=True):
        cp = L.cout_parc_mensuel()
        refa = [float(cc_all[m].sum()) for m in range(1, 13)]
        df = pd.DataFrame({"m": list(range(1, 13)), "Coût du parc": [cp[m] for m in range(1, 13)], "Refacturé": refa})
        base = alt.Chart(df).encode(x=alt.X("m:O", title=None, axis=alt.Axis(labelExpr=MOIS_EXPR, labelAngle=0)))
        zone = base.mark_area(color="#FDE3C8", opacity=.8).encode(y=alt.Y("Coût du parc:Q", title=None, axis=alt.Axis(labelExpr="format(datum.value / 1000, ',.0f') + ' k'")), y2="Refacturé:Q")
        l1 = base.mark_line(color="#C2702E", strokeWidth=2.5, point=alt.OverlayMarkDef(color="#C2702E")).encode(y="Coût du parc:Q",
                                                                              tooltip=[alt.Tooltip("m:O", title="Mois"), alt.Tooltip("Coût du parc:Q", format=",.0f")])
        l2 = base.mark_line(color=TEAL, strokeWidth=2.5, point=alt.OverlayMarkDef(color=TEAL)).encode(y="Refacturé:Q",
                                                                         tooltip=[alt.Tooltip("m:O", title="Mois"), alt.Tooltip("Refacturé:Q", format=",.0f")])
        regle = alt.Chart(pd.DataFrame({"x": [mr]})).mark_rule(color="#7A8580", strokeDash=[4, 3]).encode(x="x:O")
        st.markdown("**Coût du parc et montant refacturé, par mois** <span class='aff-sub'>· <span class='db-dot' style='background:#C2702E'></span>coût du parc "
                    "<span class='db-dot' style='background:#0F6B5C;margin-left:8px'></span>refacturé · zone orange = coût non couvert</span>",
                    unsafe_allow_html=True)
        st.altair_chart((zone + l1 + l2 + regle).properties(height=320), use_container_width=True)
        st.caption("Le coût non couvert est ventilé entre les entités à la clôture de l'exercice (page Exercices).")
    with dr.container(border=True):
        st.markdown(f"**Budgets par entité** <span class='aff-sub'>· prévision {L.annee()} / budget</span>", unsafe_allow_html=True)
        e = cc_all.groupby("entite").total.sum().to_frame("Prévision").join(bud.groupby("entite").budget.sum().rename("Budget"), how="outer").fillna(0)
        e = e[(e.Prévision > 0) | (e.Budget > 0)].sort_values("Prévision", ascending=False)
        e["%"] = [p / b * 100 if b else None for p, b in zip(e.Prévision, e.Budget)]
        st.dataframe(e.reset_index().rename(columns={"entite": "Entité"}), hide_index=True, use_container_width=True,
                     column_config={"Prévision": st.column_config.NumberColumn(format="%,.0f €"), "Budget": st.column_config.NumberColumn(format="%,.0f €"),
                                    "%": st.column_config.ProgressColumn("% budget", format="%.0f %%", min_value=0, max_value=120)})
        if not L.est_cloture():
            occ = d["occ"]
            nc = occ[occ.statut == "Actif"].groupby("type").inutilise.sum().sort_values(ascending=False)
            nc = nc[nc > 0].reset_index()
            nc.columns = ["Type", "€ / mois"]
            st.altair_chart(hbar(nc, "Type", "€ / mois", f"Où est le coût non couvert ? ({L.MOIS[mr - 1].lower()})", "#C2702E"), use_container_width=True)


# =============================================================================== PAGE
def page():
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("Dashboard")
    ids, filtre = filtres()
    lignes = L.lignes_mensuelles()
    cc_all = L.conso_clients(lignes)
    cc = cc_all[cc_all.client_id.isin(ids)]
    detail = L.conso_assets(lignes=lignes)
    d = dict(ids=ids, filtre=filtre, lignes=lignes, cc=cc, cc_all=cc_all, mr=L.mois_ref(), detail=detail,
             occ=L.occupation_parc(detail=detail) if not L.est_cloture() else pd.DataFrame(columns=["type", "parc", "utilises", "statut", "nom", "cout_parc", "inutilise"]),
             types=L.conso_par_type(lignes, ids))
    t1, t2, t5, t3, t4 = st.tabs(["Vue d'ensemble", "Par asset", "Capacité", "Par client", "Budget et couverture"])
    with t1:
        vue_ensemble(d)
    with t2:
        par_asset(d)
    with t5:
        capacite(d)
    with t3:
        par_client(d)
    with t4:
        budget_couverture(d)
