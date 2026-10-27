# IA Platform

Application Streamlit de l'équipe A (centre de coûts) pour refacturer la plateforme IA :
parc d'assets, offres, clients, affectations, devis, collecte des besoins (capacity planning),
consommation mensuelle, dashboard, budgets et exercices.

## Lancer l'application

Prérequis : **Python 3.10 ou plus récent** (https://www.python.org — sous Windows, cocher « Add Python to PATH »).

| Système | Lancement |
|---|---|
| Windows | double-cliquer sur **`lancer.bat`** |
| macOS / Linux | dans un terminal : **`./lancer.sh`** |

Le script :
1. crée l'environnement Python **`.venv`** au premier lancement et y installe les dépendances (`requirements.txt`) ;
2. **active** l'environnement ;
3. exécute **`streamlit run app.py`** : l'application s'ouvre dans le navigateur (http://localhost:8501).

Les lancements suivants sont immédiats ; les dépendances ne sont réinstallées que si `requirements.txt` change.
Autre port sous macOS / Linux : `PORT=8600 ./lancer.sh` (sous Windows : modifier `set "PORT=8501"` dans `lancer.bat`).

À la main (équivalent) :

    python -m venv .venv
    .venv\Scripts\activate          (Windows)   |   source .venv/bin/activate   (macOS / Linux)
    pip install -r requirements.txt
    streamlit run app.py

`requirements-lock.txt` fige les versions exactes testées : `pip install -r requirements-lock.txt` installe à l'identique.

### Reprendre les données d'une version précédente

Copiez votre ancien fichier **`ia_platform.db`** dans le dossier `data/` (ou à la racine du projet : il y est rangé
automatiquement dans `data/` au lancement, de même qu'un ancien dossier `archives/`). Les tables manquantes sont ajoutées
sans toucher aux données.

## Arborescence

```
IA_Platform/
├── app.py                      point d'entrée : thème, navigation par sections, barre latérale
├── lancer.bat                  lancement Windows (crée / active .venv puis streamlit run app.py)
├── lancer.sh                   lancement macOS / Linux
├── requirements.txt            dépendances
├── requirements-lock.txt       versions exactes testées
├── .streamlit/
│   └── config.toml             thème (couleurs, barre latérale) et réglages Streamlit
├── data/
│   ├── modeles/                modèles CSV d'import (assets, clients, mesures de supervision)
│   ├── ia_platform.db          base SQLite (créée au premier lancement)
│   ├── devis/<année>/          devis envoyés (PDF), un fichier par version
│   └── archives/               sauvegardes datées de la base (clôtures, remises à zéro)
└── ia_platform/                le code
    ├── config.py               chemins (base, modèles, archives)
    ├── core/                   logique métier, sans interface
    │   ├── logic.py            base de données et calculs (coûts, affectations, devis, capacité, exercices)
    │   └── planning.py         campagnes de collecte des besoins, modèles Excel, import, export
    ├── exports/                fichiers produits
    │   ├── rapport_excel.py    rapport Excel (synthèse, clients, consommation, relevés)
    │   └── devis_pdf.py        devis en PDF et en image
    ├── ui/                     interface commune
    │   ├── theme.py            styles, en-tête de page, cartes
    │   ├── commun.py           formats, filtres, import CSV, bouton de rapport
    │   ├── navigation.py       registre des pages (liens entre écrans)
    │   └── static/             logo
    └── ecrans/                 un module par écran
        ├── demarrage.py        premier lancement (base vide ou démonstration)
        ├── accueil.py
        ├── assets.py · clients.py · offres.py                       (Référentiel)
        ├── affectations.py · devis.py · capacity_planning.py        (Activité)
        ├── consommation.py · dashboard.py · rapports.py             (Suivi)
        └── exercices.py · parametres.py                             (Administration)
```

Règle de dépendance : `ecrans` → `ui`, `core`, `exports` ; `exports` → `core` ; `core` ne dépend d'aucune interface.
Pour ajouter un écran : créer `ia_platform/ecrans/mon_ecran.py` avec une fonction `page()`, puis l'ajouter à `SECTIONS` dans `app.py`.

## Écrans

| Écran | Rôle |
|---|---|
| Assets | Nouvel asset : un seul formulaire ; avec le type « Instance cloud », capacités lues dans le nom du profil (ex. IBM bx3d-128x640) et refacturation à l'instance entière ou à la part par vCPU / GPU (part créée automatiquement). Catalogue (prix, unité, coût d'une unité / mois, quantité du parc, coût total du parc / mois, capacités vCPU / RAM / GPU, région, refacturation), filtre par type, changement de prix daté, historique, import CSV |
| Clients | Liste modifiable, résumés par pays / entité, nouveau client, import CSV |
| Offres | Catalogue en cartes (coût, répartition par type d'asset, ressources, clients). Éditeur : composition avec quantités, ajout d'asset par type, coût avant / après ; une modification s'applique à partir d'un mois (le passé ne change pas, historique des compositions). Comparateur de 2 à 4 offres (export Excel, « Créer un devis »). Retrait d'une offre : les clients la gardent, migrent vers une autre offre à une date, ou arrêtent. Composants « socle » ou « retirables » ; nombre de clients ayant personnalisé l'offre |
| Affectations | Liste des clients cliquable → fiche : offres et options en cours avec dates de début / fin, frais et avoirs ponctuels (et régularisation de décembre, en lecture), frise de l'année. Ajouter plusieurs offres et options en une fois (panier), changer d'offre / remplacer une option (l'ancienne s'arrête le mois précédent), arrêter une ligne ou toute la solution (client → Inactif), modifier dates et quantité, supprimer une erreur de saisie |
| Devis | Documents d'information : ils ne créent ni ne modifient aucune affectation. Liste avec indicateurs (en attente, à relancer, brouillons, retours clients), filtres Brouillon / Envoyé / Expiré (calculé), colonne « Retour client ». Création en 3 étapes (lignes « en plus » ou « remplace », pour montrer le coût avant / après). Envoyer : le PDF est enregistré dans `data/devis/<année>/` et un brouillon de mail (.eml, PDF en pièce jointe) se télécharge. Nouvelle version (les anciennes restent téléchargeables), duplication, note de suivi sans effet sur les données (en discussion, accepté, refusé) |
| Capacity planning | Collecte des besoins des métiers (entités) par campagne : période et découpage (mois, trimestre, semestre, année), ressources proposées, date limite. Suivi des réponses (en attente, en cours de saisie, reçu, rien à signaler), contacts, relance par email. Saisie par métier : une ligne par projet et ressource, quantités par période, priorité, confiance, coût estimé. Modèles Excel à envoyer (listes déroulantes), import des fichiers reçus, export Excel complet |
| Consommation | Tableau client × mois, filtres pays / entité / client, par pays, par type d'asset, export Excel |
| Dashboard | 4 onglets avec filtres pays / entité / client. Vue d'ensemble (indicateurs, consommation mensuelle par type d'asset, « À surveiller »). Par asset (GPU, Licence, Service… : montant, tendance, occupation du parc par asset, capacité inutilisée, clients qui consomment). Capacité (pools vCPU / GPU : capacité, alloué, réservé par les devis, libre, utilisation mesurée, projection 12 mois, recommandations, placement par instance, alloué vs utilisé par client, import des mesures de supervision). Par client (carte de chaleur client × mois, prévision / budget, clic → Affectations). Budget et couverture (coût du parc vs refacturé, écart à ventiler, budgets par entité, coût non couvert par type) |
| Rapports Excel | Bouton « Générer le rapport Excel » : synthèse, clients, consommation par mois, par type, détail, relevés |
| Exercices | 4 onglets. **Budget et réel** : budget de fonctionnement par clé (infrastructure, licences = suivies par les assets ; support, maintenance, électricité, bâtiments, autre = indirectes), réel mois par mois (saisie ou import Excel / CSV), suivi budget / consommé / réel / écart. **Régularisation et clôture** : une seule régularisation, en décembre, au prorata de la consommation ou à parts égales (les deux affichées pour comparer), origine de l'écart par clé, contrôles, clôture. **Budgets clients (info)** : sans effet sur les calculs. **Exercices et archives** : historique, archives, ouverture de l'année suivante, zone sensible (réouverture, réinitialisation) |
| Accueil | Indicateurs clés, points à traiter (devis à relancer, campagnes en cours, capacité pleine, budgets dépassés), accès rapide à chaque écran |
| Paramètres | Dernier mois réel de l'exercice, listes (types, entités, pays) |

## Partager l'application avec l'équipe

Lancer sur un serveur interne : `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`,
puis donner l'adresse http://nom-du-serveur:8501. Pour plusieurs utilisateurs simultanés et des droits
d'accès, prévoir une authentification (proxy de l'entreprise) et, à terme, PostgreSQL à la place de SQLite.

## Exercices et historique

- L'exercice affiché se choisit dans la barre latérale ; toutes les pages s'y adaptent.
- **Clôturer** un exercice enregistre la consommation de chaque client mois par mois (tables `conso_figee`, `conso_type_figee`) :
  ces montants ne sont plus recalculés, même si les prix ou les offres changent ensuite. Une copie de la base et le rapport
  Excel de l'année et le détail de la régularisation sont archivés automatiquement.
- Une écriture datée dans un exercice clôturé (affectation, prix, devis) est refusée.
- **Budget de fonctionnement** : fixé en début d'année par clé. Le consommé vient chaque mois des affectations ; le réel par clé
  arrive plus tard (par exemple en octobre pour janvier → septembre), puis mois par mois. Pas de prévision, pas de report d'écart.
- **Régularisation** (une seule fois, quand décembre est le dernier mois réel) : écart = coût réel du service − consommé de l'année
  (hors régularisation). Il est réparti entre les clients consommateurs au prorata de leur consommation ou à parts égales, par une
  ligne « Régularisation de fin d'année » par client en décembre. Après régularisation, refacturé = coût réel : le centre de coûts
  finit l'année à zéro. Règle pour un mois sans réel : la régularisation attend son réel (par défaut) ou il compte pour 1/12 du budget.
  La régularisation peut être annulée tant que l'exercice n'est pas clôturé.
- **Frais et avoirs ponctuels** : depuis la fiche client (Affectations), montant facturé une fois le mois choisi.
- **Ouvrir l'exercice suivant** garde clients, assets, offres et affectations en cours, peut reprendre les clés du budget et les budgets clients (avec un % d'évolution)
  et appliquer une nouvelle grille de prix CSV au 1er janvier.
