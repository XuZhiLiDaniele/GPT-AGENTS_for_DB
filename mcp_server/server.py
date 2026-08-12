import os
import sys
from mcp.server import MCPServer
from client.tools import DatabaseTools
print(
    f"[MCP SERVER] Python: {sys.executable}",
    file = sys.stderr
)
print(
    f"[MCP SERVER] CWD: {os.getcwd()}",
    file=sys.stderr
    )

# ============Database================
db = DatabaseTools(
    host="localhost",
    port=3306,
    user="root",
    password="pastacontonno123",
    database="voli"
)

# ============MCP Server================
mcp = MCPServer("Voli Database")

# ============Lista dei tool================
@mcp.tool() #tool per l'elenco delle tabelle del database.
def list_tables() -> dict:
    """
    Restituisce l'elenco delle tabelle presenti nel database Voli
    """
    return db.list_tables()

@mcp.tool() #tool descrizione della tabella specificata.
def describe_table(table_name:str) -> dict:
    """
    Si restituisce una descrizione dettagliata dello schema della tabella specificata in input
    Vengono quindi fornite informazioni come il nome di ogni colonna, il tipo etc...
    """
    return db.describe_table(table_name)

@mcp.tool() #tool per ottenere le chiavi primarie di ogni tabella del db
def get_primary_keys() -> dict:
    """
    Restituisce le chiavi primarie di tutte le tabelle nel database
    """
    return db.get_primary_keys()

@mcp.tool() 
def get_foreign_keys() -> dict:
    """
    Restituisce le chiavi esterne di tutte le tabelle nel database.
    """
    return db.get_foreign_keys()

@mcp.tool()
def sample_rows(table_name:str) -> dict:
    """
    Restituisce 5 istanze che facciano da esempio per la tabella specificata in input
    """
    return db.sample_rows(table_name)

@mcp.tool()
def execute_sql(query:str):
    """
    Esegue una query SQL fornita sotto forma di stringa dall'agente e/o utente
    Sono consentite solo query SELECT o WITH
    """
    return db.execute_sql(query)

# ============Avvio server================
if __name__=="__main__":
    mcp.run()