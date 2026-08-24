from tools import DatabaseTools
db = DatabaseTools(
                    host="localhost",
                    port=3306,
                    user="root",
                    password="pastacontonno123",
                    database="voli"
                    )
connection = db._get_connection()
if connection.is_connected():
    print("Connessione a db MySQL Voli riuscita!")
print()
tablesList = db.list_tables()
print("Tabelle contenute nel db in oggetto:")
for table in tablesList["tables"]:
    print(f"-{table}")
print()
print(db.describe_table("COMPAGNIA")) #inserire nome tabella da describere
connection.close()