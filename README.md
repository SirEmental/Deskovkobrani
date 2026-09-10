# 🎲 Slevy na deskovky

Každý den automaticky projede vybrané české e-shopy s deskovými hrami,
najde produkty se slevou 30 %+ a:

- vygeneruje webovou galerii (foto, cena, odkaz), kterou si na iPhonu
  přidáš na plochu a chová se skoro jako appka,
- pošle e-mail o nových slevách (jen o nových, ať tě to neotravuje
  pořád dokola tím samým),
- pamatuje si, co jsi označil jako "už mě nezajímá" a příště to
  vynechá.

Běží to zadarmo na GitHub Actions - tvůj počítač ani telefon k tomu
nemusí být zapnutý.

---

## 1. Založení repozitáře

1. Na [github.com](https://github.com) klikni na **New repository**.
2. Dej mu libovolné jméno, např. `boardgame-deals`. Klidně **Private**
   (do 2000 minut běhu měsíčně zdarma, my potřebujeme řádově desítky).
3. Nahraj do něj obsah téhle složky (buď přes web rozhraní "uploading
   an existing file", nebo přes git - viz níže).

```bash
cd boardgame-deals
git init
git add .
git commit -m "Prvni verze"
git branch -M main
git remote add origin https://github.com/TVOJE-JMENO/boardgame-deals.git
git push -u origin main
```

## 2. Nastavení e-mailu (Gmail)

Doporučuju založit si pro tohle samostatné "App Password" ke svému
Gmailu (ne svoje běžné heslo):

1. Na Gmail účtu musíš mít zapnuté dvoufázové ověření
   ([myaccount.google.com/security](https://myaccount.google.com/security)).
2. Tam najdi **Aplikační hesla** (App passwords) a vytvoř nové
   (např. pro "boardgame-deals"). Dostaneš 16místný kód.
3. V repozitáři na GitHubu jdi do **Settings → Secrets and variables
   → Actions → New repository secret** a přidej:
   - `EMAIL_ADDRESS` = tvoje Gmail adresa
   - `EMAIL_APP_PASSWORD` = ten 16místný kód z kroku 2
   - `RECIPIENT_EMAIL` = kam se má posílat (klidně stejná adresa)

(Nepoužíváš Gmail? Funguje to s jakýmkoliv SMTP - stačí v souboru
`scraper/send_email.py` změnit `SMTP_HOST`/`SMTP_PORT` na údaje svého
poskytovatele.)

## 3. Zapnutí GitHub Pages (webová galerie)

**Settings → Pages** → pod "Build and deployment" vyber:
- Source: **Deploy from a branch**
- Branch: **main**, složka **/docs**

Po pár minutách bude galerie dostupná na
`https://TVOJE-JMENO.github.io/boardgame-deals/`.

Na iPhonu tuhle adresu otevři v **Safari** → tlačítko sdílení (čtvereček
se šipkou) → **Přidat na plochu**. Dostaneš ikonku, která se otevírá
na celou obrazovku bez adresního řádku.

## 4. První spuštění

V repozitáři na GitHubu jdi do záložky **Actions**, vyber workflow
"Denní kontrola slev" a klikni **Run workflow** (tlačítko vpravo) -
nemusíš čekat na naplánovaný čas. Během minuty by se mělo objevit
zeleně odškrtnuté a `docs/index.html` i `data/seen.json` by se měly
v repozitáři aktualizovat.

Pokud něco selže, otevři si detail běhu a podívej se do logu - u
každého obchodu se loguje, kolik slev našel (nebo proč selhal).

## Jak funguje "Skrýt" a "Oblíbené"

U každé položky v galerii/e-mailu jsou dva odkazy:

- **🚫 Skrýt** – založí GitHub issue, produkt se příště už nezobrazí.
- **☆ Přidat mezi oblíbené / ★ Odebrat z oblíbených** – založí GitHub
  issue, který přepne, jestli je produkt "oblíbený". Oblíbené položky
  se v galerii i e-mailu vždy řadí úplně nahoru (mají žlutý rámeček),
  dokud oblíbenost sám nezrušíš stejným tlačítkem.

Oba odkazy fungují stejně - otevřou v prohlížeči rovnou předvyplněné
nové GitHub issue, stačí kliknout **Submit new issue** (jsi přihlášený
do svého repozitáře, žádné další heslo netřeba). Do minuty to zpracuje
druhý workflow. Issue se pak samo zavře s potvrzením.

**Řazení v galerii/e-mailu:** 1) oblíbené položky, 2) mezi ostatními
nejdřív ty NOVÉ (objevily se dnes poprvé), 3) uvnitř každé skupiny
podle výše slevy.

## Přidání dalšího obchodu

Otevři `scraper/config.py`. Pokud je nový obchod na platformě Shoptet
(pozná se podle "Shoptet" v patičce stránky), stačí přidat pár řádků:

```python
ShoptetShopConfig(
    shop_name="Nazev obchodu",
    base_url="https://www.example.cz",
    sale_paths=["/cesta-ke-slevam/"],
),
```

V `config.py` je dole seznam obchodů na jiných platformách (Simplia,
WEXBO, nopCommerce, WooCommerce, vlastní systémy...) - pro každý by
šlo napsat malý adaptér stejným způsobem jako pro Xzone. Napiš mi,
který chceš jako další, a přidám ho. Jeden obchod (Domov her) má v
`robots.txt` výslovný zákaz pro roboty, takže ho záměrně nescrapujeme.

## Omezení, o kterých bys měl vědět

- **Web scraping vždy trochu křehká věc.** Když si obchod předělá
  web, scraper pro něj přestane fungovat, dokud selektory nedoladíme.
  Kód je napsaný tak, aby pád jednoho obchodu nespadl celý běh (jen
  se to zaloguje).
- Respektuje se rozumné tempo dotazů (prodleva mezi requesty), ať
  žádný obchod zbytečně nezatěžujeme.
- Tohle je pro osobní použití. Pokud by ti to obchod vyloženě
  zakazoval v podmínkách používání, respektuj to.
