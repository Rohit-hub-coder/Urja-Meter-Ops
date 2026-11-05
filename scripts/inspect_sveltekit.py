import os
import re
import httpx

BASE_URL = os.getenv("URJA_PORTAL_BASE_URL", "https://urja-ops.flockenergy.tech")

client = httpx.Client(base_url=BASE_URL, timeout=15.0)

# Fetch app.03ZTmlg3.js and start.Dtb6sIWb.js
r_start = client.get("/_app/immutable/entry/start.Dtb6sIWb.js")
r_app = client.get("/_app/immutable/entry/app.03ZTmlg3.js")

print("Start JS len:", len(r_start.text))
print("App JS len:", len(r_app.text))

# Let's find all node chunk filenames in app.js
node_matches = re.findall(r'(\d+):\s*\(\)\s*=>\s*import\("([^"]+)"\)', r_app.text)
print(f"Found {len(node_matches)} route nodes:")
for node_id, path in node_matches:
    print(f"  Node {node_id}: {path}")

# Let's find all routes defined in app.js or start.js
# In SvelteKit, routes are typically defined as an array of tuples/regexes
routes_match = re.findall(r'\[\s*\/([^\/]+)\/\s*,\s*\[([^\]]+)\]', r_app.text)
print("\nRoutes found:", routes_match)

# Let's search for fetch calls or api routes or endpoints in app.js and start.js
fetch_matches = set(re.findall(r'["\'](\/[a-zA-Z0-9_\-\.\/]+)["\']', r_app.text + r_start.text))
api_like = [m for m in fetch_matches if not m.startswith("/_app") and not m.endswith(".js") and not m.endswith(".css")]
print("\nPotential path strings in entry JS:")
for a in sorted(api_like):
    print(" ", a)
