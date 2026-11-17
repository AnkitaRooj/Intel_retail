"""
Streamlit UI for the Swiss Retail Market Intelligence Assistant.
- Chat interface
- Source citation badges (doc_type, account, page)
- Example prompt chips
- Latency display
"""
import os
import time
import requests
import streamlit as st

API_URL = os.environ.get("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="Swiss Retail Market Intelligence",
    page_icon="🛒",
    layout="wide",
)

# ---------------- Header ----------------
st.title("🛒 Swiss Retail Market Intelligence Assistant")
st.caption(
    "Ask commercial questions across **500,000+ FMCG transactions** and **15 internal reports** "
    "(category performance, promotional ROI, pricing benchmarks, shopper insights)."
)

# ---------------- Session state ----------------
if "history" not in st.session_state:
    st.session_state.history = []

# ---------------- Sidebar ----------------
with st.sidebar:
    st.header("⚙️ Configuration")
    api_url_input = st.text_input("API Endpoint", API_URL)
    st.markdown("---")
    st.header("📚 Available Tools")
    st.markdown("""
    **1. 📄 `search_documents`**
    Hybrid search over market intelligence PDFs

    **2. 🗄️ `query_sales_database`**
    SQL over 500K transactions + 5K promotions
    """)
    st.markdown("---")
    st.header("💡 Example Questions")
    examples = [
        "Which 5 accounts generated the most revenue in Q3 2025?",
        "What's our price positioning vs Coop and Migros in Beverages?",
        "Which accounts have the highest promotional ROI on chocolate?",
        "What were the key shopper insights on chocolate premiumisation?",
        "What are the top white-space opportunities in Dairy for 2026?",
    ]
    for ex in examples:
        if st.button(ex, use_container_width=True, key=ex):
            st.session_state.pending_question = ex

    st.markdown("---")
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.history = []
        st.rerun()

# ---------------- Health check ----------------
try:
    health = requests.get(f"{api_url_input}/health", timeout=3).json()
    st.success(f"✅ API online — {health['service']}", icon="🟢")
except Exception:
    st.error("❌ API not reachable. Start `python scripts/10_api.py` in another terminal.")
    st.stop()

# ---------------- Render history ----------------
for msg in st.session_state.history:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and msg.get("latency"):
            st.caption(f"⏱️ {msg['latency']} s · Model: {msg.get('model', 'gpt-4o')}")

# ---------------- Input ----------------
question = st.chat_input("Ask a question about Swiss FMCG sales, promotions, or reports…")

if "pending_question" in st.session_state and st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

if question:
    # Show user message
    st.session_state.history.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Call API
    with st.chat_message("assistant"):
        with st.spinner("🧠 Reasoning across sales data and reports…"):
            try:
                t0 = time.time()
                resp = requests.post(
                    f"{api_url_input}/ask",
                    json={"question": question},
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()
                answer = data["answer"]
                latency = data["latency_seconds"]
                model = data["model"]

                st.markdown(answer)
                st.caption(f"⏱️ {latency} s · Model: {model}")
                st.session_state.history.append({
                    "role": "assistant",
                    "content": answer,
                    "latency": latency,
                    "model": model,
                })

            except requests.exceptions.HTTPError as e:
                err = f"❌ API error: {e.response.status_code} — {e.response.text[:300]}"
                st.error(err)
                st.session_state.history.append({"role": "assistant", "content": err})
            except Exception as e:
                err = f"❌ Request failed: {e}"
                st.error(err)
                st.session_state.history.append({"role": "assistant", "content": err})