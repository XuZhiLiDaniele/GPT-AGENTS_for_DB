"""
tools.py

Script contenente le funzioni per l'interrogazione di un database MySQL 
Dovranno essere esposte tramite dei MCP servers

"""

import mysql.connector
from mysql.connector import Error

class DatabaseTools:
    def __init__(self, 
                 host="localHost", 
                 port = 3306,
                 user = "root", 
                 password = "password", 
                 database = "test"
                 ):
        self.config = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
            'database': database
        }

###############################################
# Connessione
###############################################
def _get_connection(self):
    """
    Crea una nuova connessione al db MySQL.
    """
    return mysql.connector.connect(**self.config)

################################################
# Esecuzione query
################################################
def _execute_query(self, query, params=None):
    """
    Esegue una query SQL e restituisce:
        - I risultati della query
        - Un messaggio di errore
    """
    connection = None
    cursor = None

    try:
        connection = self._get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(query, params)
        connection.commit()
        result = cursor.fetchall()
        return{
            "success": True,
            "rows": result
        }
    
    except Error as e:
        return{
            "success": False,
            "error": str(e)
        }

    finally:
        if cursor is not None: 
            cursor.close()
        if connection is not None and connection.is_connected():
            connection.close()

    ################################################
    # Elenco delle tabelle
    ################################################
    def list_tables(self):
        """
        Restituisce l'elenco delle tabelle nel database.
        """
        query = """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name;
                """
        result = self._execute_query(query)

        if not result["success"]:
            return result
        tables = [ row["table_name"] for row in result["rows"]]
        return {
            "success": True,
            "tables": tables
        }
    
    ################################################
    # Schema di una tabella
    ################################################
    def describe_table(self, table_name):
        """
        Restituisce lo schema di una tabella specificata.
        """
        query = """
                SELECT column_name, data_type, is_nullable, column_key, column_default
                FROM information_schema.columns
                WHERE table_schema = DATABASE() 
                      AND table_name = %s
                ORDER BY ordinal_position;
                """
        
        result = self._execute_query(query, (table_name,))

        if not result["success"]:
            return result
        
        return {
            "success": True,
            "table": table_name,
            "schema": result["rows"]
        }