"""Capacity planning : campagnes de collecte des besoins des métiers (logique + fichiers Excel)."""
import json
from datetime import date, datetime
from io import BytesIO

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from ia_platform.core import logic as L
from ia_platform.exports import rapport_excel as R

DECOUPAGES = ["Mois", "Trimestre", "Semestre", "Année"]
STATUTS = ["En attente", "En cours de saisie", "Reçu", "Rien à signaler"]
REPONDU = ("Reçu", "Rien à signaler")
PRIORITES = ["Haute", "Moyenne", "Basse"]
CONFIANCES = ["Ferme", "Probable", "Possible"]
UNITES_TYPE = {"GPU": "GPU", "CPU": "vCPU", "RAM": "Go", "Stockage": "To", "Licence": "licences", "Instance cloud": "instances",
               "Serveur": "serveurs", "Réseau": "ports", "Service": "jours"}


# ------------------------------------------------------------------ périodes
def _cle_periode(m, decoupage):
    if decoupage == "Mois":
        return L.mois_txt_court(m)
    if decoupage == "Trimestre":
        return f"T{(m.month - 1) // 3 + 1} {m.year}"
    if decoupage == "Semestre":
        return f"S{(m.month - 1) // 6 + 1} {m.year}"
    return str(m.year)


def periodes(camp):
    """Liste ordonnée [(libellé, [mois…])] couvrant la période de la campagne."""
    debut, fin = L.d(camp["debut"]), L.d(camp["fin"])
    out = {}
    m = debut
    while m <= fin:
        out.setdefault(_cle_periode(m, camp["decoupage"]), []).append(m)
        m = L.d(L.ajouter_mois(m, 1))
    return list(out.items())


def libelles_periodes(camp):
    return [p for p, _ in periodes(camp)]


def jour(x):
    """Date ou None (gère les valeurs vides / NaN venant de la base)."""
    if x is None or (isinstance(x, float) and pd.isna(x)) or not str(x).strip() or str(x) in ("nan", "None", "NaT"):
        return None
    v = L.date_fr(x)
    return None if v is None or pd.isna(v) else v


# ------------------------------------------------------------------ campagnes
def campagnes_df():
    return L.q("SELECT * FROM campagnes ORDER BY debut DESC, id DESC")


def campagne(cid):
    df = L.q("SELECT * FROM campagnes WHERE id=?", (cid,))
    if df.empty:
        return None
    c = df.iloc[0].to_dict()
    c["ressources"] = json.loads(c["ressources"] or "[]")
    return c


def ressources_suggerees():
    """Ressources proposées par défaut : assets actifs du catalogue (hors services et réseau, hors instances découpées en parts)."""
    a = L.assets_df()
    a = a[(a.statut != "Retiré") & ~a.type.isin(["Service", "Réseau"]) & ~a.refacturation.isin(["part_vcpu", "part_gpu"])]
    out = []
    for _, r in a.iterrows():
        unite = "vCPU" if pd.notna(r.parent_id) else UNITES_TYPE.get(r.type, "unités")
        out.append({"nom": r.nom, "unite": unite, "asset_id": r.id})
    return out


def _verifier(nom, debut, fin, decoupage, ressources):
    if not str(nom or "").strip():
        raise ValueError("Donnez un nom à la campagne.")
    if L.d(fin) < L.d(debut):
        raise ValueError("La fin de la période doit être après le début.")
    if decoupage not in DECOUPAGES:
        raise ValueError("Découpage inconnu.")
    noms = [r["nom"].strip() for r in ressources if str(r.get("nom") or "").strip()]
    if not noms:
        raise ValueError("Proposez au moins une ressource aux métiers.")
    if len(set(noms)) != len(noms):
        raise ValueError("Deux ressources portent le même nom.")


def _ressources_propres(ressources):
    out = []
    for r in ressources:
        nom = str(r.get("nom") or "").strip()
        if nom:
            aid = r.get("asset_id")
            out.append({"nom": nom, "unite": str(r.get("unite") or "unités").strip() or "unités",
                        "asset_id": aid if isinstance(aid, str) and aid else None})
    return out


