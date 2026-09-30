import json
import os
import math
from statistics import mean, stdev
from scipy.stats import t
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
    # "test_casesS.json"
    # "test_casesL.json"
)
RESULTS_FILE = os.path.join(BASE_DIR, "results/gemma_mongo_results.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "evaluations/gemma_mongo_results_evaluation.json")

DEFAULT_LEVELS = {
    "Semplice": list(range(1, 4)),
    "Intermedio": list(range(4, 7)),
    "Complesso": list(range(7, 10))
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

    if isinstance(value, (int, float, Decimal)):
        return round(float(value), 6)

    if isinstance(value, datetime):
        return value.isoformat(sep=" ")

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, str):
        value = value.strip()
        # Prova a normalizzare valori numerici
        #
        # "1790.5000" -> 1790.5
        # "108.1"     -> 108.1
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
    
    expected = set(expected_columns or [])
    actual = set(actual_columns or [])
    if not expected:
        return (
            1.0
            if not actual
            else 0.0
        )
    correct_columns = len(expected & actual)

    return (correct_columns / len(expected))

# ============================================================
# PRECISION
# ============================================================
def field_values_to_counter(rows):

    counter = Counter()

    for row in rows:
        if not isinstance(row, dict):
            continue
        for key, value in row.items():

            if key == "_id":
                continue

            normalized_key = key
            normalized_value = (normalize_value(value))
            counter[(normalized_key, normalized_value)] += 1
    return counter

def calculate_precision(expected_rows, actual_rows):

    expected = field_values_to_counter(normalize_rows(expected_rows))
    actual = field_values_to_counter(normalize_rows(actual_rows))

    if not expected:
        if not actual:
            return 1.0
        return 0.0
    correct_values = 0

    for (field_value, expected_count) in expected.items():
        actual_count = actual.get(field_value, 0)
        correct_values += min(expected_count, actual_count)

    total_expected_values = sum(expected.values())
    if total_expected_values == 0:
        return 0.0

    return (correct_values / total_expected_values)

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
    # ========================================================
    # EXPECTED
    # ========================================================
    expected_database = test_case.get("expected_database", [])
    expected_columns = test_case.get("expected_columns", [])
    expected_result = test_case.get("expected_result", [])
    # ========================================================
    # LATENCY
    # ========================================================
    latency = run.get("latency_total")
    # ========================================================
    # RISPOSTA FINALE
    # ========================================================
    actual_rows = run.get("answer", [])

    if actual_rows is None:
        actual_rows = []
    # ========================================================
    # DATABASE ACTUAL
    # ========================================================
    actual_database = extract_actual_databases(run)
    # ========================================================
    # COLONNE ACTUAL
    # ========================================================
    actual_columns = extract_actual_columns(actual_rows)
    # ========================================================
    # DATABASE ACCURACY
    # ========================================================
    database_accuracy = (
        calculate_database_accuracy(expected_database, actual_database)
    )

    # ========================================================
    # COLUMNS ACCURACY
    # ========================================================
    columns_accuracy = (
        calculate_column_accuracy(expected_columns, actual_columns)
    )

    # ========================================================
    # OVERALL ACCURACY
    # ========================================================
    overall_accuracy = (database_accuracy + columns_accuracy) / 2

    # ========================================================
    # PRECISION
    # ========================================================
    precision = calculate_precision(expected_result, actual_rows)

    # ========================================================
    # EVALUATION
    # ========================================================
    evaluation = {
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

        "precision": {
            "expected": expected_result,
            "actual": actual_rows,
            "value": precision
        },
        "latency": latency,
        "agent_completion": run.get("agent_completion"),
        "tool_calls_count": run.get("tool_calls_count")
    }

    return evaluation

# ============================================================
# CONFIDENCE INTERVAL
# ============================================================
def calculate_confidence_interval(values, confidence=0.95, bounded=False):
    """
    Calcola media e intervallo di confidenza
    usando la distribuzione t di Student.

    Parametri:
        values:
            lista delle osservazioni

        confidence:
            livello di confidenza.
            0.95 = 95%

        bounded:
            se True, limita l'intervallo a [0, 1].
            Utile per accuracy e precision.
            False per la latenza.

    Restituisce:
        {
            "mean": ...,
            "ci_lower": ...,
            "ci_upper": ...,
            "margin": ...,
            "n": ...
        }
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
# GLOBAL BENCHMARK STATISTICS
# ============================================================

def calculate_statistics(
    evaluations,
    confidence=0.95
):

    if not evaluations:

        empty_ci = {
            "mean": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "margin": 0.0,
            "n": 0
        }

        return {
            "confidence_level": confidence,
            "accuracy": {
                "database": empty_ci.copy(),
                "columns": empty_ci.copy(),
                "overall": empty_ci.copy()
            },
            "precision": empty_ci.copy(),
            "latency": empty_ci.copy()
        }
    # ========================================================
    # DATABASE ACCURACY
    # ========================================================
    database_values = [evaluation["accuracy"]["database"]["accuracy"]
        for evaluation in evaluations
    ]

    # ========================================================
    # COLUMNS ACCURACY
    # ========================================================
    columns_values = [evaluation["accuracy"]["columns"]["accuracy"]
        for evaluation in evaluations
    ]

    # ========================================================
    # OVERALL ACCURACY
    # ========================================================
    overall_values = [evaluation["accuracy"]["overall"]
        for evaluation in evaluations
    ]

    # ========================================================
    # PRECISION
    # ========================================================
    precision_values = [evaluation["precision"]["value"]
        for evaluation in evaluations
    ]

    # ========================================================
    # LATENCY
    # ========================================================
    latency_values = [
        evaluation["latency"]
        for evaluation in evaluations
        if evaluation["latency"] is not None
    ]

    # ========================================================
    # CONFIDENCE INTERVALS
    # ========================================================
    database_accuracy = calculate_confidence_interval(database_values, confidence=confidence, bounded=True)
    columns_accuracy = calculate_confidence_interval(columns_values, confidence=confidence, bounded=True)
    overall_accuracy = calculate_confidence_interval(overall_values, confidence=confidence, bounded=True)
    precision = calculate_confidence_interval(precision_values, confidence=confidence, bounded=True)
    latency = calculate_confidence_interval(latency_values, confidence=confidence, bounded=False)
    # ========================================================
    # RETURN
    # ========================================================
    return {
        "confidence_level": confidence,
        "accuracy": {
            "database": database_accuracy,
            "columns": columns_accuracy,
            "overall": overall_accuracy
        },
        "precision": precision,
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

    # ========================================================
    # ACCURACY
    # ========================================================
    print("\nACCURACY")
    # --------------------------------------------------------
    # Database
    # --------------------------------------------------------
    database = evaluation["accuracy"]["database"]
    print("\n  Database:")
    print(f"Expected: {database['expected']}")
    print(f"Actual: {database['actual']}")
    print(f"Accuracy: {database['accuracy'] * 100:.2f}%")
    # --------------------------------------------------------
    # Columns
    # --------------------------------------------------------
    columns = evaluation["accuracy"]["columns"]
    print("\n  Columns:")
    print(f"Expected: {columns['expected']}")
    print(f"Actual: {columns['actual']}")
    print(f"Accuracy: {columns['accuracy'] * 100:.2f}%")
    # --------------------------------------------------------
    # Overall
    # --------------------------------------------------------
    overall = evaluation["accuracy"]["overall"]
    print(f"\n  Overall Accuracy: {overall * 100:.2f}%")
    # ========================================================
    # PRECISION
    # ========================================================
    precision = evaluation["precision"]
    print("\nPRECISION")
    print("\n  Expected:")
    print(
        json.dumps(precision["expected"], indent=4, ensure_ascii=False)
        )
    print("\n  Actual:")
    print(
        json.dumps(precision["actual"], indent=4, ensure_ascii=False)
        )

    print(f"\n  Precision: {precision['value'] * 100:.2f}%")
    # ========================================================
    # LATENCY
    # ========================================================
    print("\nLATENCY")
    print(
        f"  {evaluation['latency']:.2f} ms"
        if evaluation["latency"] is not None
        else "  N/A"
    )
    # ========================================================
    # AGENT
    # ========================================================
    print("\nAGENT")
    print(f"  Completion: {evaluation['agent_completion']}")
    print(f"  Tool calls: {evaluation['tool_calls_count']}")

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
        f"Precision:         "
        f"{statistics_overall['precision']['mean'] * 100:.2f}%  (95% CI: "
        f"{statistics_overall['precision']['ci_lower'] * 100:.2f}% - "
        f"{statistics_overall['precision']['ci_upper'] * 100:.2f}%)"
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
            f"  Precision:         "
            f"{level_stats['precision']['mean'] * 100:.2f}% (95% CI: "
            f"{level_stats['precision']['ci_lower'] * 100:.2f}% - "
            f"{level_stats['precision']['ci_upper'] * 100:.2f}%)"
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