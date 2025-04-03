
from promptflow.core import tool
from promptflow.connections import CustomConnection
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from openai import AzureOpenAI
import datetime


# The inputs section will change based on the arguments of the tool function, after you save the code
# Adding type to arguments and return value will help the system show the types properly
# Please update the function name/signature per need
@tool
def my_python_tool(filename: str, input: list, ally: CustomConnection) -> list:
    search_endpoint = ally.search_endpoint
    search_index = ally.search_document_index
    search_key = ally.search_key

    # Create a client
    credential = AzureKeyCredential(search_key)
    search_client = SearchClient(endpoint=search_endpoint,
                        index_name=search_index,
                        credential=credential)

    client = AzureOpenAI(  
        azure_endpoint=ally.openai_endpoint,  
        api_key=ally.openai_key,  
        api_version=ally.openai_api_version
    )

    def text_embeding(text):
        import json
        response  = client.embeddings.create(
                input = text,
                model = ally.openai_embedding_deployment       
        )
        json_data = json.loads(response.model_dump_json())
        return json_data['data'][0]['embedding']
        
    # for each item in input
    for item in input['chunks']:
        # add new field to item
        item['id'] = filename.strip().split(sep='.')[0] + "-" + str(item['id'])
        item['embedding'] = text_embeding(item['paragraph'])
        item['filename'] = filename
        # now in 2024-04-14T06:35:05Z format 
        item['date'] = datetime.datetime.now(tz=datetime.timezone.utc).isoformat()
        # Leave the properties below empty for now as functionality is not implemented
        item['department'] = ""
        item['group'] = []
        item['isCompliant'] = False
        item['CompliantCollection'] = []
        item['NonCompliantCollection'] = []

    try:
        search_client.upload_documents(documents = input['chunks'])
    except Exception as e:
        print(f"Error documents to search index {search_index}: {e}")
        return

    return filename
