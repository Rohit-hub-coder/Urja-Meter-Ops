import os
import json
import time
import hmac
import hashlib
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
USERNAME = os.getenv("URJA_PORTAL_USERNAME")
PASSWORD = os.getenv("URJA_PORTAL_PASSWORD")
USER_AGENT = os.getenv("PORTAL_USER_AGENT", "UrjaMeterOpsApi/1.0")

def hmac_sign(method: str, path: str, query: str, secret: str) -> tuple[str, str]:
    timestamp = str(int(time.time()))
    payload = f"{method}\n{path}\n{query}\n{timestamp}".encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return timestamp, sig

def main():
    client = httpx.Client(
        base_url=BASE_URL,
        headers={
            "User-Agent": USER_AGENT,
            "Origin": BASE_URL,
            "Referer": f"{BASE_URL}/login"
        },
        timeout=15.0
    )

    print("--- Logging in ---")
    login_res = client.post("/login", data={"email": USERNAME, "password": PASSWORD})
    print(f"Login status: {login_res.status_code}")
    print(f"Session cookies: {list(client.cookies.keys())}")

    # 1. Test /portal/meters/search
    print("\n--- Testing GET /portal/meters/search?q=&page=1 ---")
    r_search = client.get("/portal/meters/search?q=&page=1")
    print(f"Status: {r_search.status_code}, content-type: {r_search.headers.get('content-type')}")
    try:
        search_data = r_search.json()
        print(f"Search total: {search_data.get('total')}, page: {search_data.get('page')}, limit: {search_data.get('limit')}")
        print(f"Number of meters returned: {len(search_data.get('data', []))}")
        if search_data.get('data'):
            print("First meter sample:", json.dumps(search_data['data'][0], indent=2))
        with open("docs/evidence/05_meters_search_page1.json", "w") as f:
            f.write(json.dumps(search_data, indent=2))
        print("Saved docs/evidence/05_meters_search_page1.json")
    except Exception as e:
        print(f"Error parsing search response: {e}, text: {r_search.text[:200]}")

    # 2. Test /portal/dts
    print("\n--- Testing GET /portal/dts?page=1 ---")
    r_dts = client.get("/portal/dts?page=1")
    print(f"Status: {r_dts.status_code}")
    try:
        dts_data = r_dts.json()
        print(f"DTs total: {dts_data.get('total')}, count: {len(dts_data.get('data', []))}")
        if dts_data.get('data'):
            print("First DT sample:", json.dumps(dts_data['data'][0], indent=2))
        with open("docs/evidence/06_dts_page1.json", "w") as f:
            f.write(json.dumps(dts_data, indent=2))
        print("Saved docs/evidence/06_dts_page1.json")
    except Exception as e:
        print(f"Error parsing DTs: {e}")

    # 3. Test /portal/keys
    print("\n--- Testing GET /portal/keys ---")
    r_keys = client.get("/portal/keys")
    print(f"Status: {r_keys.status_code}")
    signing_secret = None
    try:
        keys_data = r_keys.json()
        print(f"Keys response: {keys_data}")
        signing_secret = keys_data.get("data", {}).get("signingSecret")
    except Exception as e:
        print(f"Error parsing keys: {e}")

    # 4. Test /portal/export
    if signing_secret:
        print(f"\n--- Testing GET /portal/export?page=1 with HMAC signature ---")
        ts, sig = hmac_sign("GET", "/portal/export", "page=1", signing_secret)
        r_export = client.get("/portal/export?page=1", headers={"x-timestamp": ts, "x-signature": sig})
        print(f"Export status: {r_export.status_code}")
        try:
            export_data = r_export.json()
            print(f"Export total: {export_data.get('total')}, page: {export_data.get('page')}, limit: {export_data.get('limit')}")
            print(f"Number of records in page 1: {len(export_data.get('data', []))}")
            if export_data.get('data'):
                print("First export sample:", json.dumps(export_data['data'][0], indent=2))
            with open("docs/evidence/07_export_page1.json", "w") as f:
                f.write(json.dumps(export_data, indent=2))
            print("Saved docs/evidence/07_export_page1.json")
        except Exception as e:
            print(f"Error parsing export: {e}")

if __name__ == "__main__":
    main()
