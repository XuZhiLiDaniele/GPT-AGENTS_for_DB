"""
plot_results.py

Confronto delle prestazioni di due agenti LLM (Gemma vs Qwen) sui risultati prodotti dall'evaluator in base alle metriche di accuracy, precisione e latenza.
I test possono anche essere raggruppati per livelli
Sono disponibili due modalità: 
    python plot_results.py -> confronto totale su tutti i test 
    python plot_results.py --levels -> confronto per livelli

    """

import json
import os
import argparse

import matplotlib.pyplot as plt
import numpy as np


#--------------------CONFIGURAZIONE 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GEMMA_FILE = os.path.join(BASE_DIR, "evaluation_results_gemma.json")
DEFAULT_QWEN_FILE = os.path.join(BASE_DIR, "evaluation_results_qwen.json")
OUTPUT_DIR = os.path.join(BASE_DIR,"plots")


DEFAULT_LEVELS = {
    "Semplice": list(range(1, 4)),
    "Intermedio": list(range(4, 7)),
    "Complesso": list(range(7, 10))
}

#--------------------LETTURA FILE
def load_json(filename):
    """
    Carica un file JSON.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File non trovato: {filename}")

    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)

#--------------------ESTRAZIONE RUN
def get_runs(data):
    """
    Estrae tutte le valutazioni individuali dal file di valutazione.
    Per ogni run restituisce una lista del tipo:
    [
        {
            "test_id": 1,
            "run": 1,
            "accuracy": {...},
            "precision": {...},
            "latency": ...
        },
        ...
    ]
    """

    if not isinstance(data, dict):
        raise ValueError("Il file dei risultati deve contenere un oggetto JSON.")

    runs = data.get("runs", [])
    if not isinstance(runs, list):
        raise ValueError("Il campo 'runs' deve essere una lista.")
    
    return runs

#--------------------RAGGRUPPAMENTO PER TEST
def filter_runs(runs, test_ids):
    """
    Mantiene solamente le run appartenenti ai test richiesti.
    """
    test_ids = set(test_ids)
    return [
        run
        for run in runs
        if run.get("test_id") in test_ids
    ]

#--------------------CALCOLO STATISTICHE
def calculate_statistics(runs):
    """
    Calcola le statistiche medie sulle run ricevute.
    """

    if not runs:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "latency": 0.0
        }

    accuracy_values = []
    precision_values = []
    latency_values = []

    for run in runs:
        #Accuracy
        accuracy = run.get("accuracy", {})
        overall_accuracy = accuracy.get("overall")
        if overall_accuracy is not None:
            accuracy_values.append(float(overall_accuracy))

        #Precision
        precision = run.get("precision", {})
        precision_value = precision.get("value")
        if precision_value is not None:
            precision_values.append(float(precision_value))

        #Latenza
        latency = run.get("latency")
        if latency is not None:
            latency_values.append(float(latency))

    return {
        "accuracy": (sum(accuracy_values) / len(accuracy_values)
                     if accuracy_values else 0.0
                    ),
        "precision": (sum(precision_values) / len(precision_values)
                      if precision_values else 0.0
                     ),
        "latency": (sum(latency_values) / len(latency_values)
                    if latency_values else 0.0
                   )
        }

#--------------------CALCOLO STATISTICHE PER LIVELLO
def calculate_level_statistics(data, levels):
    """
    Calcola le statistiche per ciascun livello di difficoltà.
    """
    runs = get_runs(data)
    results = {}
    for level_name, test_ids in levels.items():
        selected_runs = filter_runs(runs, test_ids)
        results[level_name] = calculate_statistics(selected_runs)
    return results
#--------------------CALCOLO STATISTICHE TOTALI
def calculate_total_statistics(data):
    """
    Calcola le statistiche medie considerando tutti i test presenti nel file
    """
    runs = get_runs(data)
    return calculate_statistics(runs)

#--------------------STAMPA STATISTICHE
def print_statistics(agent_name, statistics):
    """
    Stampa le statistiche in maniera leggibile.
    """
    print()
    print("=" * 70)
    print(agent_name.upper())
    print("=" * 70)

    for level, values in statistics.items():
        print()
        print(level)
        print(f"  Accuracy:  " 
              f"{values['accuracy'] * 100:.2f}%"
             )
        print(f"  Precision: "
              f"{values['precision'] * 100:.2f}%"
             )
        print(f"  Latency:   "
              f"{values['latency']:.2f} ms"
             )

#--------------------STAMPA CONFRONTO
def print_comparison(gemma_stats, qwen_stats):
    """
    Stampa il confronto Gemma vs Qwen.
    """
    print()
    print("=" * 70)
    print("CONFRONTO GEMMA VS QWEN")
    print("=" * 70)

    for level in gemma_stats.keys():
        gemma = gemma_stats[level]
        qwen = qwen_stats[level]
        print()
        print(f"{level}")
        print(f"  Accuracy:  "
              f"Gemma {gemma['accuracy'] * 100:.2f}%  |  "
              f"Qwen {qwen['accuracy'] * 100:.2f}%"
             )
        print(f"  Precision: "
              f"Gemma {gemma['precision'] * 100:.2f}%  |  "
              f"Qwen {qwen['precision'] * 100:.2f}%"
             )
        print(f"  Latency:   "
              f"Gemma {gemma['latency']:.2f} ms  |  "
              f"Qwen {qwen['latency']:.2f} ms"
             )

#--------------------CREAZIONE CARTELLA OUTPUT
def create_output_directory():
    """
    Crea la cartella dei grafici se non esiste.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

