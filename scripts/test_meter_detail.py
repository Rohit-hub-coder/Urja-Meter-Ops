import os
import json
import httpx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")
USERNAME = os.getenv("URJA_PORTAL_USERNAME")
PASSWORD = os.getenv("URJA_PORTAL_PASSWORD")
USER_AGENT = os.getenv("PORTAL_USER_AGENT", "UrjaMeterOpsApi/1.0")

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

    client.post("/login", data={"email": USERNAME, "password": PASSWORD})

    sample_meter_id = "J100000"

    # 1. Test /portal/meters/{id}/geo
    print(f"\n--- Testing GET /portal/meters/{sample_meter_id}/geo ---")
    r_geo = client.get(f"/portal/meters/{sample_meter_id}/geo")
    print(f"Geo status: {r_geo.status_code}")
    print("Geo data:", r_geo.text)
    with open("docs/evidence/08_meter_geo_sample.json", "w") as f:
        f.write(r_geo.text)

    # 2. Test /portal/meters/{id}/energy
    print(f"\n--- Testing GET /portal/meters/{sample_meter_id}/energy ---")
    r_energy = client.get(f"/portal/meters/{sample_meter_id}/energy")
    print(f"Energy status: {r_energy.status_code}")
    try:
        energy_data = r_energy.json()
        print(f"Energy readings count: {len(energy_data.get('data', []))}")
        if energy_data.get('data'):
            print("First energy reading:", json.dumps(energy_data['data'][0], indent=2))
            print("Last energy reading:", json.dumps(energy_data['data'][-1], indent=2))
        with open("docs/evidence/09_meter_energy_sample.json", "w") as f:
            f.write(json.dumps(energy_data, indent=2))
    except Exception as e:
        print(f"Error parsing energy: {e}, text: {r_energy.text[:200]}")

    # 3. Test /meters/{id} (Page / SSR data)
    print(f"\n--- Testing GET /meters/{sample_meter_id} (HTML) ---")
    r_meter_page = client.get(f"/meters/{sample_meter_id}")
    print(f"Meter page status: {r_meter_page.status_code}")
    with open("docs/evidence/10_meter_detail_page.html", "w") as f:
        f.write(r_meter_page.text)

    # 4. Test SvelteKit data endpoint /meters/{id}/__data.json
    print(f"\n--- Testing SvelteKit SSR data: GET /meters/{sample_meter_id}/__data.json ---")
    r_data_json = client.get(f"/meters/{sample_meter_id}/__data.json")
    print(f"__data.json status: {r_data_json.status_code}")
    if r_data_json.status_code == 200:
        print("Data json excerpt:", r_data_json.text[:400])
        with open("docs/evidence/11_meter_detail_data.json", "w") as f:
            f.write(r_data_json.text)
    
if __name__ == "__main__":
    main()
