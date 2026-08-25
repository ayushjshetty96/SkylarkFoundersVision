"""Unit tests for Monday Name column -> deal alias mapping."""

from src.data_layer import normalize_deal, normalize_work_order
from src.monday.models import MondayColumn, MondayItem


def _minimal_columns() -> list[MondayColumn]:
    return [
        MondayColumn(id="name", title="Name", type="name"),
        MondayColumn(id="text_client", title="Client Code", type="text"),
        MondayColumn(id="text_serial", title="Serial #", type="text"),
    ]


def test_work_order_name_maps_to_deal_name_masked():
    item = MondayItem(
        id="wo-1",
        name="Sakura",
        column_values=[],
    )
    col_map = {"deal_name_masked": "name", "customer_name_code": "text_client"}
    wo = normalize_work_order(item, _minimal_columns(), col_map)
    assert wo.project_alias == "Sakura"


def test_deal_name_maps_from_monday_name_column():
    item = MondayItem(
        id="deal-1",
        name="Alphonse",
        column_values=[],
    )
    col_map = {"deal_name": "name", "client_code": "text_client"}
    deal = normalize_deal(item, _minimal_columns(), col_map)
    assert deal is not None
    assert deal.deal_name == "Alphonse"


def test_name_column_not_used_for_company_join():
    """project_alias/deal_name come from Name; company_code still from Client Code column."""
    from src.monday.models import MondayColumnValue

    item = MondayItem(
        id="deal-2",
        name="Sakura",
        column_values=[
            MondayColumnValue(id="text_client", text="COMPANY002", value=None, type="text"),
        ],
    )
    columns = [
        MondayColumn(id="name", title="Name", type="name"),
        MondayColumn(id="text_client", title="Client Code", type="text"),
    ]
    col_map = {"deal_name": "name", "client_code": "text_client"}
    deal = normalize_deal(item, columns, col_map)
    assert deal is not None
    assert deal.deal_name == "Sakura"
    assert deal.company_code == "COMPANY002"
