"""Unit tests for Monday client pagination logic."""

from unittest.mock import MagicMock, patch

from src.monday.client import MondayClient


def test_fetch_board_items_pagination():
    client = MondayClient(api_token="test-token")

    page1_data = {
        "boards": [{
            "items_page": {
                "cursor": "cursor-abc",
                "items": [
                    {"id": "1", "name": "Item 1", "column_values": []},
                ],
            },
        }],
    }
    page2_data = {
        "boards": [{
            "items_page": {
                "cursor": None,
                "items": [
                    {"id": "2", "name": "Item 2", "column_values": []},
                ],
            },
        }],
    }

    with patch.object(client, "_execute", side_effect=[page1_data, page2_data]) as mock_exec:
        result = client.fetch_board_items("board-123")

    assert result.total_items == 2
    assert result.pages == 2
    assert mock_exec.call_count == 2
