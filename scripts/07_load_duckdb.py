"""
Creates a persistent DuckDB database with the four structured tables.
Idempotent: recreates tables from CSV on each run.
"""
import duckdb
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "retail.duckdb"

# Delete old DB to start clean
if DB_PATH.exists():
    DB_PATH.unlink()

conn = duckdb.connect(str(DB_PATH))

print("▶ Loading tables...")
tables = {
    "products":     ROOT / "data" / "structured" / "products.csv",
    "accounts":     ROOT / "data" / "structured" / "accounts.csv",
    "promotions":   ROOT / "data" / "structured" / "promotions.csv",
    "transactions": ROOT / "data" / "structured" / "transactions.csv",
}

for name, path in tables.items():
    conn.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM read_csv_auto('{path}')")
    count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] # type: ignore
    print(f"   ✓ {name:15s} → {count:>10,} rows")

# Performance index
conn.execute("CREATE INDEX idx_tx_prod ON transactions(product_id)")
conn.execute("CREATE INDEX idx_tx_acct ON transactions(account_id)")
conn.execute("CREATE INDEX idx_tx_date ON transactions(date)")

print(f"\n✅ DuckDB ready at {DB_PATH}")
print(f"   Size: {DB_PATH.stat().st_size / 1024 / 1024:.1f} MB")

# Sanity check
print("\nSample query:")
print(conn.execute("""
    SELECT a.account_name,
           ROUND(SUM(t.total_revenue_chf), 0) AS revenue_chf,
           COUNT(*) AS tx_count
    FROM transactions t
    JOIN accounts a ON t.account_id = a.account_id
    WHERE t.date >= '2025-07-01'
    GROUP BY a.account_name
    ORDER BY revenue_chf DESC
    LIMIT 5
""").fetchdf().to_string(index=False))

conn.close()