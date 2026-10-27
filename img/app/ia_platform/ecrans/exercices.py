"""Écran Exercices : budget de fonctionnement et réel par clé, régularisation unique de décembre, budgets clients (info), historique et archives."""
from datetime import date

import pandas as pd
import streamlit as st

from ia_platform.core import logic as L
from ia_platform.exports import rapport_excel
from ia_platform.ui.commun import EUR0, eur, to_excel
from ia_platform.ui.theme import entete

TYPES = {"assets": "Assets", "indirecte": "Indirecte"}
TYPES_INV = {v: k for k, v in TYPES.items()}
ICONES = {1: "✅", 0: "⚠️", 2: "⏳"}


def _pct(v, dec=1):
    return f"{v:+.{dec}f} %".replace(".", ",")


def _periode(mois):
    if not mois:
        return "aucun mois"
    return L.MOIS[mois[0] - 1].lower() if len(mois) == 1 else f"{L.MOIS[mois[0] - 1].lower()} → {L.MOIS[mois[-1] - 1].lower()}"


def _lire_tableau(f):
    if f.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(f)
    return L.lire_csv(f)


# ------------------------------------------------------------------ 1. budget et réel
def onglet_budget(a, ferme):
    b = L.bilan_service(a)
    cl = L.cles_budget(a)
    n_as = int((cl.type == "assets").sum())
    mr = b["mois_reel"]
    ecart_d = b["reel_a_date"] - b["consomme_a_date"]
    ind_d = sum(v["reel"] for v in b["par_cle"].values() if v["type"] != "assets")
    k = st.columns(4)
    k[0].metric(f"Budget {a}", eur(b["budget"]), help="Budget de fonctionnement du service (somme des clés).")
    k[0].caption(f"{len(cl)} clés · {n_as} suivie(s) par les assets · {len(cl) - n_as} indirecte(s)")
    k[1].metric(f"Consommé à date ({_periode(mr)})", eur(b["consomme_a_date"]), help="Refacturé par les affectations sur les mois qui ont un réel.")
    k[1].caption("refacturé via les affectations")
    k[2].metric(f"Réel à date ({_periode(mr)})", eur(b["reel_a_date"]))
    k[2].caption("saisi ou importé par clé" + (f" · {_periode(b['manquants'])} à venir" if b["manquants"] else ""))
    k[3].metric("Écart à date", f"{ecart_d:+,.0f} €".replace(",", " "), help="Réel − consommé, sur les mois qui ont un réel.")
    k[3].caption(f"dont {eur(ind_d)} de coûts indirects")

    with st.container(border=True):
        t_, i_ = st.columns([3, 1.2], vertical_alignment="center")
        t_.markdown("##### Budget et réel par clé")
        with i_.popover("📥 Importer le réel (Excel / CSV)", use_container_width=True, disabled=ferme):
            st.caption("Deux formats : une ligne par clé avec une colonne par mois (Clé ; Janv. ; Févr. ; …), "
                       "ou une ligne par valeur (Clé ; Mois ; Montant). Une valeur importée remplace celle du mois ; une clé inconnue est créée (indirecte).")
            mod = pd.DataFrame({"Clé": list(cl.cle), **{L.MOIS[m - 1]: [None] * len(cl) for m in range(1, 13)}})
            st.download_button("Télécharger le modèle", to_excel({"Réel": mod}), f"Reel_{a}.xlsx", on_click="ignore")
            f = st.file_uploader("Fichier", type=["xlsx", "csv"], key="up_reel")
            if f is not None:
                try:
                    df_ = _lire_tableau(f)
                    st.dataframe(df_.head(8), hide_index=True)
                    if st.button(f"Importer ({len(df_)} lignes)", type="primary"):
                        r = L.importer_reel(a, df_)
                        st.toast(f"Réel importé : {r['valeurs']} valeur(s), {r['clés créées']} clé(s) créée(s).", icon="✅")
                        st.session_state.pop("ed_reel", None)
                        st.rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Lecture impossible : {e}")

        t = L.reel_df(a)
        ed = pd.DataFrame({"cle": cl.cle, "type": [TYPES.get(x, "Indirecte") for x in cl.type], "budget": cl.budget})
        for m in range(1, 13):
            ed[f"m{m}"] = [t.loc[c, m] if c in t.index else None for c in cl.cle]
        cfg = {"cle": st.column_config.TextColumn("Clé", required=True, width=118),
               "type": st.column_config.SelectboxColumn("Type", options=list(TYPES.values()), required=True, width=84),
               "budget": st.column_config.NumberColumn(f"Budget {a}", format=EUR0, min_value=0, step=1000, width=104)}
        for m in range(1, 13):
            cfg[f"m{m}"] = st.column_config.NumberColumn(L.MOIS[m - 1], format="%,.0f", min_value=0, width=62)
        res = st.data_editor(ed, hide_index=True, use_container_width=True, num_rows="dynamic", disabled=ferme, key="ed_reel",
                             column_config=cfg)
        st.caption("Le réel se saisit en euros, mois par mois, quand il arrive. Une case vide (« None ») = réel pas encore connu. "
                   "« Assets » : la clé est refacturée chaque mois par les affectations (infrastructure, licences). "
                   "« Indirecte » : coût du service qui n'est pas suivi par un asset (électricité, bâtiments, support…).")
        if not ferme and st.button("💾 Enregistrer le budget et le réel", type="primary"):
            sav = res.rename(columns={f"m{m}": m for m in range(1, 13)}).copy()
            sav["type"] = sav.type.map(TYPES_INV).fillna("indirecte")
            try:
                n, v = L.enregistrer_budget_reel(a, sav)
                st.toast(f"{n} clé(s) et {v} valeur(s) de réel enregistrées.", icon="💾")
                st.session_state.pop("ed_reel", None)
                st.rerun()
            except ValueError as e:
                st.error(str(e))

    with st.container(border=True):
        st.markdown("##### Suivi mensuel")
        bm = b["budget"] / 12
        rows = {"Réel total": [b["reel_mois"][m] for m in range(1, 13)],
                "Budget du mois": [bm] * 12,
                "Consommé (affectations)": [b["conso_mois"][m] for m in range(1, 13)],
                "Écart réel − consommé": [(b["reel_mois"][m] - b["conso_mois"][m]) if b["reel_mois"][m] is not None else None for m in range(1, 13)]}
        suivi = pd.DataFrame(rows, index=[L.MOIS[m - 1] for m in range(1, 13)]).T
        suivi["Année"] = [b["reel_a_date"], b["budget"], sum(b["conso_mois"].values()), ecart_d]
        signe = {"Écart réel − consommé"}
        suivi = suivi.astype(object)
        for i_ in suivi.index:
            suivi.loc[i_] = [("—" if v is None or pd.isna(v) else (f"{v:+,.0f}" if i_ in signe else f"{v:,.0f}").replace(",", " "))
                             for v in suivi.loc[i_]]
        suivi = suivi.reset_index(names="ligne")
        cfg2 = {c: st.column_config.TextColumn(c, width=70) for c in suivi.columns if c != "ligne"}
        cfg2["ligne"] = st.column_config.TextColumn(" ", width=175)
        cfg2["Année"] = st.column_config.TextColumn("Année", width=95)
        st.dataframe(suivi, hide_index=True, use_container_width=True, column_config=cfg2)
        mr_ = L.mois_ref(a)
        st.caption(f"Le consommé après {L.MOIS_LONG[mr_ - 1]} (dernier mois réel) est une prévision des affectations. "
                   "L'écart n'est calculé que pour les mois qui ont un réel ; « Année » = à date pour le réel et l'écart.")
        g_, d_ = st.columns([1.6, 1], vertical_alignment="center")
        g_.markdown("**En décembre, un mois sans réel…**")
        choix = d_.segmented_control("Règle", ["attendre", "budget"], default=b["regle"], key="regle_regul", label_visibility="collapsed",
                                     format_func=lambda x: "attend son réel" if x == "attendre" else "compte pour son budget", disabled=ferme)
        if choix and choix != b["regle"]:
            L.set_param("regul_mois_sans_reel", choix)
            st.rerun()
        st.caption("« Attend son réel » : la régularisation n'est possible que si les 12 mois ont un réel. "
                   "« Compte pour son budget » : un mois sans réel compte pour 1/12 du budget de chaque clé.")


