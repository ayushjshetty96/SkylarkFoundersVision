"""Pydantic domain models."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator


class QuantityField(BaseModel):
    value: float | None = None
    unit: str | None = None
    raw: str | None = None


class WorkOrder(BaseModel):
    item_id: str
    serial_number: str | None = None
    project_alias: str | None = None
    company_code: str | None = None
    company_code_raw: str | None = None
    owner_code: str | None = None
    sector: str | None = None
    sector_normalized: str | None = None
    nature_of_work: str | None = None
    type_of_work: str | None = None
    execution_status: str | None = None
    document_type: str | None = None
    platform_attachment: str | None = None
    po_date: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    data_delivery_date: date | None = None
    last_invoice_date: date | None = None
    recurring_month: str | None = None
    contract_value_excl_gst: float | None = None
    contract_value_incl_gst: float | None = None
    billed_value_excl_gst: float | None = None
    billed_value_incl_gst: float | None = None
    collected_amount_incl_gst: float | None = None
    amount_to_bill_excl_gst: float | None = None
    amount_to_bill_incl_gst: float | None = None
    amount_receivable: float | None = None
    ar_priority: bool = False
    ar_negative_flag: bool = False
    quantity_ops: QuantityField | None = None
    quantity_po: QuantityField | None = None
    quantity_billed: QuantityField | None = None
    quantity_balance: QuantityField | None = None
    invoice_status: str | None = None
    billing_status: str | None = None
    billing_status_normalized_from: str | None = None
    wo_status_billed: str | None = None
    field_warnings: list[str] = Field(default_factory=list)
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class Deal(BaseModel):
    item_id: str
    deal_name: str | None = None
    company_code: str | None = None
    company_code_raw: str | None = None
    owner_code: str | None = None
    deal_status: str | None = None
    deal_stage: str | None = None
    closure_probability: str | None = None
    product_type: str | None = None
    sector: str | None = None
    sector_normalized: str | None = None
    deal_value: float | None = None
    close_date: date | None = None
    tentative_close_date: date | None = None
    created_date: date | None = None
    is_stale_close_date: bool = False
    field_warnings: list[str] = Field(default_factory=list)
    raw_fields: dict[str, Any] = Field(default_factory=dict)


class Company(BaseModel):
    company_code: str
    codes_seen: list[str] = Field(default_factory=list)
    work_order_count: int = 0
    deal_count: int = 0
    has_work_orders: bool = False
    has_deals: bool = False
    sectors_wo: list[str] = Field(default_factory=list)
    sectors_deals: list[str] = Field(default_factory=list)
    sector_mismatch: bool = False


class CompanyJoinResult(BaseModel):
    company_code: str
    match_confidence: str
    match_method: str
    deals: list[Deal] = Field(default_factory=list)
    work_orders: list[WorkOrder] = Field(default_factory=list)
    match_warnings: list[str] = Field(default_factory=list)
    total_open_pipeline_value: float | None = None
    total_ar: float | None = None
    total_contract_value_wo: float | None = None

    @field_validator("deals", mode="before")
    @classmethod
    def _coerce_deals(cls, value: list) -> list:
        if not value:
            return []
        coerced: list[Deal] = []
        for item in value:
            if isinstance(item, dict):
                coerced.append(Deal.model_validate(item))
            elif hasattr(item, "model_dump"):
                coerced.append(Deal.model_validate(item.model_dump(mode="json")))
            else:
                coerced.append(Deal.model_validate(item))
        return coerced

    @field_validator("work_orders", mode="before")
    @classmethod
    def _coerce_work_orders(cls, value: list) -> list:
        if not value:
            return []
        coerced: list[WorkOrder] = []
        for item in value:
            if isinstance(item, dict):
                coerced.append(WorkOrder.model_validate(item))
            elif hasattr(item, "model_dump"):
                coerced.append(WorkOrder.model_validate(item.model_dump(mode="json")))
            else:
                coerced.append(WorkOrder.model_validate(item))
        return coerced


class JoinSummary(BaseModel):
    exact: int = 0
    normalized_exact: int = 0
    ambiguous: int = 0
    unmatched_wo_only: int = 0
    unmatched_deal_only: int = 0


class JoinByCompanyResult(BaseModel):
    match_summary: JoinSummary
    companies: list[CompanyJoinResult] = Field(default_factory=list)
    unmatched: dict[str, list[str] | int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
