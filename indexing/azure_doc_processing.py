import os
import uuid
import json
import datetime
from docx import Document
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SearchIndex, SimpleField, SearchableField, SearchField,
    SearchFieldDataType, VectorSearch, HnswAlgorithmConfiguration,
    HnswParameters, VectorSearchProfile, VectorSearchAlgorithmKind,
    VectorSearchAlgorithmMetric
)
from openai import AzureOpenAI

# ----------------------------- Configuration -----------------------------
AZURE_SEARCH_ENDPOINT = "https://.search.windows.net"
AZURE_SEARCH_KEY = ""
INDEX_NAME = "legal-documents"

AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = "https://.openai.azure.com/"
AZURE_OPENAI_DEPLOYMENT = "gpt-4o"
AZURE_EMBEDDING_DEPLOYMENT = "text-embedding-ada-002"

DOCUMENT_FOLDER = os.path.abspath("contract_documents")  # Use absolute path

# ----------------------------- GPT Prompt -----------------------------
SYSTEM_PROMPT = """
You are a legal document analysis assistant tasked with reading a formal contract or legal agreement.

Carefully extract the following structured fields in strict JSON format only, no explanations:

{
  "title": "Descriptive title of the document",
  "keyphrases": ["phrase1", "phrase2", "phrase3"],
  "summary": "Concise summary of the document or clause",
  "isCompliant": true,
  "CompliantCollection": ["Policy1", "Policy2"],
  "NonCompliantCollection": ["Policy3"]
}
"""

# ----------------------------- Create Index -----------------------------
def create_index_if_not_exists():
    index_client = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
    if INDEX_NAME in [idx.name for idx in index_client.list_indexes()]:
        print(f"Index '{INDEX_NAME}' already exists.")
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, sortable=True),
        SearchableField(name="title", type=SearchFieldDataType.String),
        SearchableField(name="paragraph", type=SearchFieldDataType.String),
        SimpleField(name="ParagraphId", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchField(name="keyphrases", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchableField(name="summary", type=SearchFieldDataType.String),
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=1536, vector_search_profile_name="myHnswProfile"),
        SimpleField(name="filename", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="department", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="date", type=SearchFieldDataType.DateTimeOffset, filterable=True),
        SearchField(name="group", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
        SimpleField(name="isCompliant", type=SearchFieldDataType.Boolean, filterable=True),
        SearchField(name="CompliantCollection", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
        SearchField(name="NonCompliantCollection", type=SearchFieldDataType.Collection(SearchFieldDataType.String)),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters=HnswParameters(m=4, ef_construction=250, ef_search=100, metric=VectorSearchAlgorithmMetric.COSINE)
            )
        ],
        profiles=[VectorSearchProfile(name="myHnswProfile", algorithm_configuration_name="myHnsw")]
    )

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_index(index)
    print(f"Index '{INDEX_NAME}' created successfully.")

# ----------------------------- GPT & Embedding -----------------------------
def extract_metadata_with_gpt(text):
    client = AzureOpenAI(api_key=AZURE_OPENAI_API_KEY, api_version="2023-05-15", azure_endpoint=AZURE_OPENAI_ENDPOINT)
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.2
    )
    return json.loads(response.choices[0].message.content)

def get_embedding(text):
    client = AzureOpenAI(api_key=AZURE_OPENAI_API_KEY, api_version="2023-05-15", azure_endpoint=AZURE_OPENAI_ENDPOINT)
    result = client.embeddings.create(model=AZURE_EMBEDDING_DEPLOYMENT, input=[text])
    return result.data[0].embedding

# ----------------------------- Upload to Azure Search -----------------------------
def upload_paragraph_to_index(file_name, paragraph, metadata, embedding, paragraph_id):
    search_client = SearchClient(endpoint=AZURE_SEARCH_ENDPOINT, index_name=INDEX_NAME, credential=AzureKeyCredential(AZURE_SEARCH_KEY))
    doc = {
        "id": str(uuid.uuid4()),
        "title": metadata["title"],
        "paragraph": paragraph,
        "ParagraphId": paragraph_id,
        "keyphrases": metadata.get("keyphrases", []),
        "summary": metadata["summary"],
        "embedding": embedding,
        "filename": file_name,
        "department": "Legal",
        "date": datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat(),
        "group": [],
        "isCompliant": metadata["isCompliant"],
        "CompliantCollection": metadata.get("CompliantCollection", []),
        "NonCompliantCollection": metadata.get("NonCompliantCollection", [])
    }
    result = search_client.upload_documents(documents=[doc])
    print(f"Uploaded document for: {file_name} | ParagraphId: {paragraph_id} | Status: {result[0].status_code}")

# ----------------------------- Main -----------------------------
def process_all_documents():
    print("📁 Current working directory:", os.getcwd())
    create_index_if_not_exists()

    for filename in os.listdir(DOCUMENT_FOLDER):
        if filename.endswith(".docx"):
            path = os.path.join(DOCUMENT_FOLDER, filename)

            if not os.path.exists(path):
                print(f"❌ File not found: {path}")
                continue

            print(f"✅ Processing: {filename}")
            try:
                document = Document(path)
            except Exception as e:
                print(f"❌ Failed to load Word document: {filename} | Error: {e}")
                continue

            paragraph_id = 1
            for para in document.paragraphs:
                if para.text.strip():
                    try:
                        paragraph_text = para.text.strip()
                        metadata = extract_metadata_with_gpt(paragraph_text)
                        embedding = get_embedding(paragraph_text)
                        upload_paragraph_to_index(filename, paragraph_text, metadata, embedding, paragraph_id)
                        paragraph_id += 1
                    except Exception as e:
                        print(f"❌ Error processing paragraph {paragraph_id} in {filename}: {e}")

if __name__ == "__main__":
    process_all_documents()
