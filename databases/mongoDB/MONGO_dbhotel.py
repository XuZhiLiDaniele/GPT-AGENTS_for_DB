import re
from pathlib import Path
from pymongo import MongoClient


# ============================================================
# CONFIGURAZIONE
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[2]
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "large" / "DB_HOTEL_l.sql")
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "medium" / "DB_HOTEL.sql")
SQL_FILE = (BASE_DIR / "databases" / "mysql" / "small" / "DB_HOTEL_s.sql")
print(SQL_FILE)

MONGO_URI = "mongodb://localhost:27017/"
#DB_NAME = "DBHOTEL_l" 
#DB_NAME = "DBHOTEL" 
DB_NAME = "DBHOTEL_s"


# ============================================================
# CONNESSIONE MONGODB
# ============================================================

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=3000
)

client.admin.command("ping")

db = client[DB_NAME]

print("Connessione a MongoDB riuscita.")


# ============================================================
# LETTURA FILE SQL
# ============================================================

with open(SQL_FILE, "r", encoding="utf-8") as f:
    sql = f.read()


# ============================================================
# FUNZIONE PER ESTRARRE TUTTI I BLOCCHI INSERT
# ============================================================

def extract_insert_blocks(table_name):
    """
    Estrae TUTTI i blocchi:

    INSERT INTO TABLE(...)
    VALUES
    (...),
    (...),
    ...;

    Non si limita al primo INSERT.
    """

    pattern = re.compile(
        r"INSERT\s+INTO\s+"
        + re.escape(table_name)
        + r"\s*\([^)]*\)\s*VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL
    )

    return pattern.findall(sql)


# ============================================================
# FUNZIONE PER ESTRARRE LE SINGOLE TUPLE
# ============================================================

def extract_rows(values_block):
    """
    Estrae le tuple contenute in un blocco VALUES.

    Esempio:

    ('401', 'Hotel', 'Suite', 300, 4, 'true'),
    ('402', 'Hotel', 'Standard', 200, 2, 'false')

    diventa:

    [
        "'401', 'Hotel', 'Suite', 300, 4, 'true'",
        "'402', 'Hotel', 'Standard', 200, 2, 'false'"
    ]

    Lo scanner tiene conto delle stringhe SQL.
    """

    rows = []

    in_quote = False
    escape = False
    depth = 0
    start = None

    for i, char in enumerate(values_block):

        if in_quote:

            if escape:
                escape = False

            elif char == "\\":
                escape = True

            elif char == "'":
                in_quote = False

            continue

        if char == "'":
            in_quote = True

        elif char == "(":

            if depth == 0:
                start = i + 1

            depth += 1

        elif char == ")":

            depth -= 1

            if depth == 0 and start is not None:
                rows.append(values_block[start:i])
                start = None

    return rows


# ============================================================
# PARSER DEI VALORI SQL
# ============================================================

def parse_sql_values(row):
    """
    Divide:

    'Hotel', 'Italia', 'Roma', 200, 'true'

    nei singoli valori.

    Gestisce le virgole contenute nelle stringhe.
    """

    values = []

    current = []
    in_quote = False
    escape = False

    i = 0

    while i < len(row):

        char = row[i]

        if in_quote:

            if escape:
                current.append(char)
                escape = False

            elif char == "\\":
                escape = True

            elif char == "'":

                # Gestione SQL di ''
                if i + 1 < len(row) and row[i + 1] == "'":
                    current.append("'")
                    i += 1
                else:
                    in_quote = False

            else:
                current.append(char)

        else:

            if char == "'":
                in_quote = True

            elif char == ",":
                values.append("".join(current).strip())
                current = []

            else:
                current.append(char)

        i += 1

    values.append("".join(current).strip())

    return values


# ============================================================
# ESTRAZIONE HOTEL
# ============================================================

hotel_blocks = extract_insert_blocks("HOTEL")

hotel_rows = []

for block in hotel_blocks:
    hotel_rows.extend(extract_rows(block))

print("\n================ HOTEL ================")
print("Blocchi INSERT trovati:", len(hotel_blocks))
print("Hotel estratti:", len(hotel_rows))


# ============================================================
# ESTRAZIONE CAMERE
# ============================================================

room_blocks = extract_insert_blocks("CAMERA")

room_rows = []

for block in room_blocks:
    room_rows.extend(extract_rows(block))

print("\n================ CAMERE ================")
print("Blocchi INSERT trovati:", len(room_blocks))
print("Camere estratte:", len(room_rows))


# ============================================================
# CONVERSIONE HOTEL → DOCUMENTI MONGODB
# ============================================================

hotel_documents = []

for row in hotel_rows:

    values = parse_sql_values(row)

    if len(values) != 5:
        print("ATTENZIONE: riga HOTEL non valida:")
        print(row)
        continue

    nome = values[0]
    stato = values[1]
    citta = values[2]
    indirizzo = values[3]
    stelle = int(values[4])

    hotel_documents.append({
        "nome": nome,
        "stato": stato,
        "citta": citta,
        "indirizzo": indirizzo,
        "stelle": stelle
    })


# ============================================================
# CONVERSIONE CAMERE → DOCUMENTI MONGODB
# ============================================================

room_documents = []

for row in room_rows:

    values = parse_sql_values(row)

    if len(values) != 6:
        print("ATTENZIONE: riga CAMERA non valida:")
        print(row)
        continue

    numero = values[0]
    hotel = values[1]
    categoria = values[2]
    prezzo = int(values[3])
    max_ospiti = int(values[4])
    disponibilita = values[5]

    room_documents.append({
        "numero": numero,
        "hotel": hotel,
        "categoria": categoria,
        "prezzo": prezzo,
        "max_ospiti": max_ospiti,
        "disponibilita": disponibilita
    })


# ============================================================
# RESET COLLECTION
# ============================================================

db.hotel.drop()
db.camera.drop()


# ============================================================
# INSERIMENTO HOTEL
# ============================================================

if hotel_documents:

    db.hotel.insert_many(
        hotel_documents,
        ordered=True
    )

# ============================================================
# INSERIMENTO CAMERE
# ============================================================

if room_documents:

    db.camera.insert_many(
        room_documents,
        ordered=True
    )

# ============================================================
# INDICI
# ============================================================

db.hotel.create_index(
    [("nome", 1)],
    unique=True
)

db.camera.create_index(
    [
        ("hotel", 1),
        ("numero", 1)
    ],
    unique=True
)

db.camera.create_index(
    [("hotel", 1)]
)

db.camera.create_index(
    [("categoria", 1)]
)

db.camera.create_index(
    [("prezzo", 1)]
)

db.camera.create_index(
    [("disponibilita", 1)]
)


# ============================================================
# VERIFICA FINALE
# ============================================================

print("\n===================================")
print("IMPORTAZIONE COMPLETATA")
print("===================================")

print(f"Hotel : {db.hotel.count_documents({})}")
print(f"Camere : {db.camera.count_documents({})}")

print("\nCollection MongoDB:")

for collection in db.list_collection_names():
    print(f"  - {collection}")

client.close()

print("\nConnessione MongoDB chiusa.")
