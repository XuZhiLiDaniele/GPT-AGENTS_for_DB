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
dbs = {
    "DBVOLI": DatabaseTools(
        host="localhost",
        port=3306,
        user="root",
        password="pastacontonno123",
    ),

    "DBMETEO": DatabaseTools(
        host="localhost",
        port=3306,
        user="root",
        password="pastacontonno123",
    ),

    "DBHOTEL": DatabaseTools(
        host="localhost",
        port=3306,
        user="root",
        password="pastacontonno123",
    )
}

# ============MCP Server================
mcp = MCPServer("Voli Database")

# ============Lista dei tool================

@mcp.tool() #tool per l'elenco delle tabelle del database.
def list_tables(database: str) -> dict:
    """
    Restituisce l'elenco delle tabelle presenti nel database specificato
    """
    if database not in dbs:
        return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].list_tables(database)

@mcp.tool() #tool descrizione della tabella specificata.
def describe_table(database:str, table_name:str) -> dict:
    """
    Si restituisce una descrizione dettagliata dello schema della tabella del database specificati in input
    Vengono quindi fornite informazioni come il nome di ogni colonna, il tipo etc...
    """
    if database not in dbs:
            return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].describe_table(database,table_name)

@mcp.tool() #tool per ottenere le chiavi primarie di ogni tabella del db
def get_primary_keys(database:str) -> dict:
    """
    Restituisce le chiavi primarie di tutte le tabelle del database specificato.
    """
    if database not in dbs:
                return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].get_primary_keys(database)

@mcp.tool() 
def get_foreign_keys(database:str) -> dict:
    """
    Restituisce le chiavi esterne di tutte le tabelle del database specificato
    """
    if database not in dbs:
                return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].get_foreign_keys(database)

@mcp.tool()
def sample_rows(database:str, table_name:str) -> dict:
    """
    Restituisce 5 istanze che facciano da esempio per la tabella del database specificati
    """
    if database not in dbs:
                return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].sample_rows(database, table_name)

@mcp.tool()
def execute_sql(database:str, query:str):
    """
    Esegue una query SQL fornita sotto forma di stringa dall'agente e/o utente sul database specificato
    Sono consentite solo query SELECT o WITH
    """
    if database not in dbs:
                return{ "error": f"Database '{database}' non disponibile"}
    return dbs[database].execute_sql(database, query)

# ============Avvio server================
if __name__=="__main__":
    mcp.run()