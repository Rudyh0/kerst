#!/usr/bin/env python3
"""plan-r: samen een feest plannen. Per viering een eigen link en thema, met een
gezamenlijk menu en/of lootjes trekken met verlanglijstjes.

Alleen Python 3 en SQLite. Voor pushmeldingen ook python3-cryptography.
nginx stuurt /api/ door naar deze dienst, die alleen op 127.0.0.1 luistert.

Gebruik:
  planr.py serveer   --db /var/lib/plan-r/planr.db --poort 8810 --url https://kerst.rudymedia.nl
  planr.py serveer   --db test.db --poort 8000 --url http://localhost:8000 --statisch web   (lokaal testen)
  planr.py beheerder --db ... --email jij@voorbeeld.nl [--naam Rudy] --url https://...
                     maakt (of herstelt) een beheerder en geeft een link om het wachtwoord te kiezen
  planr.py mail      --db ... [--host mail.example.nl] [--poort 587] [--beveiliging starttls|ssl|geen]
                     [--gebruiker ...] [--wachtwoord-stdin] [--afzender-naam ...] [--afzender-adres ...]
  planr.py backup    --db ... --map /var/backups/plan-r [--bewaar 14]
  planr.py status    --db ...
  planr.py beheerders --db ...   (aantal beheerders; gebruikt door de installer)
"""
import argparse
import datetime
import os
import random
import sqlite3
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import ThreadingHTTPServer  # noqa: E402
from functools import partial  # noqa: E402

from planr_db import Database, instelling, maak_token, tijd_tekst, zet_instelling, geldig_email  # noqa: E402,F401


