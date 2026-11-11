#!/usr/bin/env python3
"""Maakt een demo-database met een paar vieringen, mensen, gerechten, wensen en berichten.

  python3 tests/demo.py /tmp/demo.db
  python3 server/planr.py serveer --db /tmp/demo.db --poort 8099 --url http://localhost:8099 --statisch web

Inloggen kan met rudy@example.nl (beheerder) of anna@example.nl, wachtwoord: demo-wachtwoord
"""
import datetime
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "server"))
from planr_db import Database, hash_wachtwoord, tijd_tekst  # noqa: E402

pad = sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo.db"
for extra in ("", "-wal", "-shm"):
    if os.path.exists(pad + extra):
        os.remove(pad + extra)
db = Database(pad)
c = db.open()
ww = hash_wachtwoord("demo-wachtwoord")
nu = tijd_tekst()

mensen = [("rudy@example.nl", "Rudy", 1, 0), ("anna@example.nl", "Anna", 0, 1), ("bert@example.nl", "Bert", 0, 2),
          ("cees@example.nl", "Cees", 0, 3), ("dewi@example.nl", "Dewi", 0, 4), ("eva@example.nl", "Eva de Vries", 0, 5)]
ids = {}
for email, naam, beheerder, toon in mensen:
    cur = c.execute("INSERT INTO gebruikers (email, naam, wachtwoord, beheerder, status, toon, actief_sinds, laatst_gezien, gemaakt) "
                    "VALUES (?, ?, ?, ?, 'actief', ?, ?, ?, ?)", (email, naam, ww, beheerder, toon, nu, nu, nu))
    ids[naam.split()[0].lower()] = cur.lastrowid
cur = c.execute("INSERT INTO gebruikers (email, naam, status, toon, gemaakt) VALUES ('fien@example.nl', '', 'uitgenodigd', 2, ?)", (nu,))
ids["fien"] = cur.lastrowid

kerst = datetime.date.today().replace(month=12, day=25)
if kerst < datetime.date.today():
    kerst = kerst.replace(year=kerst.year + 1)
