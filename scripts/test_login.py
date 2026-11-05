import os
import re
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
USERNAME = os.getenv("URJA_PORTAL_USERNAME")
PASSWORD = os.getenv("URJA_PORTAL_PASSWORD")
USER_AGENT = os.getenv("PORTAL_USER_AGENT", "UrjaMeterOpsApi/1.0")

def redact(text: str) -> str:
    if USERNAME and USERNAME in text:
        text = text.replace(USERNAME, "[REDACTED_USERNAME]")
    if PASSWORD and PASSWORD in text:
        text = text.replace(PASSWORD, "[REDACTED_PASSWORD]")
    text = re.sub(r'([a-zA-Z0-9_\-\.]{20,})', '[REDACTED_TOKEN_OR_COOKIE]', text)
    return text

def test_login():
    client = httpx.Client(
        base_url=BASE_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/login"
        },
        follow_redirects=False,
        timeout=15.0
    )

    print("--- 1. Testing Invalid Login ---")
    bad_res = client.post("/login", data={"email": "wrong@example.com", "password": "wrong"})
    print(f"Invalid login status: {bad_res.status_code}")
    print(f"Invalid login headers: {dict(bad_res.headers)}")
    print(f"Invalid login cookies: {dict(client.cookies)}")
    print("Invalid login body excerpt:", bad_res.text[:300])

    print("\n--- 2. Testing Valid Login ---")
    valid_res = client.post("/login", data={"email": USERNAME, "password": PASSWORD})
    print(f"Valid login status: {valid_res.status_code}")
    print(f"Valid login headers: {dict(valid_res.headers)}")
    print(f"Valid login cookies: {dict(client.cookies)}")
    
    # Save sanitized headers
    with open("docs/evidence/02_login_response_headers.txt", "w") as f:
        for k, v in valid_res.headers.items():
            if k.lower() == "set-cookie":
                f.write(f"{k}: [REDACTED_COOKIE]\n")
            else:
                f.write(f"{k}: {v}\n")
    print("Saved docs/evidence/02_login_response_headers.txt")

    if valid_res.status_code in (302, 303):
        redirect_target = valid_res.headers.get("location")
        print(f"Redirect target: {redirect_target}")
        
        # Follow redirect
        dash_res = client.get(redirect_target)
        print(f"Dashboard status: {dash_res.status_code}")
        print(f"Dashboard headers: {dict(dash_res.headers)}")
        with open("docs/evidence/03_dashboard.html", "w") as f:
            f.write(redact(dash_res.text))
        print("Saved docs/evidence/03_dashboard.html")

if __name__ == "__main__":
    test_login()
