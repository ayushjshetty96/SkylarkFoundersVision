# Skylark Founder's Dashboard — Monday.com Business Intelligence Agent

Executive business intelligence over live Monday.com Work Orders and Deals, with a deterministic Python BI layer and **Ask Skylark** (Groq-powered conversational assistant).

**HOSTED DEMO:** \<ADD STREAMLIT URL AFTER DEPLOYMENT\>

## Product Overview

- **Skylark Founder's Dashboard** — client-ready executive view of revenue, pipeline, customers, and operations
- **Ask Skylark** — natural-language Q&A with server-side calculations (no raw datasets sent to the LLM)
- **Leadership snapshot** — deterministic executive summary for founder updates

## Architecture

```
Skylark Founder’s Dashboard (Streamlit)
    ↓
Deterministic metrics (Python)          Ask Skylark (Groq tool-calling)
    ↓                                        ↓
DataService (TTL cache)  ←───────────────────┘
    ↓
Normalization layer
    ↓
Monday.com GraphQL API (read-only)
    ↓
Work Orders board + Deals board
```

## LLM Provider

| Setting | Value |
|---------|-------|
| Provider | Groq |
| Model | `openai/gpt-oss-120b` (configurable) |
| Role | Interpret compact tool results — never calculate business numbers |

## Local Setup

### Prerequisites

- Python 3.11+
- Monday.com API token with read access to both boards
- Groq API key (required only for Ask Skylark)

### Installation

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### Environment Variables

Copy `.env.example` to `.env`:

```
MONDAY_API_TOKEN=
MONDAY_WORK_ORDERS_BOARD_ID=
MONDAY_DEALS_BOARD_ID=
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-120b
DEBUG_MODE=false
DASHBOARD_CACHE_TTL=180
```

The dashboard loads with Monday credentials only. Groq is optional for the UI; Ask Skylark requires `GROQ_API_KEY`.

### Run locally

```bash
streamlit run app.py
```

### Run tests

```bash
python -m pytest tests/unit -v
```

### Validate live Monday data

```bash
python scripts/validate_live_fetch.py
```

## Deployment (Streamlit Community Cloud)

Main file: `app.py`

Set secrets in the Streamlit dashboard:

```toml
MONDAY_API_TOKEN = "..."
MONDAY_WORK_ORDERS_BOARD_ID = "..."
MONDAY_DEALS_BOARD_ID = "..."
GROQ_API_KEY = "..."
GROQ_MODEL = "openai/gpt-oss-120b"
DEBUG_MODE = "false"
DASHBOARD_CACHE_TTL = "180"
```

No local `.env` is required in production when secrets are configured.

## Agent Tools

| Tool | Purpose |
|------|---------|
| `business_metric` | KPIs: revenue summary, receivables, pipeline, counts |
| `pipeline_summary` | Open pipeline overview; optional sector/period |
| `pipeline_analysis` | Filtered pipeline by sector + period (e.g. energy this quarter) |
| `sector_summary` | Sector performance; optional sector/period filter |
| `customer_analysis` | Customer rankings, overview, receivables, pipeline |
| `customer_ranking` | Shortcut: best, risk, receivables, overview |
| `customer_health` | HEALTHY / WATCH / AT RISK classification |
| `operations_summary` | Work order execution and billing status |
| `generate_leadership_snapshot` | Executive leadership summary |
| `aggregate` | Server-side grouped metrics |
| `join_by_company` | Cross-board join on normalized company codes |
| `query_items` | Compact record queries (summary by default) |
| `get_board_schema` | Board field inspection |

Normalization runs automatically in the data layer — not exposed as a separate LLM tool.

## Example Questions

- What is our revenue?
- How is our pipeline looking for the energy sector this quarter?
- Who owes us the most?
- Which customers need attention?
- Talk about our customers.
- What should I focus on this week?
- What does leadership need to know?

## Known Limitations

- Financial values are masked in Monday.com source data
- Company join uses **normalized company codes only** — Deal Name is not a join key
- Period filtering for pipeline uses `tentative_close_date` → `close_date` → `created_date`
- Monday API has rate limits — DataService TTL cache (default 180s) reduces duplicate fetches
- Hosted URL must be deployed separately; see placeholder above

See `DECISION_LOG.md` for architectural decisions.