def creer_campagne(nom, debut, fin, decoupage, date_limite, metiers, ressources, contacts=None):
    """Crée une campagne ; contacts = {métier: (contact, email)} (repris de la campagne précédente)."""
    _verifier(nom, debut, fin, decoupage, ressources)
    debut, fin = L.mois_debut(debut), L.mois_debut(fin)
    cid = f"CP-{debut.year}-{len(L.q('SELECT id FROM campagnes WHERE id LIKE ?', (f'CP-{debut.year}-%',))) + 1:02d}"
    while campagne(cid) is not None:
        cid = cid[:-2] + f"{int(cid[-2:]) + 1:02d}"
    contacts = contacts or {}
    with L.conn() as c:
        c.execute("INSERT INTO campagnes VALUES (?,?,?,?,?,?,?,?,?)",
                  (cid, nom.strip(), L.iso(debut), L.iso(fin), decoupage, L.iso(date_limite), "Ouverte", date.today().isoformat(),
                   json.dumps(_ressources_propres(ressources), ensure_ascii=False)))
        for m in metiers:
            ct, em = contacts.get(m, ("", ""))
            c.execute("INSERT INTO campagne_metiers VALUES (?,?,?,?,?,?,?,?)", (cid, m, ct, em, "En attente", None, None, 0))
    return cid


def modifier_campagne(cid, nom, debut, fin, decoupage, date_limite, statut, ressources):
    camp = campagne(cid)
    _verifier(nom, debut, fin, decoupage, ressources)
    debut, fin = L.mois_debut(debut), L.mois_debut(fin)
    b = besoins_df(cid)
    if len(b):
        if (L.iso(debut), L.iso(fin), decoupage) != (camp["debut"], camp["fin"], camp["decoupage"]):
            raise ValueError("Des besoins sont déjà saisis : la période et le découpage ne peuvent plus changer.")
        utilisees = set(b.ressource)
        restantes = {r["nom"] for r in _ressources_propres(ressources)}
        retirees = sorted(utilisees - restantes)
        if retirees:
            raise ValueError("Ressource(s) utilisée(s) dans des besoins, impossible de la retirer : " + ", ".join(retirees) + ".")
    L.run("UPDATE campagnes SET nom=?, debut=?, fin=?, decoupage=?, date_limite=?, statut=?, ressources=? WHERE id=?",
          (nom.strip(), L.iso(debut), L.iso(fin), decoupage, L.iso(date_limite), statut,
           json.dumps(_ressources_propres(ressources), ensure_ascii=False), cid))


def supprimer_campagne(cid):
    with L.conn() as c:
        for t, col in (("besoins", "campagne_id"), ("campagne_metiers", "campagne_id"), ("campagnes", "id")):
            c.execute(f"DELETE FROM {t} WHERE {col}=?", (cid,))


# ------------------------------------------------------------------ métiers
def metiers_df(cid):
    m = L.q("SELECT * FROM campagne_metiers WHERE campagne_id=? ORDER BY metier", (cid,))
    n = L.q("SELECT metier, COUNT(*) AS n FROM besoins WHERE campagne_id=? GROUP BY metier", (cid,))
    m = m.merge(n, on="metier", how="left")
    m["n"] = m.n.fillna(0).astype(int)
    m["nb_relances"] = m.nb_relances.fillna(0).astype(int)
    return m


def ajouter_metiers(cid, metiers):
    with L.conn() as c:
        for m in metiers:
            c.execute("INSERT OR IGNORE INTO campagne_metiers VALUES (?,?,?,?,?,?,?,?)", (cid, m, "", "", "En attente", None, None, 0))


def retirer_metier(cid, metier):
    with L.conn() as c:
        c.execute("DELETE FROM besoins WHERE campagne_id=? AND metier=?", (cid, metier))
        c.execute("DELETE FROM campagne_metiers WHERE campagne_id=? AND metier=?", (cid, metier))


def enregistrer_contacts(cid, df):
    with L.conn() as c:
        for _, r in df.iterrows():
            c.execute("UPDATE campagne_metiers SET contact=?, email=? WHERE campagne_id=? AND metier=?",
                      (str(r.contact or "").strip(), str(r.email or "").strip(), cid, r.metier))


