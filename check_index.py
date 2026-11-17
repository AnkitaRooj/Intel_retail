"""
Inspects Azure AI Search indexes directly using the SearchIndexClient.
"""
import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient

load_dotenv()

# Initialize the Search Index Client using environment variables
client = SearchIndexClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)

print(f"🔍 Connecting to Search Service: {os.environ['AZURE_SEARCH_ENDPOINT']}")
print(f"🎯 Target Index: {os.environ['AZURE_SEARCH_INDEX_NAME']}\n")

try:
    # List all indexes on the service
    indexes = list(client.list_indexes())
    print(f"Found {len(indexes)} index(es) on this service:")
    for idx in indexes:
        print(f"   - {idx.name}")

    # Inspect specific index details if it exists
    target_index_name = os.environ["AZURE_SEARCH_INDEX_NAME"]
    if target_index_name in [idx.name for idx in indexes]:
        index_def = client.get_index(target_index_name)
        print(f"\n✅ Successfully retrieved index definition for '{target_index_name}':")
        print(f"   Total Fields Configured : {len(index_def.fields)}")
        print(f"   Semantic Configurations : {[c.name for c in index_def.semantic_search.configurations] if index_def.semantic_search else 'None'}")
    else:
        print(f"\n⚠️  Index '{target_index_name}' does not exist yet. Run your 04_create_index.py script to create it.")

except Exception as e:
    print(f"\n❌ Error connecting to Azure AI Search: {e}")