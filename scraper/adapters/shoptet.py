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

import json
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
MAX_PAGES = 10

# Kandidáti na "obálku jedné produktové dlaždice" - zkusí se popořadě
CANDIDATE_ITEM_SELECTORS = [
    "div.p-box",
    "div.product",
    "li.product",
    "article.product",
    "div.product-box",
    "div.product-list-item",
]

# Sleva se na Shoptetu píše v několika reálně pozorovaných variantách:
#   "Původně: 420 Kč (–73 %)"     čeština, s popiskem, % v závorce
#   "Sleva · 2 515 Kč –49 %"      čeština, bez popisku, % bez závorky
#   "Was: €53,58 (–86 %)"         angličtina, měna PŘED částkou (ne za ní!)
# Proto hledáme částku+měnu v OBOU pořadích a % nemusí být v závorce -
# jen samotné "číslo (Kč|€|EUR) [-–]číslo%" už stačí jako důkaz slevy.
CURRENCY = r"Kč|€|EUR"
AMOUNT = r"[\d][\d\s.,]*"
DISCOUNT_RE = re.compile(
    rf"(?:(?P<cur1>{CURRENCY})\s*(?P<amt1>{AMOUNT})|(?P<amt2>{AMOUNT})\s*(?P<cur2>{CURRENCY}))"
    rf"\s*\(?\s*[-–]\s*(?P<pct>\d+)\s*%\s*\)?",
    re.IGNORECASE,
)
# Libovolná zmínka o ceně (bez vazby na slevu) - pro dohledání aktuální ceny
ANY_PRICE_RE = re.compile(
    rf"(?:(?P<cur1>{CURRENCY})\s*(?P<amt1>{AMOUNT})|(?P<amt2>{AMOUNT})\s*(?P<cur2>{CURRENCY}))",
    re.IGNORECASE,
)

# Slova/štítky, které se objevují jako samostatné odkazy v dlaždici,
# ale NEJSOU název produktu (žánrové štítky, tlačítka, stavy skladu...)
GENERIC_LINK_WORDS = {
    "koupit", "detail", "skladem", "vyprodáno", "doprava zdarma", "sleva",
    "akce", "novinka", "tip", "doporučujeme", "top", "buy", "in stock",
    "out of stock", "new", "sale", "action", "add to cart", "do košíku",
    "kdy se to stalo",  # POZOR: tohle je náhodou i skutečný název hry,
    # necháváme ho tu záměrně VYPUŠTĚNÝ z blacklistu - viz komentář níž
}
GENERIC_LINK_WORDS.discard("kdy se to stalo")

OUT_OF_STOCK_WORDS = ("vyprodáno", "není skladem", "out of stock", "sold out")


def _looks_like_product_name(text: str) -> bool:
    """Heuristika (záložní, použije se jen když nejsou k dispozici
    strukturovaná data): je tenhle text odkazu skutečný název produktu?"""
    stripped = text.strip()
    if len(stripped) < 2 or stripped.lower() in GENERIC_LINK_WORDS:
        return False
    # POZOR: kdyby text obsahoval KDEKOLIV cenu/měnu/procento, jde skoro
    # jistě o odkaz obalující obrázek + přilepený štítek slevy (typicky
    # "<alt textu obrázku> Action €47,39 –82 %"), ne o čistý název -
    # a to i kdyby byl tenhle text nakonec delší než skutečný název hry.
    if ANY_PRICE_RE.search(stripped) or re.search(r"[-–]\s*\d+\s*%", stripped):
        return False
    if sum(ch.isalpha() for ch in stripped) < 2:
        return False
    return True


def _pick_product_href(box) -> Optional[str]:
    """
    V dlaždici bývá víc odkazů (obrázek, název, tlačítko Koupit...),
    ale skoro vždy míří na STEJNOU URL produktu - jen ojedinělý žánrový
    štítek může mířit jinam (např. na stránku žánru). Proto bereme
    NEJČASTĚJŠÍ href v dlaždici, ne prostě první, na který narazíme.
    """
    hrefs = [a["href"] for a in box.select("a[href]") if a.get("href")]
    if not hrefs:
        return None
    counts: dict[str, int] = {}
    for h in hrefs:
        counts[h] = counts.get(h, 0) + 1
    return max(counts.items(), key=lambda pair: pair[1])[0]


def _pick_name_from_links(box) -> Optional[str]:
    """
    Záložní heuristika pro jméno - použije se JEN když stránka nemá
    strukturovaná data (microdata/JSON-LD). Z odkazů v dlaždici vybere
    ten s nejdelším SMYSLUPLNÝM textem (bez ceny/procenta/obecných slov).
    """
    candidates = [
        text
        for a in box.select("a[href]")
        if _looks_like_product_name(text := a.get_text(" ", strip=True))
    ]
    return max(candidates, key=len) if candidates else None


