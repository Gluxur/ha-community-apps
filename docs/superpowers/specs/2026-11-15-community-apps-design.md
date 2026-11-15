# Community Apps — design

Date : 2026-11-15 · Auteur : Gluxur · Statut : approuvé le 2026-11-15

## Intention

Le Marketplace intégré à Home Assistant 2026.11 (ex-HACS) couvre intégrations, cartes,
thèmes et macros, mais **pas les apps** (ex add-ons). Pour une app tierce, il faut connaître
l'URL de son dépôt et l'ajouter à la main dans le store du Supervisor. Il n'existe aucun
catalogue central.

Community Apps comble ce trou : un **catalogue communautaire d'apps tierces**, alimenté par
les auteurs via pull request comme `hacs/default`, **relu par un humain**, assisté d'une
GitHub Action qui signale ce que chaque app peut faire (permissions, communications vers
l'extérieur). Une **page dans Home Assistant** permet de parcourir le catalogue et d'ajouter
un dépôt au Supervisor en un clic.

Horizon : un format de catalogue assez propre pour pouvoir, un jour, être repris par Home
Assistant, comme HACS l'a été avec le Marketplace.

## Objectifs

- Catalogue public, ouvert aux soumissions de la communauté par PR.
- Entrée dans le catalogue soumise à une **relecture humaine**, appuyée par un rapport
  automatique : permissions sensibles, domaines contactés, provenance de l'image.
- **Rescan automatique à chaque nouvelle version** des apps acceptées ; si les signaux
  changent, l'app passe en `flagged` en attendant une nouvelle relecture.
- Intégration HA avec panneau latéral : recherche, fiche détaillée (permissions, risque,
  domaines, statut de relecture), ajout du dépôt en 1 clic, renvoi vers la page native de
  l'app pour l'installer.
- **Réparation HA** (repair issue) quand une app installée est `flagged` ou retirée.
- Intégration distribuée par le Marketplace.

## Non-objectifs

- Installer, mettre à jour ou désinstaller des apps : c'est le store natif du Supervisor.
- Relecture de chaque version ou miroir figé des dépôts (décision : relecture **à l'entrée
  seulement**, rescan automatique ensuite).
- Dépôts privés : c'est le rôle de `github_private_apps`.
- Home Assistant Container / Core : pas de Supervisor, pas d'apps. L'intégration refuse de
  s'installer.
- Site web vitrine public : possible plus tard, hors v1.

## Anti-objectifs (échec même si ça marche)

- **Paraître officiel** Home Assistant / Nabu Casa (nom, logo, textes).
- **Fausse sécurité** : ne jamais écrire « sûr », « vérifié », « sans risque ». On affiche
  « relu à l'entrée le JJ/MM/AAAA » et des signaux. Une app malveillante peut passer le scan.
- Ajouter un dépôt au Supervisor sans action explicite d'un administrateur.
- Obliger l'utilisateur à se connecter à GitHub pour parcourir le catalogue.

## Contraintes

- Le Supervisor installe et met à jour depuis l'état **courant** du dépôt de l'auteur ; le
  catalogue référence des dépôts, pas des versions. Une mise à jour arrive chez
  l'utilisateur avant le rescan. Assumé, documenté dans le README.
- Toute app a accès à Internet par défaut (pas de filtrage de sortie dans le Supervisor) :
  le scan donne des **signaux**, pas une preuve.
- Analyse dynamique limitée : premier démarrage, sans configuration, hors Supervisor.
  Beaucoup d'apps (bases `bashio`/s6) échoueront ou se comporteront différemment ; « n'a pas
  démarré » est un résultat normal, pas un rejet.
- Accès Supervisor depuis l'intégration : API REST directe via `SUPERVISOR` /
  `SUPERVISOR_TOKEN`, comme `github_private_apps/supervisor.py`.
- Les URLs de dépôt ajoutées au Supervisor sont l'URL GitHub publique telle quelle, pour que
  les slugs soient identiques à un ajout manuel.

## Approches envisagées

Côté catalogue, une seule voie raisonnable : dépôt GitHub + PR + Action + `catalog.json`
publié sur GitHub Pages (modèle `hacs/default`).

Côté HA :

| Approche | Pour | Contre |
|---|---|---|
| **A. Intégration + panneau latéral** (retenue) | Distribution 1 clic par le Marketplace ; connaît les apps installées → réparations HA ; réutilise `supervisor.py` | Frontend JS à écrire |
| B. App avec page Ingress | Stack web libre, panneau natif | Œuf et poule (son dépôt à ajouter à la main) ; notifications seulement, pas de réparations |
| C. Site web seul + liens 1 clic | Le moins cher | Pas dans HA, pas d'alertes ; ne répond pas à la demande |
| Greffe sur `github_private_apps` | Code existant | But différent ; imposerait une connexion GitHub |

Choix de Gluxur : **A**.

## Décisions

### Prises par Gluxur

- Catalogue communautaire alimenté par PR, comme `hacs/default`.
- Relecture humaine + GitHub Action qui détecte les communications vers l'extérieur.
- Relecture à l'entrée seulement, rescan à chaque version.
- Approche A.
- **Amorçage au lancement** : exception à la règle « seul l'auteur soumet ». Gluxur ajoute
  lui-même une dizaine de dépôts connus, relus par lui, marqués `added_by: catalog` (affiché
  « ajouté par le catalogue » dans le panneau). Retrait sur simple demande de l'auteur
  (issue), sans discussion. Hors lancement, la règle normale s'applique.
- Nouveau répertoire, nouveau dépôt **public** GitHub sous **Gluxur**, commits signés
  `Gluxur <5436326+Gluxur@users.noreply.github.com>`.

### Proposées par Claude (à corriger si besoin)

- **Nom** : dépôt `Gluxur/ha-community-apps`, domaine `community_apps`, titre « Community
  Apps ». Neutre, ne revendique pas « Home Assistant » comme marque.
- **Un seul dépôt** pour le catalogue et l'intégration (tu as demandé « un nouveau repo ») :
  `custom_components/community_apps/` + `hacs.json` à la racine (exigé par le Marketplace),
  catalogue dans `catalog/`. Workflows séparés par filtres de chemins. Si un jour HA reprend
  le catalogue, il se détache facilement dans son propre dépôt.
- **Qui soumet** : seul le propriétaire ou un mainteneur du dépôt d'apps, comme `hacs/default`
  (pas d'ajout du dépôt de quelqu'un d'autre sans son accord).
- **Relecteurs** : Gluxur seul au départ (`CODEOWNERS` sur `catalog/`), d'autres ajoutables.
- Langue : code, README, catalogue en anglais ; traductions de l'intégration `en` + `fr`.

## Conception

### 1. Format du catalogue

Un fichier par dépôt pour éviter les conflits de merge :
`catalog/repositories/<owner>/<repo>.yaml`

Soumis par l'auteur (PR) :
```yaml
repository: owner/repo
```

Complété par l'automatisation et le relecteur (jamais par l'auteur) :
```yaml
added_by: author        # author | catalog (amorçage au lancement)
status: approved        # pending | approved | flagged | removed
reviewed:
  by: Gluxur
  at: 2026-11-15
  commit: <sha relu>
  notes: "…"            # optionnel
scan:                   # dernier scan, écrit par l'Action
  commit: <sha>
  at: 2026-11-16T03:00Z
  apps:
    - slug: example
      name: Example
      version: 1.2.0
      arch: [aarch64, amd64]
      image: prebuilt | source     # image: dans config.yaml ou build depuis Dockerfile
      permissions: [host_network, docker_api]
      risk: high                   # low | medium | high, calculé par l'Action
      domains: [api.example.com]   # statique ∪ dynamique
      dynamic: started | failed | skipped
removed_reason: "…"     # si status: removed
```

`catalog.json` (généré, publié sur GitHub Pages) agrège toutes les entrées `approved` et
`flagged` (+ `removed` sous forme minimale `repository`/`status`/`removed_reason`, pour que
les clients puissent alerter), avec un champ `schema_version: 1` et `generated_at`.

### 2. Scan (GitHub Action)

Déclenché sur PR touchant `catalog/` et chaque nuit sur toutes les entrées `approved`.

- **Statique**, au commit visé :
  - `repository.yaml|yml|json` présent ; chaque `config.yaml|yml|json` valide.
  - Permissions sensibles : `host_network`, `privileged`, `full_access`, `docker_api`,
    `host_pid`, `host_dbus`, `apparmor: false`, `hassio_role: manager|admin`, `devices`,
    `uart`, `usb`, `gpio`, `kernel_modules`, mappings de `/config`/`/share`/`/ssl` en écriture.
  - `image:` toute faite (source non vérifiable) vs build depuis le Dockerfile.
  - Dockerfile : `curl`/`wget`/`ADD` d'URLs distantes.
  - Domaines et URLs codés en dur dans le code (hors docs, tests, `*.md`).
- **Dynamique**, amd64, durée limitée (~3 min par app) : lancer l'image sur un réseau Docker
  isolé dont le DNS est un résolveur qui journalise, plus une capture des connexions
  sortantes ; résultat = liste des domaines/IP contactés. Pas de secrets dans le job.
- **Risque** : règle simple et documentée, par ex. `high` si `full_access`, `privileged`,
  `docker_api`, `host_pid` ou `hassio_role` ≥ manager ; `medium` si `host_network`, image
  toute faite, ou accès matériel ; sinon `low`.
- **Sur PR** : rapport en commentaire (permissions, risque, domaines, résultat dynamique),
  validations bloquantes (format, `repository.yaml`, configs valides, soumetteur = owner ou
  mainteneur). Fusion uniquement après approbation d'un relecteur (`CODEOWNERS` + protection
  de branche). Après fusion, l'Action écrit `status: approved`, `reviewed` et `scan`.
