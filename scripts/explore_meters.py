import os
import re
import httpx
from bs4 import BeautifulSoup
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
    text = re.sub(r'(__Secure-better-auth\.session_token=)[^;]+', r'\1[REDACTED_SESSION_TOKEN]', text)
    return text

def login_and_explore():
    client = httpx.Client(
        base_url=BASE_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/login"
        },
        follow_redirects=True,
        timeout=15.0
    )

    # 1. Login
    res = client.post("/login", data={"email": USERNAME, "password": PASSWORD})
    print(f"Login final status: {res.status_code}, url: {res.url}")
    print(f"Session cookies: {list(client.cookies.keys())}")

    # 2. Get /meters
    r_meters = client.get("/meters")
    print(f"GET /meters status: {r_meters.status_code}")
    with open("docs/evidence/04_meters_page.html", "w") as f:
        f.write(redact(r_meters.text))
    print("Saved docs/evidence/04_meters_page.html")

    soup = BeautifulSoup(r_meters.text, "html.parser")

    # Find navigation links
    print("\n--- Navigation Links (<a> tags) ---")
    nav_links = set()
    for a in soup.find_all("a"):
        href = a.get("href")
        text = a.get_text(strip=True)
        if href:
            nav_links.add((href, text))
    for href, text in sorted(nav_links):
        print(f"  {href} -> '{text}'")

    # Check for forms (e.g. search, filters, export, logout)
    print("\n--- Forms on /meters ---")
    for f in soup.find_all("form"):
        print(f"  Form action={f.get('action')}, method={f.get('method')}")
        for inp in f.find_all(["input", "select", "button"]):
            print(f"    Element: {inp.name}, name={inp.get('name')}, type={inp.get('type')}, value={inp.get('value')}")

    # Check for script bundles to inspect SvelteKit route structure!
    print("\n--- Script tags on /meters ---")
    scripts = []
    for s in soup.find_all("script"):
        src = s.get("src")
        if src:
            scripts.append(src)
            print(f"  Script: {src}")

    return scripts

if __name__ == "__main__":
    login_and_explore()
