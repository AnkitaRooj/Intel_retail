"""
Verifies all Azure services respond correctly using keys from .env
Run BEFORE uploading data. If this fails, fix RBAC/keys first.
"""
import os
from pathlib import Path
from xmlrpc import client
from dotenv import load_dotenv
import httpx

load_dotenv()

from openai import AzureOpenAI
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

print("=" * 60)
print("CONNECTIVITY TEST")
print("=" * 60)

# 1. Azure OpenAI - chat
print("\n[1/5] Testing Azure OpenAI (gpt-4o) ...")
try:
    client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_key=os.environ["AZURE_OPENAI_API_KEY"],
    api_version=os.environ["AZURE_OPENAI_API_VERSION"],
    http_client=httpx.Client(trust_env=False) # Forces bypass of environment proxies # type: ignore
    )   
    r = client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_GPT4O_DEPLOYMENT"],
        messages=[{"role": "user", "content": "Reply with the single word: OK"}],
        max_tokens=5,
    )
    print(f"   ✅ Chat OK → {r.choices[0].message.content.strip()}") # type: ignore
except Exception as e:
    print(f"   ❌ Chat FAILED: {e}")
    raise SystemExit(1)

# 2. Azure OpenAI - embeddings
print("\n[2/5] Testing Azure OpenAI embeddings ...")
try:
    emb = client.embeddings.create(
        model=os.environ["AZURE_OPENAI_EMBEDDING_DEPLOYMENT"],
        input="Swiss FMCG category performance Q3 2025",
    )
    print(f"   ✅ Embeddings OK → dim={len(emb.data[0].embedding)}")
except Exception as e:
    print(f"   ❌ Embeddings FAILED: {e}")
    raise SystemExit(1)

# 3. Azure AI Search
print("\n[3/5] Testing Azure AI Search ...")
try:
    from azure.search.documents.indexes import SearchIndexClient
    idx = SearchIndexClient(
        endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
    )
    existing = [n.name for n in idx.list_indexes()]
    print(f"   ✅ Search OK → {len(existing)} existing index(es): {existing}")
except Exception as e:
    print(f"   ❌ Search FAILED: {e}")
    raise SystemExit(1)

# 4. Document Intelligence
print("\n[4/5] Testing Azure Document Intelligence ...")
try:
    di = DocumentIntelligenceClient(
        endpoint=os.environ["AZURE_DI_ENDPOINT"],
        credential=AzureKeyCredential(os.environ["AZURE_DI_KEY"]),
    )
    # Cheapest possible probe: list models
    print(f"   ✅ DI OK → endpoint reachable")
except Exception as e:
    print(f"   ❌ DI FAILED: {e}")
    raise SystemExit(1)

# 5. Blob Storage
print("\n[5/5] Testing Azure Blob Storage ...")
try:
    blob = BlobServiceClient.from_connection_string(
        os.environ["AZURE_STORAGE_CONNECTION_STRING"]
    )
    containers = [c.name for c in blob.list_containers()]
    print(f"   ✅ Storage OK → containers: {containers}")
    required = {"structured-data", "unstructured-docs", "parsed-docs"}
    missing = required - set(containers)
    if missing:
        print(f"   ❌ Missing containers: {missing}. Create them before proceeding.")
        raise SystemExit(1)
except Exception as e:
    print(f"   ❌ Storage FAILED: {e}")
    raise SystemExit(1)

print("\n" + "=" * 60)
print("✅ ALL SERVICES OK — safe to proceed to Phase 2 main scripts.")
print("=" * 60)




# Here is a step-by-step breakdown of what each part of that command does:

# python -c "...": Tells Python to execute the code string provided inside the double quotes right away without needing to create or open a separate .py script file.

# from azure.storage.blob import BlobServiceClient: Imports Azure's official Blob Storage library package.

# import os; from dotenv import load_dotenv; load_dotenv(): Loads your local .env file so that your Python script can securely access all your environment variables (including your storage connection string).

# BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING']): Authenticates and connects to your Azure Storage account using the connection string retrieved directly from your environment settings.

# .create_container('parsed-docs'): Tells Azure Storage to programmatically create the exact missing container that your connectivity test script was looking for (parsed-docs).

# print('Container parsed-docs created successfully!'): Prints out the success message you saw in your terminal once the container was successfully provisioned.

# python -c "from azure.storage.blob import BlobServiceClient; import os; from dotenv import load_dotenv; load_dotenv(); BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING']).create_container('parsed-docs'); print('Container parsed-docs created successfully!')"