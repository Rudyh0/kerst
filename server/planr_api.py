"""HTTP: de JSON-API onder /api/ (nginx stuurt die door naar deze dienst).

Opbouw:
  /api/...                  account, meldingen, push (iedereen die is ingelogd)
  /api/v/<link>/...         alles binnen één viering (alleen voor deelnemers)
  /api/beheer/...           vieringen aanmaken, e-mail, accounts (alleen beheerders)
  /api/beheer/v/<link>/...  deelnemers, lootjes en instellingen van één viering

Voor lokaal testen serveert dezelfde dienst ook de bestanden uit web/ (--statisch).
"""
import datetime
import json
import os
import random
import re
import secrets
import sys
import threading
import time
from http.server import SimpleHTTPRequestHandler
from urllib.parse import parse_qs, unquote, urlsplit

from planr_db import (
    CATEGORIEEN, GANG_NAMEN, GANGEN, REGEL_KEUZES, THEMAS, controleer_wachtwoord, geldig_email, hash_wachtwoord,
    instelling, instellingen, lootjes_ronde, maak_slug, maak_token, over, schoon, sha, slug_probleem, thema_van,
    tijd_tekst, voorkeuren_van, weergavenaam, zet_instelling, zoek_token,
)
from planr_mail import verstuur_direct

VERSIE = "1.0.0"
COOKIE = "planr_sessie"
SESSIE_DUUR = 180 * 86400
UITNODIGING_DUUR = 60 * 86400
HERSTEL_DUUR = 3 * 3600
MAX_LICHAAM = 64 * 1024
MIN_WACHTWOORD = 8
MIN_LOOTJES = 3
NEP_HASH = hash_wachtwoord(secrets.token_hex(8))  # om inlogtijden gelijk te houden
SLUG = r"([a-z0-9-]{3,40})"


class Fout(Exception):
    def __init__(self, status, melding, code="fout", **extra):
        super().__init__(melding)
        self.status = status
        self.melding = melding
        self.code = code
        self.extra = extra


class Teller:
    """Simpele limiet per sleutel (bijvoorbeeld inlogpogingen per IP-adres)."""

    def __init__(self):
        self.slot = threading.Lock()
        self.pogingen = {}

    def mag(self, sleutel, maximum, venster):
        tijd = time.time()
        with self.slot:
            lijst = [t for t in self.pogingen.get(sleutel, []) if tijd - t < venster]
            if len(lijst) >= maximum:
                self.pogingen[sleutel] = lijst
                return False
            lijst.append(tijd)
            self.pogingen[sleutel] = lijst
            if len(self.pogingen) > 20000:
                self.pogingen = {k: v for k, v in self.pogingen.items() if v and tijd - v[-1] < 3600}
            return True


class App:
    def __init__(self, db, melder, push, postbode, site_url, statisch=None):
        self.db = db
        self.melder = melder
        self.push = push
        self.postbode = postbode
        self.site_url = site_url.rstrip("/")
        self.veilig = self.site_url.startswith("https://")
        self.statisch = os.path.abspath(statisch) if statisch else None
        self.teller = Teller()
        self.gezien = {}


ROUTES = []


def route(methode, patroon, toegang="lid"):
    """toegang: None (iedereen), 'lid' (ingelogd), 'viering' (deelnemer van de viering in de eerste groep),
    'beheer' (beheerder), 'vbeheer' (beheerder, viering in de eerste groep)."""
    def deco(functie):
        ROUTES.append((methode, re.compile("^" + patroon + "$"), toegang, functie))
        return functie
    return deco


# --------------------------------------------------------------------------- verzoek

class Verzoek:
    def __init__(self, handler, app, delen, ruw=b""):
        self.h = handler
        self.ruw = ruw
        self.app = app
        self.c = None
        self.ik = None
        self.viering = None
        self.deelname = None
        self.sessie_hash = None
        self.cookies = []
        self.query = {k: v[0] for k, v in parse_qs(delen.query).items()}
        self._json = None

    @property
    def ip(self):
        return self.h.headers.get("X-Real-IP") or self.h.client_address[0]

    def open(self):
        self.c = self.app.db.open()
        self.ik = self.sessie_gebruiker()

    def sluit(self):
        if self.c is not None:
            try:
                if self.c.in_transaction:
                    self.c.rollback()
            finally:
                self.c.close()

    def json(self):
        if self._json is None:
            try:
                data = json.loads(self.ruw.decode("utf-8") or "{}")
            except (UnicodeDecodeError, ValueError):
                raise Fout(400, "Ongeldige gegevens.", "ongeldig")
            if not isinstance(data, dict):
                raise Fout(400, "Ongeldige gegevens.", "ongeldig")
            self._json = data
        return self._json

    def limiet(self, sleutel, maximum, venster, melding="Even rustig aan. Probeer het straks nog eens."):
        if not self.app.teller.mag(sleutel, maximum, venster):
            raise Fout(429, melding, "te_veel")

    # sessies -------------------------------------------------------------

    def sessie_token(self):
        for deel in (self.h.headers.get("Cookie") or "").split(";"):
            naam, _, waarde = deel.strip().partition("=")
            if naam == COOKIE and re.match(r"^[A-Za-z0-9_-]{30,80}$", waarde):
                return waarde
        return None

    def sessie_gebruiker(self):
        token = self.sessie_token()
        if not token:
            return None
        h = sha(token)
        g = self.c.execute(
            "SELECT g.* FROM sessies s JOIN gebruikers g ON g.id = s.gebruiker_id WHERE s.hash = ? AND s.verloopt > ? AND g.status = 'actief'",
            (h, tijd_tekst())).fetchone()
        if g is None:
            return None
        self.sessie_hash = h
        tijd = time.time()
        if tijd - self.app.gezien.get(g["id"], 0) > 300:
            self.app.gezien[g["id"]] = tijd
            self.c.execute("UPDATE gebruikers SET laatst_gezien = ? WHERE id = ?", (tijd_tekst(), g["id"]))
            self.c.execute("UPDATE sessies SET verloopt = ? WHERE hash = ?", (over(SESSIE_DUUR), h))
            self.c.commit()
        return g

    def zet_sessie(self, gebruiker_id):
        token = secrets.token_urlsafe(32)
        self.c.execute("INSERT INTO sessies (hash, gebruiker_id, gemaakt, verloopt) VALUES (?, ?, ?, ?)",
                       (sha(token), gebruiker_id, tijd_tekst(), over(SESSIE_DUUR)))
        self.c.execute("DELETE FROM sessies WHERE verloopt < ?", (tijd_tekst(),))
        self.c.commit()
        self.cookies.append(self.cookie(token, SESSIE_DUUR))

    def wis_sessie(self):
        if self.sessie_hash:
            self.c.execute("DELETE FROM sessies WHERE hash = ?", (self.sessie_hash,))
            self.c.commit()
        self.cookies.append(self.cookie("", 0))

    def cookie(self, waarde, duur):
        tekst = f"{COOKIE}={waarde}; Path=/; Max-Age={duur}; HttpOnly; SameSite=Lax"
        return tekst + ("; Secure" if self.app.veilig else "")

    def vereis_lid(self):
        if self.ik is None:
            raise Fout(401, "Log eerst in.", "niet_ingelogd")

    # vieringen ------------------------------------------------------------

    def laad_viering(self, slug, als_beheerder=False):
        v = self.c.execute("SELECT * FROM vieringen WHERE slug = ?", (slug,)).fetchone()
        if v is None:
            raise Fout(404, "Deze viering bestaat niet (meer).", "geen_viering")
        self.viering = v
        if als_beheerder:
            return
        self.deelname = self.c.execute(
            "SELECT * FROM deelnames WHERE viering_id = ? AND gebruiker_id = ?", (v["id"], self.ik["id"])).fetchone()
        if self.deelname is None:
            raise Fout(403, "Je doet niet mee met deze viering.", "geen_lid",
                       viering=viering_kort(v), beheerder=bool(self.ik["beheerder"]))
        if self.deelname["status"] != "actief":
            raise Fout(403, "Je bent uitgenodigd voor deze viering.", "uitnodiging_open", viering=viering_kort(v))

    def link(self, pad=""):
        return f"/{self.viering['slug']}{pad}"


# --------------------------------------------------------------------------- hulpjes

def persoon(g, ik_id=None):
    return {
        "id": g["id"],
        "naam": weergavenaam(g),
        "toon": g["toon"],
        "ik": g["id"] == ik_id,
    }


def regels_lijst(tekst):
    return [r.strip(" -•\t") for r in (tekst or "").split("\n") if r.strip(" -•\t")]


def viering_kort(v):
    return {"slug": v["slug"], "naam": v["naam"], "thema": v["thema"], "datum": v["datum"], "tijd": v["tijd"]}


def viering_json(v):
    return {
        "id": v["id"], "slug": v["slug"], "naam": v["naam"], "thema": v["thema"],
        "datum": v["datum"], "tijd": v["tijd"], "locatie": v["locatie"], "welkomst": v["welkomst"],
        "budget": v["budget"], "gedicht": v["gedicht"], "surprise": v["surprise"], "regels": regels_lijst(v["regels"]),
        "menu": bool(v["menu_aan"]), "lootjes": bool(v["lootjes_aan"]),
        "lootjes_getrokken": bool(lootjes_ronde(v)),
        "engel": thema_van(v)["engel"],
    }


def tekst_veld(data, sleutel, minimum, maximum, label, regels=False):
    waarde = schoon(data.get(sleutel, ""), maximum, regels=regels)
    if len(waarde) < minimum:
        if minimum <= 1:
            raise Fout(400, f"Vul {label} in.", "leeg", veld=sleutel)
        raise Fout(400, f"{label[0].upper() + label[1:]} moet minstens {minimum} tekens hebben.", "kort", veld=sleutel)
    return waarde


def wachtwoord_veld(data, sleutel="wachtwoord"):
    w = data.get(sleutel)
    if not isinstance(w, str) or len(w) < MIN_WACHTWOORD:
        raise Fout(400, f"Kies een wachtwoord van minstens {MIN_WACHTWOORD} tekens.", "wachtwoord", veld=sleutel)
    if len(w) > 200:
        raise Fout(400, "Dat wachtwoord is te lang.", "wachtwoord", veld=sleutel)
    return w


def link_veld(data):
    link = schoon(data.get("link", ""), 600)
    if not link:
        return ""
    if not re.match(r"^https?://", link, re.I):
        if re.match(r"^[a-z][a-z0-9+.-]*:(?!\d)", link, re.I):
            raise Fout(400, "Alleen gewone webadressen (https://...) kunnen als link.", "link", veld="link")
        link = "https://" + link
    if not re.match(r"^https?://[^\s/$.?#][^\s]*$", link, re.I):
        raise Fout(400, "Die link lijkt niet te kloppen.", "link", veld="link")
    return link


def gebruiker_of_404(c, gid):
    g = c.execute("SELECT * FROM gebruikers WHERE id = ?", (gid,)).fetchone()
    if g is None:
        raise Fout(404, "Deze persoon bestaat niet (meer).", "niet_gevonden")
    return g


def beheerders(c, behalve=None):
    return [g for g in c.execute("SELECT * FROM gebruikers WHERE beheerder = 1 AND status = 'actief'") if g["id"] != behalve]


def leden(c, viering_id, behalve=None):
    """Actieve deelnemers van een viering."""
    return [g for g in c.execute(
        "SELECT g.* FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id "
        "WHERE d.viering_id = ? AND d.status = 'actief' AND g.status = 'actief'", (viering_id,)) if g["id"] != behalve]


