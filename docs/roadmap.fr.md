🇫🇷 Version française | [🇬🇧 English version](roadmap.md)

---

# Feuille de route

Miroir publié et versionné de la feuille de route de développement du
projet. Le tracker de travail non versionné (mis à jour plus fréquemment
pendant le développement actif) se trouve dans
`docs/work-in-progress/TODO.md`.

Suit l'avancement section par section. Les cases sont mises à jour quand
chaque tâche se termine (cochée quand sa PR est mergée sur `main`).

## Section 1 - Architecture du système d'audit

- [x] DOCS-001 - Concevoir l'architecture du système d'audit et produire `docs/system-design.md` ainsi que les fiches de décision d'architecture
  - Inspecter l'environnement local disponible
  - Identifier les dépôts potentiellement concernés (lecture seule, aucune modification de contenu)
  - Identifier les stacks utilisées
  - Analyser les contraintes du projet
  - Proposer l'architecture globale du système
  - Proposer la structure de données
  - Proposer la taxonomie initiale
  - Proposer le système de scoring
  - Proposer le système de confiance
  - Proposer la stratégie de versioning de la méthodologie
  - Proposer la stratégie de roadmap
  - Proposer l'architecture du dashboard
  - Proposer la liste des outils candidats
  - Identifier les points nécessitant une décision humaine
  - Produire `docs/system-design.md`
  - Produire les fiches de décision d'architecture (`docs/adr/`)
  - Revue humaine des décisions ouvertes, bloquante pour la Section 2 jusqu'à résolution

## Section 2 - Découverte et sélection de la chaîne d'outils

- [x] DOCS-002 - Évaluer et documenter la chaîne d'outils finale (`docs/toolchain.md`)
  - Évaluer les outils candidats par langage/domaine (sécurité, Python, JS/TS, PHP, architecture/dépendances, conteneurs, Git/CI)
  - Valider la disponibilité locale et la licence des outils retenus
  - Documenter la chaîne d'outils finale et les alternatives rejetées (`docs/toolchain.md`)

## Section 3 - Définition finale des catégories, règles, critères, scoring

- [x] DOCS-003 - Geler le Quality Framework v1.0 (`docs/quality-framework.md`)
  - Finaliser la taxonomie (catégories + ajustements justifiés)
  - Définir des critères mesurables par catégorie (objectif, preuve, outils, niveaux, poids, dépendances, confiance, faux positifs)
  - Définir le modèle de scoring hiérarchique (critère -> catégorie -> global)
  - Définir les pénalités critiques, la gestion du N/A, la gestion des données manquantes
  - Geler le **Quality Framework v1.0** (`docs/quality-framework.md`)

## Section 4 - Calibration sur un dépôt pilote

- [x] DOCS-004 - Réaliser les audits de calibration pilotes et corriger le framework en conséquence
  - Sélectionner le dépôt pilote (voir `docs/pilot-audit-geochallenge-tracker.fr.md`)
  - Réaliser un audit complet dessus (passe manuelle)
  - Revoir la pertinence des critères, faux positifs/négatifs, poids, effort
  - Réaliser un second audit pilote sur un dépôt structurellement différent (Laravel/PHP + Vue/JS, voir `docs/pilot-audit-summit-stats.fr.md`) pour vérifier la cohérence inter-dépôts
  - Corriger le framework en fonction des constats
  - Confirmer le Quality Framework v1.0 comme référence pour le premier audit global

## Section 5 - Implémentation du système

