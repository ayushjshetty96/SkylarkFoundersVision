#!/usr/bin/env python3
"""Introspect Monday.com boards and generate config/column_map.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add project root to path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import get_settings
from src.monday.client import MondayAPIError, MondayClient

# Logical field -> expected column title (lowercase) for mapping
WO_FIELD_TITLES: dict[str, str] = {
    "deal_name_masked": "deal name masked",
    "customer_name_code": "customer name code",
    "serial_number": "serial #",
    "nature_of_work": "nature of work",
    "last_executed_month": "last executed month of recurring project",
    "execution_status": "execution status",
    "data_delivery_date": "data delivery date",
    "po_date": "date of po/loi",
    "document_type": "document type",
    "start_date": "probable start date",
    "end_date": "probable end date",
    "owner_code": "bd/kam personnel code",
    "sector": "sector",
    "type_of_work": "type of work",
    "platform_attachment": "is any skylark software platform part of the client deliverables in this deal?",
    "last_invoice_date": "last invoice date",
    "latest_invoice_no": "latest invoice no.",
    "contract_value_excl_gst": "amount in rupees (excl of gst) (masked)",
    "contract_value_incl_gst": "amount in rupees (incl of gst) (masked)",
    "billed_value_excl_gst": "billed value in rupees (excl of gst.) (masked)",
    "billed_value_incl_gst": "billed value in rupees (incl of gst.) (masked)",
    "collected_amount_incl_gst": "collected amount in rupees (incl of gst.) (masked)",
    "amount_to_bill_excl_gst": "amount to be billed in rs. (exl. of gst) (masked)",
    "amount_to_bill_incl_gst": "amount to be billed in rs. (incl. of gst) (masked)",
    "amount_receivable": "amount receivable (masked)",
    "ar_priority": "ar priority account",
    "quantity_ops": "quantity by ops",
    "quantity_po": "quantities as per po",
    "quantity_billed": "quantity billed (till date)",
    "quantity_balance": "balance in quantity",
    "invoice_status": "invoice status",
    "expected_billing_month": "expected billing month",
    "actual_billing_month": "actual billing month",
    "wo_status_billed": "wo status (billed)",
    "collection_status": "collection status",
    "collection_date": "collection date",
    "billing_status": "billing status",
}

DEAL_FIELD_TITLES: dict[str, str] = {
    "deal_name": "deal name",
    "owner_code": "owner code",
    "client_code": "client code",
    "deal_status": "deal status",
    "close_date": "close date (a)",
    "closure_probability": "closure probability",
    "deal_value": "masked deal value",
    "tentative_close_date": "tentative close date",
    "deal_stage": "deal stage",
    "product_type": "product deal",
    "sector": "sector/service",
    "created_date": "created date",
}


# Monday item "Name" column (id: name) holds project/deal alias on live boards
ITEM_NAME_COLUMN_ID = "name"
ITEM_NAME_FIELD_TO_COLUMN: dict[str, str] = {
    "deal_name_masked": ITEM_NAME_COLUMN_ID,
    "deal_name": ITEM_NAME_COLUMN_ID,
}


def _build_column_mapping(columns: list, field_titles: dict[str, str]) -> dict[str, str]:
    title_to_id = {c.title.strip().lower(): c.id for c in columns}
    col_ids = {c.id for c in columns}
    mapping: dict[str, str] = {}
    unmapped: list[str] = []

    for field_key, expected_title in field_titles.items():
        if field_key in ITEM_NAME_FIELD_TO_COLUMN:
            name_col = ITEM_NAME_FIELD_TO_COLUMN[field_key]
            if name_col in col_ids:
                mapping[field_key] = name_col
                continue

        col_id = title_to_id.get(expected_title.lower())
        if col_id:
            mapping[field_key] = col_id
        else:
            unmapped.append(field_key)

    if unmapped:
        print(f"  Warning: unmapped fields: {unmapped}")
        print(f"  Available titles: {sorted(title_to_id.keys())}")

    return mapping


def introspect_board(client: MondayClient, board_id: str, board_key: str, field_titles: dict[str, str]) -> dict:
    print(f"\n{'='*60}")
    print(f"Board: {board_key} (ID: {board_id})")
    print(f"{'='*60}")

    board = client.get_board_schema(board_id)
    print(f"Name: {board.name}")
    print(f"Items count: {board.items_count}")
    print(f"Columns: {len(board.columns)}")
    print()

    for col in board.columns:
        settings_preview = ""
        if col.settings_str and len(col.settings_str) > 80:
            settings_preview = col.settings_str[:80] + "..."
        elif col.settings_str:
            settings_preview = col.settings_str
        print(f"  [{col.id}] {col.title} ({col.type}) {settings_preview}")

    column_mapping = _build_column_mapping(board.columns, field_titles)

    # Fetch item count validation
    fetch = client.fetch_board_items(board_id)
    print(f"\nFetched items: {fetch.total_items} ({fetch.pages} pages, {fetch.duration_ms}ms)")

    return {
        "board_id": board.id,
        "board_name": board.name,
        "items_count": board.items_count,
        "fetched_items": fetch.total_items,
        "columns": column_mapping,
        "column_details": [
            {
                "id": c.id,
                "title": c.title,
                "type": c.type,
                "settings_str": c.settings_str,
            }
            for c in board.columns
        ],
    }


def main() -> int:
    try:
        settings = get_settings()
    except Exception as exc:
        print(f"ERROR: Failed to load settings: {exc}")
        print("Ensure .env exists with: MONDAY_API_TOKEN, MONDAY_WORK_ORDERS_BOARD_ID,")
        print("MONDAY_DEALS_BOARD_ID, GROQ_API_KEY")
        return 1

    missing = []
    if not settings.monday_api_token:
        missing.append("MONDAY_API_TOKEN")
    if not settings.monday_work_orders_board_id:
        missing.append("MONDAY_WORK_ORDERS_BOARD_ID")
    if not settings.monday_deals_board_id:
        missing.append("MONDAY_DEALS_BOARD_ID")

    if missing:
        print(f"ERROR: Missing environment variables: {', '.join(missing)}")
        return 1

    client = MondayClient(
        api_token=settings.monday_api_token,
        api_url=settings.monday_api_url,
    )

    try:
        wo_data = introspect_board(
            client,
            settings.monday_work_orders_board_id,
            "work_orders",
            WO_FIELD_TITLES,
        )
        deals_data = introspect_board(
            client,
            settings.monday_deals_board_id,
            "deals",
            DEAL_FIELD_TITLES,
        )
    except MondayAPIError as exc:
        print(f"ERROR: Monday API failed: {exc}")
        return 1

    column_map = {
        "work_orders": wo_data,
        "deals": deals_data,
    }

    output_path = ROOT / "config" / "column_map.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(column_map, f, indent=2, ensure_ascii=False)

    print(f"\nColumn map written to: {output_path}")
    print(f"Work Orders: {wo_data['fetched_items']} items, {len(wo_data['columns'])} mapped fields")
    print(f"Deals: {deals_data['fetched_items']} items, {len(deals_data['columns'])} mapped fields")

    # Historical audit baselines (CSV dev data only — not expected production counts)
    print("\n--- Comparison to historical CSV audit baselines ---")
    print("  (Monday.com is the production source of truth; count differences are informational)")
    if wo_data["fetched_items"] != 176:
        print(
            f"  INFO: WO count {wo_data['fetched_items']} vs historical CSV audit baseline 176"
        )
    else:
        print(f"  WO count {wo_data['fetched_items']} matches historical CSV audit baseline")
    if deals_data["fetched_items"] != 344:
        print(
            f"  INFO: Deals count {deals_data['fetched_items']} vs historical CSV audit baseline 344"
        )
    else:
        print(f"  Deals count {deals_data['fetched_items']} matches historical CSV audit baseline")

    return 0


if __name__ == "__main__":
    sys.exit(main())
