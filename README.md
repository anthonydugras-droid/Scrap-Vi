# Vinted Watcher

Surveille des recherches Vinted et envoie une notification Discord dès qu'un
nouvel article correspondant à tes critères est publié.

## ⚠️ À savoir avant de l'utiliser

- Ce script utilise l'**API interne non-officielle** de Vinted (celle que le
  site utilise lui-même). Ce n'est **pas** une API publique documentée.
- Cela peut être contraire aux conditions d'utilisation de Vinted. Usage
  **personnel** uniquement, à intervalle raisonnable (60s par défaut — ne
  descends pas trop bas pour éviter de te faire bloquer/rate-limiter).
- L'API peut changer sans préavis et casser le script.

## Installation

```bash
pip install requests
```

## Configuration (`config.json`)

1. **Webhook Discord** : dans ton serveur Discord → *Paramètres du salon* →
   *Intégrations* → *Webhooks* → *Nouveau webhook* → copie l'URL et colle-la
   dans `discord_webhook_url`.

2. **Recherches** : chaque entrée de `searches` est une recherche indépendante.
   - `keywords` : texte libre (ex: `"nike air max"`)
   - `price_min` / `price_max` : bornes de prix en euros
   - `size_ids`, `brand_ids`, `status_ids`, `catalog_ids` : listes d'IDs
     numériques Vinted (voir ci-dessous comment les trouver)

### Trouver les IDs (taille, marque, catégorie, état)

Le moyen le plus simple : va sur vinted.fr, fais une recherche avec les
filtres que tu veux (marque, taille, état...) dans l'interface web, puis
ouvre les **outils de développement du navigateur** (F12) → onglet
**Réseau/Network** → filtre `catalog/items` → regarde les paramètres de la
requête (`brand_ids`, `size_ids`, `status_ids`...). Tu peux copier ces IDs
directement dans `config.json`.

Tu peux aussi laisser une liste vide `[]` si tu ne veux pas filtrer sur ce
critère.

## Lancer le watcher

```bash
python3 vinted_watcher.py
```

- Au premier lancement, le script enregistre les articles déjà en ligne
  **sans notifier** (sinon tu reçois d'un coup tout l'historique).
- Ensuite, chaque nouvel article détecté déclenche un message Discord avec
  photo, prix, taille, marque, état et lien direct vers l'annonce.
- Les IDs déjà vus sont sauvegardés dans `seen_items.json` (créé
  automatiquement), donc tu peux arrêter/relancer le script sans spam.

## Tourner en continu

Pour le laisser tourner en arrière-plan sur ta machine ou un serveur :

```bash
nohup python3 vinted_watcher.py > watcher.log 2>&1 &
```

Ou avec `screen`/`tmux`, ou en le packageant dans un service systemd /
conteneur Docker si tu veux quelque chose de plus robuste.

## Limites connues

- Pas de gestion de proxy/rotation — si Vinted bloque ton IP après trop de
  requêtes, augmente `poll_interval_seconds`.
- Un seul webhook Discord pour toutes les recherches (facile à étendre si tu
  veux un salon différent par recherche).

---

## Déploiement gratuit sur GitHub Actions

### A. Créer le webhook Discord

1. Dans Discord, va dans le salon où tu veux recevoir les alertes.
2. Clique sur l'icône ⚙️ à côté du nom du salon (ou clic droit → *Modifier le
   salon*) → **Intégrations** → **Webhooks** → **Nouveau webhook**.
3. Donne-lui un nom (ex: "Vinted Watcher"), choisis le salon.
4. Clique sur **Copier l'URL du webhook**. Garde-la de côté, tu vas la
   coller dans GitHub juste après (jamais dans le code).

### B. Créer le repo GitHub

1. Sur github.com → **New repository** → nom au choix (ex: `vinted-watch`) →
   **Public** → Create repository.
2. Mets tous les fichiers de ce dossier dedans (via `git push` ou en
   glissant-déposant les fichiers sur l'interface web GitHub, "Add file →
   Upload files").
   - Assure-toi que `.github/workflows/vinted-watch.yml` est bien présent
     à ce chemin exact (dossier `.github` à la racine).

### C. Ajouter le webhook comme secret (jamais dans le code)

1. Dans le repo → **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret**.
3. Nom : `DISCORD_WEBHOOK_URL`
4. Valeur : colle l'URL du webhook copiée à l'étape A.
5. **Add secret**.

Le workflow lit ce secret automatiquement (`env: DISCORD_WEBHOOK_URL`), donc
tu peux laisser `discord_webhook_url` tel quel (placeholder) dans
`config.json` — il ne sera pas utilisé sur GitHub Actions.

### D. Activer les Actions

1. Onglet **Actions** du repo → si demandé, clique **I understand my
   workflows, go ahead and enable them**.
2. Le workflow `Vinted Watch` tourne automatiquement toutes les 15 minutes
   (modifiable dans le fichier `.github/workflows/vinted-watch.yml`, ligne
   `cron`).
3. Tu peux aussi le lancer manuellement : onglet **Actions** → **Vinted
   Watch** → **Run workflow**.

Au tout premier run, aucun `seen_items.json` n'existe encore : le script
enregistre l'existant sans notifier, puis committe ce fichier dans le repo.
Les runs suivants ne notifient que les **vrais nouveaux** articles.

### E. Ajouter/modifier des recherches sans toucher au code

C'est le principal intérêt de séparer `config.json` du script : pour ajouter
une nouvelle recherche (nouveau mot-clé, marque, taille...), tu n'as **jamais
besoin de toucher à `vinted_watcher.py`**.

Directement depuis le site GitHub (sur ton téléphone ou ton PC, sans rien
installer) :

1. Ouvre le fichier `config.json` dans ton repo.
2. Clique sur l'icône ✏️ (crayon, "Edit this file") en haut à droite.
3. Ajoute un nouveau bloc dans la liste `"searches"`, par exemple :

```json
{
  "name": "Manteau Zara taille M",
  "keywords": "manteau laine",
  "price_min": 5,
  "price_max": 40,
  "size_ids": [],
  "brand_ids": [],
  "status_ids": [],
  "catalog_ids": []
}
```

   (n'oublie pas la virgule entre deux blocs `{ ... }` de la liste)

4. En bas de page, **Commit changes** (directement sur `main`).
5. C'est tout — au prochain passage du cron (max 15 min), la nouvelle
   recherche est prise en compte automatiquement.

Pas besoin de connaître les `size_ids`/`brand_ids` pour démarrer : laisse ces
listes vides `[]`, seuls `keywords`, `price_min` et `price_max` suffisent
pour une recherche basique. Tu pourras affiner plus tard en suivant la
méthode "outils de développement" décrite plus haut.
