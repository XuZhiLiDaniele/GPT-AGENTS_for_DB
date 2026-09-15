import json
import os
import statistics
from decimal import Decimal
from datetime import datetime, date
from collections import Counter
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_CASES_FILE = os.path.join(BASE_DIR, "test_casesM.json")
RESULTS_FILE = os.path.join(BASE_DIR, "test_results.json")#(BASE_DIR, "test_results.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "evaluation_results.json")

#-------------------UTILITY
def load_json(filename):
    """
    carica file json
    """
    with open(filename, "r", encoding ="utf-8") as file:
        return json.load(file)
        
def save_json(filename, data):
    """
    salva file json formattato
    """
    with open(filename, "w", encoding = "utf-8") as file:
        json.dump(data, file, indent = 4, ensure_ascii=False)

def to_numeric(value):
    """
    Converte un valore in float quando possibile, restituendo None se non è numerico
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None

#------------------NORMALIZZAZIONE
def normalize_value(value):
    """
    Normalizza i valori provenienti dai JSON per evitare conflitti da formati
    """
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
        try:
            return round(float(value),6)
        except ValueError:
            return value
    return value

def normalize_row(row):
    """
    normalizzazione di una singola riga
    """
    if not isinstance(row, dict):
        return row
    return {
        key: normalize_value(value)
        for key, value in row.items()
    }

def normalize_rows(rows):
    """
    normalizzazione di tutte le righe
    """
    if rows is None:
        return []
    return[
        normalize_row(row)
        for row in rows
    ]


def row_to_tuple(row, columns):
    """
    Converte una riga in una tupla ordinata secondo columns
    """
    return tuple(normalize_value(row.get(column))
                    for column in columns
                )

# def rows_to_counter(rows, columns):
#     """
#     Trasforma le righe in counter di tuple, per considerare eventuali duplicati
#     """
#     counter = Counter()
#     for row in rows:
#         if not isinstance(row, dict):
#             continue
#         normalized_tuple = row_to_tuple(row, columns)
#         counter[normalized_tuple]+=1
#     return counter

def values_to_counter(rows):
    counter = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        for value in row.values():
            counter[normalize_value(value)] += 1
    return counter

#------------------CONFRONTO RISULTATI
def compare_results(expected_rows, actual_rows):
    """
    Confronta il risultato prodotto dall'agente con il risultato atteso
    """
    expected_rows = normalize_rows(expected_rows)
    actual_rows = normalize_rows(actual_rows)
    expected_counter = values_to_counter(expected_rows)
    actual_counter = values_to_counter(actual_rows)

    true_positive = 0


    for value, expected_count in expected_counter.items():
        actual_count = actual_counter.get(value, 0)
        true_positive += min(expected_count, actual_count)
    total_expected = sum(expected_counter.values())
    total_actual = sum(actual_counter.values())
    false_positive = (total_actual-true_positive)
    false_negative = (total_expected-true_positive)
    #Precisione
    if true_positive+false_positive > 0:
        precision = (true_positive/(true_positive+false_positive))
    else:
        precision = 0.0
    #Recall
    if true_positive+false_negative > 0:
        recall = (true_positive/(true_positive+false_negative))
    else:
        recall = 0.0
    #F1
    if precision + recall > 0:
        f1 = (2*precision*recall/(precision+recall))
    else:
        f1 = 0.0
    #EXACT MATCH
    exact_match = (expected_counter == actual_counter)
    if exact_match:
        result_status = "correct"
    elif true_positive > 0:
        result_status = "partial"
    else:
        result_status = "incorrect"
    return{
        "status": result_status,
        "exact_match": exact_match,
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "expected_rows": total_expected,
        "actual_rows": total_actual,
        "correct_rows": true_positive,
    }

#------------------ESTRAZIONE ULTIMO execute_sql
def get_final_execute_sql(run):
    """
    Restituisce l'ultimo execute_sql della run 
    """

    tool_calls = run.get("tool_calls", [])
    final_execute_sql = None
    for tool_call in tool_calls:
        if tool_call.get("tool") == "execute_sql":
            final_execute_sql = tool_call
    return final_execute_sql

#------------------PARSING OUTPUT execute_sql
def parse_tool_output(tool_call):
    """
    Estrazione output JSON della chiamata execute_sql
    """
    if tool_call is None:
        return None
    output = tool_call.get("output")
    if output is None:
        return None
    if isinstance(output, dict):
        return output
    if isinstance(output, str):
        try: 
            return json.loads(output)
        except json.JSONDecodeError:
            return None
    return None

