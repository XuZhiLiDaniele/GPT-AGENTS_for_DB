from openai import OpenAI
from tools import DatabaseTools

client = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

tools = [
    {
        "type": "function",
        "function": {
            "name": "list_tables",
            "description": "List all tables in the MySQL database.",
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
        "content": (
            "You are an assistant that can use tools. "
            "When the user asks about database tables, "
            "use the list_tables tool."
        )
    },
    {
        "role": "user",
        "content": "Quali sono le tabelle del database?"
    }
]

completion = client.chat.completions.create(
    model="local-model",
    messages=messages,
    tools=tools,
    temperature=0
)

message = completion.choices[0].message

print("================================")
print("CONTENT")
print("================================")
print(message.content)

print("\n================================")
print("TOOL CALLS")
print("================================")
print(message.tool_calls)

print("\n================================")
print("FINISH REASON")
print("================================")
print(completion.choices[0].finish_reason)