#--------------------CREAZIONE CARTELLA OUTPUT
def plot_metric(gemma_stats, qwen_stats, metric, title, ylabel, filename, percentage=False):
    """
    Crea un bar chart Gemma vs Qwen.
    """
    levels = list(gemma_stats.keys())

    gemma_values = [gemma_stats[level][metric]
                    for level in levels
                   ]
    qwen_values = [qwen_stats[level][metric]
                   for level in levels
                  ]

    if percentage:
        gemma_values = [value * 100
                        for value in gemma_values
                       ]
        qwen_values = [value * 100
                       for value in qwen_values
                      ]
    x = np.arange(len(levels))
    width = 0.35
    fig, ax = plt.subplots(figsize=(9, 6))

    bars_gemma = ax.bar(x - width / 2, gemma_values, width, label="Gemma")
    bars_qwen = ax.bar(x + width / 2, qwen_values, width, label="Qwen")
    ax.set_title(title, fontsize=14, fontweight="bold")

    ax.set_ylabel(ylabel)
    ax.set_xticks(x)
    ax.set_xticklabels(levels)
    ax.legend()
    ax.grid(axis="y", linestyle="--", alpha=0.4)

#--------------------PERCENTUALE ASSE Y
    if percentage:
        ax.set_ylim(0, 100)

#--------------------VALORI BARRE
    def add_labels(bars):
        for bar in bars:
            height = bar.get_height()

            if percentage:
                text = f"{height:.1f}%"
            else:
                text = f"{height:.0f}"

            ax.annotate(text, xy=(bar.get_x() + bar.get_width() / 2, height), xytext=(0, 4), textcoords="offset points", ha="center", va="bottom", fontsize=9)
    add_labels(bars_gemma)
    add_labels(bars_qwen)
    fig.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, filename)
    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)
    print(f"\nGrafico salvato: {output_path}")

