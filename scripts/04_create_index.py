"""
Creates the retail-intelligence index in Azure AI Search.
Schema is designed for enterprise hybrid search:
  - BM25 (searchable text fields)
  - Vector (3072-d embeddings via text-embedding-3-large)
  - Semantic ranker (title + content + keyword fields)
  - Rich filterable facets (doc_type, category, account, supplier, topic)
Idempotent: deletes and recreates if it already exists.
"""
import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SimpleField,
    SearchableField,
    SearchFieldDataType,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
)

load_dotenv()

INDEX_NAME = os.environ["AZURE_SEARCH_INDEX_NAME"]
EMBEDDING_DIMS = 3072  # text-embedding-3-large

client = SearchIndexClient(
    endpoint=os.environ["AZURE_SEARCH_ENDPOINT"],
    credential=AzureKeyCredential(os.environ["AZURE_SEARCH_ADMIN_KEY"]),
)

# ---------- Fields ----------
fields = [
    SimpleField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),

    # The chunk text itself (BM25 searchable)
    SearchableField(
        name="content",
        type=SearchFieldDataType.String,
        analyzer_name="en.lucene",
    ),

    # Vector embedding (Hybrid search)
    SearchField(
        name="content_vector",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        searchable=True,
        vector_search_dimensions=EMBEDDING_DIMS,
        vector_search_profile_name="default-vector-profile",
    ),

    # Metadata (all filterable + facetable for category-manager slicing)
    SimpleField(name="title",          type=SearchFieldDataType.String, filterable=True, facetable=True, searchable=True),
    SimpleField(name="source_document", type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="doc_type",        type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="category",        type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="account",         type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="supplier",        type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="topic",           type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="chunk_type",      type=SearchFieldDataType.String, filterable=True, facetable=True),
    SimpleField(name="page_number",     type=SearchFieldDataType.Int32,  filterable=True, sortable=True),
    SimpleField(name="chunk_index",     type=SearchFieldDataType.Int32,  filterable=True, sortable=True),
    SimpleField(name="token_count",     type=SearchFieldDataType.Int32,  filterable=True, sortable=True),
]

# ---------- Vector search config (HNSW) ----------
vector_search = VectorSearch(
    algorithms=[
        HnswAlgorithmConfiguration(
            name="default-hnsw",
            parameters=HnswParameters(
                m=4,
                ef_construction=400,
                ef_search=500,
                metric="cosine",
            ),
        )
    ],
    profiles=[
        VectorSearchProfile(
            name="default-vector-profile",
            algorithm_configuration_name="default-hnsw",
        )
    ],
)

# ---------- Semantic ranker config ----------
semantic_config = SemanticConfiguration(
    name="default-semantic",
    prioritized_fields=SemanticPrioritizedFields(
        title_field=SemanticField(field_name="title"),
        content_fields=[SemanticField(field_name="content")],
        keywords_fields=[
            SemanticField(field_name="category"),
            SemanticField(field_name="account"),
            SemanticField(field_name="doc_type"),
        ],
    ),
)

index = SearchIndex(
    name=INDEX_NAME,
    fields=fields,
    vector_search=vector_search,
    semantic_search=SemanticSearch(configurations=[semantic_config]),
)

# ---------- Create (delete if exists) ----------
existing = [i.name for i in client.list_indexes()]
if INDEX_NAME in existing:
    print(f"⚠️  Index '{INDEX_NAME}' already exists → deleting for clean recreate.")
    client.delete_index(INDEX_NAME)

print(f"▶ Creating index '{INDEX_NAME}' with {len(fields)} fields ...")
client.create_index(index)
print(f"✅ Index created: {INDEX_NAME}")
print(f"   Vector dims     : {EMBEDDING_DIMS}")
print(f"   Semantic config : default-semantic")
print(f"   HNSW params     : m=4, efC=400, efS=500, cosine")