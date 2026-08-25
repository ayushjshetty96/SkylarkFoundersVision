"""Supplementary cross-board and matching analysis."""
import pandas as pd
import re
from pathlib import Path

DATA_DIR = Path("data")
WO_FILE = list(DATA_DIR.glob("*work order*"))[0]
DEAL_FILE = list(DATA_DIR.glob("*Deal tracker*"))[0]

wo = pd.read_csv(WO_FILE, header=1)
deals = pd.read_csv(DEAL_FILE)

# Remove header-row pollution (values equal to column name)
for col in deals.columns:
    deals = deals[deals[col].astype(str).str.strip() != col]

print("=" * 80)
print("CLEANED DEALS STATS")
print("=" * 80)
print(f"Rows after removing header pollution: {len(deals)}")
print(f"Deal Status: {deals['Deal Status'].value_counts().to_dict()}")
print(f"Missing deal value: {deals['Masked Deal value'].isna().sum()}")

# Company code normalization
def normalize_company_code(code):
    if pd.isna(code):
        return None
    code = str(code).strip().upper()
    m = re.search(r"(\d+)", code)
    if not m:
        return None
    num = int(m.group(1))
    return f"COMPANY{num:03d}"  # canonical: COMPANY001 style with zero-pad

wo["company_norm"] = wo["Customer Name Code"].apply(normalize_company_code)
deals["company_norm"] = deals["Client Code"].apply(normalize_company_code)

print("\n--- NORMALIZED COMPANY MATCHING ---")
wo_codes = set(wo["company_norm"].dropna())
deal_codes = set(deals["company_norm"].dropna())
print(f"WO unique normalized: {len(wo_codes)}")
print(f"Deal unique normalized: {len(deal_codes)}")
print(f"Exact normalized match: {len(wo_codes & deal_codes)}")
print(f"WO-only: {sorted(wo_codes - deal_codes)}")
print(f"Deal-only count: {len(deal_codes - wo_codes)}")

# Deal name -> multiple companies (entity resolution challenge)
print("\n--- DEAL NAME -> MULTIPLE COMPANIES (same masked name) ---")
for board, df, col in [("WO", wo, "Customer Name Code"), ("Deals", deals, "Client Code")]:
    name_col = "Deal name masked" if board == "WO" else "Deal Name"
    grouped = df.groupby(name_col)[col].nunique().sort_values(ascending=False)
    multi = grouped[grouped > 1]
    print(f"\n{board}: {len(multi)} deal names map to multiple companies")
    for name, count in multi.head(10).items():
        companies = df[df[name_col] == name][col].unique()
        print(f"  '{name}' -> {list(companies)[:8]} ({count} companies)")

# Cross-board: same deal name, different company codes between boards
print("\n--- CROSS-BOARD DEAL NAME COMPANY MISMATCH ---")
wo_name_map = wo.groupby(wo["Deal name masked"].str.lower())["company_norm"].apply(lambda x: set(x.dropna())).to_dict()
deal_name_map = deals.groupby(deals["Deal Name"].str.lower())["company_norm"].apply(lambda x: set(x.dropna())).to_dict()

mismatches = []
for name in set(wo_name_map.keys()) & set(deal_name_map.keys()):
    wo_cos = wo_name_map[name]
    deal_cos = deal_name_map[name]
    if wo_cos != deal_cos:
        overlap = wo_cos & deal_cos
        mismatches.append({
            "name": name,
            "wo_only": wo_cos - deal_cos,
            "deal_only": deal_cos - wo_cos,
            "overlap": overlap,
        })

print(f"Deal names in both boards with different company sets: {len(mismatches)}")
for m in sorted(mismatches, key=lambda x: len(x["wo_only"]) + len(x["deal_only"]), reverse=True)[:15]:
    print(f"  {m['name']}: WO={m['wo_only']}, Deals={m['deal_only']}, overlap={m['overlap']}")

# Sector mapping between boards for matched companies
print("\n--- SECTOR MISMATCH FOR MATCHED COMPANIES ---")
matched = wo_codes & deal_codes
sector_mismatches = []
for c in sorted(matched):
    wo_sectors = set(wo[wo["company_norm"] == c]["Sector"].dropna().astype(str).str.strip())
    deal_sectors = set(deals[deals["company_norm"] == c]["Sector/service"].dropna().astype(str).str.strip())
    if wo_sectors and deal_sectors and wo_sectors != deal_sectors:
        sector_mismatches.append((c, wo_sectors, deal_sectors))

print(f"Matched companies with sector mismatch: {len(sector_mismatches)}")
for c, ws, ds in sector_mismatches[:10]:
    print(f"  {c}: WO={ws}, Deals={ds}")

# WO billing/collection health
print("\n--- WO FINANCIAL HEALTH ---")
ar = pd.to_numeric(wo["Amount Receivable (Masked)"], errors="coerce")
to_bill = pd.to_numeric(wo["Amount to be billed in Rs. (Incl. of GST) (Masked)"], errors="coerce")
billed = pd.to_numeric(wo["Billed Value in Rupees (Incl of GST.) (Masked)"], errors="coerce")
contract = pd.to_numeric(wo["Amount in Rupees (Incl of GST) (Masked)"], errors="coerce")

print(f"WO with AR > 0: {(ar > 0).sum()}, total AR: {ar[ar > 0].sum():,.2f}")
print(f"WO with amount to bill > 0: {(to_bill > 0).sum()}, total: {to_bill[to_bill > 0].sum():,.2f}")
print(f"WO not started: {(wo['Execution Status'] == 'Not Started').sum()}")
print(f"WO ongoing: {(wo['Execution Status'] == 'Ongoing').sum()}")
print(f"WO with Billing Status issues: {wo['Billing Status'].dropna().value_counts().to_dict()}")