sint = kerst.replace(day=5)
vieringen = [
    ("familie", "Kerst met de familie", "kerst", kerst.isoformat(), "17:00", "Dorpsstraat 1, Utrecht",
     "Neem je foutste kersttrui mee! We beginnen met een borrel.", "€ 25", "", "", "Inpakken in kerstpapier\nGeen cadeaubonnen", 1, 1),
    ("vrienden", "Sinterklaas met vrienden", "sinterklaas", sint.isoformat(), "19:30", "Bij Dewi thuis",
     "", "€ 15", "wel", "mag", "Gedicht van minstens 8 regels", 0, 1),
    ("bbq", "Zomer-BBQ", "zomer", f"{kerst.year + 1}-07-12", "16:00", "Strandpaviljoen Zuid", "", "", "", "", "", 1, 0),
    ("griezel", "Halloween-feest", "halloween", f"{kerst.year + 1}-10-31", "20:00", "De oude schuur", "Verkleden is verplicht!", "", "", "", "", 1, 0),
]
vid = {}
for slug, naam, thema, datum, tijd, locatie, welkomst, budget, gedicht, surprise, regels, menu, lootjes in vieringen:
    cur = c.execute("INSERT INTO vieringen (slug, naam, thema, datum, tijd, locatie, welkomst, budget, gedicht, surprise, regels, menu_aan, lootjes_aan, gemaakt) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (slug, naam, thema, datum, tijd, locatie, welkomst, budget, gedicht, surprise, regels, menu, lootjes, nu))
    vid[slug] = cur.lastrowid


def lid(slug, wie, status="actief"):
    c.execute("INSERT INTO deelnames (viering_id, gebruiker_id, status, actief_sinds, uitgenodigd_op, gemaakt) VALUES (?, ?, ?, ?, ?, ?)",
              (vid[slug], ids[wie], status, nu if status == "actief" else None, nu, nu))


for w in ("rudy", "anna", "bert", "cees", "eva"):
    lid("familie", w)
lid("familie", "fien", "uitgenodigd")
for w in ("rudy", "anna", "dewi", "cees"):
    lid("vrienden", w)
for w in ("rudy", "bert", "dewi"):
    lid("bbq", w)
lid("griezel", "rudy")
lid("griezel", "anna", "uitgenodigd")

f = vid["familie"]
for wie, gang, naam, toel in [("anna", "nagerecht", "Tiramisu", "voor 10 personen"), ("bert", "hoofdgerecht", "Rollade met jus", ""),
                              ("cees", "voorgerecht", "Carpaccio", "met pijnboompitten"), ("eva", "bijgerecht", "Stoofpeertjes", ""),
                              ("rudy", "hapjes", "Bitterballen", "vega en gewoon"), ("anna", "soep", "Tomatensoep", "")]:
    c.execute("INSERT INTO gerechten (viering_id, gebruiker_id, gang, naam, toelichting, gemaakt, bijgewerkt) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (f, ids[wie], gang, naam, toel, nu, nu))
for wie, tekst, ook in [("cees", "Glühwein", ["anna", "rudy"]), ("eva", "Alcoholvrije bubbels", []), ("bert", "Speciaalbier", ["cees"])]:
    cur = c.execute("INSERT INTO drankjes (viering_id, gebruiker_id, tekst, gemaakt) VALUES (?, ?, ?, ?)", (f, ids[wie], tekst, nu))
    for x in [wie] + ook:
        c.execute("INSERT INTO drank_stemmen (drank_id, gebruiker_id) VALUES (?, ?)", (cur.lastrowid, ids[x]))
for wie, items in {"anna": [("Een goed boek", "Iets van Herman Koch of Esther Gerritsen", "https://www.bol.com", "€ 22"),
                            ("Warme sokken", "Maat 38-40, graag gekleurd", "", "€ 10"), ("Lekkere thee", "", "", "")],
                   "rudy": [("Bordspel", "Iets voor 2 tot 4 spelers", "https://www.example.com/spel", "€ 25")],
                   "bert": [("Puzzel", "1000 stukjes", "", "€ 15")]}.items():
    for i, (titel, toel, link, prijs) in enumerate(items):
        c.execute("INSERT INTO wensen (viering_id, gebruiker_id, titel, toelichting, link, prijs, volgorde, gemaakt, bijgewerkt) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                  (f, ids[wie], titel, toel, link, prijs, i + 1, nu, nu))
# Lootjes familie getrokken: rudy -> anna -> bert -> cees -> eva -> rudy
paren = [("rudy", "anna"), ("anna", "bert"), ("bert", "cees"), ("cees", "eva"), ("eva", "rudy")]
for g, o in paren:
    c.execute("INSERT INTO lootjes (viering_id, ronde, gever_id, ontvanger_id, geopend) VALUES (?, 1, ?, ?, ?)",
              (f, ids[g], ids[o], nu if g != "rudy" else None))
c.execute("UPDATE vieringen SET lootjes_actief = 1, lootjes_ronde = 1, lootjes_getrokken_op = ? WHERE id = ?", (nu, f))
for gever, ontv, van_gever, tekst in [("eva", "rudy", 1, "Hoi Rudy! Wat voor bordspel vind je leuk? Coöperatief of juist tegen elkaar?"),
                                      ("eva", "rudy", 0, "Coöperatief graag! Pandemic vond ik super."),
                                      ("anna", "bert", 1, "Hey Bert, hoeveel stukjes mag de puzzel hebben?")]:
    c.execute("INSERT INTO berichten (viering_id, ronde, gever_id, ontvanger_id, van_gever, tekst, gemaakt) VALUES (?, 1, ?, ?, ?, ?, ?)",
              (f, ids[gever], ids[ontv], van_gever, tekst, nu))
c.execute("INSERT INTO meldingen (gebruiker_id, viering_id, soort, titel, tekst, link, gemaakt) VALUES (?, ?, 'menu', 'Nieuws over het menu', ?, '/familie/menu', ?)",
          (ids["rudy"], f, "Anna neemt Tiramisu mee (nagerecht)\nCees drinkt graag Glühwein", nu))
c.execute("INSERT INTO meldingen (gebruiker_id, viering_id, soort, titel, tekst, link, gemaakt) VALUES (?, ?, 'lootje', 'De lootjes zijn getrokken! 🎁', 'Open de app en ontdek wie jij hebt getrokken.', '/familie/lootje', ?)",
          (ids["rudy"], f, nu))
c.commit()
print(f"Demo-database klaar: {pad}")
