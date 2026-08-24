import json
import time
import sys
import os

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


llm = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

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


SYSTEM_PROMPT =  """
                    Sei un assistente che può interagire con dei database MySQL tramite strumenti MCP.
                    Quando l'utente chiede informazioni, utilizza gli strumenti disponibili invece di inventare informazioni.
                    Dopo aver ricevuto il risultato di uno strumento, analizzalo, e se ritieni che sia insufficiente, rifletti per 
                    chiamare di nuovo altri strumenti.
                    Per ogni richiesta che ritieni più complessa, prima di tutto realizza un piano d'azione a più step e strumenti, 
                    solo poi prosegui con l'esecuzione degli step in MODO AUTONOMO, ovvero SENZA necessitare di interpellare l'utente
                    Produci la risposta per l'utente solo quando completi il piano d'azione con una risposta soddisfacente.
                    Infine, quando devi eseguire delle query sul database, fai attenzione al formato dei dati, in modo da applicare
                    filtri che rispettino quel formato. Per conoscere il formato, usa gli strumenti a tua disposizione come 
                    sample_rows per ottenere un esempio di righe della tabella e capire il formato dei dati.

                    I database disponibili sono:
                    1. DBVOLI: contiene informazioni su aeroporti, compagnie, rotte e voli.
                    2. DBMETEO: contiene informazioni meteorologiche, ovvero previsioni e stazioni meteo.
                    3. DBHOTEL: contiene informazioni sugli hotel e sulle loro camere. 
                """


class Agent:

    async def run(self, question):

        total_start = time.perf_counter() #inizio misurazione del completamento della richiesta

        tool_calls_count = 0 #numero di tool chiamate

        tool_calls_log = [] #lista delle chiamate ai tool

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
                        completion = llm.chat.completions.create(
                            model="local-model",
                            messages=messages,
                            tools=tools,
                            tool_choice="auto",
                            temperature=0.7
                        )

                        message = completion.choices[0].message

                        # L'agente ha finito
                        if not message.tool_calls:

                            total_end = time.perf_counter()

                            return {
                                "question": question,
                                "answer": message.content,
                                "success": True,
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
                                    "success": False,
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
                "success": False,
                "error": repr(e),
                "latency_total": time.perf_counter() - total_start,
                "tool_calls_count": tool_calls_count,
                "tool_calls": tool_calls_log
            }
