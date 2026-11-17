"""
Tools for the retail intelligence agent.
  - search_documents : hybrid (BM25 + vector + semantic) over Azure AI Search
  - query_sales_database : LLM-generated SQL over the 500K-record DuckDB
"""
import os
import json
import duckdb
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

from langchain_core.tools import tool
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "retail.duckdb"

# ---------------- Clients ----------------
OAI = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
)
SEARCH = SearchClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    index_name=os.environ["AZURE_SEARCH_INDEX_NAME"],
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)
EMBED_MODEL = os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"]


# ============================================================
# TOOL 1: Document search (RAG)
# ============================================================
@tool
def search_documents(
    query: str,
    doc_type: Optional[str] = None,
    account: Optional[str] = None,
    category: Optional[str] = None,
    top: int = 5,
) -> str:
    """
    Search internal market intelligence documents (category reports, promotional
    ROI analyses, pricing benchmarks, supplier invoices, shopper insights)
    using hybrid retrieval (BM25 + vector + semantic ranker).

    Args:
        query: Natural-language question or search phrase.
        doc_type: Optional filter. One of: category_report, promotional_analysis,
                  pricing_benchmark, supplier_invoice, shopper_insights.
        account: Optional filter. E.g., 'Migros', 'Coop', 'Denner'.
        category: Optional filter. E.g., 'Beverages', 'Dairy', 'Confectionery'.
        top: Number of chunks to return (default 5).

    Returns:
        JSON string with a list of retrieved passages and their metadata.
    """
    # Filter expression
    filters = []
    if doc_type:
        filters.append(f"doc_type eq '{doc_type}'")
    if account:
        filters.append(f"account eq '{account}'")
    if category:
        filters.append(f"category eq '{category}'")
    filter_expr = " and ".join(filters) if filters else None

    # Embed query
    qvec = OAI.embeddings.create(model=EMBED_MODEL, input=query).data[0].embedding

    # Hybrid + semantic
    results = SEARCH.search(
        search_text=query,
        vector_queries=[VectorizedQuery(
            vector=qvec, k_nearest_neighbors=20, fields="content_vector",
        )],
        query_type="semantic",
        semantic_configuration_name="default-semantic",
        filter=filter_expr,
        top=top,
        select=["title", "doc_type", "category", "account", "supplier",
                "topic", "page_number", "content"],
    )

    passages = []
    for hit in results:
        passages.append({
            "source": hit.get("title") or hit.get("source_document", ""),
            "doc_type": hit.get("doc_type"),
            "account": hit.get("account"),
            "category": hit.get("category"),
            "supplier": hit.get("supplier"),
            "topic": hit.get("topic"),
            "page": hit.get("page_number"),
            "content": hit.get("content"),
        })

    if not passages:
        return json.dumps({"results": [], "note": "No matching documents found."})

    return json.dumps({"results": passages}, ensure_ascii=False)


# ============================================================
# TOOL 2: Structured SQL over 500K records
# ============================================================
SCHEMA = """
DuckDB tables available:

accounts(account_id TEXT, account_name TEXT, account_type TEXT, headquarters TEXT, num_stores INT, active BOOL)
products(product_id TEXT, product_name TEXT, brand TEXT, category TEXT, sub_category TEXT, pack_size TEXT, base_price_chf DOUBLE, cost_price_chf DOUBLE, margin_pct DOUBLE)
transactions(transaction_id TEXT, date DATE, account_id TEXT, product_id TEXT, units_sold INT, unit_price_chf DOUBLE, total_revenue_chf DOUBLE, is_promotion BOOL, promo_discount_pct DOUBLE)
promotions(promotion_id TEXT, account_id TEXT, account_name TEXT, product_id TEXT, product_name TEXT, category TEXT, start_date DATE, end_date DATE, promo_type TEXT, discount_pct DOUBLE, volume_uplift_pct DOUBLE)

Join keys: transactions.account_id = accounts.account_id; transactions.product_id = products.product_id; promotions.product_id = products.product_id
Always join to accounts and products for human-readable names in the answer.
Prefer aggregation (SUM, AVG, COUNT) over raw row dumps.
"""

