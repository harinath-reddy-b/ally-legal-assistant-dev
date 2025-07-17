from promptflow.core import tool
from promptflow.connections import AzureOpenAIConnection, CustomConnection
from pydantic import BaseModel 
from openai import AzureOpenAI
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
from typing import List, Optional   # import Optional
import json
import time
import logging

class SummaryResponse(BaseModel):  
    class Item(BaseModel):  
        title: str
        summary: str
        notes: str
        original_text: str
        keyItems: List[str]

    Summary: str
    KeyPoints: List[str]
    Items: List[Item]


@tool
def python_tool(input_text: str, filename: str, ally: CustomConnection) -> List[dict]:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_document_index
    search_key = ally.search_key

    search_client = SearchClient(search_endpoint, search_index, AzureKeyCredential(search_key))
    results = search_client.search(
        search_text="*",
        filter=f"filename eq '{filename}'",
        order_by=["ParagraphId"],
    )

    out_list = []
    for result in results:
        entry = {
            "title": result.get("title"),
            "summary": result.get("summary"),
            "keyphrases": result.get("keyphrases", []),
            "isCompliant": result.get("isCompliant", True),
            "CompliantCollection": result.get("CompliantCollection", []),
            "NonCompliantCollection": result.get("NonCompliantCollection", []),
        }

        if not entry["isCompliant"]:
            policylist = []
            for policyid in entry["NonCompliantCollection"]:
                policy = get_policyinfo(policyid, ally)
                if policy is None:
                    logging.warning(f"No policy info found for ID {policyid}")
                    continue
                policylist.append(policy)
            entry["NonCompliantPolicies"] = policylist

        out_list.append(entry)

    return out_list


def get_policyinfo(policyid: int, ally: CustomConnection) -> Optional[dict]:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_policy_index
    search_key = ally.search_key

    search_client = SearchClient(search_endpoint, search_index, AzureKeyCredential(search_key))
    results = search_client.search(
        filter=f"PolicyId eq '{policyid}'",
        select="id,title,instruction,tags,severity"
    )

    results_list = [r for r in results]
    if not results_list:
        return None
    # convert the first result (SearchDocument) into a plain dict
    return dict(results_list[0])
