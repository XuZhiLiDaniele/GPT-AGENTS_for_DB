#
# Script per testare il modello locale Gemma 4, collegato con LLMStudio, con cui interagiamo tramite prompt su terminale.
# Il modello mantiene memoria della sola conversazione corrente.
#

import json
import asyncio
import sys
import os
import time

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
                
                start_time = time.perf_counter() #timer per misurare la latenza
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
                        end_time = time.perf_counter()
                        messages.append(message)
                        latency = end_time - start_time
                        print("\nAssistant:", message.content)
                        print(f"\n[LATENZA: {latency:.3f} secondi]")
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