def serveer(args):
    from planr_api import App, maak_handler
    from planr_mail import Postbode
    from planr_meldingen import Melder
    from planr_push import Push

    db = Database(args.db)
    c = db.open()
    contact = instelling(c, "afzender_adres", "") or instelling(c, "smtp_gebruiker", "")
    c.close()
    postbode = Postbode(db, args.url)
    postbode.start()
    push = Push(db, "mailto:" + (contact or "planr@example.com"))
    melder = Melder(postbode, push)
    app = App(db, melder, push, postbode, args.url, args.statisch)
    handler = maak_handler(app)
    if args.statisch:
        handler = partial(handler, directory=os.path.abspath(args.statisch))

    def opruimen():
        while True:
            threading.Event().wait(6 * 3600)
            try:
                c = db.open()
                c.execute("DELETE FROM sessies WHERE verloopt < ?", (tijd_tekst(),))
                c.execute("DELETE FROM tokens WHERE verloopt < ?", (tijd_tekst(),))
                grens = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=120)).isoformat(timespec="seconds")
                c.execute("DELETE FROM meldingen WHERE gemaakt < ?", (grens,))
                c.commit()
                c.close()
            except Exception as e:  # noqa: BLE001
                print(f"[plan-r] opruimen: {e!r}", file=sys.stderr, flush=True)

    threading.Thread(target=opruimen, daemon=True).start()
    server = ThreadingHTTPServer((args.adres, args.poort), handler)
    server.daemon_threads = True
    print(f"[plan-r] luistert op http://{args.adres}:{args.poort} voor {args.url} (database: {args.db}, "
          f"push: {'aan' if push.actief else 'uit'})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def beheerder(args):
    email = args.email.strip().lower()
    if not geldig_email(email):
        sys.exit(f"'{args.email}' is geen geldig e-mailadres.")
    db = Database(args.db)
    c = db.open()
    g = c.execute("SELECT * FROM gebruikers WHERE email = ?", (email,)).fetchone()
    if g is None:
        cur = c.execute(
            "INSERT INTO gebruikers (email, naam, beheerder, status, toon, gemaakt) VALUES (?, ?, 1, 'uitgenodigd', ?, ?)",
            (email, (args.naam or "").strip()[:40], random.randint(0, 5), tijd_tekst()))
        gid = cur.lastrowid
        print(f"Beheerder {email} aangemaakt.")
    else:
        gid = g["id"]
        c.execute("UPDATE gebruikers SET beheerder = 1 WHERE id = ?", (gid,))
        if args.naam:
            c.execute("UPDATE gebruikers SET naam = ? WHERE id = ?", (args.naam.strip()[:40], gid))
        print(f"{email} is beheerder.")
    g = c.execute("SELECT * FROM gebruikers WHERE id = ?", (gid,)).fetchone()
    if g["status"] == "actief" and not args.nieuw_wachtwoord:
        c.commit()
        print("Er is al een wachtwoord. Wachtwoord vergeten? Gebruik --nieuw-wachtwoord voor een herstellink.")
        return
    soort = "herstel" if g["status"] == "actief" else "uitnodiging"
    token = maak_token(c, gid, soort, 7 * 86400)
    c.commit()
    pad = "herstel" if soort == "herstel" else "uitnodiging"
    print(f"Kies je wachtwoord via (7 dagen geldig):\n  {args.url.rstrip('/')}/{pad}/{token}")


def mail(args):
    db = Database(args.db)
    c = db.open()
    gezet = []
    for veld, sleutel in [("host", "smtp_host"), ("poort", "smtp_poort"), ("beveiliging", "smtp_beveiliging"),
                          ("gebruiker", "smtp_gebruiker"), ("afzender_naam", "afzender_naam"), ("afzender_adres", "afzender_adres")]:
        waarde = getattr(args, veld)
        if waarde is not None and (not args.alleen_leeg or not instelling(c, sleutel, "")):
            zet_instelling(c, sleutel, waarde)
            gezet.append(sleutel)
    if args.wachtwoord_stdin:
        wachtwoord = sys.stdin.readline().rstrip("\n")
        if wachtwoord and (not args.alleen_leeg or not instelling(c, "smtp_wachtwoord", "")):
            zet_instelling(c, "smtp_wachtwoord", wachtwoord)
            gezet.append("smtp_wachtwoord")
    c.commit()
    print("Mailinstellingen bijgewerkt: " + (", ".join(gezet) if gezet else "niets veranderd"))


def backup(args):
    os.makedirs(args.map, exist_ok=True)
    doel = os.path.join(args.map, f"planr-{datetime.date.today().isoformat()}.db")
    bron = sqlite3.connect(args.db)
    kopie = sqlite3.connect(doel)
    with kopie:
        bron.backup(kopie)
    kopie.close()
    bron.close()
    os.chmod(doel, 0o600)
    bestanden = sorted(f for f in os.listdir(args.map) if f.startswith("planr-") and f.endswith(".db"))
    for oud in bestanden[: -args.bewaar]:
        os.remove(os.path.join(args.map, oud))
    print(f"[plan-r] back-up gemaakt: {doel}")


def status(args):
    db = Database(args.db)
    c = db.open()
    print("Accounts:")
    for g in c.execute("SELECT email, naam, status, beheerder FROM gebruikers ORDER BY id"):
        extra = " (beheerder)" if g["beheerder"] else ""
        print(f"  {g['status']:<12} {g['email']:<36} {g['naam']}{extra}")
    print("Vieringen:")
    for v in c.execute("SELECT * FROM vieringen ORDER BY datum"):
        n = c.execute("SELECT COUNT(*) FROM deelnames WHERE viering_id = ?", (v["id"],)).fetchone()[0]
        lootjes = "getrokken" if v["lootjes_aan"] and v["lootjes_actief"] else ("aan" if v["lootjes_aan"] else "uit")
        print(f"  /{v['slug']:<24} {v['naam']} ({v['thema']}, {v['datum'] or 'geen datum'}, {n} deelnemers, "
              f"menu {'aan' if v['menu_aan'] else 'uit'}, lootjes {lootjes})")
    wacht = c.execute("SELECT COUNT(*) FROM mail_wachtrij WHERE status = 'wacht'").fetchone()[0]
    mislukt = c.execute("SELECT COUNT(*) FROM mail_wachtrij WHERE status = 'mislukt'").fetchone()[0]
    print(f"Mails in de wachtrij: {wacht}, mislukt: {mislukt}")


def beheerders(args):
    """Drukt het aantal beheerders af (de installer kijkt zo of er al een is)."""
    db = Database(args.db)
    c = db.open()
    print(c.execute("SELECT COUNT(*) FROM gebruikers WHERE beheerder = 1").fetchone()[0])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="opdracht", required=True)
    s = sub.add_parser("serveer")
    s.add_argument("--db", required=True)
    s.add_argument("--adres", default="127.0.0.1")
    s.add_argument("--poort", type=int, default=8810)
    s.add_argument("--url", required=True, help="publiek adres, bijv. https://kerst.rudymedia.nl")
    s.add_argument("--statisch", default=None, help="map met de webbestanden (alleen voor lokaal testen)")
    b = sub.add_parser("beheerder")
    b.add_argument("--db", required=True)
    b.add_argument("--email", required=True)
    b.add_argument("--naam", default="")
    b.add_argument("--url", required=True)
    b.add_argument("--nieuw-wachtwoord", action="store_true", help="ook een herstellink maken als er al een wachtwoord is")
    m = sub.add_parser("mail")
    m.add_argument("--db", required=True)
    m.add_argument("--host")
    m.add_argument("--poort")
    m.add_argument("--beveiliging", choices=["starttls", "ssl", "geen"])
    m.add_argument("--gebruiker")
    m.add_argument("--wachtwoord-stdin", action="store_true")
    m.add_argument("--afzender-naam", dest="afzender_naam")
    m.add_argument("--afzender-adres", dest="afzender_adres")
    m.add_argument("--alleen-leeg", action="store_true", help="alleen instellen wat nog leeg is")
    k = sub.add_parser("backup")
    k.add_argument("--db", required=True)
    k.add_argument("--map", required=True)
    k.add_argument("--bewaar", type=int, default=14)
    t = sub.add_parser("status")
    t.add_argument("--db", required=True)
    h = sub.add_parser("beheerders")
    h.add_argument("--db", required=True)
    args = p.parse_args()
    {"serveer": serveer, "beheerder": beheerder, "mail": mail, "backup": backup, "status": status,
     "beheerders": beheerders}[args.opdracht](args)


if __name__ == "__main__":
    main()
