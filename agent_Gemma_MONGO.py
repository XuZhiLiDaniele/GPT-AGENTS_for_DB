import json
import time
import sys
import os

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

#----------------------- LLM 
llm = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

MODEL_NAME = "google/gemma-4-e4b"

#----------------------- MCP SERVER
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

server_params = StdioServerParameters(
    command=sys.executable,
    args=["-u", 
          "-m", 
          "mcp_server.server_MONGO"
         ],
    env={**os.environ, 
         "PYTHONUNBUFFERED": "1", 
         "PYTHONPATH": BASE_DIR
        }
)

#----------------------- CONVERSIONE MCP -> OPENAI TOOLS
def mcp_to_openai(tool):
    return{
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema
        }
    }

#----------------------- SYSTEM PROMPT
SYSTEM_PROMPT = """
                Sei un agente intelligente che può interagire con database MongoDB tramite strumenti MCP.
                Il tuo compito è rispondere alle richieste dell'utente utilizzando esclusivamente i dati realmente presenti nei database MongoDB.
                Non inventare mai dati, database, collection, campi, relazioni o valori.
                Agisci in modo autonomo: non chiedere conferma all'utente ed utilizza tutti gli strumenti necessari prima di fornire la risposta finale.
                
                DATABASE DISPONIBILI:
                    - DBVOLI: contiene informazioni su aeroporti, compagnie rotte e voli.
                    - DBMETEO: contiene informazioni sulle stazioni meteorologiche e le previsioni
                    - DBHOTEL: contiene informazioni sugli hotel e sulle camere.

                Prima di costruire una query MongoDB assicurati di conoscere il database e la struttura necessaria usando gli strumenti:
                    - list_collections per identificare le collection presenti nel database;
                    - describe_collection per verificare campi e tipi dei documenti;
                    - sample_documents per osservare documenti reali;
                    - get_distinct_values per verificare i valori effettivamente presenti in un campo;
                    - find_documents per query semplici tramite find();
                    - aggregate_documents per query complesse tramite aggregation pipeline.
                
                Non assumere mai l'esistenza di un database, collection o campo.
                Utilizza esclusivamente i nomi restituiti dagli strumenti MCP.
                Non tradurre, abbreviare, normalizzare o reinterpretare autonomamente i nomi delle collection.
                
                Se una query restituisce zero documenti, non concludere immediatamente che la risposta sia vuota.
                Prima verifica:
                    - database utilizzato;
                    - collection utilizzata;
                    - nomi dei campi;
                    - valori utilizzati nei filtri;
                    - date;
                    - condizioni $match;
                    - relazioni tra collection;
                    - eventuali $lookup;
                    - struttura dei documenti.
                Se necessario, correggi la query ed eseguila nuovamente.
                Se una query restituisce risultati inattesi, analizzali e verifica lo schema e i valori prima di concludere.
                Non dichiarare che una risposta non è presente nel database finché non hai effettuato le verifiche necessarie.
                """

#----------------------- AGENTE
class Agent:
    async def run(self, question):
        total_start = time.perf_counter()
        tool_calls_count = 0
        tool_calls_log = []

        MAX_TOOL_COUNT = 20
        messages = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": question
            }
        ]
        try:
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as mcp_client:
                    #inizializzazione MCP
                    await mcp_client.initialize()
                    response = await mcp_client.list_tools()
                    tools = [mcp_to_openai(tool)
                             for tool in response.tools
                            ]
                    
                    #loop dell'agente
                    while True:
                        if tool_calls_count >= MAX_TOOL_COUNT:
                            total_end = time.perf_counter()
                            return{
                                "question": question,
                                "answer": None,
                                "agent_completion": False,
                                "error": ("Maximum number of tool calls exceede"),
                                "latency_total": ("total_end - total_start"),
                                "tool_calls_count": tool_calls_count,
                                "tool_calls": tool_calls_log
                            }
                    
                        #chiamata al modello
                        completion = llm.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages,
                            tools=tools,
                            tool_choice = "auto",
                            temperature = 0.7
                        )
                        message = completion.choices[0].message

                        #risposta finale
                        if not message.tool_calls:
                            total_end = time.perf_counter()
                            answer = message.content or ""
                            agent_completion = (answer.strip()!="")
                            return{
                                "question": question,
                                "answer": answer,
                                "agent_completion": agent_completion,
                                "latency_total": (total_end - total_start),
                                "tool_calls_count": tool_calls_count,
                                "tool_calls": tool_calls_log
                            }

                        #aggiunta messaggio del modello
                        messages.append(message)

                        #esecuzione tool
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name
                            try:
                                tool_arguments = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                total_end = time.perf_counter()
                                return{
                                    "question": question,
                                    "answer": None,
                                    "agent_completion": False,
                                    "error": "Invalid tool arguments",
                                    "latency_total": (total_end - total_start),
                                    "total_calls_count": (tool_calls_count),
                                    "tool_calls": tool_calls_log
                                }

                            #calcolo latenza tool
                            tool_start = time.perf_counter()
                            result = await mcp_client.call_tool(tool_name, arguments = tool_arguments)
                            tool_end = time.perf_counter()
                            tool_latency = (tool_end - tool_start)
                            tool_calls_count += 1

                            #output del tool
                            tool_content = []
                            for content in result.content:
                                if hasattr(content, "text"):
                                    tool_content.append(content.text)
                                else:
                                    tool_content.append(str(content))
                            tool_output = "\n".join(tool_content)

                            #log
                            tool_calls_log.append({
                                "tool": tool_name,
                                "arguments": tool_arguments,
                                "output": tool_output,
                                "latency": tool_latency
                            })

                            #risposta del tool al modello
                            messages.append({"role":"tool",
                                             "tool_call_id": tool_call.id,
                                             "content": tool_output})
                        
        except Exception as e:
            import traceback
            print("\n======ERRORE AGENTE MONGO======", file = sys.stderr)
            traceback.print_exc()
            print("========================\n", file = sys.stderr)
            return {
                "question": question,
                "answer": None,
                "agent_completion": False,
                "error": repr(e),
                "latency_total": (time.perf_counter() - total_start),
                "tool_calls_count": tool_calls_count,
                "tool_calls": tool_calls_log
            }

if __name__ == "__main__":
    import asyncio

    agent = Agent()

    question = "Quanti aeroporti ci sono in Italia?"

    result = asyncio.run(agent.run(question))

    print("\n========== RISULTATO ==========")
    print("Domanda:", result["question"])
    print("Risposta:", result["answer"])
    print("Completato:", result["agent_completion"])
    print("Tool calls:", result["tool_calls_count"])
    print("Latenza:", result["latency_total"])