def _extract_datalayer_names_ordered(soup: BeautifulSoup) -> list[str]:
    """
    Alternativa k JSON-LD pro případ, že stránka nemá schema.org data,
    ale MÁ obsáhlou Google Analytics/GTM dataLayer (běžné u Shoptetu -
    typicky "ecommerce.items" při sledování 'zobrazení seznamu
    produktů'). Tohle NENÍ platný JSON (je to JS kód), takže to
    neparsujeme jako JSON.

    POZOR na past: klíč "name" se v obsáhlé dataLayer objevuje i mimo
    produkty (název stránky, měna, jazyk...) - kdybychom brali "name"
    jen podle toho, že je NĚKDE POBLÍŽ i "id"/"price" (širší okno
    textu), ve skutečnosti bychom u krátkých/nahuštěných úseků chytali
    i úplně nesouvisející věci. Proto vyžadujeme, aby "id" a "name"
    byly PŘÍMO SOUSEDÍCÍ klíče (oddělené jen čárkou) ve stejném malém
    objektu - to už spolehlivě značí jeden produktový záznam.

    Vrací seznam jmen V POŘADÍ, v jakém se objevují. Volající kód si
    sám ověří, že se počet přesně shoduje s počtem dlaždic na stránce,
    než pozice použije - jinak by hrozilo špatné přiřazení.
    """
    id_then_name = re.compile(r'"(?:item_)?id"\s*:\s*"?[\w\-./]+"?\s*,\s*"(?:item_)?name"\s*:\s*"([^"]{2,120})"')
    name_then_id = re.compile(r'"(?:item_)?name"\s*:\s*"([^"]{2,120})"\s*,\s*"(?:item_)?id"\s*:\s*"?[\w\-./]+"?')

    pairs: list[tuple[int, str]] = []  # (pozice v textu, jméno) - napříč všemi scripty
    for script in soup.find_all("script"):
        text = script.string or script.get_text() or ""
        if "dataLayer" not in text and "ecommerce" not in text:
            continue
        for pattern in (id_then_name, name_then_id):
            for m in pattern.finditer(text):
                pairs.append((m.start(), m.group(1)))

    pairs.sort(key=lambda p: p[0])
    return [name for _, name in pairs]


def _extract_json_ld_names(soup: BeautifulSoup) -> dict[str, str]:
    """
    E-shopy kvůli SEO často vkládají do stránky strukturovaná data
    (schema.org JSON-LD) se skutečným, čistým názvem produktu - na
    rozdíl od viditelného textu tahle data nejsou "poskládaná" z
    obrázku+štítků, takže je to spolehlivější zdroj, pokud existuje.
    Vrací mapu {url_produktu: nazev}; pokud nic nenajde, prázdný slovník
    (nic se nerozbije, jen se použije záložní heuristika z textu).
    """
    url_to_name: dict[str, str] = {}

    def _walk(entry) -> None:
        if isinstance(entry, list):
            for item in entry:
                _walk(item)
            return
        if not isinstance(entry, dict):
            return
        entry_type = entry.get("@type", "")
        if entry_type == "Product" and entry.get("name") and entry.get("url"):
            url_to_name[entry["url"]] = entry["name"]
        if entry_type == "ItemList":
            for element in entry.get("itemListElement", []):
                if isinstance(element, dict):
                    _walk(element.get("item", element))
        # některé weby vnořují Product/Offer do "@graph"
        if "@graph" in entry:
            _walk(entry["@graph"])

    for script in soup.find_all("script", type="application/ld+json"):
        try:
            _walk(json.loads(script.string or ""))
        except (TypeError, ValueError):
            continue  # nevalidní/neočekávaný JSON - nevadí, jen přeskočíme

    return url_to_name


def _name_from_microdata(box) -> Optional[str]:
    """Schema.org microdata přímo v HTML (itemprop="name") - další běžný
    SEO vzor, opět spolehlivější než skládání z viditelného textu."""
    el = box.select_one('[itemprop="name"]')
    if not el:
        return None
    value = el.get("content") or el.get_text(strip=True)
    return value.strip() if value else None


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

        # Zkusíme najít jména ze strukturovaných dat - nejdřív JSON-LD
        # (přesné, podle URL), pak dataLayer (přesné jen pozičně, proto
        # jen když počet přesně sedí s počtem dlaždic na stránce).
        # Pokud stránka nic z toho nemá, použije se záložní heuristika
        # pro každou položku zvlášť - nic se nerozbije.
        all_boxes = soup.select(selector)
        json_ld_names = _extract_json_ld_names(soup)
        datalayer_names = _extract_datalayer_names_ordered(soup)
        positional_names = datalayer_names if len(datalayer_names) == len(all_boxes) else []

        results = []
        for idx, box in enumerate(all_boxes):
            text = box.get_text(" ", strip=True)
            match = DISCOUNT_RE.search(text)
            if not match:
                continue  # tahle položka není zlevněná

            amount_str = match.group("amt1") or match.group("amt2")
            currency = (match.group("cur1") or match.group("cur2")).replace("EUR", "€")
            price_original = _parse_number(amount_str)
            discount_pct = int(match.group("pct"))

            # Aktuální cena = poslední ZBÝVAJÍCÍ cenová zmínka v textu
            # (vyřízneme část textu, kde jsme právě našli původní cenu,
            # ať si ji regex nesplete sám se sebou).
            remaining_text = text[: match.start()] + text[match.end():]
            other_prices = list(ANY_PRICE_RE.finditer(remaining_text))
            if other_prices:
                last = other_prices[-1]
                price_current = _parse_number(last.group("amt1") or last.group("amt2"))
            else:
                price_current = round(price_original * (1 - discount_pct / 100), 2)

            href = _pick_product_href(box)
            if not href:
                continue
            if href.startswith("/"):
                href = self.config.base_url.rstrip("/") + href

            # Pořadí důvěryhodnosti zdroje jména - od nejspolehlivějšího:
            # 1) schema.org microdata přímo u položky, 2) JSON-LD podle
            # URL, 3) dataLayer podle pozice (jen když počet sedí),
            # 4) záložní heuristika z viditelného textu odkazů,
            # 5) alt text obrázku, 6) "Neznámý produkt" jako poslední záchrana.
            name = (
                _name_from_microdata(box)
                or json_ld_names.get(href)
                or json_ld_names.get(href.rstrip("/"))
                or (positional_names[idx] if positional_names else None)
                or _pick_name_from_links(box)
            )
            if not name:
                img_tag = box.select_one("img[alt]")
                name = img_tag["alt"].strip() if img_tag and img_tag.get("alt") else "Neznámý produkt"

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
