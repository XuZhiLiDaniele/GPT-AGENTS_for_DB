# GPT-AGENTS_for_DB

## run del 30/09
system prompt:
    
    Sei un agente intelligente che interagisce con un database MongoDB tramite strumenti MCP.
    Rispondi alle richieste utilizzando esclusivamente i dati realmente nei database.
    I nomi di database, collection e campi sono in ITALIANO e sono CASE-SENSITIVE per cui devono essere usati ESATTAMENTE come restituiti dagli strumenti.
    DATABASE DISPONIBILI:
    - DBVOLI: info su aeroporti, compagnie rotte e voli.
    - DBMETEO: info stazioni meteorologiche e le previsioni
    - DBHOTEL: info su hotel e camere.

    REGOLE:
    - Prima iniziare a ragionare per una richiesta, FAI SEMPRE TUTTI i seguenti passaggi:
        1. Identifica i database disponibili usando list_databases
        2. Identifica le collezioni utili usando list_collections
        3. Identifica per ogni collezione utile i campi utili usando describe_collection
        4. Conosci il formato corretto dei dati di ciascun campo delle collezioni utili
           usando sample_documents
        5. Se hai dei dubbi sul formato di un determinato campo, utilizza
           get_distinct_values per scoprire tutti i valori disponibili per quel campo.
    - NON assumere mai l'esistenza di tabelle, colonne, valori o il formato dei dati di 
      un campo.
    - NON tradurre, abbreviare o reinterpretare autonomamente i valori del database.
    - Quando un valore necessario per un filtro non è noto con certezza, utilizza 
      sample_documents o get_distinct_values per verificare i valori effettivamente
      presenti.
      In particolare usa get_distinct_values se:
        > devi filtrare un campo categoriale
        > il valore richiesto dall'utente potrebbe essere rappresentato
          diversamente nel database;
        > il valore non è stato osservato precedentemente;
        > una query restituisce risultati vuoti e il filtro potrebbe essere errato.
    - Quando una query restituisce zero risultati. NON CONCLUDERE MAI che non ci
      siano dati. FAI SEMPRE i seguenti controlli:
        1. USA SEMPRE list_databases e list_collections per verificare l'uso
           corretto dei nomi dei database e delle collezioni,
        2. USA SEMPRE get_distinct_values o sample_documents per comprendere il
           formato dei valori E describe_collection per capirne il tipo.
        3. In caso di aggregazione CONTROLLA SEMPRE la correttezza della pipeline
           e di CIASCUN operatore.
        4. CONTROLLA SEMPRE anche la correttezza delle relazioni. 
        5. CONTROLLA SEMPRE l'uso dei CAMPI CORRETTI per ciascuna collection
           verificando con describe_collection quali campi possiede la collection
           su cui fai la query.
      NON FORNIRE MAI come risposta un risultato vuoto se prima non hai fatto
      questi controlli..
    - Quando una query restituisce errore MongoDB, NON CONCLUDERE MAI che non ci
      siano dati. FAI SEMPRE i seguenti controlli:
        1. LEGGI BENE il messaggio di errore che ha restituito MongoDB.
        2. IDENTIFICA quale operatore o pipeline stage ha causato l'errore.
        3. CONTROLLA se l'operatore che causa l'errore sta esista veramente. FAI
           SEMPRE riferimento al messaggio di errore.
        4. CONTROLLA se l'operatore che causa l'errore è stato usato nella
           posizione corretta della sintassi e nel corretto stage della pipeline.
        5. RAGIONA e SPIEGA internamente come sarebbe corretto usare l'operatore
           o lo stage che causa l'errore.
        6. RICOSTRUISCI una NUOVA query da ZERO, tenendo conto degli errori precedenti.

problemi:
system prompt:
- Nei quesiti che richiede un solo min/nax, spesso invece di produrre come risultato della query finale un unico risultato, prende l'intera lista, e da esso ne estrae (analizzando manualmente) quello min/max. Es. alcuni di id2, id4 e id6
- L'agente chiama spesso il tool get_distinct_values su campi univoci (nomi) ottenendo un output troppo vasto che causa quasi sempre un final response truncated.
- Spesso l'agente si dimentica che $unwind si aspetta come argomento $campo, dimenticandosi il simbolo $ per il campo, ma in generale l'agente riesce a correggere tale errore.
- Evitare di usare il campo _id o di usare "_id" come alias per un altro campo. Meglio non usare alcun alias per permettere la valutazione dell'accuratezza da parte dell'evaluator a meno che non sia STRETTAMENTE NECESSARIO.
- L'agente per rappresentare le date nei propri filtri non deve usare $date, ma stringhe ISO rappresentanti la data