# ------------------------------------------------------------------ 2. régularisation et clôture
@st.dialog("Clôturer l'exercice")
def dlg_cloture(a, sim, cle):
    st.markdown(f"La clôture **fige les montants de {a}** : ils ne seront plus recalculés, même si les prix ou les offres changent. "
                "Une copie de la base, le rapport Excel de l'année et le détail de la régularisation sont archivés.")
    if not len(L.regul_appliquee(a)):
        st.warning("La régularisation n'est pas appliquée : le centre de coûts finira l'année avec un écart.")
    if st.checkbox(f"Je confirme la clôture de {a}") and st.button(f"🔒 Clôturer {a}", type="primary"):
        with st.spinner("Clôture en cours…"):
            r = L.cloturer_exercice(a)
            L.archiver(a, f"IA_Platform_rapport_{a}_cloture.xlsx", rapport_excel.generer_rapport(None, True))
            L.archiver(a, f"Regularisation_{a}.xlsx", to_excel({"Régularisation": _export_regul(sim, cle)}))
        st.toast(f"Exercice {a} clôturé : {r['lignes']} lignes figées.", icon="🔒")
        st.rerun()


def _export_regul(sim, cle):
    return pd.DataFrame({"Client": sim.client, "Entité": sim.entite, "Consommé": sim.conso.round(2), "Part (%)": (sim.part * 100).round(2),
                         "Au prorata": sim.prorata.round(2), "À parts égales": sim.egal.round(2),
                         "Retenu (" + L.CLES_REGUL[cle].lower() + ")": sim.montant.round(2), "Total de l'année": sim.total.round(2)})


