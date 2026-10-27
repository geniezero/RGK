"""Données (SQLite) et calculs de l'application IA Platform."""
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from ia_platform.config import DB_PATH, DEVIS_DIR, MODELES_DIR as DATA_DIR  # noqa: E402  (DATA_DIR : modèles CSV d'import)

MOIS = ["Janv.", "Févr.", "Mars", "Avr.", "Mai", "Juin", "Juil.", "Août", "Sept.", "Oct.", "Nov.", "Déc."]
MOIS_LONG = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
FACTEURS = {"Heure": 365 * 24 / 12, "Jour": 365 / 12, "Semaine": 52 / 12, "Mois": 1.0, "An": 1 / 12}
UNITES = list(FACTEURS)
STATUTS_CLIENT = ["Actif", "Prospect", "Inactif"]
STATUTS_OFFRE = ["Active", "Brouillon", "Retirée"]
STATUTS_ASSET = ["Actif", "Retiré"]
ASSET_EXTRA = [("region", "TEXT"), ("vcpu", "REAL"), ("ram_go", "REAL"), ("stockage_go", "REAL"), ("gpu", "REAL"), ("gpu_modele", "TEXT"),
               ("reseau_gbs", "REAL"), ("refacturation", "TEXT"), ("parent_id", "TEXT")]
