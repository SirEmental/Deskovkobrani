"""
Adaptér pro Xzone.cz - vlastní (ne-Shoptet) e-shopová platforma.

Xzone je obrovský obchod (hry, merch, oblečení...), deskovky jsou jen
jedna kategorie. Xzone u zlevněných kusů zobrazuje viditelný štítek
"Sleva XX %" přímo u produktu.

POZOR - TOHLE JE NEJVÍC "BEST EFFORT" ADAPTÉR V CELÉM PROJEKTU:
Neměl jsem možnost stáhnout syrové HTML (jen zjednodušený náhled),
takže přesné CSS třídy neznám. Adaptér proto:
  1) projde stránkovanou kategorii deskových her,
  2) u každého produktového bloku hledá text "Sleva NN %" regulárním
     výrazem (na textu, ne na konkrétní CSS třídě - odolnější vůči
     tomu, že neznám přesné třídy).

Po prvním ostrém běhu na GitHubu doporučuju zkontrolovat log - pokud
tenhle adaptér nic nenajde, pošli mi ukázku syrového HTML kategorie
a selektory doladíme.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BaseAdapter, Deal

logger = logging.getLogger("boardgame_deals")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; BoardgameDealsBot/1.0; "
        "+https://github.com/) osobni pouziti, prosim o shovivavost"
    )
}
REQUEST_TIMEOUT = 25
RETRY_ATTEMPTS = 2
DELAY_BETWEEN_REQUESTS_SEC = 1.5
MAX_PAGES = 10
ITEMS_PER_PAGE = 60  # odpovídá parametru s= v URL na xzone.cz

DISCOUNT_RE = re.compile(r"Sleva\s*(\d+)\s*%", re.IGNORECASE)
PRICE_RE = re.compile(r"([\d][\d\s]*)\s*Kč")

CANDIDATE_ITEM_SELECTORS = [
    "div.product-box",
    "div.product",
    "li.product",
    "div.item",
    "article",
]


def _parse_number(raw: str) -> float:
    raw = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


@dataclass
class XzoneCategoryConfig:
    shop_name: str
    base_url: str
    category_paths: list[str]  # např. ["/spolecenske-hry-deskove-hry", "/spolecenske-hry-karetni-hry"]


class XzoneAdapter(BaseAdapter):
    def __init__(self, config: XzoneCategoryConfig):
        self.config = config
        self.shop_name = config.shop_name

    def fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        deals: dict[str, Deal] = {}
        for path in self.config.category_paths:
            base = path if path.startswith("http") else self.config.base_url.rstrip("/") + path
            page = 1
            while page <= MAX_PAGES:
                sep = "&" if "?" in base else "?"
                url = f"{base}{sep}s={ITEMS_PER_PAGE}&page={page}"
                html = self._get(url)
                if not html:
                    break
                items = self._extract_items(html)
                if not items:
                    break
                for deal in items:
                    if deal.discount_pct >= min_discount_pct:
                        deals[deal.product_id] = deal
                page += 1
                time.sleep(DELAY_BETWEEN_REQUESTS_SEC)
        return list(deals.values())

    def _get(self, url: str) -> Optional[str]:
        last_exc = None
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            try:
                resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
                if resp.status_code != 200:
                    logger.warning("%s: HTTP %s pro %s", self.shop_name, resp.status_code, url)
                    return None
                return resp.text
            except requests.RequestException as exc:
                last_exc = exc
                if attempt < RETRY_ATTEMPTS:
                    time.sleep(3 * attempt)
        logger.warning("%s: chyba požadavku na %s po %d pokusech (%s)", self.shop_name, url, RETRY_ATTEMPTS, last_exc)
        return None

    def _pick_item_selector(self, soup: BeautifulSoup) -> Optional[str]:
        best_selector, best_count = None, 0
        for sel in CANDIDATE_ITEM_SELECTORS:
            count = len(soup.select(sel))
            if count > best_count:
                best_selector, best_count = sel, count
        return best_selector if best_count >= 2 else None

    def _extract_items(self, html: str) -> list[Deal]:
        soup = BeautifulSoup(html, "html.parser")
        selector = self._pick_item_selector(soup)
        if not selector:
            return []

        results = []
        for box in soup.select(selector):
            text = box.get_text(" ", strip=True)
            disc_match = DISCOUNT_RE.search(text)
            if not disc_match:
                continue
            discount_pct = int(disc_match.group(1))

            prices = PRICE_RE.findall(text)
            if not prices:
                continue
            price_current = _parse_number(prices[-1])
            # dopočítáme původní cenu ze slevy, pokud na dlaždici není zvlášť
            price_original = (
                _parse_number(prices[0]) if len(prices) > 1 else round(price_current / (1 - discount_pct / 100), 2)
            )

            link = box.select_one("a[href]")
            if not link or not link.get("href"):
                continue
            href = link["href"]
            if href.startswith("/"):
                href = self.config.base_url.rstrip("/") + href

            name = link.get_text(strip=True)
            if not name:
                img_tag = box.select_one("img[alt]")
                name = img_tag["alt"].strip() if img_tag else "Neznámý produkt"

            img = box.select_one("img")
            image_url = None
            if img:
                image_url = img.get("data-src") or img.get("src")

            results.append(
                Deal(
                    shop=self.shop_name,
                    name=name,
                    url=href,
                    price_current=price_current,
                    price_original=price_original,
                    discount_pct=discount_pct,
                    currency="Kč",
                    image_url=image_url,
                    in_stock=True,
                )
            )
        return results