def uitnodiging_mail(app, c, g, viering, afzender_naam):
    token = maak_token(c, g["id"], "uitnodiging", UITNODIGING_DUUR, viering_id=viering["id"])
    c.execute("UPDATE deelnames SET uitgenodigd_op = ? WHERE viering_id = ? AND gebruiker_id = ?",
              (tijd_tekst(), viering["id"], g["id"]))
    wanneer = datum_tekst(viering)
    intro = f"{afzender_naam} nodigt je uit voor {viering['naam']}" + (f" ({wanneer})" if wanneer else "") + "."
    regels = []
    if viering["menu_aan"]:
        regels.append("Geef op wat je meeneemt voor het menu en wat je graag drinkt")
    if viering["lootjes_aan"]:
        regels.append("Maak je verlanglijstje en trek straks een lootje")
    if g["status"] == "actief":
        intro += " Je hebt al een account, dus je doet met één klik mee."
        knop = "Doe mee"
    else:
        intro += " Kies een wachtwoord en doe mee."
        knop = "Doe mee"
    inhoud = {
        "kop": f"Je bent uitgenodigd voor {viering['naam']}!",
        "intro": intro,
        "regels": regels,
        "knop_tekst": knop,
        "knop_pad": f"/uitnodiging/{token}",
        "voet": "Deze uitnodiging is 60 dagen geldig en alleen voor jou bedoeld. Stuur hem dus niet door.",
    }
    app.melder.mail(c, g["email"], g["naam"], f"Uitnodiging: {viering['naam']}", "uitnodiging", inhoud, viering=viering)


MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"]


def datum_tekst(v):
    datum = v["datum"]
    if re.match(r"^\d{4}-\d{2}-\d{2}$", datum or ""):
        j, m, d = (int(x) for x in datum.split("-"))
        datum = f"{d} {MAANDEN[m - 1]} {j}"
    return " ".join(x for x in [datum, ("om " + v["tijd"]) if v["tijd"] else ""] if x)


def activeer_deelname(app, c, g, viering):
    """Zet een deelname op actief en laat de beheerders het weten."""
    d = c.execute("SELECT * FROM deelnames WHERE viering_id = ? AND gebruiker_id = ?", (viering["id"], g["id"])).fetchone()
    if d is None or d["status"] == "actief":
        return
    c.execute("UPDATE deelnames SET status = 'actief', actief_sinds = ? WHERE viering_id = ? AND gebruiker_id = ?",
              (tijd_tekst(), viering["id"], g["id"]))
    c.execute("DELETE FROM tokens WHERE gebruiker_id = ? AND viering_id = ? AND soort = 'uitnodiging'", (g["id"], viering["id"]))
    c.commit()
    naam = weergavenaam(g)
    app.melder.meld(
        c, beheerders(c, behalve=g["id"]), "deelnemers", f"{naam} doet mee!",
        f"{naam} doet mee met {viering['naam']}.", f"/{viering['slug']}/beheer/deelnemers", viering=viering,
        bundel="deelnemers", regel=naam, titel_bundel="{n} nieuwe deelnemers", vertraging=120,
        onderwerp=f"{naam} doet mee met {viering['naam']}", onderwerp_bundel=f"{{n}} nieuwe deelnemers voor {viering['naam']}",
        mail={"kop": "Er doet iemand mee!", "kop_bundel": "Er doen {n} mensen mee!",
              "intro": f"Deze mensen hebben hun uitnodiging voor {viering['naam']} aangenomen:", "regels": [naam],
              "knop_tekst": "Bekijk de deelnemers", "knop_pad": f"/{viering['slug']}/beheer/deelnemers"},
    )
    if not viering["lootjes_aan"] or lootjes_ronde(viering):
        return
    r = c.execute("SELECT COUNT(*) AS mee, SUM(status = 'actief') AS actief FROM deelnames WHERE viering_id = ? AND doet_mee = 1",
                  (viering["id"],)).fetchone()
    if r["mee"] >= MIN_LOOTJES and r["mee"] == r["actief"]:
        app.melder.meld(
            c, beheerders(c), "deelnemers", "Iedereen doet mee!",
            f"Iedereen van {viering['naam']} heeft zich aangemeld. Je kunt de lootjes trekken.",
            f"/{viering['slug']}/beheer/lootjes", viering=viering,
            onderwerp=f"{viering['naam']}: tijd om lootjes te trekken",
            mail={"kop": "Iedereen doet mee!", "intro": "Alle uitgenodigden hebben zich aangemeld. Je kunt nu de lootjes trekken.",
                  "knop_tekst": "Lootjes trekken", "knop_pad": f"/{viering['slug']}/beheer/lootjes"},
        )


def vereis_module(v, module):
    if module == "menu" and not v.viering["menu_aan"]:
        raise Fout(404, "Deze viering heeft geen menu.", "module_uit")
    if module == "lootjes" and not v.viering["lootjes_aan"]:
        raise Fout(404, "Bij deze viering worden geen lootjes getrokken.", "module_uit")


# --------------------------------------------------------------------------- algemeen en inloggen

@route("GET", "/status", None)
def r_status(v):
    return {"ok": True, "versie": VERSIE}


def mijn_vieringen(c, g):
    uit = []
    for r in c.execute(
            "SELECT v.*, d.status AS deelname_status FROM deelnames d JOIN vieringen v ON v.id = d.viering_id "
            "WHERE d.gebruiker_id = ? ORDER BY CASE WHEN v.datum = '' THEN '9999' ELSE v.datum END, v.naam", (g["id"],)):
        ronde = lootjes_ronde(r)
        ongelezen = 0
        if ronde:
            ongelezen = c.execute(
                "SELECT COUNT(*) FROM berichten WHERE viering_id = ? AND ronde = ? AND gelezen IS NULL AND "
                "((gever_id = ? AND van_gever = 0) OR (ontvanger_id = ? AND van_gever = 1))",
                (r["id"], ronde, g["id"], g["id"])).fetchone()[0]
        uit.append({
            **viering_kort(r), "locatie": r["locatie"], "status": r["deelname_status"],
            "menu": bool(r["menu_aan"]), "lootjes": bool(r["lootjes_aan"]), "lootjes_getrokken": bool(ronde),
            "berichten_ongelezen": ongelezen,
            "leden": c.execute("SELECT COUNT(*) FROM deelnames WHERE viering_id = ? AND status = 'actief'", (r["id"],)).fetchone()[0],
        })
    return uit


@route("GET", "/sessie", None)
def r_sessie(v):
    c = v.c
    app_naam = instelling(c, "app_naam", "plan-r")
    if v.ik is None:
        return {"gebruiker": None, "app_naam": app_naam}
    g = v.ik
    ongelezen = c.execute("SELECT COUNT(*) FROM meldingen WHERE gebruiker_id = ? AND gelezen IS NULL", (g["id"],)).fetchone()[0]
    return {
        "gebruiker": {
            **persoon(g, g["id"]),
            "email": g["email"],
            "beheerder": bool(g["beheerder"]),
            "voornaam": g["naam"],
            "voorkeuren": voorkeuren_van(g),
        },
        "vieringen": mijn_vieringen(c, g),
        "app_naam": app_naam,
        "vapid": v.app.push.publiek,
        "push": v.app.push.actief,
        "ongelezen": ongelezen,
        "versie": VERSIE,
    }


@route("POST", "/inloggen", None)
def r_inloggen(v):
    data = v.json()
    email = schoon(data.get("email", ""), 254).lower()
    wachtwoord = data.get("wachtwoord") if isinstance(data.get("wachtwoord"), str) else ""
    v.limiet("login-ip:" + v.ip, 20, 900, "Te veel pogingen. Wacht een kwartiertje en probeer het opnieuw.")
    v.limiet("login:" + email, 8, 900, "Te veel pogingen. Wacht een kwartiertje en probeer het opnieuw.")
    g = v.c.execute("SELECT * FROM gebruikers WHERE email = ?", (email,)).fetchone()
    if g is None or not g["wachtwoord"]:
        controleer_wachtwoord(wachtwoord, NEP_HASH)
        if g is not None and g["status"] == "uitgenodigd":
            raise Fout(401, "Je hebt nog geen wachtwoord. Gebruik de link uit je uitnodiging, of klik op 'Wachtwoord vergeten'.", "uitgenodigd")
        raise Fout(401, "Dit e-mailadres of wachtwoord klopt niet.", "onjuist")
    if not controleer_wachtwoord(wachtwoord, g["wachtwoord"]):
        raise Fout(401, "Dit e-mailadres of wachtwoord klopt niet.", "onjuist")
    v.zet_sessie(g["id"])
    return {"ok": True}


@route("POST", "/uitloggen", None)
def r_uitloggen(v):
    v.wis_sessie()
    return {"ok": True}


def token_viering(c, viering_id):
    if viering_id is None:
        return None
    return c.execute("SELECT * FROM vieringen WHERE id = ?", (viering_id,)).fetchone()


@route("GET", r"/uitnodiging/([A-Za-z0-9_-]+)", None)
def r_uitnodiging(v, token):
    g, viering_id = zoek_token(v.c, token, "uitnodiging")
    if g is None:
        raise Fout(404, "Deze uitnodiging is verlopen of al gebruikt. Log in, of vraag de organisator om een nieuwe.", "verlopen")
    viering = token_viering(v.c, viering_id)
    return {
        "email": g["email"],
        "naam": g["naam"],
        "heeft_account": g["status"] == "actief",
        "ingelogd": v.ik is not None and v.ik["id"] == g["id"],
        "viering": {**viering_kort(viering), "locatie": viering["locatie"]} if viering else None,
    }


@route("POST", r"/uitnodiging/([A-Za-z0-9_-]+)", None)
def r_uitnodiging_aannemen(v, token):
    c = v.c
    v.limiet("token-ip:" + v.ip, 30, 3600)
    g, viering_id = zoek_token(c, token, "uitnodiging")
    if g is None:
        raise Fout(404, "Deze uitnodiging is verlopen of al gebruikt. Log in, of vraag de organisator om een nieuwe.", "verlopen")
    data = v.json()
    if g["status"] == "actief":
        # Bestaand account: ingelogd als deze persoon, of het wachtwoord invullen.
        if v.ik is None or v.ik["id"] != g["id"]:
            wachtwoord = data.get("wachtwoord") if isinstance(data.get("wachtwoord"), str) else ""
            if not controleer_wachtwoord(wachtwoord, g["wachtwoord"]):
                raise Fout(401, "Dit wachtwoord klopt niet.", "onjuist", veld="wachtwoord")
            v.zet_sessie(g["id"])
    else:
        naam = tekst_veld(data, "naam", 1, 40, "je naam")
        wachtwoord = wachtwoord_veld(data)
        c.execute(
            "UPDATE gebruikers SET naam = ?, wachtwoord = ?, status = 'actief', actief_sinds = COALESCE(actief_sinds, ?) WHERE id = ?",
            (naam, hash_wachtwoord(wachtwoord), tijd_tekst(), g["id"]))
        c.commit()
        v.zet_sessie(g["id"])
    c.execute("DELETE FROM tokens WHERE hash = ?", (sha(token),))
    c.commit()
    g = gebruiker_of_404(c, g["id"])
    viering = token_viering(c, viering_id)
    if viering is not None:
        activeer_deelname(v.app, c, g, viering)
    return {"ok": True, "slug": viering["slug"] if viering else None}


@route("POST", "/wachtwoord-vergeten", None)
def r_vergeten(v):
    c = v.c
    data = v.json()
    email = schoon(data.get("email", ""), 254).lower()
    if not geldig_email(email):
        raise Fout(400, "Vul je e-mailadres in.", "email", veld="email")
    v.limiet("vergeten-ip:" + v.ip, 6, 3600)
    if not v.app.teller.mag("vergeten:" + email, 3, 3600):
        return {"ok": True}
    g = c.execute("SELECT * FROM gebruikers WHERE email = ?", (email,)).fetchone()
    if g is None:
        return {"ok": True}
    if g["status"] != "actief":
        # Nog geen account: stuur de uitnodiging (van de laatste viering) opnieuw.
        d = c.execute("SELECT v.* FROM deelnames d JOIN vieringen v ON v.id = d.viering_id WHERE d.gebruiker_id = ? "
                      "ORDER BY d.gemaakt DESC LIMIT 1", (g["id"],)).fetchone()
        if d is not None:
            afzender = (beheerders(c) or [None])[0]
            uitnodiging_mail(v.app, c, g, d, weergavenaam(afzender) if afzender else "De organisator")
        return {"ok": True}
    token = maak_token(c, g["id"], "herstel", HERSTEL_DUUR)
    v.app.melder.mail(c, g["email"], g["naam"], "Nieuw wachtwoord instellen", "account", {
        "kop": "Nieuw wachtwoord instellen",
        "intro": f"Hoi {weergavenaam(g)}, via de knop hieronder kies je een nieuw wachtwoord. De link werkt 3 uur.",
        "knop_tekst": "Nieuw wachtwoord kiezen",
        "knop_pad": f"/herstel/{token}",
        "voet": "Heb jij dit niet aangevraagd? Dan kun je deze mail negeren; je wachtwoord blijft hetzelfde.",
    })
    return {"ok": True}


