"""E-mail: opmaak, wachtrij en de postbode die op de achtergrond verstuurt.

Mails gaan altijd via de wachtrij in de database. Zo blijft de app snel, wordt
een mislukte mail later opnieuw geprobeerd en kunnen snelle wijzigingen achter
elkaar (vijf wensen toevoegen) in één mail worden gebundeld.
"""
import datetime
import email.utils
import html
import json
import smtplib
import ssl
import sys
import threading
from email.message import EmailMessage

from planr_db import THEMAS, instelling, instellingen, lees_tijd, nu, over, tijd_tekst

MAX_POGINGEN = 8
WACHTTIJDEN = [60, 300, 900, 1800, 3600, 7200, 14400, 28800]
MAX_BUNDEL_WACHT = 600  # een bundel wacht nooit langer dan 10 minuten


def smtp_instellingen(c):
    inst = instellingen(c, [
        "smtp_host", "smtp_poort", "smtp_beveiliging", "smtp_controleer", "smtp_gebruiker",
        "smtp_wachtwoord", "afzender_naam", "afzender_adres", "app_naam",
    ])
    try:
        inst["smtp_poort"] = int(inst["smtp_poort"] or 587)
    except ValueError:
        inst["smtp_poort"] = 587
    if not inst["afzender_adres"]:
        inst["afzender_adres"] = inst["smtp_gebruiker"]
    return inst


def smtp_klaar(inst):
    return bool(inst["smtp_host"] and inst["afzender_adres"])


def open_smtp(inst):
    host, poort = inst["smtp_host"], inst["smtp_poort"]
    ctx = ssl.create_default_context()
    if inst["smtp_controleer"] != "1":
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    if inst["smtp_beveiliging"] == "ssl":
        s = smtplib.SMTP_SSL(host, poort, timeout=25, context=ctx)
    else:
        s = smtplib.SMTP(host, poort, timeout=25)
        s.ehlo()
        if inst["smtp_beveiliging"] == "starttls":
            s.starttls(context=ctx)
            s.ehlo()
    if inst["smtp_gebruiker"]:
        s.login(inst["smtp_gebruiker"], inst["smtp_wachtwoord"])
    return s


# --------------------------------------------------------------------------- opmaak

LETTER = "Geist, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"


def _alinea(tekst):
    return html.escape(tekst).replace("\n", "<br>")


def maak_inhoud(inhoud, site_url, app_naam):
    """inhoud: {kop, intro, regels[], stijl: lijst|citaten, knop_tekst, knop_pad, voet, viering, thema}"""
    thema = THEMAS.get(inhoud.get("thema") or "standaard", THEMAS["standaard"])
    kleur = thema["kleur"]
    evenement = inhoud.get("viering") or app_naam
    kop = inhoud.get("kop", "")
    intro = inhoud.get("intro", "")
    regels = inhoud.get("regels") or []
    stijl = inhoud.get("stijl", "lijst")
    knop_tekst = inhoud.get("knop_tekst", "")
    knop_url = (site_url.rstrip("/") + inhoud["knop_pad"]) if inhoud.get("knop_pad") else inhoud.get("knop_url", "")
    voet = inhoud.get("voet") or (
        f"Je krijgt deze mail omdat je meedoet aan {evenement}. "
        f"Welke mails je krijgt, stel je in bij Instellingen: {site_url.rstrip('/')}/instellingen"
    )

    # Platte tekst
    delen = [kop, ""]
    if intro:
        delen += [intro, ""]
    for r in regels:
        if stijl == "citaten":
            delen += ["> " + r.replace("\n", "\n> "), ""]
        else:
            delen.append("- " + r)
    if regels and stijl != "citaten":
        delen.append("")
    if knop_url:
        delen += [f"{knop_tekst or 'Openen'}: {knop_url}", ""]
    delen += ["--", voet]
    tekst = "\n".join(delen)

    # HTML
    blokken = []
    if intro:
        blokken.append(f'<p style="margin:0 0 16px;font-size:15px;line-height:1.55;color:#3a3c42;">{_alinea(intro)}</p>')
    if regels:
        if stijl == "citaten":
            for r in regels:
                blokken.append(
                    '<div style="margin:0 0 10px;padding:12px 14px;border-radius:12px;background:#f3efe9;'
                    f'font-size:15px;line-height:1.5;color:#17181c;">{_alinea(r)}</div>'
                )
        else:
            items = "".join(f'<li style="margin:0 0 6px;">{_alinea(r)}</li>' for r in regels)
            blokken.append(f'<ul style="margin:0 0 16px;padding-left:20px;font-size:15px;line-height:1.5;color:#17181c;">{items}</ul>')
    if knop_url:
        blokken.append(
            '<p style="margin:20px 0 4px;"><a href="%s" style="display:inline-block;padding:12px 20px;border-radius:10px;'
            'background:%s;color:#ffffff;font-size:15px;font-weight:600;text-decoration:none;">%s</a></p>'
            % (html.escape(knop_url, quote=True), kleur, html.escape(knop_tekst or "Openen"))
        )
    inhoud_html = f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light"><title>{html.escape(kop)}</title></head>