def changer_statut(cid, metier, statut):
    if statut not in STATUTS:
        raise ValueError("Statut inconnu.")
    if statut == "Rien à signaler" and len(L.q("SELECT id FROM besoins WHERE campagne_id=? AND metier=?", (cid, metier))):
        raise ValueError("Ce métier a des besoins saisis : supprimez-les avant de marquer « Rien à signaler ».")
    L.run("UPDATE campagne_metiers SET statut=?, date_maj=? WHERE campagne_id=? AND metier=?",
          (statut, date.today().isoformat(), cid, metier))


def noter_relance(cid, metiers):
    with L.conn() as c:
        for m in metiers:
            c.execute("UPDATE campagne_metiers SET date_relance=?, nb_relances=COALESCE(nb_relances,0)+1 WHERE campagne_id=? AND metier=?",
                      (date.today().isoformat(), cid, m))


def clients_du_metier(metier):
    return L.q("SELECT id, nom FROM clients WHERE entite=? AND COALESCE(statut,'')<>'Inactif' ORDER BY nom", (metier,))


# ------------------------------------------------------------------ besoins
def besoins_df(cid, metier=None):
    sql = "SELECT b.*, c.nom AS client FROM besoins b LEFT JOIN clients c ON c.id=b.client_id WHERE b.campagne_id=?"
    p = [cid]
    if metier:
        sql += " AND b.metier=?"
        p.append(metier)
    df = L.q(sql + " ORDER BY b.metier, b.id", tuple(p))
    df["quantites"] = [json.loads(x or "{}") for x in df.quantites]
    return df


def tableau_saisie(cid, metier):
    """Besoins d'un métier au format « une colonne par période » (pour l'éditeur et le modèle Excel)."""
    camp = campagne(cid)
    pers = libelles_periodes(camp)
    unites = {r["nom"]: r["unite"] for r in camp["ressources"]}
    b = besoins_df(cid, metier)
    rows = []
    for _, r in b.iterrows():
        row = {"Client": r.client if isinstance(r.client, str) else "", "Projet / usage": r.projet or "", "Ressource": r.ressource,
               "Unité": unites.get(r.ressource, "")}
        row.update({p: float(r.quantites.get(p, 0) or 0) for p in pers})
        row.update({"Priorité": r.priorite or "", "Confiance": r.confiance or "", "Commentaire": r.commentaire or ""})
        rows.append(row)
    cols = ["Client", "Projet / usage", "Ressource", "Unité"] + pers + ["Priorité", "Confiance", "Commentaire"]
    df = pd.DataFrame(rows, columns=cols)
    for p in pers:
        df[p] = df[p].astype(float)
    return df


def _texte(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v).strip()


def lignes_valides(cid, metier, df):
    """Contrôle un tableau saisi (éditeur ou Excel) ; renvoie (lignes, erreurs). Les lignes entièrement vides sont ignorées."""
    camp = campagne(cid)
    pers = libelles_periodes(camp)
    ress = {r["nom"] for r in camp["ressources"]}
    clients = clients_du_metier(metier)
    par_nom = dict(zip(clients.nom, clients.id))
    lignes, erreurs = [], []
    for i, (_, r) in enumerate(df.iterrows(), start=1):
        qte = {}
        for p in pers:
            v = r.get(p)
            try:
                v = L.nombre(v)
            except ValueError:
                erreurs.append(f"Ligne {i} : quantité « {v} » non numérique en {p}.")
                v = 0
            if v < 0:
                erreurs.append(f"Ligne {i} : quantité négative en {p}.")
            if v:
                qte[p] = v
        projet, ressource, client = _texte(r.get("Projet / usage")), _texte(r.get("Ressource")), _texte(r.get("Client"))
        prio, conf, com = _texte(r.get("Priorité")), _texte(r.get("Confiance")), _texte(r.get("Commentaire"))
        if not (projet or ressource or qte or com):
            continue
        if not ressource:
            erreurs.append(f"Ligne {i} : choisissez une ressource.")
        elif ressource not in ress:
            erreurs.append(f"Ligne {i} : ressource « {ressource} » absente de la campagne.")
        if not qte:
            erreurs.append(f"Ligne {i} : indiquez au moins une quantité.")
        if not projet and not client:
            erreurs.append(f"Ligne {i} : indiquez le projet ou le client concerné.")
        if client and client not in par_nom:
            erreurs.append(f"Ligne {i} : client « {client} » inconnu pour le métier {metier}.")
        if prio and prio not in PRIORITES:
            erreurs.append(f"Ligne {i} : priorité « {prio} » inconnue ({', '.join(PRIORITES)}).")
        if conf and conf not in CONFIANCES:
            erreurs.append(f"Ligne {i} : confiance « {conf} » inconnue ({', '.join(CONFIANCES)}).")
        lignes.append((par_nom.get(client), projet, ressource, qte, prio or "Moyenne", conf or "Probable", com))
    return lignes, erreurs


