from tools import DatabaseTools
db = DatabaseTools(
                    host="localhost", 
                    user="root",
                    password="password",
                    database="test"
                    )
print(db.list_tables())
print()
print(db.describe_table("")) #inserire nome tabella da describere