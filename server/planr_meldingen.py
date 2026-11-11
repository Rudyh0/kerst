"""Meldingen: één plek die bij een gebeurtenis zorgt voor de melding in de app,
de pushmelding op telefoon/computer en de e-mail."""
import datetime
import os

from planr_db import lees_tijd, nu, thema_van, tijd_tekst, voorkeuren_van
from planr_mail import in_wachtrij

SAMENVOEG_SECONDEN = 15 * 60  # ongelezen meldingen met dezelfde bundel binnen 15 min worden er één
# Alleen voor tests: PLANR_VERTRAGING=0 verstuurt gebundelde mails meteen.
VERTRAGING_FACTOR = float(os.environ.get("PLANR_VERTRAGING", "1"))


class Melder:
    def __init__(self, postbode, push):
        self.postbode = postbode
        self.push = push

    def meld(self, c, ontvangers, soort, titel, tekst="", link="", mail=None, bundel=None, viering=None,
             vertraging=0, onderwerp=None, onderwerp_bundel=None, regel=None, titel_bundel=None):
        """Stuurt een melding naar een of meer gebruikers en commit de verbinding.

        ontvangers: lijst met gebruikers-rijen (sqlite3.Row) of id's.
        mail: inhoud voor de e-mail (zie planr_mail.maak_inhoud) of None voor geen mail.
        bundel: sleutel om snelle reeksen samen te voegen (in de app, de mail én op het toestel).
        viering: de viering (rij) waar het over gaat; bepaalt thema en naam in mail en push.
        regel: de regel die bij samenvoegen onder elkaar komt (standaard de tekst).
        titel_bundel: titel als er meerdere zijn samengevoegd; {n} = aantal.
        """
        vertraging = int(vertraging * VERTRAGING_FACTOR)
        viering_id = viering["id"] if viering is not None else None
        if bundel and viering_id:
            bundel = f"v{viering_id}:{bundel}"
        if mail is not None and viering is not None:
            mail = dict(mail, viering=viering["naam"], thema=viering["thema"])
        emoji = thema_van(viering)["emoji"] if viering is not None else ""
        rijen = []
        for o in ontvangers:
            if isinstance(o, int):
                o = c.execute("SELECT * FROM gebruikers WHERE id = ?", (o,)).fetchone()
            if o is not None and o["status"] == "actief":
                rijen.append(o)
        push_lijst = []
        mail_gezet = False
        for g in rijen:
            v = voorkeuren_van(g)
            melding_titel, melding_tekst = titel, tekst
            if bundel:
                oud = c.execute(
                    "SELECT id, tekst, gemaakt FROM meldingen WHERE gebruiker_id = ? AND bundel = ? AND gelezen IS NULL "
                    "ORDER BY id DESC LIMIT 1", (g["id"], bundel)).fetchone()
                oud_tijd = lees_tijd(oud["gemaakt"]) if oud else None
                if oud and oud_tijd and nu() - oud_tijd < datetime.timedelta(seconds=SAMENVOEG_SECONDEN):
                    regels = [r for r in oud["tekst"].split("\n") if r]
                    nieuwe = regel or tekst
                    if nieuwe and nieuwe not in regels[-1:]:
                        regels.append(nieuwe)
                    regels = regels[-6:]
                    melding_tekst = "\n".join(regels)
                    if titel_bundel and len(regels) > 1:
                        melding_titel = titel_bundel.replace("{n}", str(len(regels)))
                    # Oude weghalen en opnieuw toevoegen, zodat de app hem als nieuw ziet.
                    c.execute("DELETE FROM meldingen WHERE id = ?", (oud["id"],))
                elif regel:
                    melding_tekst = regel
            c.execute(
                "INSERT INTO meldingen (gebruiker_id, viering_id, soort, titel, tekst, link, bundel, gemaakt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (g["id"], viering_id, soort, melding_titel, melding_tekst, link, bundel, tijd_tekst()),
            )
            if v["push"].get(soort, True):
                push_lijst.append((g["id"], {
                    "titel": (emoji + " " + melding_titel).strip(),
                    "tekst": melding_tekst.split("\n")[-1] if bundel else melding_tekst,
                    "link": link or "/",
                    "tag": bundel or soort,
                }))
            if mail is not None and v["mail"].get(soort, True):
                in_wachtrij(
                    c, g["email"], g["naam"], onderwerp or titel, soort, mail,
                    bundel=(f"{bundel}:{g['id']}" if bundel else None), vertraging=vertraging,
                    onderwerp_bundel=onderwerp_bundel,
                )
                mail_gezet = True
        c.commit()
        for gebruiker_id, data in push_lijst:
            self.push.stuur(gebruiker_id, data)
        if mail_gezet and vertraging == 0:
            self.postbode.wek()

    def mail(self, c, aan, naam, onderwerp, soort, inhoud, viering=None):
        """Een losse mail die niet van voorkeuren afhangt (uitnodiging, wachtwoord)."""
        if viering is not None:
            inhoud = dict(inhoud, viering=viering["naam"], thema=viering["thema"])
        in_wachtrij(c, aan, naam, onderwerp, soort, inhoud)
        c.commit()
        self.postbode.wek()
