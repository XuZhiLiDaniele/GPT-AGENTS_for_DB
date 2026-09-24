import json
import os
from decimal import Decimal
from datetime import datetime, date
from collections import Counter


# ============================================================
# FILE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

TEST_CASES_FILE = os.path.join(
    BASE_DIR,
    "test_casesM.json"
    #"test_casesS.json"
    #"test_casesL.json"
)

RESULTS_FILE = os.path.join(
    BASE_DIR,
    "savedResults/qwen_resultsM.json"
    #"savedResults/gemma_resultsM.json"
)

OUTPUT_FILE = os.path.join(
    BASE_DIR,
    "evaluations/qwen_resultsM_evaluation.json"
    #"evaluations/evaluation_Gemma_results.json"     
)


# ============================================================
# JSON UTILITY
# ============================================================

def load_json(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=4,
            ensure_ascii=False
        )


# ============================================================
# VALUE NORMALIZATION
# ============================================================

def normalize_value(value):

    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 6)

    if isinstance(value, datetime):
        return value.isoformat(sep=" ")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):

        value = value.strip()

        # Prova a normalizzare i valori numerici.
        # Esempio:
        # "1790.5000" -> 1790.5
        # "108.1"     -> 108.1
        try:
            return round(float(value), 6)
        except ValueError:
            return value

    return value


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
            }
        )

    return normalized


# ============================================================
# ACCURACY - DATABASE
# ============================================================

def calculate_database_accuracy(
    expected_database,
    actual_database
):

    if isinstance(expected_database, str):
        expected_database = [expected_database]

    expected_database = expected_database or []

    if not expected_database:
        return 0.0

    if actual_database is None:
        return 0.0

    actual_database = str(actual_database).strip().upper()

    for expected in expected_database:

        if str(expected).strip().upper() == actual_database:
            return 1.0

    return 0.0


# ============================================================
# ACCURACY - COLUMNS
# ============================================================

def calculate_column_accuracy(
    expected_columns,
    actual_columns
):

    expected = set(expected_columns or [])
    actual = set(actual_columns or [])

    if not expected:
        return 1.0 if not actual else 0.0

    correct_columns = len(
        expected & actual
    )

    return correct_columns / len(expected)


# ============================================================
# GET ACTUAL COLUMNS
# ============================================================

def get_actual_columns(
    tool_call,
    output
):

    if not isinstance(output, dict):
        return []

    # Normal case:
    # execute_sql restituisce direttamente "columns"
    columns = output.get("columns")

    if columns is not None:
        return columns

    # Fallback:
    # se columns non è presente, ricaviamo
    # le colonne dalla prima riga.
    rows = output.get("rows", [])

    if rows and isinstance(rows[0], dict):
        return list(rows[0].keys())

    return []


# ============================================================
# PRECISION
# ============================================================

def values_to_counter(rows):

    counter = Counter()

    for row in rows:

        if not isinstance(row, dict):
            continue

        for value in row.values():

            normalized = normalize_value(value)

            counter[normalized] += 1

    return counter


def calculate_precision(
    expected_rows,
    actual_rows
):

    expected = values_to_counter(
        normalize_rows(expected_rows)
    )

    actual = values_to_counter(
        normalize_rows(actual_rows)
    )

    # Nessun risultato atteso
    if not expected:

        if not actual:
            return 1.0

        return 0.0

    correct_values = 0

    for value, expected_count in expected.items():

        actual_count = actual.get(
            value,
            0
        )

        correct_values += min(
            expected_count,
            actual_count
        )

    total_expected_values = sum(
        expected.values()
    )

    if total_expected_values == 0:
        return 0.0

    return (
        correct_values
        / total_expected_values
    )


# ============================================================
# FINAL EXECUTE SQL
# ============================================================

def get_final_execute_sql(run):

    final_execute_sql = None

    for tool_call in run.get(
        "tool_calls",
        []
    ):

        if tool_call.get("tool") == "execute_sql":

            final_execute_sql = tool_call

    return final_execute_sql


# ============================================================
# PARSE TOOL OUTPUT
# ============================================================

def parse_tool_output(tool_call):

    if tool_call is None:
        return None

    output = tool_call.get(
        "output"
    )

    if output is None:
        return None

    # Già un dizionario
    if isinstance(output, dict):
        return output

    # JSON sotto forma di stringa
    if isinstance(output, str):

        try:
            return json.loads(output)

        except json.JSONDecodeError:
            return None

    return None


# ============================================================
# EVALUATE ONE RUN
# ============================================================