ASSET_COLS = ["id", "type", "nom", "fournisseur", "prix", "unite", "qte_parc", "date_effet", "statut"] + [c for c, _ in ASSET_EXTRA]
REFACTURATIONS = {None: "—", "entiere": "Instance entière", "part_vcpu": "À la part (vCPU)", "part_gpu": "À la part (GPU)"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS parametres (cle TEXT PRIMARY KEY, valeur TEXT);
CREATE TABLE IF NOT EXISTS listes (categorie TEXT, valeur TEXT, PRIMARY KEY (categorie, valeur));
CREATE TABLE IF NOT EXISTS assets (
    id TEXT PRIMARY KEY, type TEXT, nom TEXT, fournisseur TEXT, prix REAL, unite TEXT,
    qte_parc REAL, date_effet TEXT, statut TEXT, region TEXT, vcpu REAL, ram_go REAL, stockage_go REAL, gpu REAL,
    gpu_modele TEXT, reseau_gbs REAL, refacturation TEXT, parent_id TEXT);
CREATE TABLE IF NOT EXISTS mesures (date TEXT, asset_id TEXT, client_id TEXT, cpu_moy REAL, cpu_max REAL, gpu_moy REAL);
CREATE TABLE IF NOT EXISTS prix_hist (
    id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id TEXT, prix REAL, unite TEXT, du TEXT, au TEXT, motif TEXT);
CREATE TABLE IF NOT EXISTS clients (
    id TEXT PRIMARY KEY, nom TEXT, entite TEXT, pays TEXT, responsable TEXT, email TEXT, statut TEXT, date_entree TEXT);
CREATE TABLE IF NOT EXISTS offres (id TEXT PRIMARY KEY, nom TEXT, description TEXT, statut TEXT, date_effet TEXT);
CREATE TABLE IF NOT EXISTS composition_hist (offre_id TEXT, asset_id TEXT, qte REAL, du TEXT, au TEXT);
CREATE TABLE IF NOT EXISTS composition (offre_id TEXT, asset_id TEXT, qte REAL, PRIMARY KEY (offre_id, asset_id));
CREATE TABLE IF NOT EXISTS offre_retirables (offre_id TEXT, asset_id TEXT, PRIMARY KEY (offre_id, asset_id));
CREATE TABLE IF NOT EXISTS aff_retraits (aff_id TEXT, asset_id TEXT, qte REAL, PRIMARY KEY (aff_id, asset_id));
CREATE TABLE IF NOT EXISTS affectations (
    id TEXT PRIMARY KEY, client_id TEXT, operation TEXT, element TEXT, code TEXT, qte REAL, debut TEXT, fin TEXT, ref TEXT, motif TEXT);
CREATE TABLE IF NOT EXISTS devis (
    id TEXT PRIMARY KEY, date_devis TEXT, client_id TEXT, debut TEXT, duree INTEGER, validite INTEGER,
    statut TEXT, objet TEXT, commentaire TEXT, date_decision TEXT, version INTEGER, date_envoi TEXT, ref_bc TEXT, signataire TEXT,
    motif_refus TEXT, fin_mode TEXT, retour TEXT, retour_date TEXT, retour_note TEXT, fichier TEXT);
CREATE TABLE IF NOT EXISTS devis_lignes (devis_id TEXT, num INTEGER, element TEXT, code TEXT, qte REAL, remplace TEXT, PRIMARY KEY (devis_id, num));
CREATE TABLE IF NOT EXISTS devis_historique (id INTEGER PRIMARY KEY AUTOINCREMENT, devis_id TEXT, date TEXT, evenement TEXT, detail TEXT);
CREATE TABLE IF NOT EXISTS devis_versions (devis_id TEXT, version INTEGER, date TEXT, pdf BLOB, PRIMARY KEY (devis_id, version));
CREATE TABLE IF NOT EXISTS exercices (
    annee INTEGER PRIMARY KEY, statut TEXT, mois_ref INTEGER, date_ouverture TEXT, date_cloture TEXT,
    cout_parc REAL, refacture REAL, ecart REAL, commentaire TEXT);
CREATE TABLE IF NOT EXISTS budgets (annee INTEGER, client_id TEXT, montant REAL, PRIMARY KEY (annee, client_id));
CREATE TABLE IF NOT EXISTS budget_cles (annee INTEGER, cle TEXT, type TEXT, budget REAL, ordre INTEGER, PRIMARY KEY (annee, cle));
CREATE TABLE IF NOT EXISTS reel_mensuel (annee INTEGER, cle TEXT, mois INTEGER, montant REAL, PRIMARY KEY (annee, cle, mois));
CREATE TABLE IF NOT EXISTS ajustements (
    id INTEGER PRIMARY KEY AUTOINCREMENT, annee INTEGER, mois INTEGER, client_id TEXT, libelle TEXT, montant REAL, nature TEXT);
CREATE TABLE IF NOT EXISTS conso_figee (
    annee INTEGER, aff_id TEXT, client_id TEXT, client TEXT, entite TEXT, pays TEXT, operation TEXT, element TEXT,
    code TEXT, libelle TEXT, type TEXT, qte REAL, debut TEXT, fin TEXT, m1 REAL, m2 REAL, m3 REAL, m4 REAL, m5 REAL, m6 REAL, m7 REAL, m8 REAL, m9 REAL, m10 REAL, m11 REAL, m12 REAL);
CREATE TABLE IF NOT EXISTS conso_type_figee (annee INTEGER, client_id TEXT, type TEXT, m1 REAL, m2 REAL, m3 REAL, m4 REAL, m5 REAL, m6 REAL, m7 REAL, m8 REAL, m9 REAL, m10 REAL, m11 REAL, m12 REAL);
CREATE TABLE IF NOT EXISTS archives (id INTEGER PRIMARY KEY AUTOINCREMENT, annee INTEGER, nom TEXT, date TEXT, contenu BLOB);
CREATE TABLE IF NOT EXISTS campagnes (
    id TEXT PRIMARY KEY, nom TEXT, debut TEXT, fin TEXT, decoupage TEXT, date_limite TEXT, statut TEXT, date_creation TEXT, ressources TEXT);
CREATE TABLE IF NOT EXISTS campagne_metiers (
    campagne_id TEXT, metier TEXT, contact TEXT, email TEXT, statut TEXT, date_maj TEXT, date_relance TEXT, nb_relances INTEGER,
    PRIMARY KEY (campagne_id, metier));
CREATE TABLE IF NOT EXISTS besoins (
    id INTEGER PRIMARY KEY AUTOINCREMENT, campagne_id TEXT, metier TEXT, client_id TEXT, projet TEXT, ressource TEXT,
    quantites TEXT, priorite TEXT, confiance TEXT, commentaire TEXT);
"""


# ------------------------------------------------------------------ connexion
def conn():
    c = sqlite3.connect(DB_PATH)
    c.execute("PRAGMA foreign_keys = OFF")
    return c


def init_db():
    with conn() as c:
        c.executescript(SCHEMA)
        cols = [r[1] for r in c.execute("PRAGMA table_info(affectations)")]
        if "ref" not in cols:
            c.execute("ALTER TABLE affectations ADD COLUMN ref TEXT")
        if "motif" not in cols:
            c.execute("ALTER TABLE affectations ADD COLUMN motif TEXT")
        cols_d = [r[1] for r in c.execute("PRAGMA table_info(devis)")]
        for col, typ in [("version", "INTEGER"), ("date_envoi", "TEXT"), ("ref_bc", "TEXT"), ("signataire", "TEXT"), ("motif_refus", "TEXT"), ("fin_mode", "TEXT"),
                         ("retour", "TEXT"), ("retour_date", "TEXT"), ("retour_note", "TEXT"), ("fichier", "TEXT")]:
            if col not in cols_d:
                c.execute(f"ALTER TABLE devis ADD COLUMN {col} {typ}")
        # version 2 : le devis est informatif (Brouillon / Envoyé) ; une décision « Accepté / Refusé » devient une note de suivi
        c.execute("UPDATE devis SET retour=statut, retour_date=COALESCE(retour_date, date_decision), "
                  "retour_note=COALESCE(retour_note, NULLIF(TRIM(COALESCE(motif_refus, '') || "
                  "CASE WHEN COALESCE(ref_bc, '') <> '' THEN ' BC ' || ref_bc ELSE '' END), '')), statut='Envoyé' "
                  "WHERE statut IN ('Accepté', 'Refusé')")
        cols_dl = [r[1] for r in c.execute("PRAGMA table_info(devis_lignes)")]
        if "remplace" not in cols_dl:
            c.execute("ALTER TABLE devis_lignes ADD COLUMN remplace TEXT")
        if "retraits" not in cols_dl:
            c.execute("ALTER TABLE devis_lignes ADD COLUMN retraits TEXT")
        c.execute("UPDATE devis SET version=1 WHERE version IS NULL")
        if "date_effet" not in [r[1] for r in c.execute("PRAGMA table_info(offres)")]:
            c.execute("ALTER TABLE offres ADD COLUMN date_effet TEXT")
        cols_a = [r[1] for r in c.execute("PRAGMA table_info(assets)")]
        for col, typ in ASSET_EXTRA:
            if col not in cols_a:
                c.execute(f"ALTER TABLE assets ADD COLUMN {col} {typ}")
        cols_e = [r[1] for r in c.execute("PRAGMA table_info(exercices)")]
        for col, typ in [("cle_regul", "TEXT"), ("regul_date", "TEXT"), ("regul", "REAL"), ("cout_service", "REAL"), ("consomme", "REAL"), ("budget_service", "REAL")]:
            if col not in cols_e:
                c.execute(f"ALTER TABLE exercices ADD COLUMN {col} {typ}")
        if c.execute("SELECT COUNT(*) FROM listes WHERE categorie='type'").fetchone()[0]:
            c.execute("INSERT OR IGNORE INTO listes VALUES ('type', 'Instance cloud')")
        # une base créée avant le choix « vide / démo » est considérée comme déjà initialisée
        init = c.execute("SELECT valeur FROM parametres WHERE cle='initialise'").fetchone()
        if not init:
            existe = (c.execute("SELECT COUNT(*) FROM assets").fetchone()[0] + c.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
                      + c.execute("SELECT COUNT(*) FROM exercices").fetchone()[0])
            if existe or c.execute("SELECT valeur FROM parametres WHERE cle='vide'").fetchone():
                c.execute("INSERT OR REPLACE INTO parametres VALUES ('initialise', 'existant')")
                c.commit()
            else:
                return  # premier lancement : l'application propose « base vide » ou « démonstration »
        if c.execute("SELECT COUNT(*) FROM exercices").fetchone()[0] == 0:
            a = c.execute("SELECT valeur FROM parametres WHERE cle='annee'").fetchone()
            m = c.execute("SELECT valeur FROM parametres WHERE cle='mois_ref'").fetchone()
            a = int(a[0]) if a else date.today().year
            c.execute("INSERT INTO exercices (annee, statut, mois_ref, date_ouverture) VALUES (?,?,?,?)",
                      (a, "Ouvert", int(m[0]) if m else date.today().month, date.today().isoformat()))
            c.execute("INSERT OR REPLACE INTO parametres VALUES ('annee', ?)", (str(a),))
            c.commit()


LISTES_DEFAUT = {
    "type": ["Serveur", "GPU", "CPU", "RAM", "Stockage", "Licence", "Service", "Réseau", "Instance cloud"],
    "entite": ["R&D", "Service Client", "Risques", "Marketing", "Finance", "Industrie", "RH", "Juridique", "IT Interne"],
    "pays": ["France", "Belgique", "Allemagne", "Espagne", "Italie", "Portugal", "Pays-Bas"],
}


def est_initialise():
    return param("initialise") is not None


def mode_donnees():
    """'demo', 'vide' ou 'existant'."""
    return param("initialise")


def _listes_defaut(c):
    for cat, vals in LISTES_DEFAUT.items():
        if not c.execute("SELECT COUNT(*) FROM listes WHERE categorie=?", (cat,)).fetchone()[0]:
            c.executemany("INSERT OR IGNORE INTO listes VALUES (?,?)", [(cat, v) for v in vals])


def demarrer_vide(an=None, mois=None):
    """Base vide : listes par défaut et un exercice ouvert ; aucun asset, client, offre ni affectation."""
    an = int(an or date.today().year)
    mois = int(mois or date.today().month)
    with conn() as c:
        _listes_defaut(c)
        c.execute("DELETE FROM exercices")
        c.execute("INSERT INTO exercices (annee, statut, mois_ref, date_ouverture) VALUES (?,?,?,?)", (an, "Ouvert", mois, date.today().isoformat()))
        for k, v in (("annee", an), ("mois_ref", mois), ("vide", 1), ("initialise", "vide")):
            c.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)", (k, str(v)))


def charger_demo():
    """Données de démonstration (exercice 2026, octobre) : assets, clients, offres, affectations, devis, budgets, mesures."""
    if not base_vide():
        raise ValueError("La base contient déjà des données : effacez-les d'abord (Paramètres › Données) pour charger la démonstration.")
    with conn() as c:
        c.execute("DELETE FROM exercices")
        _seed(c)
        _seed_devis(c)
        _seed_mesures(c)
        c.execute("INSERT INTO exercices (annee, statut, mois_ref, date_ouverture) VALUES (?,?,?,?)", (2026, "Ouvert", 10, date.today().isoformat()))
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('annee', '2026')")
        c.execute("DELETE FROM parametres WHERE cle='vide'")
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('initialise', 'demo')")
        c.commit()
        _seed_budgets(c, 2026)
        _seed_budget_service(c, 2026)
        c.commit()
    from ia_platform.core import planning  # campagne de collecte des besoins (exemple)
    planning.seed_demo()
    _seed_personnalisation()


def _seed_personnalisation():
    """Démonstration : stockage et licences retirables dans chaque offre ; Vision Qualité personnalise IA Standard en 2027."""
    comp = q("SELECT c.offre_id, c.asset_id, a.type FROM composition c JOIN assets a ON a.id=c.asset_id")
    with conn() as c:
        c.executemany("INSERT OR IGNORE INTO offre_retirables VALUES (?,?)",
                      [(r.offre_id, r.asset_id) for r in comp.itertuples() if r.type in ("Stockage", "Licence")])
    lig = q("SELECT id FROM affectations WHERE client_id='CL-006' AND code='OF-02' AND element='Offre' AND fin IS NULL")
    if len(lig):
        try:
            personnaliser_ligne(lig.id.iloc[0], {"A-006": 3, "A-007": 2}, date(annee() + 1, 1, 1))
        except ValueError:
            pass


def base_vide():
    return not (len(q("SELECT id FROM assets")) or len(q("SELECT id FROM clients")) or len(q("SELECT id FROM offres")))


def tout_effacer(an=None, mois=None):
    """Supprime toutes les données (sauvegarde faite avant) et repart d'une base vide ; les listes sont conservées."""
    cible = sauvegarde_fichier()
    _archiver_pdf_devis(cible)
    with conn() as c:
        for t in ("affectations", "devis", "devis_lignes", "devis_historique", "devis_versions", "conso_figee", "conso_type_figee", "ajustements",
                  "budgets", "exercices", "assets", "prix_hist", "offres", "composition", "composition_hist", "clients", "mesures",
                  "offre_retirables", "aff_retraits", "budget_cles", "reel_mensuel",
                  "campagnes", "campagne_metiers", "besoins"):
            c.execute(f"DELETE FROM {t}")
    demarrer_vide(an, mois)
    return cible


def q(sql, params=()):
    with conn() as c:
        return pd.read_sql_query(sql, c, params=params)


def run(sql, params=()):
    with conn() as c:
        c.execute(sql, params)


def runmany(sql, rows):
    with conn() as c:
        c.executemany(sql, rows)


# ------------------------------------------------------------------ paramètres et listes
def param(cle, defaut=None):
    df = q("SELECT valeur FROM parametres WHERE cle=?", (cle,))
    return df.valeur.iloc[0] if len(df) else defaut


def set_param(cle, valeur):
    run("INSERT OR REPLACE INTO parametres VALUES (?,?)", (cle, str(valeur)))


def annee():
    """Exercice sélectionné (affiché dans toute l'application)."""
    return int(param("annee", date.today().year))


def exercice(a=None):
    a = a or annee()
    df = q("SELECT * FROM exercices WHERE annee=?", (a,))
    return df.iloc[0] if len(df) else None


def est_cloture(a=None):
    e = exercice(a)
    return e is not None and e.statut == "Clôturé"


def mois_ref(a=None):
    e = exercice(a)
    if e is None:
        return int(param("mois_ref", 12))
    return 12 if e.statut == "Clôturé" else int(e.mois_ref or 1)


def set_mois_ref(m, a=None):
    run("UPDATE exercices SET mois_ref=? WHERE annee=?", (int(m), a or annee()))


def exercices_df():
    return q("SELECT * FROM exercices ORDER BY annee")


def verifier_ouvert(x, quoi="Cette opération"):
    """Refuse une écriture datée dans un exercice clôturé."""
    x = d(x)
    if x and est_cloture(x.year):
        raise ValueError(f"{quoi} tombe dans l'exercice {x.year}, qui est clôturé (données figées). Rouvrez l'exercice ou choisissez une date ultérieure.")


def liste(cat):
    return q("SELECT valeur FROM listes WHERE categorie=? ORDER BY rowid", (cat,)).valeur.tolist()


def ajouter_liste(cat, valeur):
    if valeur:
        run("INSERT OR IGNORE INTO listes VALUES (?,?)", (cat, valeur))


def remplacer_liste(cat, valeurs):
    with conn() as c:
        c.execute("DELETE FROM listes WHERE categorie=?", (cat,))
        c.executemany("INSERT OR IGNORE INTO listes VALUES (?,?)", [(cat, v) for v in valeurs if v])


# ------------------------------------------------------------------ outils
def d(s):
    """Texte ISO ou date -> date (ou None)."""
    if s is None or (isinstance(s, float) and pd.isna(s)) or s == "":
        return None
    if isinstance(s, date):
        return s
    return pd.to_datetime(s).date()


def iso(x):
    x = d(x)
    if isinstance(x, datetime):
        x = x.date()
    return x.isoformat() if x else None


def mois_debut(x):
    x = d(x)
    return date(x.year, x.month, 1)


def mois_precedent(x):
    x = mois_debut(x)
    return date(x.year - 1, 12, 1) if x.month == 1 else date(x.year, x.month - 1, 1)


def prochain_id(table, prefixe, chiffres):
    ids = q(f"SELECT id FROM {table}").id
    n = 0
    for i in ids:
        s = str(i)
        if s.startswith(prefixe) and s[len(prefixe):].isdigit():
            n = max(n, int(s[len(prefixe):]))
    return f"{prefixe}{n + 1:0{chiffres}d}"


def nombre(s):
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    return float(str(s).replace(" ", "").replace(" ", "").replace(",", ".") or 0)


def date_fr(s):
    s = str(s or "").strip()
    if not s:
        return None
    if "/" in s:
        j, m, a = s.split("/")
        return date(int(a), int(m), int(j))
    return d(s)


# ------------------------------------------------------------------ calculs
def assets_df():
    df = q("SELECT * FROM assets ORDER BY id")
    df["cout_mois"] = df.prix.fillna(0) * df.unite.map(FACTEURS).fillna(0)
    # une « part » (asset lié à une instance) n'ajoute pas de coût : le coût est porté par l'instance
    df["cout_parc"] = df.cout_mois * df.qte_parc.fillna(0) * df.parent_id.isna()
    return df


def couts_assets_mensuels(a=None):
    """DataFrame index = id asset, colonnes 1..12 : coût mensuel d'une unité, prix valable chaque mois."""
    a = a or annee()
    assets = assets_df()
    hist = q("SELECT * FROM prix_hist")
    hist["cout"] = hist.prix * hist.unite.map(FACTEURS).fillna(0)
    out = {}
    for _, r in assets.iterrows():
        eff = d(r.date_effet)
        vals = []
        for m in range(1, 13):
            dm = date(a, m, 1)
            v = r.cout_mois
            if eff and dm < eff:
                h = hist[(hist.asset_id == r.id) & (hist.du.apply(d) <= dm) & (hist.au.apply(d) >= dm)]
                if len(h):
                    v = h.cout.iloc[-1]
            vals.append(v)
        out[r.id] = vals
    return pd.DataFrame.from_dict(out, orient="index", columns=range(1, 13))


def compositions_mensuelles(a=None):
    """{mois: DataFrame(offre_id, asset_id, qte)} : la composition valable chaque mois (date d'effet + historique)."""
    a = a or annee()
    cur = q("SELECT c.offre_id, c.asset_id, c.qte, o.date_effet FROM composition c JOIN offres o ON o.id=c.offre_id")
    hist = q("SELECT * FROM composition_hist")
    eff = q("SELECT id, date_effet FROM offres")
    eff = {i: d(x) for i, x in zip(eff.id, eff.date_effet)}
    hist["du_"] = hist.du.map(d)
    hist["au_"] = hist.au.map(d)
    res = {}
    for m in range(1, 13):
        dm = date(a, m, 1)
        pas_encore = {o for o, e in eff.items() if e and e > dm}
        c1 = cur[~cur.offre_id.isin(pas_encore)][["offre_id", "asset_id", "qte"]]
        ok = pd.Series([(x is None or x <= dm) and (y is None or y >= dm) for x, y in zip(hist.du_, hist.au_)], index=hist.index, dtype=bool)
        h = hist[hist.offre_id.isin(pas_encore) & ok]
        res[m] = pd.concat([c1, h[["offre_id", "asset_id", "qte"]]], ignore_index=True) if len(h) else c1.reset_index(drop=True)
    return res


def composition_au(offre_id, quand):
    """Composition d'une offre valable au mois donné."""
    quand = mois_debut(quand)
    o = q("SELECT date_effet FROM offres WHERE id=?", (offre_id,))
    e = d(o.date_effet.iloc[0]) if len(o) else None
    if e is None or e <= quand:
        return q("SELECT asset_id, qte FROM composition WHERE offre_id=?", (offre_id,))
    h = q("SELECT * FROM composition_hist WHERE offre_id=?", (offre_id,))
    return h[[(d(x) is None or d(x) <= quand) and (d(y) is None or d(y) >= quand) for x, y in zip(h.du, h.au)]][["asset_id", "qte"]]


# ------------------------------------------------------------------ personnalisation des offres
def retirables(offre_id):
    """Assets d'une offre que le client peut retirer (les autres forment le socle)."""
    return set(q("SELECT asset_id FROM offre_retirables WHERE offre_id=?", (offre_id,)).asset_id)


def retraits_lignes():
    """{aff_id: {asset_id: quantité retirée par exemplaire}} pour toutes les lignes personnalisées."""
    out = {}
    for r in q("SELECT * FROM aff_retraits WHERE qte > 0").itertuples():
        out.setdefault(r.aff_id, {})[r.asset_id] = float(r.qte)
    return out


def retraits_ligne(aff_id):
    return retraits_lignes().get(aff_id, {})


def _json_retraits(x):
    import json
    if isinstance(x, dict):
        return {k: float(v) for k, v in x.items() if float(v or 0) > 0}
    if isinstance(x, str) and x.strip():
        return {k: float(v) for k, v in json.loads(x).items() if float(v or 0) > 0}
    return {}


def comp_effective(comp, retraits):
    """Composition (asset_id, qte) après retraits d'un exemplaire ; un retrait ne dépasse jamais la quantité de l'offre."""
    if not retraits or comp is None or comp.empty:
        return comp
    c_ = comp.copy()
    c_["qte"] = [max(0.0, float(x) - min(float(retraits.get(a_, 0)), float(x))) for a_, x in zip(c_.asset_id, c_.qte)]
    return c_


def _moins_retraits(comp, retraits, couts):
    """Coût mensuel retiré pour un exemplaire : composition du mois, coût unitaire des assets du mois (Series)."""
    if not retraits or comp is None or comp.empty:
        return 0.0
    return float(sum(min(float(retraits.get(a_, 0)), float(x)) * float(couts.get(a_, 0.0)) for a_, x in zip(comp.asset_id, comp.qte)))


def cout_retraits(code, retraits, quand):
    """Baisse du coût mensuel d'un exemplaire d'offre personnalisée (grille du mois, ou du mois de référence hors exercice)."""
    if not retraits:
        return 0.0
    a = annee()
    quand = mois_debut(quand)
    m = quand.month if quand.year == a else mois_ref()
    cam = couts_assets_mensuels(a)
    return _moins_retraits(composition_au(code, quand), retraits, cam[m])


def texte_retraits(retraits, noms=None):
    if not retraits:
        return ""
    noms = noms if noms is not None else q("SELECT id, nom FROM assets").set_index("id").nom
    return ", ".join(f"− {v:g} × {noms.get(k, k)}" for k, v in retraits.items() if v)


def verifier_retraits(code, retraits, quand):
    """Un retrait ne porte que sur un composant retirable, sans dépasser sa quantité dans l'offre."""
    comp = composition_au(code, quand).set_index("asset_id").qte
    ok = retirables(code)
    noms = q("SELECT id, nom FROM assets").set_index("id").nom
    for a_, v in retraits.items():
        if v <= 0:
            continue
        if a_ not in ok:
            raise ValueError(f"{noms.get(a_, a_)} fait partie du socle de l'offre : il ne peut pas être retiré.")
        if a_ not in comp.index:
            raise ValueError(f"{noms.get(a_, a_)} n'est pas dans la composition de l'offre en {mois_txt_court(quand)}.")
        if v > float(comp[a_]) + 1e-9:
            raise ValueError(f"On ne peut pas retirer {v:g} × {noms.get(a_, a_)} : l'offre en contient {float(comp[a_]):g}.")


def personnaliser_ligne(aff_id, retraits, depuis):
    """Personnalise une ligne d'offre à partir d'un mois. Si la ligne a commencé avant, elle est arrêtée le mois précédent
    et une nouvelle ligne identique (même offre, quantité, fin, référence) porte les retraits : le passé ne change pas.
    retraits vide = retour à l'offre standard. Renvoie l'ID de la ligne qui porte la personnalisation."""
    r = _ligne(aff_id)
    if r.element != "Offre":
        raise ValueError("Seule une ligne d'offre se personnalise.")
    depuis = mois_debut(depuis)
    verifier_ouvert(depuis, "Cette personnalisation")
    deb, fin = mois_debut(r.debut), (mois_debut(r.fin) if r.fin else None)
    if fin and fin < depuis:
        raise ValueError(f"La ligne se termine en {mois_txt_court(fin)}, avant {mois_txt_court(depuis)}.")
    retraits = {k: float(v) for k, v in (retraits or {}).items() if float(v or 0) > 0}
    verifier_retraits(r.code, retraits, max(depuis, deb))
    if retraits == retraits_ligne(aff_id):
        return aff_id
    with conn() as c:
        cible = aff_id
        if deb < depuis:
            c.execute("UPDATE affectations SET fin=?, motif=? WHERE id=?", (iso(mois_precedent(depuis)), f"Personnalisation à partir de {mois_txt_court(depuis)}", aff_id))
            cible = _inserer_ligne(c, r.client_id, r.operation, "Offre", r.code, r.qte, depuis, fin, ref=r.ref,
                                   motif="Offre personnalisée" if retraits else "Retour à l'offre standard")
        c.execute("DELETE FROM aff_retraits WHERE aff_id=?", (cible,))
        c.executemany("INSERT INTO aff_retraits (aff_id, asset_id, qte) VALUES (?,?,?)", [(cible, k, v) for k, v in retraits.items()])
    return cible


def couts_offres_mensuels(cam=None, a=None):
    cam = cam if cam is not None else couts_assets_mensuels(a)
    cm = compositions_mensuelles(a)
    offres = q("SELECT id FROM offres").id
    res = pd.DataFrame(0.0, index=offres, columns=range(1, 13))
    for m in range(1, 13):
        comp = cm[m]
        if comp.empty:
            continue
        v = comp.asset_id.map(cam[m]).fillna(0) * comp.qte
        g = v.groupby(comp.offre_id).sum()
        res.loc[g.index.intersection(res.index), m] = g[g.index.intersection(res.index)]
    return res


def _lignes_figees(a):
    f = q("SELECT * FROM conso_figee WHERE annee=? ORDER BY aff_id", (a,))
    f = f.rename(columns={f"m{k}": k for k in range(1, 13)}).rename(columns={"aff_id": "id"})
    f["ref"] = None
    fin_annee = date(a, 12, 1)
    f["statut"] = [("Planifiée" if d(x) and d(x) > fin_annee else "Terminée" if d(y) and d(y) < fin_annee else "Active")
                   for x, y in zip(f.debut, f.fin)]
    f["total"] = f[list(range(1, 13))].sum(axis=1) if len(f) else []
    f["cout_ref"] = f[12] if len(f) else []
    return f


def _lignes_ajustements(a, base_cols):
    aj = q("SELECT a.*, c.nom AS client, c.entite, c.pays FROM ajustements a LEFT JOIN clients c ON c.id=a.client_id WHERE a.annee=?", (a,))
    rows = []
    for r in aj.itertuples():
        row = dict(id=f"AJ-{r.id}", client_id=r.client_id, client=r.client, entite=r.entite, pays=r.pays, operation="Ajustement",
                   element="Ajustement", code="", libelle=r.libelle, type="Ajustement", qte=1.0,
                   debut=date(a, int(r.mois), 1).isoformat(), fin=date(a, int(r.mois), 1).isoformat(), ref=r.nature, statut="Active")
        for k in range(1, 13):
            row[k] = float(r.montant) if k == int(r.mois) else 0.0
        rows.append(row)
    return pd.DataFrame(rows, columns=base_cols) if rows else None


def lignes_mensuelles(a=None):
    """Une ligne par affectation (ou ajustement), avec le montant de chaque mois (colonnes 1..12)."""
    a = a or annee()
    if est_cloture(a):
        return _lignes_figees(a)
    cam = couts_assets_mensuels(a)
    com = couts_offres_mensuels(cam, a)
    aff = q("SELECT * FROM affectations ORDER BY id")
    cli = q("SELECT id AS client_id, nom AS client, entite, pays FROM clients")
    offres = q("SELECT id AS code, nom AS libelle_offre FROM offres")
    assets = q("SELECT id AS code, nom AS libelle_asset, type AS type_asset FROM assets")
    aff = aff.merge(cli, on="client_id", how="left").merge(offres, on="code", how="left").merge(assets, on="code", how="left")
    aff["libelle"] = aff.libelle_offre.where(aff.element == "Offre", aff.libelle_asset)
    aff["type"] = aff.type_asset.where(aff.element == "Option", "Offre")
    ref = date(a, mois_ref(a), 1)

    def statut(r):
        deb, fin = d(r.debut), d(r.fin)
        if deb and deb > ref:
            return "Planifiée"
        if fin and fin < ref:
            return "Terminée"
        return "Active"

    aff["statut"] = aff.apply(statut, axis=1) if len(aff) else []
    rl = retraits_lignes()
    cm = compositions_mensuelles(a) if rl else None
    aff["retraits"] = [rl.get(i, {}) for i in aff.id] if len(aff) else []
    for m in range(1, 13):
        dm = date(a, m, 1)
        vals = []
        for _, r in aff.iterrows():
            deb, fin = d(r.debut), d(r.fin)
            actif = deb is not None and deb <= dm and (fin is None or fin >= dm)
            if not actif:
                vals.append(0.0)
                continue
            src = com if r.element == "Offre" else cam
            unit = src.loc[r.code, m] if r.code in src.index else 0.0
            if r.element == "Offre" and r.id in rl:
                unit -= _moins_retraits(cm[m][cm[m].offre_id == r.code], rl[r.id], cam[m])
            vals.append(float(r.qte or 0) * unit)
        aff[m] = vals
    extra = _lignes_ajustements(a, list(aff.columns))
    if extra is not None:
        aff = pd.concat([aff, extra], ignore_index=True) if len(aff) else extra
    aff["total"] = aff[list(range(1, 13))].sum(axis=1) if len(aff) else []
    aff["cout_ref"] = aff[mois_ref(a)] if len(aff) else []
    return aff


def conso_clients(lignes=None):
    """Consommation par client et par mois (tous les clients)."""
    lignes = lignes if lignes is not None else lignes_mensuelles()
    cli = q("SELECT id AS client_id, nom AS client, entite, pays, statut FROM clients")
    if len(lignes):
        g = lignes.groupby("client_id")[list(range(1, 13))].sum()
    else:
        g = pd.DataFrame(index=pd.Index([], name="client_id"), columns=list(range(1, 13)), dtype=float)
    if len(lignes) and est_cloture():
        snap = lignes.drop_duplicates("client_id").set_index("client_id")[["client", "entite", "pays"]]
        manquants = snap.loc[~snap.index.isin(cli.client_id)].reset_index().assign(statut="Supprimé")
        cli = pd.concat([cli, manquants], ignore_index=True)
        for col in ("client", "entite", "pays"):
            cli[col] = cli.client_id.map(snap[col]).fillna(cli[col])
    df = cli.merge(g, left_on="client_id", right_index=True, how="left").fillna({m: 0.0 for m in range(1, 13)})
    df[list(range(1, 13))] = df[list(range(1, 13))].astype(float)
    df["total"] = df[list(range(1, 13))].sum(axis=1)
    df["reel"] = df[list(range(1, mois_ref() + 1))].sum(axis=1)
    df["mois_ref"] = df[mois_ref()]
    return df


def conso_par_type(lignes=None, clients=None):
    """Consommation par type d'asset et par mois, en éclatant les offres selon leur composition."""
    a = annee()
    types = liste("type")
    if est_cloture(a):
        f = q("SELECT * FROM conso_type_figee WHERE annee=?", (a,))
        if clients is not None:
            f = f[f.client_id.isin(clients)]
        g = f.groupby("type")[[f"m{k}" for k in range(1, 13)]].sum().rename(columns={f"m{k}": k for k in range(1, 13)})
        idx = types + [t for t in g.index if t not in types]
        return g.reindex(idx).fillna(0.0)
    lignes = lignes if lignes is not None else lignes_mensuelles()
    if clients is not None:
        lignes = lignes[lignes.client_id.isin(clients)]
    cam = couts_assets_mensuels(a)
    typ = q("SELECT id, type FROM assets").set_index("id").type
    cm = {m: c_.assign(type=c_.asset_id.map(typ)) for m, c_ in compositions_mensuelles(a).items()}
    res = pd.DataFrame(0.0, index=types, columns=range(1, 13))
    for _, r in lignes.iterrows():
        for m in range(1, 13):
            if r[m] == 0:
                continue
            if r.element == "Ajustement":
                continue
            if r.element == "Option":
                if r.type in res.index:
                    res.loc[r.type, m] += r[m]
            else:
                comp = cm[m]
                rt = r["retraits"] if "retraits" in r and isinstance(r["retraits"], dict) else {}
                for _, c in comp[comp.offre_id == r.code].iterrows():
                    if c.type in res.index and c.asset_id in cam.index:
                        qx = float(c.qte) - min(float(rt.get(c.asset_id, 0)), float(c.qte))
                        res.loc[c.type, m] += float(r.qte or 0) * qx * cam.loc[c.asset_id, m]
    return res


def conso_assets(a=None, lignes=None):
    """Détail client × asset × mois : montant et unités (offres éclatées selon leur composition du mois).
    Indisponible pour un exercice clôturé (seuls les montants par type sont figés)."""
    a = a or annee()
    cols = ["client_id", "client", "entite", "pays", "asset_id", "nom", "type", "m", "unites", "montant"]
    if est_cloture(a):
        return pd.DataFrame(columns=cols)
    lignes = lignes if lignes is not None else lignes_mensuelles(a)
    cam = couts_assets_mensuels(a)
    cm = compositions_mensuelles(a)
    ast = q("SELECT id, nom, type FROM assets").set_index("id")
    rows = []
    for _, r in lignes[lignes.element.isin(["Offre", "Option"])].iterrows():
        base = (r.client_id, r.client, r.entite, r.pays)
        for m in range(1, 13):
            if not r[m]:
                continue
            if r.element == "Option":
                rows.append(base + (r.code, m, float(r.qte or 0), float(r[m])))
            else:
                c = cm[m]
                rt = r["retraits"] if "retraits" in r and isinstance(r["retraits"], dict) else {}
                for x in c[c.offre_id == r.code].itertuples():
                    u = float(r.qte or 0) * (float(x.qte) - min(float(rt.get(x.asset_id, 0)), float(x.qte)))
                    if u <= 0:
                        continue
                    rows.append(base + (x.asset_id, m, u, u * float(cam.loc[x.asset_id, m]) if x.asset_id in cam.index else 0.0))
    df = pd.DataFrame(rows, columns=["client_id", "client", "entite", "pays", "asset_id", "m", "unites", "montant"])
    df["nom"] = df.asset_id.map(ast.nom)
    df["type"] = df.asset_id.map(ast.type)
    return df[cols]


def occupation_parc(m=None, a=None, detail=None):
    """Par asset : unités affectées au mois m (offres + options, tous clients) / unités du parc, coûts associés."""
    a = a or annee()
    m = m or mois_ref(a)
    detail = detail if detail is not None else conso_assets(a)
    ast = assets_df().set_index("id")
    cam = couts_assets_mensuels(a)
    u = detail[detail.m == m].groupby("asset_id").unites.sum() if len(detail) else pd.Series(dtype=float)
    df = pd.DataFrame({"nom": ast.nom, "type": ast.type, "statut": ast.statut, "parc": ast.qte_parc.fillna(0), "parent_id": ast.parent_id})
    df["utilises"] = u.reindex(df.index).fillna(0)
    df["cout_unit"] = cam[m].reindex(df.index).fillna(0)
    df["refacture"] = df.utilises * df.cout_unit
    df["cout_parc"] = df.parc * df.cout_unit * (df.statut == "Actif")
    # une part vendue occupe une fraction de son instance : on la ramène sur l'instance
    for cid, par in zip(ast.index, ast.parent_id):
        if isinstance(par, str) and par in df.index:
            n = n_parts(ast.loc[par])
            if n:
                df.loc[par, "utilises"] += df.loc[cid, "utilises"] / n
                df.loc[par, "refacture"] += df.loc[cid, "refacture"]
            df = df.drop(index=cid)
    df["inutilise"] = (df.cout_parc - df.refacture).clip(lower=0)
    df["occupation"] = [x / p if p else None for x, p in zip(df.utilises, df.parc)]
    return df


# ------------------------------------------------------------------ instances cloud, parts et capacité
import re as _re


def lire_flavor(nom):
    """Lit les capacités dans un nom de profil IBM Cloud VPC : bx3d-128x640, gx3-24x120x1l40s, cx2-16x32…"""
    s_ = str(nom or "").lower().replace("ibm", "").strip()
    m = _re.search(r"([a-z]+\d+[a-z]*)[-.](\d+)x(\d+)(?:x(\d+)([a-z]\d+[a-z]*))?", s_)
    if not m:
        return {}
    fam = m.group(1)
    out = dict(famille=fam, vcpu=float(m.group(2)), ram_go=float(m.group(3)))
    if m.group(4):
        out["gpu"] = float(m.group(4))
        out["gpu_modele"] = m.group(5).upper()
    else:
        out["gpu"] = 0.0
    out["stockage_local"] = fam.endswith("d")
    out["profil"] = f"{fam}-{m.group(2)}x{m.group(3)}" + (f"x{m.group(4)}{m.group(5)}" if m.group(4) else "")
    return out


def enregistrer_asset(a, synchro=True):
    """Crée ou met à jour un asset (toutes colonnes) ; les colonnes absentes du dict sont conservées."""
    a = {k: (None if (isinstance(v, float) and pd.isna(v)) or v == "" else v) for k, v in a.items()}
    cols = [c for c in ASSET_COLS if c in a]
    maj = ", ".join(f"{c}=excluded.{c}" for c in cols if c != "id")
    run(f"INSERT INTO assets ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))}) ON CONFLICT(id) DO UPDATE SET {maj}",
        tuple(a[c] for c in cols))
    if synchro:
        synchroniser_parts()


def n_parts(r):
    if r.get("refacturation") == "part_vcpu":
        return float(r.get("vcpu") or 0)
    if r.get("refacturation") == "part_gpu":
        return float(r.get("gpu") or 0)
    return 0.0


def synchroniser_parts():
    """Pour chaque instance vendue « à la part », crée ou met à jour l'asset part lié (prix = instance ÷ parts, parc = parts × instances)."""
    assets = assets_df()
    par_parent = {p: i for i, p in zip(assets.id, assets.parent_id) if isinstance(p, str)}
    for _, r in assets[assets.parent_id.isna()].iterrows():
        n = n_parts(r)
        enfant = par_parent.get(r.id)
        if r.refacturation not in ("part_vcpu", "part_gpu") or n <= 0:
            if enfant:  # le parent n'est plus vendu à la part : la part est retirée
                run("UPDATE assets SET statut='Retiré', qte_parc=0 WHERE id=?", (enfant,))
            continue
        unite_part = "vCPU" if r.refacturation == "part_vcpu" else (r.gpu_modele or "GPU")
        prix = round(float(r.cout_mois) / n, 4)
        info = lire_flavor(r.nom)
        nom = f"{unite_part} {info.get('profil', r.nom)} (part)" if unite_part == "vCPU" else f"GPU {unite_part} {info.get('profil', r.nom)} (part)"
        champs = dict(type=r.type, nom=nom, fournisseur=r.fournisseur, qte_parc=float(r.qte_parc or 0) * n, statut=r.statut, region=r.region,
                      vcpu=float(r.vcpu or 0) / n if r.vcpu else None, ram_go=float(r.ram_go or 0) / n if r.ram_go else None,
                      gpu=1.0 if r.refacturation == "part_gpu" else (float(r.gpu or 0) / n if r.gpu else None), gpu_modele=r.gpu_modele,
                      refacturation=None, parent_id=r.id)
        if not enfant:
            enfant = prochain_id("assets", "A-", 3)
            enregistrer_asset(dict(id=enfant, prix=prix, unite="Mois", date_effet=r.date_effet, **champs), synchro=False)
            continue
        e = assets.set_index("id").loc[enfant]
        enregistrer_asset(dict(id=enfant, **champs), synchro=False)
        if abs(float(e.prix or 0) - prix) > 1e-6 or e.unite != "Mois":
            de, pe = d(e.date_effet), d(r.date_effet)
            if de and pe and pe > de:
                run("INSERT INTO prix_hist (asset_id, prix, unite, du, au, motif) VALUES (?,?,?,?,?,?)",
                    (enfant, e.prix, e.unite, iso(de), iso(pe - timedelta(days=1)), f"Suit le prix de {r.id}"))
            run("UPDATE assets SET prix=?, unite='Mois', date_effet=? WHERE id=?", (prix, r.date_effet, enfant))


def capacite_geree(asset_id):
    """Assets dont la capacité est contrôlée : parts d'instance et instances cloud vendues entières."""
    a = q("SELECT parent_id, refacturation, qte_parc FROM assets WHERE id=?", (asset_id,))
    if a.empty:
        return None
    a = a.iloc[0]
    if isinstance(a.parent_id, str) or a.refacturation == "entiere":
        return float(a.qte_parc or 0)
    return None


def _comp_cache():
    cache = {}

    def comp(oid, quand):
        k = (oid, quand)
        if k not in cache:
            cache[k] = composition_au(oid, quand)
        return cache[k]
    return comp


def allocations(asset_id, quand, exclure=()):
    """Unités d'un asset allouées au mois donné, par ligne d'affectation (options + offres éclatées)."""
    quand = mois_debut(quand)
    aff = q("SELECT a.*, c.nom AS client FROM affectations a LEFT JOIN clients c ON c.id=a.client_id")
    comp = _comp_cache()
    rl = retraits_lignes()
    rows = []
    for r in aff.itertuples():
        if r.id in exclure:
            continue
        deb, fin = d(r.debut), d(r.fin)
        if not deb or deb > quand or (fin and fin < quand):
            continue
        if r.element == "Option" and r.code == asset_id:
            u = float(r.qte or 0)
        elif r.element == "Offre":
            c = comp_effective(comp(r.code, quand), rl.get(r.id))
            u = float(c[c.asset_id == asset_id].qte.sum()) * float(r.qte or 0)
        else:
            continue
        if u > 0:
            rows.append(dict(aff_id=r.id, client_id=r.client_id, client=r.client, unites=u, debut=deb))
    return pd.DataFrame(rows, columns=["aff_id", "client_id", "client", "unites", "debut"])


def reserves_devis(asset_id, quand):
    """Les devis sont informatifs : ils ne réservent plus de capacité (fonction gardée pour compatibilité)."""
    return pd.DataFrame(columns=["devis_id", "client", "unites"])


def verifier_capacite(nouvelles, exclure=()):
    """nouvelles : liste de dict(element, code, qte, debut, fin). Refuse si un asset à capacité contrôlée dépasse son parc."""
    besoins = {}
    for n in nouvelles:
        deb = mois_debut(n["debut"])
        fin = mois_debut(n["fin"]) if n.get("fin") else ajouter_mois(deb, 23)
        fin = min(fin, ajouter_mois(deb, 23))
        m = deb
        while m <= fin:
            if n["element"] == "Option":
                besoins[(n["code"], m)] = besoins.get((n["code"], m), 0) + float(n["qte"])
            else:
                c = comp_effective(composition_au(n["code"], m), n.get("retraits"))
                for x in c.itertuples():
                    besoins[(x.asset_id, m)] = besoins.get((x.asset_id, m), 0) + float(x.qte) * float(n["qte"])
            m = ajouter_mois(m, 1)
    for (aid, m), u in sorted(besoins.items(), key=lambda x: x[0][1]):
        cap = capacite_geree(aid)
        if cap is None:
            continue
        deja = float(allocations(aid, m, exclure).unites.sum())
        if deja + u > cap + 1e-9:
            nom = q("SELECT nom FROM assets WHERE id=?", (aid,)).nom.iloc[0]
            raise ValueError(f"Parc plein pour {nom} en {MOIS[m.month - 1].lower()} {m.year} : {deja:g} déjà alloués + {u:g} demandés "
                             f"> {cap:g} disponibles. Ajoutez une instance dans Assets (quantité du parc) ou réduisez la quantité.")


def placement(asset_id, quand=None):
    """Répartit les allocations d'une part sur les instances du parent (premier emplacement libre, par date de début)."""
    quand = mois_debut(quand or date(annee(), mois_ref(), 1))
    a = q("SELECT * FROM assets WHERE id=?", (asset_id,)).iloc[0]
    if not isinstance(a.parent_id, str):
        return []
    p = q("SELECT * FROM assets WHERE id=?", (a.parent_id,)).iloc[0]
    taille = n_parts(p)
    n_inst = int(p.qte_parc or 0)
    inst = [dict(num=i + 1, taille=taille, libre=taille, parts=[]) for i in range(n_inst)]
    al = allocations(asset_id, quand).sort_values(["debut", "aff_id"])
    for r in al.itertuples():
        reste = r.unites
        cible = next((i for i in inst if i["libre"] >= reste), None)
        cibles = [cible] if cible else [i for i in inst if i["libre"] > 0]
        for i in cibles:
            pris = min(i["libre"], reste)
            if pris <= 0:
                continue
            i["parts"].append(dict(client=r.client, client_id=r.client_id, unites=pris, partage=cible is None))
            i["libre"] -= pris
            reste -= pris
            if reste <= 0:
                break
    return inst


def utilisation_mesuree(asset_id, jours=30):
    """Utilisation moyenne mesurée par la supervision (sur les derniers jours importés), par client et globale."""
    me = q("SELECT * FROM mesures WHERE asset_id IN (?, (SELECT parent_id FROM assets WHERE id=?))", (asset_id, asset_id))
    if me.empty:
        return None, {}
    me["d"] = pd.to_datetime(me.date)
    me = me[me.d > me.d.max() - pd.Timedelta(days=jours)]
    typ = q("SELECT a.type, a.gpu, a.refacturation, p.refacturation AS refac_parent FROM assets a LEFT JOIN assets p ON p.id=a.parent_id WHERE a.id=?",
            (asset_id,)).iloc[0]
    gpu = typ.type == "GPU" or typ.refac_parent == "part_gpu" or (typ.refacturation == "entiere" and (typ.gpu or 0) > 0)
    col = "gpu_moy" if gpu and me.gpu_moy.notna().any() else "cpu_moy"
    par_client = me.groupby("client_id")[col].mean().to_dict()
    return float(me[col].mean()), par_client


def unites_par_mois(asset_id, mois, aff=None, devis_lignes_env=None, comp=None):
    """{mois: (alloué, réservé)} pour une liste de premiers du mois (lecture unique des tables)."""
    comp = comp or _comp_cache()
    aff = aff if aff is not None else q("SELECT * FROM affectations")
    env = devis_lignes_env if devis_lignes_env is not None else _devis_envoyes()
    rl = retraits_lignes()
    res = {}
    for m in mois:
        al = 0.0
        for r in aff.itertuples():
            deb, fin = d(r.debut), d(r.fin)
            if not deb or deb > m or (fin and fin < m):
                continue
            if r.element == "Option" and r.code == asset_id:
                al += float(r.qte or 0)
            elif r.element == "Offre":
                c = comp_effective(comp(r.code, m), rl.get(r.id))
                al += float(c[c.asset_id == asset_id].qte.sum()) * float(r.qte or 0)
        rs = 0.0
        for r in env:
            if r["debut"] <= m <= r["fin"]:
                if r["element"] == "Option" and r["code"] == asset_id:
                    rs += r["qte"]
                elif r["element"] == "Offre":
                    c = comp(r["code"], r["debut"])
                    rs += float(c[c.asset_id == asset_id].qte.sum()) * r["qte"]
        res[m] = (al, rs)
    return res


def _devis_envoyes():
    """Les devis sont informatifs : aucune ligne de devis n'est comptée comme réservée dans la capacité."""
    return []


def seuils_capacite():
    return dict(sature=float(param("seuil_sature", 90)), sous=float(param("seuil_sous", 20)), inactif=float(param("seuil_inactif", 5)),
                alerte=float(param("seuil_alerte_parc", 90)))


def pools_capacite(horizon=12):
    """Un « pool » par ressource dont on suit la capacité : parts d'instance, instances cloud entières, GPU du parc."""
    a_ = annee()
    ref = date(a_, mois_ref(a_), 1)
    mois = [ajouter_mois(ref, i) for i in range(horizon)]
    assets = assets_df()
    ai = assets.set_index("id")
    aff = q("SELECT * FROM affectations")
    env = _devis_envoyes()
    comp = _comp_cache()
    s_ = seuils_capacite()
    pools = []
    for r in assets[(assets.statut == "Actif")].itertuples():
        parent = ai.loc[r.parent_id] if isinstance(r.parent_id, str) and r.parent_id in ai.index else None
        if parent is not None:
            unite = "vCPU" if parent.refacturation == "part_vcpu" else "GPU"
            label = f"{unite} · {parent.nom}"
            detail = f"{parent.qte_parc:g} instance{'s' if parent.qte_parc > 1 else ''} · {parent.region or parent.fournisseur or ''}"
            taille, cout_inst = n_parts(parent), float(parent.cout_mois)
            vcpu_u, gpu_u = (1.0, 0.0) if unite == "vCPU" else (float(parent.vcpu or 0) / max(n_parts(parent), 1), 1.0)
            kind = "part"
        elif r.refacturation == "entiere":
            unite, label = "instances", f"Instances · {r.nom}"
            detail = f"vendue entière · {r.region or r.fournisseur or ''}"
            taille, cout_inst = 1.0, float(r.cout_mois)
            vcpu_u, gpu_u = float(r.vcpu or 0), float(r.gpu or 0)
            kind = "entiere"
        elif r.type == "GPU" and (r.qte_parc or 0) > 0:
            unite, label, detail = "GPU", r.nom, f"{r.fournisseur or ''} · on-premise"
            taille, cout_inst, vcpu_u, gpu_u, kind = 1.0, float(r.cout_mois), 0.0, 1.0, "gpu"
        else:
            continue
        cap = float(r.qte_parc or 0)
        if cap <= 0:
            continue
        um = unites_par_mois(r.id, mois, aff, env, comp)
        al = um[ref][0]
        rs = max(y for _, y in um.values())  # toujours 0 : les devis ne réservent plus de capacité
        sat = None
        for m in mois:
            x, y = um[m]
            if x + y >= cap - 1e-9 and m > ref:
                sat = m
                break
        util, par_cli = utilisation_mesuree(r.id)
        occ = (al + rs) / cap
        if al >= cap - 1e-9:
            etat = "Plein"
        elif al == 0 and rs == 0:
            etat = "Inutilisé"
        elif occ * 100 >= s_["alerte"] or (sat and sat <= ajouter_mois(ref, 6)):
            etat = "Bientôt plein"
        elif util is not None and util < s_["sous"]:
            etat = "Sur-dimensionné"
        else:
            etat = "OK"
        pools.append(dict(id=r.id, kind=kind, label=label, detail=detail, unite=unite, capacite=cap, alloue=al, reserve=rs,
                          libre=max(cap - al - rs, 0), occupation=occ, utilisation=util, par_client=par_cli, etat=etat,
                          saturation=("déjà plein" if al >= cap - 1e-9 else mois_txt_court(sat) if sat else f"> {horizon} mois"),
                          projection=um, taille=taille, cout_instance=cout_inst, vcpu_unite=vcpu_u, gpu_unite=gpu_u, saturation_date=sat,
                          parent_id=r.parent_id if isinstance(r.parent_id, str) else None))
    return pools


def mois_txt_court(x):
    x = d(x)
    return f"{MOIS[x.month - 1].lower()} {x.year}" if x else "—"


def _eu(v):
    return f"{v:,.0f}".replace(",", " ") + " €"


def recommandations(pools):
    rec = []
    for p in pools:
        unite_achat = "instance" if p["kind"] in ("part", "entiere") else "unité"
        if p["etat"] == "Plein":
            rec.append(("Acheter", f"<b>{p['label']}</b> : {p['alloue']:g} / {p['capacite']:g} {p['unite']} alloués"
                        + (f", {p['reserve']:g} demandés par des devis en attente" if p["reserve"] else "")
                        + f". Ajouter 1 {unite_achat} (+{_eu(p['cout_instance'])} / mois)."))
        elif p["etat"] == "Bientôt plein":
            fin_txt = (f"saturation prévue en {p['saturation']}" if not p["saturation"].startswith(">")
                       else f"plus que {p['capacite'] - p['alloue'] - p['reserve']:g} {p['unite']} libres")
            rec.append(("Anticiper", f"<b>{p['label']}</b> : {p['alloue'] + p['reserve']:g} / {p['capacite']:g} avec les lignes à venir ; {fin_txt}."))
        elif p["etat"] == "Inutilisé":
            rec.append(("Revoir", f"<b>{p['label']}</b> : rien d'alloué, {_eu(p['capacite'] / p['taille'] * p['cout_instance'])} / mois sans refacturation."))
        elif p["etat"] == "Sur-dimensionné":
            rec.append(("Réduire", f"<b>{p['label']}</b> : {p['occupation'] * 100:.0f} % alloué et {p['utilisation']:.0f} % utilisé en moyenne."))
        libres = int((p["capacite"] - p["alloue"] - p["reserve"]) // p["taille"]) if p["taille"] else 0
        if p["kind"] in ("part", "entiere") and libres >= 1 and p["etat"] not in ("Inutilisé",):
            rec.append(("Réduire", f"<b>{p['label']}</b> : {libres} instance{'s' if libres > 1 else ''} entièrement libre{'s' if libres > 1 else ''} — "
                        f"la rendre économiserait {_eu(libres * p['cout_instance'])} / mois."))
    ordre = {"Acheter": 0, "Anticiper": 1, "Réduire": 2, "Revoir": 3}
    return sorted(rec, key=lambda x: ordre[x[0]])


def importer_mesures(df):
    """CSV : Date;Asset;Client;CPU moyen %;CPU max %;GPU moyen %  (Asset = ID ou nom ; Client = ID ou nom)."""
    assets = q("SELECT id, nom FROM assets")
    cli = q("SELECT id, nom FROM clients")
    a_id = {**{n.lower(): i for i, n in zip(assets.id, assets.nom)}, **{i.lower(): i for i in assets.id}}
    c_id = {**{n.lower(): i for i, n in zip(cli.id, cli.nom)}, **{i.lower(): i for i in cli.id}}
    rows, ign = [], []
    for k, r in df.iterrows():
        a = a_id.get(str(r.get("Asset", "")).strip().lower())
        c = c_id.get(str(r.get("Client", "")).strip().lower())
        dt = date_fr(r.get("Date"))
        if not (a and c and dt):
            ign.append(f"ligne {k + 2}")
            continue
        val = lambda col: nombre(r.get(col)) if str(r.get(col, "") or "").strip() else None
        rows.append((iso(dt), a, c, val("CPU moyen %"), val("CPU max %"), val("GPU moyen %")))
    with conn() as cx:
        cx.executemany("DELETE FROM mesures WHERE date=? AND asset_id=? AND client_id=?", [r_[:3] for r_ in rows])
        cx.executemany("INSERT INTO mesures VALUES (?,?,?,?,?,?)", rows)
    return dict(importées=len(rows), ignorées=ign)


def offre_active(client_id):
    l = lignes_mensuelles()
    l = l[(l.client_id == client_id) & (l.element == "Offre") & (l.statut == "Active")]
    return None if l.empty else l.iloc[-1]


# ------------------------------------------------------------------ écritures métier
def changer_prix(asset_id, prix, unite, date_effet, motif):
    a = q("SELECT * FROM assets WHERE id=?", (asset_id,))
    if a.empty:
        raise ValueError(f"Asset introuvable : {asset_id}")
    a = a.iloc[0]
    eff = d(a.date_effet)
    verifier_ouvert(date_effet, "Ce changement de prix")
    if eff and date_effet <= eff:
        raise ValueError(f"La date d'effet doit être postérieure au {eff:%d/%m/%Y}.")
    run("INSERT INTO prix_hist (asset_id, prix, unite, du, au, motif) VALUES (?,?,?,?,?,?)",
        (asset_id, a.prix, a.unite, iso(eff), iso(date_effet - timedelta(days=1)), f"Remplacé le {date_effet:%d/%m/%Y} : {motif}"))
    run("UPDATE assets SET prix=?, unite=?, date_effet=? WHERE id=?", (prix, unite, iso(date_effet), asset_id))
    synchroniser_parts()


def enregistrer_offre(oid, nom, desc, statut, lignes, date_effet=None, retirables_=None):
    """Crée ou modifie une offre. Avec date_effet, la nouvelle composition ne s'applique qu'à partir de ce mois :
    l'ancienne est historisée pour les mois précédents (le passé ne change pas)."""
    ex = q("SELECT * FROM offres WHERE id=?", (oid,))
    old = q("SELECT asset_id, qte FROM composition WHERE offre_id=?", (oid,))
    change = {(a, float(x)) for a, x in zip(old.asset_id, old.qte)} != {(a, float(x)) for a, x in lignes}
    with conn() as c:
        eff = d(ex.date_effet.iloc[0]) if len(ex) and "date_effet" in ex else None
        if len(ex) and change and date_effet:
            de = mois_debut(date_effet)
            verifier_ouvert(de, "Cette modification de composition")
            if eff and de < eff:
                raise ValueError(f"La date d'effet doit être à partir de {mois_debut(eff):%m/%Y} (dernière modification).")
            if eff != de:
                c.executemany("INSERT INTO composition_hist (offre_id, asset_id, qte, du, au) VALUES (?,?,?,?,?)",
                              [(oid, a, float(x), iso(eff) if eff else None, iso(mois_precedent(de))) for a, x in zip(old.asset_id, old.qte)])
            eff = de
        c.execute("INSERT OR REPLACE INTO offres (id, nom, description, statut, date_effet) VALUES (?,?,?,?,?)",
                  (oid, nom, desc, statut, iso(eff) if eff else None))
        c.execute("DELETE FROM composition WHERE offre_id=?", (oid,))
        c.executemany("INSERT OR REPLACE INTO composition VALUES (?,?,?)", [(oid, a, float(qq)) for a, qq in lignes])
        if retirables_ is not None:  # composants que le client peut retirer (les autres forment le socle)
            garde = {a for a, _ in lignes}
            c.execute("DELETE FROM offre_retirables WHERE offre_id=?", (oid,))
            c.executemany("INSERT INTO offre_retirables VALUES (?,?)", [(oid, a) for a in retirables_ if a in garde])


def historique_composition(oid):
    return q("SELECT h.*, a.nom FROM composition_hist h LEFT JOIN assets a ON a.id=h.asset_id WHERE h.offre_id=? ORDER BY h.au DESC", (oid,))


def lignes_offre(oid, quand=None):
    """Lignes d'affectation qui utilisent l'offre et ne sont pas terminées au mois donné."""
    quand = mois_debut(quand or date(annee(), mois_ref(), 1))
    a = q("SELECT a.*, c.nom AS client FROM affectations a LEFT JOIN clients c ON c.id=a.client_id WHERE a.code=? AND a.element='Offre'", (oid,))
    return a[[d(f) is None or d(f) >= quand for f in a.fin]].reset_index(drop=True)


def dupliquer_offre(oid):
    o = q("SELECT * FROM offres WHERE id=?", (oid,)).iloc[0]
    comp = q("SELECT asset_id, qte FROM composition WHERE offre_id=?", (oid,))
    nid = prochain_id("offres", "OF-", 2)
    enregistrer_offre(nid, f"{o.nom} (copie)", o.description, "Brouillon", list(zip(comp.asset_id, comp.qte)), retirables_=retirables(oid))
    return nid


def retirer_offre(oid, mode="garder", cible=None, debut=None, client_ids=None):
    """Retire une offre. mode : 'garder' (les clients la gardent), 'migrer' (vers l'offre cible au mois debut), 'arreter'."""
    n = 0
    if mode in ("migrer", "arreter"):
        debut = mois_debut(debut)
        verifier_ouvert(debut, "Ce retrait")
        lig = lignes_offre(oid, debut)
        if client_ids is not None:
            lig = lig[lig.client_id.isin(client_ids)]
        for r in lig.itertuples():
            if mode == "migrer":
                if mois_debut(r.debut) >= debut:
                    run("UPDATE affectations SET code=?, motif=? WHERE id=?", (cible, f"Offre {oid} retirée", r.id))
                else:
                    remplacer_ligne(r.id, cible, r.qte, debut, d(r.fin))
            else:
                arreter_lignes([r.id], mois_precedent(debut), f"Offre {oid} retirée")
            n += 1
    run("UPDATE offres SET statut='Retirée' WHERE id=?", (oid,))
    return n


def supprimer_offre(oid):
    if len(q("SELECT id FROM affectations WHERE code=?", (oid,))) or len(q("SELECT devis_id FROM devis_lignes WHERE code=?", (oid,))):
        raise ValueError("Cette offre est utilisée (affectations ou devis) : retirez-la plutôt.")
    with conn() as c:
        for t, col in (("composition", "offre_id"), ("composition_hist", "offre_id"), ("offres", "id")):
            c.execute(f"DELETE FROM {t} WHERE {col}=?", (oid,))


def enregistrer_affectation(client_id, operation, debut, offre=None, garder_options=True, options=()):
    debut = mois_debut(debut)
    verifier_ouvert(debut, "Cette affectation")
    fin = iso(mois_precedent(debut))
    aff = q("SELECT * FROM affectations WHERE client_id=?", (client_id,))
    msgs = []
    with conn() as c:
        def ajoute(op, element, code, qte):
            nid = prochain_id("affectations", "L-", 4)
            c.execute("INSERT INTO affectations (id, client_id, operation, element, code, qte, debut, fin) VALUES (?,?,?,?,?,?,?,?)", (nid, client_id, op, element, code, qte, iso(debut), None))
            c.commit()

        if operation == "Changer d'offre":
            n = 0
            for _, r in aff.iterrows():
                deb, f = d(r.debut), d(r.fin)
                if r.element == "Offre" and (f is None or f >= debut):
                    c.execute("UPDATE affectations SET fin=? WHERE id=?", (fin, r.id))
                    n += 1
                elif r.element == "Option" and not garder_options and deb < debut and (f is None or f >= debut):
                    c.execute("UPDATE affectations SET fin=? WHERE id=?", (fin, r.id))
            c.commit()
            ajoute("Changement d'offre", "Offre", offre, 1)
            msgs.append(f"{n} offre(s) clôturée(s), {offre} à partir de {debut:%m/%Y}")
        elif operation == "Nouvelle offre":
            ajoute("Nouvelle offre", "Offre", offre, 1)
            msgs.append(f"offre {offre} ajoutée")
        for a, qq in options:
            ajoute("Option", "Option", a, float(qq))
        if options:
            msgs.append(f"{len(options)} option(s) ajoutée(s)")
    return " ; ".join(msgs)


# ------------------------------------------------------------------ affectations : lignes datées (offres et options)
def _date_ref(a=None):
    a = a or annee()
    return date(a, mois_ref(a), 1)


def catalogue_df(a=None):
    """Offres actives et assets actifs avec leur coût mensuel unitaire au mois de référence."""
    a = a or annee()
    m = mois_ref(a)
    cam = couts_assets_mensuels(a)
    com = couts_offres_mensuels(cam, a)
    o = q("SELECT id, nom, description FROM offres WHERE statut='Active' ORDER BY id")
    s = q("SELECT id, nom, type, unite, fournisseur, vcpu, ram_go, gpu, gpu_modele, refacturation, parent_id FROM assets "
          "WHERE statut='Actif' AND COALESCE(refacturation, '') NOT LIKE 'part%' ORDER BY id")
    rows = [dict(element="Offre", code=r.id, libelle=r.nom, detail=r.description or "", type="Offre",
                 cout=float(com.loc[r.id, m]) if r.id in com.index else 0.0) for r in o.itertuples()]
    def det(r):
        ok = lambda v: v is not None and pd.notna(v) and v > 0
        modele = r.gpu_modele if isinstance(r.gpu_modele, str) else ""
        cap = " · ".join(x for x in [f"{r.gpu:g} GPU {modele}".strip() if ok(r.gpu) else "", f"{r.vcpu:g} vCPU" if ok(r.vcpu) else "",
                                     f"{r.ram_go:g} Go" if ok(r.ram_go) else ""] if x)
        if isinstance(r.parent_id, str):
            return f"part d'instance partagée · {cap}" if cap else "part d'instance partagée"
        if r.refacturation == "entiere":
            return f"instance entière · {cap}"
        return f"{r.type} · facturé {('à l' + chr(39) + r.unite.lower()) if r.unite == 'Heure' else ('au ' + r.unite.lower())}"
    rows += [dict(element="Option", code=r.id, libelle=r.nom, detail=det(r), type=r.type,
                  cout=float(cam.loc[r.id, m]) if r.id in cam.index else 0.0) for r in s.itertuples()]
    return pd.DataFrame(rows, columns=["element", "code", "libelle", "detail", "type", "cout"])


def lignes_client(client_id, a=None):
    """Lignes d'offres et d'options d'un client, avec état et coût mensuel."""
    a = a or annee()
    lm = lignes_mensuelles(a)
    l_ = lm[(lm.client_id == client_id) & lm.element.isin(["Offre", "Option"])].copy()
    ref = _date_ref(a)
    cam = couts_assets_mensuels(a)
    com = couts_offres_mensuels(cam, a)
    fige = est_cloture(a)

    rl = retraits_lignes()
    cmr = compositions_mensuelles(a)[mois_ref(a)] if rl else None

    def standard(r):
        src = com if r.element == "Offre" else cam
        return float(src.loc[r.code, mois_ref(a)]) if r.code in src.index else 0.0

    def unit(r):
        u = standard(r)
        if r.element == "Offre" and r.id in rl:
            u -= _moins_retraits(cmr[cmr.offre_id == r.code], rl[r.id], cam[mois_ref(a)])
        return u

    def etat(r):
        deb, fin = d(r.debut), d(r.fin)
        if fin and fin < ref:
            return "Terminée"
        if deb and deb > ref:
            return "À venir"
        return "En cours"

    if len(l_):
        l_["cout_unit"] = l_.apply(unit, axis=1) if not fige else l_["cout_ref"] / l_.qte.replace(0, 1)
        l_["cout_standard"] = l_.apply(standard, axis=1) if not fige else l_["cout_unit"]
        l_["cout_mois"] = l_.cout_unit * l_.qte.fillna(0)
        l_["etat"] = l_.apply(etat, axis=1)
        l_["facturee"] = [bool(fige or (d(x) and d(x) <= ref) or (d(x) and est_cloture(d(x).year))) for x in l_.debut]
    else:
        for c_ in ("cout_unit", "cout_standard", "cout_mois", "etat", "facturee"):
            l_[c_] = []
    if "motif" not in l_.columns:
        l_["motif"] = None
    detail = catalogue_df(a).set_index("code").detail if not fige else pd.Series(dtype=str)
    l_["detail"] = l_.code.map(detail).fillna("") if len(l_) else []
    return l_.sort_values(["element", "debut"], ascending=[True, True])


def tarif(code, quand=None):
    """Coût mensuel unitaire d'une offre ou d'un asset (au mois donné s'il est dans l'exercice, sinon au mois de référence)."""
    a = annee()
    quand = d(quand)
    m = quand.month if quand and quand.year == a else mois_ref()
    cam = couts_assets_mensuels(a)
    if code in cam.index:
        return float(cam.loc[code, m])
    com = couts_offres_mensuels(cam, a)
    return float(com.loc[code, m]) if code in com.index else 0.0


def _verifier_periode(debut, fin):
    if fin is not None and mois_debut(fin) < mois_debut(debut):
        raise ValueError(f"La date de fin ({mois_debut(fin):%m/%Y}) est avant la date de début ({mois_debut(debut):%m/%Y}).")


def _inserer_ligne(c, client_id, operation, element, code, qte, debut, fin=None, ref=None, motif=None):
    ids = [r[0] for r in c.execute("SELECT id FROM affectations")]
    n = max([int(i[2:]) for i in ids if str(i).startswith("L-") and str(i)[2:].isdigit()] + [0])
    nid = f"L-{n + 1:04d}"
    c.execute("INSERT INTO affectations (id, client_id, operation, element, code, qte, debut, fin, ref, motif) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (nid, client_id, operation, element, code, float(qte), iso(mois_debut(debut)), iso(mois_debut(fin)) if fin else None, ref, motif))
    return nid


def ajouter_lignes(client_id, lignes):
    """lignes : liste de dict(element, code, qte, debut, fin) — fin None = sans fin."""
    if not lignes:
        raise ValueError("Le panier est vide.")
    for l_ in lignes:
        if float(l_["qte"] or 0) <= 0:
            raise ValueError(f"Quantité nulle pour {l_['code']}.")
        _verifier_periode(l_["debut"], l_.get("fin"))
        verifier_ouvert(mois_debut(l_["debut"]), f"Le début de {l_['code']}")
    verifier_capacite(lignes)
    ids = []
    with conn() as c:
        for l_ in lignes:
            op = "Nouvelle offre" if l_["element"] == "Offre" else "Option"
            ids.append(_inserer_ligne(c, client_id, op, l_["element"], l_["code"], l_["qte"], l_["debut"], l_.get("fin")))
        c.execute("UPDATE clients SET statut='Actif' WHERE id=? AND statut <> 'Actif'", (client_id,))
    return ids


def _ligne(aff_id):
    r = q("SELECT * FROM affectations WHERE id=?", (aff_id,))
    if r.empty:
        raise ValueError(f"Ligne introuvable : {aff_id}")
    return r.iloc[0]


def remplacer_ligne(aff_id, code, qte, debut, fin=None):
    """Remplace une offre ou une option : l'ancienne s'arrête le mois précédent, la nouvelle commence au mois choisi."""
    old = _ligne(aff_id)
    debut = mois_debut(debut)
    _verifier_periode(debut, fin)
    verifier_ouvert(debut, "Ce remplacement")
    if mois_debut(old.debut) >= debut:
        raise ValueError(f"Le remplacement doit commencer après le début de la ligne actuelle ({d(old.debut):%m/%Y}). "
                         "Pour une ligne pas encore commencée, modifiez-la ou supprimez-la.")
    if d(old.fin) and d(old.fin) < debut:
        raise ValueError(f"Cette ligne est déjà terminée en {d(old.fin):%m/%Y}.")
    op = "Changement d'offre" if old.element == "Offre" else "Remplacement option"
    verifier_capacite([dict(element=old.element, code=code, qte=qte, debut=debut, fin=fin)], exclure=(aff_id,))
    with conn() as c:
        c.execute("UPDATE affectations SET fin=?, motif=? WHERE id=?", (iso(mois_precedent(debut)), f"Remplacée par {code} en {debut:%m/%Y}", aff_id))
        nid = _inserer_ligne(c, old.client_id, op, old.element, code, qte, debut, fin, motif=f"Remplace {aff_id} ({old.code})")
    return nid


def arreter_lignes(ids, dernier_mois, motif="", client_inactif=False):
    """Arrête des lignes après le dernier mois facturé. Une ligne qui n'a pas encore commencé est annulée (supprimée)."""
    dernier = mois_debut(dernier_mois)
    verifier_ouvert(ajouter_mois(dernier, 1), "Cet arrêt")
    arretees, annulees = 0, 0
    client_id = None
    with conn() as c:
        for i in ids:
            r = _ligne(i)
            client_id = r.client_id
            if mois_debut(r.debut) > dernier:
                c.execute("DELETE FROM affectations WHERE id=?", (i,))
                annulees += 1
                continue
            f = d(r.fin)
            if f is None or f > dernier:
                c.execute("UPDATE affectations SET fin=?, motif=? WHERE id=?", (iso(dernier), motif or "Arrêt", i))
                arretees += 1
        if client_inactif and client_id:
            c.execute("UPDATE clients SET statut='Inactif' WHERE id=?", (client_id,))
    return arretees, annulees


def modifier_dates(aff_id, debut, fin, qte=None):
    r = _ligne(aff_id)
    debut = mois_debut(debut)
    _verifier_periode(debut, fin)
    if debut != mois_debut(r.debut):
        verifier_ouvert(min(debut, mois_debut(r.debut)), "Ce changement de date de début")
    lointain = date(9999, 12, 1)
    f_old, f_new = d(r.fin) or lointain, (mois_debut(fin) if fin else lointain)
    if f_old != f_new and min(f_old, f_new) != lointain:
        verifier_ouvert(ajouter_mois(min(f_old, f_new), 1), "Ce changement de date de fin")
    if qte is not None and float(qte) != float(r.qte):
        verifier_ouvert(debut, "Ce changement de quantité")
    verifier_capacite([dict(element=r.element, code=r.code, qte=float(qte if qte is not None else r.qte), debut=debut, fin=fin)], exclure=(aff_id,))
    run("UPDATE affectations SET debut=?, fin=?, qte=? WHERE id=?",
        (iso(debut), iso(mois_debut(fin)) if fin else None, float(qte if qte is not None else r.qte), aff_id))


def supprimer_ligne(aff_id, forcer=False):
    """Supprime une ligne saisie par erreur. Si elle a déjà été comptée dans des mois réels, il faut forcer."""
    r = _ligne(aff_id)
    deb = mois_debut(r.debut)
    if est_cloture(deb.year):
        raise ValueError(f"Cette ligne commence dans l'exercice {deb.year}, clôturé : utilisez « Arrêter ».")
    if deb <= _date_ref() and not forcer:
        raise ValueError("Cette ligne a déjà été facturée : utilisez « Arrêter », ou confirmez la suppression.")
    run("DELETE FROM affectations WHERE id=?", (aff_id,))
    run("DELETE FROM aff_retraits WHERE aff_id=?", (aff_id,))


# ------------------------------------------------------------------ import CSV
def lire_csv(fichier):
    raw = fichier.read() if hasattr(fichier, "read") else Path(fichier).read_bytes()
    texte = raw.decode("utf-8-sig") if raw[:3] == b"\xef\xbb\xbf" else _decode(raw)
    sep = ";" if texte.split("\n", 1)[0].count(";") >= texte.split("\n", 1)[0].count(",") else ","
    from io import StringIO
    return pd.read_csv(StringIO(texte), sep=sep, dtype=str, keep_default_na=False)


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("cp1252")


def importer_assets(df):
    rapport = {"ajoutés": 0, "mis à jour": 0, "prix historisés": 0, "ignorés": []}
    existants = q("SELECT * FROM assets").set_index("id")
    for i, r in df.iterrows():
        aid = r.get("ID", "").strip()
        unite = r.get("Unité", "").strip()
        if not aid:
            rapport["ignorés"].append(f"ligne {i + 2} : ID vide")
            continue
        if unite not in FACTEURS:
            rapport["ignorés"].append(f"{aid} : unité inconnue « {unite} »")
            continue
        prix = nombre(r.get("Prix unitaire"))
        eff = date_fr(r.get("Date effet"))
        ajouter_liste("type", r.get("Type", "").strip())
        if aid in existants.index:
            old = existants.loc[aid]
            oe = d(old.date_effet)
            if (float(old.prix or 0) != prix or old.unite != unite) and oe and eff and eff > oe:
                run("INSERT INTO prix_hist (asset_id, prix, unite, du, au, motif) VALUES (?,?,?,?,?,?)",
                    (aid, old.prix, old.unite, iso(oe), iso(eff - timedelta(days=1)), "Remplacé par import CSV"))
                rapport["prix historisés"] += 1
            rapport["mis à jour"] += 1
        else:
            rapport["ajoutés"] += 1
        cap = {k: (nombre(r.get(col)) if str(r.get(col, "") or "").strip() else None)
               for k, col in [("vcpu", "vCPU"), ("ram_go", "RAM Go"), ("stockage_go", "Stockage Go"), ("gpu", "GPU"), ("reseau_gbs", "Réseau Gbs")]}
        fl = lire_flavor(r.get("Nom", ""))
        for k in ("vcpu", "ram_go", "gpu"):
            if cap[k] is None and fl.get(k) is not None:
                cap[k] = fl[k]
        refac = {"part": "part_vcpu", "part vcpu": "part_vcpu", "part gpu": "part_gpu", "entiere": "entiere", "entière": "entiere"}.get(
            str(r.get("Refacturation", "") or "").strip().lower())
        enregistrer_asset(dict(id=aid, type=r.get("Type", ""), nom=r.get("Nom", ""), fournisseur=r.get("Fournisseur", ""), prix=prix, unite=unite,
                               qte_parc=nombre(r.get("Qté parc")), date_effet=iso(eff), statut=r.get("Statut", "") or "Actif",
                               region=(r.get("Région", "") or None), gpu_modele=fl.get("gpu_modele"), refacturation=refac, **cap), synchro=False)
    synchroniser_parts()
    return rapport


def importer_clients(df):
    rapport = {"ajoutés": 0, "mis à jour": 0, "ignorés": []}
    existants = set(q("SELECT id FROM clients").id)
    for i, r in df.iterrows():
        nom = r.get("Nom du client", "").strip()
        if not nom:
            rapport["ignorés"].append(f"ligne {i + 2} : nom vide")
            continue
        cid = r.get("ID", "").strip() or prochain_id("clients", "CL-", 3)
        ajouter_liste("entite", r.get("Entité", "").strip())
        ajouter_liste("pays", r.get("Pays", "").strip())
        rapport["mis à jour" if cid in existants else "ajoutés"] += 1
        run("INSERT OR REPLACE INTO clients VALUES (?,?,?,?,?,?,?,?)",
            (cid, nom, r.get("Entité", ""), r.get("Pays", ""), r.get("Responsable", ""), r.get("E-mail", ""),
             r.get("Statut", "") or "Actif", iso(date_fr(r.get("Date entrée")))))
        existants.add(cid)
    return rapport


# ------------------------------------------------------------------ données d'exemple
def _seed(c):
    for k, v in [("annee", 2026), ("mois_ref", 10)]:
        c.execute("INSERT OR REPLACE INTO parametres VALUES (?,?)", (k, str(v)))
    for cat, vals in {
        "type": ["Serveur", "GPU", "CPU", "RAM", "Stockage", "Licence", "Service", "Réseau"],
        "entite": ["R&D", "Service Client", "Risques", "Marketing", "Finance", "Industrie", "RH", "Juridique", "IT Interne"],
        "pays": ["France", "Belgique", "Allemagne", "Espagne", "Italie", "Portugal", "Pays-Bas"],
    }.items():
        c.executemany("INSERT OR IGNORE INTO listes VALUES (?,?)", [(cat, v) for v in vals])
    c.commit()
    if (DATA_DIR / "Import_Assets.csv").exists():
        importer_assets(lire_csv(DATA_DIR / "Import_Assets.csv"))
    if (DATA_DIR / "Import_Clients.csv").exists():
        importer_clients(lire_csv(DATA_DIR / "Import_Clients.csv"))
    c.executemany("INSERT INTO prix_hist (asset_id, prix, unite, du, au, motif) VALUES (?,?,?,?,?,?)", [
        ("A-004", 0.010, "Heure", "2026-01-01", "2026-06-30", "Tarif initial — hausse énergie"),
        ("A-010", 9.00, "Jour", "2026-01-01", "2026-06-30", "Tarif initial — révision contrat datacenter"),
        ("A-031", 3.80, "Jour", "2026-01-01", "2026-06-30", "Tarif initial — révision contrat datacenter")])
    c.executemany("INSERT INTO offres (id, nom, description, statut) VALUES (?,?,?,?)", [
        ("OF-01", "IA Starter", "1 GPU L40S, 8 vCPU, 64 Go, 1 To — prototypage", "Active"),
        ("OF-02", "IA Standard", "2 GPU H100, 32 vCPU, 256 Go, 5 To — projets", "Active"),
        ("OF-03", "IA Performance", "4 GPU H100, 64 vCPU, 512 Go, 10 To, support — production", "Active"),
        ("OF-04", "Calcul CPU", "16 vCPU, 128 Go, 2 To — traitements de données", "Active"),
        ("OF-05", "IA Inférence", "2 GPU L4, 16 vCPU, 128 Go, 2 To, IP publique — mise en production", "Active")])
    comp = {
        "OF-01": [("A-003", 1), ("A-004", 8), ("A-005", 64), ("A-006", 1), ("A-007", 1), ("A-010", 1)],
        "OF-02": [("A-002", 2), ("A-004", 32), ("A-005", 256), ("A-006", 5), ("A-007", 2), ("A-008", 1), ("A-010", 2)],
        "OF-03": [("A-001", 1), ("A-002", 4), ("A-004", 64), ("A-005", 512), ("A-006", 10), ("A-007", 4), ("A-008", 1), ("A-009", 1), ("A-010", 4), ("A-011", 1)],
        "OF-04": [("A-004", 16), ("A-005", 128), ("A-006", 2), ("A-011", 1)],
        "OF-05": [("A-014", 2), ("A-004", 16), ("A-005", 128), ("A-006", 2), ("A-010", 2), ("A-034", 1), ("A-025", 2)],
    }
    c.executemany("INSERT INTO composition VALUES (?,?,?)", [(o, a, q_) for o, l in comp.items() for a, q_ in l])
    aff = [
        ("CL-001", "Nouvelle offre", "Offre", "OF-03", 1, "2026-01-01", None), ("CL-001", "Option", "Option", "A-002", 2, "2026-03-01", None),
        ("CL-002", "Nouvelle offre", "Offre", "OF-02", 1, "2026-01-01", "2026-10-01"), ("CL-002", "Option", "Option", "A-002", 1, "2026-06-01", "2026-10-01"),
        ("CL-002", "Option", "Option", "A-007", 2, "2026-06-01", "2026-10-01"), ("CL-002", "Changement d'offre", "Offre", "OF-03", 1, "2026-11-01", None),
        ("CL-003", "Nouvelle offre", "Offre", "OF-02", 1, "2026-01-01", None), ("CL-003", "Option", "Option", "A-006", 5, "2026-04-01", None),
        ("CL-004", "Nouvelle offre", "Offre", "OF-01", 1, "2026-01-01", "2026-06-01"), ("CL-004", "Changement d'offre", "Offre", "OF-02", 1, "2026-07-01", None),
        ("CL-005", "Nouvelle offre", "Offre", "OF-04", 1, "2026-03-01", None), ("CL-006", "Nouvelle offre", "Offre", "OF-02", 1, "2026-02-01", None),
        ("CL-006", "Option", "Option", "A-002", 1, "2026-09-01", None), ("CL-007", "Nouvelle offre", "Offre", "OF-01", 1, "2026-01-01", None),
        ("CL-007", "Option", "Option", "A-003", 1, "2026-05-01", None),
        ("CL-007", "Nouvelle offre", "Offre", "OF-04", 1, "2026-03-01", "2026-12-01"), ("CL-007", "Option", "Option", "A-006", 2, "2026-01-01", None), ("CL-008", "Nouvelle offre", "Offre", "OF-01", 1, "2026-04-01", None),
        ("CL-008", "Option", "Option", "A-003", 1, "2026-10-01", None), ("CL-009", "Nouvelle offre", "Offre", "OF-03", 1, "2026-06-01", None),
        ("CL-012", "Nouvelle offre", "Offre", "OF-05", 1, "2026-05-01", None), ("CL-015", "Nouvelle offre", "Offre", "OF-04", 2, "2026-03-01", None),
        ("CL-017", "Nouvelle offre", "Offre", "OF-01", 1, "2026-02-01", None), ("CL-018", "Nouvelle offre", "Offre", "OF-05", 1, "2026-06-01", None),
        ("CL-020", "Nouvelle offre", "Offre", "OF-02", 1, "2026-01-01", None), ("CL-021", "Nouvelle offre", "Offre", "OF-03", 1, "2026-02-01", None),
        ("CL-021", "Option", "Option", "A-033", 2, "2026-04-01", None), ("CL-023", "Nouvelle offre", "Offre", "OF-02", 1, "2026-03-01", None),
        ("CL-024", "Nouvelle offre", "Offre", "OF-01", 1, "2026-06-01", None), ("CL-026", "Nouvelle offre", "Offre", "OF-04", 1, "2026-04-01", None),
        ("CL-027", "Nouvelle offre", "Offre", "OF-05", 1, "2026-01-01", None), ("CL-029", "Nouvelle offre", "Offre", "OF-05", 1, "2026-05-01", None),
        ("CL-030", "Nouvelle offre", "Offre", "OF-01", 1, "2026-03-01", None), ("CL-035", "Nouvelle offre", "Offre", "OF-02", 1, "2026-04-01", None),
        ("CL-036", "Nouvelle offre", "Offre", "OF-04", 1, "2026-07-01", None), ("CL-038", "Nouvelle offre", "Offre", "OF-05", 1, "2026-09-01", None),
        # instances cloud IBM : parts de vCPU (A-038, part de A-035) et instances entières (A-036, A-037)
        ("CL-027", "Option", "Option", "A-038", 64, "2026-04-01", None), ("CL-004", "Option", "Option", "A-038", 48, "2026-05-01", None),
        ("CL-002", "Option", "Option", "A-038", 32, "2026-06-01", None), ("CL-001", "Option", "Option", "A-038", 64, "2026-07-01", None),
        ("CL-021", "Option", "Option", "A-038", 32, "2026-08-01", None), ("CL-006", "Option", "Option", "A-038", 16, "2026-09-01", None),
        ("CL-030", "Option", "Option", "A-038", 32, "2026-09-01", None), ("CL-008", "Option", "Option", "A-038", 32, "2026-11-01", None),
        ("CL-029", "Option", "Option", "A-036", 1, "2026-05-01", None), ("CL-009", "Option", "Option", "A-037", 1, "2026-06-01", None),
        ("CL-012", "Option", "Option", "A-037", 1, "2026-07-01", None), ("CL-018", "Option", "Option", "A-037", 1, "2026-08-01", None),
    ]
    c.executemany("INSERT INTO affectations (id, client_id, operation, element, code, qte, debut, fin) VALUES (?,?,?,?,?,?,?,?)",
                  [(f"L-{i + 1:04d}",) + a for i, a in enumerate(aff)])
    c.commit()


# ------------------------------------------------------------------ devis
STATUTS_DEVIS = ["Brouillon", "Envoyé"]  # le devis est informatif : il ne crée ni ne modifie aucune affectation
RETOURS_DEVIS = ["En discussion", "Accepté", "Refusé"]  # note de suivi (retour du client), sans effet sur les données


def ajouter_mois(x, n):
    x = mois_debut(x)
    m = x.month - 1 + n
    return date(x.year + m // 12, m % 12 + 1, 1)


def catalogue_codes():
    """Libellés « CODE — nom » pour les offres actives puis les assets actifs."""
    o = q("SELECT id, nom FROM offres WHERE statut='Active' ORDER BY id")
    a = q("SELECT id, nom FROM assets WHERE statut='Actif' ORDER BY id")
    return [f"{r.id} — {r.nom}" for r in o.itertuples()] + [f"{r.id} — {r.nom} (option)" for r in a.itertuples()]


def devis_detail(lignes, debut):
    """lignes : liste (code, qte) ou (code, qte, retraits). Retourne un DataFrame chiffré au tarif du mois de début
    (une offre personnalisée est diminuée du coût des composants retirés)."""
    debut = mois_debut(debut)
    a = annee()
    m = debut.month if debut.year == a else mois_ref()
    cam = couts_assets_mensuels(a)
    com = couts_offres_mensuels(cam, a)
    offres = q("SELECT id, nom, description FROM offres").set_index("id")
    assets = q("SELECT id, nom, type FROM assets").set_index("id")
    comp = q("SELECT c.offre_id, c.asset_id, c.qte, a.nom FROM composition c LEFT JOIN assets a ON a.id=c.asset_id")
    rows = []
    noms = assets.nom
    for l_ in lignes:
        code, qte = l_[0], l_[1]
        rt = _json_retraits(l_[2]) if len(l_) > 2 else {}
        if code in offres.index:
            contenu = ", ".join(f"{int(r.qte) if float(r.qte).is_integer() else r.qte} × {r.nom}" for r in comp[comp.offre_id == code].itertuples())
            tarif_ = float(com.loc[code, m]) if code in com.index else 0.0
            if rt:
                tarif_ -= _moins_retraits(composition_au(code, debut), rt, cam[m])
            rows.append(dict(element="Offre", code=code, designation=offres.loc[code, "nom"] + (" (personnalisée)" if rt else ""),
                             detail=contenu + (f" · retiré : {texte_retraits(rt, noms)}" if rt else ""), qte=float(qte), tarif=tarif_))
        elif code in assets.index:
            rows.append(dict(element="Option", code=code, designation=assets.loc[code, "nom"], detail=f"Option · {assets.loc[code, 'type']}",
                             qte=float(qte), tarif=float(cam.loc[code, m]) if code in cam.index else 0.0))
    df = pd.DataFrame(rows, columns=["element", "code", "designation", "detail", "qte", "tarif"])
    df["mensuel"] = df.qte * df.tarif
    return df


def lignes_devis_calcul(did):
    """(code, qte, retraits) des lignes d'un devis, pour devis_detail."""
    l_ = devis_lignes_df(did)
    return list(zip(l_.code, l_.qte, l_.retraits))


def devis_totaux(df, debut, duree):
    debut = mois_debut(debut)
    mensuel = float(df.mensuel.sum()) if len(df) else 0.0
    dans_exercice = max(0, min(int(duree), 13 - debut.month)) if debut.year == annee() else 0
    return dict(mensuel=mensuel, total=mensuel * int(duree), exercice=mensuel * dans_exercice,
                mois_exercice=dans_exercice, fin=ajouter_mois(debut, int(duree) - 1))


def statut_effectif(statut, date_devis, validite, auj=None):
    """« Expiré » quand un devis envoyé (ou brouillon) a dépassé sa date de validité."""
    auj = auj or date.today()
    if statut == "Envoyé" and date_devis and d(date_devis) + timedelta(days=int(validite or 30)) < auj:
        return "Expiré"
    return statut


def devis_lignes_df(did):
    """Lignes d'un devis avec la ligne d'affectation remplacée (libellé lisible)."""
    l_ = q("SELECT * FROM devis_lignes WHERE devis_id=? ORDER BY num", (did,))
    if "remplace" not in l_.columns:
        l_["remplace"] = None
    l_["remplace"] = pd.Series([x if isinstance(x, str) and x else None for x in l_.remplace], index=l_.index, dtype=object)
    l_["remplace_lib"] = [libelle_affectation(x) if x else None for x in l_.remplace]
    l_["retraits"] = [_json_retraits(x) for x in (l_.retraits if "retraits" in l_.columns else [None] * len(l_))]
    return l_


def libelle_affectation(aff_id):
    r = q("SELECT a.*, o.nom AS o_nom, s.nom AS s_nom FROM affectations a LEFT JOIN offres o ON o.id=a.code "
          "LEFT JOIN assets s ON s.id=a.code WHERE a.id=?", (aff_id,))
    if r.empty:
        return f"{aff_id} (supprimée)"
    r = r.iloc[0]
    nom = r.o_nom if r.element == "Offre" else r.s_nom
    return f"{nom}" + ("" if r.element == "Offre" and float(r.qte) == 1 else f" × {float(r.qte):g}")


def lignes_ouvertes_au(client_id, quand):
    """Lignes d'affectation d'un client actives au mois donné (ou qui commencent avant et ne sont pas finies)."""
    quand = mois_debut(quand)
    a = q("SELECT a.*, o.nom AS o_nom, s.nom AS s_nom FROM affectations a LEFT JOIN offres o ON o.id=a.code "
          "LEFT JOIN assets s ON s.id=a.code WHERE a.client_id=? ORDER BY a.element DESC, a.debut", (client_id,))
    if a.empty:
        return a.assign(libelle=[], cout=[])
    a = a[[(d(f) is None or d(f) >= quand) and d(x) < quand for x, f in zip(a.debut, a.fin)]].copy()
    a["libelle"] = [o if e == "Offre" else s_ for e, o, s_ in zip(a.element, a.o_nom, a.s_nom)]
    rl = retraits_lignes()
    a["retraits"] = [rl.get(i, {}) for i in a.id]
    a["cout"] = [(tarif(c_, quand) - cout_retraits(c_, rl.get(i), quand)) * float(q_) for i, c_, q_ in zip(a.id, a.code, a.qte)]
    return a


def devis_liste():
    d_ = q("SELECT d.*, c.nom AS client, c.entite, c.pays FROM devis d LEFT JOIN clients c ON c.id=d.client_id ORDER BY d.id DESC")
    tot = []
    for r in d_.itertuples():
        det = devis_detail(lignes_devis_calcul(r.id), r.debut)
        tot.append(devis_totaux(det, r.debut, r.duree))
    d_["mensuel"] = [t["mensuel"] for t in tot]
    d_["total"] = [t["total"] for t in tot]
    d_["fin"] = [t["fin"] for t in tot]
    d_["statut_aff"] = [statut_effectif(s_, dd, v) for s_, dd, v in zip(d_.statut, d_.date_devis, d_.validite)]
    d_["expire_le"] = [d(dd) + timedelta(days=int(v or 30)) if dd else None for dd, v in zip(d_.date_devis, d_.validite)]
    return d_


def _histo(c, did, evenement, detail=""):
    c.execute("INSERT INTO devis_historique (devis_id, date, evenement, detail) VALUES (?,?,?,?)",
              (did, datetime.now().strftime("%Y-%m-%d %H:%M"), evenement, detail))


def historique_devis(did):
    h = q("SELECT * FROM devis_historique WHERE devis_id=? ORDER BY id", (did,))
    if len(h):
        return h
    dv = q("SELECT * FROM devis WHERE id=?", (did,))
    if dv.empty:
        return h
    dv = dv.iloc[0]
    rows = [dict(date=dv.date_devis, evenement="Créé", detail="")]
    if dv.statut != "Brouillon":
        rows.append(dict(date=dv.date_envoi if "date_envoi" in dv and dv.date_envoi else dv.date_devis, evenement="Envoyé", detail=""))
    if dv.retour:
        rows.append(dict(date=dv.retour_date, evenement=f"Retour client : {dv.retour}", detail=dv.retour_note or ""))
    return pd.DataFrame(rows)


def enregistrer_devis(did, date_devis, client_id, debut, duree, validite, statut, objet, commentaire, lignes):
    """lignes : liste de (code, qte), (code, qte, aff_remplacée) ou (code, qte, aff_remplacée, retraits)."""
    import json
    nouveau = not did
    if nouveau:
        did = prochain_id_devis(date_devis)
    lignes = [tuple(l_) + (None,) * (4 - len(l_)) for l_ in lignes]
    with conn() as c:
        c.execute("INSERT OR REPLACE INTO devis (id, date_devis, client_id, debut, duree, validite, statut, objet, commentaire, date_decision, "
                  "version, date_envoi, ref_bc, signataire, motif_refus, fin_mode, retour, retour_date, retour_note, fichier) "
                  "VALUES (?,?,?,?,?,?,?,?,?,(SELECT date_decision FROM devis WHERE id=?),COALESCE((SELECT version FROM devis WHERE id=?),1),"
                  "(SELECT date_envoi FROM devis WHERE id=?),(SELECT ref_bc FROM devis WHERE id=?),(SELECT signataire FROM devis WHERE id=?),"
                  "(SELECT motif_refus FROM devis WHERE id=?),(SELECT fin_mode FROM devis WHERE id=?),(SELECT retour FROM devis WHERE id=?),"
                  "(SELECT retour_date FROM devis WHERE id=?),(SELECT retour_note FROM devis WHERE id=?),(SELECT fichier FROM devis WHERE id=?))",
                  (did, iso(date_devis), client_id, iso(mois_debut(debut)), int(duree), int(validite), statut, objet, commentaire) + (did,) * 11)
        c.execute("DELETE FROM devis_lignes WHERE devis_id=?", (did,))
        c.executemany("INSERT INTO devis_lignes (devis_id, num, element, code, qte, remplace, retraits) VALUES (?,?,?,?,?,?,?)",
                      [(did, i + 1, "Offre" if str(code).startswith("OF") else "Option", code, float(qte), rem or None,
                        json.dumps(_json_retraits(rt)) if _json_retraits(rt) else None)
                       for i, (code, qte, rem, rt) in enumerate(lignes)])
        if nouveau:
            _histo(c, did, "Créé", "brouillon")
        else:
            der = c.execute("SELECT evenement, substr(date,1,10) FROM devis_historique WHERE devis_id=? ORDER BY id DESC LIMIT 1", (did,)).fetchone()
            if not (der and der[0] in ("Créé", "Modifié") and der[1] == date.today().isoformat()):
                _histo(c, did, "Modifié", f"{len(lignes)} ligne(s)")
    return did


def prochain_id_devis(date_devis=None):
    an = (d(date_devis) or date.today()).year
    return prochain_id("devis", f"DV-{an}-", 4)


def _slug(txt):
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", t).strip("-")[:40] or "client"


def chemin_devis(did, version=None):
    """data/devis/<année>/<n°>_v<version>_<client>.pdf"""
    dv = q("SELECT d.*, c.nom AS client FROM devis d LEFT JOIN clients c ON c.id=d.client_id WHERE d.id=?", (did,)).iloc[0]
    v = int(version or dv.version or 1)
    an = (d(dv.date_devis) or date.today()).year
    return DEVIS_DIR / str(an) / f"{did}_v{v}_{_slug(dv.client)}.pdf"


def envoyer_devis(did, pdf=None):
    """Passe le devis en « Envoyé » et enregistre son PDF dans data/devis/<année>/ ; renvoie le chemin du fichier."""
    dv = q("SELECT * FROM devis WHERE id=?", (did,)).iloc[0]
    v = int(dv.version or 1)
    cible = None
    if pdf is not None:
        cible = chemin_devis(did, v)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(pdf)
    with conn() as c:
        c.execute("UPDATE devis SET statut='Envoyé', date_envoi=?, fichier=COALESCE(?, fichier) WHERE id=?",
                  (date.today().isoformat(), str(cible.relative_to(DEVIS_DIR.parent)) if cible else None, did))
        if pdf is not None:
            c.execute("INSERT OR REPLACE INTO devis_versions (devis_id, version, date, pdf) VALUES (?,?,?,?)", (did, v, date.today().isoformat(), pdf))
        _histo(c, did, "Envoyé", f"PDF v{v}" + (f" · {cible.name}" if cible else ""))
    return cible


def brouillon_mail(did, pdf):
    """Brouillon de mail (.eml) avec le devis en pièce jointe : s'ouvre dans Outlook, Apple Mail ou Thunderbird, prêt à envoyer."""
    from email.message import EmailMessage
    from email.utils import formatdate
    dv = q("SELECT d.*, c.nom AS client, c.email, c.responsable FROM devis d LEFT JOIN clients c ON c.id=d.client_id WHERE d.id=?", (did,)).iloc[0]
    det = devis_detail(lignes_devis_calcul(did), dv.debut)
    tot = devis_totaux(det, dv.debut, dv.duree)
    v = int(dv.version or 1)
    expire = d(dv.date_devis) + timedelta(days=int(dv.validite or 30))
    eur_ = lambda x: f"{x:,.2f} €".replace(",", " ").replace(".", ",")  # noqa: E731
    m = EmailMessage()
    m["To"] = dv.email or ""
    m["Subject"] = f"Devis {did}{f' (version {v})' if v > 1 else ''} – {dv.objet or 'Plateforme IA'}"
    m["Date"] = formatdate(localtime=True)
    m["X-Unsent"] = "1"  # Outlook ouvre le fichier comme un brouillon modifiable
    m.set_content(
        f"Bonjour{(' ' + dv.responsable) if dv.responsable else ''},\n\n"
        f"Veuillez trouver ci-joint notre devis {did} pour « {dv.objet or 'la plateforme IA'} ».\n\n"
        f"- Montant mensuel : {eur_(tot['mensuel'])}\n"
        f"- Période : {mois_txt_court(dv.debut)} → {mois_txt_court(tot['fin'])} ({int(dv.duree)} mois), soit {eur_(tot['total'])}\n"
        f"- Validité : jusqu'au {expire:%d/%m/%Y}\n\n"
        "Nous restons à votre disposition pour toute question.\n\nCordialement,\nÉquipe A – Plateforme IA\n")
    m.add_attachment(pdf, maintype="application", subtype="pdf", filename=chemin_devis(did, v).name)
    return m.as_bytes()


def noter_retour(did, retour, quand=None, note=""):
    """Note de suivi (retour du client) : purement informative, aucune affectation n'est créée ni modifiée."""
    if retour not in RETOURS_DEVIS:
        raise ValueError("Retour inconnu.")
    with conn() as c:
        c.execute("UPDATE devis SET retour=?, retour_date=?, retour_note=? WHERE id=?", (retour, iso(quand or date.today()), note or None, did))
        _histo(c, did, f"Retour client : {retour}", note or "")


def effacer_retour(did):
    with conn() as c:
        c.execute("UPDATE devis SET retour=NULL, retour_date=NULL, retour_note=NULL WHERE id=?", (did,))
        _histo(c, did, "Note de suivi effacée", "")


def nouvelle_version(did, pdf=None):
    dv = q("SELECT * FROM devis WHERE id=?", (did,)).iloc[0]
    v = int(dv.version or 1)
    with conn() as c:
        if pdf is not None and not c.execute("SELECT 1 FROM devis_versions WHERE devis_id=? AND version=?", (did, v)).fetchone():
            c.execute("INSERT INTO devis_versions (devis_id, version, date, pdf) VALUES (?,?,?,?)", (did, v, date.today().isoformat(), pdf))
        c.execute("UPDATE devis SET version=?, statut='Brouillon', date_decision=NULL, motif_refus=NULL, retour=NULL, retour_date=NULL, "
                  "retour_note=NULL, date_devis=? WHERE id=?", (v + 1, date.today().isoformat(), did))
        _histo(c, did, "Nouvelle version", f"v{v + 1} (la v{v} reste consultable)")
    return v + 1


def versions_devis(did):
    return q("SELECT devis_id, version, date FROM devis_versions WHERE devis_id=? ORDER BY version", (did,))


def pdf_version(did, version):
    with conn() as c:
        r = c.execute("SELECT pdf FROM devis_versions WHERE devis_id=? AND version=?", (did, int(version))).fetchone()
    return r[0] if r else None


def plan_acceptation(did, fin_mode="echeance"):
    """Effet du devis pour le client s'il le signe (information seulement : rien n'est modifié)."""
    dv = q("SELECT * FROM devis WHERE id=?", (did,)).iloc[0]
    debut = mois_debut(dv.debut)
    fin = ajouter_mois(debut, int(dv.duree) - 1) if fin_mode == "echeance" else None
    lig = devis_lignes_df(did)
    ouvertes = lignes_ouvertes_au(dv.client_id, debut)
    remplacees = set(x for x in lig.remplace if x)
    arrets, creations, inchanges = [], [], []
    for r in ouvertes.itertuples():
        if r.id in remplacees:
            par = lig[lig.remplace == r.id]
            par_lib = ", ".join(libelle_code(c_) for c_ in par.code)
            arrets.append(dict(id=r.id, libelle=libelle_affectation(r.id), fin=mois_precedent(debut), par=par_lib, cout=float(r.cout)))
        else:
            inchanges.append(dict(id=r.id, libelle=libelle_affectation(r.id), cout=float(r.cout), fin=d(r.fin)))
    for r in lig.itertuples():
        creations.append(dict(element=r.element, code=r.code, libelle=libelle_code(r.code), qte=float(r.qte), debut=debut, fin=fin,
                              cout=(tarif(r.code, debut) - cout_retraits(r.code, r.retraits, debut)) * float(r.qte), remplace=r.remplace_lib))
    avant = sum(a["cout"] for a in arrets) + sum(i["cout"] for i in inchanges if i["fin"] is None or i["fin"] >= debut)
    apres = avant - sum(a["cout"] for a in arrets) + sum(c_["cout"] for c_ in creations)
    # prévision de l'année du début
    an = debut.year
    lm = lignes_mensuelles(an) if an >= annee() else None
    mois = {m: 0.0 for m in range(1, 13)}
    if lm is not None and len(lm):
        mine = lm[lm.client_id == dv.client_id]
        for _, r in mine.iterrows():
            for m in range(1, 13):
                v = float(r[m])
                if r["id"] in remplacees and date(an, m, 1) >= debut:
                    v = 0.0
                mois[m] += v
    for c_ in creations:
        for m in range(1, 13):
            dm = date(an, m, 1)
            if dm >= debut and (fin is None or dm <= fin):
                mois[m] += c_["cout"]
    prevision = sum(mois.values())
    bud = q("SELECT montant FROM budgets WHERE annee=? AND client_id=?", (an, dv.client_id))
    budget = float(bud.montant.iloc[0]) if len(bud) else 0.0
    return dict(debut=debut, fin=fin, arrets=arrets, creations=creations, inchanges=inchanges, avant=avant, apres=apres,
                annee=an, prevision=prevision, budget=budget)


def libelle_code(code):
    r = q("SELECT nom FROM offres WHERE id=? UNION ALL SELECT nom FROM assets WHERE id=?", (code, code))
    return r.nom.iloc[0] if len(r) else code


def supprimer_devis(did):
    with conn() as c:
        c.execute("DELETE FROM devis_lignes WHERE devis_id=?", (did,))
        c.execute("DELETE FROM devis_historique WHERE devis_id=?", (did,))
        c.execute("DELETE FROM devis_versions WHERE devis_id=?", (did,))
        c.execute("DELETE FROM devis WHERE id=?", (did,))


def _seed_mesures(c):
    """Mesures de supervision d'exemple (30 jours) pour les instances IBM de démonstration."""
    niveaux = {("A-035", "CL-001"): 82, ("A-035", "CL-021"): 91, ("A-035", "CL-002"): 18, ("A-035", "CL-004"): 55, ("A-035", "CL-006"): 40,
               ("A-035", "CL-030"): 63, ("A-035", "CL-027"): 4, ("A-036", "CL-029"): 22, ("A-037", "CL-009"): 78, ("A-037", "CL-012"): 85,
               ("A-037", "CL-018"): 71}
    if not c.execute("SELECT COUNT(*) FROM assets WHERE id IN ('A-035','A-036','A-037')").fetchone()[0]:
        return
    rows = []
    fin = date(2026, 10, 19)
    for j in range(30):
        dt = fin - timedelta(days=29 - j)
        for k, ((a, cl), v) in enumerate(niveaux.items()):
            bruit = ((j * 7 + k * 13) % 11 - 5) * 0.8
            moy = max(0.5, min(99.5, v + bruit))
            gpu = moy if a == "A-037" else None
            cpu = moy if a != "A-037" else max(1.0, moy * .35)
            rows.append((dt.isoformat(), a, cl, round(cpu, 1), round(min(100, cpu * 1.3 + 5), 1), round(gpu, 1) if gpu else None))
    c.executemany("INSERT INTO mesures VALUES (?,?,?,?,?,?)", rows)
    c.commit()


def _seed_devis(c):
    rows = [
        ("DV-2026-0001", "2026-10-02", "CL-002", "2026-11-01", 12, 30, "Envoyé", "Passage à l'offre IA Performance", "Remplace l'offre IA Standard et ses options.", "2026-10-09",
         [("OF-03", 1, "L-0003")]),
        ("DV-2026-0002", "2026-10-14", "CL-011", "2026-11-01", 12, 30, "Envoyé", "Plateforme de détection de fraude", "Montée en charge prévue au T1.", None,
         [("OF-02", 1, None), ("A-002", 1, None), ("A-022", 50, None)]),
        ("DV-2026-0003", "2026-10-18", "CL-039", "2027-01-01", 6, 30, "Brouillon", "Pilote formation interne", "", None,
         [("OF-01", 1, None), ("A-027", 10, None)]),
        ("DV-2026-0004", "2026-10-15", "CL-007", "2027-01-01", 12, 30, "Envoyé", "Passage en production", "Remplace IA Starter et le GPU L40S.", None,
         [("OF-02", 1, "L-0014"), ("A-002", 1, "L-0015"), ("A-007", 2, None)]),
        ("DV-2026-0005", "2026-08-03", "CL-004", "2026-09-01", 12, 30, "Envoyé", "Passage à IA Performance", "", "2026-08-21",
         [("OF-03", 1, "L-0010")]),
        ("DV-2026-0006", "2026-09-01", "CL-006", "2026-10-01", 12, 30, "Envoyé", "Stockage images supplémentaire", "", None,
         [("A-006", 10, None)]),
        ("DV-2026-0007", "2026-10-16", "CL-011", "2027-01-01", 12, 30, "Envoyé", "Calcul partagé et GPU d'inférence", "", None,
         [("A-038", 64, None), ("A-037", 1, None)]),
    ]
    retours = {"DV-2026-0001": ("Accepté", "2026-10-09", "BC-2026-118 signé par L. Bernard"),
               "DV-2026-0005": ("Refusé", "2026-08-21", "Budget non disponible"),
               "DV-2026-0002": ("En discussion", "2026-10-20", "Point prévu avec P. López le 05/11")}
    for r in rows:
        rt = retours.get(r[0], (None, None, None))
        c.execute("INSERT INTO devis (id, date_devis, client_id, debut, duree, validite, statut, objet, commentaire, date_decision, version, date_envoi, "
                  "retour, retour_date, retour_note) VALUES (?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)", r[:10] + (r[1] if r[6] != "Brouillon" else None,) + rt)
        c.executemany("INSERT INTO devis_lignes (devis_id, num, element, code, qte, remplace) VALUES (?,?,?,?,?,?)",
                      [(r[0], i + 1, "Offre" if code.startswith("OF") else "Option", code, q_, rem) for i, (code, q_, rem) in enumerate(r[10])])
        c.execute("INSERT INTO devis_historique (devis_id, date, evenement, detail) VALUES (?,?,?,?)", (r[0], r[1], "Créé", "brouillon"))
        if r[6] != "Brouillon":
            c.execute("INSERT INTO devis_historique (devis_id, date, evenement, detail) VALUES (?,?,?,?)", (r[0], r[1], "Envoyé", "PDF v1"))
        if rt[0]:
            c.execute("INSERT INTO devis_historique (devis_id, date, evenement, detail) VALUES (?,?,?,?)", (r[0], rt[1], f"Retour client : {rt[0]}", rt[2]))
    c.execute("UPDATE affectations SET ref='DV-2026-0001' WHERE client_id='CL-002' AND code='OF-03'")
    c.commit()


# ------------------------------------------------------------------ exercices, budgets, ajustements, archives
def cout_parc_mensuel(a=None):
    a = a or annee()
    cam = couts_assets_mensuels(a)
    assets = assets_df()
    actifs = assets[(assets.statut == "Actif") & assets.parent_id.isna()].set_index("id").qte_parc.fillna(0)
    return {m: float(sum(cam.loc[i, m] * qte for i, qte in actifs.items() if i in cam.index)) for m in range(1, 13)}


def bilan_exercice(a=None):
    a = a or annee()
    e = exercice(a)
    if e is not None and e.statut == "Clôturé":
        return dict(cout_parc=float(e.cout_parc or 0), refacture=float(e.refacture or 0), ecart=float(e.ecart or 0))
    cp = sum(cout_parc_mensuel(a).values())
    l_ = lignes_mensuelles(a)
    ref = float(l_.total.sum()) if len(l_) else 0.0
    return dict(cout_parc=cp, refacture=ref, ecart=ref - cp)


def cloturer_exercice(a):
    if est_cloture(a):
        raise ValueError(f"L'exercice {a} est déjà clôturé.")
    archiver(a, f"ia_platform_avant_cloture_{a}.db", DB_PATH.read_bytes())
    l_ = lignes_mensuelles(a)
    cols = ["annee", "aff_id", "client_id", "client", "entite", "pays", "operation", "element", "code", "libelle", "type", "qte", "debut", "fin"] + [f"m{k}" for k in range(1, 13)]
    rows = []
    for _, r in l_.iterrows():
        if r.total == 0 and r.element != "Ajustement":
            continue
        rows.append((a, r.id, r.client_id, r.client, r.entite, r.pays, r.operation, r.element, r.code, r.libelle, r.type,
                     float(r.qte or 0), iso(r.debut), iso(r.fin)) + tuple(float(r[k]) for k in range(1, 13)))
    trows = []
    for cid in sorted(set(l_.client_id)):
        t = conso_par_type(l_, {cid})
        for typ, v in t.iterrows():
            if v.sum() != 0:
                trows.append((a, cid, typ) + tuple(float(v[k]) for k in range(1, 13)))
    b = bilan_exercice(a)
    bs = bilan_service(a)
    with conn() as c:
        c.execute("UPDATE exercices SET cout_service=?, consomme=?, budget_service=? WHERE annee=?", (bs["cout"], bs["consomme"], bs["budget"], a))
        c.execute("DELETE FROM conso_figee WHERE annee=?", (a,))
        c.execute("DELETE FROM conso_type_figee WHERE annee=?", (a,))
        c.executemany(f"INSERT INTO conso_figee ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", rows)
        c.executemany(f"INSERT INTO conso_type_figee VALUES ({', '.join('?' * 15)})", trows)
        c.execute("UPDATE exercices SET statut='Clôturé', mois_ref=12, date_cloture=?, cout_parc=?, refacture=?, ecart=? WHERE annee=?",
                  (date.today().isoformat(), b["cout_parc"], b["refacture"], b["ecart"], a))
    return dict(lignes=len(rows), **b)


def rouvrir_exercice(a):
    archiver(a, f"ia_platform_avant_reouverture_{a}.db", DB_PATH.read_bytes())
    with conn() as c:
        c.execute("DELETE FROM conso_figee WHERE annee=?", (a,))
        c.execute("DELETE FROM conso_type_figee WHERE annee=?", (a,))
        c.execute("UPDATE exercices SET statut='Ouvert', date_cloture=NULL, cout_parc=NULL, refacture=NULL, ecart=NULL, cout_service=NULL, consomme=NULL "
                  "WHERE annee=?", (a,))


def ouvrir_exercice(n, budgets_depuis=None, evolution_pct=0.0, cles_depuis=None, evolution_cles_pct=0.0):
    """Ouvre l'exercice n ; reprend au choix les budgets clients et les clés du budget de fonctionnement (avec un % d'évolution)."""
    if exercice(n) is not None:
        raise ValueError(f"L'exercice {n} existe déjà.")
    with conn() as c:
        c.execute("INSERT INTO exercices (annee, statut, mois_ref, date_ouverture) VALUES (?,?,?,?)", (n, "Ouvert", 1, date.today().isoformat()))
        if budgets_depuis:
            c.execute("INSERT OR IGNORE INTO budgets SELECT ?, client_id, ROUND(montant * ?, 0) FROM budgets WHERE annee=?",
                      (n, 1 + evolution_pct / 100, budgets_depuis))
        if cles_depuis:
            c.execute("INSERT OR IGNORE INTO budget_cles SELECT ?, cle, type, ROUND(budget * ?, 0), ordre FROM budget_cles WHERE annee=?",
                      (n, 1 + evolution_cles_pct / 100, cles_depuis))
    set_param("annee", n)


# ------------------------------------------------------------------ budget de fonctionnement, réel par clé, régularisation de décembre
CLES_DEFAUT = [("Infrastructure", "assets"), ("Licences", "assets"), ("Support", "indirecte"), ("Maintenance", "indirecte"),
               ("Électricité", "indirecte"), ("Bâtiments", "indirecte"), ("Autre", "indirecte")]
TYPES_CLE = {"assets": "Suivie par les assets", "indirecte": "Indirecte"}
CLES_REGUL = {"prorata": "Au prorata de la consommation", "egal": "À parts égales"}
NATURE_REGUL = "Régularisation"


def cles_budget(a=None):
    """Clés du budget de fonctionnement de l'exercice (créées par défaut, à 0 €, pour un exercice ouvert qui n'en a pas)."""
    a = a or annee()
    df = q("SELECT cle, type, budget, ordre FROM budget_cles WHERE annee=? ORDER BY ordre, cle", (a,))
    if df.empty and not est_cloture(a) and exercice(a) is not None:
        with conn() as c:
            c.executemany("INSERT OR IGNORE INTO budget_cles VALUES (?,?,?,?,?)", [(a, k, t, 0.0, i) for i, (k, t) in enumerate(CLES_DEFAUT)])
        df = q("SELECT cle, type, budget, ordre FROM budget_cles WHERE annee=? ORDER BY ordre, cle", (a,))
    df["budget"] = df.budget.fillna(0.0).astype(float)
    return df


def reel_df(a=None):
    """Tableau clé × mois (1..12) du coût réel saisi ; NaN = pas encore connu."""
    a = a or annee()
    cl = cles_budget(a)
    r = q("SELECT cle, mois, montant FROM reel_mensuel WHERE annee=?", (a,))
    t = pd.DataFrame(float("nan"), index=list(cl.cle), columns=range(1, 13))
    for x in r.itertuples():
        if x.cle in t.index and 1 <= int(x.mois) <= 12:
            t.loc[x.cle, int(x.mois)] = float(x.montant)
    return t


def enregistrer_budget_reel(a, df):
    """df : colonnes cle, type, budget et 1..12 (réel, vide = inconnu). Remplace les clés et le réel de l'exercice."""
    verifier_ouvert(date(a, 1, 1), "La saisie du budget et du réel")
    rows, reels, noms = [], [], set()
    for i, r in enumerate(df.itertuples(index=False)):
        d_ = r._asdict() if hasattr(r, "_asdict") else dict(zip(df.columns, r))
        cle = str(d_.get("cle") or "").strip()
        if not cle:
            continue
        if cle in noms:
            raise ValueError(f"La clé « {cle} » apparaît deux fois.")
        noms.add(cle)
        typ = d_.get("type") if d_.get("type") in TYPES_CLE else "indirecte"
        rows.append((a, cle, typ, float(nombre(d_.get("budget"))), i))
        for m in range(1, 13):
            v = df.iloc[i][m] if m in df.columns else None
            if v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip() != "":
                reels.append((a, cle, m, float(nombre(v))))
    with conn() as c:
        c.execute("DELETE FROM budget_cles WHERE annee=?", (a,))
        c.execute("DELETE FROM reel_mensuel WHERE annee=?", (a,))
        c.executemany("INSERT INTO budget_cles VALUES (?,?,?,?,?)", rows)
        c.executemany("INSERT INTO reel_mensuel VALUES (?,?,?,?)", reels)
    return len(rows), len(reels)


def _num_mois(x):
    s_ = str(x).strip().lower().rstrip(".")
    if s_.isdigit() and 1 <= int(s_) <= 12:
        return int(s_)
    for i, (c_, l_) in enumerate(zip(MOIS, MOIS_LONG), start=1):
        if s_ in (c_.lower().rstrip("."), l_, l_[:3], l_[:4]):
            return i
    return None


def importer_reel(a, df):
    """Import du réel : format large (Clé ; Janv. … Déc.) ou long (Clé ; Mois ; Montant). Une clé inconnue est créée (indirecte)."""
    verifier_ouvert(date(a, 1, 1), "L'import du réel")
    cols = {str(c_).strip().lower(): c_ for c_ in df.columns}
    kcle = cols.get("clé") or cols.get("cle")
    if not kcle:
        raise ValueError("Colonne « Clé » introuvable.")
    vals = []
    if "mois" in cols and "montant" in cols:
        for _, r in df.iterrows():
            m = _num_mois(r[cols["mois"]])
            if m and str(r[kcle]).strip():
                vals.append((str(r[kcle]).strip(), m, float(nombre(r[cols["montant"]]))))
    else:
        mcols = {c_: _num_mois(c_) for c_ in df.columns if _num_mois(c_)}
        for _, r in df.iterrows():
            for c_, m in mcols.items():
                v = r[c_]
                if str(r[kcle]).strip() and v is not None and not (isinstance(v, float) and pd.isna(v)) and str(v).strip():
                    vals.append((str(r[kcle]).strip(), m, float(nombre(v))))
    connues = set(cles_budget(a).cle)
    nouvelles = sorted({k for k, _, _ in vals} - connues)
    with conn() as c:
        n0 = c.execute("SELECT COALESCE(MAX(ordre), 0) FROM budget_cles WHERE annee=?", (a,)).fetchone()[0]
        c.executemany("INSERT OR IGNORE INTO budget_cles VALUES (?,?,?,?,?)", [(a, k, "indirecte", 0.0, n0 + i + 1) for i, k in enumerate(nouvelles)])
        c.executemany("INSERT OR REPLACE INTO reel_mensuel VALUES (?,?,?,?)", [(a, k, m, v) for k, m, v in vals])
    return {"valeurs": len(vals), "clés créées": len(nouvelles)}


def regle_mois_sans_reel():
    """« attendre » (par défaut) : la régularisation attend le réel des 12 mois ; « budget » : un mois sans réel compte pour son budget."""
    return param("regul_mois_sans_reel", "attendre")


def _lignes_hors_regul(a):
    l_ = lignes_mensuelles(a)
    if len(l_):
        l_ = l_[~((l_.element == "Ajustement") & l_.ref.isin([NATURE_REGUL, "Ventilation"]))]
    return l_


def consomme_mensuel(a=None):
    """Montant refacturé chaque mois (offres, options, frais et avoirs ponctuels), hors régularisation."""
    a = a or annee()
    l_ = _lignes_hors_regul(a)
    return {m: float(l_[m].sum()) if len(l_) else 0.0 for m in range(1, 13)}


def bilan_service(a=None):
    """Budget, réel par mois, coût retenu, consommé et écart à régulariser (décomposé : assets / indirectes)."""
    a = a or annee()
    cl = cles_budget(a)
    t = reel_df(a)
    regle = regle_mois_sans_reel()
    mois_reel = [m for m in range(1, 13) if t[m].notna().any()] if len(t) else []
    manquants = [m for m in range(1, 13) if m not in mois_reel]
    bud = dict(zip(cl.cle, cl.budget))
    typ = dict(zip(cl.cle, cl.type))
    par_cle = {}
    for k in cl.cle:
        reel = float(t.loc[k].fillna(0).sum()) if k in t.index else 0.0
        complement = bud[k] / 12 * len(manquants) if regle == "budget" else 0.0
        par_cle[k] = dict(type=typ[k], budget=bud[k], reel=reel, retenu=reel + complement)
    conso = consomme_mensuel(a)
    reel_m = {m: (float(t[m].fillna(0).sum()) if m in mois_reel else None) for m in range(1, 13)}
    cout = sum(v["retenu"] for v in par_cle.values())
    # sans réel pour certains mois (règle « attendre ») : on compare le réel au consommé des mêmes mois (écart provisoire)
    consomme = sum(conso.values()) if (regle == "budget" or not manquants) else sum(conso[m] for m in mois_reel)
    assets = sum(v["retenu"] for v in par_cle.values() if v["type"] == "assets")
    indirect = sum(v["retenu"] for v in par_cle.values() if v["type"] != "assets")
    e = exercice(a)
    if e is not None and e.statut == "Clôturé" and e.get("cout_service") is not None and not pd.isna(e.cout_service):
        cout, consomme = float(e.cout_service), float(e.consomme or 0)
    return dict(budget=float(cl.budget.sum()), par_cle=par_cle, reel_mois=reel_m, conso_mois=conso, mois_reel=mois_reel, manquants=manquants,
                regle=regle, provisoire=bool(manquants), cout=cout, consomme=consomme, ecart=cout - consomme, ecart_assets=assets - consomme, indirect=indirect,
                reel_a_date=sum(v["reel"] for v in par_cle.values()), consomme_a_date=sum(conso[m] for m in mois_reel))


def simuler_regul(a=None, cle="prorata"):
    """Répartition de l'écart entre les clients consommateurs : au prorata de leur consommation ou à parts égales."""
    a = a or annee()
    b = bilan_service(a)
    l_ = _lignes_hors_regul(a)
    par = l_.groupby("client_id").total.sum() if len(l_) else pd.Series(dtype=float)
    par = par[par > 0]
    cli = q("SELECT id, nom, entite FROM clients").set_index("id")
    n = len(par)
    df = pd.DataFrame({"client_id": par.index, "client": [cli.nom.get(i, i) for i in par.index], "entite": [cli.entite.get(i, "") for i in par.index],
                       "conso": par.values})
    tot = float(par.sum()) if n else 0.0
    df["part"] = df.conso / tot if tot else 0.0
    df["prorata"] = df.part * b["ecart"]
    df["egal"] = b["ecart"] / n if n else 0.0
    df["montant"] = df[cle if cle in ("prorata", "egal") else "prorata"]
    df["total"] = df.conso + df.montant
    return df.sort_values("conso", ascending=False).reset_index(drop=True), b


def regul_appliquee(a=None):
    a = a or annee()
    return q("SELECT client_id, montant FROM ajustements WHERE annee=? AND nature=?", (a, NATURE_REGUL))


def controles_cloture(a=None):
    """Liste (état, libellé, détail) : état 1 = ok, 0 = à traiter, 2 = en attente."""
    a = a or annee()
    b = bilan_service(a)
    out = []
    mr = mois_ref(a)
    out.append((1 if mr == 12 else 0, f"Dernier mois réel : {MOIS_LONG[mr - 1]}",
                "" if mr == 12 else "La régularisation se fait quand décembre est le dernier mois réel (Paramètres)."))
    nm = len(b["mois_reel"])
    detail = ""
    if b["manquants"]:
        mq_ = b["manquants"]
        mq = ", ".join(MOIS_LONG[m - 1] for m in mq_) if len(mq_) <= 3 else f"{len(mq_)} mois ({MOIS_LONG[mq_[0] - 1]} → {MOIS_LONG[mq_[-1] - 1]})"
        detail = f"Sans réel : {mq}." + (" Ils comptent pour leur budget." if b["regle"] == "budget" else " La régularisation attend leur saisie.")
    out.append((1 if nm == 12 else (2 if b["regle"] == "budget" else 0), f"Réel saisi pour {nm} mois sur 12", detail))
    if b["budget"] <= 0:
        out.append((0, "Aucun budget de fonctionnement saisi", "Onglet « Budget et réel »."))
    brouillons = q("SELECT COUNT(*) AS n FROM devis WHERE statut='Brouillon' AND substr(debut,1,4)=?", (str(a),)).n.iloc[0]
    out.append((1 if not brouillons else 2, "Aucun devis en brouillon sur l'année" if not brouillons else f"{brouillons} devis en brouillon sur l'année",
                "" if not brouillons else "Sans effet sur les montants : à envoyer ou supprimer."))
    ap = regul_appliquee(a)
    out.append((1 if len(ap) else 2, "Régularisation appliquée" if len(ap) else "Régularisation", f"{eur_txt(float(ap.montant.sum()))} sur {len(ap)} client(s)" if len(ap) else "à appliquer"))
    return out


def budgets_clients_info(a=None, cle=None):
    """Budgets clients (informatifs) : consommé hors régularisation, régularisation (appliquée, sinon simulée), total de l'année."""
    a = a or annee()
    bd = budgets_df(a)
    l_ = _lignes_hors_regul(a)
    conso = l_.groupby("client_id").total.sum() if len(l_) else pd.Series(dtype=float)
    ap = regul_appliquee(a)
    if len(ap):
        reg = ap.groupby("client_id").montant.sum()
        simulee = False
    else:
        e = exercice(a)
        cle = cle or (getattr(e, "cle_regul", None) if e is not None else None) or "prorata"
        sim, _ = simuler_regul(a, cle)
        reg = sim.set_index("client_id").montant
        simulee = True
    bd["conso"] = bd.client_id.map(conso).fillna(0.0)
    bd["regul"] = bd.client_id.map(reg).fillna(0.0)
    bd["total"] = bd.conso + bd.regul
    bd["pct"] = [(t / b_ * 100) if b_ else None for t, b_ in zip(bd.total, bd.budget)]
    bd["etat"] = ["pas de budget" if (p is None or pd.isna(p)) else "au-dessus" if p > 100 else "proche" if p >= 90 else "sous le budget" for p in bd.pct]
    return bd, simulee


def eur_txt(v):
    return f"{v:,.0f} €".replace(",", " ")


def appliquer_regul(a, cle="prorata"):
    """Régularisation unique de décembre : une écriture par client consommateur, au prorata ou à parts égales."""
    if est_cloture(a):
        raise ValueError(f"L'exercice {a} est clôturé.")
    if mois_ref(a) != 12:
        raise ValueError("La régularisation se fait une seule fois, quand décembre est le dernier mois réel (Paramètres).")
    if len(regul_appliquee(a)):
        raise ValueError("La régularisation est déjà appliquée : annulez-la d'abord pour la refaire.")
    df, b = simuler_regul(a, cle)
    if b["manquants"] and b["regle"] != "budget":
        raise ValueError("Réel manquant pour : " + ", ".join(MOIS_LONG[m - 1] for m in b["manquants"])
                         + ". Saisissez-le, ou choisissez « un mois sans réel compte pour son budget ».")
    if df.empty or abs(b["ecart"]) < 0.5:
        raise ValueError("Rien à régulariser (pas d'écart ou aucun client consommateur).")
    lib = f"Régularisation de fin d'année {a} ({CLES_REGUL[cle].lower()})"
    with conn() as c:
        c.executemany("INSERT INTO ajustements (annee, mois, client_id, libelle, montant, nature) VALUES (?,?,?,?,?,?)",
                      [(a, 12, r.client_id, lib, round(float(r.montant), 2), NATURE_REGUL) for r in df.itertuples()])
        c.execute("UPDATE exercices SET cle_regul=?, regul_date=?, regul=? WHERE annee=?", (cle, date.today().isoformat(), float(b["ecart"]), a))
    return len(df), float(b["ecart"])


def annuler_regul(a):
    if est_cloture(a):
        raise ValueError(f"L'exercice {a} est clôturé : rouvrez-le pour annuler la régularisation.")
    with conn() as c:
        c.execute("DELETE FROM ajustements WHERE annee=? AND nature=?", (a, NATURE_REGUL))
        c.execute("UPDATE exercices SET cle_regul=NULL, regul_date=NULL, regul=NULL WHERE annee=?", (a,))


def historique_exercices():
    """Un résumé par exercice : budget, coût retenu, consommé, régularisation."""
    rows = []
    for e in exercices_df().itertuples():
        a = int(e.annee)
        b = bilan_service(a)
        ap = regul_appliquee(a)
        rows.append(dict(annee=a, statut=e.statut, budget=b["budget"], cout=b["cout"], consomme=b["consomme"],
                         regul=float(ap.montant.sum()) if len(ap) else None,
                         cle=CLES_REGUL.get(getattr(e, "cle_regul", None) or "", ""), cloture=e.date_cloture))
    return pd.DataFrame(rows)


def ajustements_client(client_id, a=None):
    a = a or annee()
    return q("SELECT id, mois, libelle, montant, nature FROM ajustements WHERE annee=? AND client_id=? ORDER BY mois, id", (a, client_id))


def supprimer_ajustement(aid):
    r = q("SELECT annee, nature FROM ajustements WHERE id=?", (int(aid),))
    if r.empty:
        return
    if est_cloture(int(r.annee.iloc[0])):
        raise ValueError("L'exercice est clôturé.")
    if r.nature.iloc[0] == NATURE_REGUL:
        raise ValueError("La régularisation s'annule depuis Exercices › Régularisation et clôture.")
    run("DELETE FROM ajustements WHERE id=?", (int(aid),))


def _seed_budget_service(c, a=2026):
    """Démonstration : budget de fonctionnement par clé et réel de janvier à septembre."""
    cles = [("Infrastructure", "assets", 780_000), ("Licences", "assets", 120_000), ("Support", "indirecte", 150_000),
            ("Maintenance", "indirecte", 60_000), ("Électricité", "indirecte", 90_000), ("Bâtiments", "indirecte", 40_000), ("Autre", "indirecte", 10_000)]
    var = [-.03, -.02, -.01, 0, 0, .01, .015, .02, .025]
    c.executemany("INSERT OR REPLACE INTO budget_cles VALUES (?,?,?,?,?)", [(a, k, t, float(b), i) for i, (k, t, b) in enumerate(cles)])
    c.executemany("INSERT OR REPLACE INTO reel_mensuel VALUES (?,?,?,?)",
                  [(a, k, m + 1, round(b / 12 * (0.96 + var[m]), 0)) for k, t, b in cles for m in range(9)])


def appliquer_grille_prix(df, annee_effet):
    """Import d'une grille de prix CSV, avec date d'effet forcée au 1er janvier de l'exercice."""
    df = df.copy()
    df["Date effet"] = f"01/01/{annee_effet}"
    return importer_assets(df)


def budgets_df(a=None):
    a = a or annee()
    cli = q("SELECT id AS client_id, nom AS client, entite, pays, statut FROM clients ORDER BY id")
    b = q("SELECT client_id, montant FROM budgets WHERE annee=?", (a,)).set_index("client_id").montant
    cli["budget"] = cli.client_id.map(b).fillna(0.0)
    return cli


def enregistrer_budgets(a, df):
    with conn() as c:
        c.execute("DELETE FROM budgets WHERE annee=?", (a,))
        c.executemany("INSERT INTO budgets VALUES (?,?,?)", [(a, r.client_id, float(r.budget or 0)) for r in df.itertuples() if float(r.budget or 0) > 0])


def ajustements_df(a=None):
    return q("SELECT a.id, a.mois, a.client_id, c.nom AS client, a.libelle, a.montant, a.nature FROM ajustements a "
             "LEFT JOIN clients c ON c.id=a.client_id WHERE a.annee=? ORDER BY a.mois, a.id", (a or annee(),))


def ajouter_ajustement(a, mois, client_id, libelle, montant, nature="Manuel"):
    if est_cloture(a):
        raise ValueError(f"L'exercice {a} est clôturé.")
    run("INSERT INTO ajustements (annee, mois, client_id, libelle, montant, nature) VALUES (?,?,?,?,?,?)", (a, mois, client_id, libelle, montant, nature))


def archiver(a, nom, contenu):
    run("INSERT INTO archives (annee, nom, date, contenu) VALUES (?,?,?,?)", (a, nom, datetime.now().isoformat(timespec="seconds"), contenu))


def archives_df():
    return q("SELECT id, annee, nom, date, length(contenu) AS taille FROM archives ORDER BY id DESC")


def archive_contenu(aid):
    with conn() as c:
        return c.execute("SELECT contenu FROM archives WHERE id=?", (aid,)).fetchone()[0]


def sauvegarde_fichier():
    """Copie datée de la base dans le dossier archives/ (en plus des archives internes)."""
    dossier = DB_PATH.with_name("archives")
    dossier.mkdir(exist_ok=True)
    cible = dossier / f"ia_platform_{datetime.now():%Y%m%d_%H%M%S}.db"
    cible.write_bytes(DB_PATH.read_bytes())
    return cible


def _archiver_pdf_devis(sauvegarde):
    """Les PDF des devis partent dans les archives (les numéros de devis vont repartir de 1)."""
    if DEVIS_DIR.exists() and any(DEVIS_DIR.iterdir()):
        DEVIS_DIR.rename(sauvegarde.with_name(f"devis_{sauvegarde.stem.split('_', 2)[-1]}"))


def reinitialiser(annee_depart, garder_assets_offres=True, garder_clients=True):
    cible = sauvegarde_fichier()
    _archiver_pdf_devis(cible)
    with conn() as c:
        for t in ("affectations", "devis", "devis_lignes", "devis_historique", "devis_versions", "conso_figee", "conso_type_figee", "ajustements", "budgets", "exercices",
                  "budget_cles", "reel_mensuel"):
            c.execute(f"DELETE FROM {t}")
        if not garder_assets_offres:
            for t in ("assets", "prix_hist", "offres", "composition", "composition_hist"):
                c.execute(f"DELETE FROM {t}")
        if not garder_clients:
            c.execute("DELETE FROM clients")
        if not (garder_assets_offres and garder_clients):
            c.execute("DELETE FROM mesures")
        c.execute("INSERT INTO exercices (annee, statut, mois_ref, date_ouverture) VALUES (?,?,?,?)", (annee_depart, "Ouvert", 1, date.today().isoformat()))
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('annee', ?)", (str(annee_depart),))
        c.execute("INSERT OR REPLACE INTO parametres VALUES ('vide', '1')")
    return cible


def _seed_budgets(c, a):
    """Budgets d'exemple : prévision de l'année arrondie, avec quelques entités sous ou sur-budgétées."""
    c.commit()
    l_ = lignes_mensuelles(a)
    tot = l_.groupby("client_id").total.sum() if len(l_) else pd.Series(dtype=float)
    coef = [1.25, 1.1, 0.92, 1.15, 1.3, 1.05, 0.97, 1.2]
    rows = []
    for i, (cid, v) in enumerate(sorted(tot.items())):
        if v > 0:
            rows.append((a, cid, float(round(v * coef[i % len(coef)] / 5000 + 0.5) * 5000)))
    for cid in ("CL-010", "CL-039", "CL-040", "CL-011"):
        rows.append((a, cid, 60000.0 if cid == "CL-011" else 20000.0))
    c.executemany("INSERT OR REPLACE INTO budgets VALUES (?,?,?)", rows)
    c.commit()
