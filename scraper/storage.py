"""
Trvalý stav mezi jednotlivými denními běhy se ukládá jako JSON soubory
přímo v git repozitáři (data/hidden.json, data/seen.json). GitHub Action
je po každém běhu commitne zpět - žádná externí databáze není potřeba.

hidden.json:     {"<product_id>": {"name": ..., "hidden_at": "2026-09-08"}}
seen.json:       {"<product_id>": {"first_seen": "2026-09-01", "last_seen": "2026-09-08"}}
favorites.json:  {"<product_id>": {"name": ..., "favorited_at": "2026-09-08"}}
last_deals.json: {"deals": [...cely Deal jako slovnik...], "is_new": {"<product_id>": bool}}
                 - snímek POSLEDNÍHO denního běhu, aby šlo galerii
                 přegenerovat okamžitě po kliknutí na Skrýt/Oblíbit,
                 beze nutnosti znovu stahovat všechny obchody.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict, Optional

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
HIDDEN_PATH = os.path.join(DATA_DIR, "hidden.json")
SEEN_PATH = os.path.join(DATA_DIR, "seen.json")
FAVORITES_PATH = os.path.join(DATA_DIR, "favorites.json")
LAST_DEALS_PATH = os.path.join(DATA_DIR, "last_deals.json")


def _load(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save(path: str, data: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)


def save_deals_snapshot(deals, is_new_map: Dict[str, bool]) -> None:
    """deals: list objektů Deal (z scraper.adapters.base)."""
    snapshot = {"deals": [d.as_dict() for d in deals], "is_new": is_new_map}
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(LAST_DEALS_PATH, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)


def load_deals_snapshot() -> Optional[tuple]:
    """Vrátí (deals, is_new_map), nebo None pokud snímek ještě neexistuje
    (např. úplně první běh se ještě neproběhl)."""
    if not os.path.exists(LAST_DEALS_PATH):
        return None
    from scraper.adapters.base import Deal  # lokální import, ať se předejde cyklické závislosti

    with open(LAST_DEALS_PATH, "r", encoding="utf-8") as f:
        try:
            raw = json.load(f)
        except json.JSONDecodeError:
            return None
    deals = [Deal(**d) for d in raw.get("deals", [])]
    return deals, raw.get("is_new", {})


def load_hidden() -> Dict[str, dict]:
    return _load(HIDDEN_PATH)


def save_hidden(data: Dict[str, dict]) -> None:
    _save(HIDDEN_PATH, data)


def hide_product(product_id: str, name: str = "") -> None:
    """Přidá produkt na blacklist. Volá se z workflow handle_hide.yml."""
    hidden = load_hidden()
    hidden[product_id] = {"name": name, "hidden_at": date.today().isoformat()}
    save_hidden(hidden)


def load_favorites() -> Dict[str, dict]:
    return _load(FAVORITES_PATH)


def save_favorites(data: Dict[str, dict]) -> None:
    _save(FAVORITES_PATH, data)


def toggle_favorite(product_id: str, name: str = "") -> bool:
    """
    Přidá/odebere produkt z oblíbených (jeden odkaz = přepínač).
    Vrací True, pokud je produkt PO akci oblíbený, jinak False.
    """
    favorites = load_favorites()
    if product_id in favorites:
        del favorites[product_id]
        save_favorites(favorites)
        return False
    favorites[product_id] = {"name": name, "favorited_at": date.today().isoformat()}
    save_favorites(favorites)
    return True


def load_seen() -> Dict[str, dict]:
    return _load(SEEN_PATH)


def save_seen(data: Dict[str, dict]) -> None:
    _save(SEEN_PATH, data)


def update_seen(current_product_ids: set[str]) -> Dict[str, bool]:
    """
    Aktualizuje seen.json a vrátí mapu {product_id: is_new_today}.

    is_new_today = True, pokud jsme tenhle produkt v žádném
    z předchozích běhů ještě neviděli.
    """
    seen = load_seen()
    today = date.today().isoformat()
    is_new: Dict[str, bool] = {}

    for pid in current_product_ids:
        if pid in seen:
            is_new[pid] = False
            seen[pid]["last_seen"] = today
        else:
            is_new[pid] = True
            seen[pid] = {"first_seen": today, "last_seen": today}

    # Volitelný úklid: produkty neviděné 60+ dní smažeme, ať soubor neroste do nekonečna
    cutoff = datetime.now().toordinal() - 60
    to_delete = [
        pid
        for pid, info in seen.items()
        if datetime.fromisoformat(info["last_seen"]).toordinal() < cutoff
    ]
    for pid in to_delete:
        del seen[pid]

    save_seen(seen)
    return is_new
