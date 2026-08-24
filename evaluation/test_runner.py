import asyncio
import json
import time
import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from autoTestAgent import Agent


# ============================================================
# CONFIGURAZIONE
# ============================================================

TEST_CASES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "test_cases.json")

# Quante volte eseguire ogni test
NUM_RUNS = 1

# File in cui salvare i risultati
RESULTS_FILE = "test_results.json"


# ============================================================
# CARICAMENTO TEST CASES
# ============================================================

def load_test_cases():

    with open(TEST_CASES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


# ============================================================
# ESECUZIONE DEI TEST
# ============================================================

async def run_tests():

    test_cases = load_test_cases()

    agent = Agent()

    all_results = []

    print("\n========================================")
    print("        AVVIO TEST AGENTE")
    print("========================================")

    print(f"Test cases: {len(test_cases)}")
    print(f"Run per test: {NUM_RUNS}")
    print(
        f"Esecuzioni totali: "
        f"{len(test_cases) * NUM_RUNS}"
    )

    # --------------------------------------------------------
    # Ciclo sui test case
    # --------------------------------------------------------

    for test_case in test_cases:

        test_id = test_case["id"]
        question = test_case["question"]
        ground_truth = test_case.get(
            "ground_truth",
            None
        )

        print("\n----------------------------------------")
        print(f"TEST {test_id}")
        print(f"Domanda: {question}")
        print("----------------------------------------")

        test_runs = []

        # ----------------------------------------------------
        # Ripetizione del test
        # ----------------------------------------------------

        for run in range(1, NUM_RUNS + 1):

            print(
                f"\n  Run {run}/{NUM_RUNS}"
            )

            start = time.perf_counter()

            result = await agent.run(question)

            end = time.perf_counter()

            # Questo tempo misura anche l'eventuale
            # overhead del runner.
            # La metrica ufficiale rimane quella
            # restituita dall'Agent.
            runner_latency = end - start

            run_result = {
                "run": run,
                "answer": result.get("answer"),
                "success": result.get("success"),

                "latency_total": result.get(
                    "latency_total"
                ),

                "tool_calls_count": result.get(
                    "tool_calls_count"
                ),

                "tool_calls": result.get(
                    "tool_calls",
                    []
                )
            }

            # Se Agent ha restituito un errore
            if not result.get("success"):

                run_result["error"] = result.get(
                    "error"
                )

            test_runs.append(run_result)

            print(
                f"  Success: {run_result['success']}"
            )

            print(
                f"  Latenza: "
                f"{run_result['latency_total']:.3f}s"
            )

            print(
                f"  Tool chiamati: "
                f"{run_result['tool_calls_count']}"
            )

        # ----------------------------------------------------
        # Risultato del test case
        # ----------------------------------------------------

        all_results.append({
            "id": test_id,
            "question": question,
            "ground_truth": ground_truth,
            "runs": test_runs
        })

    return all_results


# ============================================================
# CALCOLO STATISTICHE
# ============================================================

def calculate_statistics(results):

    statistics = []

    for test in results:

        runs = test["runs"]

        successful_runs = [
            run
            for run in runs
            if run["success"]
        ]

        if not successful_runs:

            statistics.append({
                "id": test["id"],
                "success_rate": 0,
                "average_latency": None,
                "average_tool_calls": None
            })

            continue

        # --------------------------------------------
        # Latenza media
        # --------------------------------------------

        average_latency = sum(
            run["latency_total"]
            for run in successful_runs
        ) / len(successful_runs)

        # --------------------------------------------
        # Numero medio di tool
        # --------------------------------------------

        average_tool_calls = sum(
            run["tool_calls_count"]
            for run in successful_runs
        ) / len(successful_runs)

        # --------------------------------------------
        # Success rate
        # --------------------------------------------

        success_rate = (
            len(successful_runs)
            / len(runs)
        )

        statistics.append({
            "id": test["id"],
            "success_rate": success_rate,
            "average_latency": average_latency,
            "average_tool_calls": average_tool_calls
        })

    return statistics


# ============================================================
# MAIN
# ============================================================

async def main():

    start = time.perf_counter()

    results = await run_tests()

    statistics = calculate_statistics(results)

    total_time = time.perf_counter() - start

    # --------------------------------------------------------
    # Salvataggio risultati
    # --------------------------------------------------------

    output = {
        "num_runs": NUM_RUNS,
        "results": results,
        "statistics": statistics
    }

    with open(
        RESULTS_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            output,
            file,
            indent=4,
            ensure_ascii=False
        )

    # --------------------------------------------------------
    # Riepilogo
    # --------------------------------------------------------

    print("\n\n========================================")
    print("           RISULTATI TEST")
    print("========================================")

    for stat in statistics:

        print(
            f"\nTest {stat['id']}"
        )

        print(
            f"  Success rate: "
            f"{stat['success_rate'] * 100:.1f}%"
        )

        if stat["average_latency"] is not None:

            print(
                f"  Latenza media: "
                f"{stat['average_latency']:.3f}s"
            )

            print(
                f"  Tool medi: "
                f"{stat['average_tool_calls']:.2f}"
            )

        else:

            print(
                "  Nessuna esecuzione completata"
            )

    print("\n========================================")
    print(
        f"Risultati salvati in: {RESULTS_FILE}"
    )
    print(
        f"Tempo totale runner: {total_time:.3f}s"
    )
    print("========================================")


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    asyncio.run(main())