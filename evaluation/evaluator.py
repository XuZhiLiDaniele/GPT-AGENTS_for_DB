import json
import os
import math
import sqlglot
from sqlglot import exp
from statistics import mean, stdev
from scipy.stats import t
from scipy.stats import norm
from decimal import Decimal
from datetime import datetime, date
from collections import Counter

# ============================================================
# FILE
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_CASES_FILE = os.path.join(
    BASE_DIR,
    #"test_casesM.json"
    # "test_casesS.json"
    # "test_casesL.json"
    "test_case_CROSS.json"

)
RESULTS_FILE = os.path.join(BASE_DIR, "results/qwen_cross_results2.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "evaluations/qwen_cross_results_eva.json")

DEFAULT_LEVELS = {
    "facile": list(range(1, 4)),
    "intermedio": list(range(4, 7)),
    "difficile": list(range(7, 10))
}

# ============================================================
# JSON UTILITY
# ============================================================
def load_json(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

# ============================================================
# VALUE NORMALIZATION
# ============================================================
def normalize_value(value):
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, list):
        return tuple(normalize_value(item)
                     for item in value)

    if isinstance(value, dict):
        return tuple(
            sorted(
                    (
                    normalize_value(key), normalize_value(val)
                    )
                    for key, val in value.items()
                  )
        )

    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 6)

    if isinstance(value, datetime):
        return value.isoformat(sep=" ")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        value = value.strip()
        # DATE ISO
        try:
            parsed_datetime = datetime.fromisoformat(value.replace("Z", "+00:00"))
            # Se è una datetime a mezzanotte, la considero equivalente alla corrispondente data semplice.
            if (parsed_datetime.hour == 0 and parsed_datetime.minute == 0 and parsed_datetime.second == 0 and parsed_datetime.microsecond == 0):
                return parsed_datetime.date().isoformat()
            return parsed_datetime.isoformat()
        
        except ValueError:
            pass

        # NUMERIC STRING
        try:
            return round(float(value), 6)

        except ValueError:
            return value
        
    return value

# ============================================================
# ROW NORMALIZATION
# ============================================================
def normalize_rows(rows):
    if not rows:
        return []
    
    normalized = []

    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized.append(
            {
                key: normalize_value(value)
                for key, value in row.items()
                if key != "_id"
            }
        )
    return normalized

# ============================================================
# ESTRAZIONE QUERY SQL
# ============================================================
def extract_sql_query(run):
    """
    Recupera la query SQL dall'ultima chiamata SQL disponibile.
    Cerca prima negli arguments e poi nell'output.
    """
    sql_tools = {"execute_sql", "mysql_execute_sql"}

    for tool_call in reversed(run.get("tool_calls", [])):
        if tool_call.get("tool") not in sql_tools:
            continue

        arguments = tool_call.get("arguments", {})
        output = tool_call.get("output", {})

        if isinstance(arguments, dict):
            query = arguments.get("query")
            if isinstance(query, str) and query.strip():
                return query

        # L'output potrebbe essere una stringa JSON.
        if isinstance(output, str):
            try:
                output = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                output = {}

        if isinstance(output, dict):
            query = output.get("query")
            if isinstance(query, str) and query.strip():
                return query
    return None

# ============================================================
# RISOLUZIONE ALIAS SQL
# ============================================================
def build_sql_field_provenance(query):
    """
    Costruisce una mappa alias -> colonna originale.

    Esempio:
        SELECT a.nome AS aeroporto,
               a.passeggeri AS totale
        FROM aeroporto a

    Produce:
        {
            "aeroporto": "nome",
            "totale": "passeggeri"
        }
    """
    provenance = {}

    if not isinstance(query, str) or not query.strip():
        return provenance

    try:
        statements = sqlglot.parse(query, read="mysql")
    except Exception:
        return provenance

    for statement in reversed(statements):
        if statement is None:
            continue

        # Considera la SELECT principale della query.
        select = statement.find(exp.Select)

        if select is None:
            continue

        for projection in select.expressions:
            alias = projection.alias

            # Alias esplicito o implicito.
            if not alias:
                continue

            # Recupera l'espressione sottostante l'alias.
            expression = (
                projection.this
                if isinstance(projection, exp.Alias)
                else projection
            )

            # Rimappa solo i riferimenti diretti a colonne.
            # Esempio: a.nome AS aeroporto -> aeroporto: nome
            if isinstance(expression, exp.Column):
                source_column = expression.name
                if source_column:
                    provenance[alias] = source_column
        break
    return provenance

