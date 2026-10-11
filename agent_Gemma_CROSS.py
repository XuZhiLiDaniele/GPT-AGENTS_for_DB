import json
import time
import sys
import os
import traceback

from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# CONFIGURAZIONE AGENTE
# ============================================================

llm = OpenAI(
    base_url="http://localhost:1234/v1",
    api_key="not-needed"
)

MODEL_NAME = "google/gemma-4-e4b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# MCP SERVER - MYSQL
mysql_server_params = StdioServerParameters(
    command=sys.executable,
    args=["-u", "-m", "mcp_server.server"],
    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": BASE_DIR}
)
# MCP SERVER - MONGODB
mongo_server_params = StdioServerParameters(
    command=sys.executable,
    args=["-u", "-m", "mcp_server.server_MONGO"],
    env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONPATH": BASE_DIR}
)

#MAPPATURA DB E DBMS
DB_DBMS ={
    "DBPASSEGGERI": "mysql",
    "DBVOLI": "mysql",
    "DBMETEO": "mongo",
    "DBHOTEL": "mongo"
}

# ============================================================
# CONVERSIONE MCP TOOL -> OPENAI TOOL
# ============================================================
def mcp_to_openai(tool, prefix):
    """
    Converte un MCP tool nel formato richiesto da OpenAI.
    Il prefix identifica il DBMS di appartenenza per evitare collisioni tra tool con lo stesso nome presenti nei due MCP server.
    """

    return {
        "type": "function",
        "function": {
            "name": f"{prefix}_{tool.name}",
            "description": tool.description or "",
            "parameters": tool.input_schema
        }
    }

# ============================================================
# PARSING RISULTATO TOOL
# ============================================================
def parse_tool_output(tool_output):
    """
    Prova a convertire l'output del tool in JSON.
    Se l'output non è JSON valido, viene mantenuto come stringa.
    """

    if not isinstance(tool_output, str):
        return tool_output
    try:
        return json.loads(tool_output)
    except json.JSONDecodeError:
        return tool_output

# ============================================================
# VALIDATORE TRA DB RICHIESTO E LINGUAGGIO DEI TOOL
# ============================================================
def validate_database_access(dbms,tool_arguments):
    """
    Verifica che il database richiesto dal modello
    appartenga effettivamente al DBMS selezionato.
    """

    database = tool_arguments.get("database")

    # Il tool deve specificare un database
    if database is None:
        return False, "Missing database argument"
    expected_dbms = DB_DBMS.get(database)

    # Database non presente nella configurazione.
    if expected_dbms is None:
        return False, (f"Unknown or unauthorized database: {database}")

    # Controllo fondamentale.
    if expected_dbms != dbms:
        return False, (f"Database '{database}' belongs to {expected_dbms}, but the agent attempted to access it through {dbms}")
    return True, None

