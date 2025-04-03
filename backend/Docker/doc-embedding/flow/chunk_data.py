from promptflow.core import tool
from promptflow.connections import CustomConnection
from pydantic import BaseModel
from openai import AzureOpenAI
from typing import List
import json


class Chunk(BaseModel):
    id: str
    title: str
    paragraph: str
    keyphrases: List[str]
    summary: str


class Document(BaseModel):
    chunks: List[Chunk]


@tool
def python_tool(body_text: str, ally: CustomConnection) -> object:
    client = AzureOpenAI(
        azure_endpoint=ally.openai_endpoint,
        api_key=ally.openai_key,
        api_version=ally.openai_api_version,
    )

    # Provide the answer and translate the search results into the same language as the user's question.
    prompt = """
You are a legal document processor. Your task is to break a provided legal document into manageable chunks, either by paragraphs or clauses depending on the context. The output must be in JSON format. Each chunk should include an ID, title, text, key phrases, and a summary. Key phrases should emphasize dates, names, and the most important information in the context of the document. Use the following JSON structure as a template:  

```json
{
    "chunks": [
        {
            "id": "string",
            "title": "string",
            "paragraph": "string",
            "keyphrases": ["string"],
            "summary": "string"
        }
    ]
}
```

### Instructions:
1. **Chunking Rules:**
   - Break the text into chunks by paragraph if the paragraphs are short and self-contained.
   - Break by clause if the paragraphs are long or contain multiple legal provisions.

2. **For Each Chunk:**
   - **ID:** Assign a unique numeric ID starting from "1" and incrementing for each chunk.
   - **Title:** Extract or summarize the main subject of the paragraph or clause. If not explicitly stated, infer a short, descriptive title.
   - **Paragraph:** Include the full text of the paragraph or clause.
   - **Key Phrases:** Extract the most relevant terms or phrases. Focus on:
     - Dates
     - Names (people, organizations, places)
     - Critical terms or keywords related to the legal content
   - **Summary:** Write a concise summary of the paragraph or clause.

3. **Output:** 
   - Provide the output as valid JSON.
   - Ensure the structure is consistent with the provided template.

### Example Output:  
```json
{
    "chunks": [
        {
            "id": "1",
            "title": "Introduction to Contract Terms",
            "paragraph": "This contract is entered into on January 1, 2024, between Party A and Party B.",
            "keyphrases": ["January 1, 2024", "Party A", "Party B"],
            "summary": "This paragraph introduces the contract, specifying the date and parties involved."
        },
        {
            "id": "2",
            "title": "Obligations of Party A",
            "paragraph": "Party A agrees to provide services outlined in Schedule 1 within 30 days of signing this agreement.",
            "keyphrases": ["Party A", "Schedule 1", "30 days", "agreement"],
            "summary": "This paragraph outlines the obligations of Party A to deliver services as per Schedule 1 within a specified timeframe."
        }
    ]
}
```

  """

    openai_response = client.beta.chat.completions.parse(
        model=ally.openai_model_deployment,
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": body_text},
        ],
        response_format=Document,
    )
    try:
        openai_sentiment_response_post_text = openai_response.choices[0].message.parsed
        response = json.loads(
            openai_sentiment_response_post_text.model_dump_json(indent=2)
        )
        print(response)
    except Exception as e:
        print(f"Error converting to JSON sentiment from OpenAI: {e}")
        return

    return response
