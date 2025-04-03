from promptflow.core import tool
from promptflow.connections import CustomConnection
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

@tool
def search_doc_tool(query: str, embedinginput: list, ally: CustomConnection, filename: str, groups: str) -> object:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_document_index
    search_key = ally.search_key

    vector_query = VectorizedQuery(kind="vector", vector=embedinginput, k_nearest_neighbors=50, fields="embedding", exhaustive=True)

    search_client = SearchClient(search_endpoint, search_index, AzureKeyCredential(search_key))
    file_filter = "filename eq '{}'".format(filename)
    # Add the group filter only if SSO enabled
    #group_filter = "group/any(t: search.in(t, '{}'))".format(groups)
    # combine the filter
    #filter = "({}) and ({})".format(file_filter, group_filter)
    filter = "({})".format(file_filter)   # Note this filter does no take the group into account

    results = search_client.search(
        search_text=query,  # Use the text query
        filter=filter,
        vector_queries=[vector_query],
        select="*",  # Include the fields in the result
        top=10,  # Increase the number of results returned
    )
    policy_list = []
    for result in results:
        policy_list.append({"title": result["title"], "paragraph": result["paragraph"], "keyphrases": result["keyphrases"], "summary": result["summary"]})

    return policy_list