from tools import DatabaseTools
db = DatabaseTools(
                    host="localhost",
                    port=3306,
                    user="root",
                    password="pastacontonno123"
                    )

print(db.get_distinct_values("DBVOLI","volo","modello_aereo"))