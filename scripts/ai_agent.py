"""
LangChain agent that orchestrates the two tools based on the user's question.
Uses GPT-4o function-calling. Multi-step reasoning supported by AgentExecutor.
"""
import os
import json
from dotenv import load_dotenv

from langchain_openai import AzureChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

# from scripts.agent_tools import ALL_TOOLS
# from agent_tools import ALL_TOOLS
from scripts.agent_tools import ALL_TOOLS

load_dotenv()

# ---------------- LLM ----------------
LLM = AzureChatOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"], # type: ignore
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    azure_deployment=os.environ["AZURE_OPENAI_GPT4O_DEPLOYMENT"],
    temperature=0.1,
)

# ---------------- System prompt ----------------
SYSTEM_PROMPT = """You are the Swiss Retail Market Intelligence Assistant.

You help category managers at FMCG suppliers make commercial decisions using two data sources:

1. `search_documents` — internal PDF reports: category performance reviews, promotional ROI analyses,
   pricing benchmarks, supplier invoices, and shopper insights (15 documents, ~30-100 chunks).
   USE FOR: qualitative insights, executive summaries, recommendations, account-level commentary,
   shopper behaviour findings, invoice line items.

2. `query_sales_database` — 500,000+ transaction records across 17 Swiss retail accounts (Migros, Coop,
   Denner, Aldi Suisse, Lidl, etc.), 500 products, 5,000 promotions.
   USE FOR: quantitative analysis — revenues, volumes, price trends, promo uplift, rankings,
   period comparisons, brand/category performance metrics.

DECISION RULES:
- If the question asks for NUMBERS, RANKINGS, TRENDS, or AGGREGATES → use `query_sales_database`.
- If the question asks for INSIGHTS, RECOMMENDATIONS, ROOT CAUSES, or NARRATIVE → use `search_documents`.
- If a question requires BOTH (e.g., "Why did Migros ROI improve in Q3?"), call BOTH tools,
  then synthesize a combined answer. Always show the SQL you ran when using the database tool.

CONVENTIONS:
- Currency: CHF. Numbers in millions where appropriate (e.g., CHF 12.4M).
- Periods: use Swiss quarters (Q1=Jan-Mar, etc.).
- Always cite sources: "From promotions.csv query" or "From Promotional ROI Analysis — Migros, page 2".
- If data is missing or a tool errors, explain clearly instead of inventing numbers.

FORMAT:
- Open with a one-line direct answer.
- Follow with bullet-point evidence (2-4 bullets).
- End with 1-2 actionable recommendations for the category manager.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("user", "{input}"),
    MessagesPlaceholder(variable_name="agent_scratchpad"),
])

# ---------------- Agent ----------------
agent = create_openai_tools_agent(LLM, ALL_TOOLS, prompt)
executor = AgentExecutor(
    agent=agent,
    tools=ALL_TOOLS,
    verbose=True,
    max_iterations=8,
    handle_parsing_errors=True,
)


def ask(question: str) -> str:
    """Public entry point — Phase 5 (FastAPI/Streamlit) will import this."""
    result = executor.invoke({"input": question})
    return result["output"]


if __name__ == "__main__":
    TEST_QUESTIONS = [
        # Pure SQL
        "Which 5 retail accounts generated the most revenue in Q3 2025?",
        # Pure doc search
        "What were the key findings from the shopper insights on chocolate premiumisation?",
        # Hybrid — needs both
        "Why did Migros's promotional ROI improve recently, and what was their Q3 2025 revenue trend?",
        # Hybrid — recommendations
        "Which categories present the best white-space opportunity for us at Denner, and what's the current price gap?",
    ]

    for i, q in enumerate(TEST_QUESTIONS, start=1):
        print("\n" + "=" * 80)
        print(f"Q{i}: {q}")
        print("=" * 80)
        try:
            answer = ask(q)
            print("\n📋 ANSWER:\n")
            print(answer)
        except Exception as e:
            print(f"\n❌ FAILED: {e}")