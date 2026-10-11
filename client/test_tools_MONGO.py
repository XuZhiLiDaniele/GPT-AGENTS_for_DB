from openai import OpenAI
import json

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "mongo_list_databases",
            "description": "Restituisce la lista dei database MongoDB disponibili.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

messages = [
    {
        "role": "system",
        "content": "Se necessario, usa gli strumenti disponibili."
    },
    {
        "role": "user",
        "content": "Quali database MongoDB sono disponibili?"
    }
]

response = client.chat.completions.create(
    model="qwen",
    messages=messages,
    tools=tools,
    tool_choice="auto",
    temperature=0
)

print("CONTENT:", response.choices[0].message.content)
print("TOOL CALLS:", response.choices[0].message.tool_calls)
print("FINISH:", response.choices[0].finish_reason)