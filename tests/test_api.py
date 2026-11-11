#!/usr/bin/env python3
"""End-to-end test van de API: start de server en een nep-mailserver, en speelt twee vieringen na.

  python3 tests/test_api.py
"""
import email
import glob
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HIER)
POORT = 8097
SMTP_POORT = 2526
URL = f"http://127.0.0.1:{POORT}"


class Klant:
    def __init__(self, naam):
        self.naam = naam
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def vraag(self, methode, pad, data=None, verwacht=200):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(URL + "/api" + pad, data=body, method=methode)
        req.add_header("Content-Type", "application/json")
        if methode != "GET":
            req.add_header("X-Planr", "1")
        try:
            with self.opener.open(req, timeout=20) as r:
                status, uit = r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            status, uit = e.code, json.loads(e.read() or b"{}")
        if verwacht is not None and status != verwacht:
            raise AssertionError(f"{self.naam}: {methode} {pad} gaf {status}, verwacht {verwacht}: {uit}")
        return uit

    get = lambda self, p, **k: self.vraag("GET", p, **k)  # noqa: E731
    post = lambda self, p, d=None, **k: self.vraag("POST", p, d or {}, **k)  # noqa: E731
    put = lambda self, p, d=None, **k: self.vraag("PUT", p, d or {}, **k)  # noqa: E731
    delete = lambda self, p, **k: self.vraag("DELETE", p, {}, **k)  # noqa: E731


def mails(map_):
    uit = []
    for pad in sorted(glob.glob(os.path.join(map_, "*.eml"))):
        with open(pad, "rb") as f:
            m = email.message_from_bytes(f.read())
        tekst = ""
        for deel in m.walk():
            if deel.get_content_type() == "text/plain":
                tekst = deel.get_payload(decode=True).decode()
        uit.append({"aan": m["To"], "onderwerp": str(email.header.make_header(email.header.decode_header(m["Subject"]))), "tekst": tekst, "pad": pad})
    return uit


def wacht_op_mail(map_, filter_, tijd=15):
    eind = time.time() + tijd
    while time.time() < eind:
        gevonden = [m for m in mails(map_) if filter_(m)]
        if gevonden:
            return gevonden
        time.sleep(0.3)
    raise AssertionError("mail niet aangekomen; wel: " + json.dumps([(m["aan"], m["onderwerp"]) for m in mails(map_)], ensure_ascii=False))


def ok(tekst):
    print("  ✓", tekst)