- [x] FEAT-001 - Implémenter le modèle de données (Repository, Audit, MethodologyVersion, Category, Criterion, Finding, Score, Evidence, Recommendation, ImprovementTask, RoadmapItem, Snapshot, ToolResult)
- [ ] Implémenter l'orchestration des outils et la normalisation des résultats bruts
  - [x] FEAT-002 - Moteur d'orchestration central (`radar-audit`) : configuration de portfolio, découverte des sous-projets, exclusion des worktrees, protocole `ToolRunner` avec isolation des crashs, seeding de la taxonomie Quality Framework v1.0, résolution Repository/Audit, CLI Typer
  - [ ] Normalisation des résultats bruts par catégorie du Quality Framework (une tâche par catégorie)
    - [x] FEAT-003 - Catégorie 1 - Architecture & conception : dependency-cruiser + pydeps, présence DESIGN.md/ARCHITECTURE.md/ADR, taille des modules via radon + comptage statique de lignes
    - [x] FEAT-004 - Catégorie 2 - Qualité du code : taux de réussite du lint, taux de réussite du type-check, complexité cyclomatique, gate pre-commit, duplication de code
    - [x] FEAT-005 - Catégorie 3 - Tests & fiabilité : taux de réussite des tests unitaires, tests d'intégration, exécution des tests en CI, présence de tests E2E
    - [x] FEAT-006 - Catégorie 4 - Sécurité : vulnérabilités des dépendances (pip-audit/pnpm audit/Composer audit), secrets dans l'historique git (Gitleaks), findings SAST (Semgrep), vulnérabilités des images de conteneurs (Trivy), durcissement des Dockerfiles (Hadolint)
    - [x] FEAT-007 - Catégorie 5 - Maintenabilité : points chauds de complexité (réutilise les runners de complexité de la catégorie 2), code mort / exports inutilisés (Vulture, Knip, PHPMD unusedcode), documentation dans le code (docvet, phpdoc-checker ; JS/TS est en N/A permanent, aucun outil candidat)
    - [ ] DOCS-005 - Catégorie 6 - Performance : différée, non construite (son unique critère, la performance frontend via Lighthouse, est le premier du système à nécessiter que le dépôt audité fasse tourner son propre serveur ; décision enregistrée dans `docs/quality-framework.md` section 4.6, à revisiter après une session de conception dédiée à l'outillage d'exécution live)
    - [x] FEAT-013 - Catégorie 7 - DevOps/CI-CD : présence et santé de la CI (actionlint), parité d'environnement local/prod Traefik, durcissement de la construction des conteneurs (réutilise les preuves Hadolint), automatisation du déploiement
    - [x] FEAT-014 - Catégorie 8 - Documentation : complétude du README (correspondance heuristique d'en-têtes de section), documentation d'architecture (partage les preuves avec 1.2), documentation API (présence FastAPI/Laravel L5-Swagger, N/A sinon)
    - [ ] Catégories 9 à 15 (Observabilité/opérations, API/UX/qualité produit, Gestion des dépendances, Gestion de la configuration, Qualité des données, Expérience développeur, Dette technique) - ID de tâche attribué au démarrage de chacune
- [x] Pipeline de reporting et de publication (voir `docs/work-in-progress/reporting-pipeline-notes.md` pour le détail, les dépendances et l'outillage)
  - [x] FEAT-008 - A. Étendre le contrat de rapport pour rendre les Findings et un modèle explicite à trois états par critère (noté / non applicable avec motif / pas encore audité), en réutilisant le champ `Score.na_reason` existant et le vocabulaire `FindingSeverity` plutôt que d'inventer de nouveaux statuts. Rendu des Evidence/Recommendations différé jusqu'à ce que ces tables aient un producteur (voir B)
  - [x] FEAT-009 - B. Alimenter les enregistrements `Recommendation` à partir des findings, pour que les axes d'amélioration soient des données stockées alimentant le rapport, et non seulement du texte de rapport
  - [x] FEAT-010 - C. Construire un `radar-api` minimal (FastAPI) : endpoints de lecture sur le modèle de données existant, plus des endpoints d'écriture étroits, réservés aux confirmations humaines ; c'est lui qui héberge toutes les données de rapport/finding/recommandation, jamais écrites dans les dépôts audités
  - [x] FEAT-011 - D. Ajouter un badge d'évaluation qualité (badge de type endpoint shields.io) que les dépôts audités peuvent lier depuis leur README, pointant vers la page de rapport hébergée par Radar
  - [x] FEAT-012 - E. Construire le `radar-dashboard` complet (SPA Vue 3 + Vite) : jauges de score en bandes de couleur plates et discrètes (réutilisant la palette à 5 niveaux de `FindingSeverity`, pas un dégradé continu) pour un rendu sérieux et non gadget ; critères N/A et pas encore audités affichés grisés avec le motif visible

## Section 6 - Audit complet du portfolio

Pas encore décomposée en tâches ; ID de tâche attribué au démarrage de la planification de cette section.

- [ ] Exécuter l'audit sur tous les dépôts identifiés
- [ ] Générer les documents globaux (`executive-summary`, `portfolio-scorecard`, `cross-project-analysis`, etc.)
- [ ] Générer les documents par dépôt

## Section 7 - Construction du backlog et de la roadmap

Pas encore décomposée en tâches ; ID de tâche attribué au démarrage de la planification de cette section.

- [ ] Convertir les constats en tâches d'amélioration priorisées
- [ ] Calculer les indicateurs de ROI (impact/effort/réduction de risque, clairement marqués comme des estimations)
- [ ] Publier la roadmap vivante

## Section 8 - Suivi continu et réaudits

Pas encore décomposée en tâches ; ID de tâche attribué au démarrage de la planification de cette section.

- [ ] Réauditer après les travaux d'implémentation
- [ ] Détecter les constats résolus/nouveaux/régressés avec preuves
- [ ] Détecter les divergences entre roadmap et code
- [ ] Suivre les métriques internes du système (stabilité des scores, taux de faux positifs, reproductibilité)
