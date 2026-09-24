"""
tools_MONGO.py
Funzioni per l'interrogazione di database MongoDB.
Le funzioni vengono esposte tramite MCP server.
"""

from pymongo import MongoClient
from pymongo.errors import PyMongoError
from datetime import datetime
class MongoDatabaseTools:
    def __init__(self, host = "localhost", port = 27017):
        self.host = host
        self.port = port

    # ----------------- Connessione
    def _get_connection(self):
        """
        Crea una connessione a MongoDB
        """
        return MongoClient(f"mongodb://{self.host}:{self.port}/")

    def _get_database(self, database):
        """
        Restituisce il database MongoDB specificato
        """
        client = self._get_connection()
        return client[database]

    # ----------------- Metodo utility per convertire stringhe ISO rappresentati delle date in datetime python
    def _convert_dates(self, obj):
        """
        Converte ricorsivamente le stringhe ISO in datetime Python.
        Per es.
            "2026-01-01" -> datetime(2026, 01, 01)
        """
        if isinstance(obj, dict):
            return {
                key: self._convert_dates(value)
                for key, value in obj.items()
            }
        elif isinstance(obj, list):
            return [
                self._convert_dates(value)
                for value in obj
            ]

        elif isinstance(obj, str): #data semplice
            try:
                return datetime.strptime(obj, "%Y-%m-%d")
            except ValueError:
                pass

            #Data + ora ISO
            try:
                return datetime.fromisoformat(obj.replace("Z","+00:00"))
            except ValueError:
                pass
        return obj  
    
    # ----------------- Insieme di collezioni del database
    def list_collections(self, database):
        """
        Restituisce l'insieme di collection contenute nel database MongoDB specificato
        """
        client = None
        try:
            client = self._get_connection()
            db = client[database]

            collections = db.list_collection_names()
            collections.sort()
            return {
                "success": True,
                "database": database,
                "collections": collections                        
            }
        except PyMongoError as e:
            return{
                "success": False,
                "database": database,
                "error_type": "MONGODB_CONNECTION_ERROR",
                "error": str(e)
            }
        finally:
            if client is not None:
                client.close()

    # ----------------- Struttua di una collezione
    def describe_collection(self, database, collection_name, sample_size = 20):
        """
        Restituisce la struttura approssimata di una collezione di MongoDB analizzando un campione di documenti
        Dato che MongoDB è non relazionale, la struttura non è necessariamente costante per una stessa collezione.
        """
        client = None
        try:
            client = self._get_connection()
            db = client[database]
            collections = db.list_collection_names()
            if collection_name not in collections:
                return{
                    "success": False,
                    "database": database,
                    "collection": collection_name,
                    "error_type": "COLLECTION_NOT_FOUND",
                    "error": (f"Collection '{collection_name}' does not exist in database '{database}'."),
                    "action_required": ("Use list_collections to verify the correct collection name.")
                }

            documents = list(db[collection_name].find({}).limit(sample_size))
            if not documents:
                return {
                    "success":True,
                    "database":database,
                    "collection":collection_name,
                    "fields":[],
                    "document_count":0
                }
            fields = {}

            for document in documents:
                for field_name, value in document.items():
                    value_type = type(value).__name__
                    if field_name not in fields:
                        fields[field_name] = set()
                    fields[field_name].add(value_type)
            schema = []

            for field_name, types in fields.items():
                schema.append({
                    "name":field_name,
                    "types":sorted(types)
                })
            schema.sort(key = lambda x: x["name"])

            return{
                "success": True,
                "database": database,
                "collection": collection_name,
                "fields": schema,
                "sample_size": len(documents)
            }
        except PyMongoError as e:
            return {
                "success": False,
                "database": database,
                "collection": collection_name,
                "error_type": "MONGODB_ERROR",
                "error": str(e)
            }
        finally: 
            if client is not None:
                client.close()

    # ----------------- Esempi di documenti
    def sample_documents(self, database, collection_name, limit = 10):
        """
        Restituisce un insieme di 10 documenti di esempio della collection specificata
        """
        client = None
        try:
            client = self._get_connection()
            db = client[database]
            collections = db.list_collection_names()

            if collection_name not in collections:
                return {
                    "success": False,
                    "database": database,
                    "collection": collection_name,
                    "error": (f"Collection '{collection_name}' does not exist")
                }

            documents = list(
                db[collection_name]
                .find({})
                .limit(limit)
            )
            for document in documents:
                if "_id" in document:
                    document["_id"] = str(document["_id"])

            return {
                "success": True,
                "database": database,
                "collection": collection_name,
                "documents": documents
            }

        except PyMongoError as e:
            return {
                "success": False,
                "database": database,
                "collection": collection_name,
                "error_type": "MONGODB_ERROR",
                "error": str(e)
            }
        finally:
            if client is not None:
                client.close()

    # ----------------- Valori distinti di un field
    def get_distinct_values(self, database, collection_name, field_name):
        """
        Restituisci valori distinti presenti in un determinato campo della collezione
        """
        client = None
        try:
            client = self._get_connection()
            db = client[database]
            collections = db.list_collection_names()
            if collection_name not in collections:
                return {
                    "success": False,
                    "database": database,
                    "collection": collection_name,
                    "error":(f"Collection '{collection_name}' does not exist")
                }
            values = db[collection_name].distinct(field_name)

            values = [str(value)
                      if value.__class__.__name__ == "ObjectId"
                      else value
                      for value in values
                     ]
            return {
                "success": True,
                "database": database,
                "collection": collection_name,
                "field": field_name,
                "values": values
            }
        except PyMongoError as e:
            return{
                "success": False,
                "database": database,
                "collection": collection_name,
                "field": field_name,
                "error_type": "MONGODB_ERROR",
                "error": str(e)
            }
        finally:
            if client is not None:
                client.close()

    # ----------------- Esecuzione di una query find
    def find_documents(self, database, collection_name, filter={}, projection = None):
        """
        Esecuzione di una query MongoDB find
        """
        client = None
        try:
            client = self._get_connection()
            db = client[database]

            collections = db.list_collection_names()
            if collection_name not in collections:
                return{
                    "success": False,
                    "database": database,
                    "collection": collection_name,
                    "error_type": "COLLECTION_NOT_FOUND",
                    "error": (f"Collection '{collection_name}' does not exist.")
                }

            mongo_filter = self._convert_dates(filter) #conversione stringhe delle date in datetime Python
            
            cursor = db[collection_name].find(
                mongo_filter,
                projection
            )

            documents = list(cursor)
            for document in documents:
                if "_id" in document and document["_id"] is not None:
                    document["_id"] = str(document["_id"])

            return{
                "success": True,
                "database": database,
                "collection": collection_name,
                "filter": filter,
                "row_count": len(documents),
                "documents": documents
            }
        except PyMongoError as e:
            return {
                "success": False,
                "database": database,
                "collection": collection_name,
                "filter": filter,
                "error_type": "MONGODB_QUERY_ERROR",
                "error": str(e)
            }
        finally:
            if client is not None:
                client.close()

    # ----------------- Pipeline per l'aggregazione
    def aggregate_documents(self, database, collection_name, pipeline):
        """
        Esegue una MongoDB aggregation pipeline.
        La pipeline deve essere una lista di stage MongoDB, ad esempio:
        [
            {
                "$group":{
                        "_id":"$stato",
                        "media":{"$avg": "$temperatura"}
                         }
            }
        ]
        """
        client = None

        try:
            client = self._get_connection()
            db = client[database]
            collections = db.list_collection_names()

            if collection_name not in collections:
                return{
                    "success": False,
                    "database": database,
                    "collection": collection_name,
                    "error_type": "COLLECTION_NOT_FOUND",
                    "error":(f"Collection '{collection_name}' does not exist")
                }
            
            mongo_pipeline = self._convert_dates(pipeline) #conversione stringhe delle date in datetime Python

            documents = list(db[collection_name].aggregate(mongo_pipeline))
            for document in documents:
                if "_id" in document and document["_id"] is not None:
                    document["_id"] = str(document["_id"])
            return{
                "success": True,
                "database": database,
                "collection": collection_name,
                "pipeline": pipeline,
                "row_count": len(documents),
                "documents": documents
            }
        except PyMongoError as e:
            return{
                "success": False,
                "database": database,
                "collection": collection_name,
                "error_type": "MONGODB_AGGREGATION_ERROR",
                "error": str(e),
                "action_required": ("Inspect the collection structure and correct the aggregation pipeline")
            }

        finally:
            if client is not None:
                client.close()



