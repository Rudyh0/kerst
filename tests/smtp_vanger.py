#!/usr/bin/env python3
"""Een piepkleine nep-mailserver om lokaal te testen. Elke mail komt als .eml in de opgegeven map.

  python3 tests/smtp_vanger.py --poort 2525 --map /tmp/kerst-mails
"""
import argparse
import os
import socketserver
import time


class Vanger(socketserver.StreamRequestHandler):
    def regel(self, tekst):
        self.wfile.write((tekst + "\r\n").encode())

    def handle(self):
        self.regel("220 vanger klaar")
        afzender, ontvangers = "", []
        while True:
            ruw = self.rfile.readline()
            if not ruw:
                return
            opdracht = ruw.decode(errors="replace").strip()
            hoofd = opdracht.upper()
            if hoofd.startswith(("EHLO", "HELO")):
                self.wfile.write(b"250-vanger\r\n250-AUTH PLAIN LOGIN\r\n250 OK\r\n")
            elif hoofd.startswith("AUTH"):
                self.regel("235 ok")
            elif hoofd.startswith("MAIL FROM"):
                afzender, ontvangers = opdracht[10:], []
                self.regel("250 ok")
            elif hoofd.startswith("RCPT TO"):
                ontvangers.append(opdracht[8:])
                self.regel("250 ok")
            elif hoofd == "DATA":
                self.regel("354 ga je gang")
                regels = []
                while True:
                    r = self.rfile.readline()
                    if r in (b".\r\n", b".\n", b""):
                        break
                    regels.append(r[1:] if r.startswith(b"..") else r)
                naam = os.path.join(self.server.map, f"{time.time():.6f}.eml")
                with open(naam, "wb") as f:
                    f.write(b"".join(regels))
                self.regel("250 opgeslagen")
            elif hoofd in ("RSET", "NOOP"):
                self.regel("250 ok")
            elif hoofd == "QUIT":
                self.regel("221 dag")
                return
            else:
                self.regel("502 onbekend")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--poort", type=int, default=2525)
    p.add_argument("--map", required=True)
    a = p.parse_args()
    os.makedirs(a.map, exist_ok=True)
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    s = socketserver.ThreadingTCPServer(("127.0.0.1", a.poort), Vanger)
    s.map = a.map
    s.daemon_threads = True
    s.serve_forever()


if __name__ == "__main__":
    main()
