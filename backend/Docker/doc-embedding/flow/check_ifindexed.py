
from promptflow.core import tool
from promptflow.connections import CustomConnection
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def list_policy_tool(filename:str, ally: CustomConnection) -> object:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_document_index
    search_key = ally.search_key
    # use ai azure search to query 

    search_client = SearchClient(search_endpoint, search_index, AzureKeyCredential(search_key))
    file_filter = "filename eq '{}'".format(filename)
    filter = "({})".format(file_filter)   # Note this filter does no take the group into account

    results = search_client.search(
        select="filename",     # Specify the fields to include in the results
        filter=filter,
        include_total_count=True # Include the total count of documents in the results
    )


    # policy_list = []
    # for result in results:
    #     policy_list.append({"filename": result["filename"]})

    count = results.get_count()

    if count == 0:
        return 0 # not indexed
    else:
        return 1 # indexed