def evaluate_run(
    test_case,
    run
):

    # --------------------------------------------------------
    # EXPECTED
    # --------------------------------------------------------

    expected_database = test_case.get(
        "expected_database"
    )

    expected_columns = test_case.get(
        "expected_columns",
        []
    )

    expected_result = test_case.get(
        "expected_result",
        []
    )

    # --------------------------------------------------------
    # LATENCY
    # --------------------------------------------------------

    latency = run.get(
        "latency_total"
    )

    # --------------------------------------------------------
    # DEFAULT EVALUATION
    # --------------------------------------------------------

    evaluation = {

        "test_id": test_case.get(
            "id"
        ),

        "run": run.get(
            "run"
        ),

        "accuracy": {

            "database": {
                "expected": expected_database,
                "actual": None,
                "accuracy": 0.0
            },

            "columns": {
                "expected": expected_columns,
                "actual": [],
                "accuracy": 0.0
            },

            "overall": 0.0
        },

        "precision": {

            "expected": expected_result,
            "actual": [],
            "value": 0.0
        },

        "latency": latency,

        "final_sql": None
    }

    # --------------------------------------------------------
    # CERCA L'ULTIMO execute_sql
    # --------------------------------------------------------

    final_execute_sql = get_final_execute_sql(
        run
    )

    # Nessun execute_sql
    if final_execute_sql is None:
        return evaluation

    # --------------------------------------------------------
    # SQL INFORMATION
    # --------------------------------------------------------

    arguments = final_execute_sql.get(
        "arguments",
        {}
    )

    actual_database = arguments.get(
        "database"
    )

    actual_query = arguments.get(
        "query"
    )

    evaluation["final_sql"] = {

        "database": actual_database,

        "query": actual_query
    }

    # --------------------------------------------------------
    # TOOL OUTPUT
    # --------------------------------------------------------

    output = parse_tool_output(
        final_execute_sql
    )

    if output is None:
        return evaluation

    # --------------------------------------------------------
    # ACTUAL RESULT
    # --------------------------------------------------------

    actual_rows = output.get(
        "rows",
        []
    )

    actual_columns = get_actual_columns(
        final_execute_sql,
        output
    )

    # ========================================================
    # DATABASE ACCURACY
    # ========================================================

    database_accuracy = calculate_database_accuracy(
        expected_database,
        actual_database
    )

    evaluation["accuracy"]["database"] = {

        "expected": expected_database,

        "actual": actual_database,

        "accuracy": database_accuracy
    }

    # ========================================================
    # COLUMNS ACCURACY
    # ========================================================

    columns_accuracy = calculate_column_accuracy(
        expected_columns,
        actual_columns
    )

    evaluation["accuracy"]["columns"] = {

        "expected": expected_columns,

        "actual": actual_columns,

        "accuracy": columns_accuracy
    }

    # ========================================================
    # OVERALL ACCURACY
    # ========================================================

    overall_accuracy = (
        database_accuracy
        + columns_accuracy
    ) / 2

    evaluation["accuracy"]["overall"] = (
        overall_accuracy
    )

    # ========================================================
    # PRECISION
    # ========================================================

    precision = calculate_precision(
        expected_result,
        actual_rows
    )

    evaluation["precision"] = {

        "expected": expected_result,

        "actual": actual_rows,

        "value": precision
    }

    return evaluation


# ============================================================
# GLOBAL BENCHMARK STATISTICS
# ============================================================

def calculate_statistics(
    evaluations
):

    if not evaluations:

        return {

            "accuracy": {
                "database": 0.0,
                "columns": 0.0,
                "overall": 0.0
            },

            "precision": 0.0,

            "latency": 0.0
        }

    # --------------------------------------------------------
    # DATABASE ACCURACY
    # --------------------------------------------------------

    database_values = [

        evaluation["accuracy"]["database"]["accuracy"]

        for evaluation in evaluations
    ]

    # --------------------------------------------------------
    # COLUMNS ACCURACY
    # --------------------------------------------------------

    columns_values = [

        evaluation["accuracy"]["columns"]["accuracy"]

        for evaluation in evaluations
    ]

    # --------------------------------------------------------
    # OVERALL ACCURACY
    # --------------------------------------------------------

    overall_values = [

        evaluation["accuracy"]["overall"]

        for evaluation in evaluations
    ]

    # --------------------------------------------------------
    # PRECISION
    # --------------------------------------------------------

    precision_values = [

        evaluation["precision"]["value"]

        for evaluation in evaluations
    ]

    # --------------------------------------------------------
    # LATENCY
    # --------------------------------------------------------

    latency_values = [

        evaluation["latency"]

        for evaluation in evaluations

        if evaluation["latency"] is not None
    ]

    # --------------------------------------------------------
    # AVERAGES
    # --------------------------------------------------------

    database_accuracy = (
        sum(database_values)
        / len(database_values)
    )

    columns_accuracy = (
        sum(columns_values)
        / len(columns_values)
    )

    overall_accuracy = (
        sum(overall_values)
        / len(overall_values)
    )

    precision = (
        sum(precision_values)
        / len(precision_values)
    )

    if latency_values:

        latency = (
            sum(latency_values)
            / len(latency_values)
        )

    else:

        latency = 0.0

    return {

        "accuracy": {

            "database": database_accuracy,

            "columns": columns_accuracy,

            "overall": overall_accuracy
        },

        "precision": precision,

        "latency": latency
    }