- **Nuit** : si le commit par défaut a changé, rescan. Si les signaux n'ont pas changé
  (mêmes permissions, risque, domaines), mise à jour silencieuse de `scan`. S'ils ont changé,
  `status: flagged` + issue assignée aux relecteurs avec le diff des signaux. Le relecteur
  repasse en `approved` ou passe en `removed`. Dépôt introuvable / archivé → issue.

### 3. Intégration `community_apps`

- Config flow : une seule entrée, aucune authentification ; abandon `no_supervisor` sans
  Supervisor.
- Coordinateur : récupère `catalog.json` (toutes les 6 h, et à la demande depuis le
  panneau) ; état Supervisor : dépôts du store et apps installées.
- API WebSocket :
  - `community_apps/list` : catalogue enrichi (dépôt déjà ajouté ? apps installées ?).
  - `community_apps/add_repository` (**admin uniquement**) : ajoute l'URL publique au store
    du Supervisor, recharge le store, renvoie les slugs des apps du dépôt.
- Panneau latéral « Community Apps » (admin uniquement) : recherche, filtres (risque,
  architecture compatible avec l'hôte), fiche détaillée avec permissions expliquées en clair,
  domaines contactés, date de relecture, lien vers le dépôt et le rapport ; bouton
  « Ajouter le dépôt » puis lien vers la page native de l'app. Thème HA via les variables
  CSS. Confirmation explicite avant l'ajout d'un dépôt `high`.
- Réparations : une issue par app installée dont le dépôt est `flagged` ou `removed`, avec
  la raison et le lien vers le rapport. Disparaît quand le statut redevient `approved` ou que
  l'app est désinstallée.
- L'intégration ne retire jamais un dépôt et n'installe jamais d'app.

### 4. Dépôt

```
hacs.json
custom_components/community_apps/   intégration + panneau (frontend/)
catalog/repositories/<owner>/<repo>.yaml
tools/                              scan, génération catalog.json (Python)
.github/workflows/                  validate (hassfest, HACS), scan-pr, nightly, publish
CODEOWNERS
README.md                           usage + publier une app + limites du scan
```

## Laissé au constructeur

- Frontend : web component JS sans build ou Lit bundlé ; vérifier le chemin de la page native
  d'une app dans HA 2026.11 pour le lien « Installer ».
- Outils de capture réseau dans l'Action (résolveur DNS journalisant, tcpdump…).
- Détails de l'heuristique de domaines statiques (filtrer le bruit : licences, liens doc,
  registres d'images).
- Mise en forme exacte du rapport de PR et du diff des signaux.
- Tests : outils de scan et génération du catalogue testables sans Home Assistant ; modules
  de l'intégration au minimum compilés.