def enregistrer_besoins(cid, metier, df, statut=None):
    """Remplace les besoins d'un métier ; lève ValueError si le tableau contient des erreurs."""
    camp = campagne(cid)
    if camp["statut"] != "Ouverte":
        raise ValueError("La campagne est clôturée : rouvrez-la pour modifier les besoins.")
    lignes, erreurs = lignes_valides(cid, metier, df)
    if erreurs:
        raise ValueError("\n".join(erreurs))
    actuel = L.q("SELECT statut FROM campagne_metiers WHERE campagne_id=? AND metier=?", (cid, metier))
    if actuel.empty:
        raise ValueError(f"Le métier {metier} ne fait pas partie de la campagne.")
    if statut is None:
        statut = actuel.statut.iloc[0]
        if statut in ("En attente", "Rien à signaler"):
            statut = "En cours de saisie" if lignes else statut
    with L.conn() as c:
        c.execute("DELETE FROM besoins WHERE campagne_id=? AND metier=?", (cid, metier))
        c.executemany("INSERT INTO besoins (campagne_id, metier, client_id, projet, ressource, quantites, priorite, confiance, commentaire) "
                      "VALUES (?,?,?,?,?,?,?,?,?)",
                      [(cid, metier, cl, pj, rs, json.dumps(q, ensure_ascii=False), pr, cf, cm) for cl, pj, rs, q, pr, cf, cm in lignes])
        c.execute("UPDATE campagne_metiers SET statut=?, date_maj=? WHERE campagne_id=? AND metier=?",
                  (statut, date.today().isoformat(), cid, metier))
    return len(lignes)


def recap_metier(cid, metier):
    """Total par ressource et par période, avec un coût estimé au coût actuel des assets liés."""
    camp = campagne(cid)
    pers = periodes(camp)
    b = besoins_df(cid, metier)
    if b.empty:
        return pd.DataFrame()
    a = L.assets_df().set_index("id")
    rows = []
    for r in camp["ressources"]:
        sel = b[b.ressource == r["nom"]]
        if sel.empty:
            continue
        row = {"Ressource": r["nom"], "Unité": r["unite"]}
        cout_u = float(a.cout_mois.get(r["asset_id"], float("nan"))) if r.get("asset_id") else float("nan")
        cout = 0.0
        for p, mois in pers:
            v = sum(float(q_.get(p, 0) or 0) for q_ in sel.quantites)
            row[p] = v
            cout += v * len(mois) * (cout_u if cout_u == cout_u else 0)
        row["Coût estimé"] = cout if cout_u == cout_u else None
        rows.append(row)
    return pd.DataFrame(rows)


def offres_en_cours(metier):
    """Ce que les clients du métier ont déjà aujourd'hui (offres et options en cours)."""
    out = []
    for _, c in clients_du_metier(metier).iterrows():
        lg = L.lignes_ouvertes_au(c.id, L.mois_debut(date.today()))
        for _, l_ in lg.iterrows():
            out.append({"Client": c.nom, "Élément": l_.libelle, "Qté": l_.qte})
    return pd.DataFrame(out, columns=["Client", "Élément", "Qté"])


# ------------------------------------------------------------------ Excel : modèle à envoyer
LIGNE_ENTETE = 6
NB_LIGNES = 150


