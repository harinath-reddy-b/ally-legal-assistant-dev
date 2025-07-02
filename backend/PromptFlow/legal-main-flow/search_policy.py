from promptflow.core import tool
from promptflow.connections import CustomConnection
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery
from openai import AzureOpenAI
import json

@tool
def list_policy_tool(query: str, embeding: list, searchconnection: CustomConnection, groups: list) -> object:
    search_endpoint = searchconnection.search_endpoint
    search_index = searchconnection.search_policy_index
    search_key = searchconnection.search_key    

    # 1. Call OpenAI to detect language
    client = AzureOpenAI(
        azure_endpoint=searchconnection.openai_endpoint,
        api_key=searchconnection.openai_key,
        api_version=searchconnection.openai_api_version
    )

    prompt = f"""
You are a language detection assistant. Identify the language of the following text and respond with only the language name: 'English' or 'German'. No extra text.

Text:
\"{query}\"
    """

    try:
        openai_response = client.chat.completions.create(
            model=searchconnection.openai_model_deployment,
            messages=[
                {"role": "system", "content": "You detect the language of the given user input."},
                {"role": "user", "content": prompt},
            ]
        )

        language = openai_response.choices[0].message.content.strip()
        print(f"Detected language: {language}")
    except Exception as e:
        print(f"Language detection failed, defaulting to English. Error: {e}")
        language = "English"

    # 2. Build language filter
    if language == "German":
        language_filter = "language eq 'German'"
    else:
        language_filter = "language eq 'English'"

    # 3. Optional group filtering (you can extend this if needed)
    # group_filter = "adgroup/any(t: search.in(t, '{}'))".format(','.join(groups))
    # combined_filter = f"({language_filter}) and ({group_filter})"

    vector_query = VectorizedQuery(kind="vector", vector=embeding, k_nearest_neighbors=1, fields="embedding")     

    search_client = SearchClient(search_endpoint, search_index, AzureKeyCredential(search_key))

    results = search_client.search(
        search_text=query,
        filter=language_filter,
        vector_queries=[vector_query],
        select="title,instruction"
    )

    policy_list = []
    for result in results:
        policy_list.append({
            "title": result["title"],
            "instruction": result["instruction"]
        })

    return policy_list