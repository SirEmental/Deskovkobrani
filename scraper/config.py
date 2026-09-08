"""
Seznam sledovaných obchodů.

Přidat nový Shoptet obchod je otázka pár řádků - stačí najít jeho
kategorii/stránku se slevami (v adminu shopu se obvykle jmenuje
"Akce a slevy", "Výprodej" nebo podobně) a přidat ShoptetShopConfig.

MIN_DISCOUNT_PCT: výchozí práh, od kolika % slevy se položka počítá
za "velkou slevu". Dá se přebít i za běhu (viz main.py / env proměnná).
"""

from .adapters import ShoptetAdapter, ShoptetShopConfig, XzoneAdapter, XzoneCategoryConfig

MIN_DISCOUNT_PCT = 30

# ---------------------------------------------------------------------------
# HOTOVO A OVĚŘENO (stáhl jsem si živou stránku a viděl skutečnou strukturu)
# ---------------------------------------------------------------------------

SHOPTET_SHOPS = [
    ShoptetShopConfig(
        shop_name="Planeta her",
        base_url="https://www.planetaher.cz",
        # ?dd=1 = filtr "Slevy" na kategorii deskových/karetních her
        sale_paths=["/deskove-a-karetni-hry/?dd=1&stock=1"],
    ),
    ShoptetShopConfig(
        shop_name="TLAMA games",
        base_url="https://www.tlamagames.com",
        sale_paths=["/en/permanently-discounted/"],
    ),
    # HRAS.cz - vzhled stránky (Open filter/Show filter, "X items to
    # display") silně napovídá na Shoptet, ale konkrétní stránku se
    # slevami jsem nedohledal - zkusíme obecnou kategorii deskovek a
    # necháme filtr na regexu z ceny. Pokud nic nenajde, doladíme.
    ShoptetShopConfig(
        shop_name="HRAS",
        base_url="https://www.hras.cz",
        sale_paths=["/spolecenske-hry/"],
    ),
]

# ---------------------------------------------------------------------------
# XZONE - vlastní platforma, čteme přímo kategorii deskových/karetních her
# ---------------------------------------------------------------------------

XZONE_SHOPS = [
    XzoneAdapter(
        XzoneCategoryConfig(
            shop_name="Xzone",
            base_url="https://www.xzone.cz",
            category_paths=[
                "/spolecenske-hry-deskove-hry",
                "/spolecenske-hry-karetni-hry",
            ],
        )
    ),
]

# ---------------------------------------------------------------------------
# TODO - obchody, které čekají na doladění (znám URL, ne přesnou strukturu)
# ---------------------------------------------------------------------------
# Až uvidíme první ostrý běh, přidáme je stejným způsobem jako výše.
# Pro připomenutí, co už o nich víme:
#
#   Svět deskových her   https://www.svet-deskovych-her.cz/produkty/slevy
#   Domov her            https://www.domovher.cz/prices-drop
#   Svět her             https://www.svet-her.cz/Vyprodej
#   Black Lotus          https://www.blacklotus.cz/vyprodej/
#   Ostrov her           https://www.ostrov-her.cz  (nekontrolováno)
#   Najáda               https://www.najada.games  (nekontrolováno)
#   Hry do ruky          https://www.hrydoruky.cz  (nekontrolováno)
#   Myší doupě           https://www.mysidoupe.cz  (nekontrolováno)
#   Ráj deskovek         https://www.rajdeskovek.cz  (nekontrolováno)
#   Fox in the Box       https://www.foxinthebox.cz  (nekontrolováno)
#   MindOK               https://www.mindok.cz  (nekontrolováno)
#   REXhry               https://www.rexhry.cz  (nekontrolováno)
#   Albi                 https://www.albi.cz  (nekontrolováno)
#   BoardBros            https://www.boardbros.cz  (nekontrolováno)


def get_all_adapters():
    adapters = [ShoptetAdapter(cfg) for cfg in SHOPTET_SHOPS]
    adapters.extend(XZONE_SHOPS)
    return adapters
