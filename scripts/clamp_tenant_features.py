"""Report or clamp saved tenant feature flags (defaults to dry-run).

Use only with an isolated test database for --apply.
"""
from __future__ import annotations

import argparse
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from shared.tenancy import loader, store


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write clamped profiles")
    args = parser.parse_args()
    mismatches = 0
    for tenant in store.list_tenants():
        tid = str(tenant.get("id") or "")
        if not tid:
            continue
        payload = store.get_current_payload(tid) or {}
        vertical = tenant.get("vertical") or payload.get("vertical") or "generic"
        saved = payload.get("features") or {}
        effective = loader.effective_features(saved, vertical)
        excess = sorted(k for k, value in saved.items() if bool(value) and not effective.get(k, False))
        if excess:
            mismatches += 1
            print(f"{tid}: vertical={vertical} excess={', '.join(excess)}")
            if args.apply:
                payload["features"] = effective
                store.publish_version(tid, payload, published_by="clamp_tenant_features")
        else:
            print(f"{tid}: OK")
    print(f"summary: mismatches={mismatches} mode={'apply' if args.apply else 'dry-run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