def modele_excel(cid, metier):
    camp = campagne(cid)
    pers = libelles_periodes(camp)
    wb = Workbook()
    ws = wb.active
    ws.title = "Besoins"
    R._titre(ws, f"{camp['nom']} · {metier}",
             f"Période : {L.mois_txt_court(camp['debut'])} → {L.mois_txt_court(camp['fin'])} · par {camp['decoupage'].lower()}"
             f" · à renvoyer avant le {L.date_fr(camp['date_limite']):%d/%m/%Y}")
    consignes = ["Une ligne par projet et par ressource. Indiquez les quantités EN PLUS de ce que vous avez déjà.",
                 "Ressource, client, priorité et confiance : choisissez dans la liste déroulante. L'unité se remplit seule."]
    for i, t in enumerate(consignes):
        ws.cell(row=3 + i, column=1, value=t).font = R._f(10, color=R.GREY)
    cols = ["Client", "Projet / usage", "Ressource", "Unité"] + pers + ["Priorité", "Confiance", "Commentaire"]
    R._entetes(ws, LIGNE_ENTETE, cols)
    first, last = LIGNE_ENTETE + 1, LIGNE_ENTETE + NB_LIGNES
    # listes (feuille masquée)
    li = wb.create_sheet("Listes")
    li.append(["Ressource", "Unité", "Client", "Priorité", "Confiance"])
    clients = list(clients_du_metier(metier).nom)
    n = max(len(camp["ressources"]), len(clients), len(PRIORITES), len(CONFIANCES))
    for i in range(n):
        r = camp["ressources"][i] if i < len(camp["ressources"]) else None
        li.append([r["nom"] if r else None, r["unite"] if r else None, clients[i] if i < len(clients) else None,
                   PRIORITES[i] if i < len(PRIORITES) else None, CONFIANCES[i] if i < len(CONFIANCES) else None])
    li.sheet_state = "hidden"
    ref = wb.create_sheet("_ref")
    ref.append(["campagne", cid])
    ref.append(["metier", metier])
    ref.sheet_state = "hidden"
    # validations
    nr, nc = len(camp["ressources"]), len(clients)
    ccol = {n_: get_column_letter(i + 1) for i, n_ in enumerate(cols)}
    def dv(formule, col, msg):
        v = DataValidation(type="list", formula1=formule, allow_blank=True, showErrorMessage=True, errorTitle="Valeur non prévue", error=msg)
        v.add(f"{ccol[col]}{first}:{ccol[col]}{last}")
        ws.add_data_validation(v)
    dv(f"=Listes!$A$2:$A${nr + 1}", "Ressource", "Choisissez une ressource de la liste.")
    if nc:
        dv(f"=Listes!$C$2:$C${nc + 1}", "Client", "Choisissez un client de la liste ou laissez vide pour un nouveau projet.")
    dv(f"=Listes!$D$2:$D${len(PRIORITES) + 1}", "Priorité", "Haute, Moyenne ou Basse.")
    dv(f"=Listes!$E$2:$E${len(CONFIANCES) + 1}", "Confiance", "Ferme, Probable ou Possible.")
    vq = DataValidation(type="decimal", operator="greaterThanOrEqual", formula1="0", allow_blank=True, showErrorMessage=True,
                        errorTitle="Quantité", error="Saisissez un nombre positif ou nul.")
    vq.add(f"{ccol[pers[0]]}{first}:{ccol[pers[-1]]}{last}")
    ws.add_data_validation(vq)
    # données existantes + formule d'unité
    exist = tableau_saisie(cid, metier)
    saisie = PatternFill("solid", fgColor="FFFFFF")
    for i in range(NB_LIGNES):
        row = first + i
        rec = exist.iloc[i] if i < len(exist) else None
        for j, col in enumerate(cols, start=1):
            cell = ws.cell(row=row, column=j)
            if col == "Unité":
                cell.value = f'=IFERROR(VLOOKUP({ccol["Ressource"]}{row},Listes!$A:$B,2,FALSE),"")'
                cell.font = R._f(10, color=R.GREY)
                cell.fill = R.BAND
                continue
            if rec is not None:
                v = rec[col]
                cell.value = (float(v) if v else None) if col in pers else (v or None)
            cell.fill = saisie
            cell.border = R.Border(bottom=R.thin)
            if col in pers:
                cell.number_format = "#,##0.##"
                cell.alignment = Alignment(horizontal="right")
    R._largeurs(ws, {ccol["Client"]: 26, ccol["Projet / usage"]: 32, ccol["Ressource"]: 34, ccol["Unité"]: 11,
                     ccol["Priorité"]: 11, ccol["Confiance"]: 12, ccol["Commentaire"]: 44})
    for p in pers:
        ws.column_dimensions[ccol[p]].width = 11
    ws.freeze_panes = ws.cell(row=first, column=3)
    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


