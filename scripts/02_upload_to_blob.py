"""
Uploads structured CSVs and unstructured PDFs from local data/ to Blob Storage.
Idempotent: overwrites if already present.
"""
import os
from pathlib import Path
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient, ContentSettings

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
BLOB = BlobServiceClient.from_connection_string(
    os.environ["AZURE_STORAGE_CONNECTION_STRING"]
)

def upload_folder(local_dir: Path, container: str, content_type: str):
    cc = BLOB.get_container_client(container)
    files = sorted(local_dir.glob("*"))
    if not files:
        print(f"⚠️  No files in {local_dir}")
        return
    print(f"\n📤 Uploading {len(files)} file(s) from {local_dir.name}/ → {container}/")
    for f in files:
        if f.suffix.lower() not in (".csv", ".pdf"):
            continue
        with open(f, "rb") as fh:
            cc.upload_blob(
                name=f.name,
                data=fh,
                overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        print(f"   ✓ {f.name}  ({f.stat().st_size / 1024:.1f} KB)")

upload_folder(ROOT / "data" / "structured",  "structured-data",  "text/csv")
upload_folder(ROOT / "data" / "unstructured", "unstructured-docs", "application/pdf")

print("\n✅ Upload complete.")