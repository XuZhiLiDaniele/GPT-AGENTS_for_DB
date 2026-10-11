"""
server_mongo.py
MCP server per l'interrogazione di database MongoDB
"""
import os
import sys
from mcp.server import MCPServer
from client.tools_MONGO import MongoDatabaseTools

print(f"[MCP MONGO SERVER] Python: {sys.executable}", file=sys.stderr)
print(f"[MCP MONGO SERVER] CWD: {os.getcwd()}", file=sys.stderr)

# -----------------
dbs = {
    "DBVOLI":MongoDatabaseTools(host="localhost",
                                port=27017),
    "DBMETEO":MongoDatabaseTools(host="localhost",
                                port=27017),
    "DBHOTEL":MongoDatabaseTools(host="localhost",
                                port=27017)                                                        
    }
mcp = MCPServer("MongoDB Database")
# ----------------- LIST DATABASES
@mcp.tool()
def list_databases() -> dict:
    """
    Restituisce l'elenco dei database MongoDB su cui fare le query
    """
    return{
        "success": True,
        "databases": ["DBVOLI", "DBMETEO", "DBHOTEL"]
    }
# ----------------- LIST COLLECTIONS
@mcp.tool()
def list_collections(database: str) -> dict:
    """
    Restituisce l'elenco delle collection presenti nel database MongoDB specificato
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}
    
    return dbs[database].list_collections(database)

# ----------------- DESCRIBE COLLECTION
@mcp.tool()
def describe_collection(database: str, collection_name: str, sample_size: int = 20) -> dict:
    """
    Descrive la struttura osservata di una collezione MongoDB analizzando un campione di documenti
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}
    
    return dbs[database].describe_collection(database, collection_name, sample_size)

# ----------------- SAMPLE DOCUMENTS
@mcp.tool()
def sample_documents(database: str, collection_name: str, limit: int = 10) -> dict:
    """
    Restituisce alcuni documenti di esempio della collection specificata
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}
    
    return dbs[database].sample_documents(database, collection_name, limit)

# ----------------- DISTINCT VALUES
@mcp.tool()
def get_distinct_values(database: str, collection_name: str, field_name: str) -> dict:
    """
    Restituisce 10 valori distinti presenti in un determinato field
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}

    return dbs[database].get_distinct_values(database, collection_name, field_name)

# ----------------- FIND DOCUMENTS
@mcp.tool()
def find_documents(database: str, collection_name: str, filter: dict = {}, projection: dict = {}) -> dict:
    """
    Esegue db[collection_name].find(filter, projection).

    PARAMETRI:
    - database: nome del database MongoDB.
    - collection_name: nome della collection.
    - filter: normale oggetto JSON contenente il filtro MongoDB.
    - projection: normale oggetto JSON contenente la proiezione MongoDB.
    Il parametro filter deve essere un normale oggetto JSON MongoDB.

    Esempi:
    {"citta": "Pechino"}
    {"stelle": 5}
    {"temperatura": {"$lt": 30}}
    {"temperatura": {"$gte": 10, "$lt": 35}}

    I nomi dei campi devono essere scritti esattamente come nello schema.
    Gli operatori MongoDB ($lt, $gt, $gte, $lte, $eq, ecc.)
    devono essere chiavi dell'oggetto.

    NON aggiungere virgolette o backslash ai nomi dei campi.
    """
    if database not in dbs:
        return {
            "success": False,
            "database": database,
            "collection": collection_name,
            "error_type": "DATABASE_NOT_FOUND",
            "error": f"Database '{database}' non disponibile"
        }

    return dbs[database].find_documents(database, collection_name, filter, projection)

# ----------------- AGGREGATE
@mcp.tool()
def aggregate_documents(database: str, collection_name: str, pipeline: list) -> dict:
    """
    Esegue una MongoDB aggregation pipeline
     La pipeline deve essere una lista di normali oggetti JSON MongoDB.

    ESEMPIO: 
    "$group": {
        "_id": "$stato",
        "media_temperatura": {
            "$avg": "$temperatura"
        }
    }

    REGOLE IMPORTANTI:
    - Gli operatori MongoDB devono essere usati come CHIAVI.
    - Non aggiungere virgolette o backslash artificiali ai nomi dei campi.
    - I riferimenti ai campi nelle aggregation usano la sintassi MongoDB, ad esempio "$nomeCampo".
    - Non creare strutture intermedie con "valore", "type" o "str".
    """
    if database not in dbs:
        return {
            "success": False,
            "database": database,
            "collection": collection_name,
            "error_type": "DATABASE_NOT_FOUND",
            "error": f"Database '{database}' non disponibile"
        }
    
    return dbs[database].aggregate_documents(database, collection_name, pipeline)

# ----------------- AVVIO SERVER
if __name__ == "__main__":
    mcp.run()