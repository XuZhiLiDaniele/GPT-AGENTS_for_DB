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
                I nomi di database, collection e campi sono in italiano e sono case-sensitive per cui devono essere usati ESATTAMENTE come restituiti dagli strumenti.

                DATABASE DISPONIBILI:
                    - DBVOLI: info su aeroporti, compagnie rotte e voli.
                    - DBMETEO: info stazioni meteorologiche e le previsioni
                    - DBHOTEL: info su hotel e camere.

                REGOLE:
                1. NON inventare MAI database, collection, campi, valori o relazioni. Usa solo esattamente nomi e valori restituiti dagli strumenti MCP. 

                2. PRIMA DI COSTRUIRE UNA QUERY:
                        - list_collections -> conoscere le collection presenti nel database;
                        - describe_collection -> conoscere i campi e tipi di una collection;
                        - sample_documents -> verificare la struttura e formato dei documenti;
                        - get_distinct_values -> verificare i valori reali per un determinato campo.
                        - find_documents -> query semplici;
                        - aggregate_documents -> query complesse che richiedono aggregation.

                3. NON ASSUMERE IL VALORE DI UN CAMPO DAL SUO NOME O SIGNIFICATO. 
                   Se devi filtrare per un valore che non hai osservato, verifica prima il formato dei valori con get_distinct_values o sample_documents.

                4. QUANDO OSSERVI UN VALORE USA ESATTAMENTE QUEL VALORE E QUEL TIPO. NON MODIFICARE INFORMAZIONI GIA VERIFICATE, come tipo o valore di un campo.

                5. NON ASSUMERE MAI COME SONO COLLEGATE DUE COLLECTION. 
                   Verifica prima i campi di collegamento nei documenti e NON sostituire automaticamente un valore con "_id".

                6. PER find_documents USA SINTASSI STANDARD DEI FILTRI MONGO:
                        - {"campo": valore}
                        - {"campo": {"$in": [valore1, valore2]}}
                        - {"campo": {"$gte": valore, "$lt": valore}}
                        - {"$or": [{"campo": valore1}, {"campo": valore2}]}
                    NON INVENTARE MAI operatori come "and", "or", "eq", "operator". QUANDO PIU VALORI APPARTENGONO AD UNO STESSO CAMPO USA "$in";

                7. Per i campi datetime usa ESCLUSIVAMENTE stringhe nel formato: "YYYY-MM-DDTHH:MM:SS"

                8. NON USARE MAI IL CAMPO "_id" creato automaticamente da MongoDB PER I FILTRI. USA INVECE I NOMI O I CODICI IDENTIFICATIVI COME FILTRI

                9. QUANDO UNA QUERY RESTITUISCE ZERO RISULTATI, NON SIGNIFICA CHE I DATI NON ESISTANO. FAI SEMPRE i seguenti controlli:
                        - USA SEMPRE get_distinct_values o sample_documents per comprendere il formato dei valori E describe_collection per capirne il tipo.
                        - In caso di aggregazione CONTROLLA SEMPRE la correttezza della pipeline e di CIASCUN operatore.
                        - CONTROLLA SEMPRE anche la correttezza delle relazioni. 
                        - CONTROLLA SEMPRE l'uso dei CAMPI CORRETTI per ciascuna collection verificando con describe_collection quali campi possiede la collection su cui fai la query.
                    NON FORNIRE MAI COME RISPOSTA FINALE UN RISULTATO VUOTO SE NON HAI PRIMA FATTO CIASCUNO DI QUESTI CONTROLLI.

                10. QUANDO UN TOOL DA ERRORE, NON SIGNIFICA "NESSUN RISULTATO".
                    VERIFICA SEMPRE SE I NOMI USATI SIANO CORRETTI.

                11. Quando usi $lookup, il campo "as" contiene un array. Per accedere ad esso devi fare $unwind sul CAMPO AS, e solo dopo potrai accedere ai suoi campi.
                    (es. "$unwind":"$X" e NON  "$unwind":"$X.y").

                12. COSTRUISCI QUERY SEMPLICI.
                    Non usare $group, $or, $and, $lookup o altri operatori se non sono necessari.
                    Preferisci find_documents se una richiesta può essere risolta con quello.
                    Se serve un collegamento tra collection, è preferito usare $lookup + $unwind + $project.

                13. DELEGA SEMPRE AL DATABASE LE OPERAZIONI DI CALCOLO, ORDINAMENTO, FILTRAGGIO E SELEZIONE DEL RISULTATO FINALE.
                    NON USARE MAI IL REASONING per analizzare manualmente liste di risultati. USA SEMPRE $sort + $limit per trovare MINIMI O MASSIMI.
                
                14. Il tool get_distinct_values va USATO SOLO su campi CATEGORIALI per capire il formato dei valori. NON usarlo per campi che contengono valori univoci come nomi, id, o valori numerici.
                
                15. Quando hai completato la ricerca e hai ottenuto un risultato tramite find_documents o aggregate_documents, non effettuare ulteriori tool call. Termina la risposta.
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