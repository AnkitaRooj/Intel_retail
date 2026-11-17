import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
load_dotenv()
s = SearchClient(endpoint=os.environ['AZURE_SEARCH_ENDPOINT'],
                 index_name=os.environ['AZURE_SEARCH_INDEX_NAME'],
                 credential=AzureKeyCredential(os.environ['AZURE_SEARCH_ADMIN_KEY']))
r = s.search('Migros promotional ROI feature display', top=3, select=['title','doc_type','page_number','content'])
for hit in r:
    print(f"  [{hit['doc_type']} p{hit['page_number']}] {hit['title']}")
    print(f"     {hit['content'][:180]}...")

print('Total docs in index:', s.get_document_count())