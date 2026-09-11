"""
Spouští ho .github/workflows/handle_actions.yml, kdykoliv vznikne nové
issue, jehož NÁZEV začíná na "hide:" nebo "favorite:" (to se stane po
kliknutí na odkaz "Skrýt" nebo "Přidat/odebrat z oblíbených" v galerii
nebo v e-mailu).

Formát názvu issue:
    "hide: <product_id>"      -> natrvalo skrýt
    "favorite: <product_id>"  -> přepnout oblíbenost (přidat/odebrat)

GitHub Actions předá název a tělo issue přes proměnné prostředí
ISSUE_TITLE a ISSUE_BODY (viz workflow soubor).

Po zpracování akce se navíc OKAMŽITĚ přegeneruje docs/index.html ze
snímku poslední denní kontroly (data/last_deals.json) - takže se
změna projeví na stránce hned, ne až při dalším denním běhu zítra.
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import storage  # noqa: E402

TITLE_RE = re.compile(r"(hide|favorite)\s*:\s*([a-f0-9]{16})", re.IGNORECASE)
NAME_RE = re.compile(r"(?:Skrýt natrvalo|Přepnout oblíbenost)\s*:\s*(.+)")


def _regenerate_gallery() -> None:
    from scraper.render_html import render_gallery

    snapshot = storage.load_deals_snapshot()
    if snapshot is None:
        print("Zatím neproběhl žádný denní běh (chybí data/last_deals.json) - "
              "galerie se přegeneruje až při něm. Nic se nekazí, jen na "
              "vizuální projev změny počkej do zítřka nebo spusť denní "
              "workflow ručně (Actions -> Denní kontrola slev -> Run workflow).")
        return

    deals, is_new_map = snapshot
    hidden = storage.load_hidden()
    favorites = storage.load_favorites()
    visible = [d for d in deals if d.product_id not in hidden]

    github_repo = os.environ.get("GITHUB_REPOSITORY", "tvoje-jmeno/boardgame-deals")
    min_discount = int(os.environ.get("MIN_DISCOUNT_PCT", 30))
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "index.html"
    )
    render_gallery(visible, is_new_map, favorites, github_repo, min_discount, output_path)
    print(f"Galerie přegenerována ({len(visible)} viditelných položek).")


def main() -> None:
    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")

    match = TITLE_RE.search(title)
    if not match:
        print(f"Nepodařilo se rozpoznat akci a product_id v názvu issue: {title!r}")
        sys.exit(1)

    action = match.group(1).lower()
    product_id = match.group(2)
    name_match = NAME_RE.search(body)
    name = name_match.group(1).strip() if name_match else ""

    if action == "hide":
        storage.hide_product(product_id, name)
        print(f"Skryto natrvalo: {name or product_id} ({product_id})")
    elif action == "favorite":
        is_favorite = storage.toggle_favorite(product_id, name)
        stav = "PŘIDÁNO mezi oblíbené" if is_favorite else "ODEBRÁNO z oblíbených"
        print(f"{stav}: {name or product_id} ({product_id})")
    else:
        return

    _regenerate_gallery()


if __name__ == "__main__":
    main()
