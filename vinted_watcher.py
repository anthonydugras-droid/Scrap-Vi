#!/usr/bin/env python3
"""
Vinted Watcher
==============
Surveille des recherches Vinted selon des critères (mots-clés, prix, taille,
marque, état) et envoie une notification Discord pour chaque nouvel article.

Usage:
    python3 vinted_watcher.py

Configuration: voir config.json et README.md

⚠️ Ceci utilise l'API interne (non-officielle) de Vinted. Usage personnel
uniquement, à intervalle raisonnable pour ne pas se faire bloquer.
"""

import json
import os
import time
import sys
from pathlib import Path
from datetime import datetime

import requests

CONFIG_PATH = Path(__file__).parent / "config.json"
STATE_PATH = Path(__file__).parent / "seen_items.json"

# Mode "une seule passe" : utilisé par GitHub Actions (le cron relance le
# script périodiquement, pas besoin de boucle infinie côté script).
RUN_ONCE = "--once" in sys.argv or os.environ.get("VINTED_RUN_ONCE") == "1"

# Le webhook peut venir d'une variable d'environnement (recommandé, ex:
# GitHub Secrets) et prend le pas sur celui du config.json si présent.
WEBHOOK_ENV_VAR = "DISCORD_WEBHOOK_URL"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_seen_ids():
    if STATE_PATH.exists():
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_seen_ids(seen_ids):
    # On garde seulement les 5000 derniers pour ne pas grossir indéfiniment
    trimmed = list(seen_ids)[-5000:]
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(trimmed, f)


class VintedClient:
    """Petit client pour l'API interne de Vinted (session + requêtes)."""

    def __init__(self, domain):
        self.domain = domain
        self.base_url = f"https://{domain}"
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        })
        self._init_session()

    def _init_session(self):
        # Vinted exige des cookies de session valides avant d'accepter
        # des appels API. On les récupère en visitant la page d'accueil.
        resp = self.session.get(self.base_url, timeout=15)
        resp.raise_for_status()

    def search_items(self, search_cfg, per_page=20):
        params = {
            "page": 1,
            "per_page": per_page,
            "order": "newest_first",
        }
        if search_cfg.get("keywords"):
            params["search_text"] = search_cfg["keywords"]
        if search_cfg.get("price_min"):
            params["price_from"] = search_cfg["price_min"]
        if search_cfg.get("price_max"):
            params["price_to"] = search_cfg["price_max"]
        if search_cfg.get("size_ids"):
            params["size_ids"] = search_cfg["size_ids"]
        if search_cfg.get("brand_ids"):
            params["brand_ids"] = search_cfg["brand_ids"]
        if search_cfg.get("status_ids"):
            params["status_ids"] = search_cfg["status_ids"]
        if search_cfg.get("catalog_ids"):
            params["catalog_ids"] = search_cfg["catalog_ids"]
        if search_cfg.get("color_ids"):
            params["color_ids"] = search_cfg["color_ids"]


        url = f"{self.base_url}/api/v2/catalog/items"
        resp = self.session.get(url, params=params, timeout=15)

        if resp.status_code == 401:
            # Session expirée : on la relance une fois
            self._init_session()
            resp = self.session.get(url, params=params, timeout=15)

        resp.raise_for_status()
        return resp.json().get("items", [])


def send_discord_notification(webhook_url, search_name, item):
    title = item.get("title", "Article Vinted")
    price_obj = item.get("price", {})
    price = f"{price_obj.get('amount', '?')} {price_obj.get('currency_code', '')}"
    brand = item.get("brand_title", "Marque inconnue")
    size = item.get("size_title", "Taille inconnue")
    status = item.get("status", "État inconnu")
    url = item.get("url", "")
    photo = (item.get("photo") or {}).get("url")

    embed = {
        "title": title[:256],
        "url": url,
        "color": 0x09B1BA,
        "fields": [
            {"name": "Prix", "value": price, "inline": True},
            {"name": "Taille", "value": size, "inline": True},
            {"name": "Marque", "value": brand, "inline": True},
            {"name": "État", "value": status, "inline": True},
        ],
        "footer": {"text": f"Recherche: {search_name}"},
    }
    if photo:
        embed["thumbnail"] = {"url": photo}

    payload = {"embeds": [embed]}
    resp = requests.post(webhook_url, json=payload, timeout=15)
    if resp.status_code >= 300:
        print(f"[!] Erreur envoi Discord ({resp.status_code}): {resp.text[:200]}")


def do_one_pass(config, client, webhook_url, seen_ids, first_pass):
    for search_cfg in config["searches"]:
        try:
            items = client.search_items(search_cfg)
        except requests.RequestException as e:
            print(f"[!] Erreur requête pour '{search_cfg['name']}': {e}")
            continue

        new_items = [it for it in items if str(it["id"]) not in seen_ids]

        # Au tout premier passage, on enregistre l'existant sans notifier
        # (sinon on spam Discord avec tout l'historique)
        if not first_pass:
            for item in reversed(new_items):  # du plus ancien au plus récent
                send_discord_notification(webhook_url, search_cfg["name"], item)
                print(f"[{datetime.now():%H:%M:%S}] Notifié: {item.get('title')}")
                time.sleep(1)  # évite de spammer le webhook Discord

        for item in items:
            seen_ids.add(str(item["id"]))

    save_seen_ids(seen_ids)


def run():
    config = load_config()
    seen_ids = load_seen_ids()
    client = VintedClient(config["vinted_domain"])

    webhook_url = os.environ.get(WEBHOOK_ENV_VAR) or config.get("discord_webhook_url", "")
    interval = config.get("poll_interval_seconds", 60)

    if not webhook_url or "COLLE_TON_ID" in webhook_url:
        print(f"⚠️  Configure le webhook Discord (variable d'env {WEBHOOK_ENV_VAR} "
              f"ou discord_webhook_url dans config.json)")
        sys.exit(1)

    # first_pass=True tant qu'aucun seen_items.json n'existe encore, pour ne
    # pas notifier tout l'historique existant au tout premier run.
    first_pass = not STATE_PATH.exists()

    if RUN_ONCE:
        print(f"[{datetime.now():%H:%M:%S}] Passe unique "
              f"({len(config['searches'])} recherche(s))")
        do_one_pass(config, client, webhook_url, seen_ids, first_pass)
        return

    print(f"[{datetime.now():%H:%M:%S}] Démarrage du watcher "
          f"({len(config['searches'])} recherche(s), poll toutes les {interval}s)")

    while True:
        do_one_pass(config, client, webhook_url, seen_ids, first_pass)
        first_pass = False
        time.sleep(interval)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\nArrêt du watcher.")