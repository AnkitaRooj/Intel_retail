from azure.storage.blob import BlobServiceClient
import os
from dotenv import load_dotenv

load_dotenv()
blob = BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING'])
print('Structured:', [b.name for b in blob.get_container_client('structured-data').list_blobs()])
print('Unstructured:', [b.name for b in blob.get_container_client('unstructured-docs').list_blobs()])