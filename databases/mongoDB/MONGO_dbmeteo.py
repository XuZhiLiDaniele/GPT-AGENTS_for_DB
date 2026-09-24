import re
from pathlib import Path
from datetime import datetime
from pymongo import MongoClient


# ============================================================
# CONFIGURAZIONE
# ============================================================

BASE_DIR = Path(__file__).resolve().parents[2]
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "large" / "DB_METEO_l.sql")
#SQL_FILE = (BASE_DIR / "databases" / "mysql" / "medium" / "DB_METEO.sql")
SQL_FILE = (BASE_DIR / "databases" / "mysql" / "small" / "DB_METEO_s.sql")

MONGO_URI = "mongodb://localhost:27017/"
#DB_NAME = "DBMETEO_l"
#DB_NAME = "DBMETEO"
DB_NAME = "DBMETEO_s"


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

    pattern = re.compile(
        r"INSERT\s+INTO\s+"
        + re.escape(table_name)
        + r"\s*\([^)]*\)\s*VALUES\s*(.*?);",
        re.IGNORECASE | re.DOTALL
    )

    return pattern.findall(sql)


# ============================================================
# ESTRAZIONE SINGOLE TUPLE
# ============================================================

def extract_rows(values_block):

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
# ESTRAZIONE STAZIONI
# ============================================================

station_blocks = extract_insert_blocks("STAZIONE")

station_rows = []

for block in station_blocks:
    station_rows.extend(
        extract_rows(block)
    )


print("\n================ STAZIONI ================")
print(
    "Blocchi INSERT trovati:",
    len(station_blocks)
)
print(
    "Stazioni estratte:",
    len(station_rows)
)


# ============================================================
# ESTRAZIONE PREVISIONI
# ============================================================

forecast_blocks = extract_insert_blocks("PREVISIONE")

forecast_rows = []

for block in forecast_blocks:
    forecast_rows.extend(
        extract_rows(block)
    )


print("\n================ PREVISIONI ================")
print(
    "Blocchi INSERT trovati:",
    len(forecast_blocks)
)
print(
    "Previsioni estratte:",
    len(forecast_rows)
)

# ============================================================
# CONVERSIONE STAZIONI
# ============================================================

station_documents = []

for row in station_rows:

    values = parse_sql_values(row)

    if len(values) != 4:

        print("\nATTENZIONE: riga STAZIONE non valida:")
        print(row)

        continue

    icao = values[0]

    latitudine = float(values[1])
    longitudine = float(values[2])
    ricercatori = int(values[3])

    station_documents.append({
        "icao": icao,
        "latitudine": latitudine,
        "longitudine": longitudine,
        "ricercatori": ricercatori
    })


# ============================================================
# CONVERSIONE PREVISIONI
# ============================================================

forecast_documents = []

for index, row in enumerate(
    forecast_rows,
    start=1
):

    values = parse_sql_values(row)

    if len(values) != 7:

        print(
            "\nATTENZIONE: riga PREVISIONE non valida:"
        )
        print(row)

        continue

    stato = values[0]
    citta = values[1]
    stazione = values[2]

    temperatura = float(values[3])
    precipitazioni = float(values[4])
    vento = int(values[5])

    data = datetime.strptime(
        values[6],
        "%Y-%m-%d"
    )

    forecast_documents.append({

        # Equivalente dell'AUTO_INCREMENT MySQL
        "id": index,
        "stato": stato,
        "citta": citta,
        "stazione": stazione,
        "temperatura": temperatura,
        "precipitazioni": precipitazioni,
        "vento": vento,
        "data": data
    })


# ============================================================
# RESET COLLECTION
# ============================================================

db.stazione.drop()
db.previsione.drop()


# ============================================================
# INSERIMENTO STAZIONI
# ============================================================

if station_documents:

    db.stazione.insert_many(
        station_documents,
        ordered=True
    )

# ============================================================
# INSERIMENTO PREVISIONI
# ============================================================

if forecast_documents:

    db.previsione.insert_many(
        forecast_documents,
        ordered=True
    )

# ============================================================
# INDICI
# ============================================================

# ICAO univoco
db.stazione.create_index(
    [("icao", 1)],
    unique=True
)


# ID previsione univoco
db.previsione.create_index(
    [("id", 1)],
    unique=True
)


# Riferimento alla stazione
db.previsione.create_index(
    [("stazione", 1)]
)


# Indici utili per le query del benchmark
db.previsione.create_index(
    [("stato", 1)]
)

db.previsione.create_index(
    [("citta", 1)]
)

db.previsione.create_index(
    [("data", 1)]
)

db.previsione.create_index(
    [("temperatura", 1)]
)

db.previsione.create_index(
    [("precipitazioni", 1)]
)

db.previsione.create_index(
    [("vento", 1)]
)


# ============================================================
# VERIFICA FINALE
# ============================================================

print("\n===================================")
print("IMPORTAZIONE COMPLETATA")
print("===================================")

print(f"Stazioni : {db.stazione.count_documents({})}")
print(f"Previsioni : {db.previsione.count_documents({})}")

print("\nCollection MongoDB:")

for collection in db.list_collection_names():
    print(f"  - {collection}")

client.close()

print("\nConnessione MongoDB chiusa.")

client.close()