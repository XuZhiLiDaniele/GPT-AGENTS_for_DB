from tools_MONGO import MongoDatabaseTools
from pymongo import MongoClient
from datetime import datetime

client = MongoClient("mongodb://localhost:27017/")

db = client["DBVOLI"]

pipeline = [
    {
        "$lookup": {
            "from": "aeroporto",
            "localField": "iata_partenza",
            "foreignField": "iata",
            "as": "origine_details"
        }
    },
    {
        "$match": {
            "origine_details.continente": "OC"
        }
    }
]

result = list(db["rotta"].aggregate(pipeline))

print("ROW COUNT:", len(result))

for r in result:
    print({
        "partenza": r.get("iata_partenza"),
        "arrivo": r.get("iata_arrivo"),
        "origine_details": r.get("origine_details")
    })

client.close()