# ============================================================
# NORMALIZZAZIONE RISULTATO SQL CON ALIAS
# ============================================================
def normalize_sql_rows_with_provenance(rows, provenance):
    """
    Sostituisce i nomi delle colonne alias con i nomi originali,
    mantenendo invariati i valori e le altre colonne.
    """
    if not rows:
        return []

    normalized = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        normalized_row = {}

        for key, value in row.items():
            canonical_key = provenance.get(key, key)

            # In caso di collisione, non sovrascrivere
            # silenziosamente una colonna già presente.
            if canonical_key in normalized_row:
                normalized_row[key] = normalize_value(value)
            else:
                normalized_row[canonical_key] = normalize_value(value)

        normalized.append(normalized_row)

    return normalized

# ============================================================
# ESTRAZIONE ULTIMO FIND O AGGREGATE
# ============================================================
def extract_mongodb_result(run):
    tool_calls = run.get("tool_calls", [])

    for tool_call in reversed(tool_calls):
        tool_name = tool_call.get("tool")

        if tool_name not in ("find_documents", "aggregate_documents"):
            continue
        output = tool_call.get("output", {})
        arguments = tool_call.get("arguments", {})
        if isinstance(output, dict):
            documents = output.get("documents", [])
            return{
                "tool": tool_name,
                "arguments": arguments,
                "result": documents,
                "raw_output": output
            }
        return{
            "tool": None,
            "arguments":arguments,
            "result": [],
            "raw_output": output
        }
    return{
        "tool": None,
        "arguments":{},
        "result": [],
        "raw_output": None
    }
    
#ESTRATTORE PIPELINE AGGREGAZIONE
def extract_pipeline(mongodb_result):
    arguments = mongodb_result.get("arguments", {})

    if mongodb_result.get("tool") == "aggregate_documents":
        return arguments.get("pipeline", [])

    return []

# ============================================================
# RISOLUTORE ALIAS
# ============================================================
def extract_source_field(expression):
    """
    Estrae il campo MongoDB originale da un'espressione semplice del tipo "$campo".
    """
    if isinstance(expression, str) and expression.startswith("$"):
        return expression[1:]
    return None

def normalize_provenance_field(source):
    if not isinstance(source, str):
        return source
    return source.split(".")[-1]

def build_field_provenance(pipeline):
    """
    Costruisce una mappa   alias -> campo_originale   analizzando le parti semplici della pipeline.
    """
    provenance = {}
    
    for stage in pipeline:
        if not isinstance(stage, dict):
            continue

        # Ricerca del $group
        if "$group" in stage:
            group = stage["$group"]
            
            for output_field, expression in group.items():
                # Riferimento diretto (es. "_id": "$iata_arrivo")
                source = extract_source_field(expression)
                if source:
                    source = normalize_provenance_field(source)
                    provenance[output_field] = source
                    continue

                # Accumulatore es.( "max_passeggeri": {"$max": "$passeggeri"})
                if isinstance(expression, dict) and len(expression) == 1:
                    operator, value = next(iter(expression.items()))
                    source = extract_source_field(value)
                    if source:
                        source = normalize_provenance_field(source)
                        provenance[output_field] = source

        # ----------------------------------------------------
        # In caso di $project per join tra collezioni
        # ----------------------------------------------------
        elif "$project" in stage:

            project = stage["$project"]

            for output_field, expression in project.items():
                # esclusione
                if expression in (0, False):
                    provenance.pop(output_field, None)
                    continue
                
                # inclusione: mantiene il campo originale
                if expression in (1, True):
                    continue

                # alias diretto:
                source = extract_source_field(expression)
                if source:
                    source = normalize_provenance_field(source)
                    provenance[output_field] = source

        # ----------------------------------------------------
        # $set / $addFields
        # ----------------------------------------------------
        elif "$set" in stage or "$addFields" in stage:

            fields = stage.get("$set", stage.get("$addFields", {}))
            
            for output_field, expression in fields.items():
                source = extract_source_field(expression)
                if source:
                    source = normalize_provenance_field(source)
                    provenance[output_field] = source

    return provenance

