# IA Platform — application Streamlit

Gestion des assets (prix + unité de facturation), des offres, des clients (nom, entité, pays),
des affectations (offre, options, changement d'offre), suivi de la consommation mensuelle et dashboard.
Les données sont stockées dans `ia_platform.db` (SQLite), créé automatiquement au premier lancement
avec les données d'exemple du dossier `data/` (34 assets, 40 clients, 5 offres).

## Installer et lancer

L'application s'installe dans un **environnement virtuel** (dossier `.venv`) : ses bibliothèques sont isolées
du reste de l'ordinateur, sans conflit avec d'autres projets Python, et sans droits administrateur.

### Windows
1. Installer Python 3.10 ou plus récent (https://www.python.org — cocher « Add Python to PATH »).
2. Double-cliquer sur **`installer.bat`** (une seule fois : crée `.venv` et installe les bibliothèques).
3. Double-cliquer sur **`lancer.bat`** : l'application s'ouvre dans le navigateur (http://localhost:8501).

### macOS / Linux
    ./installer.sh
    ./lancer.sh

### À la main (équivalent)
    python -m venv .venv
    .venv\Scripts\activate          (Windows)   |   source .venv/bin/activate   (macOS / Linux)
    pip install -r requirements.txt
    streamlit run app.py

`requirements-lock.txt` fige les versions exactes testées : `pip install -r requirements-lock.txt` installe à l'identique.

Mise à jour de l'application : remplacer les fichiers `.py`, puis relancer `installer.bat` si `requirements.txt` a changé.
Le dossier `.venv`, la base `ia_platform.db` et le dossier `archives/` ne sont pas à copier d'une machine à l'autre
(sauf la base, si vous voulez transférer les données).

## Écrans

| Écran | Rôle |
|---|---|
| Assets | Nouvel asset (formulaire), catalogue (prix, unité, coût d'une unité / mois, quantité du parc, coût total du parc / mois, capacités vCPU / RAM / GPU, région, refacturation), filtre par type, nouvelle instance cloud (capacités lues dans le nom du profil, ex. IBM bx3d-128x640 ; refacturation à l'instance entière ou à la part par vCPU / GPU avec création automatique de la part), changement de prix daté, historique, import CSV |
| Clients | Liste modifiable, résumés par pays / entité, nouveau client, import CSV |
| Offres | Catalogue en cartes (coût, répartition par type d'asset, ressources, clients). Éditeur : composition avec quantités, ajout d'asset par type, coût avant / après ; une modification s'applique à partir d'un mois (le passé ne change pas, historique des compositions). Comparateur de 2 à 4 offres (export Excel, « Créer un devis »). Retrait d'une offre : les clients la gardent, migrent vers une autre offre à une date, ou arrêtent |
| Affectations | Liste des clients cliquable → fiche : offres et options en cours avec dates de début / fin, frise de l'année. Ajouter plusieurs offres et options en une fois (panier), changer d'offre / remplacer une option (l'ancienne s'arrête le mois précédent), arrêter une ligne ou toute la solution (client → Inactif), modifier dates et quantité, supprimer une erreur de saisie |
| Devis | Liste avec indicateurs (en attente, à relancer, brouillons, taux d'acceptation), filtres par statut (Expiré calculé automatiquement). Création en 3 étapes avec le même catalogue que les Affectations ; chaque ligne vient « en plus » ou « remplace » une ligne actuelle du client. Fiche : aperçu du document, PDF / image, suivi, effet sur le coût et le budget. Accepter (remplacements, lignes créées, fin à l'échéance ou sans fin, bon de commande, ajustement du budget), refuser avec motif, nouvelle version (les anciennes restent téléchargeables) |
| Consommation | Tableau client × mois, filtres pays / entité / client, par pays, par type d'asset, export Excel |
| Dashboard | 4 onglets avec filtres pays / entité / client. Vue d'ensemble (indicateurs, consommation mensuelle par type d'asset, « À surveiller »). Par asset (GPU, Licence, Service… : montant, tendance, occupation du parc par asset, capacité inutilisée, clients qui consomment). Capacité (pools vCPU / GPU : capacité, alloué, réservé par les devis, libre, utilisation mesurée, projection 12 mois, recommandations, placement par instance, alloué vs utilisé par client, import des mesures de supervision). Par client (carte de chaleur client × mois, prévision / budget, clic → Affectations). Budget et couverture (coût du parc vs refacturé, écart à ventiler, budgets par entité, coût non couvert par type) |
| Rapports Excel | Bouton « Générer le rapport Excel » : synthèse, clients, consommation par mois, par type, détail, relevés |
| Exercices | Un exercice par année : ventilation de l'écart, clôture (montants figés), réouverture, ouverture de l'année suivante (budgets repris, nouvelle grille de prix), budgets par client, ajustements, archives, réinitialisation |
| Paramètres | Dernier mois réel de l'exercice, listes (types, entités, pays) |

## Fichiers

- `app.py` : les écrans.
- `affectations_ui.py` : l'écran Affectations (liste des clients, fiche, ajout, remplacement, arrêt).
- `devis_ui.py` : l'écran Devis (liste, création en 3 étapes, fiche, acceptation et refus).
- `offres_ui.py` : l'écran Offres (catalogue, éditeur avec date d'effet, comparateur, retrait).
- `dashboard_ui.py` : le Dashboard (vue d'ensemble, par asset, capacité, par client, budget et couverture).
- `devis_pdf.py` : mise en page du devis en PDF (reportlab) et en image PNG.
- `rapport.py` : fabrication du rapport Excel (openpyxl), avec totaux en formules, graphique et relevés par client.
- `logic.py` : base de données et calculs (coût mensuel des assets avec historique des prix,
  coût des offres, montants mensuels des affectations, consommation par client et par type).
- `data/Import_Assets.csv`, `data/Import_Clients.csv` : données d'exemple, aussi utilisables comme modèles d'import.

## Partager l'application avec l'équipe

Lancer sur un serveur interne : `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`,
puis donner l'adresse http://nom-du-serveur:8501. Pour plusieurs utilisateurs simultanés et des droits
d'accès, prévoir une authentification (proxy de l'entreprise) et, à terme, PostgreSQL à la place de SQLite.

## Exercices et historique

- L'exercice affiché se choisit dans la barre latérale ; toutes les pages s'y adaptent.
- **Clôturer** un exercice enregistre la consommation de chaque client mois par mois (tables `conso_figee`, `conso_type_figee`) :
  ces montants ne sont plus recalculés, même si les prix ou les offres changent ensuite. Une copie de la base et le rapport
  Excel de l'année sont archivés automatiquement (onglet Archives).
- Une écriture datée dans un exercice clôturé (affectation, prix, devis) est refusée.
- **Ouvrir l'exercice suivant** garde clients, assets, offres et affectations en cours, peut reprendre les budgets (avec un % d'évolution)
  et appliquer une nouvelle grille de prix CSV au 1er janvier.
- **Réinitialiser** sauvegarde d'abord la base dans le dossier `archives/`.

## Démarrer avec vos données (sans les données de test)

Au **premier lancement** (aucune base `ia_platform.db`), l'application propose :
- **Commencer avec une base vide** : aucun asset, offre, client ni affectation ; vous choisissez l'exercice et le dernier mois réel.
  L'accueil affiche ensuite les « Premiers pas » : 1. Assets → 2. Offres → 3. Clients → 4. Affectations.
- **Charger les données de démonstration** : données fictives pour découvrir l'application.

Les fichiers du dossier `data/` ne sont **plus chargés automatiquement** : ce sont des modèles pour l'import CSV
(Assets › Importer un CSV, Clients › Importer un CSV, Dashboard › Capacité › Mesures).

Pour passer de la démonstration à vos données : **Paramètres › Données › Tout effacer** (une copie de la base est d'abord enregistrée dans
le dossier `archives`). Pour revenir à l'écran de choix, vous pouvez aussi arrêter l'application et supprimer (ou renommer) `ia_platform.db`.
Une base existante (créée avec une version précédente) est conservée telle quelle.

## Instances cloud et capacité

- **Coût total du parc** = coût d'une unité × quantité du parc : ce que l'équipe A paie, vendu ou non. Comparé au refacturé, il donne la couverture,
  la capacité inutilisée et l'écart à ventiler en fin d'année. Une « part » d'instance n'a pas de coût propre (il est porté par l'instance).
- **Instance cloud à la part** : l'asset « part » (vCPU ou GPU) est créé et tenu à jour automatiquement : prix = prix de l'instance ÷ nombre de vCPU
  (ou de GPU), parc = parts × instances ; un changement de prix de l'instance est reporté sur la part à la même date d'effet.
- **Garde-fou** : impossible d'allouer (affectation, remplacement, acceptation de devis) plus d'unités qu'il n'y en a dans le parc pour une part ou une
  instance vendue entière.
- **Mesures** : `data/Import_Mesures_exemple.csv` montre le format (Date ; Asset ; Client ; CPU moyen % ; CPU max % ; GPU moyen %), à alimenter par un
  export quotidien de la supervision (IBM Cloud Monitoring, Prometheus, NVIDIA DCGM…). Import dans Dashboard › Capacité › Mesures et seuils.
