"""
Univerzální adaptér pro e-shopy na platformě WooCommerce (plugin do
WordPressu) - celosvětově jedna z nejrozšířenějších e-shopových
platforem, mezi českými vydavateli her ji používá např. MindOK nebo
BoardBros.

Na rozdíl od Shoptetu, kde je sleva "zamotaná" do jednoho textového
řetězce, WooCommerce ukazuje původní a zlevněnou cenu ve dvou čistě
oddělených HTML značkách - <del> (původní cena) a <ins> (nová cena) -
a tahle struktura je napříč různě graficky nastylovanými WooCommerce
obchody velmi konzistentní, protože je to součást jádra pluginu, ne
každého vzhledu zvlášť.
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
MAX_PAGES = 8

CANDIDATE_ITEM_SELECTORS = ["li.product", "div.product", "li.type-product"]

PRICE_RE = re.compile(r"[\d][\d\s.,]*")


def _parse_price(text: str) -> float:
    """WooCommerce obvykle píše '499,00 Kč' nebo '1 398,00 Kč'."""
    match = PRICE_RE.search(text.replace("\xa0", " "))
    if not match:
        return 0.0
    raw = match.group(0).replace(" ", "")
    # cesky format pouziva carku jako desetinnou - "499,00" -> "499.00"
    if "," in raw and "." not in raw:
        raw = raw.replace(",", ".")
    else:
        raw = raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


@dataclass
class WooCommerceShopConfig:
    shop_name: str
    base_url: str
    sale_paths: list[str]  # kategorie/obchod ke stránkování - nemusí to být přímo "jen slevy" stránka


class WooCommerceAdapter(BaseAdapter):
    def __init__(self, config: WooCommerceShopConfig):
        self.config = config
        self.shop_name = config.shop_name

    def fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        deals: dict[str, Deal] = {}
        for path in self.config.sale_paths:
            base = path if path.startswith("http") else self.config.base_url.rstrip("/") + path
            for page_items in self._iter_pages(base):
                for deal in page_items:
                    if deal.discount_pct >= min_discount_pct:
                        deals[deal.product_id] = deal
        return list(deals.values())

    def _iter_pages(self, base_url: str):
        page = 1
        while page <= MAX_PAGES:
            url = base_url if page == 1 else f"{base_url.rstrip('/')}/page/{page}/"
            html = self._get(url)
            if html is None:
                break
            items = self._extract_items(html)
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

    def _extract_items(self, html: str) -> list[Deal]:
        soup = BeautifulSoup(html, "html.parser")
        selector = self._pick_item_selector(soup)
        if not selector:
            return []

        results = []
        for box in soup.select(selector):
            price_box = box.select_one(".price") or box
            del_tag = price_box.select_one("del")
            ins_tag = price_box.select_one("ins")
            if not del_tag or not ins_tag:
                continue  # tahle položka není zlevněná (WooCommerce ukazuje
                # del+ins JEN u zlevněného zboží, jinak jen čistou cenu)

            price_original = _parse_price(del_tag.get_text(" ", strip=True))
            price_current = _parse_price(ins_tag.get_text(" ", strip=True))
            if price_original <= 0 or price_current <= 0 or price_current >= price_original:
                continue
            discount_pct = round((1 - price_current / price_original) * 100)

            title_el = (
                box.select_one(".woocommerce-loop-product__title")
                or box.select_one("h2")
                or box.select_one("h3")
            )
            name = title_el.get_text(strip=True) if title_el else None
            link = box.select_one("a[href]")
            href = link["href"] if link and link.get("href") else None
            if not name or not href:
                continue
            if href.startswith("/"):
                href = self.config.base_url.rstrip("/") + href

            img = box.select_one("img")
            image_url = None
            if img:
                image_url = img.get("data-src") or img.get("src")
                if image_url and image_url.startswith("/"):
                    image_url = self.config.base_url.rstrip("/") + image_url

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
                )
            )
        return results