# ============================================================
# SYSTEM PROMPT
# ============================================================
SYSTEM_PROMPT = """
                Sei un agente cross-database MongoDB e MySQL a cui puoi accedere tramite strumenti MCP.
                Rispondi alle richieste utilizzando esclusivamente i dati realmente nei database.
                I nomi di database, collection e campi sono in ITALIANO e sono CASE-SENSITIVE per cui devono essere usati ESATTAMENTE come restituiti dagli strumenti.
                
                DATABASE DISPONIBILI:
                MySQL:
                - DBPASSEGGERI -> contiene informazioni riguardanti i passeggeri ed i biglietti da loro acquistati.
                - DBVOLI -> contiene informazioni riguardanti gli aeroporti, le compagnie aeree, le rotte di volo ed i singoli voli.
                MongoDB:
                - DBMETEO -> contiene informazioni riguardanti le stazioni meteo e le rispettive previsioni.
                - DBHOTEL -> contiene informazioni riguardanti gli hotel e le camere degli hotel.

                REGOLE:
                - Usa strumenti MySQL solo su database MySQL.
                - Usa strumenti MongoDB solo su database MongoDB
                - Prima iniziare a ragionare per una richiesta, FAI SEMPRE TUTTI i seguenti passaggi utilizzando gli strumenti adatti a quel database:
                    1. Identifica le collezioni necessarie per rispondere alla richiesta;
                    2. Identifica per ogni collezione utile i suoi campi;
                    3. Conosci il formato corretto dei dati di ciascun campo delle collezioni utili gli strumenti per ottenere esempi.
                - NON assumere mai l'esistenza di collezioni, campi, valori o il formato dei dati di un campo.
                - NON tradurre, abbreviare o reinterpretare autonomamente i valori del database.
                - NON includere mai virgolette doppie o apici, o altre forme di quotazione per all'interno delle chiavi MongoDB che DEVONO essere stringhe JSON normali.
                - Quando un valore necessario per un filtro non è noto con certezza, utilizza gli appositi strumenti per quel database per ottenere esempi e verificare i valori
                  effettivamente presenti.
                    In particolare usa get_distinct_values SOLO SE:
                    > NON si tratta di un campo ad alta cardinalità (es, nomi, identificativi, codici).
                    > devi filtrare un campo categoriale
                    > il valore richiesto dall'utente potrebbe essere rappresentato diversamente nel database;
                    > il valore non è stato osservato precedentemente;
                    > una query restituisce risultati vuoti e il filtro potrebbe essere errato.
                    PREFERISCI invece l'uso di sample_document per capire il formato, oppure di find_documents se CONOSCI i filtri adatti per ridurre l'output.
                - Quando una richiesta richiede un minimo o un massimo singolo o multiplo rispondi sempre creando una query che restituisca direttamente le righe interessate.
                - Per query MongoDB, se devi filtrare una data, rappresentala SEMPRE come stringa ISO 8601. NON USARE $date, $year, $month etc...
                - Quando una query restituisce zero risultati. NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. VERIFICA SEMPRE di aver usato i nomi corretti dei database o delle collezioni.
                    2. USA SEMPRE sample_documents per comprendere il formato dei valori tenendo conto del suo tipo.
                    3. In caso di aggregazione CONTROLLA SEMPRE la correttezza della pipeline e di CIASCUN operatore.
                    4. CONTROLLA SEMPRE anche la correttezza delle relazioni. 
                    5. CONTROLLA SEMPRE l'uso dei CAMPI CORRETTI per ciascuna collection verificando con describe_collection quali campi possiede la collection
                        su cui fai la query.
                NON FORNIRE MAI come risposta un risultato vuoto se prima non hai fatto questi controlli.
                - Quando una query restituisce errore MongoDB, NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. LEGGI BENE il messaggio di errore che ha restituito.
                    2. IDENTIFICA la fonte dell'errore.
                    3. RAGIONA e SPIEGA internamente come cosa ha causato l'errore e come correggerlo.
                    4. Seguendo il ragionamento CREA una NUOVA query da ZERO correggendo gli errori individuati.

                """
                # Sei un agente intelligente cross-database che interagisce con database MySQL e MongoDB tramite strumenti MCP.
                # Rispondi esclusivamente utilizzando dati realmente presenti nei database. 
                # Non inventare mai dati, valori, campi, collection o relazioni.
                
                # Database MySQL:
                # - DBPASSEGGERI: passeggeri e biglietti.
                # - DBVOLI: aeroporti, compagnie, rotte e voli.
                # Database MongoDB:
                # - DBMETEO: stazioni meteorologiche e previsioni.
                # - DBHOTEL: hotel e camere.

                # I nomi di database, tabelle, collection e campi sono CASE-SENSITIVE.
                # Usa sempre esattamente i nomi restituiti dagli strumenti

                # REGOLE:
                # - Usa strumenti MySQL esclusivamente sui database MySQL.
                # - Usa strumenti MongoDB esclusivamente sui database MongoDB.
                # - Fai attenzione a fornire i parametri corretti quando chiami un tool.
                # - Non utilizzare SQL su MongoDB.
                # - Non usare operatori MongoDB su MySQL.
                # - Non eseguire JOIN tra DBMS differenti.
                # - Se una richiesta richiede più DBMS, esegui query separate e combina i risultati nell'agente.
                # - Prima di interrogare una tabella o collection, verifica che esista e controlla i campi necessari.
                # - Non assumere mai l'esistenza di campi, valori, tipi o formati.
                
                # MYSQL:
                # - Utilizza esclusivamente sintassi SQL valida.
                # - Usa solo colonne presenti nello schema.
                # - Per minimo, massimo, TOP-N o BOTTOM-N utilizza ORDER BY e LIMIT.

                # MONGODB:
                # - Utilizza esclusivamente sintassi MongoDB valida.
                # - Usa solo i nomi dei campi esattamenti come restituiti dallo schema.
                # - I nomi dei campi sono SEMPRE STRINGHE JSON normali.
                # - Gli operatori MongoDB sono chiavi dell'oggetto e iniziano con $.
                # - Per minimo, massimo, TOP-N o BOTTOM-N utilizza $sort e $limit.
                # - Le date devono essere rappresentate come stringhe ISO 8601 coerenti con i dati.
                # - Non utilizzare mai $date, $year, $month per rappresentare date.

                #   Esempi MongoDB:
                #   {"città": "Londra" }
                #   {"stelle": 5}
                #   {"temperatura": {"$lt": 40.0}}
                #   {"date": }

                # SE UNA QUERY RESTITUISCE ZERO RISULTATI:
                # - Non concludere che non esistano dati.
                # - Verifica nuovamente database, campi, valori, formato ed operatori.
                # - Se necessario, controlla nuovamente schema e dati.
                # - Correggi la query e riprova.

                # SE UNA QUERY RESTITUISCE UN ERRORE:
                # - Analizza il messaggio di errore.
                # - Identifica la parte della query responsabile.
                # - Correggi l'errore costruendo una nuova query.
                # - Esegui nuovamente la query.

                # Fornisci come risposta finale esclusivamente risultati supportati dai dati ottenuti dagli strumenti.
                # Non terminare la risposta se non hai trovato alcun dato o non hai fatto tutte le verifiche elencate qui sopra.