#------------------ESTRAZIONE DB
def get_actual_database(tool_call):
    """
    Restituisce il db utilizzato dalla chiamata execute_sql
    """
    if tool_call is None:
        return None
    arguments = tool_call.get("arguments", {})
    return arguments.get("database")

#------------------ESTRAZIONE QUERY
def get_actual_query(tool_call):
    """
    Restituisce la query SQL utilizzata.
    """
    if tool_call is None:
        return None
    arguments = tool_call.get("arguments", {})
    return arguments.get("query")

#------------------ESTRAZIONE COLONNE
def get_actual_columns(tool_call, output):
    if isinstance(output, dict):
        columns = output.get("columns")
        if columns is not None:
            return columns
    if isinstance(output, dict):
        rows = output.get("rows", [])
        if rows and isinstance(rows[0],dict):
            return list(rows[0].keys())
    return []

#------------------ACCURACY COLONNE
def compare_columns(expected_columns, actual_columns):
    """
    Confronta le colonne attese con quelle restituite dalla query dell'agente
    """
    expected = set(expected_columns or [])
    actual = set(actual_columns or [])
    true_positive = len(expected & actual)
    false_positive = len(actual - expected)
    false_negative = len(expected - actual)
    #precisione colonne
    if true_positive + false_positive > 0:
        precision = (true_positive/(true_positive+false_positive))
    else:
        precision = 0.0
    #recall colonne
    if true_positive + false_negative > 0:
        recall = (true_positive/(true_positive+false_negative))
    else:
        recall = 0.0
    #f1 colonne
    if precision + recall > 0:
        f1 = (2*precision*recall/(precision+recall))
    else:
        f1 = 0.0
    #exact match colonne
    exact_match = (expected == actual)

    return {
        "correct": exact_match,
        "expected": list(expected_columns or []),
        "actual": list(actual_columns or []),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

#------------------ACCURACY DATABASE
def compare_database(expected_database, actual_database):
    """
    Verifica se l'agente ha interrogato il database corretto.
    """
    if isinstance(expected_database, str):
        expected_database = [expected_database]
    expected_database = expected_database or []

    correct = (
        expected_database is not None
        and any(expected.upper() == actual_database.upper()
                for expected in expected_database)
    )

    return {
        "correct": correct,
        "expected": expected_database,
        "actual": actual_database
    }

#------------------VALUTAZIONE DI UNA RUN
def evaluate_run(test_case, run):
    """
    Valuta una singola esecuzione di un test
    """
    test_id = test_case.get("id")
    run_id = run.get("run")

    agent_completion = (run.get("agent_completion") is True)
    latency = run.get("latency_total")
    tool_calls_count = run.get("tool_calls_count")

    #ground truth
    expected_database = test_case.get("expected_database")
    expected_columns = test_case.get("expected_columns", [])
    expected_result = test_case.get("expected_result",[])

    #risultato base
    evaluation = {
        "test_id": test_id,
        "run": run_id,
        "agent_completion": agent_completion,
        "latency": latency,
        "tool_calls_count": tool_calls_count,
        "accuracy": {},
        "result_correctness": {},
        "final_sql":None
    } 


    #recupero ultimo execute_sql
    final_execute_sql = get_final_execute_sql(run)
    if final_execute_sql is None:
        evaluation["error"] = ("No execute_sql call found")
        evaluation["accuracy"] = {
            "database":{
                "correct": False,
                "expected": expected_database,
                "actual": None
            },
            "columns": compare_columns(expected_columns, [])
        }
        evaluation["result_correctness"] = compare_results(expected_result, [])
        return evaluation

    #query finale
    actual_database = get_actual_database(final_execute_sql)
    actual_query = get_actual_query(final_execute_sql)
    evaluation["final_sql"] = {"database": actual_database,
                               "query": actual_query
                               }
    #output sql
    output = parse_tool_output(final_execute_sql)
    if output is None:
        evaluation["error"] = ("Unable to parse execute_sql output")
        evaluation["accuracy"] = {
            "database": compare_database(
                expected_database,
                actual_database
            ),
            "columns": compare_columns(expected_columns, [])
        }
        evaluation["result_correctness"] = compare_results(expected_result, [])
        return evaluation
    
    #estrazione metriche
    actual_rows = output.get("rows", [])
    actual_columns = get_actual_columns(final_execute_sql, output)
    database_accuracy = compare_database(expected_database, actual_database)
    column_accuracy = compare_columns(expected_columns, actual_columns)
    result_correctness = compare_results(expected_result, actual_rows)

    #salvataggio metriche
    evaluation["accuracy"] = {
        "database": database_accuracy,
        "columns": column_accuracy
    }
    evaluation["result_correctness"] = (
        result_correctness
    )
    evaluation["actual_result"] = actual_rows
    return evaluation

#---------------CALCOLO STATISTICHE
def calculate_numeric_statistics(values):
    """
    calcoliamo media, mediana, deviazione standard, minimo e massimo di ciascuna metrica
    """
    numeric_values = []
    for value in values:
        numeric_value = to_numeric(value)
        if numeric_value is not None:
            numeric_values.append(numeric_value)
    if not numeric_values:
        return{
            "mean": None,
            "median": None,
            "std": None,
            "min": None,
            "max": None
        }
    if len(numeric_values) >= 2:
        std = statistics.stdev(numeric_values)
    else:
        std = 0.0
    return {
        "mean": statistics.mean(numeric_values),
        "median": statistics.median(numeric_values),
        "std": std,
        "min": min(numeric_values),
        "max": max(numeric_values)
    }

#------------------STATISTICHE DI UN TEST
def calculate_test_statistics(evaluations):
    """
    Calcolo delle statistiche aggregate di un singolo test su tutte le sue run
    """
    if not evaluations:
        return{
            "num_runs": 0,
            "completion_rate": 0.0,
            "latency": calculate_numeric_statistics([]),
            "tool_calls": calculate_numeric_statistics([]),
            "database_accuracy": 0.0,
            "column_accuracy": 0.0,
            "result_precision": 0.0,
            "result_recall": 0.0,
            "result_f1": 0.0,
            "exact_match_rate": 0.0
        }

    completed_runs = [
        evaluation
        for evaluation in evaluations
        if evaluation.get("agent_completion") is True
    ]
    completion_rate = (len(completed_runs)/len(evaluations))

    latency_values = [
            evaluation.get("latency")
            for evaluation in evaluations
            if isinstance(evaluation.get("latency"),(int, float))
            ]
    
    tool_call_values = [
        evaluation.get("tool_calls_count")
        for evaluation in evaluations
        if isinstance(evaluation.get("tool_calls_count"),(int, float))
            ]
    
    database_correct = sum(
        1
        for evaluation in evaluations
        if evaluation.get("accuracy", {}).get("database", {}).get("correct") is True
    )
    database_accuracy = (database_correct/len(evaluations))

    column_correct = sum(
        1
        for evaluation in evaluations
        if evaluation.get("accuracy", {}).get("columns", {}).get("correct") is True
    )
    column_accuracy = (column_correct/len(evaluations))

    #metriche dei risultati
    correct_results = sum(1
                          for evaluation in evaluations
                          if evaluation.get("result_correctness", {}).get("status")== "correct"
                         )
    partial_results = sum(1
                          for evaluation in evaluations
                          if evaluation.get("result_correctness",{}).get("status") == "partial"
                          )
    incorrect_results = sum(1
                            for evaluation in evaluations
                            if evaluation.get("result_correctness", {}).get("status") == "incorrect"
                            )
    correct_result_rate = correct_results/len(evaluations)
    partial_result_rate = partial_results/len(evaluations)
    incorrect_result_rate = incorrect_results/len(evaluations)
    

    precision_values = [
        evaluation.get("result_correctness", {}).get("precision", 0.0)
        for evaluation in evaluations
    ]

    recall_values = [
        evaluation.get("result_correctness", {}).get("recall", 0.0)
        for evaluation in evaluations
    ]

    f1_values = [
        evaluation.get("result_correctness", {}).get("f1", 0.0)
        for evaluation in evaluations
    ]

    exact_matches = sum(
        1
        for evaluation in evaluations
        if evaluation.get("result_correctness", {}).get("exact_match") is True
    )
    exact_match_rate = (exact_matches/len(evaluations))

    return {
        "num_runs": len(evaluations),
        "completion_rate": completion_rate,
        "latency": calculate_numeric_statistics(latency_values),
        "tool_calls": calculate_numeric_statistics(tool_call_values),
        "database_accuracy": database_accuracy,
        "column_accuracy": column_accuracy,
        "result_correct_rate": correct_result_rate,
        "result_partial_rate": partial_result_rate,
        "result_incorrect_rate": incorrect_result_rate,
        "result_precision": statistics.mean(precision_values),
        "result_recall": statistics.mean(recall_values),
        "result_f1": statistics.mean(f1_values),
        "exact_match_rate": exact_match_rate
    }



#---------------------STATISTICHE GLOBALI
def calculate_global_statistics(all_evaluations):
    """
    Calcola le statistiche complessive del benchmark.
    """

    if not all_evaluations:
        return {
            "total_runs": 0,
            "completed_runs": 0,
            "completion_rate": 0.0
        }

    total_runs = len(all_evaluations)

    completed_runs = sum(
        1
        for evaluation in all_evaluations
        if evaluation.get("agent_completion") is True
    )
    completion_rate = (completed_runs/total_runs)

    latency_values = [
        evaluation.get("latency")
        for evaluation in all_evaluations
        if isinstance(evaluation.get("latency"),(int, float))
    ]

    tool_call_values = [
        evaluation.get("tool_calls_count")
        for evaluation in all_evaluations
        if isinstance(evaluation.get("tool_calls_count"),(int, float))
    ]

    database_correct = sum(
        1
        for evaluation in all_evaluations
        if evaluation.get("accuracy", {}).get("database", {}).get("correct") is True
    )
    database_accuracy = (database_correct/total_runs)

    column_correct = sum(
        1
        for evaluation in all_evaluations
        if evaluation.get("accuracy", {}).get("columns", {}).get("correct") is True
    )
    column_accuracy = (column_correct/total_runs)


    correct_results = sum(1
                          for evaluation in all_evaluations
                          if evaluation.get("result_correctness", {}).get("status") == "correct"
                          )
    partial_results = sum(1
                          for evaluation in all_evaluations
                          if evaluation.get("result_correctness", {}).get("status") == "partial"
                          )
    
    incorrect_results = sum(1
                            for evaluation in all_evaluations
                            if evaluation.get("result_correctness", {}).get("status") == "incorrect"
                            )
    correct_result_rate = correct_results / total_runs
    partial_result_rate = partial_results / total_runs
    incorrect_result_rate = incorrect_results / total_runs

    precision_values = [
        evaluation.get("result_correctness", {}).get("precision", 0.0)
        for evaluation in all_evaluations
    ]

    recall_values = [
        evaluation.get("result_correctness", {}).get("recall", 0.0)
        for evaluation in all_evaluations
    ]

    f1_values = [
        evaluation.get("result_correctness", {}).get("f1", 0.0)
        for evaluation in all_evaluations
    ]

    exact_matches = sum(
        1
        for evaluation in all_evaluations
        if evaluation.get("result_correctness", {}).get("exact_match") is True
    )
    exact_match_rate = (exact_matches/total_runs)

    return {
        "total_runs": total_runs,
        "completed_runs": completed_runs,
        "completion_rate": completion_rate,
        "latency": calculate_numeric_statistics(latency_values),
        "tool_calls": calculate_numeric_statistics(tool_call_values),
        "database_accuracy": database_accuracy,
        "column_accuracy": column_accuracy,
        "result_correct_rate": correct_result_rate,
        "result_partial_rate": partial_result_rate,
        "result_incorrect_rate": incorrect_result_rate,
        "result_precision": statistics.mean(precision_values),
        "result_recall": statistics.mean(recall_values),
        "result_f1": statistics.mean(f1_values),
        "exact_match_rate": exact_match_rate
    }

#---------------------VALUTAZIONE TEST
def evaluate(test_cases_data, test_results_data):
    """
    Funzione principale della logica dell'evaluator
    """
    #caricamento dati test_case 
    if isinstance(test_cases_data, dict):
        test_cases = test_cases_data.get("tests",[])
    else:
        test_cases = test_cases_data

    test_cases_by_id = {    #indicizzazione ogni test
        str(test_case["id"]): test_case
        for test_case in test_cases
    }

    #caricamento risultato test
    if isinstance(test_results_data, dict):
        test_results = test_results_data.get("results", [])
    else:
        test_results = test_results_data

    #valutazione
    evaluated_tests = []
    all_evaluations = []
    missing_test_cases = []
    for test_result in test_results:
        test_id = test_result.get("id")
        test_case = test_cases_by_id.get(str(test_id))

        if test_case is None:
            missing_test_cases.append(test_id)
            continue

        question = test_result.get("question",test_case.get("question"))
        runs = test_result.get("runs", [])
        run_evaluations = []
        # Valutazione di ogni run
        for run in runs:
            evaluation = evaluate_run(test_case, run)
            run_evaluations.append(evaluation)
            all_evaluations.append(evaluation) 
        #Statistiche test
        test_statistics = (calculate_test_statistics(run_evaluations))
        evaluated_tests.append({
            "id": test_id,
            "question": question,
            "num_runs": len(runs),
            "runs": run_evaluations,
            "statistics": test_statistics
        })

    #STATISTICHE GLOBALI
    global_statistics = (calculate_global_statistics(all_evaluations))
    #STATISTICHE TEST-LEVEL
    test_completion_rates = [
        test["statistics"]["completion_rate"]
        for test in evaluated_tests
    ]
    if test_completion_rates:
        mean_test_completion_rate = (statistics.mean(test_completion_rates))
    else:
        mean_test_completion_rate = 0.0
    #test con tutte run corrette
    tests_all_runs_correct = 0
    tests_at_least_one_correct = 0

    for test in evaluated_tests:
        runs = test["runs"]

        if not runs:
            continue

        correct_runs = sum(
            1
            for run in runs
            if run.get("result_correctness", {}).get("exact_match") is True
        )

        if correct_runs == len(runs):
            tests_all_runs_correct += 1

        if correct_runs > 0:
            tests_at_least_one_correct += 1

    total_tests = len(evaluated_tests)

    if total_tests > 0:
        all_runs_completion_rate = (tests_all_runs_correct/total_tests)
        at_least_one_completion_rate = (tests_at_least_one_correct/total_tests)

    else:
        all_runs_completion_rate = 0.0
        at_least_one_completion_rate = 0.0

    
    #--------------------RISULTATO FINALE
    evaluation_result = {
        "configuration": {
            "test_cases_file": TEST_CASES_FILE,
            "results_file": RESULTS_FILE,
            "output_file": OUTPUT_FILE,
            "num_runs_declared": test_results_data.get("num_runs")
            if isinstance(test_results_data, dict)
            else None
        },

        "summary": {
            "total_tests": total_tests,
            "total_runs": len(all_evaluations),
            "missing_test_cases": (missing_test_cases),
            "run_completion_rate": (global_statistics["completion_rate"]),
            "mean_test_completion_rate": (mean_test_completion_rate),
            "tests_all_runs_completion_rate": (all_runs_completion_rate),
            "tests_at_least_one_completion_rate": (at_least_one_completion_rate),
            "latency": (global_statistics["latency"]),
            "tool_calls": (global_statistics["tool_calls"]),
            "database_accuracy": (global_statistics["database_accuracy"]),
            "column_accuracy": (global_statistics["column_accuracy"]),
            "result_correct_rate": global_statistics["result_correct_rate"],
            "result_partial_rate": global_statistics["result_partial_rate"],
            "result_incorrect_rate": global_statistics["result_incorrect_rate"],
            "result_precision": (global_statistics["result_precision"]),
            "result_recall": (global_statistics["result_recall"]),
            "result_f1": (global_statistics["result_f1"]),
            "exact_match_rate": (global_statistics["exact_match_rate"])
        },
        "tests": evaluated_tests
    }

    return evaluation_result


# ============================================================
# STAMPA RISULTATI
# ============================================================

def print_results(evaluation):
    """
    Stampa un riepilogo leggibile dei risultati.
    """

    summary = evaluation["summary"]
    print("\n")
    print("=" * 70)
    print("                    EVALUATION RESULTS")
    print("=" * 70)
    print(f"\nTest totali: " f"{summary['total_tests']}")
    print(f"Run totali: " f"{summary['total_runs']}")
    print(f"\nRun completion rate: " f"{summary['run_completion_rate'] * 100:.2f}%")
    print(f"Test completion rate medio: " f"{summary['mean_test_completion_rate'] * 100:.2f}%")
    print(f"Test con TUTTE le run corrette: " f"{summary['tests_all_runs_completion_rate'] * 100:.2f}%")
    print(f"Test con ALMENO una run corretta: " f"{summary['tests_at_least_one_completion_rate'] * 100:.2f}%")

    print("\n--- LATENZA ---")
    latency = summary["latency"]
    if latency["mean"] is not None:
        print(f"Media:   {latency['mean']:.3f}s")
        print(f"Mediana: {latency['median']:.3f}s")
        print(f"Std:     {latency['std']:.3f}s")
        print(f"Min:     {latency['min']:.3f}s")
        print(f"Max:     {latency['max']:.3f}s")

    print("\n--- TOOL CALLS ---")
    tool_calls = summary["tool_calls"]
    if tool_calls["mean"] is not None:
        print(f"Media:   {tool_calls['mean']:.2f}")
        print(f"Mediana: {tool_calls['median']:.2f}")
        print(f"Min:     {tool_calls['min']:.0f}")
        print(f"Max:     {tool_calls['max']:.0f}")

    print("\n--- ACCURACY ---")
    print(f"Database accuracy: " f"{summary['database_accuracy'] * 100:.2f}%")
    print(f"Column accuracy:   " f"{summary['column_accuracy'] * 100:.2f}%")

    print("\n--- RESULT CORRECTNESS ---")
    print(f"Completamente corretti: "  f"{summary['result_correct_rate'] * 100:.2f}%")
    print(f"Parzialmente corretti:  "  f"{summary['result_partial_rate'] * 100:.2f}%")
    print(f"Errati: "  f"{summary['result_incorrect_rate'] * 100:.2f}%")
    print(f"Precision: "  f"{summary['result_precision'] * 100:.2f}%")
    print(f"Recall:    "  f"{summary['result_recall'] * 100:.2f}%")
    print(f"F1:        "  f"{summary['result_f1'] * 100:.2f}%")
    print(f"Exact match: "  f"{summary['exact_match_rate'] * 100:.2f}%")

    print("\n")
    print("=" * 70)
    print("                    PER TEST")
    print("=" * 70)
    for test in evaluation["tests"]:
        stat = test["statistics"]
        print(f"\nTest {test['id']}: " f"{test['question']}")
        print(f"  Run: {stat['num_runs']}")
        print(
            f"  Completion rate: "
            f"{stat['completion_rate'] * 100:.2f}%"
        )

        if stat["latency"]["mean"] is not None:

            print(f"  Latenza media: "  f"{stat['latency']['mean']:.3f}s")

        if stat["tool_calls"]["mean"] is not None:
            print(f"  Tool calls medi: "  f"{stat['tool_calls']['mean']:.2f}")

        print(
            f"  Database accuracy: "
            f"{stat['database_accuracy'] * 100:.2f}%"
        )

        print(
            f"  Column accuracy: "
            f"{stat['column_accuracy'] * 100:.2f}%"
        )

        print(
            f"  Risultato completamente corretto: "
            f"{stat['result_correct_rate'] * 100:.2f}%"
        )

        print(
            f"  Risultato parzialmente corretto:  "
            f"{stat['result_partial_rate'] * 100:.2f}%"
        )

        print(
            f"  Risultato errato:                 "
            f"{stat['result_incorrect_rate'] * 100:.2f}%"
        )

        print(
            f"  Result precision: "
            f"{stat['result_precision'] * 100:.2f}%"
        )

        print(
            f"  Result recall: "
            f"{stat['result_recall'] * 100:.2f}%"
        )

        print(
            f"  Result F1: "
            f"{stat['result_f1'] * 100:.2f}%"
        )

        print(
            f"  Exact match: "
            f"{stat['exact_match_rate'] * 100:.2f}%"
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print("\n")
    print("=" * 70)
    print("                 AVVIO EVALUATOR")
    print("=" * 70)

    print(
        f"\nTest cases: {TEST_CASES_FILE}"
    )

    print(
        f"Test results: {RESULTS_FILE}"
    )

    # --------------------------------------------------------
    # Caricamento file
    # --------------------------------------------------------

    try:

        test_cases_data = load_json(
            TEST_CASES_FILE
        )

    except FileNotFoundError:

        print(
            f"\nERRORE: file non trovato:"
            f"\n{TEST_CASES_FILE}"
        )

        return

    try:

        test_results_data = load_json(
            RESULTS_FILE
        )

    except FileNotFoundError:

        print(
            f"\nERRORE: file non trovato:"
            f"\n{RESULTS_FILE}"
        )

        return

    # --------------------------------------------------------
    # Evaluation
    # --------------------------------------------------------

    evaluation = evaluate(
        test_cases_data,
        test_results_data
    )

    # --------------------------------------------------------
    # Salvataggio
    # --------------------------------------------------------

    save_json(
        OUTPUT_FILE,
        evaluation
    )

    # --------------------------------------------------------
    # Stampa
    # --------------------------------------------------------

    print_results(
        evaluation
    )

    print(
        f"\nRisultati salvati in:"
        f"\n{OUTPUT_FILE}"
    )

    print("\n")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    main()



