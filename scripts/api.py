"""
FastAPI backend exposing the retail intelligence agent.
Endpoints:
  GET  /health              → liveness probe
  POST /ask                 → main Q&A endpoint
  GET  /tools               → returns available tool names (for discovery)
"""
import os
import time
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

from scripts.ai_agent import ask

app = FastAPI(
    title="Swiss Retail Market Intelligence API",
    description="Enterprise RAG assistant over 500K+ FMCG records + internal reports",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- Schemas ----------------
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000,
                          description="Natural-language business question")
    include_trace: bool = Field(False, description="Include agent reasoning trace")


class AskResponse(BaseModel):
    question: str
    answer: str
    latency_seconds: float
    model: str


# ---------------- Endpoints ----------------
@app.get("/health")
def health():
    return {"status": "ok", "service": "retail-intelligence-api"}


@app.get("/tools")
def tools():
    return {
        "tools": [
            {
                "name": "search_documents",
                "description": "Hybrid search over market intelligence PDFs",
            },
            {
                "name": "query_sales_database",
                "description": "SQL over 500K FMCG transaction records",
            },
        ]
    }


@app.post("/ask", response_model=AskResponse)
def ask_endpoint(req: AskRequest):
    try:
        t0 = time.time()
        answer = ask(req.question)
        elapsed = round(time.time() - t0, 2)
        return AskResponse(
            question=req.question,
            answer=answer,
            latency_seconds=elapsed,
            model=os.environ["AZURE_OPENAI_GPT4O_DEPLOYMENT"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("scripts.api:app", host="0.0.0.0", port=8000, reload=False)