# ============================================================
# AGENTE CROSS-DB
# ============================================================
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
            # ====================================================
            # AVVIAMO ENTRAMBI I SERVER MCP
            # ====================================================
            async with stdio_client(mysql_server_params) as (mysql_read,mysql_write):
                async with stdio_client(mongo_server_params) as (mongo_read, mongo_write):
                    # ====================================================
                    # CREAZIONE SESSIONI MCP
                    # ====================================================
                    async with ClientSession(mysql_read, mysql_write) as mysql_client:
                        async with ClientSession(mongo_read, mongo_write) as mongo_client:
                            # ====================================================
                            # INIZIALIZZAZIONE MCP
                            # ====================================================
                            await mysql_client.initialize()
                            await mongo_client.initialize()
                            # ====================================================
                            # RECUPERO TOOL MYSQL
                            # ====================================================
                            mysql_response = (await mysql_client.list_tools())
                            # ====================================================
                            # RECUPERO TOOL MONGODB
                            # ====================================================
                            mongo_response = (await mongo_client.list_tools())
                            # ====================================================
                            # CONVERSIONE TOOL
                            # ====================================================
                            mysql_tools = [
                                mcp_to_openai(tool, "mysql") 
                                for tool in mysql_response.tools
                            ]
                            mongo_tools = [
                                mcp_to_openai(tool, "mongo")
                                for tool in mongo_response.tools
                            ]
                            # ====================================================
                            # UNICA LISTA DI TOOL PER IL MODELLO
                            # ====================================================
                            tools = (mysql_tools + mongo_tools)
                            # ====================================================
                            # LOOP DELL'AGENTE
                            # ====================================================
                            while True:
                                if tool_calls_count >= MAX_TOOL_COUNT:
                                    total_end = time.perf_counter()
                                    return {
                                        "question": question,
                                        "answer": None,
                                        "agent_completion": False,
                                        "error": ("Maximum number of tool calls exceeded"),
                                        "latency_total": (total_end - total_start),
                                        "tool_calls_count": (tool_calls_count),
                                        "tool_calls": tool_calls_log
                                    }
                                # --------------------------------------------
                                # CHIAMATA AL MODELLO
                                # --------------------------------------------0
                                completion = (
                                    llm.chat.completions.create(
                                        model=MODEL_NAME,
                                        messages=messages,
                                        tools=tools,
                                        tool_choice="auto",
                                        temperature=0.2
                                    )
                                )
                                message = (completion.choices[0].message)
                                finish_reason = (completion.choices[0].finish_reason)
                                # --------------------------------------------
                                # DEBUG
                                # --------------------------------------------
                                print("\n========== MODEL RESPONSE ==========", file=sys.stderr)
                                print("CONTENT:", repr(message.content), file=sys.stderr)
                                print("TOOL CALLS:", message.tool_calls, file=sys.stderr)
                                print("FINISH REASON:", finish_reason, file=sys.stderr)
                                print("====================================\n", file=sys.stderr)
                                # --------------------------------------------
                                # RISPOSTA FINALE
                                # --------------------------------------------
                                if not message.tool_calls:
                                    total_end = time.perf_counter()
                                    raw_final_message = (message.content or "")
                                    # Risposta troncata
                                    if finish_reason == "length":
                                        return {
                                            "question": question,
                                            "answer": None,
                                            "agent_completion": False,
                                            "error": ("Final response truncated"),
                                            "finish_reason": finish_reason,
                                            "raw_final_message": (raw_final_message),
                                            "latency_total": (total_end - total_start),
                                            "tool_calls_count": (tool_calls_count),
                                            "tool_calls": tool_calls_log
                                        }
                                    # ----------------------------------------
                                    # RECUPERO ULTIMO RISULTATO QUERY
                                    # ----------------------------------------
                                    final_output = None

                                    for tool_call in reversed(tool_calls_log):
                                        # Tool SQL di interrogazione
                                        if tool_call["tool"] == "mysql_execute_sql":
                                            output = (tool_call["output"])
                                            if (isinstance(output, dict) and output.get("success")is True):
                                                final_output = output
                                                break
                                        # Tool MongoDB di interrogazione
                                        if tool_call["tool"] in ("mongo_find_documents", "mongo_aggregate_documents", "mongo_find", "mongo_aggregate"):
                                            output = (tool_call["output"])
                                            if (isinstance(output, dict) and output.get("success") is True):
                                                final_output = output
                                                break
                                    # ----------------------------------------
                                    # NESSUNA QUERY VALIDA
                                    # ----------------------------------------
                                    if final_output is None:
                                        return {
                                            "question": question,
                                            "answer": None,
                                            "agent_completion": False,
                                            "error": ("No successful database query found"),
                                            "finish_reason": (finish_reason),
                                            "raw_final_message": (raw_final_message),
                                            "latency_total": (total_end - total_start),
                                            "tool_calls_count": (tool_calls_count),
                                            "tool_calls": (tool_calls_log)
                                        }
                                    # ----------------------------------------
                                    # RISULTATO AGENTE
                                    # ----------------------------------------
                                    answer = (
                                        final_output.get("rows", final_output.get("documents",[]))
                                    )
                                    return {
                                        "question": question,
                                        "answer": answer,
                                        "agent_completion": True,
                                        "finish_reason": finish_reason,
                                        "final_message": (raw_final_message),
                                        "latency_total": (total_end - total_start),
                                        "tool_calls_count": (tool_calls_count),
                                        "tool_calls": tool_calls_log
                                    }
                                # ====================================================
                                # AGGIUNTA MESSAGGIO DEL MODELLO
                                # ====================================================
                                messages.append(message)
                                for tool_call in message.tool_calls:
                                    exposed_tool_name = (tool_call.function.name)
                                    # --------------------------------------------
                                    # Individuiamo DBMS e nome reale del tool
                                    # --------------------------------------------
                                    if exposed_tool_name.startswith("mysql_"):
                                        dbms = "mysql"
                                        real_tool_name = (exposed_tool_name[len("mysql_"):])
                                        mcp_client = mysql_client
                                    elif exposed_tool_name.startswith("mongo_"):
                                        dbms = "mongo"
                                        real_tool_name = (exposed_tool_name[len("mongo_"):])
                                        mcp_client = mongo_client
                                    else:
                                        raise ValueError(f"Unknown tool: {exposed_tool_name}")
                                    # --------------------------------------------
                                    # Parsing argomenti
                                    # --------------------------------------------
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
                                            "error": (
                                                "Invalid tool arguments"
                                            ),
                                            "latency_total": (
                                                total_end - total_start
                                            ),
                                            "tool_calls_count": (
                                                tool_calls_count
                                            ),
                                            "tool_calls": (
                                                tool_calls_log
                                            )
                                        }

                                    tool_calls_count += 1
                                    current_tool_number = tool_calls_count
                                    # ============================================================
                                    # CONTROLLO DBMS / DATABASE
                                    # ============================================================
                                    is_valid, validation_error = validate_database_access(dbms, tool_arguments)
                                    if not is_valid:
                                        # NON eseguiamo il tool. Informiamo invece il modello dell'errore.
                                        print(f"[CROSS-DB VALIDATION ERROR] {validation_error}", file=sys.stderr)
                                        tool_output = json.dumps({
                                            "success": False,
                                            "error": validation_error,
                                            "type": "database_routing_error"
                                        })
                                        tool_latency = 0.0
                                    else:
                                        # --------------------------------------------
                                        # ESECUZIONE TOOL
                                        # --------------------------------------------
                                        tool_start = time.perf_counter()
                                        result = await mcp_client.call_tool(real_tool_name, arguments=tool_arguments)
                                        tool_end = time.perf_counter()
                                        tool_latency = (tool_end - tool_start)
                                        # --------------------------------------------
                                        # ESTRAZIONE OUTPUT
                                        # --------------------------------------------
                                        tool_content = []
                                        for content in result.content:
                                            if hasattr(content, "text"):
                                                tool_content.append(content.text)
                                            else:
                                                tool_content.append(str(content))
                                        tool_output = "\n".join(tool_content)

                                    # --------------------------------------------
                                    # PARSING OUTPUT
                                    # --------------------------------------------
                                    parsed_tool_output = (parse_tool_output(tool_output))
                                    # --------------------------------------------
                                    # LOG
                                    # --------------------------------------------
                                    tool_calls_log.append({
                                        "tool_call_number": current_tool_number,
                                        "tool": exposed_tool_name,
                                        "dbms": dbms,
                                        "arguments": tool_arguments,
                                        "output": parsed_tool_output,
                                        "raw_output": tool_output,
                                        "latency": tool_latency
                                    })
                                    # --------------------------------------------
                                    # OUTPUT VISIBILE AL MODELLO
                                    # --------------------------------------------
                                    tool_message_content = (
                                        f"TOOL_CALL_{current_tool_number}\n"
                                        f"{tool_output}"
                                    )
                                    messages.append({
                                        "role": "tool",
                                        "tool_call_id": (tool_call.id),
                                        "content": (tool_message_content)
                                    })
        # ========================================================
        # GESTIONE ERRORI GENERALI DELL'AGENTE
        # ========================================================
        except Exception as e:
            total_end = time.perf_counter()
            print("\n========== AGENT ERROR ==========", file=sys.stderr)
            print(f"{type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc()
            print("=================================\n", file=sys.stderr)
            return {
                "question": question,
                "answer": None,
                "agent_completion": False,
                "error": f"{type(e).__name__}: {str(e)}",
                "latency_total": total_end - total_start,
                "tool_calls_count": tool_calls_count,
                "tool_calls": tool_calls_log
            }

# ============================================================
# TEST LOCALE
# ============================================================

if __name__ == "__main__":
    import asyncio
    agent = Agent()
    question = ("Quanti aeroporti ci sono in Italia?")
    result = asyncio.run(agent.run(question))
    print("\n========== RISULTATO ==========")
    print("Domanda:", result["question"])
    print("Risposta:", result["answer"])
    print("Completato:", result["agent_completion"])
    print("Tool calls:", result["tool_calls_count"])
    print("Final message:", result.get("final_message"))
    print("Latenza:", result["latency_total"])