def modeles_zip(cid):
    import zipfile
    camp = campagne(cid)
    bio = BytesIO()
    with zipfile.ZipFile(bio, "w", zipfile.ZIP_DEFLATED) as z:
        for m in metiers_df(cid).metier:
            z.writestr(f"{camp['nom']} - {m}.xlsx", modele_excel(cid, m))
    return bio.getvalue()


# ------------------------------------------------------------------ Excel : import des fichiers reçus
def lire_modele(fichier):
    """Lit un modèle rempli ; renvoie (campagne_id, métier, DataFrame) — campagne et métier peuvent être None."""
    wb = load_workbook(fichier, data_only=False)
    cid = metier = None
    if "_ref" in wb.sheetnames:
        for k, v in wb["_ref"].iter_rows(values_only=True):
            if k == "campagne":
                cid = v
            elif k == "metier":
                metier = v
    ws = wb["Besoins"] if "Besoins" in wb.sheetnames else wb.active
    lignes = list(ws.iter_rows(values_only=True))
    h = next((i for i, r in enumerate(lignes) if r and "Ressource" in r and "Projet / usage" in r), None)
    if h is None:
        raise ValueError("Colonnes « Projet / usage » et « Ressource » introuvables : utilisez le modèle téléchargé depuis l'application.")
    entetes = [str(x).strip() if x is not None else "" for x in lignes[h]]
    df = pd.DataFrame([list(r) + [None] * (len(entetes) - len(r)) for r in lignes[h + 1:]], columns=entetes)
    df = df.loc[:, [c for c in df.columns if c]]
    if "Unité" in df.columns:
        df = df.drop(columns="Unité")
    return cid, metier, df


def importer_modele(fichier, cid, metier=None, marquer_recu=True):
    f_cid, f_met, df = lire_modele(fichier)
    if f_cid and f_cid != cid:
        raise ValueError(f"Ce fichier appartient à une autre campagne ({f_cid}).")
    metier = f_met or metier
    if not metier:
        raise ValueError("Métier introuvable dans le fichier : choisissez-le avant d'importer.")
    pers = libelles_periodes(campagne(cid))
    manquantes = [p for p in pers if p not in df.columns]
    if manquantes:
        raise ValueError("Colonnes de période absentes du fichier : " + ", ".join(manquantes) + ".")
    n = enregistrer_besoins(cid, metier, df, statut="Reçu" if marquer_recu else None)
    return metier, n


