"""
Vygeneruje docs/index.html - statickou stránku se všemi aktuálními
slevami. Tenhle soubor GitHub Pages servíruje jako běžnou webovou
stránku; na iPhonu si ji přes Safari -> "Přidat na plochu" uložíš
jako ikonku, která se otevírá na celou obrazovku jako appka.

U každé položky jsou dva odkazy:
  - "Skrýt"     -> založí GitHub issue, produkt se příště už nenabídne.
  - "Oblíbit"   -> založí GitHub issue, produkt se bude natrvalo řadit
                   mezi prvními (dokud oblíbenost znovu nezrušíš).

Oboje zpracuje workflow handle_actions.yml.

Řazení (odshora dolů):
  1) oblíbené položky,
  2) mezi neoblíbenými nejdřív ty NOVÉ (objevily se dnes poprvé),
  3) uvnitř každé skupiny podle výše slevy.
"""

from __future__ import annotations

import html
from datetime import datetime
from urllib.parse import quote

from .adapters import Deal

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="cs">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Slevy na deskovky</title>
<link rel="apple-touch-icon" href="icon.png">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Deskovky">
<style>
  :root {{
    --bg: #0f1115;
    --card: #1a1d24;
    --card-border: #2a2e38;
    --text: #eef0f4;
    --muted: #9aa1af;
    --accent: #ff6b4a;
    --new: #4ade80;
    --fav: #facc15;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding-bottom: 60px;
  }}
  header {{
    padding: 24px 16px 12px;
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 5;
    border-bottom: 1px solid var(--card-border);
  }}
  h1 {{ margin: 0 0 4px; font-size: 1.4rem; }}
  .subtitle {{ color: var(--muted); font-size: 0.85rem; }}
  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: 14px;
    padding: 16px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--card-border);
    border-radius: 14px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    position: relative;
  }}
  .card.is-favorite {{ border-color: var(--fav); box-shadow: 0 0 0 1px var(--fav); }}
  .card img {{
    width: 100%;
    aspect-ratio: 1 / 1;
    object-fit: contain;
    background: #fff;
  }}
  .badge {{
    position: absolute;
    top: 8px;
    left: 8px;
    background: var(--accent);
    color: #fff;
    font-weight: 700;
    font-size: 0.75rem;
    padding: 3px 8px;
    border-radius: 999px;
  }}
  .top-right-badges {{
    position: absolute;
    top: 8px;
    right: 8px;
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    gap: 4px;
  }}
  .badge.new {{ background: var(--new); color: #06280f; }}
  .badge.fav {{ background: var(--fav); color: #3a2c00; }}
  .card-body {{ padding: 10px 12px 12px; flex: 1; display: flex; flex-direction: column; gap: 6px; }}
  .shop {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .name {{ font-size: 0.92rem; font-weight: 600; line-height: 1.25; color: var(--text); text-decoration: none; }}
  .prices {{ margin-top: auto; display: flex; align-items: baseline; gap: 6px; }}
  .price-now {{ font-size: 1.05rem; font-weight: 700; color: var(--accent); }}
  .price-old {{ font-size: 0.8rem; color: var(--muted); text-decoration: line-through; }}
  .actions {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }}
  .actions a {{ font-size: 0.72rem; color: var(--muted); text-decoration: none; border: 1px solid var(--card-border); border-radius: 8px; padding: 4px 8px; }}
  .actions a.hide-link:active, .actions a.fav-link:active {{ background: var(--card-border); }}
  .actions a.fav-link.is-favorite {{ color: var(--fav); border-color: var(--fav); }}
  footer {{ text-align: center; color: var(--muted); font-size: 0.75rem; padding: 24px 16px; }}
  .empty {{ text-align: center; color: var(--muted); padding: 60px 16px; }}
</style>
</head>
<body>
<header>
  <h1>🎲 Slevy na deskovky</h1>
  <div class="subtitle">Aktualizováno {updated} &middot; {count} nabídek se slevou {min_discount}%+</div>
</header>
{body}
<footer>Generuje se automaticky každý den přes GitHub Actions.</footer>
</body>
</html>
"""

CARD_TEMPLATE = """
<div class="card{card_favorite_class}">
  <span class="badge">-{discount}%</span>
  <div class="top-right-badges">
    {new_badge}
    {fav_badge}
  </div>
  <a href="{url}" target="_blank" rel="noopener">
    <img src="{image}" alt="{name_attr}" loading="lazy" onerror="this.style.display='none'">
  </a>
  <div class="card-body">
    <div class="shop">{shop}</div>
    <a class="name" href="{url}" target="_blank" rel="noopener">{name}</a>
    <div class="prices">
      <span class="price-now">{price_current} {currency}</span>
      <span class="price-old">{price_original} {currency}</span>
    </div>
    <div class="actions">
      <a href="{url}" target="_blank" rel="noopener">Koupit ↗</a>
      <a class="fav-link{fav_link_class}" href="{fav_url}" target="_blank" rel="noopener">{fav_label}</a>
      <a class="hide-link" href="{hide_url}" target="_blank" rel="noopener">🚫 Skrýt</a>
    </div>
  </div>
</div>
"""

PLACEHOLDER_IMAGE = "https://placehold.co/300x300/1a1d24/9aa1af?text=%F0%9F%8E%B2"


def _fmt_price(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def build_hide_issue_url(github_repo: str, product_id: str, name: str) -> str:
    """
    github_repo: "uzivatel/nazev-repozitare"
    Vytvoří odkaz, který v prohlížeči rovnou předvyplní nový GitHub issue.
    Uživatel jen musí kliknout "Submit new issue" - jinak žádná akce není potřeba.
    """
    title = quote(f"hide: {product_id}")
    body = quote(f"Skrýt natrvalo: {name}\n\nID produktu: {product_id}")
    return (
        f"https://github.com/{github_repo}/issues/new"
        f"?title={title}&body={body}"
    )


def build_favorite_issue_url(github_repo: str, product_id: str, name: str) -> str:
    """Stejný princip jako u skrytí, ale přepíná stav oblíbenosti."""
    title = quote(f"favorite: {product_id}")
    body = quote(f"Přepnout oblíbenost: {name}\n\nID produktu: {product_id}")
    return (
        f"https://github.com/{github_repo}/issues/new"
        f"?title={title}&body={body}"
    )


def render_gallery(
    deals: list[Deal],
    is_new_map: dict[str, bool],
    favorites: dict,
    github_repo: str,
    min_discount_pct: int,
    output_path: str,
) -> None:
    def sort_key(d: Deal):
        is_fav = d.product_id in favorites
        is_new = is_new_map.get(d.product_id, False)
        return (not is_fav, not is_new, -d.discount_pct)

    deals_sorted = sorted(deals, key=sort_key)

    if not deals_sorted:
        body = '<div class="empty">Aktuálně žádné velké slevy. Zkus to zítra 🙂</div>'
    else:
        cards = []
        for deal in deals_sorted:
            is_fav = deal.product_id in favorites
            new_badge = '<span class="badge new">NOVÉ</span>' if is_new_map.get(deal.product_id) else ""
            fav_badge = '<span class="badge fav">★ OBLÍBENÉ</span>' if is_fav else ""
            fav_label = "★ Odebrat z oblíbených" if is_fav else "☆ Přidat mezi oblíbené"
            cards.append(
                CARD_TEMPLATE.format(
                    card_favorite_class=" is-favorite" if is_fav else "",
                    discount=deal.discount_pct,
                    url=html.escape(deal.url),
                    image=html.escape(deal.image_url or PLACEHOLDER_IMAGE),
                    name_attr=html.escape(deal.name),
                    shop=html.escape(deal.shop),
                    name=html.escape(deal.name),
                    price_current=_fmt_price(deal.price_current),
                    price_original=_fmt_price(deal.price_original),
                    currency=html.escape(deal.currency),
                    new_badge=new_badge,
                    fav_badge=fav_badge,
                    fav_link_class=" is-favorite" if is_fav else "",
                    fav_label=fav_label,
                    fav_url=build_favorite_issue_url(github_repo, deal.product_id, deal.name),
                    hide_url=build_hide_issue_url(github_repo, deal.product_id, deal.name),
                )
            )
        body = f'<div class="grid">{"".join(cards)}</div>'

    page = PAGE_TEMPLATE.format(
        updated=datetime.now().strftime("%d.%m.%Y %H:%M"),
        count=len(deals_sorted),
        min_discount=min_discount_pct,
        body=body,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(page)