def onglet_regul(a, ferme):
    e = L.exercice(a)
    ap = L.regul_appliquee(a)
    cle_ap = (getattr(e, "cle_regul", None) or None) if len(ap) else None
    b = L.bilan_service(a)
    k = st.columns(4)
    k[0].metric("Coût réel du service", eur(b["cout"]))
    bref = b["budget"] * len(b["mois_reel"]) / 12 if (b["provisoire"] and b["regle"] != "budget") else b["budget"]
    k[0].caption(("réel à date · budget des mêmes mois " if bref != b["budget"] else "budget ") + eur(bref)
                 + (f" · {_pct((b['cout'] / bref - 1) * 100, 0)}" if bref else ""))
    k[1].metric(f"Consommé {'à date' if b['provisoire'] and b['regle'] != 'budget' else 'de l’année ' + str(a)}", eur(b["consomme"]))
    k[1].caption("refacturé via les affectations (hors régularisation)")
    k[2].metric("Écart à régulariser", f"{b['ecart']:+,.0f} €".replace(",", " "))
    k[2].caption(f"soit {_pct(b['ecart'] / b['consomme'] * 100)} sur la facture de chaque client" if b["consomme"] else "")
    with k[3].container(border=True):
        st.markdown(f"<div style='font-size:.88rem;color:#55625C'>Dont</div>"
                    f"<div style='margin-top:6px'>coûts indirects <b>{eur(b['indirect'])}</b></div>"
                    f"<div>écart sur les assets <b>{b['ecart_assets']:+,.0f} €</b></div>".replace(",", " "), unsafe_allow_html=True)
    if b["manquants"] and not ferme:
        reg = ("comptent pour leur budget" if b["regle"] == "budget"
               else "ne sont pas encore comptés : l'écart est provisoire (réel à date face au consommé des mêmes mois)")
        st.info(f"Réel saisi pour {len(b['mois_reel'])} mois sur 12. Les mois sans réel ({', '.join(L.MOIS_LONG[m - 1] for m in b['manquants'])}) {reg}. "
                "La régularisation se fait une seule fois, en décembre.", icon="ℹ️")

    g, d = st.columns([2.3, 1], gap="medium")
    with g, st.container(border=True):
        t_, x_ = st.columns([3, 1], vertical_alignment="center")
        t_.markdown("##### Régularisation de décembre")
        cle = cle_ap or st.session_state.get("cle_regul") or "prorata"
        c1, c2 = st.columns([1, 3], vertical_alignment="center")
        c1.markdown("Clé de répartition")
        choix = c2.segmented_control("Clé", list(L.CLES_REGUL), default=cle, format_func=L.CLES_REGUL.get, key="cle_regul_sc",
                                     label_visibility="collapsed", disabled=bool(cle_ap) or ferme)
        cle = cle_ap or choix or "prorata"
        st.session_state["cle_regul"] = cle
        sim, _ = L.simuler_regul(a, cle)
        n = len(sim)
        if n:
            pc = b["ecart"] / b["consomme"] * 100 if b["consomme"] else 0
            st.caption(f"Au prorata : chacun paie l'écart à proportion de ce qu'il a consommé ({_pct(pc)} de sa facture). "
                       f"À parts égales : chaque client consommateur paie le même montant ({eur(b['ecart'] / n)}), quel que soit son usage.")
        x_.download_button("📄 Exporter (Excel)", to_excel({"Régularisation": _export_regul(sim, cle)}), f"Regularisation_{a}.xlsx",
                           on_click="ignore", use_container_width=True, disabled=not n)
        vue = sim[["client", "entite", "conso", "part", "prorata", "egal", "total"]].assign(part=lambda x: x.part * 100)
        coche = {"prorata": " ✓" if cle == "prorata" else "", "egal": " ✓" if cle == "egal" else ""}
        st.dataframe(vue, hide_index=True, use_container_width=True, height=min(36 * (n + 1) + 4, 430), column_config={
            "client": "Client", "entite": st.column_config.TextColumn("Entité", width="small"), "conso": st.column_config.NumberColumn(f"Consommé {a}", format=EUR0),
            "part": st.column_config.NumberColumn("Part", format="%.1f %%"),
            "prorata": st.column_config.NumberColumn("Au prorata" + coche["prorata"], format=EUR0),
            "egal": st.column_config.NumberColumn("À parts égales" + coche["egal"], format=EUR0),
            "total": st.column_config.NumberColumn("Total de l'année", format=EUR0)})
        st.caption(f"Total · {n} clients consommateurs : consommé {eur(sim.conso.sum())}, régularisation {b['ecart']:+,.0f} €, "
                   f"total {eur(sim.total.sum())}.".replace(",", " ") + " La colonne cochée est celle appliquée ; l'autre est affichée pour comparer. "
                   f"Une ligne « Régularisation de fin d'année {a} » par client, en décembre, une seule fois. Un écart négatif donne un avoir.")
        if len(ap):
            st.success(f"Régularisation appliquée le {L.d(e.regul_date):%d/%m/%Y} ({L.CLES_REGUL.get(cle_ap, '').lower()}) : "
                       f"{eur(ap.montant.sum())} sur {len(ap)} client(s).", icon="✅")

    with d:
        with st.container(border=True):
            st.markdown("##### D'où vient l'écart")
            pk = pd.DataFrame([dict(cle=k_ + ("" if v["type"] == "assets" else " *"), type=TYPES.get(v["type"], v["type"]), budget=v["budget"], reel=v["retenu"]) for k_, v in b["par_cle"].items()])
            if len(pk):
                pk = pd.concat([pk, pd.DataFrame([dict(cle="Coût du service", type="", budget=pk.budget.sum(), reel=pk.reel.sum())])], ignore_index=True)
            st.dataframe(pk, hide_index=True, use_container_width=True, column_config={
                "cle": st.column_config.TextColumn("Clé", width=118), "type": None,
                "budget": st.column_config.NumberColumn("Budget", format=EUR0, width=92),
                "reel": st.column_config.NumberColumn("Réel", format=EUR0, width=92)})
            st.caption(f"Assets : réel {eur(b['cout'] - b['indirect'])} − consommé {eur(b['consomme'])} = {b['ecart_assets']:+,.0f} € ".replace(",", " ")
                       + "(parc non affecté, écarts de prix). * Indirectes : " + eur(b["indirect"]) + ", jamais refacturées dans l'année.")
        with st.container(border=True):
            st.markdown(f"##### Avant clôture {a}")
            if ferme:
                st.success(f"Exercice {a} clôturé le {L.d(e.date_cloture):%d/%m/%Y} : les montants sont figés. "
                           "Pour corriger : Exercices et archives › Zone sensible.", icon="🔒")
                return
            for etat, lib, det in L.controles_cloture(a):
                st.markdown(f"{ICONES[etat]} **{lib}**" + (f"  \n<span style='color:#5E6B65;font-size:.86rem'>{det}</span>" if det else ""),
                            unsafe_allow_html=True)
            b1, b2 = st.columns(2)
            if len(ap):
                if b1.button("↩️ Annuler", use_container_width=True, help="Annuler la régularisation pour la refaire"):
                    L.annuler_regul(a)
                    st.toast("Régularisation annulée.", icon="↩️")
                    st.rerun()
            elif b1.button("Appliquer la régularisation", type="primary", use_container_width=True):
                try:
                    nb, ec = L.appliquer_regul(a, cle)
                    st.toast(f"Régularisation appliquée : {ec:+,.0f} € sur {nb} clients.".replace(",", " "), icon="✅")
                    st.rerun()
                except ValueError as err:
                    st.error(str(err))
            if b2.button(f"🔒 Clôturer {a}", use_container_width=True):
                dlg_cloture(a, sim, cle)


