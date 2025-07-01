import uuid
import json
import os
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

# -----------------------------
# Azure Search Configuration
# -----------------------------
AZURE_SEARCH_ENDPOINT = ""
AZURE_SEARCH_KEY = ""
INDEX_NAME = "legal-instructions"

# -----------------------------
# Azure OpenAI Configuration
# -----------------------------
AZURE_OPENAI_API_KEY = ""
AZURE_OPENAI_ENDPOINT = ""
AZURE_OPENAI_DEPLOYMENT = "gpt4o"
AZURE_EMBEDDING_DEPLOYMENT = "ada002"
AZURE_API_VERSION = "2023-05-15"

# -----------------------------
# System Prompt
# -----------------------------
SYSTEM_PROMPT = """
You are a legal document analysis assistant tasked with reading a formal policy document.
Your role is to extract structured data that will be used as a reference to verify legal contracts against these policy instructions.

Carefully analyze the content and extract the following fields in strict JSON format only, without any commentary or explanation:

{
    "title": "Descriptive title of the policy",
    "instruction": "Concise but complete description of the core policy directive or rule",
    "tags": ["keyword1", "keyword2", "keyword3"],
    "severity": 1
}

Guidelines:
- "title": Extract a clear and descriptive name for the policy.
- "instruction": Extract the key instruction, rule, or mandate this policy enforces.
- "tags": Provide 2 to 3 relevant, general-purpose keywords.
- "severity": Use 1 for Critical, 2 for Warning.
"""

# -----------------------------
# Create Azure Search Index
# -----------------------------
def create_index_if_not_exists():
    index_client = SearchIndexClient(endpoint=AZURE_SEARCH_ENDPOINT, credential=AzureKeyCredential(AZURE_SEARCH_KEY))

    if INDEX_NAME in [i.name for i in index_client.list_indexes()]:
        print(f"Index '{INDEX_NAME}' already exists.")
        return

    fields = [
        SimpleField(name="id", type=SearchFieldDataType.String, key=True, sortable=True),
        SimpleField(name="PolicyId", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="title", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="instruction", type=SearchFieldDataType.String),
        SearchField(name="embedding", type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
                    searchable=True, vector_search_dimensions=1536, vector_search_profile_name="myHnswProfile"),
        SearchField(name="tags", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True, facetable=True),
        SimpleField(name="locked", type=SearchFieldDataType.Boolean, filterable=True),
        SearchField(name="groups", type=SearchFieldDataType.Collection(SearchFieldDataType.String), filterable=True),
        SimpleField(name="severity", type=SearchFieldDataType.Int32, filterable=True),
        SimpleField(name="language", type=SearchFieldDataType.String, filterable=True),  # ✅ New field
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="myHnsw",
                kind=VectorSearchAlgorithmKind.HNSW,
                parameters=HnswParameters(m=5, ef_construction=300, ef_search=400, metric=VectorSearchAlgorithmMetric.COSINE),
            )
        ],
        profiles=[
            VectorSearchProfile(name="myHnswProfile", algorithm_configuration_name="myHnsw"),
        ],
    )

    index = SearchIndex(name=INDEX_NAME, fields=fields, vector_search=vector_search)
    index_client.create_index(index)
    print(f"Index '{INDEX_NAME}' created successfully.")

# -----------------------------
# Read Word Document
# -----------------------------
def extract_text_from_docx(file_path):
    doc = Document(file_path)
    return "\n".join([p.text.strip() for p in doc.paragraphs if p.text.strip()])

# -----------------------------
# Detect Language with OpenAI
# -----------------------------
def detect_language(text):
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )

    prompt = f"""
Identify the language of the following text. Respond only with 'English' or 'German'. No extra text.

Text:
\"\"\"{text}\"\"\"
"""
    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": "You detect the language of legal text."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    language = response.choices[0].message.content.strip()
    return "German" if "German" in language else "English"

# -----------------------------
# Analyze Text with Azure OpenAI
# -----------------------------
def analyze_text_with_openai(text):
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )

    response = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text}
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        print("GPT output is not valid JSON:\n", content)
        raise

# -----------------------------
# Get Embedding for Instruction
# -----------------------------
def get_embedding(text):
    client = AzureOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_API_VERSION,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
    )
    response = client.embeddings.create(
        model=AZURE_EMBEDDING_DEPLOYMENT,
        input=[text]
    )
    return response.data[0].embedding

# -----------------------------
# Upload to Azure Search
# -----------------------------
def upload_to_search(data, embedding, language):
    search_client = SearchClient(
        endpoint=AZURE_SEARCH_ENDPOINT,
        index_name=INDEX_NAME,
        credential=AzureKeyCredential(AZURE_SEARCH_KEY)
    )
    id = str(uuid.uuid4())
    doc = {
        "id": id,
        "PolicyId": id,
        "title": data["title"],
        "instruction": data["instruction"],
        "embedding": embedding,
        "tags": data["tags"],
        "locked": False,
        "groups": [],
        "severity": data["severity"],
        "language": language
    }

    result = search_client.upload_documents(documents=[doc])
    print("Document uploaded:", result)

# -----------------------------
# Main Execution
# -----------------------------


if __name__ == "__main__":
    create_index_if_not_exists()

    # Get absolute path to policy_document folder relative to this script
    base_dir = os.path.dirname(__file__)  # Path to indexing/
    folder_path = os.path.join(base_dir, "..", "policy_document")

    for filename in os.listdir(folder_path):
        if filename.endswith(".docx"):
            docx_path = os.path.join(folder_path, filename)
            print(f"Processing: {docx_path}")

            # Extract -> Detect Language -> Analyze -> Embed -> Upload
            text = extract_text_from_docx(docx_path)
            language = detect_language(text)
            structured_data = analyze_text_with_openai(text)
            embedding = get_embedding(structured_data["instruction"])
            upload_to_search(structured_data, embedding, language)