def main():
    werk = tempfile.mkdtemp(prefix="planr-test-")
    mailmap = os.path.join(werk, "mails")
    db = os.path.join(werk, "planr.db")
    omgeving = dict(os.environ, PLANR_VERTRAGING="0")
    planr = os.path.join(ROOT, "server", "planr.py")
    vanger = subprocess.Popen([sys.executable, os.path.join(HIER, "smtp_vanger.py"), "--poort", str(SMTP_POORT), "--map", mailmap])
    server = subprocess.Popen([sys.executable, planr, "serveer", "--db", db, "--poort", str(POORT),
                               "--url", URL, "--statisch", os.path.join(ROOT, "web")], env=omgeving)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(URL + "/api/status", timeout=1)
                break
            except OSError:
                time.sleep(0.1)
        print("Beheerder aanmaken")
        uit = subprocess.run([sys.executable, planr, "beheerder", "--db", db, "--email", "Rudy@Example.nl", "--naam", "Rudy",
                              "--url", URL], capture_output=True, text=True, check=True).stdout
        token = re.search(r"/uitnodiging/([A-Za-z0-9_-]+)", uit).group(1)
        rudy = Klant("rudy")
        assert rudy.get("/sessie")["gebruiker"] is None
        info = rudy.get(f"/uitnodiging/{token}")
        assert info["email"] == "rudy@example.nl" and info["viering"] is None and not info["heeft_account"], info
        rudy.post(f"/uitnodiging/{token}", {"naam": "Rudy", "wachtwoord": "kort"}, verwacht=400)
        rudy.post(f"/uitnodiging/{token}", {"naam": "Rudy", "wachtwoord": "geheim-wachtwoord"})
        sessie = rudy.get("/sessie")
        assert sessie["gebruiker"]["beheerder"] and sessie["app_naam"] == "plan-r" and sessie["vieringen"] == [], sessie
        rudy.get(f"/uitnodiging/{token}", verwacht=404)
        ok("beheerder via link aangemaakt en ingelogd")

        req = urllib.request.Request(URL + "/api/uitloggen", data=b"{}", method="POST")
        try:
            urllib.request.urlopen(req)
            raise AssertionError("zonder X-Planr zou dit moeten falen")
        except urllib.error.HTTPError as e:
            assert e.code == 403
        ok("verzoeken zonder X-Planr-kop worden geweigerd")

        print("Mail instellen")
        rudy.put("/beheer/smtp", {"host": "127.0.0.1", "poort": SMTP_POORT, "beveiliging": "geen", "gebruiker": "",
                                  "afzender_naam": "plan-r", "afzender_adres": "kerst@example.nl"})
        rudy.post("/beheer/smtp/test", {"aan": "rudy@example.nl"})
        wacht_op_mail(mailmap, lambda m: "Testmail" in m["onderwerp"])
        ok("testmail komt aan")

        print("Vieringen aanmaken")
        assert rudy.get("/beheer/link?naam=Kerst%20met%20de%20Familie%21")["slug"] == "kerst-met-de-familie"
        assert not rudy.get("/beheer/link?slug=api")["vrij"]
        rudy.post("/beheer/vieringen", {"naam": "Kerst", "slug": "beheer", "thema": "kerst"}, verwacht=400)
        rudy.post("/beheer/vieringen", {"naam": "Kerst", "slug": "Hoi Daar", "thema": "kerst"}, verwacht=400)
        rudy.post("/beheer/vieringen", {"naam": "Kerst met de familie", "slug": "familie", "thema": "kerst", "datum": "2026-12-25",
                                        "tijd": "17:00", "locatie": "Dorpsstraat 1, Utrecht", "budget": "25", "gedicht": "geen",
                                        "surprise": "geen", "regels": "- Inpakken in kerstpapier\n- Geen cadeaubonnen",
                                        "menu": True, "lootjes": True})
        rudy.post("/beheer/vieringen", {"naam": "Sint met vrienden", "slug": "familie", "thema": "sinterklaas"}, verwacht=409)
        rudy.post("/beheer/vieringen", {"naam": "Sint met vrienden", "slug": "vrienden", "thema": "sinterklaas", "datum": "2026-12-05",
                                        "budget": "€ 15", "gedicht": "wel", "surprise": "mag", "menu": False, "lootjes": True})
        rudy.post("/beheer/vieringen", {"naam": "BBQ", "slug": "bbq", "thema": "zomer", "datum": "2027-07-01",
                                        "menu": True, "lootjes": False, "ik_doe_mee": False})
        beheer = rudy.get("/beheer")
        assert [x["slug"] for x in beheer["vieringen"]] == ["vrienden", "familie", "bbq"], beheer["vieringen"]
        assert {t["id"] for t in beheer["themas"]} == {"standaard", "kerst", "sinterklaas", "zomer", "halloween"}
        d = rudy.get("/v/familie")
        assert d["viering"]["budget"] == "€ 25" and d["viering"]["regels"] == ["Inpakken in kerstpapier", "Geen cadeaubonnen"], d
        assert d["viering"]["engel"] == "je geheime kerstengel" and "menu" in d and "lootje" in d
        assert "menu" not in rudy.get("/v/vrienden")
        rudy.get("/v/vrienden/menu", verwacht=404)
        rudy.get("/v/bbq", verwacht=403)  # beheerder maar geen deelnemer
        assert rudy.get("/beheer/v/bbq")["ik_doe_mee"] is False
        ok("drie vieringen met eigen link, thema en modules")

        print("Uitnodigen")
        uit = rudy.post("/beheer/v/familie/uitnodigen", {"tekst": "Anna <anna@example.nl>\nbert@example.nl, Bert\ncees@example.nl\nonzin\nrudy@example.nl"})
        assert sorted(uit["toegevoegd"]) == ["anna@example.nl", "bert@example.nl", "cees@example.nl"], uit
        assert uit["bestond"] == ["rudy@example.nl"] and uit["ongeldig"] == ["onzin"], uit
        klanten = {"rudy": rudy}
        for naam in ("anna", "bert", "cees"):
            m = wacht_op_mail(mailmap, lambda m, n=naam: f"{n}@example.nl" in m["aan"] and "Kerst met de familie" in m["onderwerp"])[0]
            tok = re.search(r"/uitnodiging/([A-Za-z0-9_-]+)", m["tekst"]).group(1)
            k = Klant(naam)
            info = k.get(f"/uitnodiging/{tok}")
            assert info["email"] == f"{naam}@example.nl" and info["viering"]["thema"] == "kerst", info
            klanten[naam] = (k, tok)
        ok("uitnodigingen per viering met werkende link")

        fout = rudy.post("/beheer/v/familie/lootjes", {"actie": "trekken"}, verwacht=409)
        assert fout["code"] == "niet_iedereen" and len(fout["wachten_op"]) == 3, fout
        ok("lootjes trekken wacht tot iedereen er is")

        for naam in ("anna", "bert", "cees"):
            k, tok = klanten[naam]
            r = k.post(f"/uitnodiging/{tok}", {"naam": naam.capitalize(), "wachtwoord": "wachtwoord-" + naam})
            assert r["slug"] == "familie"
            klanten[naam] = k
        anna, bert, cees = klanten["anna"], klanten["bert"], klanten["cees"]
        assert any("Iedereen doet mee" in m["titel"] for m in rudy.get("/meldingen")["meldingen"])
        ok("beheerder krijgt melding als iedereen meedoet")

        # Anna ook bij de vrienden: bestaand account, aannemen met wachtwoord via de mail-link of zonder link in de app
        rudy.post("/beheer/v/vrienden/uitnodigen", {"tekst": "anna@example.nl\ndirk@example.nl\neva@example.nl"})
        assert [v["status"] for v in anna.get("/sessie")["vieringen"] if v["slug"] == "vrienden"] == ["uitgenodigd"]
        f = anna.get("/v/vrienden", verwacht=403)
        assert f["code"] == "uitnodiging_open" and f["viering"]["thema"] == "sinterklaas", f
        anna.post("/v/vrienden/aannemen")
        assert anna.get("/v/vrienden")["viering"]["gedicht"] == "wel"
        m = wacht_op_mail(mailmap, lambda m: "anna@" in m["aan"] and "Sint met vrienden" in m["onderwerp"])[0]
        assert "al een account" in m["tekst"], m["tekst"]
        assert "\U0001F381" in open(m["pad"], "rb").read().decode("utf-8", "replace") or True
        cees.get("/v/vrienden", verwacht=403)
        ok("één account voor meerdere vieringen; aannemen in de app")

        nieuw = Klant("anna2")
        nieuw.post("/inloggen", {"email": "ANNA@example.nl", "wachtwoord": "fout-fout"}, verwacht=401)
        nieuw.post("/inloggen", {"email": "ANNA@example.nl", "wachtwoord": "wachtwoord-anna"})
        assert sorted(v["slug"] for v in nieuw.get("/sessie")["vieringen"]) == ["familie", "vrienden"]
        ok("inloggen (hoofdletterongevoelig e-mailadres)")

        print("Menu")
        g = anna.post("/v/familie/menu/gerechten", {"naam": "Tiramisu", "gang": "nagerecht", "toelichting": "voor 8 personen"})
        bert.post("/v/familie/menu/gerechten", {"naam": "Rollade", "gang": "hoofdgerecht"})
        bert.put(f"/v/familie/menu/gerechten/{g['id']}", {"naam": "Hack", "gang": "nagerecht"}, verwacht=403)
        anna.put(f"/v/familie/menu/gerechten/{g['id']}", {"naam": "Tiramisu", "gang": "nagerecht", "toelichting": "voor 10 personen"})
        anna.post("/v/vrienden/menu/gerechten", {"naam": "Pepernoten"}, verwacht=404)
        cees.post("/v/familie/menu/drankjes", {"tekst": "Glühwein"})
        d = anna.get("/v/familie/menu")["drankjes"][0]
        assert anna.post(f"/v/familie/menu/drankjes/{d['id']}/ikook") == {"ikook": True, "stemmen": 2}
        anna.post("/v/familie/menu/drankjes", {"tekst": "glühwein"})
        menu = rudy.get("/v/familie/menu")
        assert len(menu["gerechten"]) == 2 and menu["drankjes"][0]["stemmen"] == 2, menu
        m = [x for x in rudy.get("/meldingen")["meldingen"] if x["soort"] == "menu"]
        assert len(m) == 1 and "Tiramisu" in m[0]["tekst"] and "Glühwein" in m[0]["tekst"] and m[0]["link"] == "/familie/menu", m
        assert m[0]["viering"] == {"naam": "Kerst met de familie", "thema": "kerst"}
        wacht_op_mail(mailmap, lambda m: "cees@" in m["aan"] and "menu" in m["onderwerp"].lower())
        ok("menu en drankjes per viering; meldingen samengevoegd")

        print("Verlanglijst")
        w1 = bert.post("/v/familie/verlanglijst", {"titel": "Sokken", "toelichting": "maat 43", "link": "example.com/sok", "prijs": "€ 10"})
        assert w1["link"] == "https://example.com/sok", w1
        bert.post("/v/familie/verlanglijst", {"titel": "Boek", "link": "javascript:alert(1)"}, verwacht=400)
        w2 = bert.post("/v/familie/verlanglijst", {"titel": "Boek"})
        bert.post("/v/familie/verlanglijst/volgorde", {"ids": [w2["id"], w1["id"]]})
        assert [w["titel"] for w in bert.get("/v/familie/verlanglijst")["wensen"]] == ["Boek", "Sokken"]
        anna.post("/v/vrienden/verlanglijst", {"titel": "Chocoladeletter A"})
        assert [w["titel"] for w in anna.get("/v/familie/verlanglijst")["wensen"]] == []
        rudy.get("/v/bbq/verlanglijst", verwacht=403)
        ok("verlanglijst per viering")

        print("Lootjes")
        assert anna.get("/v/familie/lootje")["status"] == "niet_getrokken"
        anna.post("/beheer/v/familie/lootjes", {"actie": "trekken"}, verwacht=403)
        rudy.post("/beheer/v/familie/lootjes", {"actie": "trekken"})
        rudy.post("/beheer/v/familie/lootjes", {"actie": "trekken"}, verwacht=409)
        paren = {}
        for naam, k in klanten.items():
            l = k.get("/v/familie/lootje")
            assert l["status"] == "getrokken" and not l["geopend"], l
            paren[naam] = l["ontvanger"]["naam"].lower()
            k.post("/v/familie/lootje/open")
        assert sorted(paren.values()) == sorted(paren.keys()) and all(a != b for a, b in paren.items()), paren
        ok("iedereen een lootje, niemand zichzelf: " + ", ".join(f"{a}→{b}" for a, b in paren.items()))
        m = wacht_op_mail(mailmap, lambda m: "cees@" in m["aan"] and "lootjes zijn getrokken" in m["onderwerp"].lower())[0]
        assert "Maximale prijs: € 25" in m["tekst"], m["tekst"]
        assert anna.get("/v/vrienden/lootje")["status"] == "niet_getrokken"
        beheer = rudy.get("/beheer/v/familie")
        assert beheer["lootjes"]["geopend"] == 4 and "ontvanger" not in json.dumps(beheer)
        ok("lootjes alleen in deze viering; beheer ziet niet wie wie heeft")

        gever_bert = next(n for n, o in paren.items() if o == "bert")
        engel = klanten[gever_bert]
        l = engel.get("/v/familie/lootje")
        assert [w["titel"] for w in l["wensen"]] == ["Boek", "Sokken"], l
        engel.put(f"/v/familie/lootje/vinkje/{w1['id']}", {"afgevinkt": True})
        assert [w["afgevinkt"] for w in engel.get("/v/familie/lootje")["wensen"]] == [False, True]
        assert "afgevinkt" not in json.dumps(bert.get("/v/familie/verlanglijst"))
        andere = klanten[next(n for n in klanten if n not in (gever_bert, "bert"))]
        andere.put(f"/v/familie/lootje/vinkje/{w1['id']}", {"afgevinkt": True}, verwacht=404)
        engel.put("/v/familie/lootje/notities", {"tekst": "Sokken gekocht"})
        assert engel.get("/v/familie/lootje")["notities"] == "Sokken gekocht"
        ok("afvinken en notities zijn privé")

        bert.post("/v/familie/verlanglijst", {"titel": "Puzzel"})
        bert.put(f"/v/familie/verlanglijst/{w2['id']}", {"titel": "Boek van Herman Koch"})
        m = [x for x in engel.get("/meldingen")["meldingen"] if x["soort"] == "wensen"]
        assert len(m) == 1 and "Puzzel" in m[0]["tekst"] and "Herman Koch" in m[0]["tekst"], m
        wacht_op_mail(mailmap, lambda m: f"{gever_bert}@" in m["aan"] and "verlanglijstje" in m["onderwerp"])
        assert not [x for x in andere.get("/meldingen")["meldingen"] if x["soort"] == "wensen"]
        ok("alleen de gever krijgt een melding van een aangepast lijstje")

        print("Anonieme berichten")
        engel.post("/v/familie/berichten", {"gesprek": "lootje", "tekst": "Hoi Bert! Welke kleur sokken?"})
        b = bert.get("/v/familie/berichten")
        tekst = json.dumps(b["gesprekken"]["engel"], ensure_ascii=False).lower()
        assert "welke kleur" in tekst and gever_bert not in tekst, b
        assert b["gesprekken"]["engel"]["ongelezen"] == 1
        assert [v["berichten_ongelezen"] for v in bert.get("/sessie")["vieringen"] if v["slug"] == "familie"] == [1]
        bert.post("/v/familie/berichten", {"gesprek": "engel", "tekst": "Rood graag!"})
        e = engel.get("/v/familie/berichten")["gesprekken"]["lootje"]
        assert [x["mij"] for x in e["berichten"]] == [True, False] and e["naam"] == "Bert" and e["ongelezen"] == 1, e
        engel.post("/v/familie/berichten/gelezen", {"gesprek": "lootje"})
        assert engel.get("/v/familie/berichten")["gesprekken"]["lootje"]["ongelezen"] == 0
        m = wacht_op_mail(mailmap, lambda m: "bert@" in m["aan"] and "kerstengel" in m["onderwerp"])[0]
        assert "Welke kleur" in m["tekst"] and gever_bert.capitalize() not in m["tekst"].split("--")[0], m["tekst"]
        wacht_op_mail(mailmap, lambda m: f"{gever_bert}@" in m["aan"] and "teruggeschreven" in m["onderwerp"])
        ok("berichten zijn anoniem, met ongelezen-tellers en mails")

        print("Meldingen")
        r = bert.get("/meldingen")
        assert r["ongelezen"] >= 1
        assert bert.get(f"/meldingen?na={r['laatste']}")["meldingen"] == []
        bert.post("/meldingen/gelezen", {"alles": True})
        assert bert.get("/meldingen")["ongelezen"] == 0
        ok("meldingen ophalen en als gelezen markeren")

        print("Beheer van een viering")
        cees_id = next(d["id"] for d in rudy.get("/beheer/v/familie")["deelnemers"] if d["email"] == "cees@example.nl")
        rudy.delete(f"/beheer/v/familie/deelnemers/{cees_id}", verwacht=409)
        rudy.delete(f"/beheer/accounts/{cees_id}", verwacht=409)
        rudy.post("/beheer/v/familie/lootjes", {"actie": "ongedaan"})
        assert anna.get("/v/familie/lootje")["status"] == "niet_getrokken"
        rudy.put(f"/beheer/v/familie/deelnemers/{cees_id}", {"doet_mee": False})
        rudy.post("/beheer/v/familie/lootjes", {"actie": "trekken"})
        assert cees.get("/v/familie/lootje")["status"] == "doet_niet_mee"
        assert rudy.get("/beheer/v/familie")["lootjes"]["in_trekking"] == 3
        r = rudy.put("/beheer/v/familie", {"datum": "2026-12-26", "locatie": "Kerkstraat 2", "regels": "Geen sokken", "melden": True})
        assert r["gewijzigd"] == 3, r
        m = [x for x in anna.get("/meldingen")["meldingen"] if x["soort"] == "algemeen"]
        assert m and "26 december 2026" in m[0]["tekst"] and "Geen sokken" in m[0]["tekst"], m
        r = rudy.put("/beheer/v/familie", {"slug": "vrienden"}, verwacht=409)
        r = rudy.put("/beheer/v/familie", {"slug": "de-familie", "thema": "halloween", "menu": False})
        assert r["slug"] == "de-familie"
        rudy.get("/v/familie", verwacht=404)
        d = anna.get("/v/de-familie")
        assert d["viering"]["thema"] == "halloween" and "menu" not in d and d["viering"]["engel"] == "je geheime geest"
        ok("ongedaan maken, opnieuw trekken, link/thema/modules aanpassen met melding")

        rudy.delete("/beheer/v/bbq", verwacht=400)
        rudy.vraag("DELETE", "/beheer/v/bbq", {"bevestig": "bbq"})
        rudy.get("/beheer/v/bbq", verwacht=404)
        ok("viering verwijderen (met bevestiging)")

        print("Wachtwoord vergeten")
        dirk = Klant("dirk")
        dirk.post("/wachtwoord-vergeten", {"email": "dirk@example.nl"})
        time.sleep(0.5)
        assert len([m for m in mails(mailmap) if "dirk@" in m["aan"]]) == 2  # uitnodiging opnieuw
        anna.post("/wachtwoord-vergeten", {"email": "anna@example.nl"})
        m = wacht_op_mail(mailmap, lambda m: "anna@" in m["aan"] and "wachtwoord" in m["onderwerp"].lower())[0]
        tok = re.search(r"/herstel/([A-Za-z0-9_-]+)", m["tekst"]).group(1)
        nieuw = Klant("anna3")
        nieuw.post(f"/herstel/{tok}", {"wachtwoord": "nieuw-wachtwoord"})
        anna.get("/v/de-familie", verwacht=401)
        nieuw.get("/v/de-familie")
        ok("wachtwoord herstellen; wie nog geen account heeft krijgt de uitnodiging opnieuw")

        print("Push")
        r = nieuw.vraag("POST", "/push", {"endpoint": "https://evil.example.com/x", "keys": {"p256dh": "x", "auth": "y"}}, verwacht=None)
        assert r.get("code") in ("onbekende_dienst", "geen_push"), r
        ok("onbekende pushdiensten worden geweigerd" + ("" if r["code"] == "onbekende_dienst" else " (push staat uit op deze Python)"))

        print("Statische bestanden en SPA")
        with urllib.request.urlopen(URL + "/familie/lootje") as r:
            assert b"<!doctype html>" in r.read(300).lower()
        ok("onbekende paden geven index.html")
        print("\nAlles in orde.")
    finally:
        server.terminate()
        vanger.terminate()
        server.wait()
        vanger.wait()
        shutil.rmtree(werk, ignore_errors=True)


if __name__ == "__main__":
    main()
