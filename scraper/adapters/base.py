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

logger = logging.getLogger("boardgame_deals")


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
        nemá to shodit celý denní běh. Chybu jen zaloguje.
        """
        try:
            deals = self.fetch_deals(min_discount_pct=min_discount_pct)
            logger.info("%s: nalezeno %d slev >= %d%%", self.shop_name, len(deals), min_discount_pct)
            return deals
        except Exception as exc:  # noqa: BLE001 - záměrně chytáme vše
            logger.error("%s: scraping selhal (%s)", self.shop_name, exc)
            return []