# ============================================================
# NORMALIZZAZIONE ALIAS -> ORIGINALE
# ============================================================
def normalize_rows_with_provenance(rows, provenance):
    if not rows:
        return []

    normalized = []

    for row in rows:

        if not isinstance(row, dict):
            continue

        normalized_row = {}

        for key, value in row.items():
            # Se conosciamo la provenienza dell'alias
            canonical_key = provenance.get(key, key)
            normalized_row[canonical_key] = normalize_value(value)

        normalized.append(normalized_row)

    return normalized


# ============================================================
# DATABASE ACCURACY
# ============================================================
def calculate_database_accuracy(expected_database, actual_database):

    if isinstance(expected_database, str):
        expected_database = [expected_database]

    if isinstance(actual_database, str):
        actual_database = [actual_database]

    expected_database = {
        str(db).strip().upper()
        for db in (expected_database or [])
    }

    actual_database = {
        str(db).strip().upper()
        for db in (actual_database or [])
    }

    if not expected_database:
        return (
            1.0
            if not actual_database
            else 0.0
        )
    correct_databases = len(expected_database & actual_database)
    return (correct_databases / len(expected_database))

# ============================================================
# COLUMN ACCURACY
# ============================================================
def calculate_column_accuracy(expected_columns, actual_columns):

    expected = expected_columns or []
    actual = set(actual_columns or [])
    if not expected:
        return 1.0 if not actual else 0.0

    correct_columns = 0
    for expected_column in expected:
        # Colonna con più nomi alternativi
        if isinstance(expected_column, list):
            alternatives = set(expected_column)
            if alternatives & actual:
                correct_columns += 1

        # Colonna con nome singolo
        else:
            if expected_column in actual:
                correct_columns += 1

    return correct_columns / len(expected)

# ============================================================
# ROW MATCHING
# ============================================================
def row_matches(expected_row, actual_row, expected_columns):
    """
    Verifica se una riga actual contiene tutti i valori richiesti dalla riga expected.
    Le colonne aggiuntive presenti nella riga actual vengono ignorate.
    """

    if not isinstance(expected_row, dict):
        return False

    if not isinstance(actual_row, dict):
        return False

    for expected_column, expected_value in expected_row.items():
        # Individua gli alias ammessi per la colonna
        aliases = [expected_column]

        for definition in expected_columns or []:
            if isinstance(definition, list):
                if expected_column in definition:
                    aliases = definition
                    break
            elif definition == expected_column:
                aliases = [expected_column]
                break

        # Cerca una colonna actual compatibile
        actual_column = None
        for alias in aliases:
            if alias in actual_row:
                actual_column = alias
                break
        if actual_column is None:
            return False
        
        # Confronto del valore
        expected_normalized = normalize_value(expected_value)
        actual_normalized = normalize_value(actual_row[actual_column])
        if expected_normalized != actual_normalized:
            return False

    return True


def match_expected_rows(expected_rows, actual_rows, expected_columns=None):
    """
    Abbina esclusivamente le righe completamente corrispondenti.
    Ogni riga attesa e ogni riga effettiva possono essere usate una sola volta.
    """
    expected_rows = normalize_rows(expected_rows or [])
    actual_rows = normalize_rows(actual_rows or [])

    matched_expected = set()
    matched_actual = set()

    for actual_index, actual_row in enumerate(actual_rows):
        for expected_index, expected_row in enumerate(expected_rows):
            if expected_index in matched_expected:
                continue

            if row_matches(expected_row, actual_row, expected_columns):
                matched_expected.add(expected_index)
                matched_actual.add(actual_index)
                break

    return (
        len(matched_expected),
        len(expected_rows),
        len(actual_rows),
        matched_expected,
        matched_actual,
    )