@route("GET", r"/herstel/([A-Za-z0-9_-]+)", None)
def r_herstel(v, token):
    g, _ = zoek_token(v.c, token, "herstel")
    if g is None:
        raise Fout(404, "Deze link is verlopen of al gebruikt. Vraag een nieuwe aan.", "verlopen")
    return {"email": g["email"]}


@route("POST", r"/herstel/([A-Za-z0-9_-]+)", None)
def r_herstel_opslaan(v, token):
    c = v.c
    v.limiet("token-ip:" + v.ip, 30, 3600)
    g, _ = zoek_token(c, token, "herstel")
    if g is None:
        raise Fout(404, "Deze link is verlopen of al gebruikt. Vraag een nieuwe aan.", "verlopen")
    wachtwoord = wachtwoord_veld(v.json())
    c.execute("UPDATE gebruikers SET wachtwoord = ? WHERE id = ?", (hash_wachtwoord(wachtwoord), g["id"]))
    c.execute("DELETE FROM tokens WHERE gebruiker_id = ? AND soort = 'herstel'", (g["id"],))
    c.execute("DELETE FROM sessies WHERE gebruiker_id = ?", (g["id"],))
    c.commit()
    v.zet_sessie(g["id"])
    return {"ok": True}


# --------------------------------------------------------------------------- mijn account

@route("PUT", "/ik")
def r_ik(v):
    c = v.c
    data = v.json()
    if "naam" in data:
        naam = tekst_veld(data, "naam", 1, 40, "je naam")
        c.execute("UPDATE gebruikers SET naam = ? WHERE id = ?", (naam, v.ik["id"]))
    if isinstance(data.get("voorkeuren"), dict):
        huidig = voorkeuren_van(v.ik)
        for kanaal in ("mail", "push"):
            for k, waarde in (data["voorkeuren"].get(kanaal) or {}).items():
                if k in CATEGORIEEN:
                    huidig[kanaal][k] = bool(waarde)
        c.execute("UPDATE gebruikers SET voorkeuren = ? WHERE id = ?", (json.dumps(huidig), v.ik["id"]))
    c.commit()
    return {"ok": True}


@route("POST", "/ik/wachtwoord")
def r_ik_wachtwoord(v):
    c = v.c
    data = v.json()
    v.limiet("ww:" + str(v.ik["id"]), 10, 900)
    huidig = data.get("huidig") if isinstance(data.get("huidig"), str) else ""
    if not controleer_wachtwoord(huidig, v.ik["wachtwoord"]):
        raise Fout(400, "Je huidige wachtwoord klopt niet.", "onjuist", veld="huidig")
    nieuw = wachtwoord_veld(data, "nieuw")
    c.execute("UPDATE gebruikers SET wachtwoord = ? WHERE id = ?", (hash_wachtwoord(nieuw), v.ik["id"]))
    c.execute("DELETE FROM sessies WHERE gebruiker_id = ? AND hash != ?", (v.ik["id"], v.sessie_hash or ""))
    c.commit()
    return {"ok": True}


@route("POST", r"/v/" + SLUG + r"/aannemen")
def r_aannemen(v, slug):
    """Een uitnodiging aannemen als je al bent ingelogd (zonder de link uit de mail)."""
    c = v.c
    viering = c.execute("SELECT * FROM vieringen WHERE slug = ?", (slug,)).fetchone()
    if viering is None:
        raise Fout(404, "Deze viering bestaat niet (meer).", "geen_viering")
    d = c.execute("SELECT * FROM deelnames WHERE viering_id = ? AND gebruiker_id = ?", (viering["id"], v.ik["id"])).fetchone()
    if d is None:
        raise Fout(403, "Je bent niet uitgenodigd voor deze viering.", "geen_lid")
    activeer_deelname(v.app, c, v.ik, viering)
    return {"ok": True}


# --------------------------------------------------------------------------- dashboard van een viering

@route("GET", r"/v/" + SLUG, "viering")
def r_dashboard(v):
    c = v.c
    vi = v.viering
    ik = v.ik
    ronde = lootjes_ronde(vi)
    deelnemers = []
    for r in c.execute(
            "SELECT g.*, d.status AS d_status FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id "
            "WHERE d.viering_id = ? ORDER BY d.status = 'actief' DESC, COALESCE(d.actief_sinds, d.gemaakt), g.id", (vi["id"],)):
        deelnemers.append({**persoon(r, ik["id"]), "status": r["d_status"]})
    uit = {"viering": viering_json(vi), "deelnemers": deelnemers, "doet_mee": bool(v.deelname["doet_mee"])}
    if vi["lootjes_aan"]:
        lootje = {"status": "niet_getrokken"}
        if ronde:
            r = c.execute(
                "SELECT l.geopend, g.* FROM lootjes l JOIN gebruikers g ON g.id = l.ontvanger_id "
                "WHERE l.viering_id = ? AND l.ronde = ? AND l.gever_id = ?", (vi["id"], ronde, ik["id"])).fetchone()
            if r is None:
                lootje = {"status": "doet_niet_mee"}
            else:
                lootje = {"status": "getrokken", "geopend": bool(r["geopend"])}
                if r["geopend"]:
                    lootje.update(naam=weergavenaam(r), toon=r["toon"])
        uit["lootje"] = lootje
        uit["wensen"] = c.execute("SELECT COUNT(*) FROM wensen WHERE viering_id = ? AND gebruiker_id = ?",
                                  (vi["id"], ik["id"])).fetchone()[0]
        uit["berichten_ongelezen"] = berichten_ongelezen(c, vi, ik["id"])
    if vi["menu_aan"]:
        uit["menu"] = {
            "gerechten": c.execute("SELECT COUNT(*) FROM gerechten WHERE viering_id = ?", (vi["id"],)).fetchone()[0],
            "drankjes": c.execute("SELECT COUNT(*) FROM drankjes WHERE viering_id = ?", (vi["id"],)).fetchone()[0],
            "mijn_gerechten": [{"naam": r["naam"], "gang": GANG_NAMEN.get(r["gang"], r["gang"])} for r in c.execute(
                "SELECT naam, gang FROM gerechten WHERE viering_id = ? AND gebruiker_id = ? ORDER BY id", (vi["id"], ik["id"]))],
        }
    return uit


# --------------------------------------------------------------------------- menu

GERECHT_SQL = ("SELECT r.*, g.naam AS van_naam, g.email AS van_email, g.toon AS van_toon "
               "FROM gerechten r JOIN gebruikers g ON g.id = r.gebruiker_id")


def van_json(r):
    return {"id": r["gebruiker_id"], "naam": r["van_naam"] or r["van_email"].split("@")[0], "toon": r["van_toon"]}


def gerecht_json(r, ik):
    return {
        "id": r["id"], "gang": r["gang"], "naam": r["naam"], "toelichting": r["toelichting"], "van": van_json(r),
        "mijn": r["gebruiker_id"] == ik["id"], "mag": r["gebruiker_id"] == ik["id"] or bool(ik["beheerder"]),
        "gemaakt": r["gemaakt"],
    }


@route("GET", r"/v/" + SLUG + r"/menu", "viering")
def r_menu(v):
    vereis_module(v, "menu")
    c = v.c
    ik = v.ik
    gerechten = [gerecht_json(r, ik) for r in c.execute(GERECHT_SQL + " WHERE r.viering_id = ? ORDER BY r.id", (v.viering["id"],))]
    drankjes = []
    for r in c.execute(
            "SELECT d.*, g.naam AS van_naam, g.email AS van_email, g.toon AS van_toon FROM drankjes d "
            "JOIN gebruikers g ON g.id = d.gebruiker_id WHERE d.viering_id = ? ORDER BY d.id", (v.viering["id"],)):
        stemmers = c.execute(
            "SELECT g.id, g.naam, g.email FROM drank_stemmen s JOIN gebruikers g ON g.id = s.gebruiker_id WHERE s.drank_id = ? ORDER BY g.naam",
            (r["id"],)).fetchall()
        drankjes.append({
            "id": r["id"], "tekst": r["tekst"], "van": van_json(r),
            "mijn": r["gebruiker_id"] == ik["id"], "mag": r["gebruiker_id"] == ik["id"] or bool(ik["beheerder"]),
            "stemmen": len(stemmers),
            "ikook": any(s["id"] == ik["id"] for s in stemmers),
            "wie": [weergavenaam(s) for s in stemmers],
        })
    return {"gerechten": gerechten, "drankjes": drankjes, "gangen": [{"id": g, "naam": GANG_NAMEN[g]} for g in GANGEN]}


def meld_menu(v, onderwerp, regel):
    c = v.c
    naam = v.viering["naam"]
    v.app.melder.meld(
        c, leden(c, v.viering["id"], behalve=v.ik["id"]), "menu", "Nieuws over het menu", regel, v.link("/menu"),
        viering=v.viering, bundel="menu", regel=regel, titel_bundel="{n} wijzigingen in het menu", vertraging=180,
        onderwerp=f"{naam}: {onderwerp}", onderwerp_bundel=f"{naam}: {{n}} wijzigingen in het menu",
        mail={"kop": "Nieuws over het menu", "intro": "Dit is er veranderd:", "regels": [regel],
              "knop_tekst": "Bekijk het menu", "knop_pad": v.link("/menu")},
    )


def gerecht_velden(data):
    naam = tekst_veld(data, "naam", 1, 80, "wat je meeneemt")
    gang = data.get("gang") if data.get("gang") in GANGEN else "overig"
    toelichting = schoon(data.get("toelichting", ""), 200)
    return naam, gang, toelichting


def eigen_gerecht(v, gid):
    r = v.c.execute(GERECHT_SQL + " WHERE r.id = ? AND r.viering_id = ?", (gid, v.viering["id"])).fetchone()
    if r is None:
        raise Fout(404, "Dit gerecht staat niet (meer) op het menu.", "niet_gevonden")
    if r["gebruiker_id"] != v.ik["id"] and not v.ik["beheerder"]:
        raise Fout(403, "Alleen wie dit meeneemt, kan het aanpassen.", "geen_toegang")
    return r


