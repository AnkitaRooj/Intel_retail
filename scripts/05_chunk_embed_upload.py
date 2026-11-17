"""
Phase 3 main script:
  1. Download all parsed .txt files from parsed-docs
  2. Extract metadata from filename (doc_type, category, account, supplier, topic)
  3. Chunk each doc (page-aware, table-aware, 500-token target, 50-token overlap)
  4. Generate embeddings via Azure OpenAI text-embedding-3-large
  5. Upload chunks to Azure AI Search (hybrid index)
"""
import os
import re
import time
import uuid
from pathlib import Path
from dotenv import load_dotenv
from openai import AzureOpenAI, APIStatusError
from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import tiktoken

load_dotenv()

# ---------------- Clients ----------------
BLOB = BlobServiceClient.from_connection_string(
    os.environ["AZURE_STORAGE_CONNECTION_STRING"]
)
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
ENC = tiktoken.get_encoding("cl100k_base")

TARGET_TOKENS  = 500
OVERLAP_TOKENS = 50

# ---------------- Metadata extraction ----------------
def extract_metadata(filename: str) -> dict:
    stem = Path(filename).stem
    meta = {
        "title": stem.replace("_", " "),
        "source_document": filename,
        "doc_type": "unknown",
        "category": "",
        "account": "",
        "supplier": "",
        "topic": "",
    }
    if "Category_Report" in stem:
        meta["doc_type"] = "category_report"
        meta["category"] = stem.split("Category_Report_")[1].split("_Q")[0].replace("_", " ")
    elif "Promotional_ROI" in stem:
        meta["doc_type"] = "promotional_analysis"
        meta["account"] = stem.split("Promotional_ROI_")[1].replace("_", " ")
    elif "Pricing_Benchmark" in stem:
        meta["doc_type"] = "pricing_benchmark"
        meta["category"] = stem.split("Pricing_Benchmark_")[1].replace("_", " ")
    elif "Supplier_Invoice" in stem:
        meta["doc_type"] = "supplier_invoice"
        meta["supplier"] = stem.split("Supplier_Invoice_")[1].replace("_", " ")
    elif "Shopper_Insights" in stem:
        meta["doc_type"] = "shopper_insights"
        meta["topic"] = stem.split("Shopper_Insights_")[1].replace("_", " ")
    return meta


# ---------------- Chunking ----------------
PAGE_RX  = re.compile(r"=== Page (\d+) ===")
TABLE_RX = re.compile(r"\[TABLE\](.*?)\[/TABLE\]", re.DOTALL)

def chunk_document(text: str, meta: dict) -> list[dict]:
    """
    Split text into (type, content, page_no) segments.
    Tables are always their own chunk. Text paragraphs are packed into ~500-token chunks
    with 50-token overlap.
    """
    chunks: list[dict] = []
    parts = PAGE_RX.split(text)  # ['preamble', '1', 'page1_body', '2', 'page2_body', ...]
    # Walk pages: parts[i] is page number string, parts[i+1] is page body
    for i in range(1, len(parts), 2):
        page_no = int(parts[i])
        page_body = parts[i + 1] if i + 1 < len(parts) else ""

        # 1. Extract tables
        tables = TABLE_RX.findall(page_body)
        text_without_tables = TABLE_RX.sub("", page_body)

        for tbl in tables:
            tbl_clean = tbl.strip()
            if not tbl_clean:
                continue
            chunks.append({
                "content": f"[TABLE - page {page_no}]\n{tbl_clean}",
                "chunk_type": "table",
                "page_number": page_no,
            })

        # 2. Chunk remaining text (paragraph-based with overlap)
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text_without_tables) if p.strip()]
        current: list[str] = []
        current_tokens = 0

        for para in paragraphs:
            para_tokens = len(ENC.encode(para))
            if current_tokens + para_tokens > TARGET_TOKENS and current:
                chunks.append({
                    "content": "\n\n".join(current),
                    "chunk_type": "text",
                    "page_number": page_no,
                })
                # overlap: keep last paragraph if it fits
                if current and len(ENC.encode(current[-1])) <= OVERLAP_TOKENS:
                    current = [current[-1]]
                    current_tokens = len(ENC.encode(current[-1]))
                else:
                    current, current_tokens = [], 0
            current.append(para)
            current_tokens += para_tokens

        if current:
            chunks.append({
                "content": "\n\n".join(current),
                "chunk_type": "text",
                "page_number": page_no,
            })

    # Enrich with metadata
    for idx, c in enumerate(chunks):
        c.update(meta)
        c["chunk_index"] = idx
        c["token_count"] = len(ENC.encode(c["content"]))
        c["id"] = str(uuid.uuid4())
    return chunks


# ---------------- Embedding with retries ----------------
def embed_batch(texts: list[str], max_retries: int = 6) -> list[list[float]]:
    for attempt in range(max_retries):
        try:
            resp = OAI.embeddings.create(model=EMBED_MODEL, input=texts)
            return [d.embedding for d in resp.data]
        except APIStatusError as e:
            if e.status_code == 429:
                wait = min(60, 2 ** attempt + 5)
                print(f"   ⏳ 429 rate-limit, waiting {wait}s (attempt {attempt+1}/{max_retries})")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Embedding failed after retries")


# ---------------- Main ----------------
src = BLOB.get_container_client("parsed-docs")
txt_blobs = [b.name for b in src.list_blobs() if b.name.endswith(".txt")]
print(f"Found {len(txt_blobs)} parsed .txt documents.\n")

all_chunks: list[dict] = []
for i, blob_name in enumerate(sorted(txt_blobs), start=1):
    text = src.download_blob(blob_name).readall().decode("utf-8", errors="replace")
    meta = extract_metadata(blob_name)
    chunks = chunk_document(text, meta)
    all_chunks.extend(chunks)
    print(f"[{i:>2}/{len(txt_blobs)}] {blob_name}")
    print(f"        → {len(chunks)} chunk(s) | doc_type={meta['doc_type']}")

print(f"\nTotal chunks: {len(all_chunks)}")

# Embed in batches of 100
print("\n▶ Generating embeddings (batches of 100) ...")
BATCH = 100
for start in range(0, len(all_chunks), BATCH):
    batch = all_chunks[start:start + BATCH]
    texts = [c["content"] for c in batch]
    vectors = embed_batch(texts)
    for c, v in zip(batch, vectors):
        c["content_vector"] = v
    done = min(start + BATCH, len(all_chunks))
    pct = done / len(all_chunks) * 100
    print(f"   [{done:>4}/{len(all_chunks)}] {pct:5.1f}% embedded")

# Upload to Azure AI Search
print("\n▶ Uploading chunks to Azure AI Search ...")
UPLOAD_BATCH = 500
total_uploaded = 0
for start in range(0, len(all_chunks), UPLOAD_BATCH):
    batch = all_chunks[start:start + UPLOAD_BATCH]
    result = SEARCH.upload_documents(documents=batch)
    ok = sum(1 for r in result if r.succeeded)
    total_uploaded += ok
    print(f"   Uploaded {ok}/{len(batch)} (running total: {total_uploaded})")

print(f"\n✅ INDEXED {total_uploaded} chunks into '{os.environ['AZURE_SEARCH_INDEX_NAME']}'")