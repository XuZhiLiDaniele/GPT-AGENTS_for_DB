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
    Restituisce i valori distinti presenti in un determinato field
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}

    return dbs[database].get_distinct_values(database, collection_name, field_name)

# ----------------- FIND DOCUMENTS
@mcp.tool()
def find_documents(database: str, collection_name: str, filter: dict | None = None, projection: dict | None = None) -> dict:
    """
    Esegue una query MongoDB find() sulla collezione specificata
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}

    return dbs[database].find_documents(database, collection_name, filter, projection)

# ----------------- AGGREGATE
@mcp.tool()
def aggregate_documents(database: str, collection_name: str, pipeline: list) -> dict:
    """
    Esegue una MongoDB aggregation pipeline
    """
    if database not in dbs:
        return{"error": f"Database '{database}' non disponibile"}
    
    return dbs[database].aggregate_documents(database, collection_name, pipeline)

# ----------------- AVVIO SERVER
if __name__ == "__main__":
    mcp.run()