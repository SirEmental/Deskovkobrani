"""
Seznam sledovaných obchodů.

Přidat nový Shoptet obchod je otázka pár řádků - stačí najít jeho
kategorii/stránku se slevami (v adminu shopu se obvykle jmenuje
"Akce a slevy", "Výprodej" nebo podobně) a přidat ShoptetShopConfig.

MIN_DISCOUNT_PCT: výchozí práh, od kolika % slevy se položka počítá
za "velkou slevu". Dá se přebít i za běhu (viz main.py / env proměnná).
"""

from .adapters import (
    AlzaAdapter,
    AlzaShopConfig,
    ShoptetAdapter,
    ShoptetShopConfig,
    WooCommerceAdapter,
    WooCommerceShopConfig,
    XzoneAdapter,
    XzoneCategoryConfig,
)

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
    # HRAS.cz - POZOR: dočasně VYPNUTO. Potvrzený Shoptet a skutečnou
    # "Akce" stránku jsem našel (?dd=1, 236 položek v ní), ale stejně
    # jako Black Lotus ukazuje jen finální cenu, BEZ původní ceny/%
    # slevy - není z čeho počítat.
    # ShoptetShopConfig(
    #     shop_name="HRAS",
    #     base_url="https://www.hras.cz",
    #     sale_paths=["/spolecenske-hry/?dd=1"],
    # ),
    # Black Lotus - POZOR: dočasně VYPNUTO. Je to sice potvrzený Shoptet,
    # ale jejich "VÝPRODEJ A BAZAR" sekce ukazuje jen finální cenu
    # (např. "999 Kč"), BEZ původní ceny nebo % slevy - není tedy z čeho
    # slevu spočítat, aniž by se musela stahovat stránka každého produktu
    # zvlášť (výrazně pomalejší a náročnější). Necháváme configuraci
    # tady pro budoucí použití, kdyby se to řešení rozšířilo.
    # ShoptetShopConfig(
    #     shop_name="Black Lotus",
    #     base_url="https://www.blacklotus.cz",
    #     sale_paths=["/vyprodej/"],
    # ),
]

# ---------------------------------------------------------------------------
# XZONE - VYPNUTO na žádost uživatele. Blokuje požadavky z GitHub Actions
# (timeouty), takže to bylo jen zbytečné čekání bez výsledku.
# ---------------------------------------------------------------------------

XZONE_SHOPS = []
# Původní konfigurace pro budoucí použití, kdyby se blokace vyřešila:
# XzoneAdapter(
#     XzoneCategoryConfig(
#         shop_name="Xzone",
#         base_url="https://www.xzone.cz",
#         category_paths=[
#             "/spolecenske-hry-deskove-hry",
#             "/spolecenske-hry-karetni-hry",
#         ],
#     )
# ),

# ---------------------------------------------------------------------------
# ALZA - vlastní velký systém. Detaily viz komentář v adapters/alza.py -
# stručně: řeší klasické slevy, "Cenová bomba", slevové kódy (i jejich
# kombinaci s klasickou slevou) a AlzaPlus+ ceny (označené poznámkou, že
# vyžadují členství). "Alza Benefit" záměrně vynechán - cena je schovaná
# za přihlášení + neveřejný aktivační kód, není co scrapovat.
# ---------------------------------------------------------------------------

ALZA_SHOPS = [
    AlzaShopConfig(
        shop_name="Alza",
        base_url="https://www.alza.cz",
        sale_paths=[
            "/hracky/spolecenske-deskove-hry/vyprodej-akce-sleva/18857192-e0.htm",
        ],
    ),
]

# ---------------------------------------------------------------------------
# WOOCOMMERCE - další velmi rozšířená platforma, potvrzeno u dvou obchodů
# ---------------------------------------------------------------------------

WOOCOMMERCE_SHOPS = [
    WooCommerceShopConfig(
        shop_name="MindOK",
        base_url="https://mindok.cz",
        sale_paths=["/nase-hry/akce-yes/"],
    ),
    WooCommerceShopConfig(
        shop_name="BoardBros",
        base_url="https://boardbros.cz",
        # Nemají samostatnou "jen slevy" stránku - filtrujeme podle
        # přítomnosti <del>/<ins> přímo v kódu adaptéru, takže stačí
        # projet celý obchod. Je jich málo (jedno vydavatelství), takže
        # to není velký objem stránek.
        sale_paths=["/obchod/"],
    ),
]

# ---------------------------------------------------------------------------
# ZJIŠTĚNO, ŽE NEJSOU NA SHOPTETU ANI WOOCOMMERCE - běží na dalších
# platformách, na které zatím nemáme adaptér. Dej vědět, kterou chceš
# jako další, a napíšu pro ni malý adaptér (stejným způsobem jako
# xzone.py/woocommerce.py).
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
#   Albi                  albi.cz                vlastní systém (PragueBest)
#                         (sleva: /akcni-ceny/, % je vidět jen u části zboží)
#   Fox in the Box        foxinthebox.cz         OpenCart, nenašel jsem
#                         aktuálně aktivní slevovou sekci
#   Myší doupě            mysidoupe.cz (.eu)     Shoptet, ale AKTUÁLNĚ 0
#                         položek se slevou u deskovek (prodávají hlavně
#                         doplňky/inserty)
#
# NEZAŘAZENO (blokují automatizovaný přístup, respektujeme to):
#   Domov her             domovher.cz            robots.txt zakazuje botům
#                         přístup na celý web
#   Ráj deskovek          rajdeskovek.cz         robots.txt zakazuje botům
#   REXhry                rexhry.cz              aktivní detekce botů
#                         (podobný problém jako Xzone)


def get_all_adapters():
    adapters = [ShoptetAdapter(cfg) for cfg in SHOPTET_SHOPS]
    adapters.extend(WooCommerceAdapter(cfg) for cfg in WOOCOMMERCE_SHOPS)
    adapters.extend(AlzaAdapter(cfg) for cfg in ALZA_SHOPS)
    adapters.extend(XZONE_SHOPS)
    return adapters
