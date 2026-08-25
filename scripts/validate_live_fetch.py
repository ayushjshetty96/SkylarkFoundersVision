#!/usr/bin/env python3
"""Validate live Monday.com data fetch and normalization."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from src.data_service import create_data_service
from src.tools.join import join_by_company


def main() -> int:
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"ERROR: {exc}")
        print("Create .env from .env.example with your credentials.")
        return 1

    svc = create_data_service(settings)

    print("Fetching Work Orders...")
    wos = svc.get_work_orders()
    print(f"  Work Orders: {len(wos)} records")

    print("Fetching Deals...")
    deals = svc.get_deals()
    print(f"  Deals: {len(deals)} records")

    open_deals = [d for d in deals if d.deal_status == "Open"]
    print(f"  Open deals: {len(open_deals)}")

    total_ar = sum(w.amount_receivable for w in wos if w.amount_receivable)
    print(f"  Total AR: {total_ar:,.2f}")

    pipeline = sum(d.deal_value for d in open_deals if d.deal_value)
    print(f"  Open pipeline: {pipeline:,.2f}")

    join = join_by_company(deals, wos)
    print(f"\nJoin summary: {join.match_summary.model_dump()}")
    print(f"Warnings: {len(join.warnings)}")

    # Historical CSV audit baselines (informational only — Monday is source of truth)
    print("\n--- Comparison to historical CSV audit baselines ---")
    print("  (Monday.com is the production source of truth; count differences are informational)")
    if len(wos) != 176:
        print(f"  INFO: WO count {len(wos)} vs historical CSV audit baseline 176")
    else:
        print(f"  WO count {len(wos)} matches historical CSV audit baseline")
    if len(deals) != 344:
        print(f"  INFO: Deals count {len(deals)} vs historical CSV audit baseline 344")
    else:
        print(f"  Deals count {len(deals)} matches historical CSV audit baseline")

    # Verify name column mapping
    wo_with_alias = sum(1 for w in wos if w.project_alias)
    deals_with_name = sum(1 for d in deals if d.deal_name)
    print(f"\n--- Name column mapping ---")
    print(f"  Work Orders with project_alias (from Name): {wo_with_alias}/{len(wos)}")
    print(f"  Deals with deal_name (from Name): {deals_with_name}/{len(deals)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
