"""Load column mapping and normalize Monday items into domain records."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

from src.models.records import Deal, QuantityField, WorkOrder
from src.monday.models import MondayColumn, MondayItem, ParsedItem
from src.monday.parser import build_title_lookup, get_field_value, parse_item
from src.normalization.company_code import normalize_company_code
from src.normalization.dates import parse_iso_date, parse_month_name
from src.normalization.numeric import safe_numeric
from src.normalization.quantity import parse_quantity
from src.normalization.sectors import normalize_billing_status, normalize_sector

logger = logging.getLogger(__name__)

COLUMN_MAP_PATH = Path(__file__).resolve().parents[2] / "config" / "column_map.json"

# Logical field keys used in column_map.json
WO_FIELDS = [
    "deal_name_masked", "customer_name_code", "serial_number", "nature_of_work",
    "last_executed_month", "execution_status", "data_delivery_date", "po_date",
    "document_type", "start_date", "end_date", "owner_code", "sector",
    "type_of_work", "platform_attachment", "last_invoice_date", "latest_invoice_no",
    "contract_value_excl_gst", "contract_value_incl_gst", "billed_value_excl_gst",
    "billed_value_incl_gst", "collected_amount_incl_gst", "amount_to_bill_excl_gst",
    "amount_to_bill_incl_gst", "amount_receivable", "ar_priority", "quantity_ops",
    "quantity_po", "quantity_billed", "quantity_balance", "invoice_status",
    "expected_billing_month", "actual_billing_month", "wo_status_billed",
    "collection_status", "collection_date", "billing_status",
]

DEAL_FIELDS = [
    "deal_name", "owner_code", "client_code", "deal_status", "close_date",
    "closure_probability", "deal_value", "tentative_close_date", "deal_stage",
    "product_type", "sector", "created_date",
]

# Title-based fallback when column_map not yet populated
WO_TITLE_MAP: dict[str, str] = {
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

DEAL_TITLE_MAP: dict[str, str] = {
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

DEAL_HEADER_POLLUTION = {
    "deal name", "owner code", "client code", "deal status",
    "close date (a)", "closure probability", "masked deal value",
    "tentative close date", "deal stage", "product deal",
    "sector/service", "created date",
}

# Monday item "Name" column (id: name) — project/deal alias, not a company join key
ITEM_NAME_COLUMN_ID = "name"
ITEM_NAME_FIELD_TO_COLUMN: dict[str, str] = {
    "deal_name_masked": ITEM_NAME_COLUMN_ID,
    "deal_name": ITEM_NAME_COLUMN_ID,
}


def load_column_map() -> dict[str, Any]:
    if not COLUMN_MAP_PATH.exists():
        return {"work_orders": {"columns": {}}, "deals": {"columns": {}}}
    with open(COLUMN_MAP_PATH, encoding="utf-8") as f:
        return json.load(f)


def _get_text(
    parsed: ParsedItem,
    field_key: str,
    title_map: dict[str, str],
    col_map: dict[str, str],
    columns: list[MondayColumn],
    *,
    item_name: str | None = None,
) -> str | None:
    col_id = col_map.get(field_key)
    if col_id == ITEM_NAME_COLUMN_ID or field_key in ITEM_NAME_FIELD_TO_COLUMN:
        if item_name and str(item_name).strip():
            return str(item_name).strip()
        return None

    if col_id and col_id in parsed.columns:
        pcv = parsed.columns[col_id]
        val = pcv.parsed_value if pcv.parsed_value is not None else pcv.text
        if val is not None:
            return str(val).strip() if str(val).strip() else None

    title = title_map.get(field_key)
    if title:
        lookup = build_title_lookup(columns)
        col = lookup.get(title)
        if col and col.id in parsed.columns:
            pcv = parsed.columns[col.id]
            val = pcv.parsed_value if pcv.parsed_value is not None else pcv.text
            if val is not None:
                return str(val).strip() if str(val).strip() else None

    return None


def _get_numeric(
    parsed: ParsedItem,
    field_key: str,
    title_map: dict[str, str],
    col_map: dict[str, str],
    columns: list[MondayColumn],
    warnings: list[str],
    *,
    item_name: str | None = None,
) -> float | None:
    text = _get_text(parsed, field_key, title_map, col_map, columns, item_name=item_name)
    if text is None:
        return None
    result = safe_numeric(text)
    if result.warning:
        warnings.append(f"{field_key}: {result.warning} (raw={result.raw})")
    return result.value


def _qty_field(
    parsed: ParsedItem,
    field_key: str,
    title_map: dict[str, str],
    col_map: dict[str, str],
    columns: list[MondayColumn],
    warnings: list[str],
    *,
    item_name: str | None = None,
) -> QuantityField | None:
    text = _get_text(parsed, field_key, title_map, col_map, columns, item_name=item_name)
    if text is None:
        return None
    q = parse_quantity(text)
    if q.warning:
        warnings.append(f"{field_key}: {q.warning}")
    return QuantityField(value=q.value, unit=q.unit, raw=q.raw)


def normalize_work_order(item: MondayItem, columns: list[MondayColumn], col_map: dict[str, str] | None = None) -> WorkOrder:
    col_map = col_map or {}
    parsed = parse_item(item, columns)
    warnings: list[str] = []

    company_raw = _get_text(parsed, "customer_name_code", WO_TITLE_MAP, col_map, columns)
    company_code = normalize_company_code(company_raw)

    ar = _get_numeric(parsed, "amount_receivable", WO_TITLE_MAP, col_map, columns, warnings)
    ar_negative = ar is not None and ar < 0

    billing_raw = _get_text(parsed, "billing_status", WO_TITLE_MAP, col_map, columns)
    billing_status, billing_note = normalize_billing_status(billing_raw)
    if billing_note:
        warnings.append(f"billing_status: {billing_note}")

    platform_raw = _get_text(parsed, "platform_attachment", WO_TITLE_MAP, col_map, columns)
    if platform_raw is None:
        platform_attachment = None
    else:
        platform_attachment = platform_raw

    exec_status = _get_text(parsed, "execution_status", WO_TITLE_MAP, col_map, columns)

    month_raw = _get_text(parsed, "last_executed_month", WO_TITLE_MAP, col_map, columns)
    month_result = parse_month_name(month_raw)

    return WorkOrder(
        item_id=item.id,
        serial_number=_get_text(parsed, "serial_number", WO_TITLE_MAP, col_map, columns) or item.name,
        project_alias=_get_text(
            parsed, "deal_name_masked", WO_TITLE_MAP, col_map, columns, item_name=item.name
        ),
        company_code=company_code,
        company_code_raw=company_raw,
        owner_code=_get_text(parsed, "owner_code", WO_TITLE_MAP, col_map, columns),
        sector=_get_text(parsed, "sector", WO_TITLE_MAP, col_map, columns),
        sector_normalized=normalize_sector(_get_text(parsed, "sector", WO_TITLE_MAP, col_map, columns)),
        nature_of_work=_get_text(parsed, "nature_of_work", WO_TITLE_MAP, col_map, columns),
        type_of_work=_get_text(parsed, "type_of_work", WO_TITLE_MAP, col_map, columns),
        execution_status=exec_status,
        document_type=_get_text(parsed, "document_type", WO_TITLE_MAP, col_map, columns),
        platform_attachment=platform_attachment,
        po_date=parse_iso_date(_get_text(parsed, "po_date", WO_TITLE_MAP, col_map, columns)).value,
        start_date=parse_iso_date(_get_text(parsed, "start_date", WO_TITLE_MAP, col_map, columns)).value,
        end_date=parse_iso_date(_get_text(parsed, "end_date", WO_TITLE_MAP, col_map, columns)).value,
        data_delivery_date=parse_iso_date(_get_text(parsed, "data_delivery_date", WO_TITLE_MAP, col_map, columns)).value,
        last_invoice_date=parse_iso_date(_get_text(parsed, "last_invoice_date", WO_TITLE_MAP, col_map, columns)).value,
        recurring_month=month_result.month_name,
        contract_value_excl_gst=_get_numeric(parsed, "contract_value_excl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        contract_value_incl_gst=_get_numeric(parsed, "contract_value_incl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        billed_value_excl_gst=_get_numeric(parsed, "billed_value_excl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        billed_value_incl_gst=_get_numeric(parsed, "billed_value_incl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        collected_amount_incl_gst=_get_numeric(parsed, "collected_amount_incl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        amount_to_bill_excl_gst=_get_numeric(parsed, "amount_to_bill_excl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        amount_to_bill_incl_gst=_get_numeric(parsed, "amount_to_bill_incl_gst", WO_TITLE_MAP, col_map, columns, warnings),
        amount_receivable=ar,
        ar_priority=(_get_text(parsed, "ar_priority", WO_TITLE_MAP, col_map, columns) or "").lower() == "priority",
        ar_negative_flag=ar_negative,
        quantity_ops=_qty_field(parsed, "quantity_ops", WO_TITLE_MAP, col_map, columns, warnings),
        quantity_po=_qty_field(parsed, "quantity_po", WO_TITLE_MAP, col_map, columns, warnings),
        quantity_billed=_qty_field(parsed, "quantity_billed", WO_TITLE_MAP, col_map, columns, warnings),
        quantity_balance=_qty_field(parsed, "quantity_balance", WO_TITLE_MAP, col_map, columns, warnings),
        invoice_status=_get_text(parsed, "invoice_status", WO_TITLE_MAP, col_map, columns),
        billing_status=billing_status,
        billing_status_normalized_from="BIlled" if billing_note else None,
        wo_status_billed=_get_text(parsed, "wo_status_billed", WO_TITLE_MAP, col_map, columns),
        field_warnings=warnings,
    )


def normalize_deal(item: MondayItem, columns: list[MondayColumn], col_map: dict[str, str] | None = None, *, as_of: date | None = None) -> Deal | None:
    col_map = col_map or {}
    parsed = parse_item(item, columns)
    warnings: list[str] = []

    company_raw = _get_text(parsed, "client_code", DEAL_TITLE_MAP, col_map, columns)
    company_code = normalize_company_code(company_raw)

    deal_status = _get_text(parsed, "deal_status", DEAL_TITLE_MAP, col_map, columns)
    tentative_close = parse_iso_date(_get_text(parsed, "tentative_close_date", DEAL_TITLE_MAP, col_map, columns))

    as_of = as_of or date.today()
    is_stale = (
        deal_status == "Open"
        and tentative_close.value is not None
        and tentative_close.value < as_of
    )

    deal_value = _get_numeric(parsed, "deal_value", DEAL_TITLE_MAP, col_map, columns, warnings)

    deal = Deal(
        item_id=item.id,
        deal_name=_get_text(
            parsed, "deal_name", DEAL_TITLE_MAP, col_map, columns, item_name=item.name
        ),
        company_code=company_code,
        company_code_raw=company_raw,
        owner_code=_get_text(parsed, "owner_code", DEAL_TITLE_MAP, col_map, columns),
        deal_status=deal_status,
        deal_stage=_get_text(parsed, "deal_stage", DEAL_TITLE_MAP, col_map, columns),
        closure_probability=_get_text(parsed, "closure_probability", DEAL_TITLE_MAP, col_map, columns),
        product_type=_get_text(parsed, "product_type", DEAL_TITLE_MAP, col_map, columns),
        sector=_get_text(parsed, "sector", DEAL_TITLE_MAP, col_map, columns),
        sector_normalized=normalize_sector(_get_text(parsed, "sector", DEAL_TITLE_MAP, col_map, columns)),
        deal_value=deal_value,
        close_date=parse_iso_date(_get_text(parsed, "close_date", DEAL_TITLE_MAP, col_map, columns)).value,
        tentative_close_date=tentative_close.value,
        created_date=parse_iso_date(_get_text(parsed, "created_date", DEAL_TITLE_MAP, col_map, columns)).value,
        is_stale_close_date=is_stale,
        field_warnings=warnings,
    )

    # Header pollution filter
    if deal.deal_status in DEAL_HEADER_POLLUTION or deal.deal_name in DEAL_HEADER_POLLUTION:
        return None
    if deal.deal_status == "Deal Status":
        return None

    return deal


def normalize_work_orders(items: list[MondayItem], columns: list[MondayColumn], board_key: str = "work_orders") -> list[WorkOrder]:
    col_map = load_column_map().get(board_key, {}).get("columns", {})
    return [normalize_work_order(item, columns, col_map) for item in items]


def normalize_deals(items: list[MondayItem], columns: list[MondayColumn], board_key: str = "deals", as_of: date | None = None) -> list[Deal]:
    col_map = load_column_map().get(board_key, {}).get("columns", {})
    results: list[Deal] = []
    for item in items:
        deal = normalize_deal(item, columns, col_map, as_of=as_of)
        if deal is not None:
            results.append(deal)
    return results