# ============================================================
# PRINT ONE RUN
# ============================================================

def print_run(
    evaluation
):

    print()
    print("=" * 70)
    print("risultati"+RESULTS_FILE+":")

    print(
        f"TEST {evaluation['test_id']} "
        f"- RUN {evaluation['run']}"
    )

    print("=" * 70)

    # ========================================================
    # ACCURACY
    # ========================================================

    print("\nACCURACY")

    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------

    database = evaluation[
        "accuracy"
    ][
        "database"
    ]

    print("\n  Database:")

    print(
        f"    Expected: {database['expected']}"
    )

    print(
        f"    Actual:   {database['actual']}"
    )

    print(
        f"    Accuracy: "
        f"{database['accuracy'] * 100:.2f}%"
    )

    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------

    columns = evaluation[
        "accuracy"
    ][
        "columns"
    ]

    print("\n  Columns:")

    print(
        f"    Expected: {columns['expected']}"
    )

    print(
        f"    Actual:   {columns['actual']}"
    )

    print(
        f"    Accuracy: "
        f"{columns['accuracy'] * 100:.2f}%"
    )

    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------

    overall = evaluation[
        "accuracy"
    ][
        "overall"
    ]

    print(
        f"\n  Overall Accuracy: "
        f"{overall * 100:.2f}%"
    )

    # ========================================================
    # PRECISION
    # ========================================================

    precision = evaluation[
        "precision"
    ]

    print("\nPRECISION")

    print("\n  Expected:")

    print(
        json.dumps(
            precision["expected"],
            indent=4,
            ensure_ascii=False
        )
    )

    print("\n  Actual:")

    print(
        json.dumps(
            precision["actual"],
            indent=4,
            ensure_ascii=False
        )
    )

    print(
        f"\n  Precision: "
        f"{precision['value'] * 100:.2f}%"
    )

    # ========================================================
    # LATENCY
    # ========================================================

    print("\nLATENCY")

    print(
        f"  {evaluation['latency']:.2f} ms"
        if evaluation["latency"] is not None
        else "  N/A"
    )


# ============================================================
# MAIN EVALUATOR
# ============================================================

def evaluate():

    # --------------------------------------------------------
    # LOAD FILES
    # --------------------------------------------------------

    test_cases = load_json(
        TEST_CASES_FILE
    )

    test_results = load_json(
        RESULTS_FILE
    )

    # --------------------------------------------------------
    # SUPPORTA EVENTUALE STRUTTURA:
    #
    # [
    #     {...},
    #     {...}
    # ]
    #
    # oppure:
    #
    # {
    #     "test_cases": [...]
    # }
    # --------------------------------------------------------

    if isinstance(test_cases, dict):

        test_cases = test_cases.get(
            "test_cases",
            test_cases.get(
                "results",
                []
            )
        )

    # --------------------------------------------------------
    # test_results ha la struttura:
    #
    # {
    #     "num_runs": 1,
    #     "results": [
    #         {
    #             "id": 1,
    #             "question": "...",
    #             "runs": [...]
    #         }
    #     ]
    # }
    # --------------------------------------------------------

    if isinstance(test_results, dict):

        results = test_results.get(
            "results",
            []
        )

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

        test_id = test_case.get(
            "id"
        )

        # ----------------------------------------------------
        # Trova il risultato corrispondente
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

        runs = result_entry.get(
            "runs",
            []
        )

        for run in runs:

            evaluation = evaluate_run(
                test_case,
                run
            )

            all_evaluations.append(
                evaluation
            )

            print_run(
                evaluation
            )

    # ========================================================
    # STATISTICHE
    # ========================================================

    statistics = calculate_statistics(
        all_evaluations
    )

    # ========================================================
    # OUTPUT JSON
    # ========================================================

    output = {

        "statistics": statistics,

        "runs": all_evaluations
    }

    save_json(
        OUTPUT_FILE,
        output
    )

    # ========================================================
    # SUMMARY
    # ========================================================

    print()
    print("=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)

    print(
        f"\nAccuracy Database: "
        f"{statistics['accuracy']['database'] * 100:.2f}%"
    )

    print(
        f"Accuracy Columns:  "
        f"{statistics['accuracy']['columns'] * 100:.2f}%"
    )

    print(
        f"Accuracy Overall:   "
        f"{statistics['accuracy']['overall'] * 100:.2f}%"
    )

    print(
        f"Precision:          "
        f"{statistics['precision'] * 100:.2f}%"
    )

    print(
        f"Latency:            "
        f"{statistics['latency']:.2f} ms"
    )

    print("=" * 70)

    print(
        f"\nRisultati salvati in: "
        f"{OUTPUT_FILE}"
    )


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    evaluate()
