# Decision Log

## API vs MCP

**Decision:** Direct Monday.com GraphQL API  
**Rationale:** Fastest reliable path for the assignment window. Python tools provide the same agent architecture. MCP remains a future migration.

## Product: Skylark Founder's Dashboard

**Decision:** Executive dashboard + Ask Skylark conversational assistant  
**Rationale:** Founders need a 30-second financial read (dashboard) and ad-hoc questions (chat). Client-facing branding is **Skylark Founder's Dashboard** — no internal codenames in the UI.

## UI Framework

**Decision:** Streamlit Community Cloud  
**Rationale:** Assignment-compatible hosted prototype at minimal cost. Dashboard is deterministic Python; Groq loads lazily for chat only.

## LLM Provider

**Decision:** Groq `openai/gpt-oss-120b` via OpenAI-compatible function calling  
**Rationale:** Deterministic tools stay in Python; the LLM routes questions and explains compact results. Dashboard works without Groq.

## Company Join Strategy

**Decision:** Normalized company code only (`WOCOMPANY_002` → `COMPANY002`)  
**Rationale:** Deal Name is a masked project alias — not safe for cross-board joins. Company-code normalization yields reliable exact matches.

## Missing Data Treatment

**Decision:** Missing ≠ zero  
**Rationale:** `#VALUE!` and blank financials surface as parse failures or exclusions, not zeros. Aggregations report excluded null counts in tool output.

## Calculations

**Decision:** Deterministic Python aggregation; the LLM never computes business numbers  
**Rationale:** Testable, reproducible, auditable. Revenue measures (contract, billed, collected, receivables) are returned separately with `do_not_sum`.

## Revenue Semantics

**Decision:** “Revenue” in the dashboard and default AI answers = **billed revenue**  
**Rationale:** Distinct from contract value, collected cash, and receivables. Never summed into a fake “total revenue.”

## Data Source

**Decision:** Monday.com live API for production; CSV files for audit/test fixtures only  
**Rationale:** Assignment requirement. CSVs in `data/` are not loaded by the runtime agent.

## Normalization

**Decision:** Automatic in the data layer, not an LLM tool  
**Rationale:** Deterministic — reduces tool rounds and token cost.

## Temporal Filtering

**Decision:** Server-side period resolution (`today`, `this_week`, `this_month`, `this_quarter`, `this_year`)  
**Date field for pipeline periods:** `tentative_close_date` first, then `close_date`, then `created_date`  
**Rationale:** Open pipeline timing is best represented by expected close; fallbacks handle incomplete records. Quarters are computed programmatically from the current date.

## Sector Filtering

**Decision:** Normalized sector matching in Python (`sector_matches`) before aggregation  
**Rationale:** LLM must not filter hundreds of records. Energy/Renewables treated as a related group where labels differ.

## Caching

**Decision:** DataService in-memory TTL (default 180s, `DASHBOARD_CACHE_TTL`) + Streamlit dashboard cache  
**Rationale:** Monday API budget and fast Ask Skylark follow-ups. Refresh invalidates both caches.

## Pipeline Definition

**Decision:** `Deal Status == "Open"` for pipeline sums  
**Probability weights:** High=0.70, Medium=0.40, Low=0.15 (`config/settings.py`)

## Leadership Feature

**Decision:** Revenue & Pipeline Health Snapshot + Skylark dashboard  
**Interpretation of “leadership updates”:** Deterministic cross-board snapshot (pipeline, AR, operations, risks, data quality) that a founder can read or ask Skylark to narrate — not a slide deck generator.

## Clarification Behavior

**Decision:** Clarify only when genuinely ambiguous (e.g. “show performance” with no dimension)  
**Rationale:** Simple KPIs answer immediately; over-clarification hurts founder UX.

## Scope Trade-offs

- No MCP (yet)
- No database (stateless sessions)
- No fuzzy company-name matching (data audit showed codes are sufficient)
- Unit tests mock Monday/Groq; live validation via `scripts/validate_live_fetch.py`

## Future Improvements

- MCP migration for Monday.com
- Hosted evaluation harness for founder Q&A regression
- AR aging when collection dates are reliable
- Persistent conversation history
