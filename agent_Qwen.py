import json
import time
import sys
import os

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


llm = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")
MODEL_NAME = "qwen3.5-9b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

server_params = StdioServerParameters(
    command=sys.executable,
    args=[
        "-u",
        "-m",
        "mcp_server.server"
    ],
    env={
        **os.environ,
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": BASE_DIR
    }
)


def mcp_to_openai(tool):
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.input_schema
        }
    }
SYSTEM_PROMPT = """
                Sei un agente intelligente che può interagire con database MySQL tramite strumenti MCP. 
                Il tuo compito è rispondere alle richieste dell'utente utilizzando esclusivamente i dati presenti nei database. 
                Non inventare mai dati, tabelle, colonne, relazioni o valori.
                Agisci sempre in modo autonomo: non chiedere conferma all'utente e utilizza tutti gli strumenti necessari prima di fornire la risposta finale.

                Prima di costruire una query SQL, assicurati di conoscere lo schema necessario ed utilizza gli strumenti MCP quando necessario:
                - list_tables per identificare le tabelle;
                - describe_table per verificare colonne e tipi;
                - sample_rows per osservare dati reali;
                - get_distinct_values per ottenere un esempio di valori distinti di una data colonna di una tabella.
                - execute_sql per eseguire una query di sola lettura data in input.
                Non assumere mai l'esistenza di tabelle, colonne, valori o il formato dei dati di una colonna.
                Non tradurre, abbreviare, normalizzare o reinterpretare autonomamente i valori del database.
                Quando un valore necessario per un filtro non è noto con certezza, utilizza sample_rows o get_distinct_values per verificare i valori effettivamente presenti.
                In particolare, usare get_distinct_values quando:
                - devi filtrare una colonna categoriale;
                - il valore richiesto dall'utente potrebbe essere rappresentato diversamente nel database;
                - il valore non è stato osservato precedentemente;
                - una query restituisce risultati vuoti e il filtro potrebbe essere errato.

                Costruisci le query utilizzando esclusivamente tabelle, colonne, relazioni e valori verificati, e dopo ogni execute_sql, assicurati di analizzarne i risultati.
                Se una query restituisce zero risultati o risultati inattesi, non concludere immediatamente che la risposta non sia disponibile. Verifica nuovamente:
                - schema;
                - valori;
                - filtri;
                - date;
                - JOIN;
                - database utilizzato.
                Se necessario, correggi la query e rieseguila.
                Non dichiarare che una risposta non è presente nei database finché non hai effettuato le verifiche necessarie.

                Quando una domanda richiede informazioni da più database:
                    1. Identifica il primo database necessario.
                    2. Esegui una query per ottenere i valori intermedi.
                    3. Conserva esplicitamente tali valori.
                    4. Utilizza i valori ottenuti come input della query sul database successivo.
                    5. Non tentare JOIN SQL tra database differenti tramite execute_sql.
                    6. Il collegamento tra database deve essere effettuato logicamente dall'agente.
                    7. Ripetere gli step precedenti se ci sono ancora più database differenti da interrogare.

                I database disponibili sono:
                    - DBVOLI: contiene informazioni su aeroporti, compagnie, rotte e voli.
                    - DBMETEO: contiene informazioni meteorologiche, ovvero previsioni e stazioni meteo.
                    - DBHOTEL: contiene informazioni sugli hotel e sulle loro camere. 
                """

class Agent:

    async def run(self, question):

        total_start = time.perf_counter() #inizio misurazione del completamento della richiesta
        tool_calls_count = 0 #numero di tool chiamate
        tool_calls_log = [] #lista delle chiamate ai tool
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

                    await mcp_client.initialize()

                    response = await mcp_client.list_tools()

                    tools = [
                        mcp_to_openai(tool)
                        for tool in response.tools
                    ]

                    while True:
                        if tool_calls_count >= MAX_TOOL_COUNT:
                            total_end = time.perf_counter()
                            return {
                                "question": question,
                                "answer": None,
                                "agent_completion": False,
                                "error": "Maximum number of tool calls exceeded",
                                "latency_total": total_end - total_start,
                                "tool_calls_count": tool_calls_count,
                                "tool_calls": tool_calls_log
                            }
                          
                        completion = llm.chat.completions.create(
                            model=MODEL_NAME,
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.7
                        )

                        message = completion.choices[0].message

                        # L'agente ha finito
                        if not message.tool_calls:

                            total_end = time.perf_counter()
                            answer = message.content or ""
                            agent_completion = answer.strip() != ""

                            return {
                                "question": question,
                                "answer": message.content,
                                "agent_completion": agent_completion,
                                "latency_total": total_end - total_start,
                                "tool_calls_count": tool_calls_count,
                                "tool_calls": tool_calls_log
                            }

                        messages.append(message)

                        for tool_call in message.tool_calls:

                            tool_name = tool_call.function.name

                            try:
                                tool_arguments = json.loads(
                                    tool_call.function.arguments
                                )

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

                            tool_start = time.perf_counter()

                            result = await mcp_client.call_tool(
                                tool_name,
                                arguments=tool_arguments
                            )

                            tool_end = time.perf_counter()

                            tool_latency = tool_end - tool_start

                            tool_calls_count += 1

                            tool_content = []

                            for content in result.content:

                                if hasattr(content, "text"):
                                    tool_content.append(content.text)
                                else:
                                    tool_content.append(str(content))

                            tool_output = "\n".join(tool_content)

                            tool_calls_log.append({
                                "tool": tool_name,
                                "arguments": tool_arguments,
                                "output": tool_output,
                                "latency": tool_latency
                            })

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": tool_output
                                }
                            )
        except Exception as e:
            import traceback

            print("\n========== ERRORE AGENTE ==========")
            traceback.print_exc()
            print("===================================\n")

            return {
                "question": question,
                "answer": None,
                "agent_completion": False,
                "error": repr(e),
                "latency_total": time.perf_counter() - total_start,
                "tool_calls_count": tool_calls_count,
                "tool_calls": tool_calls_log
            }