# ------------------------------------------------------------------ 3. budgets clients (info)
def onglet_budgets_clients(a, ferme):
    st.info("**Pour information seulement.** Les budgets des clients ne bloquent rien et n'entrent pas dans la régularisation : "
            "ils servent à prévenir un client qui approche ou dépasse son enveloppe. Un client peut ne pas avoir de budget.", icon="ℹ️")
    bd, simulee = L.budgets_clients_info(a, st.session_state.get("cle_regul"))
    bd = bd[(bd.statut != "Inactif") | (bd.budget > 0) | (bd.conso > 0)] if "statut" in bd else bd
    avec = bd[bd.budget > 0]
    k = st.columns(4)
    k[0].metric("Clients avec un budget", f"{len(avec)} / {len(bd)}")
    k[0].caption(f"total des budgets : {eur(avec.budget.sum())}")
    k[1].metric("Au-dessus de leur budget", int((bd.etat == "au-dessus").sum()))
    k[1].caption("régularisation comprise" + (" (simulée)" if simulee else ""))
    k[2].metric("Proches (≥ 90 %)", int((bd.etat == "proche").sum()))
    k[2].caption("à prévenir")
    sans = bd[(bd.budget <= 0) & (bd.conso > 0)]
    k[3].metric("Consommateurs sans budget", len(sans))
    k[3].caption(f"dont {sans.client.iloc[0]}" if len(sans) else "—")

    with st.container(border=True):
        t_, p_, s_ = st.columns([3, 1.2, 1], vertical_alignment="center")
        t_.markdown(f"##### Budgets {a} par client")
        with p_.popover(f"Reprendre {a - 1} + %", use_container_width=True, disabled=ferme):
            pct = st.number_input("Évolution (%)", value=0.0, step=1.0, key="bud_evo")
            prec = L.budgets_df(a - 1)
            st.caption(f"{int((prec.budget > 0).sum())} budget(s) en {a - 1}, total {eur(prec.budget.sum())}. Remplace les budgets {a}.")
            if st.button("Reprendre", type="primary", disabled=not (prec.budget > 0).any()):
                prec["budget"] = (prec.budget * (1 + pct / 100)).round(0)
                L.enregistrer_budgets(a, prec)
                st.session_state.pop("ed_budcli", None)
                st.rerun()
        vue = bd[["client_id", "client", "entite", "budget", "conso", "regul", "total", "pct", "etat"]].copy()
        vue["pct"] = vue.pct.fillna(0)
        res = st.data_editor(vue, hide_index=True, use_container_width=True, key="ed_budcli", disabled=ferme, height=min(36 * (len(vue) + 1) + 4, 560),
                             column_config={
                                 "client_id": None, "client": st.column_config.TextColumn("Client", disabled=True),
                                 "entite": st.column_config.TextColumn("Entité", disabled=True),
                                 "budget": st.column_config.NumberColumn(f"Budget {a}", format=EUR0, min_value=0, step=1000),
                                 "conso": st.column_config.NumberColumn("Consommé", format=EUR0, disabled=True),
                                 "regul": st.column_config.NumberColumn("Régularisation" + (" (simulée)" if simulee else ""), format=EUR0, disabled=True),
                                 "total": st.column_config.NumberColumn("Total de l'année", format=EUR0, disabled=True),
                                 "pct": st.column_config.ProgressColumn("Total / budget", format="%.0f %%", min_value=0, max_value=130),
                                 "etat": st.column_config.TextColumn("État", disabled=True)})
        st.caption("Le budget se modifie directement dans le tableau (0 = pas de budget). Le consommé est celui de l'année (prévision comprise) ; "
                   "la régularisation est celle appliquée, ou à défaut simulée avec la clé choisie dans « Régularisation et clôture ».")
        if not ferme and s_.button("💾 Enregistrer", type="primary", use_container_width=True):
            L.enregistrer_budgets(a, res)
            st.toast("Budgets clients enregistrés.", icon="💾")
            st.session_state.pop("ed_budcli", None)
            st.rerun()


