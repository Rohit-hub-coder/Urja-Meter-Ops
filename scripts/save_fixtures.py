import os
import json
import re
import httpx
import hmac
import hashlib
import time
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
USERNAME = os.getenv("URJA_PORTAL_USERNAME")
PASSWORD = os.getenv("URJA_PORTAL_PASSWORD")
USER_AGENT = os.getenv("PORTAL_USER_AGENT", "UrjaMeterOpsApi/1.0")

def redact_text(text: str) -> str:
    if USERNAME and USERNAME in text:
        text = text.replace(USERNAME, "[REDACTED_USERNAME]")
    if PASSWORD and PASSWORD in text:
        text = text.replace(PASSWORD, "[REDACTED_PASSWORD]")
    text = re.sub(r'(__Secure-better-auth\.session_token=)[^;\"\s]+', r'\1[REDACTED_SESSION_TOKEN]', text)
    return text

def main():
    os.makedirs("tests/fixtures", exist_ok=True)
    client = httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT, "Origin": BASE_URL, "Referer": f"{BASE_URL}/login"}
    )

    # 1. Login Failure
    r_bad = client.post("/login", data={"email": "bad@example.com", "password": "wrong"})
    with open("tests/fixtures/login_failure.json", "w") as f:
        f.write(redact_text(r_bad.text))

    # 2. Login Success
    r_good = client.post("/login", data={"email": USERNAME, "password": PASSWORD})
    with open("tests/fixtures/login_success.json", "w") as f:
        f.write(redact_text(r_good.text))

    # 3. Keys
    r_keys = client.get("/portal/keys")
    secret = r_keys.json()["data"]["signingSecret"]
    with open("tests/fixtures/portal_keys.json", "w") as f:
        f.write(r_keys.text)

    # 4. Full Export
    ts = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"GET\n/portal/export\npage=1\n{ts}".encode(), hashlib.sha256).hexdigest()
    r_export = client.get("/portal/export?page=1", headers={"x-timestamp": ts, "x-signature": sig})
    with open("tests/fixtures/portal_export.json", "w") as f:
        f.write(r_export.text)

    # 5. DTs (Page 1 and Page 2)
    r_dts1 = client.get("/portal/dts?page=1")
    with open("tests/fixtures/portal_dts_page1.json", "w") as f:
        f.write(r_dts1.text)
    r_dts2 = client.get("/portal/dts?page=2")
    with open("tests/fixtures/portal_dts_page2.json", "w") as f:
        f.write(r_dts2.text)

    # 6. Meter Geo
    r_geo = client.get("/portal/meters/J100000/geo")
    with open("tests/fixtures/meter_geo.json", "w") as f:
        f.write(r_geo.text)

    # 7. Meter Energy (unfiltered)
    r_energy = client.get("/portal/meters/J100000/energy")
    with open("tests/fixtures/meter_energy.json", "w") as f:
        f.write(r_energy.text)

    # 8. Meter Detail (__data.json & HTML)
    r_detail_data = client.get("/meters/J100000/__data.json")
    with open("tests/fixtures/meter_detail_data.json", "w") as f:
        f.write(redact_text(r_detail_data.text))

    r_detail_html = client.get("/meters/J100000")
    with open("tests/fixtures/meter_detail_page.html", "w") as f:
        f.write(redact_text(r_detail_html.text))

    # 9. 404 Error
    r_404 = client.get("/portal/meters/DOESNOTEXIST/energy")
    with open("tests/fixtures/not_found.json", "w") as f:
        f.write(r_404.text)

    print("Fixtures successfully captured and sanitized in tests/fixtures/")

if __name__ == "__main__":
    main()
