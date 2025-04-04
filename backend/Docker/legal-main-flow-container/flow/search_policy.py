from promptflow.core import tool
from promptflow.connections import CustomConnection
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery


@tool
def list_policy_tool(
    query: str, embeding: list, ally: CustomConnection, groups: list
) -> object:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_policy_index
    search_key = ally.search_key

    vector_query = VectorizedQuery(
        kind="vector", vector=embeding, k_nearest_neighbors=10, fields="embeding"
    )

    search_client = SearchClient(
        search_endpoint, search_index, AzureKeyCredential(search_key)
    )
    # print the param groups type
    print(type(groups))
    # convert list to string
    groupssplit = ",".join(groups)

    group_filter = "adgroup/any(t: search.in(t, '{}'))".format(groupssplit)
    results = search_client.search(
        search_text=query,  # Use '*' to match all documents
        filter=group_filter,
        vector_queries=[vector_query],
        select="title,instruction",  # Specify the fields to include in the results
    )
    policy_list = []
    for result in results:
        policy_list.append(
            {"title": result["title"], "instruction": result["instruction"]}
        )
    
    # This is temporary code to return a static list of policies
    # until the search function is implemented.
    policy_list = [
        {
            "title": "Scope of Work and Exclusions",
            "instruction": "Clearly define the work included and explicitly list what’s excluded or considered optional. This protects against scope creep and misaligned expectations.",
        },
        {
            "title": "Roles, Responsibilities, and Availability",
            "instruction": "Assign clear roles on both sides, including availability expectations (e.g., response times, validation delays). Clarify customer obligations (e.g., providing access, decision-makers).",
        },
        {
            "title": "Project Milestones and Delay Handling",
            "instruction": "Define project milestones, planning assumptions, and what happens in case of delays (especially customer-side). Include rules for pausing/resuming the project, and how timeframes are recalculated.",
        },
        {
            "title": "Billing, Payments, and Expenses",
            "instruction": "Describe the billing model (T&M, fixed price, capped), invoicing frequency, payment terms (e.g., 30 days net), and rules around travel or additional expenses.",
        },
        {
            "title": "Change Management Process",
            "instruction": "Detail how changes to scope, budget, or timeline are handled — through formal change requests, estimation, approval, and documented agreement.",
        },
    ]

    return policy_list