- **Réinitialiser** sauvegarde d'abord la base dans le dossier `data/archives/`.

## Démarrer avec vos données (sans les données de test)

Au **premier lancement** (aucune base `data/ia_platform.db`), l'application propose :
- **Commencer avec une base vide** : aucun asset, offre, client ni affectation ; vous choisissez l'exercice et le dernier mois réel.
  L'accueil affiche ensuite les « Premiers pas » : 1. Assets → 2. Offres → 3. Clients → 4. Affectations.
- **Charger les données de démonstration** : données fictives pour découvrir l'application.

Les fichiers du dossier `data/modeles/` ne sont **plus chargés automatiquement** : ce sont des modèles pour l'import CSV
(Assets › Importer un CSV, Clients › Importer un CSV, Dashboard › Capacité › Mesures).

Pour passer de la démonstration à vos données : **Paramètres › Données › Tout effacer** (une copie de la base est d'abord enregistrée dans
le dossier `data/archives`). Pour revenir à l'écran de choix, vous pouvez aussi arrêter l'application et supprimer (ou renommer) `data/ia_platform.db`.
Une base existante (créée avec une version précédente) est conservée telle quelle.

## Instances cloud et capacité

- **Coût total du parc** = coût d'une unité × quantité du parc : ce que l'équipe A paie, vendu ou non. Comparé au refacturé, il donne la couverture,
  la capacité inutilisée et l'écart à ventiler en fin d'année. Une « part » d'instance n'a pas de coût propre (il est porté par l'instance).
- **Instance cloud à la part** : l'asset « part » (vCPU ou GPU) est créé et tenu à jour automatiquement : prix = prix de l'instance ÷ nombre de vCPU
  (ou de GPU), parc = parts × instances ; un changement de prix de l'instance est reporté sur la part à la même date d'effet.
- **Garde-fou** : impossible d'allouer (affectation, remplacement, acceptation de devis) plus d'unités qu'il n'y en a dans le parc pour une part ou une
  instance vendue entière.
- **Mesures** : `data/modeles/Import_Mesures_exemple.csv` montre le format (Date ; Asset ; Client ; CPU moyen % ; CPU max % ; GPU moyen %), à alimenter par un
  export quotidien de la supervision (IBM Cloud Monitoring, Prometheus, NVIDIA DCGM…). Import dans Dashboard › Capacité › Mesures et seuils.

## Capacity planning : collecte des besoins

- **Campagne** : une période (ex. janv. → déc. 2027), un découpage, une date limite et une liste de ressources (reprise du catalogue des assets ;
  l'« asset lié » sert au coût estimé). Une nouvelle campagne reprend les métiers, ressources et contacts de la précédente.
- **Métier** = une entité (R&D, Risques…). Chaque besoin peut être rattaché à un client existant de l'entité ou à un nouveau projet.
  Les quantités sont **en plus** de ce qui est déjà alloué.
- **Modèle Excel** : un fichier par métier, pré-rempli, avec listes déroulantes (ressource, client, priorité, confiance) ; le fichier renvoyé
  est reconnu automatiquement à l'import (il remplace les besoins du métier, qui passe à « Reçu »). Les erreurs sont listées ligne par ligne.
- **Export Excel** : paramètres, suivi des réponses, besoins (une colonne par période, total en formule) et une feuille « une ligne par besoin et
  par période » prête pour un tableau croisé dynamique.
- Dès qu'un besoin est saisi, la période et le découpage sont verrouillés ; une campagne clôturée passe en consultation seule.

## Devis : document d'information

- **Brouillon** : création, modification, suppression ; le PDF porte le filigrane « BROUILLON ».
- **Envoyé** : « Envoyer le devis » enregistre le PDF dans `data/devis/<année>/<n°>_v<version>_<client>.pdf` et prépare un
  **brouillon de mail** (.eml) : destinataire (e-mail du client), objet, texte et PDF en pièce jointe. Ouvrez le fichier .eml :
  Outlook l'affiche comme un brouillon prêt à envoyer (Apple Mail et Thunderbird l'ouvrent aussi).
- **Expiré** : calculé quand la validité est dépassée ; « Nouvelle version » repasse en brouillon avec la version suivante.
- **Note de suivi** : en discussion, accepté ou refusé, avec une date et une note (n° de bon de commande, motif…). Elle sert au suivi
  commercial seulement : les offres se mettent en place dans **Affectations**.
- Les devis ne réservent pas de capacité. Les anciens devis « Accepté » ou « Refusé » sont convertis en « Envoyé » avec la note de suivi correspondante.
- « Tout effacer » et « Réinitialiser » rangent le dossier `data/devis` dans `data/archives/`.

## Personnalisation d'une offre par client

- **Offres** : chaque composant est soit dans le **socle** (🔒, ne se retire pas), soit **retirable** (interrupteur « Retirable » dans l'éditeur).
  Le panneau de coût affiche le socle (minimum facturé) et la part retirable ; la liste des clients montre qui a personnalisé l'offre.
- **Affectations** : « ⚙️ Personnaliser » sur une ligne d'offre : quantité gardée de chaque composant retirable (de 0 à la quantité de l'offre),
  à partir d'un mois. Le prix de la ligne baisse exactement du coût des composants retirés (pas de remise). Si la ligne a commencé avant,
  elle s'arrête le mois précédent et une nouvelle ligne identique porte la personnalisation : le passé ne change pas.
  « Revenir à l'offre standard » annule les retraits à partir d'un mois.
- Seule la ligne du client change : l'offre et les autres clients ne bougent pas. Si l'offre évolue (date d'effet), le client suit la nouvelle
  composition et garde ses retraits ; un retrait sur un composant qui n'est plus dans l'offre n'a plus d'effet.
- Avec une quantité > 1 (ex. IA Standard × 2), les retraits s'appliquent à chaque exemplaire.
- Les composants retirés sont rendus au parc (capacité) et disparaissent de la consommation par type et par asset.
- **Devis** : le menu ⚙️ d'une ligne d'offre permet la même personnalisation ; le PDF indique « (personnalisée) » et ce qui est retiré.
