"""Temporary data audit script - development only."""
import pandas as pd
import numpy as np
import re
from collections import Counter
from pathlib import Path

pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)

DATA_DIR = Path("data")
WO_FILE = list(DATA_DIR.glob("*work order*"))[0]
DEAL_FILE = list(DATA_DIR.glob("*Deal tracker*"))[0]

def blank_count(series):
    s = series.astype(str).str.strip()
    return s.isin(["", "nan", "None", "NaN"]).sum()

def audit_work_orders():
    wo = pd.read_csv(WO_FILE, header=1)
    print("=" * 80)
    print("WORK ORDERS AUDIT")
    print("=" * 80)
    print(f"Filename: {WO_FILE.name}")
    print(f"Row count: {len(wo)}")
    print(f"Column count: {len(wo.columns)}")
    print(f"\nColumns:\n{list(wo.columns)}")
    print(f"\nDuplicate rows (all cols): {wo.duplicated().sum()}")
    print(f"Duplicate Serial #: {wo['Serial #'].duplicated().sum()}")
    print(f"Unique Serial #: {wo['Serial #'].nunique()}")

    print("\n--- NULL/BLANK COUNTS ---")
    for col in wo.columns:
        n = wo[col].isna().sum() + blank_count(wo[col])
        if n > 0:
            print(f"  {col}: {n} ({n/len(wo)*100:.1f}%)")

    print("\n--- CATEGORICAL DISTINCT VALUES ---")
    cat_cols = [
        "Sector", "Execution Status", "WO Status (billed)", "Billing Status",
        "Collection status", "Invoice Status", "Nature of Work", "Type of Work",
        "Document Type",
        "Is any Skylark software platform part of the client deliverables in this deal?",
        "AR Priority account", "Last executed month of recurring project",
    ]
    for col in cat_cols:
        if col in wo.columns:
            vals = wo[col].dropna().astype(str).str.strip()
            vals = vals[~vals.isin(["", "nan"])]
            print(f"\n{col} ({vals.nunique()} distinct):")
            print(vals.value_counts().to_string())

    print("\n--- NUMERIC COLUMNS ---")
    num_cols = [
        c for c in wo.columns
        if any(x in c.lower() for x in ["amount", "value", "quantity", "billed", "collected", "receivable", "balance"])
    ]
    for col in num_cols:
        s = wo[col]
        coerced = pd.to_numeric(s.astype(str).str.replace(",", "").str.strip(), errors="coerce")
        failed_mask = coerced.isna() & s.notna() & (~s.astype(str).str.strip().isin(["", "nan"]))
        print(f"\n{col}: non-null={s.notna().sum()}, parse_failures={failed_mask.sum()}")
        if failed_mask.sum() > 0:
            print(f"  Non-numeric examples: {s[failed_mask].head(8).tolist()}")
        if coerced.notna().sum() > 0:
            print(f"  stats: min={coerced.min():.4f}, max={coerced.max():.4f}, mean={coerced.mean():.2f}")

    print("\n--- DATE / MONTH COLUMNS ---")
    date_cols = [c for c in wo.columns if "date" in c.lower() or "month" in c.lower()]
    for col in date_cols:
        s = wo[col].dropna().astype(str).str.strip()
        s = s[~s.isin(["", "nan"])]
        print(f"\n{col} ({len(s)} non-empty):")
        print(f"  samples: {s.head(10).tolist()}")
        formats = Counter()
        for v in s:
            if re.match(r"^\d{4}-\d{2}-\d{2}", v):
                formats["YYYY-MM-DD"] += 1
            elif re.match(r"^[A-Za-z]+$", v):
                formats["Month name"] += 1
            else:
                formats["other"] += 1
        print(f"  formats: {dict(formats)}")

    print("\n--- QUANTITY COLUMNS (unit mixing) ---")
    for col in ["Quantity by Ops", "Quantities as per PO", "Quantity billed (till date)", "Balance in quantity"]:
        if col in wo.columns:
            s = wo[col].dropna().astype(str).str.strip()
            s = s[~s.isin(["", "nan"])]
            has_units = s.str.contains(r"[A-Za-z]", regex=True, na=False)
            print(f"{col}: {len(s)} values, {has_units.sum()} with text/units")
            if has_units.sum() > 0:
                print(f"  Examples: {s[has_units].head(10).tolist()}")

    print("\n--- COMPANY CODES ---")
    codes = wo["Customer Name Code"].dropna().astype(str).str.strip()
    print(f"Unique: {codes.nunique()}")
    print(f"All values: {sorted(codes.unique())}")

    print("\n--- DEAL NAME MASKED ---")
    names = wo["Deal name masked"].dropna().astype(str).str.strip()
    print(f"Unique: {names.nunique()}")
    print(names.value_counts().head(15).to_string())

    print("\n--- BD/KAM PERSONNEL ---")
    if "BD/KAM Personnel code" in wo.columns:
        print(wo["BD/KAM Personnel code"].value_counts().to_string())

    print("\n--- CASING / WHITESPACE VARIANTS ---")
    for col in ["Sector", "Execution Status", "Billing Status", "WO Status (billed)", "Invoice Status"]:
        vals = wo[col].dropna().astype(str)
        lower_map = {}
        for v in vals.unique():
            lower_map.setdefault(v.strip().lower(), set()).add(v)
        multi = {k: v for k, v in lower_map.items() if len(v) > 1}
        if multi:
            print(f"{col}: {multi}")

    print("\n--- OUTLIERS ---")
    amt = pd.to_numeric(wo["Amount in Rupees (Excl of GST) (Masked)"], errors="coerce")
    print(f"Amount < 100: {(amt < 100).sum()} rows")
    ar = pd.to_numeric(wo["Amount Receivable (Masked)"], errors="coerce")
    print(f"Negative receivable: {(ar < 0).sum()}")
    print(f"Negative amount: {(amt < 0).sum()}")

    print("\n--- BILLING STATUS TYPO CHECK ---")
    if "Billing Status" in wo.columns:
        print(wo["Billing Status"].dropna().astype(str).value_counts().to_string())

    return wo


