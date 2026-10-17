"""Example of a billing system pushing a stock change to Royal Stack (and reading stock back).

    python infra/scripts/sync_example.py --store demo-grocery --secret <sync secret> --sku RICE-5KG --on-hand 2
    python infra/scripts/sync_example.py --store demo-grocery --secret <sync secret> --pull

Signature: X-Sync-Signature = "sha256=" + HMAC_SHA256(secret, timestamp + "." + body). Timestamps older than five
minutes are refused; repeating an event_id is ignored, so retries are safe.
"""

import argparse
import hashlib
import hmac
import json
import time
import urllib.request
import uuid

API = "https://retail-api-881917398995.asia-south1.run.app"


def signed_post(path: str, secret: str, payload: dict) -> dict:
    body = json.dumps(payload).encode()
    ts = str(int(time.time()))
    sig = "sha256=" + hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    req = urllib.request.Request(API + path, data=body, method="POST",
                                 headers={"Content-Type": "application/json", "X-Sync-Timestamp": ts, "X-Sync-Signature": sig})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res)


def pull(store: str, secret: str) -> list[dict]:
    req = urllib.request.Request(f"{API}/sync/{store}/inventory", headers={"Authorization": f"Bearer {secret}"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", required=True)
    ap.add_argument("--secret", required=True)
    ap.add_argument("--sku")
    ap.add_argument("--on-hand", type=int)
    ap.add_argument("--price", type=float)
    ap.add_argument("--pull", action="store_true")
    a = ap.parse_args()
    if a.pull:
        rows = pull(a.store, a.secret)
        for r in rows[:20]:
            print(f"{r['sku']:<20} on hand {r['on_hand']:>5}  available {r['available']:>5}  price {r['price']}")
        print(f"... {len(rows)} rows")
    else:
        row = {"sku": a.sku, "on_hand": a.on_hand}
        if a.price is not None:
            row["price"] = a.price
        print(signed_post(f"/sync/{a.store}/inventory", a.secret, {"event_id": uuid.uuid4().hex, "rows": [row]}))