# ------------------------------------------------------------------ 4. exercices et archives
@st.dialog("Rouvrir l'exercice")
def dlg_rouvrir(a):
    st.warning("Rouvrir supprime les montants figés : l'année sera recalculée avec les prix et offres actuels. "
               "Une copie de la base est archivée avant. La régularisation appliquée est conservée (elle peut ensuite être annulée).")
    if st.checkbox(f"Je confirme vouloir rouvrir {a}") and st.button(f"Rouvrir {a}", type="primary"):
        L.rouvrir_exercice(a)
        st.rerun()


@st.dialog("Réinitialiser")
def dlg_reinit():
    st.warning("La réinitialisation supprime les affectations, devis, budgets, réel, ajustements, exercices et montants figés. "
               "Une copie complète de la base est d'abord enregistrée dans « data/archives ».")
    c1, c2, c3 = st.columns(3)
    dep = c1.number_input("Exercice de départ", value=date.today().year + 1, step=1)
    garder_ref = c2.checkbox("Garder assets, prix et offres", value=True)
    garder_cli = c3.checkbox("Garder les clients", value=True)
    conf = st.text_input("Tapez RÉINITIALISER pour confirmer")
    if st.button("Repartir à zéro", type="primary", disabled=conf.strip().upper() not in ("RÉINITIALISER", "REINITIALISER")):
        cible = L.reinitialiser(int(dep), garder_ref, garder_cli)
        st.session_state["_msg_reinit"] = f"Base réinitialisée. Copie de sauvegarde : data/archives/{cible.name}"
        st.rerun()
    st.divider()
    if st.button("Recharger les données d'exemple (efface tout)"):
        L.sauvegarde_fichier()
        L.DB_PATH.unlink(missing_ok=True)
        L.init_db()
        st.rerun()