# ------------------------------------------------------------------ Excel : export complet
def export_excel(cid):
    camp = campagne(cid)
    pers = libelles_periodes(camp)
    met = metiers_df(cid)
    b = besoins_df(cid)
    unites = {r["nom"]: r["unite"] for r in camp["ressources"]}
    wb = Workbook()

    ws = wb.active
    ws.title = "Campagne"
    R._titre(ws, camp["nom"], f"Export du {datetime.now():%d/%m/%Y %H:%M}")
    infos = [("Identifiant", cid), ("Période", f"{L.mois_txt_court(camp['debut'])} → {L.mois_txt_court(camp['fin'])}"),
             ("Découpage", camp["decoupage"]), ("Date limite de réponse", L.date_fr(camp["date_limite"])), ("Statut", camp["statut"]),
             ("Créée le", jour(camp["date_creation"])), ("Métiers sollicités", len(met)),
             ("Réponses", int(met.statut.isin(REPONDU).sum())), ("Besoins collectés", len(b))]
    for i, (k, v) in enumerate(infos, start=4):
        ws.cell(row=i, column=1, value=k).font = R._f(11, True)
        c = ws.cell(row=i, column=2, value=v)
        if isinstance(v, date):
            c.number_format = R.DATE
            c.alignment = Alignment(horizontal="left")
    r0 = len(infos) + 6
    ws.cell(row=r0 - 1, column=1, value="Ressources proposées").font = R._f(12, True)
    R._entetes(ws, r0, ["Ressource", "Unité", "Asset lié"])
    for i, r in enumerate(camp["ressources"], start=r0 + 1):
        ws.cell(row=i, column=1, value=r["nom"]); ws.cell(row=i, column=2, value=r["unite"]); ws.cell(row=i, column=3, value=r.get("asset_id"))
    R._largeurs(ws, {"A": 28, "B": 34, "C": 12})

    ws = wb.create_sheet("Suivi des réponses")
    R._titre(ws, "Suivi des réponses", camp["nom"])
    cols = ["Métier", "Contact", "Email", "Statut", "Besoins", "Dernière mise à jour", "Dernière relance", "Relances"]
    R._entetes(ws, 4, cols)
    for i, (_, r) in enumerate(met.iterrows(), start=5):
        vals = [r.metier, r.contact, r.email, r.statut, int(r.n), jour(r.date_maj), jour(r.date_relance), int(r.nb_relances)]
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=i, column=j, value=v)
            if isinstance(v, date):
                c.number_format = R.DATE
    if len(met):
        R._table(ws, "Suivi", f"A4:H{4 + len(met)}")
    R._largeurs(ws, {"A": 22, "B": 20, "C": 34, "D": 18, "E": 10, "F": 18, "G": 16, "H": 10})

    ws = wb.create_sheet("Besoins")
    R._titre(ws, "Besoins des métiers", f"{camp['nom']} · quantités en plus de l'existant, par {camp['decoupage'].lower()}")
    cols = ["Métier", "Client", "Projet / usage", "Ressource", "Unité"] + pers + ["Total", "Priorité", "Confiance", "Commentaire"]
    R._entetes(ws, 4, cols)
    for i, (_, r) in enumerate(b.iterrows(), start=5):
        q_ = [float(r.quantites.get(p, 0) or 0) for p in pers]
        vals = [r.metier, r.client if isinstance(r.client, str) else None, r.projet, r.ressource, unites.get(r.ressource)] + q_
        for j, v in enumerate(vals, start=1):
            c = ws.cell(row=i, column=j, value=v)
            if j > 5:
                c.number_format = "#,##0.##"
        t = ws.cell(row=i, column=len(vals) + 1, value=f"=SUM({get_column_letter(6)}{i}:{get_column_letter(5 + len(pers))}{i})")
        t.number_format = "#,##0.##"
        t.font = R._f(11, True)
        for j, v in enumerate([r.priorite, r.confiance, r.commentaire], start=len(vals) + 2):
            ws.cell(row=i, column=j, value=v)
    if len(b):
        R._table(ws, "Besoins", f"A4:{get_column_letter(len(cols))}{4 + len(b)}")
    R._largeurs(ws, {"A": 18, "B": 24, "C": 30, "D": 32, "E": 10})
    for j in range(6, 7 + len(pers)):
        ws.column_dimensions[get_column_letter(j)].width = 11
    for j, w in zip(range(7 + len(pers), 10 + len(pers)), (10, 11, 40)):
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.freeze_panes = "E5"

    ws = wb.create_sheet("Besoins par période")
    R._titre(ws, "Besoins par période (format liste)", "Une ligne par besoin et par période : pratique pour un tableau croisé dynamique.")
    cols = ["Métier", "Client", "Projet / usage", "Ressource", "Unité", "Période", "Début de période", "Quantité", "Priorité", "Confiance"]
    R._entetes(ws, 4, cols)
    i = 5
    for _, r in b.iterrows():
        for p, mois in periodes(camp):
            v = float(r.quantites.get(p, 0) or 0)
            if not v:
                continue
            vals = [r.metier, r.client if isinstance(r.client, str) else None, r.projet, r.ressource, unites.get(r.ressource), p, mois[0], v,
                    r.priorite, r.confiance]
            for j, x in enumerate(vals, start=1):
                c = ws.cell(row=i, column=j, value=x)
                if j == 7:
                    c.number_format = R.DATE
            i += 1
    if i > 5:
        R._table(ws, "BesoinsPeriode", f"A4:J{i - 1}")
    R._largeurs(ws, {"A": 18, "B": 24, "C": 30, "D": 32, "E": 10, "F": 12, "G": 15, "H": 10, "I": 10, "J": 11})
    ws.freeze_panes = "A5"

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


