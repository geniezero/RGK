"""Écran d'accueil : indicateurs clés, points à traiter, accès rapide aux écrans."""
from datetime import date

import streamlit as st

from ia_platform.core import logic as L
from ia_platform.core import planning as P
from ia_platform.ui import navigation as N
from ia_platform.ui.commun import eur, mois_txt
from ia_platform.ui.theme import ORANGE, ROUGE, TEAL, a_faire, carte

ACCES = [
    ("🖥️", "Assets", "assets", "Le parc : prix, unité de facturation, quantité, instances cloud."),
    ("📦", "Offres", "offres", "Le catalogue : composition, coût et clients de chaque offre."),
    ("👥", "Clients", "clients", "Les clients (projets) avec leur entité et leur pays."),
    ("🔁", "Affectations", "affectation", "Ce que chaque client consomme, avec les dates de début et de fin."),
    ("🧾", "Devis", "devis", "Préparer et envoyer les devis par mail ; noter le retour du client."),
    ("📈", "Capacity planning", "capacity-planning", "La collecte des besoins des métiers pour une période."),
    ("📊", "Dashboard", "dashboard", "Vue d'ensemble, par asset, capacité, par client, budget et couverture."),
    ("📅", "Consommation", "consommation", "Le tableau client × mois, réel puis prévision."),
    ("📄", "Rapports Excel", "rapports", "Le classeur mis en forme pour partager les chiffres."),
]


def _points_a_traiter():
    """Liste (icône, couleur, texte, page) des sujets qui demandent une action."""
    out = []
    auj = date.today()
    try:
        dl = L.devis_liste()
        if len(dl):
            dl = dl[~dl.retour.isin(["Accepté", "Refusé"])]  # retour définitif noté : plus rien à faire
            env = dl[dl.statut_aff == "Envoyé"]
            rel = env[[(e - auj).days <= 7 for e in env.expire_le]]
            if len(rel):
                out.append(("🧾", ORANGE, f"<b>{len(rel)} devis à relancer</b> : leur validité se termine dans 7 jours ou moins.", "devis"))
            exp = int((dl.statut_aff == "Expiré").sum())
            if exp:
                out.append(("🧾", ROUGE, f"<b>{exp} devis expiré(s)</b> sans réponse : relancer, faire une nouvelle version ou noter le refus.", "devis"))
            br = int((dl.statut_aff == "Brouillon").sum())
            if br:
                out.append(("✏️", "#7A8580", f"<b>{br} brouillon(s) de devis</b> à finaliser et envoyer.", "devis"))
    except Exception:  # noqa: BLE001 — l'accueil ne doit jamais bloquer
        pass
    try:
        camps = P.campagnes_df()
        for c in camps[camps.statut == "Ouverte"].itertuples():
            met = P.metiers_df(c.id)
            sans = int((met.statut == "En attente").sum())
            rep = int(met.statut.isin(P.REPONDU).sum())
            lim = P.jour(c.date_limite)
            txt = f"<b>{c.nom}</b> : {rep} réponse(s) sur {len(met)}"
            if lim:
                txt += f", date limite le {lim:%d/%m/%Y}" + (" (dépassée)" if lim < auj else "")
            if sans:
                txt += f" · {sans} métier(s) à relancer"
            out.append(("📈", ROUGE if (lim and lim < auj and sans) else TEAL, txt + ".", "capacity-planning"))
    except Exception:  # noqa: BLE001
        pass
    try:
        pools = L.pools_capacite()
        pleins = [p["label"] for p in pools if p["etat"] == "Plein"]
        bientot = [p["label"] for p in pools if p["etat"] == "Bientôt plein"]
        if pleins:
            out.append(("⚠️", ROUGE, f"<b>Capacité pleine</b> : {', '.join(pleins[:3])}{'…' if len(pleins) > 3 else ''}.", "dashboard"))
        if bientot:
            out.append(("⏳", ORANGE, f"<b>Bientôt plein</b> : {', '.join(bientot[:3])}{'…' if len(bientot) > 3 else ''}.", "dashboard"))
    except Exception:  # noqa: BLE001
        pass
    try:
        cc = L.conso_clients().set_index("client_id")
        bud = L.budgets_df()
        bud = bud[bud.budget > 0]
        dep = [r.client for r in bud.itertuples() if cc.total.get(r.client_id, 0) > r.budget]
        if dep:
            out.append(("💶", ORANGE, f"<b>{len(dep)} client(s) au-dessus de leur budget {L.annee()}</b> (prévision de fin d'année).", "dashboard"))
    except Exception:  # noqa: BLE001
        pass
    try:
        if not L.est_cloture() and L.mois_ref() == 12 and not len(L.regul_appliquee()):
            out.append(("⚖️", ORANGE, f"<b>Régularisation {L.annee()}</b> à appliquer avant la clôture (une seule fois, en décembre).", "exercices"))
    except Exception:  # noqa: BLE001
        pass
    if not L.est_cloture() and L.annee() == date.today().year and L.mois_ref() < date.today().month - 1:
        out.append(("🗓️", "#3A5BA0", f"Le dernier mois réel est <b>{L.MOIS_LONG[L.mois_ref() - 1]}</b> : pensez à l'avancer dans Paramètres.",
                    "parametres"))
    return out