def calculate_exact_match(expected_rows, actual_rows, expected_columns=None):
    """
    Exact Match se tutte le righe attese sono presenti,
    non esistono righe aggiuntive e le colonne richieste sono presenti.
    Le colonne aggiuntive non compromettono il risultato.
    """
    expected_rows = normalize_rows(expected_rows or [])
    actual_rows = normalize_rows(actual_rows or [])

    if not expected_rows:
        return 1.0 if not actual_rows else 0.0

    if len(expected_rows) != len(actual_rows):
        return 0.0

    matched_count, total_expected, total_actual, _, _ = (
        match_expected_rows(
            expected_rows,
            actual_rows,
            expected_columns
        )
    )

    return float(
        matched_count == total_expected
        and total_actual == total_expected
    )



def row_matches_partial(expected_row, actual_row, expected_columns=None):
    """
    Verifica una corrispondenza parziale tra due righe.

    I campi mancanti sono ammessi, ma tutti i valori confrontabili
    devono coincidere. È necessaria almeno una colonna confrontabile.
    Gli alias ammessi sono definiti in expected_columns.
    """
    if not isinstance(expected_row, dict) or not isinstance(actual_row, dict):
        return False

    compared_fields = 0

    for expected_column, expected_value in expected_row.items():
        aliases = [expected_column]

        for definition in expected_columns or []:
            if isinstance(definition, list) and expected_column in definition:
                aliases = definition
                break
            elif isinstance(definition, str) and definition == expected_column:
                aliases = [expected_column]
                break

        actual_aliases = [
            alias for alias in aliases
            if alias in actual_row
        ]

        # Il campo atteso è assente: può essere una colonna mancante.
        if not actual_aliases:
            continue

        # Se è presente un alias, il valore deve corrispondere.
        if not any(
            normalize_value(actual_row[alias])
            == normalize_value(expected_value)
            for alias in actual_aliases
        ):
            return False

        compared_fields += 1

    return compared_fields > 0


def calculate_partial_match(
    expected_rows,
    actual_rows,
    expected_columns=None
):
    """
    Partial Match se almeno una riga attesa è riconoscibile
    e il risultato non soddisfa i criteri di Exact Match.

    Sono ammessi:
    - colonne mancanti;
    - righe attese mancanti;
    - righe aggiuntive.

    Tutti i valori confrontabili devono coincidere.
    """
    expected_rows = normalize_rows(expected_rows or [])
    actual_rows = normalize_rows(actual_rows or [])

    if not expected_rows or not actual_rows:
        return 0

    if calculate_exact_match(
        expected_rows,
        actual_rows,
        expected_columns
    ):
        return 0

    # Riserva prima le corrispondenze complete.
    _, _, _, full_expected, full_actual = match_expected_rows(
        expected_rows,
        actual_rows,
        expected_columns
    )

    matched_expected = set(full_expected)
    matched_actual = set(full_actual)

    # Cerca corrispondenze parziali tra le righe non ancora abbinate.
    for actual_index, actual_row in enumerate(actual_rows):
        if actual_index in matched_actual:
            continue

        for expected_index, expected_row in enumerate(expected_rows):
            if expected_index in matched_expected:
                continue

            if row_matches_partial(
                expected_row,
                actual_row,
                expected_columns
            ):
                matched_expected.add(expected_index)
                matched_actual.add(actual_index)
                break

    return int(bool(matched_expected))



# ============================================================
# ESTRAZIONE DATABASE USATI
# ============================================================
def extract_actual_databases(run):

    databases = set()

    tool_calls = run.get("tool_calls", [])
    
    for tool_call in tool_calls:
        arguments = tool_call.get("arguments", {})

        if not isinstance(arguments, dict):
            continue

        database = arguments.get("database")

        if database is not None:
            databases.add(str(database).strip().upper())
    return sorted(databases)

