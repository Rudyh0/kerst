"""Pushmeldingen (Web Push met VAPID, RFC 8291 + RFC 8292).

Hiervoor is het pakket python3-cryptography nodig (de installer zet het neer).
Zonder dat pakket werkt de rest van de app gewoon; alleen pushmeldingen staan dan uit.
"""
import base64
import hashlib
import hmac
import json
import os
import queue
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from planr_db import instelling, tijd_tekst, zet_instelling

try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    BESCHIKBAAR = True
except BaseException as e:  # noqa: BLE001  ook een kapotte installatie (PanicException) mag de app niet stoppen
    if isinstance(e, (KeyboardInterrupt, SystemExit)):
        raise
    BESCHIKBAAR = False

# Alleen naar de bekende pushdiensten van browsers sturen (geen willekeurige adressen).
TOEGESTANE_DIENSTEN = (
    "fcm.googleapis.com",
    "android.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
    "push.apple.com",
)


def b64u(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def b64u_terug(tekst):
    tekst = tekst.strip()
    return base64.urlsafe_b64decode(tekst + "=" * (-len(tekst) % 4))


def _hmac(sleutel, data):
    return hmac.new(sleutel, data, hashlib.sha256).digest()


def endpoint_toegestaan(endpoint):
    try:
        delen = urlsplit(endpoint)
    except ValueError:
        return False
    host = (delen.hostname or "").lower()
    if delen.scheme != "https" or not host or len(endpoint) > 1000:
        return False
    return any(host == d or host.endswith("." + d) for d in TOEGESTANE_DIENSTEN)


def versleutel(p256dh, auth, inhoud, zout=None, server_sleutel=None):
    """Versleutelt een bericht volgens RFC 8291 (aes128gcm). Geeft de complete body terug."""
    ua_publiek = b64u_terug(p256dh) if isinstance(p256dh, str) else p256dh
    auth_geheim = b64u_terug(auth) if isinstance(auth, str) else auth
    if len(ua_publiek) != 65 or len(auth_geheim) < 16:
        raise ValueError("ongeldige sleutels")
    ua_sleutel = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), ua_publiek)
    as_prive = server_sleutel or ec.generate_private_key(ec.SECP256R1())
    as_publiek = as_prive.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    gedeeld = as_prive.exchange(ec.ECDH(), ua_sleutel)
    zout = zout or os.urandom(16)

    prk_sleutel = _hmac(auth_geheim, gedeeld)
    ikm = _hmac(prk_sleutel, b"WebPush: info\x00" + ua_publiek + as_publiek + b"\x01")
    prk = _hmac(zout, ikm)
    cek = _hmac(prk, b"Content-Encoding: aes128gcm\x00\x01")[:16]
    nonce = _hmac(prk, b"Content-Encoding: nonce\x00\x01")[:12]

    record = 4096
    if len(inhoud) + 1 + 16 > record:
        raise ValueError("bericht te groot")
    versleuteld = AESGCM(cek).encrypt(nonce, inhoud + b"\x02", None)
    kop = zout + struct.pack("!I", record) + bytes([len(as_publiek)]) + as_publiek
    return kop + versleuteld


class Push:
    def __init__(self, db, contact):
        self.db = db
        self.contact = contact
        self.actief = BESCHIKBAAR
        self.publiek = ""
        self.rij = queue.Queue(maxsize=2000)
        if not self.actief:
            print("[plan-r] python3-cryptography ontbreekt of werkt niet: pushmeldingen staan uit.", file=sys.stderr, flush=True)
            return
        c = db.open()
        try:
            pem = instelling(c, "vapid_prive", "")
            if pem:
                self.sleutel = serialization.load_pem_private_key(pem.encode(), password=None)
            else:
                self.sleutel = ec.generate_private_key(ec.SECP256R1())
                pem = self.sleutel.private_bytes(
                    serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
                ).decode()
                zet_instelling(c, "vapid_prive", pem)
                c.commit()
            self.publiek = b64u(self.sleutel.public_key().public_bytes(
                serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        except Exception as e:  # noqa: BLE001
            print(f"[plan-r] pushsleutel maken mislukt ({e!r}): pushmeldingen staan uit.", file=sys.stderr, flush=True)
            self.actief = False
            return
        finally:
            c.close()
        threading.Thread(target=self.werk, daemon=True, name="push").start()

    # ------------------------------------------------------------------ versturen

    def vapid(self, endpoint):
        delen = urlsplit(endpoint)
        publiek = f"{delen.scheme}://{delen.netloc}"
        kop = b64u(json.dumps({"typ": "JWT", "alg": "ES256"}, separators=(",", ":")).encode())
        claims = b64u(json.dumps(
            {"aud": publiek, "exp": int(time.time()) + 12 * 3600, "sub": self.contact},
            separators=(",", ":")).encode())
        ondertekenen = f"{kop}.{claims}".encode()
        der = self.sleutel.sign(ondertekenen, ec.ECDSA(hashes.SHA256()))
        r, s = decode_dss_signature(der)
        handtekening = b64u(r.to_bytes(32, "big") + s.to_bytes(32, "big"))
        return f"vapid t={kop}.{claims}.{handtekening}, k={self.publiek}"

    def verstuur(self, abonnement, data, ttl=86400):
        """Geeft de HTTP-status terug (201 = gelukt, 404/410 = abonnement bestaat niet meer)."""
        if not endpoint_toegestaan(abonnement["endpoint"]):
            return 410
        body = versleutel(abonnement["p256dh"], abonnement["auth"], json.dumps(data, ensure_ascii=False).encode())
        verzoek = urllib.request.Request(abonnement["endpoint"], data=body, method="POST", headers={
            "TTL": str(ttl),
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
            "Authorization": self.vapid(abonnement["endpoint"]),
            "Urgency": "normal",
        })
        try:
            with urllib.request.urlopen(verzoek, timeout=12) as antwoord:
                return antwoord.status
        except urllib.error.HTTPError as e:
            return e.code

    def stuur(self, gebruiker_id, data):
        """Zet een melding klaar voor alle apparaten van iemand (verstuurt op de achtergrond)."""
        if not self.actief:
            return
        try:
            self.rij.put_nowait((gebruiker_id, data))
        except queue.Full:
            pass

    def werk(self):
        while True:
            gebruiker_id, data = self.rij.get()
            try:
                c = self.db.open()
                try:
                    abonnementen = c.execute("SELECT * FROM push_abonnementen WHERE gebruiker_id = ?", (gebruiker_id,)).fetchall()
                finally:
                    c.close()
                for ab in abonnementen:
                    try:
                        status = self.verstuur(ab, data)
                    except Exception as e:  # noqa: BLE001
                        print(f"[plan-r] push mislukt: {e!r}", file=sys.stderr, flush=True)
                        continue
                    c = self.db.open()
                    try:
                        if status in (404, 410):
                            c.execute("DELETE FROM push_abonnementen WHERE endpoint = ?", (ab["endpoint"],))
                        elif 200 <= status < 300:
                            c.execute("UPDATE push_abonnementen SET laatst_ok = ? WHERE endpoint = ?", (tijd_tekst(), ab["endpoint"]))
                        else:
                            print(f"[plan-r] pushdienst gaf status {status}", file=sys.stderr, flush=True)
                        c.commit()
                    finally:
                        c.close()
            except Exception as e:  # noqa: BLE001
                print(f"[plan-r] push: {e!r}", file=sys.stderr, flush=True)
