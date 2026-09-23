#!/usr/bin/env python
"""Publish the live OpenAPI document, and check it against the frozen contract.

Two files, two jobs.

`contracts/openapi.yaml` is the **frozen contract**, written by hand in Phase 0
and agreed between the backend, the web app and every agent building against
either. It is the intent.

`contracts/openapi.generated.json` is what FastAPI **actually serves**, dumped
here. `openapi-typescript` generates the front end's types from it, so a
backend change that breaks the front end fails a typecheck rather than
production.

This tool also reports where the two disagree. It does not fail on a
difference, because the generated document legitimately carries detail the
hand-written one does not -- Pydantic's full schemas, validation ranges,
FastAPI's own error shapes. What it fails on is a **path in the contract that
the server does not serve**: that is a promise made to a client that nobody
kept, and it is the direction that actually breaks someone.

    python tools/publish_openapi.py            # write and report
    python tools/publish_openapi.py --check    # report only, non-zero on drift
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contracts" / "openapi.yaml"
GENERATED = ROOT / "contracts" / "openapi.generated.json"

# Paths the contract describes that are not built yet. Each one is a promise
# with a phase attached rather than an oversight, and the list only shrinks.
NOT_BUILT_YET = {
    ("post", "/auth/signup"),          # Jinja route exists; JSON in Phase 3
    ("post", "/auth/login"),
    ("post", "/auth/logout"),
    ("get", "/auth/sessions"),
    ("delete", "/auth/sessions"),
    ("post", "/auth/consent/request"),  # Phase 3
    ("post", "/auth/consent/confirm"),
    ("get", "/dashboard"),              # Phase 3
    ("get", "/reading/packs/{subject_code}"),  # Phase 5, offline packs
    ("post", "/tutor/photo"),           # Jinja route exists; JSON later
    ("post", "/tutor/feedback"),
    ("get", "/billing/plans"),          # Phase 8
    ("post", "/billing/checkout"),
    ("post", "/billing/webhook"),
    ("get", "/review/queue"),           # Phase 4
    ("patch", "/review/questions/{question_id}"),
}


def live_spec() -> dict:
    from sabi.api.app import app

    return app.openapi()


def contract_spec() -> dict:
    return yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))


def operations(spec: dict, strip_prefix: str = "") -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for path, item in (spec.get("paths") or {}).items():
        if strip_prefix and path.startswith(strip_prefix):
            path = path[len(strip_prefix):]
        elif strip_prefix:
            continue
        for method in item:
            if method in {"get", "post", "put", "patch", "delete"}:
                out.add((method, path))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="report only")
    args = ap.parse_args()

    live = live_spec()
    served = operations(live, strip_prefix="/api")
    promised = operations(contract_spec())

    missing = sorted(promised - served - NOT_BUILT_YET)
    extra = sorted(served - promised)
    pending = sorted(promised & NOT_BUILT_YET)

    print(f"contract promises  {len(promised)} operations")
    print(f"server serves      {len(served)} under /api")
    print(f"not built yet      {len(pending)}")

    if extra:
        print("\nserved but not in the contract (add them, or they are untyped):")
        for method, path in extra:
            print(f"  {method.upper():6s} {path}")

    if missing:
        print("\nPROMISED BUT NOT SERVED -- a client would get a 404:")
        for method, path in missing:
            print(f"  {method.upper():6s} {path}")

    if not args.check:
        # Only the /api surface is published. The Jinja routes are in the live
        # document too, but they return HTML, and generating TypeScript types
        # for them would tell the front end it can call something that does not
        # answer JSON. They disappear from here as they are retired.
        api_only = dict(live)
        api_only["paths"] = {
            path: item
            for path, item in (live.get("paths") or {}).items()
            if path.startswith("/api")
        }
        GENERATED.write_text(
            json.dumps(api_only, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        print(
            f"\nwrote {GENERATED.relative_to(ROOT)} "
            f"({len(api_only['paths'])} paths, /api only)"
        )

    if missing:
        print("\nA path in the contract that the server does not serve is a")
        print("promise nobody kept. Either build it, or move it to NOT_BUILT_YET")
        print("with the phase it belongs to.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
