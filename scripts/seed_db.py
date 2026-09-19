"""
Seed the Neon Postgres database with the AdventureWorks CSV data
bundled in the dataa/ folder. Run once to populate the schema that
the SQL agent (pro/sql_agent.py) queries against.

Usage:
    python scripts/seed_db.py
"""

import os
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env")

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
if not DATABASE_URL:
    raise SystemExit("DATABASE_URL / POSTGRES_URL is not set.")

engine = create_engine(DATABASE_URL, connect_args={"connect_timeout": 10})

DATA_DIR = ROOT / "dataa"

# Map CSV file -> (table_name, date_columns)
FILES = {
    "AdventureWorks Calendar Lookup.csv": ("calendar_lookup", ["Date", "Start of Day", "Start of Month", "Start of Week", "Start of Quarter"]),
    "AdventureWorks Customer Lookup.csv": ("customer_lookup", ["BirthDate"]),
    "AdventureWorks Product Categories Lookup.csv": ("product_categories_lookup", []),
    "AdventureWorks Product Lookup.csv": ("product_lookup", []),
    "AdventureWorks Product Subcategories Lookup.csv": ("product_subcategories_lookup", []),
    "AdventureWorks Returns Data.csv": ("returns_data", ["ReturnDate"]),
    "AdventureWorks Sales Data.csv": ("sales_data", ["OrderDate", "StockDate"]),
    "AdventureWorks Territory Lookup.csv": ("territory_lookup", []),
    "Product Category Sales (Unpivot Demo).csv": ("product_category_sales_unpivot_demo", ["Date"]),
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().replace(" ", "_") for c in df.columns]
    return df


def main():
    for filename, (table_name, date_cols) in FILES.items():
        csv_path = DATA_DIR / filename
        if not csv_path.exists():
            print(f"skip (missing): {filename}")
            continue

        try:
            df = pd.read_csv(csv_path, encoding="utf-8")
        except UnicodeDecodeError:
            df = pd.read_csv(csv_path, encoding="latin-1")
        df = normalize_columns(df)

        for col in date_cols:
            normalized_col = col.strip().replace(" ", "_")
            if normalized_col in df.columns:
                df[normalized_col] = pd.to_datetime(df[normalized_col], dayfirst=True, errors="coerce")

        df.to_sql(table_name, engine, if_exists="replace", index=False, chunksize=5000)
        print(f"loaded {len(df):>6} rows -> {table_name}")

    print("\nSeed complete.")


if __name__ == "__main__":
    main()
