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
            - I risultati della query
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
            
        return {
            "table": table_name,
            "schema": result["rows"]
        }
        
    ################################################
    # Ricerca di chiavi primarie del database
    ################################################
    def get_primary_keys(self, database):
        """
        Restituisce le chiavi primarie di tutte le tabelle nel database.
        """
        query = """
                SELECT table_name, column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = DATABASE() 
                    AND constraint_name = 'PRIMARY'
                ORDER BY table_name, ordinal_position;
                """
        result = self._execute_query(query, database = database)
        if not result["success"]:
            return result
        
        return {
            "primary_keys": result["rows"]
        }
        
    ################################################
    # Ricerca di relazioni del database
    ################################################
    def get_foreign_keys(self, database):
        """
        Restituisce le chiavi esterne di tutte le tabelle nel database.
        """
        query = """
                SELECT table_name, column_name, referenced_table_name, referenced_column_name
                FROM information_schema.key_column_usage
                WHERE table_schema = DATABASE() 
                AND referenced_table_name IS NOT NULL
                ORDER BY table_name;
                """
        result = self._execute_query(query, database = database)
        if not result["success"]:
            return result
        
        return {
            "foreign_keys": result["rows"]
        }
    
    ################################################
    # Esempi di righe di tabelle del db
    ################################################
    def sample_rows(self, database, table_name, limit=5):
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
                "error": "Only SELECT queries are allowed."
            }
        
        result = self._execute_query(query, database=database)

        return result
        