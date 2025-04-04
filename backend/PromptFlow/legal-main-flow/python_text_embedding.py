from promptflow.core import tool
from openai import AzureOpenAI
from promptflow.connections import CustomConnection

@tool
def my_python_tool(input: str, ally: CustomConnection,) -> object:
    client = AzureOpenAI(  
        azure_endpoint=ally.openai_endpoint,  
        api_key=ally.openai_key,  
        api_version=ally.openai_api_version,
    )

    system_prompt='''You are a legal assistant who is an expert in revising legal documents. You will be provided with the user's question about a legal document.
    You task is to provide a list of the 3 best search intents derived from the user's question. Format your answer as a comma separated list of search intents.'''
    
    user_promt = input
    openai_response = client.chat.completions.create(  
        model=ally.openai_model_deployment,  
        messages=[  
            {"role": "system", "content": system_prompt},  
            {"role": "user", "content": user_promt},  
        ]
    )
    try:  
        openai_sentiment_response_post_text = openai_response.choices[0].message.content
        print(f"OpenAI response: {openai_sentiment_response_post_text}")
    except Exception as e:  
        print(f"Error converting to JSON sentiment from OpenAI: {e}")
        return e

    response =  client.embeddings.create(input = openai_sentiment_response_post_text, model=ally.openai_embedding_deployment).data[0].embedding
    
    return response
