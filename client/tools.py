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
                 password = "pastacontonno123", 
                 ):
        self.config = {
            'host': host,
            'port': port,
            'user': user,
            'password': password,
        }

    ###############################################
    # Connessione
    ###############################################
    def _get_connection(self, database):
        """
        Crea una nuova connessione al db MySQL specificato.
        """
        config = self.config.copy()
        config["database"] = database
        return mysql.connector.connect(**config)

    ################################################
    # Esecuzione query
    ################################################
    def _execute_query(self, query, params=None, database=None):
        """
        Esegue una query SQL sul db specificato e restituisce:
            - Le colonne del risultato 
            - Le righe del risultato
            - Un messaggio di errore
        """
        connection = None
        cursor = None

        if database is None:
            return{ 
                "success": False,
                "error": "Database not specified."
            }

        try:
            connection = self._get_connection(database)
            cursor = connection.cursor(dictionary=True)
            cursor.execute(query, params)
            result = cursor.fetchall()
            columns = [column[0] for column in cursor.description]
            return{
                "success": True,
                "columns": columns,
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
    # Insieme di tabelle del database
    ################################################
    def list_tables(self, database):
        """
        Restituisce l'insieme di tabelle contenute nel database
        """
        query= """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                ORDER BY table_name
               """
        result = self._execute_query(query, database = database)
        
        if not result["success"]:
            return result
        
        table_names = [row["TABLE_NAME"]
                       for row in result["rows"]
                      ]
        return{
            "success": True,
            "tables": table_names
        }

    ################################################
    # Schema di una tabella
    ################################################
    def describe_table(self, database, table_name):
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
        
        result = self._execute_query(query, (table_name,), database = database)

        if not result["success"]:
            return result

        if not result["rows"]:
            return{
                "success": False,
                "database": database,
                "table": table_name,
                "error_type": "TABLE_NOT_FOUND",
                "error": (f"Table '{table_name}' does not exist"
                          f"in database '{database}'."),
                "action_required": ("Use list_tables to verify the correct table name")
            }
            
        return {
            "success": True,
            "database": database,
            "table": table_name,
            "schema": result["rows"]
        }
        
    ################################################
    # Esempi di righe di tabelle del db
    ################################################
    def sample_rows(self, database, table_name, limit=10):
        """
        Restituisce un esempio di righe da una tabella specificata.
        """
        tables_result = self.list_tables(database)
        if not tables_result["success"]:
            return tables_result
        if table_name not in tables_result["tables"]:
            return {
                "success": False,
                "error": f"Table '{table_name}' does not exist in the database."
            }
        query = f"""
                SELECT * 
                FROM `{table_name}`
                LIMIT %s;
                """
        result = self._execute_query(query, (limit,), database = database)

        if not result["success"]:
            return result
           
        return {
            "success": True,
            "table": table_name,
            "rows": result["rows"]
        }


    ################################################
    # Esempi di valori distinti di una determinata colonna di una tabella
    ################################################
    def get_distinct_values(self, database, table_name, column_name):
        """
        Restituisce i valori distinti presenti in una determinata colonna.
        """
        tables_result = self.list_tables(database)
        if not tables_result.get("success"):
            return tables_result
        if table_name not in tables_result["tables"]:
            return {
                "success": False,
                "error": f"Table '{table_name}' does not exits in '{database}'."
            }
        
        describe_result = self.describe_table(database, table_name)
        if not describe_result.get("success"):
            return describe_result
        columns = [col["COLUMN_NAME"] for col in describe_result["schema"]]
        if column_name not in columns:
            return {
                "success": False,
                "error": (
                    f"La colonna '{column_name}' non esiste "
                    f"nella tabella '{table_name}'."
                )
            }

        query = f"""
            SELECT DISTINCT `{column_name}`
            FROM `{table_name}`
            ORDER BY `{column_name}`;
        """
        result = self._execute_query(query,database=database)
        return result
    
    ###############################################
    # Esecuzione di query SQL
    ###############################################
    def execute_sql(self, database, query):
        """
        Esegue una query SQL fornita dall'utente.
        """
        query = query.strip()

        #Per ora permettiamo solo query SELECT e WITH 
        if not query.upper().startswith(("SELECT", "WITH")):
            return {
                "success": False,
                "database": database,
                "query": query,
                "error_type": "INVALID_QUERY_TYPE",
                "error": "Only SELECT queries are allowed.",
                "action_required": ("Generate a SELECT or WITH query")
            }

        result = self._execute_query(query, database = database)

        if result["success"]:
            return{
                "success": True,
                "database": database,
                "query": query,
                "columns": result["columns"],
                "row_count": len(result["rows"]),
                "rows": result["rows"]
            }
        #Query fallita
        return{
            "success": False,
            "database": database,
            "query": query,
            "error_type": "SQL_EXECUTION_ERROR",
            "error": result["error"],
            "action_required":("Do NOT repeat the failed SQL query. "
                               "Inspect the schema of the relevant table using describe_table before generating another SQL query. "
                               "Verify table and column names, then generate a corrected query.")
        }