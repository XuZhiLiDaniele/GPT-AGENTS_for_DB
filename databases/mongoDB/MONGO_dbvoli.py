import re
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient


# ============================================================
# CONFIGURAZIONE
# ============================================================
BASE_DIR = Path(__file__).resolve().parents[2]
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "large" / "DB_VOLI_l.sql")
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "medium" / "DB_VOLI.sql")
SQL_FILE = (BASE_DIR / "databases" / "mysql" / "small" / "DB_VOLI_s.sql")

MONGO_URI = "mongodb://localhost:27017/"
#DATABASE_NAME = "DBVOLI_l"
#DATABASE_NAME = "DBVOLI"
DATABASE_NAME = "DBVOLI_s"

# ============================================================
# LETTURA FILE SQL
# ============================================================

print("Lettura del file SQL...")

with open(SQL_FILE, "r", encoding="utf-8") as file:
    sql = file.read()


# ============================================================
# CONNESSIONE MONGODB
# ============================================================

client = MongoClient(
    MONGO_URI,
    serverSelectionTimeoutMS=3000
)

client.server_info()

db = client[DATABASE_NAME]

print("Connessione MongoDB OK.")


# ============================================================
# PULIZIA DATABASE
# ============================================================

print("Pulizia delle collection esistenti...")

for collection in [
    "aeroporto",
    "compagnia",
    "rotta",
    "volo"
]:
    db.drop_collection(collection)


# ============================================================
# FUNZIONE PER ESTRARRE UNA SEZIONE INSERT
# ============================================================

def extract_insert(table_name):
    """
    Estrae il blocco:

    INSERT INTO TABLE(...)
    VALUES
    (...),
    (...),
    ...;

    e restituisce una lista di tuple.
    """

    pattern = (
        r"INSERT\s+INTO\s+"
        + re.escape(table_name)
        + r"\s*\([^;]+?\)\s*VALUES\s*(.*?);"
    )

    match = re.search(
        pattern,
        sql,
        re.IGNORECASE | re.DOTALL
    )

    if not match:
        raise ValueError(
            f"INSERT INTO {table_name} non trovato."
        )

    values_block = match.group(1)

    # Trova tutte le parentesi dei VALUES
    rows = re.findall(
        r"\((.*?)\)",
        values_block,
        re.DOTALL
    )

    return rows


# ============================================================
# PARSER DI UNA RIGA SQL
# ============================================================

def parse_sql_row(row):
    """
    Trasforma:

    'ATL', 'Amsterdam', 'EU', 10.5, 3

    in:

    ['ATL', 'Amsterdam', 'EU', 10.5, 3]
    """

    values = []

    current = ""
    inside_string = False
    escape = False

    for char in row:

        if escape:
            current += char
            escape = False
            continue

        if char == "\\" and inside_string:
            escape = True
            current += char
            continue

        if char == "'":
            inside_string = not inside_string
            continue

        if char == "," and not inside_string:
            values.append(current.strip())
            current = ""
        else:
            current += char

    if current.strip():
        values.append(current.strip())

    return [
        convert_sql_value(value)
        for value in values
    ]


# ============================================================
# CONVERSIONE VALORI SQL → PYTHON
# ============================================================

def convert_sql_value(value):

    value = value.strip()

    if value.upper() == "NULL":
        return None

    # Numeri interi
    if re.fullmatch(r"-?\d+", value):
        return int(value)

    # Numeri decimali
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)

    return value


# ============================================================
# AEROPORTI
# ============================================================

print("\nImportazione AEROPORTI...")

airport_rows = extract_insert("AEROPORTO")

aeroporto = []

for row in airport_rows:

    values = parse_sql_row(row)

    ist_aeroporto = {
        "iata": values[0],
        "nome": values[1],
        "continente": values[2],
        "stato": values[3],
        "citta": values[4],
        "passeggeri": values[5],
        "corsie": values[6]
    }

    aeroporto.append(ist_aeroporto)


if aeroporto:
    db.aeroporto.insert_many(aeroporto)

print(f"Aeroporti importati: {len(aeroporto)}")


# ============================================================
# COMPAGNIE
# ============================================================

print("\nImportazione COMPAGNIE...")

company_rows = extract_insert("COMPAGNIA")

compagnia = []

for row in company_rows:

    values = parse_sql_row(row)

    ist_compagnia = {
        "nome": values[0],
        "main_hub": values[1]
    }

    compagnia.append(ist_compagnia)


if compagnia:
    db.compagnia.insert_many(compagnia)

print(f"Compagnie importate: {len(compagnia)}")


# ============================================================
# ROTTE
# ============================================================

print("\nImportazione ROTTE...")

route_rows = extract_insert("ROTTA")

rotta = []

for index, row in enumerate(route_rows, start=1):

    values = parse_sql_row(row)

    ist_rotta = {
        "id": index,
        "iata_partenza": values[0],
        "iata_arrivo": values[1],
        "compagnia": values[2]
    }

    rotta.append(ist_rotta)


if rotta:
    db.rotta.insert_many(rotta)

print(f"Rotte importate: {len(rotta)}")


# ============================================================
# VOLI
# ============================================================

print("\nImportazione VOLI...")

flight_rows = extract_insert("VOLO")

volo = []

for index, row in enumerate(flight_rows, start=1):

    values = parse_sql_row(row)

    # Timestamp MySQL:
    # YYYY-MM-DD HH:MM

    timestamp = datetime.strptime(
        values[2],
        "%Y-%m-%d %H:%M"
    )

    ist_volo = {
        "id": index,
        "rotta": values[0],
        "modello_aereo": values[1],
        "timestamp": timestamp
    }

    volo.append(ist_volo)


if volo:
    db.volo.insert_many(volo)

print(f"Voli importati: {len(volo)}")


# ============================================================
# INDICI
# ============================================================

print("\nCreazione degli indici...")

db.aeroporto.create_index(
    "iata",
    unique=True
)

db.compagnia.create_index(
    "nome",
    unique=True
)

db.rotta.create_index(
    "id",
    unique=True
)

db.volo.create_index(
    "id",
    unique=True
)

db.rotta.create_index("iata_partenza")
db.rotta.create_index("iata_arrivo")
db.rotta.create_index("compagnia")

db.volo.create_index("rotta")


# ============================================================
# VERIFICA FINALE
# ============================================================

print("\n===================================")
print("IMPORTAZIONE COMPLETATA")
print("===================================")

print(f"Aeroporti : {db.aeroporto.count_documents({})}")
print(f"Compagnia : {db.compagnia.count_documents({})}")
print(f"Rotte     : {db.rotta.count_documents({})}")
print(f"Voli      : {db.volo.count_documents({})}")

print("\nCollection MongoDB:")

for collection in db.list_collection_names():
    print(f"  - {collection}")

client.close()

print("\nConnessione MongoDB chiusa.")