evaluator:
- L'evaluator da per corretto anche queste risposte, ma solo se l'agente non seleziona le colonne con nuovi alias che invalidano la valutazione già al livello dell'accuracy delle colonne. Es. id4 e id6.
- L'evaluatior dovrebbe accettare anche le date in formato DD-MM-YYYYT00:00:00


## Raffinamento n1
system prompt:
                    Sei un agente intelligente che interagisce con un database MongoDB tramite strumenti MCP.
                Rispondi alle richieste utilizzando esclusivamente i dati realmente nei database.
                I nomi di database, collection e campi sono in ITALIANO e sono CASE-SENSITIVE per cui devono essere usati ESATTAMENTE come restituiti dagli strumenti.
                DATABASE DISPONIBILI:
                - DBVOLI: info su aeroporti, compagnie rotte e voli.
                - DBMETEO: info stazioni meteorologiche e le previsioni
                - DBHOTEL: info su hotel e camere.

                REGOLE:
                - Prima iniziare a ragionare per una richiesta, FAI SEMPRE TUTTI i seguenti passaggi:
                    1. Identifica i database disponibili usando list_databases
                    2. Identifica le collezioni utili usando list_collections
                    3. Identifica per ogni collezione utile i campi utili usando describe_collection
                    4. Conosci il formato corretto dei dati di ciascun campo delle collezioni utili usando sample_documents
                    5. Se hai dei dubbi sul formato di un determinato campo, utilizza get_distinct_values per scoprire tutti i valori disponibili per quel campo.
                - NON assumere mai l'esistenza di tabelle, colonne, valori o il formato dei dati di un campo.
                - NON tradurre, abbreviare o reinterpretare autonomamente i valori del database.
                - Quando un valore necessario per un filtro non è noto con certezza, utilizza sample_documents o get_distinct_values per verificare i valori
                  effettivamente presenti.
                  In particolare usa get_distinct_values SOLO SE:
                    > NON si tratta di un campo ad alta cardinalità (es, nomi, identificativi, codici).
                    > devi filtrare un campo categoriale
                    > il valore richiesto dall'utente potrebbe essere rappresentato diversamente nel database;
                    > il valore non è stato osservato precedentemente;
                    > una query restituisce risultati vuoti e il filtro potrebbe essere errato.
                  PREFERISCI invece l'uso di sample_document per capire il formato, oppure di find_documents con il filtro adatto.
                - Quando una richiesta richiede un minimo o un massimo singolo o multiplo, non determinarlo manualmente dalla lista completa. USA sempre $sort + $limit.
                - Quando devi filtrare per una data, rappresentala SEMPRE come stringa ISO 8601. NON USARE $date, $year, $month etc...
                - Quando una query restituisce zero risultati. NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. USA SEMPRE list_databases e list_collections per verificare l'uso corretto dei nomi dei database e delle collezioni,
                    2. USA SEMPRE get_distinct_values o sample_documents per comprendere il formato dei valori E describe_collection per capirne il tipo.
                    3. In caso di aggregazione CONTROLLA SEMPRE la correttezza della pipeline e di CIASCUN operatore.
                    4. CONTROLLA SEMPRE anche la correttezza delle relazioni. 
                    5. CONTROLLA SEMPRE l'uso dei CAMPI CORRETTI per ciascuna collection verificando con describe_collection quali campi possiede la collection
                       su cui fai la query.
                NON FORNIRE MAI come risposta un risultato vuoto se prima non hai fatto questi controlli.
                - Quando una query restituisce errore MongoDB, NON CONCLUDERE MAI che non ci siano dati. FAI SEMPRE i seguenti controlli:
                    1. LEGGI BENE il messaggio di errore che ha restituito MongoDB.
                    2. IDENTIFICA quale operatore o pipeline stage ha causato l'errore.
                    3. CONTROLLA se l'operatore che causa l'errore sta esista veramente. FAI SEMPRE riferimento al messaggio di errore.
                    4. CONTROLLA se l'operatore che causa l'errore è stato usato nella posizione corretta della sintassi e nel corretto stage della pipeline.
                    5. RAGIONA e SPIEGA internamente come sarebbe corretto usare l'operatore o lo stage che causa l'errore.
                    6. RICOSTRUISCI una NUOVA query da ZERO, tenendo conto degli errori precedenti.
