"""
Demonstrates time savings: measures end-to-end latency of agent answering
a category-manager question, vs the assumed 2-hour manual research baseline.
"""
import importlib
import time
agent_module = importlib.import_module("scripts.ai_agent")
ask = agent_module.ask

QUESTIONS = [
    "Which accounts have the highest promotional ROI on chocolate, and what's driving it?",
    "What is our current price positioning vs Coop and Migros in Beverages?",
    "What are the top 3 white-space opportunities in Dairy for 2026?",
]

MANUAL_MINUTES = 120  # baseline: analyst pulling reports + cross-referencing + drafting

for q in QUESTIONS:
    t0 = time.time()
    answer = ask(q) # type: ignore
    elapsed = time.time() - t0
    saved_min = MANUAL_MINUTES - elapsed / 60
    pct = saved_min / MANUAL_MINUTES * 100
    print(f"\nQ: {q[:80]}...")
    print(f"  Agent time : {elapsed:.1f} s")
    print(f"  Manual est.: {MANUAL_MINUTES} min")
    print(f"  Time saved : {saved_min:.1f} min  ({pct:.0f}%)")