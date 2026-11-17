"""
Parses every PDF in unstructured-docs via Azure Document Intelligence (prebuilt-layout),
extracts text + tables + page structure, and stores the JSON result in parsed-docs.
Also produces a flat .txt (per document) ready for chunking in Phase 3.
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

load_dotenv()

BLOB = BlobServiceClient.from_connection_string(
    os.environ["AZURE_STORAGE_CONNECTION_STRING"]
)
DI = DocumentIntelligenceClient(
    endpoint=os.environ["AZURE_DI_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["AZURE_DI_KEY"]),
)

SRC_CONTAINER = "unstructured-docs"
OUT_CONTAINER = "parsed-docs"

src = BLOB.get_container_client(SRC_CONTAINER)
out = BLOB.get_container_client(OUT_CONTAINER)


def analyze_pdf(blob_name: str) -> dict:
    """Run prebuilt-layout on one PDF, return the full analysis result as dict."""
    pdf_bytes = src.download_blob(blob_name).readall()
    poller = DI.begin_analyze_document(
        model_id="prebuilt-layout",
        body=pdf_bytes, # type: ignore
    ) # type: ignore
    result = poller.result()
    # `result` is an AnalyzeResult object; .as_dict() gives the full JSON
    return result.as_dict()


def result_to_plain_text(result: dict) -> str:
    """
    Convert DI output to a human-readable text representation.
    Tables are rendered as Markdown-style pipes so downstream chunking
    preserves row/column semantics.
    """
    lines = []
    # Document layout: iterate pages in order
    for page_no, page in enumerate(result.get("pages", []), start=1):
        lines.append(f"\n=== Page {page_no} ===\n")
        # Extract lines on this page in reading order
        for line in page.get("lines", []):
            txt = line.get("content", "").strip()
            if txt:
                lines.append(txt)
        # Append any tables that start on this page
        for table in result.get("tables", []):
            bbox = table.get("boundingRegions", [])
            page_hits = [b.get("pageNumber") for b in bbox]
            if page_no not in page_hits:
                continue
            lines.append("\n[TABLE]")
            for row in range(table["rowCount"]):
                cells = [c for c in table["cells"] if c["rowIndex"] == row]
                cells.sort(key=lambda c: c["columnIndex"])
                lines.append(" | ".join(c.get("content", "").strip() for c in cells))
            lines.append("[/TABLE]\n")
    return "\n".join(lines)


pdfs = [b.name for b in src.list_blobs() if b.name.lower().endswith(".pdf")]
print(f"Found {len(pdfs)} PDFs to parse.\n")

for i, name in enumerate(sorted(pdfs), start=1):
    print(f"[{i}/{len(pdfs)}] Parsing {name} ...")
    try:
        result = analyze_pdf(name)
        plain = result_to_plain_text(result)

        # Save full DI JSON
        json_blob = f"{Path(name).stem}.json"
        out.upload_blob(
            name=json_blob,
            data=json.dumps(result, indent=2, ensure_ascii=False).encode("utf-8"),
            overwrite=True,
            content_type="application/json",
        )

        # Save flattened text (easier to chunk in Phase 3)
        txt_blob = f"{Path(name).stem}.txt"
        out.upload_blob(
            name=txt_blob,
            data=plain.encode("utf-8"),
            overwrite=True,
            content_type="text/plain; charset=utf-8",
        )

        n_pages = len(result.get("pages", []))
        n_tables = len(result.get("tables", []))
        print(f"   ✓ {n_pages} page(s), {n_tables} table(s), {len(plain):,} chars text")
    except Exception as e:
        print(f"   ❌ FAILED: {e}")

print("\n✅ Parsing complete.")