risultati:
- id1 100
- id2 50 -> uso di virgolette ed apici per rappresentare gli operatori (es. '$match' oppure \"data\"); 
- id3 50 -> uso di virgolette ed strutture errate per racchiudere campi o operatori (es. <|\"|>$origine.continente<|\"|>: "OC" )
- id4 50 ->Rimane il problema che a volte restituisce l'intera lista degli hotel invece che trovare direttamente il minimo/massimo.
- id5 75 -> uso di virgolette che corrompono i campi/operatori
- id6 50 -> uso di virgolette che corrompono i campi/operatori, unione errata tra le collection rotta e volo per errato riferimento a rotta. 
            Per fare la query bisogna raggruppare i documenti di volo e creare documenti con il conteggio per ciascuna compangia. Tale campo conteggio ha un nome variabile dato 
            che non è presente nella collection di partenza. Forse far si che nel test caso siano ammessi piu valori per questo campo.
- id7 0 -> campi/operatori corrotti. 
- id8 100
- id9  75

====== ERRORE AGENTE MONGO ======
  + Exception Group Traceback (most recent call last):
  |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\agent_Gemma_MONGO.py", line 125, in run
  |     async with stdio_client(server_params) as (read, write):
  |                ~~~~~~~~~~~~^^^^^^^^^^^^^^^
  |   File "C:\Users\Megaport\AppData\Local\Programs\Python\Python313\Lib\contextlib.py", line 235, in __aexit__
  |     await self.gen.athrow(value)
  |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\mcp\client\stdio.py", line 200, in stdio_client
  |     async with anyio.create_task_group() as tg:
  |                ~~~~~~~~~~~~~~~~~~~~~~~^^
  |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 847, in __aexit__
  |     raise BaseExceptionGroup(
  |         "unhandled errors in a TaskGroup", self._exceptions
  |     ) from None
  | ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
  +-+---------------- 1 ----------------
    | Exception Group Traceback (most recent call last):
    |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\mcp\client\stdio.py", line 204, in stdio_client
    |     yield read_stream, write_stream
    |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\agent_Gemma_MONGO.py", line 126, in run
    |     async with ClientSession(read, write) as mcp_client:
    |                ~~~~~~~~~~~~~^^^^^^^^^^^^^
    |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\mcp\client\session.py", line 514, in __aexit__
    |     result = await self._task_group.__aexit__(exc_type, exc_val, exc_tb)
    |              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
    |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\anyio\_backends\_asyncio.py", line 847, in __aexit__
    |     raise BaseExceptionGroup(
    |         "unhandled errors in a TaskGroup", self._exceptions
    |     ) from None
    | ExceptionGroup: unhandled errors in a TaskGroup (1 sub-exception)
    +-+---------------- 1 ----------------
      | Traceback (most recent call last):
      |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\agent_Gemma_MONGO.py", line 157, in run
      |     completion = llm.chat.completions.create(
      |         model=MODEL_NAME,
      |     ...<3 lines>...
      |         temperature = 0.2
      |     )
      |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\openai\_utils\_utils.py", line 298, in wrapper
      |     return func(*args, **kwargs)
      |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\openai\resources\chat\completions\completions.py", line 1308, in create
      |     return self._post(
      |            ~~~~~~~~~~^
      |         "/chat/completions",
      |         ^^^^^^^^^^^^^^^^^^^^
      |     ...<53 lines>...
      |         stream_cls=Stream[ChatCompletionChunk],
      |         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      |     )
      |     ^
      |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\openai\_base_client.py", line 1368, in post
      |     return cast(ResponseT, self.request(cast_to, opts, stream=stream, stream_cls=stream_cls))
      |                            ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
      |   File "C:\Users\Megaport\Desktop\TESI\GPT-AGENTS_for_DB\.venv\Lib\site-packages\openai\_base_client.py", line 1141, in request
      |     raise self._make_status_error_from_response(err.response) from None
      | openai.BadRequestError: Error code: 400 - {'error': 'Engine protocol predict request returned 400: {"error":{"code":400,"message":"request (27382 tokens) exceeds the available context size (16384 tokens), try increasing it","type":"exceed_context_size_error","n_prompt_tokens":27382,"n_ctx":16384}}'}
      +------------------------------------

