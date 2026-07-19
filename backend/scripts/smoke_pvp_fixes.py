"""Quick smoke for PvP edge-case fixes."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.data.stag_hunt_seed import STAG_SCENES
from app.models.match import PvpMatch
from app.models.user import User

BASE = "http://127.0.0.1:8003"


def call(method: str, path: str, token: str, body=None, expect: int | None = None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE + path,
        data=data,
        method=method,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode()
            d = json.loads(raw)
            print(method, path, r.status, d.get("status"), "round", d.get("current_round"), "resumed", d.get("resumed"))
            if expect is not None and r.status != expect:
                raise AssertionError(f"expected {expect} got {r.status}")
            return d
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        print("ERR", e.code, raw[:220])
        if expect is not None and e.code != expect:
            raise AssertionError(f"expected {expect} got {e.code}: {raw}") from e
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


def main() -> None:
    db = SessionLocal()
    db.query(PvpMatch).filter(PvpMatch.status.in_(["waiting", "playing"])).update(
        {PvpMatch.status: "cancelled"}, synchronize_session=False
    )
    db.commit()
    a = db.query(User).filter(User.email == "pvp_a@test.cn").first()
    b = db.query(User).filter(User.email == "pvp_b@test.cn").first()
    assert a and b
    ta = create_access_token(a.id, a.password_hash)
    tb = create_access_token(b.id, b.password_hash)
    key = STAG_SCENES[0]["scene_key"]

    # 1) normal match + play
    call("POST", f"/api/v1/pvp/stag-hunt/scenes/{key}/queue", ta)
    d2 = call("POST", f"/api/v1/pvp/stag-hunt/scenes/{key}/queue", tb)
    mid = d2["id"]
    call("POST", f"/api/v1/pvp/matches/{mid}/choice", ta, {"choice": "A", "round_no": 1})
    call("POST", f"/api/v1/pvp/matches/{mid}/choice", tb, {"choice": "B", "round_no": 1})

    # 2) late submit after timeout -> 409
    db.query(PvpMatch).filter(PvpMatch.status.in_(["waiting", "playing"])).update(
        {PvpMatch.status: "cancelled"}, synchronize_session=False
    )
    db.commit()
    call("POST", f"/api/v1/pvp/stag-hunt/scenes/{key}/queue", ta)
    d2 = call("POST", f"/api/v1/pvp/stag-hunt/scenes/{key}/queue", tb)
    mid = d2["id"]
    m = db.get(PvpMatch, mid)
    assert m is not None
    m.round_deadline = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
    db.commit()
    call(
        "POST",
        f"/api/v1/pvp/matches/{mid}/choice",
        ta,
        {"choice": "A", "round_no": 1},
        expect=409,
    )
    call("POST", f"/api/v1/pvp/matches/{mid}/choice", ta, {"choice": "A", "round_no": 2})
    print("late-submit OK")

    # 3) resume
    r = call("POST", f"/api/v1/pvp/stag-hunt/scenes/{key}/queue", ta)
    assert r.get("resumed") is True
    print("resume OK")

    # 4) cancel while playing
    r = call("POST", "/api/v1/pvp/queue/cancel", ta)
    assert r.get("cancelled") is False
    assert r.get("status") == "playing"
    print("cancel-while-playing OK")

    db.close()
    print("ALL SMOKE PASS")


if __name__ == "__main__":
    main()