# ============================================================
# ESTRAZIONE COLONNE
# ============================================================
def extract_actual_columns(answer):

    if not answer:
        return []

    if not isinstance(answer, list):
        return []

    columns = set()

    for row in answer:
        if not isinstance(row, dict):
            continue

        for key in row.keys():
            if key != "_id":
                columns.add(key)

    return sorted(columns)

# ============================================================
# EVALUATE ONE RUN
# ============================================================
def evaluate_run(test_case, run):
    
    # EXPECTED
    expected_database = test_case.get("expected_database", [])
    expected_columns = test_case.get("expected_columns", [])
    expected_result = test_case.get("expected_result", [])

    # LATENCY
    latency = run.get("latency_total")

    # ACTUAL RESULT -> L'answer del runner è la fonte ufficiale del risultato prodotto dall'agente.
    actual_rows = run.get("answer") or []

    # Normalizzazione degli alias MongoDB.
    mongodb_result = extract_mongodb_result(run)

    if mongodb_result["tool"] is not None:
        pipeline = extract_pipeline(mongodb_result)
        mongo_provenance = build_field_provenance(pipeline)

        actual_rows = normalize_rows_with_provenance(
            actual_rows,
            mongo_provenance
        )

    # Estrazione query SQL e provenienza degli alias.
    sql_query = extract_sql_query(run)
    sql_provenance = build_sql_field_provenance(sql_query)
    # Normalizzazione dei risultati SQL.
    actual_rows = normalize_sql_rows_with_provenance(actual_rows, sql_provenance)
    # Normalizzazione comune a MySQL e MongoDB.
    # Mantiene anche la rimozione di _id prevista per MongoDB.
    actual_rows = normalize_rows(actual_rows)
    # ACTUAL COLUMNS
    actual_columns = extract_actual_columns(actual_rows)

    # DATABASE -> Il database può essere ricavato dai tool_calls, ma NON dal risultato answer.
    actual_database = extract_actual_databases(run)

    
    # DATABASE ACCURACY
    database_accuracy = calculate_database_accuracy(expected_database, actual_database)
    # COLUMN ACCURACY
    columns_accuracy = calculate_column_accuracy(expected_columns, actual_columns)
    # OVERALL ACCURACY
    overall_accuracy = (database_accuracy + columns_accuracy) / 2
    # EXACT MATCH
    exact_match = calculate_exact_match(expected_result, actual_rows, expected_columns)
    # PARTIAL MATCH
    partial_match = calculate_partial_match(expected_result, actual_rows, expected_columns)
    # WRONG
    wrong_match = (1.0 - exact_match - partial_match)

    # EVALUATION
    return {
        "test_id": test_case.get("id"),
        "run": run.get("run"),

        "accuracy": {
            "database": {
                "expected": expected_database,
                "actual": actual_database,
                "accuracy": database_accuracy
            },
            "columns": {
                "expected": expected_columns,
                "actual": actual_columns,
                "accuracy": columns_accuracy
            },
            "overall": overall_accuracy
        },

        "result_matching": {
            "exact_match": exact_match,
            "partial_match": partial_match,
            "wrong": wrong_match,
            "expected": expected_result,
            "actual": actual_rows
        },

        "latency": latency,

        "agent_completion": run.get("agent_completion"),
        "tool_calls_count": run.get("tool_calls_count")
    }

