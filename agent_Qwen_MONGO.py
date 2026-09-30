import json
import time
import sys
import os
import re

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

#----------------------- LLM 
llm = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

MODEL_NAME = "qwen3.5-9b"

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

#----------------------- PARSING DEL RISULTATO DI UN TOOL
def parse_tool_output(tool_output):
    """
    Trasforma l'output testuale dal tool in un oggetto Python. 
    Se l'output non è JSON valido, lo lascia come stringa.
    """
    if not isinstance(tool_output, str):
        return tool_output
    try:
        return json.loads(tool_output)
    except json.JSONDecodeError:
        return tool_output

#----------------------- SYSTEM PROMPT
SYSTEM_PROMPT = """
                Sei un agente intelligente che interagisce con un database MongoDB tramite strumenti MCP.
                Rispondi alle richieste utilizzando esclusivamente i dati realmente nei database.
                I nomi di database, collection e campi sono in ITALIANO e sono CASE-SENSITIVE per cui devono essere usati ESATTAMENTE come restituiti dagli strumenti.
                DATABASE DISPONIBILI:
                - DBVOLI: info su aeroporti, compagnie rotte e voli.
                - DBMETEO: info stazioni meteorologiche e le previsioni
                - DBHOTEL: info su hotel e camere.

                REGOLE:
                - Prima di rispondere ad una richiesta FAI SEMPRE TUTTI i seguenti passaggi:
                    1. Identifica le collezioni utili usando list_collections
                    2. Identifica per ogni collezione utile i campi utili usando describe_collection
                    3. Conosci il formato corretto dei dati di ciascun campo delle collezioni utili usando sample_documents
                    4. Se hai dei dubbi sul formato di un determinato campo, utilizza get_distinct_values per scoprire tutti i valori disponibili per quel campo.
                - NON assumere mai l'esistenza di tabelle, colonne, valori o il formato dei dati di un campo.
                - NON tradurre, abbreviare o reinterpretare autonomamente i valori del database.
                - Quando un valore necessario per un filtro non è noto con certezza, utilizza sample_documents o get_distinct_values per verificare i valori
                effettivamente presenti.
                In particolare usa get_distinct_values se:
                    > devi filtrare un campo categoriale
                    > il valore richiesto dall'utente potrebbe essere rappresentato diversamente nel database;
                    > il valore non è stato osservato precedentemente;
                    > una query restituisce risultati vuoti e il filtro potrebbe essere errato.
                - Quando una query restituisce zero risultati. NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. USA SEMPRE get_distinct_values o sample_documents per comprendere il formato dei valori E describe_collection per capirne il tipo.
                    2. In caso di aggregazione CONTROLLA SEMPRE la correttezza della pipeline e di CIASCUN operatore.
                    3. CONTROLLA SEMPRE anche la correttezza delle relazioni. 
                    4. CONTROLLA SEMPRE l'uso dei CAMPI CORRETTI per ciascuna collection verificando con describe_collection quali campi possiede la collection
                    su cui fai la query.
                NON FORNIRE MAI come risposta un risultato vuoto se prima non hai fatto questi controlli..
                - Quando una query restituisce errore MongoDB, NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. CONTROLLA SEMPRE tutti i nomi che hai usato per il database, la collection o i campi.
                    2. CONTROLLA SEMPRE tutti gli operatori che hai usato.
                    3. CONTROLLA SEMPRE la correttezza della pipeline che hai usato nella query.
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
                                "latency_total": (total_end - total_start),
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
                        finish_reason = completion.choices[0].finish_reason

                        print("\n========== MODEL RESPONSE ==========", file=sys.stderr)
                        print("CONTENT:", repr(message.content), file=sys.stderr)
                        print("TOOL CALLS:", message.tool_calls, file=sys.stderr)
                        print("FINISH REASON:", finish_reason, file=sys.stderr)
                        print("====================================\n", file=sys.stderr)

                        #risposta finale
                        if not message.tool_calls:
                            total_end = time.perf_counter()
                            raw_final_message = message.content or ""
                            
                            if finish_reason == "length":
                                return{
                                    "question": question,
                                    "answer": None,
                                    "agent_completion": False,
                                    "error": "Final response truncated",
                                    "finish_reason": finish_reason,
                                    "raw_final_message": raw_final_message,
                                    "latency_total": total_end-total_start,
                                    "tool_calls_count": tool_calls_count,
                                    "tool_calls": tool_calls_log
                                }
                            #RECUPERO AUTOMATICO RISULTATO ULTIMA QUERY
                            final_output = None
                            for tool_calls in reversed(tool_calls_log):
                                if tool_call["tool"] in ("find_documents", "aggregate_documents"):
                                    output = tool_call["output"]
                                    if (isinstance(output, dict) and output.get("success") is True):
                                        final_output = output
                                        break
                            if final_output is None: #SE NESSUNA QUERY VALIDA ESEGUITA
                                return {
                                    "question": question,
                                    "answer": None,
                                    "agent_completion": False,
                                    "error": "No successful MongoDB query found",
                                    "finish_reason": finish_reason,
                                    "raw_final_message": raw_final_message,
                                    "latency_total": total_end - total_start,
                                    "tool_calls_count": tool_calls_count,
                                    "tool_calls": tool_calls_log
                                }
                            return { # RISULTATO AGENTE
                                "question": question,
                                "answer": final_output.get("documents",[]),
                                "agent_completion": True,
                                "finish_reason": finish_reason,
                                "final_message": raw_final_message,
                                "latency_total": (total_end - total_start),
                                "tool_calls_count": tool_calls_count,
                                "tool_calls": tool_calls_log
                            }
                        
                        messages.append(message)#aggiunta messaggio

                        # ESECUZIONE TOOL
                        for tool_call in message.tool_calls:
                            tool_name = tool_call.function.name
                            try: # PARSING ARGOMENTI TOOL
                                tool_arguments = json.loads(tool_call.function.arguments)
                            except json.JSONDecodeError:
                                total_end = time.perf_counter()
                                return {
                                    "question": question,
                                    "answer": None,
                                    "agent_completion": False,
                                    "error": "Invalid tool arguments",
                                    "latency_total": (total_end - total_start),
                                    "tool_calls_count": tool_calls_count,
                                    "tool_calls": tool_calls_log
                                }
                            
                            current_tool_number = tool_calls_count + 1 # NUMERO TOOL CALL

                            # ESECUZIONE TOOL
                            tool_start = time.perf_counter()
                            result = await mcp_client.call_tool(tool_name, arguments=tool_arguments)
                            tool_end = time.perf_counter()
                            tool_latency = (tool_end - tool_start)
                            tool_calls_count += 1

                            # ESTRAZIONE OUTPUT TOOL
                            tool_content = []
                            for content in result.content:

                                if hasattr(content, "text"):
                                    tool_content.append(content.text)
                                else:
                                    tool_content.append(str(content))

                            tool_output = "\n".join(tool_content)

                            # PARSING OUTPUT TOOL
                            parsed_tool_output = parse_tool_output(tool_output)
                            
                            # LOG
                            tool_calls_log.append({
                                "tool_call_number":
                                    current_tool_number,
                                "tool":
                                    tool_name,
                                "arguments":
                                    tool_arguments,
                                "output":
                                    parsed_tool_output,
                                "raw_output":
                                    tool_output,
                                "latency":
                                    tool_latency
                            })

                            # OUTPUT VISIBILE AL MODELLO
                            tool_message_content = (
                                f"TOOL_CALL_{current_tool_number}\n"
                                f"{tool_output}"
                            )

                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": tool_message_content
                            })

        # ============================================================
        # ERRORE GENERALE
        # ============================================================

        except Exception as e:

            import traceback

            print("\n====== ERRORE AGENTE MONGO ======", file=sys.stderr)
            traceback.print_exc()
            print("=================================\n", file=sys.stderr)
            return {
                "question": question,
                "answer": None,
                "agent_completion": False,
                "error": repr(e),
                "latency_total": (time.perf_counter() - total_start),
                "tool_calls_count": tool_calls_count,
                "tool_calls": tool_calls_log
            }

# TEST
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
    print("Final tool call:", result.get("final_tool_call"))
    print("Final message:", result.get("final_message"))
    print("Latenza:", result["latency_total"])