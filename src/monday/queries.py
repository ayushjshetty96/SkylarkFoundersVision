"""GraphQL query strings for Monday.com API."""

BOARD_SCHEMA_QUERY = """
query ($board_id: [ID!]!) {
  boards(ids: $board_id) {
    id
    name
    items_count
    columns {
      id
      title
      type
      settings_str
    }
  }
}
"""

BOARD_ITEMS_PAGE_QUERY = """
query ($board_id: ID!, $cursor: String, $limit: Int!) {
  boards(ids: [$board_id]) {
    items_page(limit: $limit, cursor: $cursor) {
      cursor
      items {
        id
        name
        column_values {
          id
          text
          value
          type
        }
      }
    }
  }
}
"""