# ============================================================
# STUDENT CONFIDENCE INTERVAL
# ============================================================
def calculate_student_interval(values, confidence=0.95, bounded=False):
    """
    Calcola media e intervallo di confidenza usando la distribuzione t di Student.
    Parametri:
        values: lista delle osservazioni
        confidence: livello di confidenza al 0.95 = 95%
    """
    if not values:
        return {
            "mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin": 0.0,
            "n": 0
        }
    n = len(values)
    average = mean(values)

    # Una sola osservazione:
    # non è possibile stimare la deviazione standard.
    if n == 1:
        return {
            "mean": average,
            "ci_lower": average,
            "ci_upper": average,
            "margin": 0.0,
            "n": 1
        }
    standard_deviation = stdev(values)
    standard_error = (standard_deviation / math.sqrt(n))

    # Quantile della distribuzione t di Student
    t_critical = t.ppf(1 - (1 - confidence) / 2, df=n - 1)
    margin = (t_critical * standard_error)

    ci_lower = average - margin
    ci_upper = average + margin

    # Accuracy e precision sono comprese
    # nell'intervallo [0, 1].
    if bounded:
        ci_lower = max(0.0, ci_lower)
        ci_upper = min(1.0, ci_upper)

    print("\n--- CONFIDENCE INTERVAL ---")
    print("values:", values)
    print("n:", n)
    print("mean:", average)

    if n > 1:
        print("std:", standard_deviation)
        print("standard error:", standard_error)
        print("t critical:", t_critical)
        print("margin:", margin)

    return {
        "mean": average,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "margin": margin,
        "n": n
    }

# ============================================================
# WILSON CONFIDENCE INTERVAL
# ============================================================
def calculate_wilson_interval(values, confidence=0.95):

    if not values:
        return {
            "mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin_lower": 0.0,
            "margin_upper": 0.0,
            "n": 0
        }

    n = len(values)

    # Numero di successi
    successes = sum(values)

    # Proporzione osservata
    p_hat = successes / n

    # Quantile della normale standard
    z = norm.ppf(1 - (1 - confidence) / 2)
    z_squared = z ** 2

    # Denominatore
    denominator = 1 + z_squared / n

    # Centro dell'intervallo
    center = (p_hat + z_squared / (2 * n)) / denominator

    # Margine di Wilson
    margin = (z * math.sqrt((p_hat * (1 - p_hat) / n) + (z_squared / (4 * n ** 2))) / denominator)

    ci_lower = center - margin
    ci_upper = center + margin

    return {
        "mean": p_hat,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "margin_lower": p_hat - ci_lower,
        "margin_upper": ci_upper - p_hat,
        "n": n
    }

# ============================================================
# GLOBAL BENCHMARK STATISTICS
# ============================================================
def calculate_statistics(evaluations, confidence=0.95):
    if not evaluations:
        empty_student_ci = {
            "mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin": 0.0,
            "n": 0
        }
        empty_wilson_ci = {
            "mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin_lower": 0.0,
            "margin_upper": 0.0,
            "n": 0
        }
        return {
            "confidence_level": confidence,
            "accuracy": {
                "database": empty_student_ci.copy(),
                "columns": empty_student_ci.copy(),
                "overall": empty_student_ci.copy()
            },
            "exact_match": empty_wilson_ci.copy(),
            "partial_match": empty_wilson_ci.copy(),
            "wrong": empty_wilson_ci.copy(),
            "latency": empty_student_ci.copy()
        }

    # DATABASE ACCURACY
    database_values = [
        evaluation["accuracy"]["database"]["accuracy"]
        for evaluation in evaluations
    ]

    # COLUMNS ACCURACY
    columns_values = [
        evaluation["accuracy"]["columns"]["accuracy"]
        for evaluation in evaluations
    ]

    # OVERALL ACCURACY
    overall_values = [
        evaluation["accuracy"]["overall"]
        for evaluation in evaluations
    ]

    # EXACT MATCH
    exact_match_values = [
        evaluation["result_matching"]["exact_match"]
        for evaluation in evaluations
    ]

    # PARTIAL MATCH
    partial_match_values = [
        evaluation["result_matching"]["partial_match"]
        for evaluation in evaluations
    ]

    # WRONG
    wrong_values = [
        evaluation["result_matching"]["wrong"]
        for evaluation in evaluations
    ]

    # LATENCY
    latency_values = [
        evaluation["latency"]
        for evaluation in evaluations
        if evaluation["latency"] is not None
    ]
    # CONFIDENCE INTERVALS
    database_accuracy = calculate_student_interval(database_values, confidence=confidence, bounded=True)
    columns_accuracy = calculate_student_interval(columns_values, confidence=confidence, bounded=True)
    overall_accuracy = calculate_student_interval(overall_values, confidence=confidence, bounded=True)
    exact_match = calculate_wilson_interval(exact_match_values, confidence=confidence)
    partial_match = calculate_wilson_interval(partial_match_values, confidence=confidence)
    wrong = calculate_wilson_interval(wrong_values, confidence=confidence)
    latency = calculate_student_interval(latency_values, confidence=confidence, bounded=False)

    # RETURN
    return {
        "confidence_level": confidence,
        "accuracy": {
            "database": database_accuracy,
            "columns": columns_accuracy,
            "overall": overall_accuracy
        },
        "exact_match": exact_match,
        "partial_match": partial_match,
        "wrong": wrong,
        "latency": latency
    }