def audit_deals():
    deals = pd.read_csv(DEAL_FILE)
    print("\n" + "=" * 80)
    print("DEALS AUDIT")
    print("=" * 80)
    print(f"Filename: {DEAL_FILE.name}")
    print(f"Row count: {len(deals)}")
    print(f"Column count: {len(deals.columns)}")
    print(f"\nColumns:\n{list(deals.columns)}")
    print(f"\nDuplicate rows (all cols): {deals.duplicated().sum()}")

    print("\n--- NULL/BLANK COUNTS ---")
    for col in deals.columns:
        n = deals[col].isna().sum() + blank_count(deals[col])
        if n > 0:
            print(f"  {col}: {n} ({n/len(deals)*100:.1f}%)")

    print("\n--- CATEGORICAL DISTINCT VALUES ---")
    cat_cols = ["Deal Status", "Closure Probability", "Deal Stage", "Product deal", "Sector/service", "Owner code"]
    for col in cat_cols:
        if col in deals.columns:
            vals = deals[col].dropna().astype(str).str.strip()
            vals = vals[~vals.isin(["", "nan"])]
            print(f"\n{col} ({vals.nunique()} distinct):")
            print(vals.value_counts().to_string())

    print("\n--- DEAL VALUE ---")
    dv = pd.to_numeric(deals["Masked Deal value"], errors="coerce")
    print(f"Non-null: {dv.notna().sum()}, null: {dv.isna().sum()}")
    print(f"min={dv.min()}, max={dv.max()}, mean={dv.mean():.2f}, median={dv.median():.2f}")
    print(f"Zero values: {(dv == 0).sum()}")

    print("\n--- DATE COLUMNS ---")
    for col in ["Close Date (A)", "Tentative Close Date", "Created Date"]:
        s = deals[col].dropna().astype(str).str.strip()
        s = s[~s.isin(["", "nan"])]
        print(f"\n{col} ({len(s)} non-empty):")
        print(f"  samples: {s.head(10).tolist()}")
        parsed = pd.to_datetime(s, errors="coerce")
        print(f"  parseable: {parsed.notna().sum()}, failed: {parsed.isna().sum()}")
        if parsed.notna().sum() > 0:
            print(f"  range: {parsed.min()} to {parsed.max()}")
        # past tentative close dates for open deals
        if col == "Tentative Close Date":
            open_deals = deals[deals["Deal Status"].astype(str).str.strip() == "Open"]
            tcd = pd.to_datetime(open_deals[col], errors="coerce")
            past = tcd[tcd < pd.Timestamp("2026-08-25")]
            print(f"  Open deals with tentative close before today: {len(past)}")

    print("\n--- CLIENT CODES ---")
    codes = deals["Client Code"].dropna().astype(str).str.strip()
    print(f"Unique: {codes.nunique()}")
    print(f"Sample: {sorted(codes.unique())[:20]}")
    print(f"Format WOCOMPANY vs COMPANY: WOCOMPANY={codes.str.startswith('WOCOMPANY').sum()}, COMPANY={codes.str.startswith('COMPANY').sum()}")

    print("\n--- DEAL NAME ---")
    names = deals["Deal Name"].dropna().astype(str).str.strip()
    print(f"Unique deal names: {names.nunique()}")
    print(names.value_counts().head(15).to_string())

    print("\n--- DUPLICATE CLIENT+DEAL combos ---")
    dup = deals.groupby(["Deal Name", "Client Code"]).size()
    multi = dup[dup > 1]
    print(f"Deal Name + Client Code combos with >1 row: {len(multi)}")
    if len(multi) > 0:
        print("Top duplicates:")
        print(multi.sort_values(ascending=False).head(10).to_string())

    print("\n--- SECTOR INCONSISTENCIES ---")
    sectors = deals["Sector/service"].dropna().astype(str).str.strip()
    print(sectors.value_counts().to_string())

    print("\n--- INCOMPLETE RECORDS ---")
    incomplete = deals[
        deals["Deal Stage"].isna() | (deals["Deal Stage"].astype(str).str.strip().isin(["", "nan"]))
    ]
    print(f"Missing Deal Stage: {len(incomplete)}")
    if len(incomplete) > 0:
        print(incomplete[["Deal Name", "Client Code", "Deal Status", "Deal Stage", "Masked Deal value"]].head(10).to_string())

    no_value = deals["Masked Deal value"].isna() | (deals["Masked Deal value"].astype(str).str.strip().isin(["", "nan"]))
    print(f"Missing deal value: {no_value.sum()}")

    return deals


