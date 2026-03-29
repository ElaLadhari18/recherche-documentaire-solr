# README — Système de Recherche Documentaire avec Apache Solr
Projet réalisé dans le cadre du cours Techniques d'Indexation — 1ère année Services Web

---

## Structure du projet

```
projet_solr/
├── main.py            → Interface graphique (Tkinter)
├── solr_client.py     → Communication avec Apache Solr (API REST)
├── extractor.py       → Extraction de texte (PDF, Word, Excel, TXT)
├── historique.py      → Gestion de l'historique des recherches
├── requirements.txt   → Dépendances Python
└── historique.json    → Créé automatiquement au premier lancement
```

---

## Prérequis

- Python 3.8 ou supérieur
- Apache Solr installé et lancé (voir ci-dessous)

---

## Étape 1 — Installer les dépendances Python

```bash
pip install -r requirements.txt
```

---

## Étape 2 — Installer et configurer Apache Solr

### Téléchargement
Téléchargez Solr sur : https://solr.apache.org/downloads.html
Extrayez l'archive dans un dossier (ex: C:\solr ou /opt/solr)

### Démarrage
```bash
# Windows
bin\solr.cmd start

# Linux / macOS
bin/solr start
```

Solr sera accessible sur : http://localhost:8983/solr

### Créer la collection "documents"
```bash
# Windows
bin\solr.cmd create -c documents

# Linux / macOS
bin/solr create -c documents
```

---

## Étape 3 — Lancer l'application

```bash
python main.py
```

---

## Comment utiliser l'application

### Indexer un document
1. Cliquez sur l'onglet "Indexation"
2. Cliquez sur "Parcourir les fichiers..." et sélectionnez vos fichiers
3. Cliquez sur "Indexer les fichiers sélectionnés"
4. Suivez la progression dans le journal

### Rechercher
1. Cliquez sur l'onglet "Recherche"
2. Tapez votre mot-clé dans le champ de saisie
   → Des suggestions apparaissent automatiquement pendant la frappe
3. Optionnel : choisissez un type de fichier dans le menu déroulant
4. Appuyez sur Entrée ou cliquez "Rechercher"
5. Cliquez sur un résultat pour voir l'extrait correspondant à droite

### Historique
L'onglet "Historique" affiche toutes vos recherches passées.
Vous pouvez l'effacer à tout moment.

---

## Fonctionnalités implémentées

- [x] Indexation de fichiers PDF, Word (.docx), Excel (.xlsx) et texte (.txt)
- [x] Recherche full-text dans le contenu et le titre des documents
- [x] Filtrage par type de fichier
- [x] Mise en surbrillance des extraits pertinents (Solr highlighting)
- [x] Autocomplétion (depuis l'historique local + Suggester Solr)
- [x] Prévisualisation de l'extrait du document sélectionné
- [x] Historique des recherches (sauvegardé dans historique.json)
- [x] Interface multi-onglets (Tkinter)
- [x] Opérations longues dans des threads (interface non bloquante)
- [x] Vérification de la connexion Solr au démarrage