def onglet_historique(a):
    if st.session_state.get("_msg_reinit"):
        st.success(st.session_state.pop("_msg_reinit"))
    ex = L.exercices_df()
    g, d = st.columns([1.75, 1], gap="medium")
    with g:
        with st.container(border=True):
            st.markdown("##### Exercices")
            h = L.historique_exercices()
            if len(h):
                h["regul_txt"] = [(f"{r:+,.0f} € ({'prorata' if c.startswith('Au') else 'égales'})".replace(",", " ")
                                   if r is not None and not pd.isna(r) else "à appliquer") for r, c in zip(h.regul, h.cle)]
                h["cloture"] = [L.d(x).strftime("%d/%m/%Y") if L.d(x) else "—" for x in h.cloture]
                st.dataframe(h[["annee", "statut", "budget", "cout", "consomme", "regul_txt", "cloture"]], hide_index=True, use_container_width=True,
                             column_config={"annee": st.column_config.NumberColumn("Exercice", format="%d"), "statut": "Statut",
                                            "budget": st.column_config.NumberColumn("Budget", format=EUR0),
                                            "cout": st.column_config.NumberColumn("Coût réel", format=EUR0),
                                            "consomme": st.column_config.NumberColumn("Consommé", format=EUR0),
                                            "regul_txt": "Régularisation",
                                            "cloture": "Clôturé le"})
        with st.container(border=True):
            st.markdown("##### Archives")
            ar = L.archives_df()
            if ar.empty:
                st.caption("Aucune archive pour le moment : elles sont créées à la clôture et à la réouverture (base, rapport Excel, régularisation).")
            for r in ar.itertuples():
                c1, c2, c3 = st.columns([3.2, 2.2, .6], vertical_alignment="center")
                ico = "📊" if r.nom.endswith(".xlsx") else "🗄️"
                c1.markdown(f"{ico} **{r.nom}**")
                c2.caption(f"Exercice {r.annee} · {r.date.replace('T', ' ')[:16]} · {r.taille / 1024:.0f} Ko")
                c3.download_button("⬇️", L.archive_contenu(r.id), r.nom, key=f"ar_{r.id}", on_click="ignore")
            st.download_button("⬇️ Sauvegarder la base actuelle", L.DB_PATH.read_bytes(), f"ia_platform_{date.today():%Y%m%d}.db", on_click="ignore")
    with d:
        suivant = int(ex.annee.max()) + 1 if len(ex) else date.today().year
        with st.container(border=True):
            st.markdown(f"##### Ouvrir l'exercice {suivant}")
            base = suivant - 1
            reprise = st.toggle(f"Reprendre les clés et le budget {base}", value=True)
            bud = L.cles_budget(base).budget.sum() if L.exercice(base) is not None else 0
            c1, c2 = st.columns([1, 1], vertical_alignment="bottom")
            evo = c1.number_input("Évolution du budget (%)", value=0.0, step=1.0, format="%.1f", disabled=not reprise)
            if reprise:
                c2.markdown(f"→ **{eur(bud * (1 + evo / 100))}**")
            cli = st.toggle("Reprendre les budgets clients (même évolution)", value=True)
            grille = st.file_uploader(f"Nouvelle grille de prix au 01/01/{suivant} (CSV, facultatif)", type=["csv"], key="grille")
            st.caption(f"Clients, assets, offres et affectations en cours sont conservés : une ligne sans date de fin continue en {suivant}.")
            if st.button(f"Ouvrir {suivant}", type="primary"):
                try:
                    L.ouvrir_exercice(suivant, base if cli else None, evo, base if reprise else None, evo)
                    if grille is not None:
                        rap = L.appliquer_grille_prix(L.lire_csv(grille), suivant)
                        st.toast("Grille de prix : " + " · ".join(f"{k_} : {v}" for k_, v in rap.items() if k_ != "ignorés"))
                    st.toast(f"Exercice {suivant} ouvert.", icon="🗓️")
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
        with st.container(border=True):
            st.markdown("<div style='color:#9C1C14;font-weight:700;font-size:1.05rem'>Zone sensible</div>", unsafe_allow_html=True)
            st.markdown(f"**Rouvrir {a}** · pour corriger : supprime les montants figés, copie de la base faite avant.  \n"
                        "**Réinitialiser** · repartir à zéro (garder ou non assets, offres, clients), copie faite avant.")
            b1, b2 = st.columns(2)
            if b1.button(f"Rouvrir {a}…", disabled=not L.est_cloture(a), use_container_width=True):
                dlg_rouvrir(a)
            if b2.button("Réinitialiser…", use_container_width=True):
                dlg_reinit()


def page():
    a = L.annee()
    ferme = L.est_cloture(a)
    mr = L.mois_ref(a)
    entete("Exercices", f"Exercice {a} · {'clôturé' if ferme else 'ouvert'} · dernier mois réel : {L.MOIS_LONG[mr - 1]}. "
                        "Le budget en janvier, le consommé chaque mois, le réel par clé quand il arrive, une seule régularisation en décembre.",
           "🗓️", "Administration")
    t1, t2, t3, t4 = st.tabs(["Budget et réel", "Régularisation et clôture", "Budgets clients (info)", "Exercices et archives"])
    with t1:
        onglet_budget(a, ferme)
    with t2:
        onglet_regul(a, ferme)
    with t3:
        onglet_budgets_clients(a, ferme)
    with t4:
        onglet_historique(a)