<body style="margin:0;padding:0;background:#f6f3ee;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f6f3ee;">
<tr><td align="center" style="padding:32px 14px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:520px;background:#ffffff;border:1px solid #e8e2d9;border-radius:16px;">
<tr><td style="height:6px;line-height:6px;font-size:0;background:{kleur};border-radius:16px 16px 0 0;">&nbsp;</td></tr>
<tr><td style="padding:26px 28px 6px;font-family:{LETTER};">
<p style="margin:0 0 14px;font-size:14px;font-weight:600;color:{kleur};">{thema['emoji']} {html.escape(evenement)}</p>
<h1 style="margin:0 0 14px;font-size:22px;line-height:1.25;font-weight:600;color:#17181c;">{html.escape(kop)}</h1>
{''.join(blokken)}
</td></tr>
<tr><td style="padding:18px 28px 26px;font-family:{LETTER};font-size:12px;line-height:1.5;color:#7a7d85;">{_alinea(voet)}</td></tr>
</table>
</td></tr></table>
</body></html>"""
    return tekst, inhoud_html


def maak_bericht(inst, aan, naam, onderwerp, tekst, inhoud_html):
    m = EmailMessage()
    m["From"] = email.utils.formataddr((inst["afzender_naam"] or inst["app_naam"], inst["afzender_adres"]))
    m["To"] = email.utils.formataddr((naam, aan)) if naam else aan
    m["Subject"] = onderwerp
    m["Date"] = email.utils.formatdate(localtime=True)
    domein = inst["afzender_adres"].split("@")[-1] or None
    m["Message-ID"] = email.utils.make_msgid(domain=domein)
    m["Auto-Submitted"] = "auto-generated"
    m.set_content(tekst)
    m.add_alternative(inhoud_html, subtype="html")
    return m


# --------------------------------------------------------------------------- wachtrij

def in_wachtrij(c, aan, naam, onderwerp, soort, inhoud, bundel=None, vertraging=0, onderwerp_bundel=None):
    """Zet een mail klaar. Met een bundel-sleutel worden mails die nog wachten samengevoegd.

    Bij samenvoegen worden de regels achter elkaar gezet; onderwerp_bundel mag {n} bevatten
    (het aantal regels)."""
    if bundel:
        r = c.execute(
            "SELECT id, data, gemaakt FROM mail_wachtrij WHERE bundel = ? AND aan = ? AND status = 'wacht' ORDER BY id DESC LIMIT 1",
            (bundel, aan),
        ).fetchone()
        if r:
            data = json.loads(r["data"])
            regels = data.get("regels") or []
            for regel in inhoud.get("regels") or []:
                if regel not in regels or data.get("stijl") == "citaten":
                    regels.append(regel)
            data["regels"] = regels[-40:]
            n = str(len(data["regels"]))
            for k in ("kop", "intro", "knop_tekst", "knop_pad"):
                if k + "_bundel" in inhoud:
                    data[k] = inhoud[k + "_bundel"].replace("{n}", n)
                elif k in inhoud:
                    data[k] = inhoud[k]
            nieuw_onderwerp = (onderwerp_bundel or onderwerp).replace("{n}", n)
            gemaakt = lees_tijd(r["gemaakt"]) or nu()
            uiterlijk = gemaakt + datetime.timedelta(seconds=MAX_BUNDEL_WACHT)
            wanneer = min(uiterlijk, nu() + datetime.timedelta(seconds=vertraging))
            c.execute(
                "UPDATE mail_wachtrij SET data = ?, onderwerp = ?, verstuur_na = ? WHERE id = ?",
                (json.dumps(data, ensure_ascii=False), nieuw_onderwerp, tijd_tekst(wanneer), r["id"]),
            )
            return r["id"]
    cur = c.execute(
        "INSERT INTO mail_wachtrij (aan, naam, onderwerp, soort, bundel, data, verstuur_na, gemaakt) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (aan, naam, onderwerp.replace("{n}", str(len(inhoud.get("regels") or []))), soort, bundel,
         json.dumps(inhoud, ensure_ascii=False), over(vertraging), tijd_tekst()),
    )
    return cur.lastrowid


class Postbode(threading.Thread):
    """Verstuurt de mails uit de wachtrij, met nieuwe pogingen als het misgaat."""

    def __init__(self, db, site_url):
        super().__init__(daemon=True, name="postbode")
        self.db = db
        self.site_url = site_url
        self.wekker = threading.Event()

    def wek(self):
        self.wekker.set()

    def run(self):
        while True:
            try:
                while self.ronde():
                    pass
            except Exception as e:  # noqa: BLE001
                print(f"[plan-r] postbode: {e!r}", file=sys.stderr, flush=True)
            self.wekker.wait(5)
            self.wekker.clear()

    def ronde(self):
        """Verstuurt wat klaarstaat. Geeft True terug als er misschien nog meer ligt."""
        c = self.db.open()
        try:
            rijen = c.execute(
                "SELECT * FROM mail_wachtrij WHERE status = 'wacht' AND verstuur_na <= ? ORDER BY id LIMIT 20",
                (tijd_tekst(),),
            ).fetchall()
            if not rijen:
                return False
            inst = smtp_instellingen(c)
            if not smtp_klaar(inst):
                c.execute(
                    "UPDATE mail_wachtrij SET verstuur_na = ?, fout = 'De mailserver is nog niet ingesteld (Beheer, E-mail).' "
                    "WHERE status = 'wacht' AND verstuur_na <= ?", (over(120), tijd_tekst()))
                c.commit()
                return False
            ids = [r["id"] for r in rijen]
            c.execute(f"UPDATE mail_wachtrij SET status = 'bezig' WHERE id IN ({','.join('?' * len(ids))})", ids)
            c.commit()
            # Lees opnieuw: een bundel kan net voor het vastzetten nog zijn aangevuld.
            rijen = c.execute(f"SELECT * FROM mail_wachtrij WHERE id IN ({','.join('?' * len(ids))}) ORDER BY id", ids).fetchall()
            app_naam = instelling(c, "app_naam", "plan-r")
            try:
                server = open_smtp(inst)
            except Exception as e:  # noqa: BLE001
                for r in rijen:
                    self.mislukt(c, r, e)
                c.commit()
                return False
            try:
                for r in rijen:
                    try:
                        tekst, inhoud_html = maak_inhoud(json.loads(r["data"]), self.site_url, app_naam)
                        server.send_message(maak_bericht(inst, r["aan"], r["naam"], r["onderwerp"], tekst, inhoud_html))
                        c.execute("UPDATE mail_wachtrij SET status = 'verstuurd', verstuurd = ?, fout = '' WHERE id = ?",
                                  (tijd_tekst(), r["id"]))
                    except (smtplib.SMTPServerDisconnected, OSError) as e:
                        self.mislukt(c, r, e)
                        raise
                    except Exception as e:  # noqa: BLE001
                        self.mislukt(c, r, e)
                    c.commit()
            except (smtplib.SMTPServerDisconnected, OSError):
                c.execute(f"UPDATE mail_wachtrij SET status = 'wacht' WHERE status = 'bezig' AND id IN ({','.join('?' * len(ids))})", ids)
                c.commit()
                return False
            finally:
                try:
                    server.quit()
                except Exception:  # noqa: BLE001
                    pass
            # Oude verstuurde mails opruimen (na 60 dagen).
            c.execute("DELETE FROM mail_wachtrij WHERE status = 'verstuurd' AND verstuurd < ?", (over(-60 * 86400),))
            c.commit()
            return len(rijen) == 20
        finally:
            c.close()

    def mislukt(self, c, r, fout):
        pogingen = r["pogingen"] + 1
        melding = (f"{type(fout).__name__}: {fout}")[:400]
        if pogingen >= MAX_POGINGEN:
            c.execute("UPDATE mail_wachtrij SET status = 'mislukt', pogingen = ?, fout = ? WHERE id = ?", (pogingen, melding, r["id"]))
        else:
            wacht = WACHTTIJDEN[min(pogingen - 1, len(WACHTTIJDEN) - 1)]
            c.execute("UPDATE mail_wachtrij SET status = 'wacht', pogingen = ?, fout = ?, verstuur_na = ? WHERE id = ?",
                      (pogingen, melding, over(wacht), r["id"]))
        print(f"[plan-r] mail naar {r['aan']} mislukt (poging {pogingen}): {melding}", file=sys.stderr, flush=True)


def verstuur_direct(c, site_url, aan, inhoud, onderwerp):
    """Voor de testmail in het beheer: meteen versturen en de fout teruggeven."""
    inst = smtp_instellingen(c)
    if not smtp_klaar(inst):
        raise ValueError("Vul eerst de mailserver en het afzenderadres in.")
    tekst, inhoud_html = maak_inhoud(inhoud, site_url, inst["app_naam"] or "plan-r")
    server = open_smtp(inst)
    try:
        server.send_message(maak_bericht(inst, aan, "", onderwerp, tekst, inhoud_html))
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            pass