# ============================================================
# STATISTICHE PER LIVELLO DI DIFFICOLTÀ
# ============================================================
def calculate_level_statistics(evaluations, levels=DEFAULT_LEVELS, confidence=0.95):
    """
    Calcola le statistiche separatamente per ciascun
    livello di difficoltà.

    Le evaluation vengono raggruppate in base al test_id.
    """
    results = {}
    for level_name, test_ids in levels.items():
        test_ids = set(test_ids)
        level_evaluations = [
            evaluation
            for evaluation in evaluations
            if evaluation.get("test_id") in test_ids
        ]
        results[level_name] = calculate_statistics(level_evaluations, confidence=confidence)

    return results


# ============================================================
# PRINT ONE RUN
# ============================================================
def print_run(evaluation):
    print()
    print("=" * 70)
    print(
        f"TEST {evaluation['test_id']} "
        f"- RUN {evaluation['run']}"
    )
    print("=" * 70)

    # ACCURACY
    overall = evaluation["accuracy"]["overall"]
    print(
        f"\n  Overall Accuracy: "
        f"{overall * 100:.2f}%"
    )

    # RESULT MATCHING
    matching = evaluation["result_matching"]
    print("\nRESULT MATCHING")
    print(
        f"  Exact Match: "
        f"{matching['exact_match'] * 100:.2f}%"
    )

    print(
        f"  Partial Match: "
        f"{matching['partial_match'] * 100:.2f}%"
    )

    print(
        f"  Wrong: "
        f"{matching['wrong'] * 100:.2f}%"
    )

    # LATENCY
    print("\nLATENCY")

    print(
        f"  {evaluation['latency']:.2f} ms"
        if evaluation["latency"] is not None
        else "  N/A"
    )

    # AGENT
    print("\nAGENT")
    print(
        f"  Completion: "
        f"{evaluation['agent_completion']}"
    )

    print(
        f"  Tool calls: "
        f"{evaluation['tool_calls_count']}"
    )