@route("POST", r"/v/" + SLUG + r"/menu/gerechten", "viering")
def r_gerecht_nieuw(v):
    vereis_module(v, "menu")
    c = v.c
    v.limiet("menu:" + str(v.ik["id"]), 60, 3600)
    naam, gang, toelichting = gerecht_velden(v.json())
    cur = c.execute(
        "INSERT INTO gerechten (viering_id, gebruiker_id, gang, naam, toelichting, gemaakt, bijgewerkt) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (v.viering["id"], v.ik["id"], gang, naam, toelichting, tijd_tekst(), tijd_tekst()))
    c.commit()
    wie = weergavenaam(v.ik)
    meld_menu(v, f"{wie} neemt {naam} mee", f"{wie} neemt {naam} mee ({GANG_NAMEN[gang].lower()})")
    return gerecht_json(c.execute(GERECHT_SQL + " WHERE r.id = ?", (cur.lastrowid,)).fetchone(), v.ik)


@route("PUT", r"/v/" + SLUG + r"/menu/gerechten/(\d+)", "viering")
def r_gerecht_wijzig(v, gid):
    vereis_module(v, "menu")
    c = v.c
    r = eigen_gerecht(v, int(gid))
    naam, gang, toelichting = gerecht_velden(v.json())
    if (naam, gang, toelichting) == (r["naam"], r["gang"], r["toelichting"]):
        return gerecht_json(r, v.ik)
    c.execute("UPDATE gerechten SET naam = ?, gang = ?, toelichting = ?, bijgewerkt = ? WHERE id = ?",
              (naam, gang, toelichting, tijd_tekst(), r["id"]))
    c.commit()
    wie = r["van_naam"] or r["van_email"].split("@")[0]
    if naam != r["naam"]:
        regel = f"{wie} neemt nu {naam} mee in plaats van {r['naam']}"
    else:
        regel = f"{wie} heeft {naam} aangepast ({GANG_NAMEN[gang].lower()})"
    meld_menu(v, f"Aangepast op het menu: {naam}", regel)
    return gerecht_json(c.execute(GERECHT_SQL + " WHERE r.id = ?", (r["id"],)).fetchone(), v.ik)


@route("DELETE", r"/v/" + SLUG + r"/menu/gerechten/(\d+)", "viering")
def r_gerecht_weg(v, gid):
    vereis_module(v, "menu")
    c = v.c
    r = eigen_gerecht(v, int(gid))
    c.execute("DELETE FROM gerechten WHERE id = ?", (r["id"],))
    c.commit()
    wie = r["van_naam"] or r["van_email"].split("@")[0]
    meld_menu(v, f"{r['naam']} gaat niet meer mee", f"{wie} neemt toch geen {r['naam']} mee")
    return {"ok": True}


@route("POST", r"/v/" + SLUG + r"/menu/drankjes", "viering")
def r_drank_nieuw(v):
    vereis_module(v, "menu")
    c = v.c
    v.limiet("menu:" + str(v.ik["id"]), 60, 3600)
    tekst = tekst_veld(v.json(), "tekst", 1, 60, "wat je graag drinkt")
    bestaand = c.execute("SELECT id FROM drankjes WHERE viering_id = ? AND lower(tekst) = lower(?)",
                         (v.viering["id"], tekst)).fetchone()
    if bestaand:
        c.execute("INSERT OR IGNORE INTO drank_stemmen (drank_id, gebruiker_id) VALUES (?, ?)", (bestaand["id"], v.ik["id"]))
        c.commit()
        return {"ok": True, "bestond": True}
    cur = c.execute("INSERT INTO drankjes (viering_id, gebruiker_id, tekst, gemaakt) VALUES (?, ?, ?, ?)",
                    (v.viering["id"], v.ik["id"], tekst, tijd_tekst()))
    c.execute("INSERT INTO drank_stemmen (drank_id, gebruiker_id) VALUES (?, ?)", (cur.lastrowid, v.ik["id"]))
    c.commit()
    wie = weergavenaam(v.ik)
    meld_menu(v, f"{wie} drinkt graag {tekst}", f"{wie} drinkt graag {tekst}")
    return {"ok": True}


def drankje(v, did):
    r = v.c.execute("SELECT * FROM drankjes WHERE id = ? AND viering_id = ?", (did, v.viering["id"])).fetchone()
    if r is None:
        raise Fout(404, "Dit drankje staat er niet (meer).", "niet_gevonden")
    return r


@route("DELETE", r"/v/" + SLUG + r"/menu/drankjes/(\d+)", "viering")
def r_drank_weg(v, did):
    vereis_module(v, "menu")
    r = drankje(v, int(did))
    if r["gebruiker_id"] != v.ik["id"] and not v.ik["beheerder"]:
        raise Fout(403, "Alleen wie dit voorstelde, kan het weghalen.", "geen_toegang")
    v.c.execute("DELETE FROM drankjes WHERE id = ?", (r["id"],))
    v.c.commit()
    return {"ok": True}


@route("POST", r"/v/" + SLUG + r"/menu/drankjes/(\d+)/ikook", "viering")
def r_drank_ikook(v, did):
    vereis_module(v, "menu")
    c = v.c
    r = drankje(v, int(did))
    if c.execute("SELECT 1 FROM drank_stemmen WHERE drank_id = ? AND gebruiker_id = ?", (r["id"], v.ik["id"])).fetchone():
        c.execute("DELETE FROM drank_stemmen WHERE drank_id = ? AND gebruiker_id = ?", (r["id"], v.ik["id"]))
        ikook = False
    else:
        c.execute("INSERT INTO drank_stemmen (drank_id, gebruiker_id) VALUES (?, ?)", (r["id"], v.ik["id"]))
        ikook = True
    c.commit()
    stemmen = c.execute("SELECT COUNT(*) FROM drank_stemmen WHERE drank_id = ?", (r["id"],)).fetchone()[0]
    return {"ikook": ikook, "stemmen": stemmen}


# --------------------------------------------------------------------------- verlanglijst

def wens_json(r):
    return {"id": r["id"], "titel": r["titel"], "toelichting": r["toelichting"], "link": r["link"], "prijs": r["prijs"]}


def wens_velden(data):
    titel = tekst_veld(data, "titel", 1, 100, "wat je graag wilt")
    toelichting = schoon(data.get("toelichting", ""), 500, regels=True)
    link = link_veld(data)
    prijs = schoon(data.get("prijs", ""), 30)
    return titel, toelichting, link, prijs


def meld_wens(v, regel):
    c = v.c
    vi = v.viering
    ronde = lootjes_ronde(vi)
    if not ronde:
        return
    r = c.execute("SELECT gever_id, geopend FROM lootjes WHERE viering_id = ? AND ronde = ? AND ontvanger_id = ?",
                  (vi["id"], ronde, v.ik["id"])).fetchone()
    if r is None:
        return
    if r["geopend"]:
        naam = weergavenaam(v.ik)
        titel, intro = f"{naam} heeft het verlanglijstje aangepast", f"Jij hebt het lootje van {naam}. Dit is er veranderd:"
    else:
        # Nog niet geopend: de naam niet verklappen.
        titel, intro = "Je lootje heeft het verlanglijstje aangepast", "Open je lootje in de app om te zien van wie het verlanglijstje is."
        regel = "Er is iets veranderd aan het verlanglijstje"
    v.app.melder.meld(
        c, [r["gever_id"]], "wensen", titel, regel, v.link("/lootje"),
        viering=vi, bundel=f"wensen:{ronde}:{v.ik['id']}", regel=regel, vertraging=120,
        onderwerp=titel,
        mail={"kop": titel, "intro": intro, "regels": [regel] if r["geopend"] else [],
              "knop_tekst": "Bekijk het verlanglijstje", "knop_pad": v.link("/lootje")},
    )


def mijn_wens(v, wid):
    r = v.c.execute("SELECT * FROM wensen WHERE id = ? AND gebruiker_id = ? AND viering_id = ?",
                    (wid, v.ik["id"], v.viering["id"])).fetchone()
    if r is None:
        raise Fout(404, "Deze wens staat niet (meer) op je lijstje.", "niet_gevonden")
    return r


@route("GET", r"/v/" + SLUG + r"/verlanglijst", "viering")
def r_verlanglijst(v):
    vereis_module(v, "lootjes")
    c = v.c
    vi = v.viering
    ronde = lootjes_ronde(vi)
    heeft_engel = bool(ronde) and c.execute(
        "SELECT 1 FROM lootjes WHERE viering_id = ? AND ronde = ? AND ontvanger_id = ?", (vi["id"], ronde, v.ik["id"])).fetchone() is not None
    wensen = [wens_json(r) for r in c.execute(
        "SELECT * FROM wensen WHERE viering_id = ? AND gebruiker_id = ? ORDER BY volgorde, id", (vi["id"], v.ik["id"]))]
    return {"wensen": wensen, "kerstengel": heeft_engel, "viering": viering_json(vi)}


@route("POST", r"/v/" + SLUG + r"/verlanglijst", "viering")
def r_wens_nieuw(v):
    vereis_module(v, "lootjes")
    c = v.c
    vid = v.viering["id"]
    v.limiet("wens:" + str(v.ik["id"]), 80, 3600)
    if c.execute("SELECT COUNT(*) FROM wensen WHERE viering_id = ? AND gebruiker_id = ?", (vid, v.ik["id"])).fetchone()[0] >= 60:
        raise Fout(400, "Je lijstje is vol (60 wensen). Dat is wel genoeg, toch?", "vol")
    titel, toelichting, link, prijs = wens_velden(v.json())
    volgorde = c.execute("SELECT COALESCE(MAX(volgorde), 0) + 1 FROM wensen WHERE viering_id = ? AND gebruiker_id = ?",
                         (vid, v.ik["id"])).fetchone()[0]
    cur = c.execute(
        "INSERT INTO wensen (viering_id, gebruiker_id, titel, toelichting, link, prijs, volgorde, gemaakt, bijgewerkt) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (vid, v.ik["id"], titel, toelichting, link, prijs, volgorde, tijd_tekst(), tijd_tekst()))
    c.commit()
    meld_wens(v, f"Nieuw: {titel}")
    return wens_json(c.execute("SELECT * FROM wensen WHERE id = ?", (cur.lastrowid,)).fetchone())


@route("PUT", r"/v/" + SLUG + r"/verlanglijst/(\d+)", "viering")
def r_wens_wijzig(v, wid):
    vereis_module(v, "lootjes")
    c = v.c
    r = mijn_wens(v, int(wid))
    titel, toelichting, link, prijs = wens_velden(v.json())
    if (titel, toelichting, link, prijs) == (r["titel"], r["toelichting"], r["link"], r["prijs"]):
        return wens_json(r)
    c.execute("UPDATE wensen SET titel = ?, toelichting = ?, link = ?, prijs = ?, bijgewerkt = ? WHERE id = ?",
              (titel, toelichting, link, prijs, tijd_tekst(), r["id"]))
    c.commit()
    meld_wens(v, f"Aangepast: {titel}")
    return wens_json(c.execute("SELECT * FROM wensen WHERE id = ?", (r["id"],)).fetchone())


@route("DELETE", r"/v/" + SLUG + r"/verlanglijst/(\d+)", "viering")
def r_wens_weg(v, wid):
    vereis_module(v, "lootjes")
    c = v.c
    r = mijn_wens(v, int(wid))
    c.execute("DELETE FROM wensen WHERE id = ?", (r["id"],))
    c.commit()
    meld_wens(v, f"Van het lijstje gehaald: {r['titel']}")
    return {"ok": True}


@route("POST", r"/v/" + SLUG + r"/verlanglijst/volgorde", "viering")
def r_wens_volgorde(v):
    vereis_module(v, "lootjes")
    c = v.c
    ids = v.json().get("ids")
    if not isinstance(ids, list) or len(ids) > 100:
        raise Fout(400, "Ongeldige volgorde.", "ongeldig")
    for i, wid in enumerate(ids):
        if isinstance(wid, int):
            c.execute("UPDATE wensen SET volgorde = ? WHERE id = ? AND gebruiker_id = ? AND viering_id = ?",
                      (i + 1, wid, v.ik["id"], v.viering["id"]))
    c.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- lootje

def mijn_lootje(v):
    ronde = lootjes_ronde(v.viering)
    if not ronde:
        return ronde, None
    return ronde, v.c.execute("SELECT * FROM lootjes WHERE viering_id = ? AND ronde = ? AND gever_id = ?",
                              (v.viering["id"], ronde, v.ik["id"])).fetchone()


@route("GET", r"/v/" + SLUG + r"/lootje", "viering")
def r_lootje(v):
    vereis_module(v, "lootjes")
    c = v.c
    vi = v.viering
    ronde, l = mijn_lootje(v)
    if not ronde:
        return {"status": "niet_getrokken", "viering": viering_json(vi)}
    if l is None:
        return {"status": "doet_niet_mee", "viering": viering_json(vi)}
    ontvanger = gebruiker_of_404(c, l["ontvanger_id"])
    wensen = []
    for r in c.execute(
            "SELECT w.*, a.gemaakt AS afgevinkt FROM wensen w LEFT JOIN afgevinkt a ON a.wens_id = w.id AND a.gever_id = ? "
            "WHERE w.viering_id = ? AND w.gebruiker_id = ? ORDER BY w.volgorde, w.id", (v.ik["id"], vi["id"], ontvanger["id"])):
        wensen.append({**wens_json(r), "afgevinkt": bool(r["afgevinkt"])})
    ongelezen = c.execute(
        "SELECT COUNT(*) FROM berichten WHERE viering_id = ? AND ronde = ? AND gever_id = ? AND van_gever = 0 AND gelezen IS NULL",
        (vi["id"], ronde, v.ik["id"])).fetchone()[0]
    return {
        "status": "getrokken",
        "geopend": bool(l["geopend"]),
        "ontvanger": {"id": ontvanger["id"], "naam": weergavenaam(ontvanger), "toon": ontvanger["toon"]},
        "wensen": wensen,
        "notities": l["notities"],
        "viering": viering_json(vi),
        "ongelezen": ongelezen,
    }


@route("POST", r"/v/" + SLUG + r"/lootje/open", "viering")
def r_lootje_open(v):
    vereis_module(v, "lootjes")
    ronde, l = mijn_lootje(v)
    if l is None:
        raise Fout(404, "Je hebt (nog) geen lootje.", "geen_lootje")
    v.c.execute("UPDATE lootjes SET geopend = COALESCE(geopend, ?) WHERE viering_id = ? AND ronde = ? AND gever_id = ?",
                (tijd_tekst(), v.viering["id"], ronde, v.ik["id"]))
    v.c.commit()
    return {"ok": True}


@route("PUT", r"/v/" + SLUG + r"/lootje/vinkje/(\d+)", "viering")
def r_lootje_vinkje(v, wid):
    vereis_module(v, "lootjes")
    c = v.c
    ronde, l = mijn_lootje(v)
    if l is None:
        raise Fout(404, "Je hebt (nog) geen lootje.", "geen_lootje")
    w = c.execute("SELECT * FROM wensen WHERE id = ? AND gebruiker_id = ? AND viering_id = ?",
                  (int(wid), l["ontvanger_id"], v.viering["id"])).fetchone()
    if w is None:
        raise Fout(404, "Deze wens staat niet (meer) op het lijstje.", "niet_gevonden")
    if v.json().get("afgevinkt"):
        c.execute("INSERT OR IGNORE INTO afgevinkt (gever_id, wens_id, gemaakt) VALUES (?, ?, ?)", (v.ik["id"], w["id"], tijd_tekst()))
    else:
        c.execute("DELETE FROM afgevinkt WHERE gever_id = ? AND wens_id = ?", (v.ik["id"], w["id"]))
    c.commit()
    return {"ok": True}


@route("PUT", r"/v/" + SLUG + r"/lootje/notities", "viering")
def r_lootje_notities(v):
    vereis_module(v, "lootjes")
    ronde, l = mijn_lootje(v)
    if l is None:
        raise Fout(404, "Je hebt (nog) geen lootje.", "geen_lootje")
    tekst = schoon(v.json().get("tekst", ""), 3000, regels=True)
    v.c.execute("UPDATE lootjes SET notities = ? WHERE viering_id = ? AND ronde = ? AND gever_id = ?",
                (tekst, v.viering["id"], ronde, v.ik["id"]))
    v.c.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- berichten

def berichten_ongelezen(c, viering, ik_id):
    ronde = lootjes_ronde(viering)
    if not ronde:
        return 0
    return c.execute(
        "SELECT COUNT(*) FROM berichten WHERE viering_id = ? AND ronde = ? AND gelezen IS NULL AND "
        "((gever_id = ? AND van_gever = 0) OR (ontvanger_id = ? AND van_gever = 1))",
        (viering["id"], ronde, ik_id, ik_id)).fetchone()[0]


def gesprek_paar(v, gesprek):
    """(ronde, gever_id, ontvanger_id, ik_ben_gever, ander) of None."""
    c = v.c
    vid = v.viering["id"]
    ronde = lootjes_ronde(v.viering)
    if not ronde:
        return None
    if gesprek == "lootje":
        l = c.execute("SELECT * FROM lootjes WHERE viering_id = ? AND ronde = ? AND gever_id = ?", (vid, ronde, v.ik["id"])).fetchone()
        if l is None:
            return None
        return ronde, v.ik["id"], l["ontvanger_id"], True, gebruiker_of_404(c, l["ontvanger_id"])
    if gesprek == "engel":
        l = c.execute("SELECT * FROM lootjes WHERE viering_id = ? AND ronde = ? AND ontvanger_id = ?", (vid, ronde, v.ik["id"])).fetchone()
        if l is None:
            return None
        return ronde, l["gever_id"], v.ik["id"], False, None
    return None


def gesprek_json(v, paar):
    ronde, gever, ontvanger, ik_gever, ander = paar
    berichten = []
    ongelezen = 0
    for r in v.c.execute(
            "SELECT * FROM (SELECT * FROM berichten WHERE viering_id = ? AND ronde = ? AND gever_id = ? AND ontvanger_id = ? "
            "ORDER BY id DESC LIMIT 400) ORDER BY id", (v.viering["id"], ronde, gever, ontvanger)):
        mij = bool(r["van_gever"]) == ik_gever
        if not mij and r["gelezen"] is None:
            ongelezen += 1
        berichten.append({"id": r["id"], "mij": mij, "tekst": r["tekst"], "gemaakt": r["gemaakt"]})
    uit = {"berichten": berichten, "ongelezen": ongelezen}
    if ander is not None:
        geopend = v.c.execute("SELECT geopend FROM lootjes WHERE viering_id = ? AND ronde = ? AND gever_id = ?",
                              (v.viering["id"], ronde, gever)).fetchone()["geopend"]
        uit["geopend"] = bool(geopend)
        if geopend:
            uit["naam"] = weergavenaam(ander)
            uit["toon"] = ander["toon"]
    return uit


@route("GET", r"/v/" + SLUG + r"/berichten", "viering")
def r_berichten(v):
    vereis_module(v, "lootjes")
    if not lootjes_ronde(v.viering):
        return {"status": "niet_getrokken", "gesprekken": {}, "viering": viering_json(v.viering)}
    gesprekken = {}
    for gesprek in ("lootje", "engel"):
        paar = gesprek_paar(v, gesprek)
        gesprekken[gesprek] = gesprek_json(v, paar) if paar else None
    return {"status": "getrokken", "gesprekken": gesprekken, "viering": viering_json(v.viering)}


@route("POST", r"/v/" + SLUG + r"/berichten", "viering")
def r_bericht_nieuw(v):
    vereis_module(v, "lootjes")
    c = v.c
    vi = v.viering
    data = v.json()
    gesprek = data.get("gesprek")
    paar = gesprek_paar(v, gesprek)
    if paar is None:
        raise Fout(404, "Dit gesprek bestaat (nog) niet.", "geen_gesprek")
    v.limiet("bericht:" + str(v.ik["id"]), 40, 600, "Je stuurt wel heel veel berichtjes. Wacht even.")
    tekst = tekst_veld(data, "tekst", 1, 2000, "een bericht", regels=True)
    ronde, gever, ontvanger, ik_gever, ander = paar
    if ik_gever and not c.execute("SELECT geopend FROM lootjes WHERE viering_id = ? AND ronde = ? AND gever_id = ?",
                                  (vi["id"], ronde, gever)).fetchone()["geopend"]:
        raise Fout(400, "Open eerst je lootje, dan weet je aan wie je schrijft.", "niet_geopend")
    cur = c.execute(
        "INSERT INTO berichten (viering_id, ronde, gever_id, ontvanger_id, van_gever, tekst, gemaakt) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (vi["id"], ronde, gever, ontvanger, 1 if ik_gever else 0, tekst, tijd_tekst()))
    # Wie terugschrijft, heeft de berichten van de ander gelezen.
    c.execute("UPDATE berichten SET gelezen = ? WHERE viering_id = ? AND ronde = ? AND gever_id = ? AND ontvanger_id = ? "
              "AND van_gever = ? AND gelezen IS NULL", (tijd_tekst(), vi["id"], ronde, gever, ontvanger, 0 if ik_gever else 1))
    c.commit()
    voorbeeld = schoon(tekst, 140)
    engel = thema_van(vi)["engel"]
    Engel = engel[0].upper() + engel[1:]
    if ik_gever:
        v.app.melder.meld(
            c, [ontvanger], "berichten", f"Bericht van {engel}", voorbeeld, v.link("/berichten/engel"), viering=vi,
            bundel=f"bericht:{ronde}:{gever}:e", regel=voorbeeld, titel_bundel=f"{{n}} berichten van {engel}",
            vertraging=60, onderwerp=f"{Engel} heeft je een bericht gestuurd",
            onderwerp_bundel=f"{{n}} berichten van {engel}",
            mail={"kop": "Je hebt een anoniem bericht", "kop_bundel": "Je hebt {n} anonieme berichten",
                  "intro": f"{Engel} heeft je geschreven:", "regels": [tekst], "stijl": "citaten",
                  "knop_tekst": "Antwoord sturen", "knop_pad": v.link("/berichten/engel")},
        )
    else:
        naam = weergavenaam(v.ik)
        v.app.melder.meld(
            c, [gever], "berichten", f"Bericht van {naam}, je lootje", voorbeeld, v.link("/berichten/lootje"), viering=vi,
            bundel=f"bericht:{ronde}:{gever}:l", regel=voorbeeld, titel_bundel=f"{{n}} berichten van {naam}, je lootje",
            vertraging=60, onderwerp=f"{naam} heeft je teruggeschreven", onderwerp_bundel=f"{{n}} berichten van {naam}",
            mail={"kop": f"{naam} heeft je teruggeschreven", "kop_bundel": f"{{n}} berichten van {naam}",
                  "intro": f"{naam} (jouw lootje) heeft gereageerd op je anonieme berichtjes:", "regels": [tekst],
                  "stijl": "citaten", "knop_tekst": "Antwoord sturen", "knop_pad": v.link("/berichten/lootje")},
        )
    return {"id": cur.lastrowid, "mij": True, "tekst": tekst, "gemaakt": tijd_tekst()}


@route("POST", r"/v/" + SLUG + r"/berichten/gelezen", "viering")
def r_berichten_gelezen(v):
    vereis_module(v, "lootjes")
    c = v.c
    gesprek = v.json().get("gesprek")
    paar = gesprek_paar(v, gesprek)
    if paar is None:
        return {"ok": True}
    ronde, gever, ontvanger, ik_gever, ander = paar
    c.execute("UPDATE berichten SET gelezen = ? WHERE viering_id = ? AND ronde = ? AND gever_id = ? AND ontvanger_id = ? "
              "AND van_gever = ? AND gelezen IS NULL", (tijd_tekst(), v.viering["id"], ronde, gever, ontvanger, 0 if ik_gever else 1))
    c.execute("UPDATE meldingen SET gelezen = ? WHERE gebruiker_id = ? AND link = ? AND gelezen IS NULL",
              (tijd_tekst(), v.ik["id"], v.link(f"/berichten/{gesprek}")))
    c.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- meldingen en push

def melding_json(r):
    return {"id": r["id"], "soort": r["soort"], "titel": r["titel"], "tekst": r["tekst"], "link": r["link"],
            "gemaakt": r["gemaakt"], "gelezen": r["gelezen"] is not None,
            "viering": {"naam": r["v_naam"], "thema": r["v_thema"]} if r["v_naam"] else None}


MELDING_SQL = ("SELECT m.*, v.naam AS v_naam, v.thema AS v_thema FROM meldingen m "
               "LEFT JOIN vieringen v ON v.id = m.viering_id WHERE m.gebruiker_id = ?")


@route("GET", "/meldingen")
def r_meldingen(v):
    c = v.c
    try:
        na = max(0, int(v.query.get("na", 0)))
    except ValueError:
        na = 0
    if na:
        rijen = c.execute(MELDING_SQL + " AND m.id > ? ORDER BY m.id LIMIT 50", (v.ik["id"], na)).fetchall()
    else:
        rijen = c.execute(MELDING_SQL + " ORDER BY m.id DESC LIMIT 50", (v.ik["id"],)).fetchall()
    ongelezen = c.execute("SELECT COUNT(*) FROM meldingen WHERE gebruiker_id = ? AND gelezen IS NULL", (v.ik["id"],)).fetchone()[0]
    laatste = c.execute("SELECT COALESCE(MAX(id), 0) FROM meldingen WHERE gebruiker_id = ?", (v.ik["id"],)).fetchone()[0]
    return {"meldingen": [melding_json(r) for r in rijen], "ongelezen": ongelezen, "laatste": laatste}


@route("POST", "/meldingen/gelezen")
def r_meldingen_gelezen(v):
    c = v.c
    data = v.json()
    if data.get("alles"):
        c.execute("UPDATE meldingen SET gelezen = ? WHERE gebruiker_id = ? AND gelezen IS NULL", (tijd_tekst(), v.ik["id"]))
    elif isinstance(data.get("link"), str):
        c.execute("UPDATE meldingen SET gelezen = ? WHERE gebruiker_id = ? AND link = ? AND gelezen IS NULL",
                  (tijd_tekst(), v.ik["id"], data["link"][:200]))
    elif isinstance(data.get("ids"), list):
        for mid in data["ids"][:200]:
            if isinstance(mid, int):
                c.execute("UPDATE meldingen SET gelezen = ? WHERE id = ? AND gebruiker_id = ? AND gelezen IS NULL",
                          (tijd_tekst(), mid, v.ik["id"]))
    c.commit()
    ongelezen = c.execute("SELECT COUNT(*) FROM meldingen WHERE gebruiker_id = ? AND gelezen IS NULL", (v.ik["id"],)).fetchone()[0]
    return {"ok": True, "ongelezen": ongelezen}


@route("POST", "/push")
def r_push(v):
    from planr_push import b64u_terug, endpoint_toegestaan
    c = v.c
    if not v.app.push.actief:
        raise Fout(503, "Pushmeldingen staan uit op de server.", "geen_push")
    data = v.json()
    endpoint = data.get("endpoint") if isinstance(data.get("endpoint"), str) else ""
    sleutels = data.get("keys") if isinstance(data.get("keys"), dict) else {}
    p256dh, auth = sleutels.get("p256dh"), sleutels.get("auth")
    if not endpoint_toegestaan(endpoint):
        raise Fout(400, "Deze browser gebruikt een onbekende pushdienst.", "onbekende_dienst")
    try:
        if len(b64u_terug(p256dh)) != 65 or len(b64u_terug(auth)) < 16:
            raise ValueError
    except (TypeError, ValueError, AttributeError):
        raise Fout(400, "Ongeldig abonnement.", "ongeldig")
    apparaat = schoon(data.get("apparaat", ""), 80)
    c.execute(
        "INSERT INTO push_abonnementen (endpoint, gebruiker_id, p256dh, auth, apparaat, gemaakt) VALUES (?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(endpoint) DO UPDATE SET gebruiker_id = excluded.gebruiker_id, p256dh = excluded.p256dh, "
        "auth = excluded.auth, apparaat = excluded.apparaat",
        (endpoint, v.ik["id"], p256dh, auth, apparaat, tijd_tekst()))
    c.commit()
    return {"ok": True}


@route("POST", "/push/weg")
def r_push_weg(v):
    endpoint = v.json().get("endpoint")
    if isinstance(endpoint, str):
        v.c.execute("DELETE FROM push_abonnementen WHERE endpoint = ? AND gebruiker_id = ?", (endpoint, v.ik["id"]))
        v.c.commit()
    return {"ok": True}


@route("POST", "/push/test")
def r_push_test(v):
    v.limiet("pushtest:" + str(v.ik["id"]), 10, 600)
    n = v.c.execute("SELECT COUNT(*) FROM push_abonnementen WHERE gebruiker_id = ?", (v.ik["id"],)).fetchone()[0]
    v.app.push.stuur(v.ik["id"], {"titel": "Het werkt! 🎉", "tekst": "Pushmeldingen staan aan op dit apparaat.",
                                  "link": "/instellingen", "tag": "test"})
    return {"apparaten": n}


# --------------------------------------------------------------------------- beheer: algemeen

def beheer_viering_rij(c, r):
    tellers = c.execute("SELECT COUNT(*) AS n, SUM(status = 'actief') AS actief FROM deelnames WHERE viering_id = ?",
                        (r["id"],)).fetchone()
    return {**viering_kort(r), "locatie": r["locatie"], "menu": bool(r["menu_aan"]), "lootjes": bool(r["lootjes_aan"]),
            "lootjes_getrokken": bool(lootjes_ronde(r)), "deelnemers": tellers["n"], "actief": tellers["actief"] or 0}


@route("GET", "/beheer", "beheer")
def r_beheer(v):
    c = v.c
    inst = instellingen(c, [
        "smtp_host", "smtp_poort", "smtp_beveiliging", "smtp_controleer", "smtp_gebruiker", "smtp_wachtwoord",
        "afzender_naam", "afzender_adres", "app_naam",
    ])
    log = [dict(r) for r in c.execute(
        "SELECT id, aan, onderwerp, status, fout, pogingen, gemaakt, verstuurd, verstuur_na FROM mail_wachtrij ORDER BY id DESC LIMIT 25")]
    accounts = []
    for g in c.execute("SELECT * FROM gebruikers ORDER BY status = 'actief' DESC, naam, email"):
        namen = [r["naam"] for r in c.execute(
            "SELECT v.naam FROM deelnames d JOIN vieringen v ON v.id = d.viering_id WHERE d.gebruiker_id = ? ORDER BY v.naam", (g["id"],))]
        accounts.append({**persoon(g, v.ik["id"]), "email": g["email"], "status": g["status"], "beheerder": bool(g["beheerder"]),
                         "laatst_gezien": g["laatst_gezien"], "vieringen": namen})
    return {
        "vieringen": [beheer_viering_rij(c, r) for r in c.execute(
            "SELECT * FROM vieringen ORDER BY CASE WHEN datum = '' THEN '9999' ELSE datum END, naam")],
        "accounts": accounts,
        "app_naam": inst["app_naam"],
        "smtp": {
            "host": inst["smtp_host"], "poort": inst["smtp_poort"], "beveiliging": inst["smtp_beveiliging"],
            "controleer": inst["smtp_controleer"] == "1", "gebruiker": inst["smtp_gebruiker"],
            "wachtwoord_gezet": bool(inst["smtp_wachtwoord"]),
            "afzender_naam": inst["afzender_naam"], "afzender_adres": inst["afzender_adres"],
        },
        "mail": {
            "wacht": c.execute("SELECT COUNT(*) FROM mail_wachtrij WHERE status IN ('wacht', 'bezig')").fetchone()[0],
            "mislukt": c.execute("SELECT COUNT(*) FROM mail_wachtrij WHERE status = 'mislukt'").fetchone()[0],
            "log": log,
        },
        "push": {"actief": v.app.push.actief, "apparaten": c.execute("SELECT COUNT(*) FROM push_abonnementen").fetchone()[0]},
        "site": v.app.site_url,
        "themas": [{"id": k, "naam": t["naam"], "emoji": t["emoji"]} for k, t in THEMAS.items()],
    }


def controleer_slug(c, slug, behalve=None):
    probleem = slug_probleem(slug)
    if probleem:
        raise Fout(400, probleem, "link", veld="slug")
    r = c.execute("SELECT id FROM vieringen WHERE slug = ?", (slug,)).fetchone()
    if r is not None and r["id"] != behalve:
        raise Fout(409, "Deze link is al in gebruik. Kies een andere.", "link_bezet", veld="slug")


@route("GET", "/beheer/link", "beheer")
def r_link_vrij(v):
    """Live controle in het formulier: is deze link nog vrij?"""
    slug = (v.query.get("slug") or "").strip().lower()
    voorstel = v.query.get("naam")
    if voorstel is not None and not slug:
        slug = maak_slug(voorstel)
    try:
        behalve = int(v.query.get("behalve", 0)) or None
    except ValueError:
        behalve = None
    try:
        controleer_slug(v.c, slug, behalve)
        return {"slug": slug, "vrij": True}
    except Fout as f:
        return {"slug": slug, "vrij": False, "probleem": f.melding}


def viering_velden(c, data, huidig=None):
    """Leest en controleert de velden van een viering. Velden die ontbreken blijven zoals ze waren."""
    uit = {}

    def heeft(k):
        return huidig is None or k in data

    if heeft("naam"):
        uit["naam"] = tekst_veld(data, "naam", 1, 60, "een naam voor de viering")
    if heeft("slug"):
        slug = schoon(data.get("slug", ""), 60).lower()
        controleer_slug(c, slug, huidig["id"] if huidig is not None else None)
        uit["slug"] = slug
    if heeft("thema"):
        uit["thema"] = data.get("thema") if data.get("thema") in THEMAS else "standaard"
    if heeft("datum"):
        datum = schoon(data.get("datum", ""), 10)
        if datum:
            try:
                datetime.date.fromisoformat(datum)
            except ValueError:
                raise Fout(400, "Kies een geldige datum.", "datum", veld="datum")
        uit["datum"] = datum
    if heeft("tijd"):
        tijd = schoon(data.get("tijd", ""), 5)
        if tijd and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", tijd):
            raise Fout(400, "Kies een geldige tijd, bijvoorbeeld 18:00.", "tijd", veld="tijd")
        uit["tijd"] = tijd
    if heeft("locatie"):
        uit["locatie"] = schoon(data.get("locatie", ""), 200)
    if heeft("welkomst"):
        uit["welkomst"] = schoon(data.get("welkomst", ""), 800, regels=True)
    if heeft("budget"):
        budget = schoon(data.get("budget", ""), 40)
        if re.match(r"^\d+([.,]\d{1,2})?$", budget):
            budget = "€ " + budget
        uit["budget"] = budget
    for k in ("gedicht", "surprise"):
        if heeft(k):
            uit[k] = data.get(k) if data.get(k) in REGEL_KEUZES else ""
    if heeft("regels"):
        regels = regels_lijst(schoon(data.get("regels", ""), 2000, regels=True))[:15]
        uit["regels"] = "\n".join(schoon(r, 160) for r in regels)
    if heeft("menu"):
        uit["menu_aan"] = 1 if data.get("menu", True) else 0
    if heeft("lootjes"):
        uit["lootjes_aan"] = 1 if data.get("lootjes", True) else 0
    return uit


@route("POST", "/beheer/vieringen", "beheer")
def r_viering_nieuw(v):
    c = v.c
    data = v.json()
    velden = viering_velden(c, data)
    velden["gemaakt"] = tijd_tekst()
    kolommen = ", ".join(velden)
    cur = c.execute(f"INSERT INTO vieringen ({kolommen}) VALUES ({', '.join('?' * len(velden))})", tuple(velden.values()))
    vid = cur.lastrowid
    if data.get("ik_doe_mee", True):
        c.execute("INSERT INTO deelnames (viering_id, gebruiker_id, status, actief_sinds, gemaakt) VALUES (?, ?, 'actief', ?, ?)",
                  (vid, v.ik["id"], tijd_tekst(), tijd_tekst()))
    c.commit()
    return {"ok": True, "slug": velden["slug"]}


@route("PUT", "/beheer/app", "beheer")
def r_app(v):
    naam = tekst_veld(v.json(), "app_naam", 1, 40, "een naam voor de app")
    zet_instelling(v.c, "app_naam", naam)
    v.c.commit()
    return {"ok": True}


@route("PUT", r"/beheer/accounts/(\d+)", "beheer")
def r_account(v, gid):
    c = v.c
    g = gebruiker_of_404(c, int(gid))
    data = v.json()
    if "beheerder" in data:
        if g["id"] == v.ik["id"] and not data["beheerder"]:
            raise Fout(400, "Je kunt jezelf niet als beheerder weghalen.", "zelf")
        c.execute("UPDATE gebruikers SET beheerder = ? WHERE id = ?", (1 if data["beheerder"] else 0, g["id"]))
    if "naam" in data:
        c.execute("UPDATE gebruikers SET naam = ? WHERE id = ?", (schoon(data.get("naam"), 40), g["id"]))
    c.commit()
    return {"ok": True}


def in_actieve_trekking(c, gid):
    for r in c.execute("SELECT v.* FROM lootjes l JOIN vieringen v ON v.id = l.viering_id "
                       "WHERE (l.gever_id = ? OR l.ontvanger_id = ?) AND l.ronde = v.lootjes_ronde", (gid, gid)):
        if lootjes_ronde(r):
            return r
    return None


@route("DELETE", r"/beheer/accounts/(\d+)", "beheer")
def r_account_weg(v, gid):
    c = v.c
    g = gebruiker_of_404(c, int(gid))
    if g["id"] == v.ik["id"]:
        raise Fout(400, "Je kunt je eigen account niet verwijderen.", "zelf")
    vi = in_actieve_trekking(c, g["id"])
    if vi is not None:
        raise Fout(409, f"{weergavenaam(g)} zit in de lootjestrekking van {vi['naam']}. Maak die eerst ongedaan.", "in_trekking")
    c.execute("DELETE FROM gebruikers WHERE id = ?", (g["id"],))
    c.commit()
    return {"ok": True}


@route("PUT", "/beheer/smtp", "beheer")
def r_smtp(v):
    c = v.c
    data = v.json()
    host = schoon(data.get("host", ""), 200)
    if host and not re.match(r"^[A-Za-z0-9.-]+$", host):
        raise Fout(400, "De naam van de mailserver klopt niet.", "host", veld="host")
    try:
        poort = int(data.get("poort") or 587)
        if not 1 <= poort <= 65535:
            raise ValueError
    except (TypeError, ValueError):
        raise Fout(400, "Vul een geldige poort in (meestal 587).", "poort", veld="poort")
    beveiliging = data.get("beveiliging") if data.get("beveiliging") in ("starttls", "ssl", "geen") else "starttls"
    afzender_adres = schoon(data.get("afzender_adres", ""), 254)
    if afzender_adres and not geldig_email(afzender_adres):
        raise Fout(400, "Het afzenderadres klopt niet.", "email", veld="afzender_adres")
    zet_instelling(c, "smtp_host", host)
    zet_instelling(c, "smtp_poort", poort)
    zet_instelling(c, "smtp_beveiliging", beveiliging)
    zet_instelling(c, "smtp_controleer", "1" if data.get("controleer", True) else "0")
    zet_instelling(c, "smtp_gebruiker", schoon(data.get("gebruiker", ""), 254))
    if isinstance(data.get("wachtwoord"), str) and data["wachtwoord"]:
        zet_instelling(c, "smtp_wachtwoord", data["wachtwoord"][:300])
    if data.get("wis_wachtwoord"):
        zet_instelling(c, "smtp_wachtwoord", "")
    zet_instelling(c, "afzender_naam", schoon(data.get("afzender_naam", ""), 80))
    zet_instelling(c, "afzender_adres", afzender_adres)
    # Mails die stonden te wachten op de instellingen, meteen weer proberen.
    c.execute("UPDATE mail_wachtrij SET verstuur_na = ? WHERE status = 'wacht' AND pogingen = 0", (tijd_tekst(),))
    c.commit()
    v.app.postbode.wek()
    return {"ok": True}


@route("POST", "/beheer/smtp/test", "beheer")
def r_smtp_test(v):
    c = v.c
    v.limiet("smtptest", 10, 600)
    aan = schoon(v.json().get("aan", "") or v.ik["email"], 254)
    if not geldig_email(aan):
        raise Fout(400, "Vul een geldig e-mailadres in.", "email", veld="aan")
    app_naam = instelling(c, "app_naam", "plan-r")
    try:
        verstuur_direct(c, v.app.site_url, aan, {
            "kop": "Het werkt! 🎉",
            "intro": f"Dit is een testmail van {app_naam}. De mailinstellingen kloppen: uitnodigingen en meldingen komen aan.",
            "knop_tekst": "Naar de app", "knop_pad": "/",
            "voet": "Deze mail is verstuurd vanuit het beheer.",
        }, f"Testmail van {app_naam}")
    except Exception as e:  # noqa: BLE001
        raise Fout(502, f"Versturen is mislukt: {type(e).__name__}: {e}", "smtp")
    return {"ok": True, "aan": aan}


@route("POST", "/beheer/mail/opnieuw", "beheer")
def r_mail_opnieuw(v):
    n = v.c.execute("UPDATE mail_wachtrij SET status = 'wacht', pogingen = 0, verstuur_na = ? WHERE status = 'mislukt' OR status = 'wacht'",
                    (tijd_tekst(),)).rowcount
    v.c.commit()
    v.app.postbode.wek()
    return {"ok": True, "aantal": n}


# --------------------------------------------------------------------------- beheer: één viering

def lootjes_stand(c, vi):
    ronde = lootjes_ronde(vi)
    mee = c.execute("SELECT g.*, d.status AS d_status FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id "
                    "WHERE d.viering_id = ? AND d.doet_mee = 1", (vi["id"],)).fetchall()
    return {
        "aan": bool(vi["lootjes_aan"]),
        "actief": bool(ronde),
        "ronde": ronde,
        "getrokken_op": vi["lootjes_getrokken_op"] if ronde else "",
        "mee": len(mee),
        "mee_actief": sum(1 for g in mee if g["d_status"] == "actief" and g["status"] == "actief"),
        "wachten_op": [weergavenaam(g) for g in mee if g["d_status"] != "actief" or g["status"] != "actief"],
        "in_trekking": c.execute("SELECT COUNT(*) FROM lootjes WHERE viering_id = ? AND ronde = ?", (vi["id"], ronde)).fetchone()[0] if ronde else 0,
        "geopend": c.execute("SELECT COUNT(*) FROM lootjes WHERE viering_id = ? AND ronde = ? AND geopend IS NOT NULL",
                             (vi["id"], ronde)).fetchone()[0] if ronde else 0,
        "minimum": MIN_LOOTJES,
    }


@route("GET", r"/beheer/v/" + SLUG, "vbeheer")
def r_vbeheer(v):
    c = v.c
    vi = v.viering
    ronde = lootjes_ronde(vi)
    deelnemers = []
    for g in c.execute(
            "SELECT g.*, d.status AS d_status, d.doet_mee, d.uitgenodigd_op, d.actief_sinds AS d_actief_sinds "
            "FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id WHERE d.viering_id = ? ORDER BY d.gemaakt, g.id", (vi["id"],)):
        deelnemers.append({
            **persoon(g, v.ik["id"]),
            "email": g["email"],
            "voornaam": g["naam"],
            "status": g["d_status"],
            "account": g["status"],
            "beheerder": bool(g["beheerder"]),
            "doet_mee": bool(g["doet_mee"]),
            "uitgenodigd_op": g["uitgenodigd_op"],
            "actief_sinds": g["d_actief_sinds"],
            "laatst_gezien": g["laatst_gezien"],
            "in_trekking": bool(ronde) and c.execute(
                "SELECT 1 FROM lootjes WHERE viering_id = ? AND ronde = ? AND gever_id = ?", (vi["id"], ronde, g["id"])).fetchone() is not None,
        })
    ik_lid = any(d["ik"] for d in deelnemers)
    return {
        "viering": {**viering_json(vi), "regels_tekst": vi["regels"]},
        "deelnemers": deelnemers,
        "lootjes": lootjes_stand(c, vi),
        "ik_doe_mee": ik_lid,
        "themas": [{"id": k, "naam": t["naam"], "emoji": t["emoji"]} for k, t in THEMAS.items()],
        "site": v.app.site_url,
    }


@route("PUT", r"/beheer/v/" + SLUG, "vbeheer")
def r_vbeheer_opslaan(v):
    c = v.c
    oud = v.viering
    data = v.json()
    velden = viering_velden(c, data, huidig=oud)
    if velden:
        c.execute(f"UPDATE vieringen SET {', '.join(k + ' = ?' for k in velden)} WHERE id = ?", (*velden.values(), oud["id"]))
        c.commit()
    nieuw = c.execute("SELECT * FROM vieringen WHERE id = ?", (oud["id"],)).fetchone()
    namen = {"naam": "Naam", "datum": "Datum", "tijd": "Tijd", "locatie": "Waar", "budget": "Maximale prijs",
             "gedicht": "Gedicht", "surprise": "Surprise", "regels": "Spelregels"}
    regels = []
    for k, label in namen.items():
        if nieuw[k] != oud[k]:
            waarde = nieuw[k]
            if k == "datum" and waarde:
                waarde = datum_tekst({"datum": waarde, "tijd": ""})
            if k in ("gedicht", "surprise"):
                waarde = REGEL_KEUZES.get(waarde, "")
            if k == "regels":
                waarde = "; ".join(regels_lijst(waarde))
            regels.append(f"{label}: {waarde or '(geen)'}")
    if regels and data.get("melden"):
        v.app.melder.meld(
            c, leden(c, nieuw["id"], behalve=v.ik["id"]), "algemeen", f"{nieuw['naam']} is bijgewerkt", "\n".join(regels),
            f"/{nieuw['slug']}", viering=nieuw, onderwerp=f"Nieuws over {nieuw['naam']}",
            mail={"kop": f"Nieuws over {nieuw['naam']}", "intro": "De organisator heeft iets aangepast:", "regels": regels,
                  "knop_tekst": "Bekijk de viering", "knop_pad": f"/{nieuw['slug']}"},
        )
    return {"ok": True, "slug": nieuw["slug"], "gewijzigd": len(regels)}


@route("DELETE", r"/beheer/v/" + SLUG, "vbeheer")
def r_vbeheer_weg(v):
    if v.json().get("bevestig") != v.viering["slug"]:
        raise Fout(400, "Typ de link van de viering ter bevestiging.", "bevestig", veld="bevestig")
    v.c.execute("DELETE FROM vieringen WHERE id = ?", (v.viering["id"],))
    v.c.execute("DELETE FROM meldingen WHERE viering_id IS NULL AND link LIKE ?", (f"/{v.viering['slug']}%",))
    v.c.commit()
    return {"ok": True}


def lees_adressen(tekst):
    """Haalt namen en e-mailadressen uit vrije tekst: 'anna@x.nl', 'Anna <anna@x.nl>', 'Anna, anna@x.nl'."""
    uit, ongeldig = [], []
    for regel in re.split(r"[\n;]+", tekst or ""):
        regel = regel.strip()
        if not regel:
            continue
        adressen = re.findall(r"[^\s<>,;\"'()]+@[^\s<>,;\"'()]+", regel)
        if not adressen:
            ongeldig.append(regel[:80])
            continue
        if len(adressen) > 1:
            for a in adressen:
                if geldig_email(a):
                    uit.append(("", a.lower()))
                else:
                    ongeldig.append(a[:80])
            continue
        adres = adressen[0]
        naam = schoon(re.sub(r"[<>,\"'()]", " ", regel.replace(adres, " ")), 40)
        if geldig_email(adres):
            uit.append((naam, adres.lower()))
        else:
            ongeldig.append(adres[:80])
    return uit, ongeldig


@route("POST", r"/beheer/v/" + SLUG + r"/uitnodigen", "vbeheer")
def r_uitnodigen(v):
    c = v.c
    vi = v.viering
    paren, ongeldig = lees_adressen(v.json().get("tekst", ""))
    if not paren and not ongeldig:
        raise Fout(400, "Vul minstens één e-mailadres in.", "leeg", veld="tekst")
    toegevoegd, bestond = [], []
    afzender = weergavenaam(v.ik)
    for naam, adres in paren[:200]:
        g = c.execute("SELECT * FROM gebruikers WHERE email = ?", (adres,)).fetchone()
        if g is None:
            cur = c.execute("INSERT INTO gebruikers (email, naam, status, toon, gemaakt) VALUES (?, ?, 'uitgenodigd', ?, ?)",
                            (adres, naam, random.randint(0, 5), tijd_tekst()))
            g = gebruiker_of_404(c, cur.lastrowid)
        elif c.execute("SELECT 1 FROM deelnames WHERE viering_id = ? AND gebruiker_id = ?", (vi["id"], g["id"])).fetchone():
            bestond.append(adres)
            continue
        zelf = g["id"] == v.ik["id"]
        c.execute("INSERT INTO deelnames (viering_id, gebruiker_id, status, actief_sinds, gemaakt) VALUES (?, ?, ?, ?, ?)",
                  (vi["id"], g["id"], "actief" if zelf else "uitgenodigd", tijd_tekst() if zelf else None, tijd_tekst()))
        if not zelf:
            uitnodiging_mail(v.app, c, g, vi, afzender)
        toegevoegd.append(adres)
    c.commit()
    return {"toegevoegd": toegevoegd, "bestond": bestond, "ongeldig": ongeldig}


@route("POST", r"/beheer/v/" + SLUG + r"/ikdoemee", "vbeheer")
def r_ikdoemee(v):
    c = v.c
    c.execute("INSERT INTO deelnames (viering_id, gebruiker_id, status, actief_sinds, gemaakt) VALUES (?, ?, 'actief', ?, ?) "
              "ON CONFLICT(viering_id, gebruiker_id) DO UPDATE SET status = 'actief', actief_sinds = COALESCE(actief_sinds, excluded.actief_sinds)",
              (v.viering["id"], v.ik["id"], tijd_tekst(), tijd_tekst()))
    c.commit()
    return {"ok": True}


def deelname_of_404(v, gid):
    d = v.c.execute("SELECT d.*, g.naam, g.email, g.status AS account FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id "
                    "WHERE d.viering_id = ? AND d.gebruiker_id = ?", (v.viering["id"], gid)).fetchone()
    if d is None:
        raise Fout(404, "Deze persoon doet niet mee met deze viering.", "niet_gevonden")
    return d


@route("POST", r"/beheer/v/" + SLUG + r"/deelnemers/(\d+)/uitnodigen", "vbeheer")
def r_opnieuw_uitnodigen(v, gid):
    c = v.c
    d = deelname_of_404(v, int(gid))
    v.limiet(f"opnieuw:{v.viering['id']}:{gid}", 6, 3600, "Je hebt deze uitnodiging net al een paar keer verstuurd.")
    if d["status"] == "actief":
        raise Fout(400, f"{weergavenaam(d)} doet al mee.", "al_actief")
    uitnodiging_mail(v.app, c, gebruiker_of_404(c, int(gid)), v.viering, weergavenaam(v.ik))
    return {"ok": True}


@route("PUT", r"/beheer/v/" + SLUG + r"/deelnemers/(\d+)", "vbeheer")
def r_deelnemer_wijzig(v, gid):
    c = v.c
    d = deelname_of_404(v, int(gid))
    data = v.json()
    if "doet_mee" in data:
        c.execute("UPDATE deelnames SET doet_mee = ? WHERE viering_id = ? AND gebruiker_id = ?",
                  (1 if data["doet_mee"] else 0, v.viering["id"], d["gebruiker_id"]))
    if "naam" in data and d["account"] != "actief":
        c.execute("UPDATE gebruikers SET naam = ? WHERE id = ?", (schoon(data.get("naam"), 40), d["gebruiker_id"]))
    c.commit()
    return {"ok": True}


@route("DELETE", r"/beheer/v/" + SLUG + r"/deelnemers/(\d+)", "vbeheer")
def r_deelnemer_weg(v, gid):
    c = v.c
    vi = v.viering
    d = deelname_of_404(v, int(gid))
    ronde = lootjes_ronde(vi)
    if ronde and c.execute("SELECT 1 FROM lootjes WHERE viering_id = ? AND ronde = ? AND (gever_id = ? OR ontvanger_id = ?)",
                           (vi["id"], ronde, d["gebruiker_id"], d["gebruiker_id"])).fetchone():
        raise Fout(409, f"{weergavenaam(d)} zit in de lootjestrekking. Maak die eerst ongedaan.", "in_trekking")
    c.execute("DELETE FROM deelnames WHERE viering_id = ? AND gebruiker_id = ?", (vi["id"], d["gebruiker_id"]))
    c.execute("DELETE FROM tokens WHERE viering_id = ? AND gebruiker_id = ?", (vi["id"], d["gebruiker_id"]))
    # Nooit aangemeld en nergens anders uitgenodigd: account opruimen.
    if d["account"] != "actief" and not c.execute("SELECT 1 FROM deelnames WHERE gebruiker_id = ?", (d["gebruiker_id"],)).fetchone():
        c.execute("DELETE FROM gebruikers WHERE id = ?", (d["gebruiker_id"],))
    c.commit()
    return {"ok": True}


def trek(ids):
    """Willekeurige verdeling waarbij niemand zichzelf trekt."""
    kans = secrets.SystemRandom()
    for _ in range(10000):
        verdeling = ids[:]
        kans.shuffle(verdeling)
        if all(a != b for a, b in zip(ids, verdeling)):
            return list(zip(ids, verdeling))
    raise Fout(500, "Het trekken is niet gelukt. Probeer het nog eens.", "server")


@route("POST", r"/beheer/v/" + SLUG + r"/lootjes", "vbeheer")
def r_lootjes(v):
    c = v.c
    vi = v.viering
    data = v.json()
    actie = data.get("actie")
    if not vi["lootjes_aan"]:
        raise Fout(400, "Zet eerst het onderdeel lootjes aan bij de instellingen van deze viering.", "module_uit")
    ronde = lootjes_ronde(vi)
    if actie == "ongedaan":
        if not ronde:
            raise Fout(400, "Er zijn geen lootjes getrokken.", "niet_getrokken")
        deelnemers = [r["gever_id"] for r in c.execute("SELECT gever_id FROM lootjes WHERE viering_id = ? AND ronde = ?", (vi["id"], ronde))]
        c.execute("UPDATE vieringen SET lootjes_actief = 0 WHERE id = ?", (vi["id"],))
        c.commit()
        v.app.melder.meld(
            c, deelnemers, "lootje", "De lootjestrekking is ongedaan gemaakt",
            "De organisator trekt de lootjes binnenkort opnieuw. Je krijgt dan weer een melding.", v.link("/lootje"), viering=vi,
            onderwerp=f"{vi['naam']}: de lootjestrekking is ongedaan gemaakt",
            mail={"kop": "De lootjestrekking is ongedaan gemaakt",
                  "intro": "De organisator heeft de lootjestrekking teruggedraaid. Binnenkort worden de lootjes opnieuw getrokken; je krijgt dan weer bericht.",
                  "knop_tekst": "Naar de viering", "knop_pad": v.link()},
        )
        return {"ok": True}
    if actie != "trekken":
        raise Fout(400, "Onbekende actie.", "ongeldig")
    if ronde and not data.get("opnieuw"):
        raise Fout(409, "De lootjes zijn al getrokken.", "al_getrokken")
    mee = c.execute("SELECT g.*, d.status AS d_status FROM deelnames d JOIN gebruikers g ON g.id = d.gebruiker_id "
                    "WHERE d.viering_id = ? AND d.doet_mee = 1 ORDER BY g.id", (vi["id"],)).fetchall()
    klaar = [g for g in mee if g["d_status"] == "actief" and g["status"] == "actief"]
    wachten = [weergavenaam(g) for g in mee if g not in klaar]
    if wachten and not data.get("alleen_actief"):
        raise Fout(409, "Nog niet iedereen heeft zich aangemeld.", "niet_iedereen", wachten_op=wachten)
    pool = [g["id"] for g in klaar]
    if len(pool) < MIN_LOOTJES:
        raise Fout(400, f"Er zijn minstens {MIN_LOOTJES} aangemelde deelnemers nodig om lootjes te trekken.", "te_weinig")
    nieuwe_ronde = vi["lootjes_ronde"] + 1
    for gever, ontvanger in trek(pool):
        c.execute("INSERT INTO lootjes (viering_id, ronde, gever_id, ontvanger_id) VALUES (?, ?, ?, ?)", (vi["id"], nieuwe_ronde, gever, ontvanger))
    c.execute("UPDATE vieringen SET lootjes_ronde = ?, lootjes_actief = 1, lootjes_getrokken_op = ? WHERE id = ?",
              (nieuwe_ronde, tijd_tekst(), vi["id"]))
    c.commit()
    vi = c.execute("SELECT * FROM vieringen WHERE id = ?", (vi["id"],)).fetchone()
    opnieuw = bool(ronde)
    titel = "De lootjes zijn opnieuw getrokken!" if opnieuw else "De lootjes zijn getrokken!"
    intro = "Open de app en ontdek wie jij hebt getrokken."
    if opnieuw:
        intro = "De lootjes zijn opnieuw getrokken, dus je hebt misschien iemand anders. " + intro
    regels = ["Bekijk het verlanglijstje van je lootje", "Vink af wat je al hebt gekocht (alleen jij ziet dat)",
              "Stuur je lootje anoniem een berichtje"]
    keuze = {"wel": "Met een {}", "geen": "Geen {}", "mag": "Een {} mag, hoeft niet"}
    extra = [f"Maximale prijs: {vi['budget']}"] if vi["budget"] else []
    for k in ("gedicht", "surprise"):
        if vi[k] in keuze:
            extra.append(keuze[vi[k]].format(k))
    extra += regels_lijst(vi["regels"])
    regels = extra + regels
    v.app.melder.meld(
        c, pool, "lootje", titel + " 🎁", "Open de app en ontdek wie jij hebt getrokken.", f"/{vi['slug']}/lootje", viering=vi,
        onderwerp=f"{vi['naam']}: {titel[0].lower() + titel[1:]}",
        mail={"kop": titel, "intro": intro, "regels": regels, "knop_tekst": "Bekijk je lootje", "knop_pad": f"/{vi['slug']}/lootje"},
    )
    return {"ok": True, "deelnemers": len(pool)}


# --------------------------------------------------------------------------- HTTP-handler

def maak_handler(app):
    class Handler(SimpleHTTPRequestHandler):
        server_version = "plan-r/" + VERSIE
        sys_version = ""
        protocol_version = "HTTP/1.1"

        def log_message(self, formaat, *args):
            pass

        def end_headers(self):
            if app.statisch and not self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-cache")
            super().end_headers()

        def stuur_json(self, status, data, cookies=()):
            lichaam = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for cookie in cookies:
                self.send_header("Set-Cookie", cookie)
            self.send_header("Content-Length", str(len(lichaam)))
            self.end_headers()
            self.wfile.write(lichaam)

        def is_api(self):
            return self.path == "/api" or self.path.startswith("/api/")

        def api(self, methode):
            delen = urlsplit(self.path)
            pad = delen.path[4:].rstrip("/") or "/"
            # De body altijd helemaal lezen, ook als de route hem niet gebruikt; anders blijft hij
            # in de (keep-alive) verbinding hangen en breekt hij het volgende verzoek.
            try:
                lengte = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                lengte = 0
            if lengte > MAX_LICHAAM:
                self.close_connection = True
                return self.stuur_json(413, {"fout": "Dat is te veel tekst.", "code": "te_groot"})
            v = Verzoek(self, app, delen, self.rfile.read(lengte) if lengte > 0 else b"")
            try:
                if methode != "GET" and self.headers.get("X-Planr") != "1":
                    raise Fout(403, "Ongeldig verzoek.", "csrf")
                for m, patroon, toegang, functie in ROUTES:
                    if m != methode:
                        continue
                    gevonden = patroon.match(pad)
                    if not gevonden:
                        continue
                    v.open()
                    groepen = gevonden.groups()
                    if toegang is not None:
                        v.vereis_lid()
                    if toegang in ("beheer", "vbeheer") and not v.ik["beheerder"]:
                        raise Fout(403, "Dit is alleen voor de organisator.", "geen_beheerder")
                    if toegang in ("viering", "vbeheer"):
                        v.laad_viering(groepen[0], als_beheerder=(toegang == "vbeheer"))
                        groepen = groepen[1:]
                    uit = functie(v, *groepen)
                    return self.stuur_json(200, uit, v.cookies)
                raise Fout(404, "Niet gevonden.", "niet_gevonden")
            except Fout as f:
                self.stuur_json(f.status, {"fout": f.melding, "code": f.code, **f.extra}, v.cookies)
            except Exception as e:  # noqa: BLE001
                print(f"[plan-r] fout bij {methode} {delen.path}: {e!r}", file=sys.stderr, flush=True)
                import traceback
                traceback.print_exc()
                self.stuur_json(500, {"fout": "Er ging iets mis op de server.", "code": "server"})
            finally:
                v.sluit()

        def do_GET(self):
            if self.is_api():
                return self.api("GET")
            if app.statisch:
                pad = unquote(urlsplit(self.path).path)
                volledig = os.path.normpath(os.path.join(app.statisch, pad.lstrip("/")))
                if not volledig.startswith(app.statisch) or not os.path.exists(volledig):
                    if "." not in os.path.basename(pad):
                        self.path = "/index.html"
                return super().do_GET()
            self.stuur_json(404, {"fout": "Niet gevonden."})

        def do_HEAD(self):
            if app.statisch and not self.is_api():
                return super().do_HEAD()
            self.stuur_json(405, {"fout": "Niet toegestaan."})

        def do_POST(self):
            self.api("POST")

        def do_PUT(self):
            self.api("PUT")

        def do_DELETE(self):
            self.api("DELETE")

    return Handler