# ------------------------------------------------------------------ démonstration
def seed_demo():
    """Campagne d'exemple « Besoins 2027 » sur les données de démonstration."""
    if len(L.q("SELECT id FROM campagnes")):
        return
    ids = {r.nom: r.id for r in L.assets_df().itertuples()}
    ress = [("GPU H100 80 Go", "GPU"), ("GPU L40S 48 Go", "GPU"), ("GPU L4 24 Go", "GPU"), ("vCPU", "vCPU"),
            ("Stockage NVMe (To)", "To"), ("Licence plateforme MLOps (utilisateur)", "licences")]
    ressources = [{"nom": n, "unite": u, "asset_id": ids.get(n)} for n, u in ress]
    metiers = ["R&D", "Service Client", "Risques", "Marketing", "Industrie", "Juridique", "RH", "Finance"]
    contacts = {"R&D": ("C. Martin", "pricing.lab@entreprise.example"), "Service Client": ("L. Bernard", "chatbot.service@entreprise.example"),
                "Risques": ("A. Peeters", "scoring.credit@entreprise.example"), "Marketing": ("M. García", "data.marketing@entreprise.example"),
                "Industrie": ("J. Müller", "vision.qualite@entreprise.example"), "Juridique": ("H. Lefèvre", "assistant.juridique@entreprise.example"),
                "RH": ("N. Durand", "rh.analytics@entreprise.example"), "Finance": ("S. Petit", "audit.ia@entreprise.example")}
    cid = creer_campagne("Besoins 2027", date(2027, 1, 1), date(2027, 12, 1), "Trimestre", date(2026, 11, 30), metiers, ressources, contacts)
    L.run("UPDATE campagnes SET date_creation='2026-10-06' WHERE id=?", (cid,))
    cols = ["Client", "Projet / usage", "Ressource", "T1 2027", "T2 2027", "T3 2027", "T4 2027", "Priorité", "Confiance", "Commentaire"]
    saisies = {
        "Risques": [("Scoring Crédit", "Scoring crédit v2", "GPU H100 80 Go", 4, 4, 8, 8, "Haute", "Ferme", "Ré-entraînement mensuel du modèle"),
                    ("Détection Fraude", "Détection de fraude temps réel", "vCPU", 32, 32, 64, 64, "Moyenne", "Probable", "Montée en charge au S2"),
                    ("", "Analystes risques", "Licence plateforme MLOps (utilisateur)", 5, 5, 5, 5, "Moyenne", "Ferme", "5 nouveaux analystes")],
        "Service Client": [("Agent Service Client", "Assistant agents", "GPU L40S 48 Go", 1, 2, 2, 2, "Haute", "Probable", ""),
                           ("Agent Service Client", "Assistant agents", "Licence plateforme MLOps (utilisateur)", 10, 10, 15, 15, "Moyenne", "Probable", "")],
        "R&D": [("Modèles de Langage", "Fine-tuning LLM interne", "GPU H100 80 Go", 0, 8, 8, 0, "Moyenne", "Possible", "Selon arbitrage du comité"),
                ("Modèles de Langage", "Corpus d'entraînement", "Stockage NVMe (To)", 10, 20, 20, 20, "Basse", "Probable", "")],
        "Marketing": [("Segmentation Clients", "Génération de contenu", "Licence plateforme MLOps (utilisateur)", 3, 3, 3, 3, "Basse", "Probable", "")],
        "Industrie": [("Prévision Stocks", "Prévision des stocks", "vCPU", 16, 16, 32, 32, "Moyenne", "Probable", "Saisie en cours")],
    }
    for m, rows in saisies.items():
        enregistrer_besoins(cid, m, pd.DataFrame(rows, columns=cols), statut="En cours de saisie" if m == "Industrie" else "Reçu")
    changer_statut(cid, "Juridique", "Rien à signaler")
    dates = {"Risques": "2026-10-20", "Service Client": "2026-10-22", "R&D": "2026-10-23", "Marketing": "2026-10-24", "Industrie": "2026-10-25",
             "Juridique": "2026-10-21"}
    with L.conn() as c:
        for m, d_ in dates.items():
            c.execute("UPDATE campagne_metiers SET date_maj=? WHERE campagne_id=? AND metier=?", (d_, cid, m))
