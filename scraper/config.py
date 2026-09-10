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
        # POZOR: česká URL (/trvale-zlevneno/) i endpoint na přepnutí
        # měny (/action/Currency/...) jsou v robots.txt obchodu
        # zakázané pro roboty - respektujeme to a zůstáváme na
        # povolené anglické verzi. Měna (EUR) se přepočítává na Kč
        # v kódu, viz normalize_to_czk() v base.py.
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
    # Black Lotus - potvrzeno "Vytvořil Shoptet Premium" v patičce.
    # Sekce "VÝPRODEJ A BAZAR Deskových her" (jen deskovky, ne
    # Magic/Pokémon karty, které tenhle obchod taky prodává).
    ShoptetShopConfig(
        shop_name="Black Lotus",
        base_url="https://www.blacklotus.cz",
        sale_paths=["/vyprodej/"],
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
# ZJIŠTĚNO, ŽE NEJSOU NA SHOPTETU - běží na jiných platformách, takže náš
# ShoptetAdapter/XzoneAdapter na ně nesedne. Pro každou by šlo napsat vlastní
# malý adaptér (stejným způsobem jako xzone.py) - dej vědět, kterou chceš
# jako další, a přidám ji.
# ---------------------------------------------------------------------------
#   Svět her              svet-her.cz            platforma Simplia
#                         (sleva: https://www.svet-her.cz/Vyprodej)
#   Svět deskových her    svet-deskovych-her.cz  vlastní/custom systém
#                         (sleva: /produkty/slevy, sleva rovnou v %)
#   Ostrov her            ostrov-her.cz          platforma WEXBO
#                         (sekce "Akční nabídka", % slevy nejsou vždy vidět
#                          přímo v seznamu - možná bude nutné otevřít detail)
#   Najáda                najada.games           vlastní Nuxt.js aplikace
#                         (sleva: /discounted, spíš TCG/Magic než deskovky)
#   Hry do ruky           hrydoruky.cz           nopCommerce
#                         (cena "X Kč s DPH Y Kč s DPH" pár = sleva)
#   MindOK                mindok.cz              WordPress/WooCommerce
#                         (sleva: /nase-hry/akce-yes/)
#   Albi                  albi.cz                vlastní systém (PragueBest)
#                         (sleva: /akcni-ceny/, % je vidět jen u části zboží)
#
# NEZAŘAZENO (blokují automatizovaný přístup, respektujeme to):
#   Domov her             domovher.cz            robots.txt zakazuje botům
#                         přístup na celý web - proto ho NESCRAPUJEME.
#
# JEŠTĚ NEKONTROLOVÁNO:
#   Myší doupě     mysidoupe.cz
#   Ráj deskovek   rajdeskovek.cz
#   Fox in the Box foxinthebox.cz
#   REXhry         rexhry.cz
#   BoardBros      boardbros.cz


def get_all_adapters():
    adapters = [ShoptetAdapter(cfg) for cfg in SHOPTET_SHOPS]
    adapters.extend(XZONE_SHOPS)
    return adapters
