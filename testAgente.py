#
# Script per testare il modello locale Gemma 4, collegato con LLMStudio, con cui interagiamo tramite prompt su terminale.
# Il modello mantiene memoria della sola conversazione corrente.
#

import json
import asyncio
import sys
import os

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Point to the local server LLM which provides our LLM
llm = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

# MCP Server setup
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
server_params = StdioServerParameters(
    command = sys.executable,
    args = [
        "-u",
        "-m",
        "mcp_server.server"
    ],
    env={
        **os.environ, 
        "PYTHONUNBUFFERED":"1",
        "PYTHONPATH": BASE_DIR
    }
)

# MCP tool to OpenAI tool
def mcp_to_openai(tool):
    return{
        "type":"function", 
        "function": {
            "name":tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema
        }
    }


# Agent setup
async def main():
    print("\nConnessione al server MCP...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as mcp_client:
            await mcp_client.initialize() #initialization MCP
            print("Connessione MCP riuscita")

            response = await mcp_client.list_tools() #discovering available MCP tools
            
            tools = [
                mcp_to_openai(tool)
                for tool in response.tools
            ]

            print("\nTool MCP disponibili:")
            for tool in response.tools:
                print(f"- {tool.name}")
                print(f" {tool.description}")


            messages = [
                {"role": "system", 
                "content": """
                            Sei un assistente che può interagire con un database MySQL tramite strumenti MCP.
                            Quando l'utente chiede informazioni, utilizza gli strumenti disponibili invece di inventare informazioni.
                            Dopo aver ricevuto il risultato di uno strumento, analizzalo e fornisci una risposta comprensibile all'utente.
                        """
                }
            ]

            # Chat loop via terminal
            print("Insert exit or quit to end chat.")
            while True:
                user_input = input("\nYou:").strip()

                if user_input.lower() in ["exit", "quit"]:
                    print("Goodbye!")
                    break
                print("[DEBUG 1] Input ricevuto")
                if not user_input:
                    continue

                messages.append(
                    {"role": "user", 
                    "content": user_input
                    }
                )
                #loop for multiple tool calls
                while True:
                    print("[DEBUG 2] Chiamo LM Studio")
                    # Generating the first response
                    completion = llm.chat.completions.create(
                        model ="local-model", # this field is currently unused
                        messages = messages,
                        tools = tools,
                        tool_choice = "auto",
                        temperature = 0.7
                    )
                
                    print("[DEBUG 3] Risposta ricevuta da LM Studio")
                    message = completion.choices[0].message

                    #if it doesn't require a tool
                    if not message.tool_calls:
                        print("\nAssistant:", message.content)
                        messages.append(message)
                        break

                    print(f"[DEBUG] LM Studio ha rischiesto {len(message.tool_calls)} tool")
                    messages.append(message)

                    for tool_call in message.tool_calls:
                        tool_name=tool_call.function.name
                        tool_arguments=json.loads(tool_call.function.arguments)
                        print(f"\n[Tool chiamato:{tool_name}]")
                        print(f"[Argomenti:{tool_arguments}]")

                        result = await mcp_client.call_tool(tool_name, arguments=tool_arguments)
                        print(f"[Risultato: {result}]")

                        tool_content=[]
                        for content in result.content:
                            if hasattr(content, "text"):
                                tool_content.append(
                                    content.text
                                )
                            else:
                                tool_content.append(
                                    str(content)
                                )
                        tool_output = "\n".join(
                            tool_content
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_output
                            }
                        )
                    print("[DEBUG] Risultati tool inseriti nella conversazioni")
                    print("[DEBUG] Richiamo LM Studio")

#Start
if __name__=="__main__":
    asyncio.run(main())

