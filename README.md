# plan-r

Samen een feest plannen. Per viering (kerst met de familie, Sinterklaas met vrienden, een zomer-BBQ...) een eigen link, een eigen thema en precies de onderdelen die je nodig hebt:

- **Menu**: iedereen geeft op wat hij of zij meeneemt (per gang) en wat ze graag drinken. *Anders bepaal jij dat eem.*
- **Lootjes en verlanglijstjes**: verlanglijstje maken, lootjes trekken, het lijstje van je lootje zien, privé afvinken wat je hebt gekocht en anoniem berichtjes sturen.

Elke deelnemer krijgt een dashboard met een countdown naar de viering, het thema van die viering, de spelregels en wie er meedoen.

## Installeren

Op een Ubuntu-server (22.04 of nieuwer), als root:

```bash
curl -fsSL https://raw.githubusercontent.com/Rudyh0/kerst/main/install.sh | sudo bash
```

De installer vraagt naar het domein (standaard `kerst.rudymedia.nl`), Cloudflare, je e-mailadres als beheerder en het wachtwoord van de mailbox. Daarna regelt hij nginx, HTTPS (Let's Encrypt of Cloudflare), een vrije poort, de firewall, nachtelijke back-ups en automatische updates.

Hij kan naast Marble Tycoon en "... en de Duitse streken" op dezelfde server draaien: eigen namen, eigen poort, geen standaardsite in nginx, en hij controleert dat het domein nog vrij is.

Aan het eind krijg je een link om je wachtwoord te kiezen. Daarna: **Beheer → Nieuwe viering**.

Opties (allemaal optioneel):

| Optie | Betekenis |
| --- | --- |
| `--domein NAAM` | domeinnaam |
| `--cloudflare ja\|nee` | loopt het domein via Cloudflare met de proxy aan? |
| `--email ADRES` | e-mailadres voor Let's Encrypt |
| `--beheerder ADRES` / `--naam NAAM` | de beheerder (eerste installatie) |
| `--smtp-host` / `--smtp-gebruiker` | mailserver (standaard `mail.rudymedia.nl` / `kerst@rudymedia.nl`) |
| `--autoupdate ja\|nee` | elke 10 minuten nieuwe versies van GitHub halen |
| `--ja` | geen vragen stellen |
| `--verwijder` | weer verwijderen |

Nog een keer draaien = bijwerken; instellingen en gegevens blijven staan.

Handige commando's op de server:

```bash
sudo plan-r-update                          # nu meteen bijwerken
sudo plan-r-beheerder jij@voorbeeld.nl      # beheerder toevoegen of wachtwoord herstellen
sudo -u plan-r python3 /opt/plan-r/dienst/planr.py status --db /var/lib/plan-r/planr.db
journalctl -u plan-r-server                 # logboek
```

## Hoe het werkt

**Vieringen.** De beheerder maakt een viering met een zelfgekozen link (`kerst.rudymedia.nl/familie`), datum, tijd, locatie, welkomstbericht, thema en onderdelen. Bij lootjes horen spelregels: maximale prijs, wel/geen gedicht, wel/geen surprise en eigen regels. Alles is later aan te passen; met één vinkje krijgt iedereen een melding van de wijziging.

**Thema's.** Standaard, Kerst, Sinterklaas, Zomer en Halloween. Het thema bepaalt kleuren, logo, animaties (sneeuw, pepernoten, bubbels, vonken) en hoe de anonieme gever heet (je geheime kerstengel, de Sint, je geheime geest...). Licht en donker werken in elk thema.

**Accounts.** Eén account per e-mailadres, ook als iemand bij meerdere vieringen hoort. Wie al een account heeft, doet met één klik mee met een nieuwe viering. Het menu, het verlanglijstje en de lootjes zijn per viering.

**Lootjes.** Trekken kan zodra iedereen zich heeft aangemeld (of bewust met alleen wie er al is). Niemand trekt zichzelf. Ook de beheerder ziet niet wie wie heeft. Opnieuw trekken en ongedaan maken kan ook.

**Meldingen.** Bij elke wijziging (lootjes getrokken, aangepast verlanglijstje van je lootje, nieuw bericht, iets nieuws op het menu, nieuwe datum...) krijg je:

- een melding in de app (belletje, met een toast als de app open staat),
- een pushmelding op je telefoon of computer (Web Push; op iPhone na 'Zet op beginscherm'),
- een e-mail.

Per soort kun je mail en push aan- of uitzetten. Snelle reeksen (vijf wensen achter elkaar) worden gebundeld tot één mail en één pushmelding.

**E-mail.** Mailserver, poort, beveiliging, gebruikersnaam, wachtwoord, afzendernaam en afzenderadres stel je in bij **Beheer → E-mail**, met een knop voor een testmail en een overzicht van verstuurde en mislukte mails. Mails gaan via een wachtrij en worden bij een storing later opnieuw geprobeerd. Het mailwachtwoord staat alleen in de database op de server, nooit in deze repository.

## Techniek

- `server/`: Python 3 (alleen de standaardbibliotheek) met SQLite. `python3-cryptography` is nodig voor pushmeldingen; zonder dat pakket werkt de rest gewoon.
- `web/`: de app zelf, gewone HTML/CSS/JavaScript-modules zonder bouwstap. Stijl gebaseerd op Afterfeed (Geist-letter).
- nginx serveert `web/` en stuurt `/api/` door naar de server op 127.0.0.1.

Lokaal proberen:

```bash
python3 tests/demo.py /tmp/demo.db
python3 server/planr.py serveer --db /tmp/demo.db --poort 8000 --url http://localhost:8000 --statisch web
# open http://localhost:8000 en log in met rudy@example.nl / demo-wachtwoord
```

Testen:

```bash
python3 tests/test_api.py   # start de server en een nep-mailserver en speelt een paar vieringen na
```

Veiligheid in het kort: wachtwoorden met PBKDF2 (480.000 rondes), sessies in een HttpOnly-cookie, een extra kop tegen CSRF, limieten op inloggen en versturen, een strikte Content-Security-Policy, pushmeldingen alleen naar de bekende pushdiensten, en de dienst draait als eigen gebruiker met systemd-afscherming.

Het lettertype Geist valt onder de SIL Open Font License (zie `web/fonts/GEIST-LICENSE.txt`).