def page():
    demo = L.mode_donnees() == "demo"
    chips = [f"Exercice {L.annee()} · {'clôturé' if L.est_cloture() else 'ouvert'}", f"Réel jusqu'à {mois_txt()}"]
    if demo:
        chips.append("Données de démonstration")
    st.markdown(
        "<div class='ia-hero'><h1>IA Platform</h1>"
        "<p>Refacturation de la plateforme IA de l'équipe A : parc, offres, clients, devis, capacité et budget.</p>"
        f"<div class='chips'>{''.join(f'<span>{c}</span>' for c in chips)}</div></div>", unsafe_allow_html=True)
    if demo:
        st.info("Vous utilisez les **données de démonstration** (fictives). Pour saisir vos propres données : Paramètres › Données › « Tout effacer ».",
                icon="🧪")

    n_a, n_o, n_c = len(L.q("SELECT id FROM assets")), len(L.q("SELECT id FROM offres")), len(L.q("SELECT id FROM clients"))
    n_af = len(L.q("SELECT id FROM affectations"))
    if not (n_a and n_o and n_c and n_af):
        with st.container(border=True):
            st.markdown("#### Premiers pas")
            etapes = [(n_a, "Assets", "saisir vos ressources (prix, unité, quantité du parc) ou les importer en CSV", "assets"),
                      (n_o, "Offres", "composer vos offres à partir des assets", "offres"),
                      (n_c, "Clients", "créer vos clients (nom, entité, pays) ou les importer en CSV", "clients"),
                      (n_af, "Affectations", "donner une offre ou des options à un client, avec une date de début", "affectation")]
            for i, (n, nom, txt, url) in enumerate(etapes, 1):
                g_, d_ = st.columns([5, 1], vertical_alignment="center")
                g_.markdown(f"{'✅' if n else '⬜'} **{i}. {nom}** — {txt}" + (f" · {n} saisi{'s' if n > 1 else ''}" if n else ""))
                if N.page(url):
                    d_.page_link(N.page(url), label=f"Ouvrir {nom}", icon="➡️")
            st.caption("Le Dashboard, la consommation et les rapports se remplissent ensuite tout seuls.")

    assets = L.assets_df()
    cc = L.conso_clients()
    parc = assets.loc[assets.statut == "Actif", "cout_parc"].sum()
    refact = cc.mois_ref.sum()
    c = st.columns(5)
    c[0].metric("Coût du parc / mois", eur(parc), help="Ce que l'équipe A paie chaque mois pour les assets actifs, vendus ou non.")
    c[1].metric(f"Refacturé en {L.MOIS_LONG[L.mois_ref() - 1]}", eur(refact))
    c[2].metric("Taux de couverture", f"{refact / parc * 100:.1f} %".replace(".", ",") if parc else "—",
                help="Refacturé du mois ÷ coût du parc du mois.")
    c[3].metric("Clients consommateurs", int((cc.mois_ref > 0).sum()))
    c[4].metric("Offres actives", int((L.q("SELECT statut FROM offres").statut == "Active").sum()))

    st.write("")
    g, d = st.columns([1.75, 1], gap="large")
    with g:
        st.markdown("#### Accès rapide")
        for i in range(0, len(ACCES), 3):
            cols = st.columns(3)
            for col, (ico, titre, url, desc) in zip(cols, ACCES[i:i + 3]):
                with col:
                    carte(ico, titre, desc)
                    if N.page(url):
                        st.page_link(N.page(url), label=f"Ouvrir {titre}", icon=":material/arrow_forward:")
    with d:
        st.markdown("#### À traiter")
        pts = _points_a_traiter()
        with st.container(border=True):
            if not pts:
                st.markdown("✅ Rien d'urgent : pas de devis à relancer, de capacité saturée ni de budget dépassé.")
            for ico, col, txt, url in pts:
                t_, l_ = st.columns([2.7, 1], vertical_alignment="center")
                t_.markdown(a_faire(ico, col, txt), unsafe_allow_html=True)
                if N.page(url):
                    l_.page_link(N.page(url), label="Voir", icon=":material/chevron_right:")
        with st.expander("Comment ça marche"):
            st.markdown("""
1. **Assets** : chaque ressource avec son prix et son unité de facturation ; le coût mensuel est calculé.
2. **Offres** : une offre regroupe plusieurs assets ; son coût mensuel est calculé automatiquement.
3. **Clients** : nom, entité et pays, pour suivre la consommation par pays et par entité.
4. **Affectations** et **Devis** : ce que chaque client consomme, avec des dates de début et de fin.
5. **Consommation**, **Dashboard** et **Rapports** : se mettent à jour tout seuls.

Les mois après le dernier mois réel sont des **prévisions**.
""")
