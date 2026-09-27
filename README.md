# GPT-AGENTS_for_DB
Progetto di tesi Xu Zhi Li Daniele 
Università di Bologna, Informatica per il Management.

## Required libraries:
- openai
- mysql-connector-python
- mcp
## Argomento della tesi
Sviluppare un agente accessibile che sfrutti come llm un agente locale, (gemma) e che si possa collegare ad un database. L'agente dovrà disporre degli strumenti per realizzare query al posto dell'utente per interagire con il database.

Fare un benchmark di piu llm locali, e confrontarli magari con llm commerciali non locali. Per testare capacità di aggregazione tra più database, prima relazione (es. mysql) e poi 

Sviluppare un piano di test per con query via via piu complesse.
Fare benchmark sulla latenza, ovvero velocità di esecuzione della query, e precisione, che può essere intesa come precisione rispetto alla ground truth, e la accuratezza, ovvero se almeno il formato è corretto (solo le colonne richieste).

# TO DO
- Implementare DB rimanenti ed adattare i tool e l'agente su query multi DB.
- Definire le query di testing adatte.
- Implementare testing autonomo e funzioni di memorizzazione delle metriche per valutare e confrontare il modello in termini di precisione, accuratezza e latenza.














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
- Quando un valore necessario per un filtro non è noto con certezza, utilizza sample_documents o get_distinct_values per verificare i valori effettivamente presenti.
  In particolare usa get_distinct values se:
 	> devi filtrare un campo categoriale
 	> il valore richiesto dall'utente potrebbe essere rappresentato diversamente nel database;
        > il valore non è stato osservato precedentemente;
        > una query restituisce risultati vuoti e il filtro potrebbe essere errato.
- 
