"""
Smoke test for the hybrid RAG index.
Runs: keyword (BM25), vector (semantic similarity), and hybrid + semantic ranker.
"""
import os
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

load_dotenv()

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

QUERY = "Which retail accounts drove the highest promotional ROI on chocolate?"

def embed(text):
    return OAI.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input=text,
    ).data[0].embedding

def show(tag, results):
    print(f"\n--- {tag} ---")
    for i, hit in enumerate(results, start=1):
        print(f"  {i}. [{hit['doc_type']} | {hit.get('account') or hit.get('category')} | p{hit['page_number']}]")
        print(f"     {hit['content'][:140].replace(chr(10), ' ')}...")

# 1. BM25 (keyword)
show("BM25 keyword search", list(SEARCH.search(QUERY, top=3,
     select=["title","doc_type","account","category","page_number","content"])))

# 2. Vector only
qvec = embed(QUERY)
show("Vector-only search", list(SEARCH.search(
    search_text=None,
    vector_queries=[VectorizedQuery(vector=qvec, k_nearest_neighbors=3, fields="content_vector")],
    top=3,
    select=["title","doc_type","account","category","page_number","content"],
)))

# 3. Hybrid + semantic ranker (the production pattern)
show("Hybrid + semantic ranker", list(SEARCH.search(
    search_text=QUERY,
    vector_queries=[VectorizedQuery(vector=qvec, k_nearest_neighbors=20, fields="content_vector")],
    query_type="semantic",
    semantic_configuration_name="default-semantic",
    top=3,
    select=["title","doc_type","account","category","page_number","content"],
)))