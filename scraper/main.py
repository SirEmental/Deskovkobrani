"""
Hlavní vstupní bod. Spouští se jednou denně z GitHub Actions
(.github/workflows/daily.yml), ale klidně ho spustíš i ručně lokálně:

    python -m scraper.main

Co udělá, popořadě:
  1. Projde všechny nakonfigurované obchody (config.py) a posbírá
     všechny položky se slevou >= MIN_DISCOUNT_PCT.
  2. Vyřadí produkty, které jsi dřív označil jako "Skrýt" (data/hidden.json).
  3. Zjistí, které z nich jsou dnes nové (data/seen.json).
  4. Vygeneruje docs/index.html (galerie pro GitHub Pages).
  5. Pokud jsou nějaké nové položky, pošle o nich e-mail.
"""

from __future__ import annotations

import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import storage  # noqa: E402
from scraper.config import MIN_DISCOUNT_PCT, get_all_adapters  # noqa: E402
from scraper.render_html import render_gallery  # noqa: E402
from scraper.send_email import build_email_html, send_email  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("boardgame_deals")

GITHUB_REPO = os.environ.get("GITHUB_REPOSITORY", "tvoje-jmeno/boardgame-deals")
GALLERY_URL = os.environ.get("GALLERY_URL", f"https://{GITHUB_REPO.split('/')[0]}.github.io/{GITHUB_REPO.split('/')[-1]}/")
MIN_DISCOUNT = int(os.environ.get("MIN_DISCOUNT_PCT", MIN_DISCOUNT_PCT))
OUTPUT_HTML = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "index.html")


def main() -> None:
    logger.info("Spouštím denní kontrolu slev (práh %d %%)...", MIN_DISCOUNT)

    all_deals = []
    for adapter in get_all_adapters():
        all_deals.extend(adapter.safe_fetch_deals(min_discount_pct=MIN_DISCOUNT))

    logger.info("Celkem napříč obchody nalezeno %d slev >= %d%% (před filtrem skrytých).", len(all_deals), MIN_DISCOUNT)

    hidden = storage.load_hidden()
    visible_deals = [d for d in all_deals if d.product_id not in hidden]
    logger.info("Po odečtení skrytých produktů zbývá %d.", len(visible_deals))

    favorites = storage.load_favorites()
    is_new_map = storage.update_seen({d.product_id for d in visible_deals})
    new_deals = [d for d in visible_deals if is_new_map.get(d.product_id)]

    render_gallery(
        deals=visible_deals,
        is_new_map=is_new_map,
        favorites=favorites,
        github_repo=GITHUB_REPO,
        min_discount_pct=MIN_DISCOUNT,
        output_path=OUTPUT_HTML,
    )
    logger.info("Galerie uložena do %s", OUTPUT_HTML)

    if new_deals:
        logger.info("Nalezeno %d nových položek, posílám e-mail...", len(new_deals))
        email_html = build_email_html(new_deals, favorites, GITHUB_REPO, GALLERY_URL, MIN_DISCOUNT)
        send_email(subject=f"🎲 {len(new_deals)} nových slev na deskovky", html_body=email_html)
    else:
        logger.info("Žádné nové položky - e-mail se dnes neposílá.")


if __name__ == "__main__":
    main()
