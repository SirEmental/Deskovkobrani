"""
Univerzální adaptér pro e-shopy na platformě Shoptet.

Shoptet je jeden z nejrozšířenějších českých e-shopových systémů a
u zlevněného zboží prakticky vždy zobrazuje text ve tvaru:

    Původně: 420 Kč (–73 %)
    110 Kč

(anglická verze obchodu totéž píše jako "Was: €45,33 (–10 %)").

Tenhle text je součástí jádra šablony, takže se opakuje napříč různě
graficky nastylovanými Shoptet obchody - proto z něj čteme slevu
regulárním výrazem, místo abychom se spoléhali na konkrétní CSS třídy
(ty se mezi shopy liší podle zvoleného vzhledu/šablony).

POZNÁMKA K SPOLEHLIVOSTI:
Bez živého spuštění proti každému konkrétnímu shopu nejde zaručit, že
selektory pro nalezení "jedné dlaždice produktu" sednou na 100 %.
Proto to zkoušíme přes několik běžných kandidátů a bereme ten, který
na stránce najde nejvíc opakujících se bloků. Pokud by se konkrétní
shop choval jinak, stačí doladit CANDIDATE_ITEM_SELECTORS níž.
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

REQUEST_TIMEOUT = 20
DELAY_BETWEEN_REQUESTS_SEC = 1.5
MAX_PAGES = 6

# Kandidáti na "obálku jedné produktové dlaždice" - zkusí se popořadě
CANDIDATE_ITEM_SELECTORS = [
    "div.p-box",
    "div.product",
    "li.product",
    "article.product",
    "div.product-box",
    "div.product-list-item",
]

# Text vzor pro "Původně: 420 Kč (–73 %)" / "Was: €45,33 (–10 %)"
ORIGINAL_PRICE_RE = re.compile(
    r"(?:Původně|Was)\s*:?\s*([\d\s.,]+)\s*(Kč|€|EUR)\s*\(\s*[-–]\s*(\d+)\s*%\s*\)",
    re.IGNORECASE,
)
# Libovolná cena v textu, použije se pro dohledání "aktuální" (poslední) ceny
ANY_PRICE_RE = re.compile(r"([\d][\d\s]*[\d]|\d)\s*(Kč|€|EUR)")

OUT_OF_STOCK_WORDS = ("vyprodáno", "není skladem", "out of stock", "sold out")


def _parse_number(raw: str) -> float:
    raw = raw.replace("\xa0", " ").replace(" ", "").replace(",", ".")
    # "1.299.00" apod. - necháme jen poslední desetinnou čárku/tečku
    parts = raw.split(".")
    if len(parts) > 2:
        raw = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(raw)
    except ValueError:
        return 0.0


@dataclass
class ShoptetShopConfig:
    shop_name: str
    base_url: str            # např. "https://www.planetaher.cz"
    sale_paths: list[str]    # jedna nebo víc URL cest se slevami (kategorie s filtrem)
    skip_out_of_stock: bool = True


class ShoptetAdapter(BaseAdapter):
    def __init__(self, config: ShoptetShopConfig):
        self.config = config
        self.shop_name = config.shop_name

    def fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        deals: dict[str, Deal] = {}
        for path in self.config.sale_paths:
            url = path if path.startswith("http") else self.config.base_url.rstrip("/") + path
            for page_deals in self._iter_pages(url):
                for deal in page_deals:
                    if deal.discount_pct >= min_discount_pct:
                        deals[deal.product_id] = deal
        return list(deals.values())

    # -- interní metody -----------------------------------------------

    def _iter_pages(self, start_url: str):
        page = 1
        while page <= MAX_PAGES:
            sep = "&" if "?" in start_url else "?"
            page_url = start_url if page == 1 else f"{start_url}{sep}page={page}"
            html = self._get(page_url)
            if html is None:
                break
            items = self._extract_items(html, page_url)
            if not items:
                break
            yield items
            page += 1
            time.sleep(DELAY_BETWEEN_REQUESTS_SEC)

    def _get(self, url: str) -> Optional[str]:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            if resp.status_code != 200:
                logger.warning("%s: HTTP %s pro %s", self.shop_name, resp.status_code, url)
                return None
            return resp.text
        except requests.RequestException as exc:
            logger.warning("%s: chyba požadavku na %s (%s)", self.shop_name, url, exc)
            return None

    def _pick_item_selector(self, soup: BeautifulSoup) -> Optional[str]:
        best_selector, best_count = None, 0
        for sel in CANDIDATE_ITEM_SELECTORS:
            count = len(soup.select(sel))
            if count > best_count:
                best_selector, best_count = sel, count
        return best_selector if best_count >= 2 else None

    def _extract_items(self, html: str, page_url: str) -> list[Deal]:
        soup = BeautifulSoup(html, "html.parser")
        selector = self._pick_item_selector(soup)
        if not selector:
            logger.info("%s: na %s se nepodařilo najít produktové dlaždice", self.shop_name, page_url)
            return []

        results = []
        for box in soup.select(selector):
            text = box.get_text(" ", strip=True)
            match = ORIGINAL_PRICE_RE.search(text)
            if not match:
                continue  # tahle položka není zlevněná

            price_original = _parse_number(match.group(1))
            currency = match.group(2).replace("EUR", "€")
            discount_pct = int(match.group(3))

            # aktuální cena = poslední cenová částka v textu dlaždice
            all_prices = ANY_PRICE_RE.findall(text)
            if not all_prices:
                continue
            price_current = _parse_number(all_prices[-1][0])

            link = box.select_one("a[href]")
            if not link or not link.get("href"):
                continue
            href = link["href"]
            if href.startswith("/"):
                href = self.config.base_url.rstrip("/") + href

            name = link.get_text(strip=True) or (link.get("title") or "").strip()
            if not name:
                # zkus alt text obrázku
                img_tag = box.select_one("img[alt]")
                name = img_tag["alt"].strip() if img_tag else "Neznámý produkt"

            img = box.select_one("img")
            image_url = None
            if img:
                image_url = img.get("data-src") or img.get("src")
                if image_url and image_url.startswith("/"):
                    image_url = self.config.base_url.rstrip("/") + image_url

            in_stock = not any(w in text.lower() for w in OUT_OF_STOCK_WORDS)
            if self.config.skip_out_of_stock and not in_stock:
                continue

            results.append(
                Deal(
                    shop=self.shop_name,
                    name=name,
                    url=href,
                    price_current=price_current,
                    price_original=price_original,
                    discount_pct=discount_pct,
                    currency=currency,
                    image_url=image_url,
                    in_stock=in_stock,
                )
            )
        return results