# ============================================================
# MAIN EVALUATOR
# ============================================================
def evaluate():
    # --------------------------------------------------------
    # LOAD FILES
    # --------------------------------------------------------
    test_cases = load_json(TEST_CASES_FILE)
    test_results = load_json(RESULTS_FILE)
    # --------------------------------------------------------
    # SUPPORTO STRUTTURE DIVERSE
    # --------------------------------------------------------
    if isinstance(test_cases, dict):
        test_cases = test_cases.get(
            "test_cases",
            test_cases.get("results", [])
        )

    if isinstance(test_results,dict):
        results = test_results.get("results", [])
    else:
        results = test_results

    # --------------------------------------------------------
    # EVALUATIONS
    # --------------------------------------------------------
    all_evaluations = []
    # ========================================================
    # CICLO SUI TEST
    # ========================================================
    for test_case in test_cases:
        test_id = test_case.get("id")
        # ----------------------------------------------------
        # RISULTATO CORRISPONDENTE
        # ----------------------------------------------------
        result_entry = next(
            (
                result
                for result in results
                if result.get("id") == test_id
            ),
            None
        )
        if result_entry is None:
            print(
                f"\nATTENZIONE: "
                f"nessun risultato trovato "
                f"per il test {test_id}"
            )
            continue

        # ----------------------------------------------------
        # RUNS
        # ----------------------------------------------------
        runs = result_entry.get("runs", [])
        for run in runs:
            evaluation = evaluate_run(test_case, run)
            all_evaluations.append(evaluation)
            print_run(evaluation)

    # ========================================================
    # STATISTICHE
    # ========================================================
    confidence = 0.95
    statistics_overall = calculate_statistics(all_evaluations, confidence = confidence)
    statistics_by_difficulty = calculate_level_statistics(all_evaluations, levels = DEFAULT_LEVELS, confidence = confidence)
    
    # ========================================================
    # OUTPUT
    # ========================================================
    output = {
        "statistics": {
            "confidence_level": confidence,
            "overall": statistics_overall,
            "by_difficulty": statistics_by_difficulty
        },
        "runs": all_evaluations
    }
    save_json(OUTPUT_FILE, output)

    # ========================================================
    # SUMMARY OVERALL
    # ========================================================
    print()
    print("=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    print(
        f"\nAccuracy Database: "
        f"{statistics_overall['accuracy']['database']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['accuracy']['database']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['accuracy']['database']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Accuracy Columns:  "
        f"{statistics_overall['accuracy']['columns']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['accuracy']['columns']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['accuracy']['columns']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Accuracy Overall:  "
        f"{statistics_overall['accuracy']['overall']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['accuracy']['overall']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['accuracy']['overall']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Exact Match Rate:   "
        f"{statistics_overall['exact_match']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['exact_match']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['exact_match']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Partial Match Rate: "
        f"{statistics_overall['partial_match']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['partial_match']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['partial_match']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Wrong Rate:         "
        f"{statistics_overall['wrong']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['wrong']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['wrong']['ci_upper'] * 100:.2f}%)"
    )
    print(
        f"Average Latency:   "
        f"{statistics_overall['latency']['mean']:.2f} ms  (95% CI: "
        f"{statistics_overall['latency']['ci_lower']:.2f} ms - "
        f"{statistics_overall['latency']['ci_upper']:.2f} ms)"
    )
    # ========================================================
    # SUMMARY BY LEVEL
    # ========================================================
    print()
    print("=" * 70)
    print("STATISTICHE PER LIVELLO DI DIFFICOLTÀ")
    print("=" * 70)
    for level, level_stats in statistics_by_difficulty.items():
        print()
        print(level.upper())
        print(
            f"  Accuracy Overall: "
            f"{level_stats['accuracy']['overall']['mean'] * 100:.2f}% (95% CI: "
            f"{level_stats['accuracy']['overall']['ci_lower'] * 100:.2f}% - "
            f"{level_stats['accuracy']['overall']['ci_upper'] * 100:.2f}%)"
        )
        print(
            f"  Exact Match Rate:   "
            f"{level_stats['exact_match']['mean'] * 100:.2f}% (95% CI: "
            f"{level_stats['exact_match']['ci_lower'] * 100:.2f}% - "
            f"{level_stats['exact_match']['ci_upper'] * 100:.2f}%)"
        )

        print(
            f"  Partial Match Rate: "
            f"{level_stats['partial_match']['mean'] * 100:.2f}% (95% CI: "
            f"{level_stats['partial_match']['ci_lower'] * 100:.2f}% - "
            f"{level_stats['partial_match']['ci_upper'] * 100:.2f}%)"
        )

        print(
            f"  Wrong Rate:         "
            f"{level_stats['wrong']['mean'] * 100:.2f}% (95% CI: "
            f"{level_stats['wrong']['ci_lower'] * 100:.2f}% - "
            f"{level_stats['wrong']['ci_upper'] * 100:.2f}%)"
        )
        print(
            f"  Average Latency:   "
            f"{level_stats['latency']['mean']:.2f} ms (95% CI: "
            f"{level_stats['latency']['ci_lower']:.2f} ms - "
            f"{level_stats['latency']['ci_upper']:.2f} ms)"
        )
    print()
    print(f"Evaluation salvata in: {OUTPUT_FILE}")
# ============================================================
# START
# ============================================================
if __name__ == "__main__":

    evaluate()