#--------------------PLOT DEL CHART TOTALE
def plot_total_statistics(gemma_stats, qwen_stats):
    """
    Crea tre bar chart per il confronto totale tra Gemma e Qwen
    """
    create_output_directory()
    metrics = [
                ("accuracy", "Accuracy", "Accuracy(%)", True),
                ("precision", "Precision", "Precision (%)", True),
                ("latency", "Latency", "Latency (ms)", False)
              ]
    for metric, title, ylabel, percentage in metrics:
        gemma_value = gemma_stats[metric]
        qwen_value = qwen_stats[metric]

        if percentage:
            gemma_value *= 100
            qwen_value *= 100

        labels = ["Gemma", "Qwen"]
        values = [gemma_value, qwen_value]
        fig, ax = plt.subplots(figsize=(7, 5))

        bars = ax.bar(labels, values)
        ax.set_title(f"{title} - Gemma vs Qwen", fontsize=14, fontweight="bold")
        ax.set_ylabel(ylabel)

        if percentage:
            ax.set_ylim(0, 100)

        ax.grid(axis="y", linestyle="--", alpha=0.4)

        for bar in bars:
            height = bar.get_height()
            if percentage:
                text = f"{height:.2f}%"
            else:
                text = f"{height:.2f} ms"

            ax.annotate(text,
                        xy=(bar.get_x() + bar.get_width() / 2, height),
                        xytext=(0, 4),
                        textcoords="offset points",
                        ha="center",
                        va="bottom"
                       )
        fig.tight_layout()
        filename = f"{metric}_total_comparison.png"
        output_path = os.path.join(OUTPUT_DIR, filename)
        fig.savefig(output_path, dpi=300, bbox_inches="tight")
        plt.show()
        plt.close(fig)
        print(f"\nGrafico salvato: {output_path}")
    
#--------------------CREAZIONE DI TUTTI I GRAFICI
def create_plots(gemma_stats, qwen_stats):
    """
    Crea i tre grafici principali:
        1. Accuracy
        2. Precision
        3. Latency
    """
    create_output_directory()

    plot_metric(gemma_stats, qwen_stats, metric="accuracy", title="Accuracy - Gemma vs Qwen", ylabel="Accuracy (%)", filename="accuracy_comparison.png", percentage=True) #Accuracy

    plot_metric(gemma_stats, qwen_stats, metric="precision", title="Precision - Gemma vs Qwen", ylabel="Precision (%)", filename="precision_comparison.png", percentage=True) #Precision

    plot_metric(gemma_stats, qwen_stats, metric="latency", title="Latency - Gemma vs Qwen", ylabel="Latency (ms)", filename="latency_comparison.png", percentage=False) #Latency

#--------------------MAIN
def main():

    parser = argparse.ArgumentParser(
        description=("Confronta le performance di Gemma e Qwen su gruppi di test.")
    )
    parser.add_argument("--gemma", default = DEFAULT_GEMMA_FILE, help = ("File evaluation_results di -Gemma."))
    parser.add_argument("--qwen", default=DEFAULT_QWEN_FILE, help=("File evaluation_results di Qwen"))
    parser.add_argument("--levels", action ="store_true", help="Confronta Gemma e Qwen per livello di difficolta")
    args = parser.parse_args()

    # --------------------------------------------------------
    # Caricamento dati
    # --------------------------------------------------------

    gemma_data = load_json(args.gemma)
    qwen_data = load_json(args.qwen)
    #confronto per difficoltà
    if args.levels:
        gemma_stats = calculate_level_statistics(gemma_data, DEFAULT_LEVELS)
        qwen_stats = calculate_level_statistics(qwen_data, DEFAULT_LEVELS)
        print_statistics("Gemma", gemma_stats)
        print_statistics("Qwen",qwen_stats)
        print_comparison(gemma_stats, qwen_stats)
        create_plots(gemma_stats, qwen_stats)

    #confronto totale
    else:
        gemma_stats = calculate_total_statistics(gemma_data)
        qwen_stats = calculate_total_statistics(qwen_data)
        total_gemma = {"Totale": gemma_stats}
        total_qwen = {"Totale": qwen_stats}
        print_statistics("Gemma - Totale", {"Totale": gemma_stats})
        print_statistics("Qwen - Totale", {"Totale": qwen_stats})
        print_comparison(total_gemma, total_qwen)
        plot_total_statistics(gemma_stats, qwen_stats)

# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()