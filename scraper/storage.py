"""
Trvalý stav mezi jednotlivými denními běhy se ukládá jako JSON soubory
přímo v git repozitáři (data/hidden.json, data/seen.json). GitHub Action
je po každém běhu commitne zpět - žádná externí databáze není potřeba.

hidden.json:  {"<product_id>": {"name": ..., "hidden_at": "2026-09-08"}}
seen.json:    {"<product_id>": {"first_seen": "2026-09-01", "last_seen": "2026-09-08"}}
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime
from typing import Dict

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
HIDDEN_PATH = os.path.join(DATA_DIR, "hidden.json")
SEEN_PATH = os.path.join(DATA_DIR, "seen.json")


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


def load_hidden() -> Dict[str, dict]:
    return _load(HIDDEN_PATH)


def save_hidden(data: Dict[str, dict]) -> None:
    _save(HIDDEN_PATH, data)


def hide_product(product_id: str, name: str = "") -> None:
    """Přidá produkt na blacklist. Volá se z workflow handle_hide.yml."""
    hidden = load_hidden()
    hidden[product_id] = {"name": name, "hidden_at": date.today().isoformat()}
    save_hidden(hidden)


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
