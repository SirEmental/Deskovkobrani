"""
Pošle jeden denní e-mail s NOVÝMI slevami (aby ti chodil e-mail jen
když se opravdu něco nového objeví, ne pořád dokola o tom stejném).
Kompletní přehled všech aktuálních slev je vždy na webové galerii.

Použití: Gmail SMTP + "App Password" (viz README, sekce Nastavení).
Přihlašovací údaje se čtou z proměnných prostředí (v GitHub Actions
z "Secrets", takže nikde nejsou vidět natvrdo v kódu):
    EMAIL_ADDRESS        - odesílající Gmail adresa
    EMAIL_APP_PASSWORD   - vygenerované heslo pro aplikace
    RECIPIENT_EMAIL      - kam se má e-mail posílat (může být stejná adresa)
"""

from __future__ import annotations

import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .adapters import Deal
from .render_html import PLACEHOLDER_IMAGE, build_favorite_issue_url, build_hide_issue_url

logger = logging.getLogger("boardgame_deals")

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

EMAIL_TEMPLATE = """\
<html>
<body style="font-family: -apple-system, Arial, sans-serif; background:#f4f4f6; margin:0; padding:24px;">
  <div style="max-width:600px; margin:0 auto;">
    <h2 style="margin-bottom:4px;">🎲 Nové slevy na deskovky</h2>
    <p style="color:#666; margin-top:0;">{count} nových nabídek se slevou {min_discount}%+</p>
    {items}
    <p style="text-align:center; margin-top:24px;">
      <a href="{gallery_url}" style="color:#ff6b4a;">Zobrazit všechny aktuální slevy →</a>
    </p>
  </div>
</body>
</html>
"""

ITEM_TEMPLATE = """
<table role="presentation" width="100%" style="background:#fff; border-radius:12px; margin-bottom:12px; overflow:hidden;">
  <tr>
    <td width="100" style="padding:0;">
      <a href="{url}"><img src="{image}" width="100" height="100" style="object-fit:contain; background:#fff; display:block;"></a>
    </td>
    <td style="padding:12px; vertical-align:top;">
      <div style="font-size:11px; color:#999; text-transform:uppercase;">{shop}</div>
      <a href="{url}" style="font-size:15px; font-weight:600; color:#222; text-decoration:none;">{fav_star}{name}</a><br>
      <span style="color:#ff6b4a; font-weight:700;">{price_current} {currency}</span>
      <span style="color:#999; text-decoration:line-through; font-size:13px;">{price_original} {currency}</span>
      <span style="color:#fff; background:#ff6b4a; font-size:12px; font-weight:700; padding:1px 6px; border-radius:6px;">-{discount}%</span>
      {note_html}
      <br>
      <a href="{fav_url}" style="font-size:12px; color:#c9a300;">{fav_label}</a>
      &nbsp;·&nbsp;
      <a href="{hide_url}" style="font-size:12px; color:#999;">🚫 Skrýt natrvalo</a>
    </td>
  </tr>
</table>
"""


def _fmt_price(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def build_email_html(
    new_deals: list[Deal], favorites: dict, github_repo: str, gallery_url: str, min_discount_pct: int
) -> str:
    def sort_key(d: Deal):
        is_fav = d.product_id in favorites
        return (not is_fav, -d.discount_pct)

    items_html = []
    for deal in sorted(new_deals, key=sort_key):
        is_fav = deal.product_id in favorites
        note_html = (
            f'<br><span style="font-size:11px; color:#a67c00; background:#fff8e1; '
            f'padding:1px 6px; border-radius:6px;">ℹ️ {html.escape(deal.note)}</span>'
            if deal.note
            else ""
        )
        items_html.append(
            ITEM_TEMPLATE.format(
                url=html.escape(deal.url),
                image=html.escape(deal.image_url or PLACEHOLDER_IMAGE),
                shop=html.escape(deal.shop),
                fav_star="★ " if is_fav else "",
                name=html.escape(deal.name),
                price_current=_fmt_price(deal.price_current),
                price_original=_fmt_price(deal.price_original),
                currency=html.escape(deal.currency),
                discount=deal.discount_pct,
                note_html=note_html,
                fav_label="★ Odebrat z oblíbených" if is_fav else "☆ Přidat mezi oblíbené",
                fav_url=build_favorite_issue_url(github_repo, deal.product_id, deal.name),
                hide_url=build_hide_issue_url(github_repo, deal.product_id, deal.name),
            )
        )
    return EMAIL_TEMPLATE.format(
        count=len(new_deals),
        min_discount=min_discount_pct,
        items="".join(items_html),
        gallery_url=html.escape(gallery_url),
    )


def send_email(subject: str, html_body: str) -> bool:
    sender = os.environ.get("EMAIL_ADDRESS")
    password = os.environ.get("EMAIL_APP_PASSWORD")
    recipient = os.environ.get("RECIPIENT_EMAIL", sender)

    if not sender or not password:
        logger.warning("EMAIL_ADDRESS / EMAIL_APP_PASSWORD nejsou nastavené - e-mail se neposílá.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [recipient], msg.as_string())
        logger.info("E-mail odeslán na %s", recipient)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("Odeslání e-mailu selhalo: %s", exc)
        return False
