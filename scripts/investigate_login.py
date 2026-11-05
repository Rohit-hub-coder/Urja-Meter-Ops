import os
import re
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
USER_AGENT = os.getenv("PORTAL_USER_AGENT", "UrjaMeterOpsApi/1.0")

def redact(text: str) -> str:
    username = os.getenv("URJA_PORTAL_USERNAME", "")
    password = os.getenv("URJA_PORTAL_PASSWORD", "")
    if username and username in text:
        text = text.replace(username, "[REDACTED_USERNAME]")
    if password and password in text:
        text = text.replace(password, "[REDACTED_PASSWORD]")
    # Redact common cookie values and session IDs
    text = re.sub(r'(session=[a-zA-Z0-9_\-\.]+)', 'session=[REDACTED_SESSION_TOKEN]', text)
    text = re.sub(r'(token=[a-zA-Z0-9_\-\.]+)', 'token=[REDACTED_TOKEN]', text)
    return text

def main():
    client = httpx.Client(
        base_url=BASE_URL,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=False,
        timeout=15.0
    )

    print("--- 1. Checking robots.txt ---")
    try:
        r_robots = client.get("/robots.txt")
        print(f"Status: {r_robots.status_code}")
        print("Robots text content:\n", r_robots.text[:500])
    except Exception as e:
        print(f"Robots check failed: {e}")

    print("\n--- 2. Checking sitemap.xml ---")
    try:
        r_sitemap = client.get("/sitemap.xml")
        print(f"Status: {r_sitemap.status_code}")
        print("Sitemap content:\n", r_sitemap.text[:500])
    except Exception as e:
        print(f"Sitemap check failed: {e}")

    print("\n--- 3. Checking GET /login ---")
    r_login_page = client.get("/login")
    print(f"Status: {r_login_page.status_code}")
    print(f"Headers: {dict(r_login_page.headers)}")
    print(f"Cookies: {dict(client.cookies)}")
    
    # Save raw login page (redacted)
    with open("docs/evidence/01_login_page.html", "w") as f:
        f.write(redact(r_login_page.text))
    print("Saved docs/evidence/01_login_page.html")

    soup = BeautifulSoup(r_login_page.text, "html.parser")
    forms = soup.find_all("form")
    print(f"Found {len(forms)} form(s)")
    for idx, f in enumerate(forms):
        print(f"Form {idx} action: {f.get('action')}, method: {f.get('method')}")
        for inp in f.find_all("input"):
            print(f"  Input: name={inp.get('name')}, type={inp.get('type')}, value={inp.get('value')}")

    # Check script tags
    scripts = soup.find_all("script")
    print(f"\nFound {len(scripts)} script tags:")
    for s in scripts:
        if s.get("src"):
            print(f"  Script src: {s.get('src')}")
        else:
            print(f"  Inline script ({len(s.text)} chars): {s.text[:100]}...")

if __name__ == "__main__":
    main()
