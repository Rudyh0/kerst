"""Database en kleine hulpjes voor Kerst.

Alles staat in één SQLite-bestand. Elke aanvraag opent een eigen verbinding;
de achtergronddiensten (post, push) ook.
"""
import datetime
import hashlib
import json
import os
import re
import secrets
import sqlite3

SCHEMA_VERSIE = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS instellingen (
  sleutel TEXT PRIMARY KEY,
  waarde TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gebruikers (
  id INTEGER PRIMARY KEY,
  email TEXT NOT NULL UNIQUE COLLATE NOCASE,
  naam TEXT NOT NULL DEFAULT '',
  wachtwoord TEXT,
  beheerder INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'uitgenodigd',
  toon INTEGER NOT NULL DEFAULT 0,
  voorkeuren TEXT NOT NULL DEFAULT '{}',
  actief_sinds TEXT,
  laatst_gezien TEXT,
  gemaakt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS vieringen (
  id INTEGER PRIMARY KEY,
  slug TEXT NOT NULL UNIQUE,
  naam TEXT NOT NULL,
  thema TEXT NOT NULL DEFAULT 'standaard',
  datum TEXT NOT NULL DEFAULT '',
  tijd TEXT NOT NULL DEFAULT '',
  locatie TEXT NOT NULL DEFAULT '',
  welkomst TEXT NOT NULL DEFAULT '',
  budget TEXT NOT NULL DEFAULT '',
  gedicht TEXT NOT NULL DEFAULT '',
  surprise TEXT NOT NULL DEFAULT '',
  regels TEXT NOT NULL DEFAULT '',
  menu_aan INTEGER NOT NULL DEFAULT 1,
  lootjes_aan INTEGER NOT NULL DEFAULT 1,
  lootjes_actief INTEGER NOT NULL DEFAULT 0,
  lootjes_ronde INTEGER NOT NULL DEFAULT 0,
  lootjes_getrokken_op TEXT NOT NULL DEFAULT '',
  gemaakt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS deelnames (
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  status TEXT NOT NULL DEFAULT 'uitgenodigd',
  doet_mee INTEGER NOT NULL DEFAULT 1,
  uitgenodigd_op TEXT,
  actief_sinds TEXT,
  gemaakt TEXT NOT NULL,
  PRIMARY KEY (viering_id, gebruiker_id)
);
CREATE TABLE IF NOT EXISTS tokens (
  hash TEXT PRIMARY KEY,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  viering_id INTEGER REFERENCES vieringen(id) ON DELETE CASCADE,
  soort TEXT NOT NULL,
  verloopt TEXT NOT NULL,
  gemaakt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessies (
  hash TEXT PRIMARY KEY,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  gemaakt TEXT NOT NULL,
  verloopt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gerechten (
  id INTEGER PRIMARY KEY,
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  gang TEXT NOT NULL,
  naam TEXT NOT NULL,
  toelichting TEXT NOT NULL DEFAULT '',
  gemaakt TEXT NOT NULL,
  bijgewerkt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drankjes (
  id INTEGER PRIMARY KEY,
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  tekst TEXT NOT NULL,
  gemaakt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS drank_stemmen (
  drank_id INTEGER NOT NULL REFERENCES drankjes(id) ON DELETE CASCADE,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  PRIMARY KEY (drank_id, gebruiker_id)
);
CREATE TABLE IF NOT EXISTS wensen (
  id INTEGER PRIMARY KEY,
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  titel TEXT NOT NULL,
  toelichting TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL DEFAULT '',
  prijs TEXT NOT NULL DEFAULT '',
  volgorde INTEGER NOT NULL DEFAULT 0,
  gemaakt TEXT NOT NULL,
  bijgewerkt TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lootjes (
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  ronde INTEGER NOT NULL,
  gever_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  ontvanger_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  geopend TEXT,
  notities TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (viering_id, ronde, gever_id)
);
CREATE TABLE IF NOT EXISTS afgevinkt (
  gever_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  wens_id INTEGER NOT NULL REFERENCES wensen(id) ON DELETE CASCADE,
  gemaakt TEXT NOT NULL,
  PRIMARY KEY (gever_id, wens_id)
);
CREATE TABLE IF NOT EXISTS berichten (
  id INTEGER PRIMARY KEY,
  viering_id INTEGER NOT NULL REFERENCES vieringen(id) ON DELETE CASCADE,
  ronde INTEGER NOT NULL,
  gever_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  ontvanger_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  van_gever INTEGER NOT NULL,
  tekst TEXT NOT NULL,
  gemaakt TEXT NOT NULL,
  gelezen TEXT
);
CREATE TABLE IF NOT EXISTS meldingen (
  id INTEGER PRIMARY KEY,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  viering_id INTEGER REFERENCES vieringen(id) ON DELETE CASCADE,
  soort TEXT NOT NULL,
  titel TEXT NOT NULL,
  tekst TEXT NOT NULL DEFAULT '',
  link TEXT NOT NULL DEFAULT '',
  bundel TEXT,
  gemaakt TEXT NOT NULL,
  gelezen TEXT
);
CREATE TABLE IF NOT EXISTS push_abonnementen (
  endpoint TEXT PRIMARY KEY,
  gebruiker_id INTEGER NOT NULL REFERENCES gebruikers(id) ON DELETE CASCADE,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  apparaat TEXT NOT NULL DEFAULT '',
  gemaakt TEXT NOT NULL,
  laatst_ok TEXT
);
CREATE TABLE IF NOT EXISTS mail_wachtrij (
  id INTEGER PRIMARY KEY,
  aan TEXT NOT NULL,
  naam TEXT NOT NULL DEFAULT '',
  onderwerp TEXT NOT NULL,
  soort TEXT NOT NULL,
  bundel TEXT,
  data TEXT NOT NULL,
  verstuur_na TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'wacht',
  pogingen INTEGER NOT NULL DEFAULT 0,
  fout TEXT NOT NULL DEFAULT '',
  gemaakt TEXT NOT NULL,
  verstuurd TEXT
);
CREATE INDEX IF NOT EXISTS meldingen_gebruiker ON meldingen(gebruiker_id, id);
CREATE INDEX IF NOT EXISTS berichten_paar ON berichten(viering_id, ronde, gever_id, ontvanger_id);
CREATE INDEX IF NOT EXISTS wensen_gebruiker ON wensen(viering_id, gebruiker_id, volgorde);
CREATE INDEX IF NOT EXISTS gerechten_viering ON gerechten(viering_id);
CREATE INDEX IF NOT EXISTS drankjes_viering ON drankjes(viering_id);
CREATE INDEX IF NOT EXISTS deelnames_gebruiker ON deelnames(gebruiker_id);
CREATE INDEX IF NOT EXISTS mail_status ON mail_wachtrij(status, verstuur_na);
CREATE INDEX IF NOT EXISTS sessies_gebruiker ON sessies(gebruiker_id);
"""

# Soorten meldingen. Per soort kan iemand e-mail en push aan- of uitzetten.
CATEGORIEEN = ["lootje", "berichten", "wensen", "menu", "algemeen", "deelnemers"]

GANGEN = ["hapjes", "voorgerecht", "soep", "hoofdgerecht", "bijgerecht", "nagerecht", "overig"]
GANG_NAMEN = {
    "hapjes": "Hapjes", "voorgerecht": "Voorgerecht", "soep": "Soep", "hoofdgerecht": "Hoofdgerecht",
    "bijgerecht": "Bijgerecht", "nagerecht": "Nagerecht", "overig": "Overig",
}

# Thema's per viering. 'engel' is hoe de anonieme gever van je lootje heet.
THEMAS = {
    "standaard": {"naam": "Standaard", "emoji": "\U0001F389", "kleur": "#3b5bdb", "engel": "je geheime gever"},
    "kerst": {"naam": "Kerst", "emoji": "\U0001F384", "kleur": "#b3262e", "engel": "je geheime kerstengel"},
    "sinterklaas": {"naam": "Sinterklaas", "emoji": "\U0001F381", "kleur": "#b0182a", "engel": "de Sint"},
    "zomer": {"naam": "Zomer", "emoji": "\u2600\ufe0f", "kleur": "#0c8599", "engel": "je geheime zomergast"},
    "halloween": {"naam": "Halloween", "emoji": "\U0001F383", "kleur": "#d9480f", "engel": "je geheime geest"},
}

# Spelregels voor gedicht en surprise: '' = niet noemen.
REGEL_KEUZES = {"": "", "wel": "Wel", "geen": "Geen", "mag": "Mag, hoeft niet"}

# Woorden die niet als link van een viering mogen, omdat de app ze zelf gebruikt.
GERESERVEERD = {
    "api", "beheer", "inloggen", "uitloggen", "uitnodiging", "herstel", "wachtwoord-vergeten", "instellingen",
    "fonts", "icons", "css", "js", "sw.js", "manifest.webmanifest", "favicon.ico", "robots.txt", "vieringen",
    "nieuw", "status", "static", "assets", "index.html", "admin", "login",
}
SLUG_PATROON = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")

STANDAARD_INSTELLINGEN = {
    "app_naam": "plan-r",
    "smtp_host": "",
    "smtp_poort": "587",
    "smtp_beveiliging": "starttls",
    "smtp_controleer": "1",
    "smtp_gebruiker": "",
    "smtp_wachtwoord": "",
    "afzender_naam": "plan-r",
    "afzender_adres": "",
}

PBKDF2_ITERATIES = 480_000
EMAIL_PATROON = re.compile(r"^[^@\s<>,;\"']+@[^@\s<>,;\"']+\.[^@\s<>,;\"']{2,}$")


def nu():
    return datetime.datetime.now(datetime.timezone.utc)


def tijd_tekst(dt=None):
    return (dt or nu()).isoformat(timespec="seconds")


def lees_tijd(tekst):
    try:
        return datetime.datetime.fromisoformat(tekst)
    except (TypeError, ValueError):
        return None


def over(seconden):
    return tijd_tekst(nu() + datetime.timedelta(seconds=seconden))


def sha(tekst):
    return hashlib.sha256(tekst.encode()).hexdigest()


def schoon(tekst, maximum, regels=False):
    """Haalt stuurtekens weg. Zonder regels wordt alles één regel."""
    if not isinstance(tekst, str):
        return ""
    if regels:
        tekst = tekst.replace("\r\n", "\n").replace("\r", "\n")
        tekst = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", "", tekst)
        tekst = re.sub(r"[ \t]+\n", "\n", tekst)
        tekst = re.sub(r"\n{3,}", "\n\n", tekst)
        return tekst.strip()[:maximum]
    tekst = re.sub(r"[\x00-\x1f\x7f]", " ", tekst)
    return " ".join(tekst.split())[:maximum]


def geldig_email(adres):
    return isinstance(adres, str) and len(adres) <= 254 and EMAIL_PATROON.match(adres) is not None


def hash_wachtwoord(wachtwoord):
    zout = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", wachtwoord.encode(), zout, PBKDF2_ITERATIES)
    return "pbkdf2_sha256$%d$%s$%s" % (PBKDF2_ITERATIES, zout.hex(), h.hex())


def controleer_wachtwoord(wachtwoord, opgeslagen):
    try:
        soort, iteraties, zout, h = (opgeslagen or "").split("$")
        if soort != "pbkdf2_sha256":
            return False
        nieuw = hashlib.pbkdf2_hmac("sha256", wachtwoord.encode(), bytes.fromhex(zout), int(iteraties))
        return secrets.compare_digest(nieuw.hex(), h)
    except (ValueError, TypeError):
        return False


def standaard_voorkeuren():
    return {
        "mail": {k: True for k in CATEGORIEEN},
        "push": {k: True for k in CATEGORIEEN},
    }


def voorkeuren_van(rij):
    v = standaard_voorkeuren()
    try:
        opgeslagen = json.loads(rij["voorkeuren"] or "{}")
    except (TypeError, ValueError):
        opgeslagen = {}
    for kanaal in ("mail", "push"):
        for k, waarde in (opgeslagen.get(kanaal) or {}).items():
            if k in CATEGORIEEN:
                v[kanaal][k] = bool(waarde)
    return v


def weergavenaam(rij):
    naam = (rij["naam"] or "").strip()
    if naam:
        return naam
    return (rij["email"] or "").split("@")[0]


class Database:
    def __init__(self, pad):
        self.pad = pad
        map_ = os.path.dirname(os.path.abspath(pad))
        os.makedirs(map_, exist_ok=True)
        c = self.open()
        c.execute("PRAGMA journal_mode = WAL")
        c.executescript(SCHEMA)
        for sleutel, waarde in STANDAARD_INSTELLINGEN.items():
            c.execute("INSERT OR IGNORE INTO instellingen (sleutel, waarde) VALUES (?, ?)", (sleutel, waarde))
        c.execute("INSERT OR IGNORE INTO instellingen (sleutel, waarde) VALUES ('schema', ?)", (str(SCHEMA_VERSIE),))
        # Na een herstart: mails die halverwege waren gewoon opnieuw proberen.
        c.execute("UPDATE mail_wachtrij SET status = 'wacht' WHERE status = 'bezig'")
        c.commit()
        c.close()

    def open(self):
        c = sqlite3.connect(self.pad, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys = ON")
        c.execute("PRAGMA busy_timeout = 15000")
        return c


def instelling(c, sleutel, standaard=""):
    r = c.execute("SELECT waarde FROM instellingen WHERE sleutel = ?", (sleutel,)).fetchone()
    return r["waarde"] if r else standaard


def instellingen(c, sleutels):
    uit = {k: STANDAARD_INSTELLINGEN.get(k, "") for k in sleutels}
    plekken = ",".join("?" * len(sleutels))
    for r in c.execute(f"SELECT sleutel, waarde FROM instellingen WHERE sleutel IN ({plekken})", tuple(sleutels)):
        uit[r["sleutel"]] = r["waarde"]
    return uit


def zet_instelling(c, sleutel, waarde):
    c.execute(
        "INSERT INTO instellingen (sleutel, waarde) VALUES (?, ?) ON CONFLICT(sleutel) DO UPDATE SET waarde = excluded.waarde",
        (sleutel, str(waarde)),
    )


def slug_probleem(slug):
    """Geeft een uitleg terug als de link niet mag, anders None."""
    if not isinstance(slug, str) or not SLUG_PATROON.match(slug):
        return "Gebruik 3 tot 40 tekens: kleine letters, cijfers en streepjes (niet aan het begin of eind)."
    if slug in GERESERVEERD:
        return "Dit woord gebruikt de app zelf. Kies een andere link."
    if "--" in slug:
        return "Gebruik geen twee streepjes achter elkaar."
    return None


def maak_slug(tekst):
    """Maakt van een naam een voorstel voor de link: 'Kerst met de familie!' -> 'kerst-met-de-familie'."""
    import unicodedata
    tekst = unicodedata.normalize("NFKD", tekst or "").encode("ascii", "ignore").decode().lower()
    tekst = re.sub(r"[^a-z0-9]+", "-", tekst).strip("-")
    tekst = re.sub(r"-{2,}", "-", tekst)[:40].strip("-")
    return tekst if len(tekst) >= 3 else (tekst + "-feest").strip("-")


def thema_van(rij):
    return THEMAS.get(rij["thema"] if rij is not None else "", THEMAS["standaard"])


def lootjes_ronde(viering):
    """De huidige ronde van een viering, of 0 als er (nu) geen lootjes getrokken zijn."""
    if viering is None or not viering["lootjes_aan"] or not viering["lootjes_actief"]:
        return 0
    return viering["lootjes_ronde"]


def maak_token(c, gebruiker_id, soort, geldig_seconden, viering_id=None):
    """Maakt een eenmalige link-code (uitnodiging of wachtwoordherstel). Oude codes van dezelfde soort vervallen."""
    if viering_id is None:
        c.execute("DELETE FROM tokens WHERE gebruiker_id = ? AND soort = ? AND viering_id IS NULL", (gebruiker_id, soort))
    else:
        c.execute("DELETE FROM tokens WHERE gebruiker_id = ? AND soort = ? AND viering_id = ?", (gebruiker_id, soort, viering_id))
    c.execute("DELETE FROM tokens WHERE verloopt < ?", (tijd_tekst(),))
    token = secrets.token_urlsafe(24)
    c.execute(
        "INSERT INTO tokens (hash, gebruiker_id, viering_id, soort, verloopt, gemaakt) VALUES (?, ?, ?, ?, ?, ?)",
        (sha(token), gebruiker_id, viering_id, soort, over(geldig_seconden), tijd_tekst()),
    )
    return token


def zoek_token(c, token, soort):
    """Geeft (gebruiker, viering_id) terug of (None, None)."""
    if not isinstance(token, str) or not re.match(r"^[A-Za-z0-9_-]{20,64}$", token):
        return None, None
    r = c.execute(
        "SELECT g.*, t.viering_id AS token_viering FROM tokens t JOIN gebruikers g ON g.id = t.gebruiker_id "
        "WHERE t.hash = ? AND t.soort = ? AND t.verloopt > ?",
        (sha(token), soort, tijd_tekst()),
    ).fetchone()
    if r is None:
        return None, None
    return r, r["token_viering"]