# Open WO with high AR
print("\n--- TOP 10 AR WORK ORDERS ---")
wo_ar = wo.copy()
wo_ar["ar_num"] = ar
top_ar = wo_ar.nlargest(10, "ar_num")[["Deal name masked", "Customer Name Code", "Serial #", "Sector", "Execution Status", "ar_num", "Invoice Status"]]
print(top_ar.to_string())

# Pipeline weighted by probability
print("\n--- WEIGHTED PIPELINE ---")
deals_clean = deals.copy()
deals_clean["value"] = pd.to_numeric(deals_clean["Masked Deal value"], errors="coerce")
prob_map = {"High": 0.7, "Medium": 0.4, "Low": 0.15}
deals_clean["prob_weight"] = deals_clean["Closure Probability"].map(prob_map)
deals_clean["weighted_value"] = deals_clean["value"] * deals_clean["prob_weight"]
open_d = deals_clean[deals_clean["Deal Status"] == "Open"]
print(f"Open deals: {len(open_d)}")
print(f"Raw pipeline: {open_d['value'].sum():,.2f}")
print(f"Probability-weighted pipeline: {open_d['weighted_value'].sum():,.2f}")
print(f"Open deals missing probability: {open_d['Closure Probability'].isna().sum()}")
print(f"Open deals missing value: {open_d['value'].isna().sum()}")

# Stage ordering for funnel
print("\n--- DEAL FUNNEL (open only) ---")
stage_order = [
    "A. Lead Generated", "B. Sales Qualified Leads", "C. Demo Done", "D. Feasibility",
    "E. Proposal/Commercials Sent", "F. Negotiations", "G. Project Won",
    "H. Work Order Received", "I. POC", "J. Invoice sent", "K. Amount Accrued",
    "M. Projects On Hold",
]
for stage in stage_order:
    subset = open_d[open_d["Deal Stage"] == stage]
    if len(subset) > 0:
        print(f"  {stage}: {len(subset)} deals, {subset['value'].sum():,.0f} INR")

# Recurring vs one-time WO breakdown
print("\n--- WO BY NATURE OF WORK ---")
print(wo.groupby("Nature of Work").agg(
    count=("Serial #", "count"),
    total_contract=("Amount in Rupees (Incl of GST) (Masked)", lambda x: pd.to_numeric(x, errors="coerce").sum()),
    total_ar=("Amount Receivable (Masked)", lambda x: pd.to_numeric(x, errors="coerce").sum()),
).to_string())

# Software platform revenue
print("\n--- SKYLARK PLATFORM ATTACHMENT ---")
platform = wo["Is any Skylark software platform part of the client deliverables in this deal?"].fillna("MISSING")
print(platform.value_counts().to_string())
for p in ["SPECTRA", "DMO", "SPECTRA + DMO"]:
    subset = wo[wo["Is any Skylark software platform part of the client deliverables in this deal?"] == p]
    print(f"  {p}: {len(subset)} WOs, contract value {pd.to_numeric(subset['Amount in Rupees (Incl of GST) (Masked)'], errors='coerce').sum():,.0f}")

# Fuzzy match simulation for 'ace' case
print("\n--- ENTITY RESOLUTION: DEAL NAME ONLY MATCHES ---")
# Names in both boards where company codes don't overlap at all
zero_overlap = [m for m in mismatches if len(m["overlap"]) == 0]
print(f"Deal names with ZERO company code overlap: {len(zero_overlap)}")
for m in zero_overlap[:10]:
    print(f"  {m['name']}: WO={m['wo_only']}, Deals={m['deal_only']}")

# Check if Serial # appears in deals board (unlikely but check)
print("\n--- SERIAL # IN DEALS? ---")
deal_text = deals.astype(str).apply(lambda x: x.str.cat(sep=" ")).str.cat(sep=" ")
serial_in_deals = sum(1 for s in wo["Serial #"].dropna() if str(s) in deal_text)
print(f"WO serial numbers found anywhere in deals data: {serial_in_deals}")

# Date issues in WO
print("\n--- WO DATE ANOMALIES ---")
for col in ["Probable Start Date", "Probable End Date", "Date of PO/LOI"]:
    s = pd.to_datetime(wo[col], errors="coerce")
    print(f"{col}: {s.notna().sum()} parsed, range {s.min()} to {s.max()}")

# End before start
start = pd.to_datetime(wo["Probable Start Date"], errors="coerce")
end = pd.to_datetime(wo["Probable End Date"], errors="coerce")
bad_dates = (end < start) & start.notna() & end.notna()
print(f"End date before start date: {bad_dates.sum()}")

# #VALUE! row
print("\n--- #VALUE! ROW ---")
bad_amt = wo[wo["Amount in Rupees (Excl of GST) (Masked)"].astype(str).str.contains("#VALUE", na=False)]
if len(bad_amt) > 0:
    print(bad_amt[["Deal name masked", "Serial #", "Amount in Rupees (Excl of GST) (Masked)"]].to_string())

# Duplicate deals analysis
print("\n--- DUPLICATE DEAL ROWS (same name+client) ---")
dup_groups = deals.groupby(["Deal Name", "Client Code"]).filter(lambda x: len(x) > 1)
print(f"Rows in duplicate groups: {len(dup_groups)}")
if len(dup_groups) > 0:
    sample = dup_groups.groupby(["Deal Name", "Client Code"]).head(3)
    print(sample[["Deal Name", "Client Code", "Deal Stage", "Masked Deal value", "Tentative Close Date", "Created Date"]].head(15).to_string())
