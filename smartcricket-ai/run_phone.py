"""Run SmartCricket AI so a phone on the same Wi-Fi can use it, camera included.

Phones only allow the camera on secure (https) pages, so this script:
  1. finds this computer's address on the local network,
  2. makes a self-signed certificate for that address (kept in data/certs, renewed when the address changes),
  3. starts the app over https on port 8443, reachable from devices on the same Wi-Fi.

Run:   .venv/bin/python run_phone.py
Then open the address it prints on the phone (or scan the QR code on the Live mirror page). The phone shows a
warning because the certificate is self-made: tap "Advanced" -> "Proceed". Stop with Ctrl+C.

Only use this on a network you trust (home or your own hotspot): anyone on that Wi-Fi can reach the sign-in page.
"""
import json
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CERTS = ROOT / "data" / "certs"
PORT = 8443


def lan_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))   # no packet is sent; this only picks the outgoing interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def certificate(ip: str) -> tuple[Path, Path]:
    CERTS.mkdir(parents=True, exist_ok=True)
    key, crt, stamp = CERTS / "lan.key", CERTS / "lan.crt", CERTS / "lan.ip"
    if not (key.exists() and crt.exists() and stamp.exists() and stamp.read_text() == ip):
        subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "825",
                        "-keyout", str(key), "-out", str(crt), "-subj", "/CN=SmartCricket AI (local)",
                        "-addext", f"subjectAltName=IP:{ip},IP:127.0.0.1,DNS:localhost"],
                       check=True, capture_output=True)
        stamp.write_text(ip)
    return key, crt


def main():
    ip = lan_ip()
    key, crt = certificate(ip)
    url = f"https://{ip}:{PORT}/app/live.html"
    (ROOT / "data" / "lan.json").write_text(json.dumps({"ip": ip, "port": PORT, "url": url}))
    print("\n  SmartCricket AI is reachable from your phone on the same Wi-Fi:\n")
    print(f"    {url}\n")
    print("  The phone will warn about the certificate: tap Advanced -> Proceed (it is this computer).")
    print("  Sign in on the phone, then press Start camera.  Stop with Ctrl+C.\n", flush=True)
    sys.exit(subprocess.call([sys.executable, "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0",
                              "--port", str(PORT), "--ssl-keyfile", str(key), "--ssl-certfile", str(crt)], cwd=ROOT))


if __name__ == "__main__":
    main()
