"""
Vygeneruje docs/index.html - statickou stránku se všemi aktuálními
slevami. Tenhle soubor GitHub Pages servíruje jako běžnou webovou
stránku; na iPhonu si ji přes Safari -> "Přidat na plochu" uložíš
jako ikonku, která se otevírá na celou obrazovku jako appka.

U každé položky je odkaz "Skrýt", který založí GitHub issue - ten
zpracuje workflow handle_hide.yml a produkt příště už nenabídne.
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
  .badge.new {{
    left: auto;
    right: 8px;
    background: var(--new);
    color: #06280f;
  }}
  .card-body {{ padding: 10px 12px 12px; flex: 1; display: flex; flex-direction: column; gap: 6px; }}
  .shop {{ font-size: 0.72rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .name {{ font-size: 0.92rem; font-weight: 600; line-height: 1.25; color: var(--text); text-decoration: none; }}
  .prices {{ margin-top: auto; display: flex; align-items: baseline; gap: 6px; }}
  .price-now {{ font-size: 1.05rem; font-weight: 700; color: var(--accent); }}
  .price-old {{ font-size: 0.8rem; color: var(--muted); text-decoration: line-through; }}
  .actions {{ display: flex; gap: 8px; margin-top: 4px; }}
  .actions a {{ font-size: 0.72rem; color: var(--muted); text-decoration: none; border: 1px solid var(--card-border); border-radius: 8px; padding: 4px 8px; }}
  .actions a.hide-link:active {{ background: var(--card-border); }}
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
<div class="card">
  {new_badge}
  <span class="badge">-{discount}%</span>
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
        f"?title={title}&body={body}&labels=hide-request"
    )


def render_gallery(
    deals: list[Deal],
    is_new_map: dict[str, bool],
    github_repo: str,
    min_discount_pct: int,
    output_path: str,
) -> None:
    deals_sorted = sorted(deals, key=lambda d: d.discount_pct, reverse=True)

    if not deals_sorted:
        body = '<div class="empty">Aktuálně žádné velké slevy. Zkus to zítra 🙂</div>'
    else:
        cards = []
        for deal in deals_sorted:
            new_badge = '<span class="badge new">NOVÉ</span>' if is_new_map.get(deal.product_id) else ""
            cards.append(
                CARD_TEMPLATE.format(
                    new_badge=new_badge,
                    discount=deal.discount_pct,
                    url=html.escape(deal.url),
                    image=html.escape(deal.image_url or PLACEHOLDER_IMAGE),
                    name_attr=html.escape(deal.name),
                    shop=html.escape(deal.shop),
                    name=html.escape(deal.name),
                    price_current=_fmt_price(deal.price_current),
                    price_original=_fmt_price(deal.price_original),
                    currency=html.escape(deal.currency),
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
