"""
Stat Tracker — HTTPS LAN server for the web build.

Why this exists: run_web_lan.bat already serves the built web app to other
devices on the same WiFi over plain http://. That's fine for viewing the
UI, but iOS Safari and Android Chrome both refuse to expose the camera
(getUserMedia) to any page that isn't loaded from a "secure context" —
https://, or http://localhost specifically. A phone opening
http://<your-PC's-LAN-IP>:8000 does NOT count as secure, so the new
"This Device's Camera" button in the web build's camera picker will fail
silently (or with a permission-denied-style error) on a phone even though
it works fine on the PC itself, where http://localhost IS secure.

This script serves the same build/web folder over https:// instead, using
a self-signed certificate it generates once and reuses after that. Phones
on the same WiFi can then open https://<LAN-IP>:8443 and get a real
camera permission prompt.

Because the certificate is self-signed (not issued by a recognized
authority), every browser will show a "connection is not private" /
"your connection isn't secure" warning the first time — this is expected
for a certificate you generated yourself rather than something wrong.
On the phone, tap "Advanced" (or "Details") then "proceed anyway" /
"visit this website" once; it won't ask again for that browser afterward.

Usage: double-click run_web_lan_https.bat (placed in the same "web"
folder as index.html) rather than running this directly — the .bat finds
your LAN IP and launches this with the right working directory.
"""
from __future__ import annotations
import http.server
import os
import socket
import ssl
import sys

PORT = 8443
CERT_FILE = "stattracker_dev_cert.pem"
KEY_FILE = "stattracker_dev_key.pem"


def _ensure_self_signed_cert():
    """Generate a self-signed cert+key on first run, valid for 10 years,
    and reuse them on every run after that. Requires the `cryptography`
    package — the one non-stdlib dependency this needs, since Python's
    built-in `ssl` module can only *use* a certificate, not create one."""
    if os.path.exists(CERT_FILE) and os.path.exists(KEY_FILE):
        return
    try:
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
        import datetime
    except ImportError:
        print("The 'cryptography' package is needed once to generate a local HTTPS")
        print("certificate for LAN camera access. Install it, then run this again:")
        print()
        print("    py -m pip install cryptography")
        print()
        sys.exit(1)

    print("Generating a self-signed HTTPS certificate for LAN use (one-time step)...")
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, "Stat Tracker Local Dev Server"),
    ])
    # Wildcard-ish coverage for typical home/office LAN IPs isn't possible
    # with a single cert the way a real hostname is, so this includes
    # localhost plus this machine's own detected LAN address as SANs —
    # covers the common "open it on the same PC" and "open it on a phone
    # on the same WiFi" cases without needing per-network reconfiguration.
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "127.0.0.1"

    san_names = [x509.DNSName("localhost"), x509.IPAddress(__import__("ipaddress").ip_address("127.0.0.1"))]
    try:
        san_names.append(x509.IPAddress(__import__("ipaddress").ip_address(local_ip)))
    except Exception:
        pass

    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.utcnow())
        .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName(san_names), critical=False)
        .sign(key, hashes.SHA256())
    )
    with open(CERT_FILE, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with open(KEY_FILE, "wb") as f:
        f.write(key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ))
    print(f"Certificate saved as {CERT_FILE} / {KEY_FILE} — reused on future runs.")


def main():
    if not os.path.exists("index.html"):
        print("index.html not found in this folder.")
        print("Place this script (and run_web_lan_https.bat) directly inside the")
        print('"web" folder that flet build web produced.')
        sys.exit(1)

    _ensure_self_signed_cert()

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    handler = http.server.SimpleHTTPRequestHandler
    httpd = http.server.ThreadingHTTPServer(("0.0.0.0", PORT), handler)
    httpd.socket = ctx.wrap_socket(httpd.socket, server_side=True)

    print()
    print(f"Serving HTTPS on port {PORT} (Ctrl+C to stop).")
    print("On a phone's browser, expect a 'connection is not private' warning the")
    print("first time — tap Advanced / Details, then 'proceed anyway'. That's")
    print("expected for a self-signed certificate, not an error.")
    print()
    httpd.serve_forever()


if __name__ == "__main__":
    main()