SQL_GEN_SYSTEM = """You are a Swiss FMCG data analyst. Convert the user's question into a single valid DuckDB SQL query.
Rules:
- Output ONLY the SQL. No markdown, no explanation, no semicolons at the end.
- Use the schema exactly as provided.
- Always SELECT with column aliases so the result reads naturally.
- Use date literals like DATE '2025-07-01'.
- If the question is ambiguous, make a reasonable assumption and note it in a comment.
- LIMIT results to at most 50 rows unless aggregating.
<examples>
User: "Which accounts have the highest promotional ROI on chocolate?"
SQL: SELECT a.account_name, ROUND(SUM(t.total_revenue_chf), 2) AS revenue_chf FROM transactions t JOIN accounts a ON t.account_id = a.account_id JOIN products p ON t.product_id = p.product_id WHERE t.is_promotion = TRUE AND p.sub_category = 'Chocolate' GROUP BY a.account_name ORDER BY revenue_chf DESC LIMIT 10

User: "What was the total revenue for Dairy?"
SQL: SELECT ROUND(SUM(t.total_revenue_chf), 2) AS total_revenue_chf FROM transactions t JOIN products p ON t.product_id = p.product_id WHERE p.category = 'Dairy'
</examples>
"""+SCHEMA


@tool
def query_sales_database(question: str) -> str:
    """
    Query 500,000+ Swiss FMCG retail transaction records (sales, pricing,
    promotions, accounts, products) using SQL.

    Use this for quantitative questions like:
      - "Which account had the highest revenue in Q3 2025?"
      - "What was the average promotional discount on chocolate products?"
      - "Which 5 products had the biggest volume uplift?"
      - "How did Denner sales trend across the last 6 months?"

    Do NOT use for retrieving text from PDF reports — use search_documents for that.

    Args:
        question: A natural-language question requiring structured data analysis.

    Returns:
        A JSON string with the executed SQL and the result rows.
    """
    # Step 1: Generate SQL
    gen = OAI.chat.completions.create(
        model=os.environ["AZURE_OPENAI_GPT4O_DEPLOYMENT"],
        messages=[
            {"role": "system", "content": SQL_GEN_SYSTEM + "\n\n" + SCHEMA},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    sql = gen.choices[0].message.content.strip() # type: ignore
    # Strip markdown code fences if the model added them
    sql = sql.replace("```sql", "").replace("```", "").strip().rstrip(";")

    # Step 2: Guardrails — read-only enforcement
    upper = sql.upper()
    forbidden = ["DROP ", "DELETE ", "UPDATE ", "INSERT ", "ALTER ",
                 "TRUNCATE ", "CREATE ", "ATTACH ", "COPY ", "EXPORT "]
    if any(kw in upper for kw in forbidden):
        return json.dumps({
            "error": "Query blocked: only SELECT statements are permitted.",
            "generated_sql": sql,
        })
    if not upper.lstrip().startswith(("SELECT", "WITH")):
        return json.dumps({
            "error": "Query must start with SELECT or WITH.",
            "generated_sql": sql,
        })

    # Step 3: Execute
    try:
        conn = duckdb.connect(str(DB_PATH), read_only=True)
        df = conn.execute(sql).fetchdf()
        conn.close()
        return json.dumps({
            "sql": sql,
            "row_count": len(df),
            "results": df.to_dict(orient="records"),
        }, default=str, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"SQL execution failed: {str(e)}",
            "generated_sql": sql,
        })


# Exported for use by the agent
ALL_TOOLS = [search_documents, query_sales_database]


if __name__ == "__main__":
    # Quick smoke test of each tool
    print("=" * 60)
    print("TOOL 1: search_documents")
    print("=" * 60)
    print(search_documents.invoke({
        "query": "Denner promotional ROI on Feature + Display",
        "doc_type": "promotional_analysis",
        "top": 2,
    })[:600], "...\n")

    print("=" * 60)
    print("TOOL 2: query_sales_database")
    print("=" * 60)
    print(query_sales_database.invoke({
        "question": "Which 3 accounts had the highest total revenue in Q3 2025?"
    })[:800], "...")