import os
import json
import time
import hmac
import hashlib
from collections import Counter, defaultdict
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
        timeout=20.0
    )

    print("Authenticating...")
    login_res = client.post("/login", data={"email": USERNAME, "password": PASSWORD})
    assert login_res.status_code == 200, f"Login failed: {login_res.status_code}"

    # Get signing secret
    keys_res = client.get("/portal/keys")
    secret = keys_res.json()["data"]["signingSecret"]

    # 1. Fetch full export
    ts, sig = hmac_sign("GET", "/portal/export", "page=1", secret)
    export_res = client.get("/portal/export?page=1", headers={"x-timestamp": ts, "x-signature": sig})
    export_json = export_res.json()
    meters = export_json.get("data", [])
    total_meters = export_json.get("total", len(meters))
    print(f"\n=== 1. FULL METER EXPORT DATASET ===")
    print(f"Total reported: {total_meters}, records received: {len(meters)}")

    # 2. Fetch all DTs
    dts = []
    page = 1
    while True:
        r = client.get(f"/portal/dts?page={page}")
        d = r.json().get("data", [])
        if not d:
            break
        dts.extend(d)
        page += 1
        time.sleep(0.1)
    print(f"Total DTs fetched: {len(dts)}")

    # 3. Analyze Meters
    meter_ids = [m.get("meterId") for m in meters]
    serials = [m.get("serialNo") for m in meters]
    makes = Counter(m.get("make") for m in meters)
    phase_types = Counter(m.get("phaseType") for m in meters)
    statuses = Counter(m.get("installStatus") for m in meters)
    install_types = Counter(m.get("installType") for m in meters)
    builds = Counter(m.get("build") for m in meters)
    dt_codes_in_meters = Counter(m.get("dtCode") for m in meters)

    print("\n--- Meter Attributes Breakdown ---")
    print(f"Unique meter IDs: {len(set(meter_ids))} / {len(meter_ids)}")
    print(f"Unique serials: {len(set(serials))} / {len(serials)}")
    if len(set(meter_ids)) != len(meter_ids):
        dup_ids = [k for k, v in Counter(meter_ids).items() if v > 1]
        print(f"  DUPLICATE METER IDs: {dup_ids}")
    if len(set(serials)) != len(serials):
        dup_serials = [k for k, v in Counter(serials).items() if v > 1]
        print(f"  DUPLICATE SERIALS: {dup_serials}")

    print("Makes:", dict(makes))
    print("Phase types:", dict(phase_types))
    print("Statuses:", dict(statuses))
    print("Install types:", dict(install_types))
    print("Builds:", dict(builds))

    # 4. Analyze Coordinates (Spatial cleanliness)
    print("\n=== 2. SPATIAL / COORDINATE ANALYSIS ===")
    null_coords = 0
    swapped_coords = 0
    out_of_range = 0
    valid_coords = 0
    coord_ranges = {"lat": [999.0, -999.0], "lng": [999.0, -999.0]}

    for m in meters:
        geo = m.get("geo")
        if not geo:
            null_coords += 1
            continue
        lat = geo.get("lat")
        lng = geo.get("lng")
        if lat is None or lng is None:
            null_coords += 1
            continue
        try:
            lat = float(lat)
            lng = float(lng)
        except (ValueError, TypeError):
            null_coords += 1
            continue

        # Check bounds: Jaipur, Rajasthan is roughly lat 26.7-27.1, lng 75.6-76.0
        # If lat is ~75 and lng is ~26, they are swapped!
        if 70.0 <= lat <= 80.0 and 20.0 <= lng <= 35.0:
            swapped_coords += 1
        elif not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
            out_of_range += 1
        else:
            valid_coords += 1
            coord_ranges["lat"][0] = min(coord_ranges["lat"][0], lat)
            coord_ranges["lat"][1] = max(coord_ranges["lat"][1], lat)
            coord_ranges["lng"][0] = min(coord_ranges["lng"][0], lng)
            coord_ranges["lng"][1] = max(coord_ranges["lng"][1], lng)

    print(f"Total meters analyzed for geo: {len(meters)}")
    print(f"Valid coordinates: {valid_coords}")
    print(f"Null / missing coordinates: {null_coords}")
    print(f"Swapped lat/lng detected: {swapped_coords}")
    print(f"Out of range (-90..90, -180..180): {out_of_range}")
    print(f"Coordinate bounding box (valid): Lat {coord_ranges['lat'][0]:.4f} to {coord_ranges['lat'][1]:.4f}, Lng {coord_ranges['lng'][0]:.4f} to {coord_ranges['lng'][1]:.4f}")

    # 5. Analyze Hierarchy
    print("\n=== 3. HIERARCHY ANALYSIS ===")
    dt_code_set = {d["code"] for d in dts}
    print(f"Total known DT codes in /portal/dts: {len(dt_code_set)}")

    orphaned_meters = []
    missing_hierarchy_levels = defaultdict(int)
    feeders = set()
    substations = set()
    divisions = set()
    circles = set()
    zones = set()

    for m in meters:
        mid = m["meterId"]
        dt_code = m.get("dtCode")
        if not dt_code or dt_code not in dt_code_set:
            orphaned_meters.append((mid, dt_code))

        h = m.get("hierarchy", {})
        for level in ["zone", "circle", "division", "subdivision", "substation", "feeder", "dt"]:
            val = h.get(level)
            if not val or not val.get("name") or not val.get("code"):
                missing_hierarchy_levels[level] += 1
            elif level == "feeder":
                feeders.add(val.get("code"))
            elif level == "substation":
                substations.add(val.get("code"))
            elif level == "division":
                divisions.add(val.get("code"))
            elif level == "circle":
                circles.add(val.get("code"))
            elif level == "zone":
                zones.add(val.get("code"))

    print(f"Meters with missing or unmapped dtCode: {len(orphaned_meters)} / {len(meters)}")
    if orphaned_meters:
        print(f"  Sample orphaned meters: {orphaned_meters[:5]}")
    print("Missing hierarchy levels count:", dict(missing_hierarchy_levels))
    print(f"Hierarchy counts: Zones={len(zones)}, Circles={len(circles)}, Divisions={len(divisions)}, Substations={len(substations)}, Feeders={len(feeders)}, DTs={len(dt_code_set)}")

    # Check parent-child consistency:
    # Does each DT belong to exactly one Feeder?
    dt_to_feeder = {}
    dt_feeder_mismatch = []
    for m in meters:
        h = m.get("hierarchy", {})
        dt_obj = h.get("dt") or {}
        feeder_obj = h.get("feeder") or {}
        dt_c = dt_obj.get("code")
        f_c = feeder_obj.get("code")
        if dt_c and f_c:
            if dt_c in dt_to_feeder and dt_to_feeder[dt_c] != f_c:
                dt_feeder_mismatch.append((dt_c, dt_to_feeder[dt_c], f_c))
            else:
                dt_to_feeder[dt_c] = f_c
    print(f"DTs with multiple distinct feeder parents: {len(dt_feeder_mismatch)}")

    # 6. Check Energy / Consumption API parameters & characteristics
    print("\n=== 4. ENERGY / CONSUMPTION API PROBING ===")
    # Pick 5 distinct meters
    test_meter_ids = meter_ids[:5]
    for mid in test_meter_ids:
        r_en = client.get(f"/portal/meters/{mid}/energy")
        en_data = r_en.json().get("data", [])
        print(f"Meter {mid} energy readings count: {len(en_data)}")
        if en_data:
            print(f"  First: {en_data[0]}")
            print(f"  Last:  {en_data[-1]}")
            # Check interval
            if len(en_data) >= 2:
                print(f"  Second: {en_data[1]}")
        time.sleep(0.2)

    # Test query parameters on energy endpoint: from, to, limit, start, end, date
    print("\nTesting query parameters on /portal/meters/J100000/energy ...")
    param_tests = [
        {"limit": "5"},
        {"from": "2026-06-25"},
        {"start": "2026-06-25"},
        {"startDate": "2026-06-25"},
        {"from": "25/06/2026"},
        {"to": "2026-06-28"},
        {"page": "1"},
        {"granularity": "daily"}
    ]
    for p in param_tests:
        r = client.get("/portal/meters/J100000/energy", params=p)
        res_data = r.json().get("data", [])
        print(f"  Params {p}: status={r.status_code}, count={len(res_data)}")
        time.sleep(0.2)

if __name__ == "__main__":
    main()
