"""Nightly customer job for every store: refresh segments, expire points, release stale redemptions.

    python -m app.jobs.customers
"""

import json

from app.services import db, points, segments


def run() -> dict:
    out = []
    for d in db.client().collection("stores").select([]).stream():
        sid = d.id
        out.append({"store_id": sid, "segments": segments.refresh(sid),
                    "expired_points": points.expire(sid), "released_orders": points.release_stale(sid)})
    return {"stores": out}


if __name__ == "__main__":
    print(json.dumps(run()))
