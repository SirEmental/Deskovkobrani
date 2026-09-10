"""
Společné datové typy a základní rozhraní pro všechny adaptéry obchodů.

Každý adaptér (jeden soubor na obchod / na platformu) musí umět jednu věc:
projít stránky se slevami daného obchodu a vrátit seznam objektů Deal.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from typing import Optional

import requests

logger = logging.getLogger("boardgame_deals")

# Záložní kurz pro případ, že se nepodaří stáhnout aktuální (např. výpadek
# API). Občas ho aktualizuj - není potřeba na chlup přesně, jde jen o to,
# aby "sleva 30 %+" dávala rozumný smysl i v Kč.
FALLBACK_EUR_TO_CZK = 24.2

_exchange_rate_cache: dict[str, float] = {}


def _get_eur_to_czk_rate() -> float:
    if "EUR" in _exchange_rate_cache:
        return _exchange_rate_cache["EUR"]
    rate = FALLBACK_EUR_TO_CZK
    try:
        resp = requests.get("https://api.frankfurter.app/latest?from=EUR&to=CZK", timeout=10)
        if resp.status_code == 200:
            rate = float(resp.json()["rates"]["CZK"])
    except Exception as exc:  # noqa: BLE001
        logger.warning("Nepodařilo se stáhnout kurz EUR->CZK, používám zálohu %.2f (%s)", FALLBACK_EUR_TO_CZK, exc)
    _exchange_rate_cache["EUR"] = rate
    return rate


@dataclass
class Deal:
    """Jedna nalezená zlevněná položka."""

    shop: str                      # čitelný název obchodu, např. "Planeta her"
    name: str                      # název produktu
    url: str                       # odkaz na produkt
    price_current: float           # aktuální cena (číslo, bez měny)
    price_original: float          # původní cena
    discount_pct: int              # sleva v %, celé číslo (např. 45)
    currency: str = "Kč"
    image_url: Optional[str] = None
    in_stock: bool = True
    product_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.product_id:
            # Stabilní ID, které se nemění mezi jednotlivými běhy -
            # potřebujeme ho pro "hidden" seznam a pro detekci novinek.
            raw = f"{self.shop}|{self.url}"
            self.product_id = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def as_dict(self) -> dict:
        return {
            "shop": self.shop,
            "name": self.name,
            "url": self.url,
            "price_current": self.price_current,
            "price_original": self.price_original,
            "discount_pct": self.discount_pct,
            "currency": self.currency,
            "image_url": self.image_url,
            "in_stock": self.in_stock,
            "product_id": self.product_id,
        }


class BaseAdapter:
    """Společný předek pro adaptéry. Podtřídy implementují fetch_deals()."""

    #: čitelné jméno obchodu (přepiš v podtřídě / configu)
    shop_name: str = "Neznámý obchod"

    def fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        raise NotImplementedError

    def safe_fetch_deals(self, min_discount_pct: int = 30) -> list[Deal]:
        """
        Obálka nad fetch_deals(), která nikdy nespadne s výjimkou -
        pokud se jeden obchod rozbije (změna šablony, výpadek, timeout),
        nemá to shodit celý denní běh. Chybu jen zaloguje. Zároveň
        sjednotí měnu všech položek na Kč.
        """
        try:
            deals = self.fetch_deals(min_discount_pct=min_discount_pct)
            deals = [_normalize_to_czk(d) for d in deals]
            logger.info("%s: nalezeno %d slev >= %d%%", self.shop_name, len(deals), min_discount_pct)
            return deals
        except Exception as exc:  # noqa: BLE001 - záměrně chytáme vše
            logger.error("%s: scraping selhal (%s)", self.shop_name, exc)
            return []


def _normalize_to_czk(deal: Deal) -> Deal:
    """Pokud obchod ukazuje cenu v EUR (typicky kvůli jazyku serveru
    bez české geolokace), přepočítá ji na Kč, ať jsou všechny obchody
    v galerii/e-mailu srovnatelné a čitelné."""
    if deal.currency in ("Kč", "CZK"):
        return deal
    if deal.currency in ("€", "EUR"):
        rate = _get_eur_to_czk_rate()
        deal.price_current = round(deal.price_current * rate)
        deal.price_original = round(deal.price_original * rate)
        deal.currency = "Kč"
    return deal
