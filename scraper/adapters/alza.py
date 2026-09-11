"""
Adaptér pro Alza.cz.

Alza je mnohem větší a komplikovanější než ostatní obchody v projektu -
na jedné dlaždici se může potkat až několik různých typů "slevy"
najednou. Zjistil jsem (živým stažením skutečné výprodejové stránky),
že se aktuálně používají tyhle čtyři vzory textu:

  1) "Zlevněno -28 % 699,- 979,-"
     Klasická sleva - % i obě ceny (novou i původní) dává Alza rovnou.

  2) "Cenová bomba 325,- Ušetříte 74,-"
     Jen aktuální cena + ušetřená částka (původní cena = součet obou).
     POZOR: občas se "Ušetříte" u "Cenová bomba" vůbec neobjeví - pak
     nemáme žádnou referenční cenu a takovou položku musíme přeskočit,
     protože bychom si % slevy jinak museli vymyslet.

  3) "Získejte slevu 20 % s kódem ALZADNY20. Klikněte a kód se uplatní
     automaticky. 260,-"
     Sleva navíc PŘES kód, který se dle textu uplatní jedním kliknutím
     (ne ručním opisováním kódu u pokladny). Tahle sleva se vždy
     kombinuje s (1) nebo (2) jako základní cenou, na kterou se kód
     uplatňuje - výsledná cena je už přímo v textu, nic nedopočítáváme.

  4) "Přidat AlzaPlus+ a koupit hned levněji 1 533,- 2 190,-"
     Cena platí JEN s aktivním (placeným) členstvím AlzaPlus+. Tohle
     bereme v potaz, ale označíme zvlášť (Deal.note), ať je jasné, že
     bez členství tuhle cenu nezískáš.

Čtvrtý typ, který jsi zmínil - "Alza Benefit" - jsem záměrně VYNECHAL.
Zjistil jsem, že jde o neveřejný program vázaný na konkrétní
zaměstnavatele/instituce (aktivační kód, přihlášení) - výsledná cena
se anonymnímu požadavku vůbec neposílá, takže není co scrapovat, ani
kdyby byl scraper sebelepší.

TECHNICKÁ POZNÁMKA K DETEKCI DLAŽDIC:
Alza je natolik velký a vlastní systém, že jsem si netroufl hádat
přesné CSS třídy bez přístupu k syrovému HTML. Místo toho dlaždice
poznávám podle něčeho spolehlivějšího a stabilnějšího napříč
redesignama - podle URL vzoru "-dNNNNNNN.htm" (číselné ID produktu),
který se objevuje u KAŽDÉHO produktu. Text mezi dvěma takovými odkazy
= text jedné dlaždice.

DŮLEŽITÉ UPOZORNĚNÍ K BLOKOVÁNÍ BOTŮ:
Při ručním ověření (jiným nástrojem, ne touhle knihovnou) mě Alza
nijak neblokovala. To ale bohužel negarantuje, že stejně proleze i
běžný Python požadavek z GitHub Actions - velké e-shopy běžně
rozlišují klienty mnohem sofistikovaněji (otisk prohlížeče, chování,
IP rozsahy). Uvidíme až při ostrém běhu.
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
DELAY_BETWEEN_REQUESTS_SEC = 2.0
MAX_PAGES = 8

PRODUCT_LINK_RE = re.compile(r'href="([^"#]*-d(\d+)\.htm)"')

ZLEVNENO_RE = re.compile(r"Zlevněno\s*-(\d+)\s*%\s*([\d\s]+),-\s*([\d\s]+),-")
CENOVA_BOMBA_RE = re.compile(r"Cenová bomba\s*([\d\s]+),-(?:\s*Ušetříte\s*([\d\s]+),-)?")
KOD_SLEVA_RE = re.compile(
    r"Získejte slevu\s*(\d+)\s*%\s*s\s*kódem\s*(\S+?)\.\s*"
    r"Klikněte a kód se uplatní automaticky\.\s*([\d\s]+),-"
)
ALZAPLUS_RE = re.compile(
    r"Přidat AlzaPlus\+ a koupit hned levněji\s*([\d\s]+),-\s*(?:Super cena\s*)?([\d\s]+),-"
)

ALZAPLUS_NOTE = "Vyžaduje aktivní členství AlzaPlus+"


def _parse_number(raw: str) -> float:
    raw = raw.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return float(raw)
    except ValueError:
        return 0.0


@dataclass
class AlzaShopConfig:
    shop_name: str
    base_url: str
    sale_paths: list[str]  # URL výprodejové/akční kategorie, KONČÍCÍ na "-e0.htm"


class AlzaAdapter(BaseAdapter):
    def __init__(self, config: AlzaShopConfig):
        self.config = config
        self.shop_name = config.shop_name

    def fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        deals: dict[str, Deal] = {}
        for path in self.config.sale_paths:
            base = path if path.startswith("http") else self.config.base_url.rstrip("/") + path
            for page in range(1, MAX_PAGES + 1):
                url = base if page == 1 else base.replace("-e0.htm", f"-e0-p{page}.htm")
                html = self._get(url)
                if html is None:
                    break
                items = self._extract_items(html)
                if not items:
                    break
                for deal in items:
                    if deal.discount_pct >= min_discount_pct:
                        deals[deal.product_id] = deal
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

    def _extract_items(self, html: str) -> list[Deal]:
        # Najdeme hranice jednotlivých dlaždic podle unikátního product_id
        # v URL (viz vysvětlení v hlavičce souboru) - první výskyt každého
        # ID = začátek jeho dlaždice.
        seen_ids: set[str] = set()
        boundaries: list[tuple[int, str]] = []  # (pozice v HTML, product_id)
        for m in PRODUCT_LINK_RE.finditer(html):
            pid = m.group(2)
            if pid not in seen_ids:
                seen_ids.add(pid)
                boundaries.append((m.start(), pid))

        if not boundaries:
            return []

        results = []
        for i, (start, pid) in enumerate(boundaries):
            end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(html)
            chunk_html = html[start:end]
            deal = self._parse_chunk(chunk_html, pid)
            if deal:
                results.append(deal)
        return results

    def _parse_chunk(self, chunk_html: str, product_id: str) -> Optional[Deal]:
        chunk_soup = BeautifulSoup(chunk_html, "html.parser")
        text = chunk_soup.get_text(" ", strip=True)

        base_current: Optional[float] = None
        true_original: Optional[float] = None
        note: Optional[str] = None

        zlevneno = ZLEVNENO_RE.search(text)
        bomba = CENOVA_BOMBA_RE.search(text)
        alzaplus = ALZAPLUS_RE.search(text)

        if zlevneno:
            base_current = _parse_number(zlevneno.group(2))
            true_original = _parse_number(zlevneno.group(3))
        elif bomba and bomba.group(2):
            base_current = _parse_number(bomba.group(1))
            true_original = base_current + _parse_number(bomba.group(2))
        elif alzaplus:
            base_current = _parse_number(alzaplus.group(1))
            true_original = _parse_number(alzaplus.group(2))
            note = ALZAPLUS_NOTE

        final_current = base_current
        kod = KOD_SLEVA_RE.search(text)
        if kod:
            final_current = _parse_number(kod.group(3))

        if true_original is None or final_current is None or final_current <= 0:
            return None  # žádný z rozpoznaných typů slevy tu není
        if final_current >= true_original:
            return None

        discount_pct = round((true_original - final_current) / true_original * 100)

        link = chunk_soup.find("a", href=re.compile(rf"-d{product_id}\.htm"))
        href = link["href"] if link else None
        if not href:
            return None
        if href.startswith("/"):
            href = self.config.base_url.rstrip("/") + href

        name = None
        for a in chunk_soup.find_all("a", href=re.compile(rf"-d{product_id}\.htm")):
            candidate = a.get_text(strip=True)
            if candidate:
                name = candidate
                break
        if not name:
            return None

        img = chunk_soup.find("img")
        image_url = None
        if img:
            image_url = img.get("src") or img.get("data-src")

        return Deal(
            shop=self.shop_name,
            name=name,
            url=href,
            price_current=final_current,
            price_original=true_original,
            discount_pct=discount_pct,
            currency="Kč",
            image_url=image_url,
            note=note,
            product_id=f"alza-{product_id}",
        )
