"""
Spouští ho .github/workflows/handle_hide.yml, kdykoliv vznikne nové
issue se štítkem "hide-request" (to se stane po kliknutí na odkaz
"Skrýt" v galerii nebo v e-mailu).

Očekává, že GitHub Actions předá název a tělo issue přes proměnné
prostředí ISSUE_TITLE a ISSUE_BODY (viz workflow soubor).

Formát názvu issue: "hide: <product_id>"
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper import storage  # noqa: E402

TITLE_RE = re.compile(r"hide:\s*([a-f0-9]{16})", re.IGNORECASE)
NAME_RE = re.compile(r"Skrýt natrvalo:\s*(.+)")


def main() -> None:
    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")

    match = TITLE_RE.search(title)
    if not match:
        print(f"Nepodařilo se najít product_id v názvu issue: {title!r}")
        sys.exit(1)

    product_id = match.group(1)
    name_match = NAME_RE.search(body)
    name = name_match.group(1).strip() if name_match else ""

    storage.hide_product(product_id, name)
    print(f"Skryto natrvalo: {name or product_id} ({product_id})")


if __name__ == "__main__":
    main()