def cross_board_analysis(wo, deals):
    print("\n" + "=" * 80)
    print("CROSS-BOARD RELATIONSHIP ANALYSIS")
    print("=" * 80)

    wo_codes = set(wo["Customer Name Code"].dropna().astype(str).str.strip().unique())
    deal_codes_raw = deals["Client Code"].dropna().astype(str).str.strip().unique()

    # Normalize deal codes to WO format
    def to_wo_format(code):
        code = str(code).strip()
        if code.startswith("COMPANY"):
            num = code.replace("COMPANY", "")
            return f"WOCOMPANY_{num.zfill(3)}" if num.isdigit() else None
        if code.startswith("WOCOMPANY"):
            return code
        return None

    deal_codes_norm = {}
    for c in deal_codes_raw:
        norm = to_wo_format(c)
        if norm:
            deal_codes_norm[c] = norm

    deal_codes_wo = set(deal_codes_norm.values())

    print(f"\nWork Order unique company codes: {len(wo_codes)}")
    print(f"Deals unique client codes (raw): {len(deal_codes_raw)}")
    print(f"Deals unique client codes (normalized to WO format): {len(deal_codes_wo)}")

    exact_match = wo_codes & deal_codes_wo
    wo_only = wo_codes - deal_codes_wo
    deal_only = deal_codes_wo - wo_codes

    print(f"\nExact match after normalization: {len(exact_match)}")
    print(f"WO-only companies: {len(wo_only)} -> {sorted(wo_only)}")
    print(f"Deal-only companies: {len(deal_only)} -> {sorted(list(deal_only))[:30]}")

    # Deal name overlap (masked names in both boards)
    wo_deal_names = set(wo["Deal name masked"].dropna().astype(str).str.strip().str.lower().unique())
    deal_names = set(deals["Deal Name"].dropna().astype(str).str.strip().str.lower().unique())
    name_overlap = wo_deal_names & deal_names
    print(f"\nDeal name overlap (case-insensitive): {len(name_overlap)}")
    print(f"Overlapping names: {sorted(name_overlap)[:20]}")
    print(f"WO-only deal names: {len(wo_deal_names - deal_names)}")
    print(f"Deal-only deal names: {len(deal_names - wo_deal_names)}")

    # Serial # linkage
    if "Serial #" in wo.columns:
        serials = wo["Serial #"].dropna().astype(str)
        print(f"\nSerial # in WO: all SDPLDEAL format: {serials.str.match(r'SDPLDEAL-\d+').all()}")

    # Sector overlap
    wo_sectors = set(wo["Sector"].dropna().astype(str).str.strip().unique())
    deal_sectors = set(deals["Sector/service"].dropna().astype(str).str.strip().unique())
    print(f"\nWO sectors: {sorted(wo_sectors)}")
    print(f"Deal sectors: {sorted(deal_sectors)}")
    print(f"Sector overlap: {wo_sectors & deal_sectors}")
    print(f"WO-only sectors: {wo_sectors - deal_sectors}")
    print(f"Deal-only sectors: {deal_sectors - wo_sectors}")

    # Owner code overlap
    wo_owners = set(wo["BD/KAM Personnel code"].dropna().astype(str).str.strip().unique())
    deal_owners = set(deals["Owner code"].dropna().astype(str).str.strip().unique())
    print(f"\nWO BD/KAM owners: {sorted(wo_owners)}")
    print(f"Deal owners: {sorted(deal_owners)}")
    print(f"Owner overlap: {wo_owners & deal_owners}")

    # Company code mapping analysis - numeric part extraction
    print("\n--- COMPANY CODE NUMERIC MAPPING ---")
    wo_nums = {}
    for c in wo_codes:
        m = re.search(r"(\d+)", c)
        if m:
            wo_nums[int(m.group(1))] = c

    deal_nums = {}
    for c in deal_codes_raw:
        m = re.search(r"(\d+)", c)
        if m:
            deal_nums[int(m.group(1))] = c

    shared_nums = set(wo_nums.keys()) & set(deal_nums.keys())
    print(f"Shared numeric IDs: {len(shared_nums)}")
    print(f"Sample mappings:")
    for n in sorted(shared_nums)[:15]:
        print(f"  WO {wo_nums[n]} <-> Deal {deal_nums[n]}")

    # Fuzzy name analysis - deal names that appear as company proxies
    print("\n--- POTENTIAL FUZZY MATCH CANDIDATES ---")
    # Check if deal name 'Sakura' maps to WOCOMPANY_002
    for name in sorted(name_overlap)[:10]:
        wo_companies_for_name = wo[wo["Deal name masked"].str.lower() == name]["Customer Name Code"].unique()
        deal_companies_for_name = deals[deals["Deal Name"].str.lower() == name]["Client Code"].unique()
        print(f"  '{name}': WO companies={list(wo_companies_for_name)[:5]}, Deal clients={list(deal_companies_for_name)[:5]}")

    # Revenue/AR summary for cross-board
    print("\n--- CROSS-BOARD VALUE SUMMARY ---")
    ar = pd.to_numeric(wo["Amount Receivable (Masked)"], errors="coerce")
    print(f"Total WO Amount Receivable: {ar.sum():,.2f}")
    billed = pd.to_numeric(wo["Billed Value in Rupees (Incl of GST.) (Masked)"], errors="coerce")
    print(f"Total WO Billed (incl GST): {billed.sum():,.2f}")
    dv = pd.to_numeric(deals["Masked Deal value"], errors="coerce")
    open_deals = deals[deals["Deal Status"].astype(str).str.strip() == "Open"]
    print(f"Total pipeline value (all deals): {dv.sum():,.2f}")
    print(f"Open pipeline value: {pd.to_numeric(open_deals['Masked Deal value'], errors='coerce').sum():,.2f}")

    # Stage distribution for open pipeline
    print("\n--- OPEN PIPELINE BY STAGE ---")
    print(open_deals.groupby("Deal Stage")["Masked Deal value"].agg(["count", "sum"]).sort_values("sum", ascending=False).to_string())

    # WO execution status
    print("\n--- WO EXECUTION STATUS ---")
    print(wo.groupby("Execution Status").size().to_string())

    # AR priority accounts
    print("\n--- AR PRIORITY ---")
    priority = wo[wo["AR Priority account"].astype(str).str.strip().str.lower() == "priority"]
    print(f"Priority AR accounts: {len(priority)}, total AR: {pd.to_numeric(priority['Amount Receivable (Masked)'], errors='coerce').sum():,.2f}")


if __name__ == "__main__":
    wo = audit_work_orders()
    deals = audit_deals()
    cross_board_analysis(wo, deals)
