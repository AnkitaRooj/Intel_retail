from azure.storage.blob import BlobServiceClient
import os
from dotenv import load_dotenv; load_dotenv()
blob = BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING'])
print([b.name for b in blob.get_container_client('parsed-docs').list_blobs()])

c=0
for b in blob.get_container_client('parsed-docs').list_blobs():
    if b.name:
        c+=1

print("Total parsed-docs blobs:", c)


# from azure.storage.blob import BlobServiceClient
# import os
# from dotenv import load_dotenv
# load_dotenv()
blob_service = BlobServiceClient.from_connection_string(os.environ['AZURE_STORAGE_CONNECTION_STRING'])
blob_client = blob_service.get_blob_client(container='parsed-docs', blob='01_Category_Report_Beverages_Q3-2025.txt')
with open('check.txt', 'wb') as f: f.write(blob_client.download_blob().readall())
print('Downloaded successfully to check.txt')