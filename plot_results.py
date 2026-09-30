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
DEFAULT_GEMMA_FILE = os.path.join(BASE_DIR, "evaluation/gemma_resultsM_evaluation.json")
DEFAULT_QWEN_FILE = os.path.join(BASE_DIR, "evaluation/qwen_resultsM_evaluation.json")
OUTPUT_DIR = os.path.join(BASE_DIR,"plots")

#--------------------LETTURA FILE
def load_json(filename):
    """
    Carica un file JSON.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"File non trovato: {filename}")

    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)
    
#--------------------STAMPA STATISTICHE
def print_statistics(agent_name, statistics):
    """
    Stampa le statistiche già calcolate dall'evaluator.
    """
    print()
    print("=" * 70)
    print(agent_name.upper())
    print("=" * 70)

    for level, values in statistics.items():
        print()
        print(level)

        accuracy = values["accuracy"]["overall"]
        precision = values["precision"]
        latency = values["latency"]

        print(
            f"  Accuracy: {accuracy['mean'] * 100:.2f}% "
            f"[{accuracy['ci_lower'] * 100:.2f}%, "
            f"{accuracy['ci_upper'] * 100:.2f}%]"
        )

        print(
            f"  Precision: {precision['mean'] * 100:.2f}% "
            f"[{precision['ci_lower'] * 100:.2f}%, "
            f"{precision['ci_upper'] * 100:.2f}%]"
        )

        print(
            f"  Latency: {latency['mean']:.2f} ms "
            f"[{latency['ci_lower']:.2f}, "
            f"{latency['ci_upper']:.2f}] ms"
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

        gemma_accuracy = gemma["accuracy"]["overall"]["mean"]
        qwen_accuracy = qwen["accuracy"]["overall"]["mean"]

        gemma_precision = gemma["precision"]["mean"]
        qwen_precision = qwen["precision"]["mean"]

        gemma_latency = gemma["latency"]["mean"]
        qwen_latency = qwen["latency"]["mean"]

        print()
        print(level)

        print(
            f"  Accuracy:  "
            f"Gemma {gemma_accuracy * 100:.2f}%  |  "
            f"Qwen {qwen_accuracy * 100:.2f}%"
        )
        print(
            f"  Precision: "
            f"Gemma {gemma_precision * 100:.2f}%  |  "
            f"Qwen {qwen_precision * 100:.2f}%"
        )
        print(
            f"  Latency:   "
            f"Gemma {gemma_latency:.2f} ms  |  "
            f"Qwen {qwen_latency:.2f} ms"
        )

#--------------------CREAZIONE CARTELLA OUTPUT
def create_output_directory():
    """
    Crea la cartella dei grafici se non esiste.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)

#--------------------CREAZIONE CARTELLA OUTPUT
def plot_metric(gemma_stats, qwen_stats, metric, title, xlabel, filename, percentage=False):
    """
    Crea un bar chart Gemma vs Qwen per livello di difficoltà.

    Le statistiche e gli intervalli di confidenza vengono
    letti direttamente dal file prodotto dall'evaluator.
    """

    levels = list(gemma_stats.keys())

    # ========================================================
    # ESTRAZIONE STATISTICHE
    # ========================================================
    if metric == "accuracy":
        gemma_metric = [
            gemma_stats[level]["accuracy"]["overall"]
            for level in levels
        ]
        qwen_metric = [
            qwen_stats[level]["accuracy"]["overall"]
            for level in levels
        ]
    else:
        gemma_metric = [
            gemma_stats[level][metric]
            for level in levels
        ]
        qwen_metric = [
            qwen_stats[level][metric]
            for level in levels
        ]

    # ========================================================
    # MEDIA
    # ========================================================
    gemma_values = [value["mean"] for value in gemma_metric]
    qwen_values = [value["mean"] for value in qwen_metric]
    # ========================================================
    # MARGINE CI
    # ========================================================
    gemma_errors = [value["margin"] for value in gemma_metric]
    qwen_errors = [value["margin"] for value in qwen_metric]
    # ========================================================
    # CONVERSIONE PERCENTUALE
    # ========================================================
    if percentage:
        gemma_values = [value * 100 for value in gemma_values]
        qwen_values = [value * 100 for value in qwen_values]
        gemma_errors = [error * 100 for error in gemma_errors]
        qwen_errors = [error * 100 for error in qwen_errors]
    # ========================================================
    # BAR CHART
    # ========================================================
    y = np.arange(len(levels))
    height = 0.35
    fig, ax = plt.subplots(figsize=(9, 6))
    bars_gemma = ax.barh(
        y - height / 2,
        gemma_values,
        height,
        xerr=gemma_errors,
        capsize=4,
        label="Gemma"
    )

    bars_qwen = ax.barh(
        y + height / 2,
        qwen_values,
        height,
        xerr=qwen_errors,
        capsize=4,
        label="Qwen"
    )

    # ========================================================
    # ASSI
    # ========================================================

    ax.set_title(title, fontsize=14, fontweight="bold")
    ax.set_yticks(y)
    ax.set_yticklabels(levels)
    ax.set_xlabel(xlabel)
    ax.legend()

    ax.grid(axis="x", linestyle="--", alpha=0.4)
    if percentage:
        ax.set_xlim(0, 100)

    # ========================================================
    # LABEL VALORI
    # ========================================================
    def add_labels(bars):
        for bar in bars:
            width = bar.get_width()
            if percentage:
                text = f"{width:.1f}%"
            else:
                text = f"{width:.0f} ms"

            ax.annotate(
                text,
                xy=(width, bar.get_y() + bar.get_height() / 2),
                xytext=(5, 0),
                textcoords="offset points",
                ha="left",
                va="center",
                fontsize=9
            )

    add_labels(bars_gemma)
    add_labels(bars_qwen)

    # ========================================================
    # SALVATAGGIO
    # ========================================================

    fig.tight_layout()

    output_path = os.path.join(OUTPUT_DIR,filename)

    fig.savefig(output_path, dpi=300, bbox_inches="tight")

    plt.show()
    plt.close(fig)

    print(f"\nGrafico salvato: {output_path}")


#--------------------PLOT DEL CHART TOTALE
# #def plot_total_statistics(gemma_stats, qwen_stats):
    # """
    # Crea tre bar chart per il confronto totale tra Gemma e Qwen
    # """
    # create_output_directory()
    # metrics = [
    #             ("accuracy", "Accuracy", "Accuracy(%)", True),
    #             ("precision", "Precision", "Precision (%)", True),
    #             ("latency", "Latency", "Latency (ms)", False)
    #           ]
    # for metric, title, ylabel, percentage in metrics:
    #     gemma_value = gemma_stats[metric]
    #     qwen_value = qwen_stats[metric]

    #     if percentage:
    #         gemma_value *= 100
    #         qwen_value *= 100

    #     labels = ["Gemma", "Qwen"]
    #     values = [gemma_value, qwen_value]
    #     fig, ax = plt.subplots(figsize=(7, 5))

    #     bars = ax.bar(labels, values)
    #     ax.set_title(f"{title} - Gemma vs Qwen", fontsize=14, fontweight="bold")
    #     ax.set_ylabel(ylabel)

    #     if percentage:
    #         ax.set_ylim(0, 100)

    #     ax.grid(axis="y", linestyle="--", alpha=0.4)

    #     for bar in bars:
    #         height = bar.get_height()
    #         if percentage:
    #             text = f"{height:.2f}%"
    #         else:
    #             text = f"{height:.2f} ms"

    #         ax.annotate(text,
    #                     xy=(bar.get_x() + bar.get_width() / 2, height),
    #                     xytext=(0, 4),
    #                     textcoords="offset points",
    #                     ha="center",
    #                     va="bottom"
    #                    )
    #     fig.tight_layout()
    #     filename = f"{metric}_total_comparison.png"
    #     output_path = os.path.join(OUTPUT_DIR, filename)
    #     fig.savefig(output_path, dpi=300, bbox_inches="tight")
    #     plt.show()
    #     plt.close(fig)
    #     print(f"\nGrafico salvato: {output_path}")
    
def plot_total_accuracy_precision(gemma_stats, qwen_stats):

    """
    Crea un grafico orizzontale per Accuracy e Precision.
    Usa direttamente media e CI prodotti dall'evaluator.
    """
    create_output_directory()
    metrics = ["Accuracy", "Precision"]

    gemma_accuracy = gemma_stats["accuracy"]["overall"]
    qwen_accuracy = qwen_stats["accuracy"]["overall"]

    gemma_precision = gemma_stats["precision"]
    qwen_precision = qwen_stats["precision"]

    gemma_values = [gemma_accuracy["mean"] * 100, gemma_precision["mean"] * 100]

    qwen_values = [qwen_accuracy["mean"] * 100, qwen_precision["mean"] * 100]

    gemma_errors = [gemma_accuracy["margin"] * 100, gemma_precision["margin"] * 100]

    qwen_errors = [qwen_accuracy["margin"] * 100, qwen_precision["margin"] * 100]

    y = np.arange(len(metrics))
    height = 0.35

    fig, ax = plt.subplots(figsize=(9, 5))

    bars_gemma = ax.barh(
        y - height / 2,
        gemma_values,
        height,
        xerr=gemma_errors,
        capsize=4,
        label="Gemma"
    )

    bars_qwen = ax.barh(
        y + height / 2,
        qwen_values,
        height,
        xerr=qwen_errors,
        capsize=4,
        label="Qwen"
    )

    ax.set_yticks(y)
    ax.set_yticklabels(metrics)

    ax.set_xlabel("Valore (%)")
    ax.set_xlim(0, 100)

    ax.set_title(
        "Accuracy e Precision - Gemma vs Qwen",
        fontsize=14,
        fontweight="bold"
    )

    ax.grid(axis="x", linestyle="--", alpha=0.4)
    ax.legend()
    for bar in bars_gemma:
        width = bar.get_width()
        ax.annotate(
            f"{width:.2f}%",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            ha="left",
            va="center"
        )

    for bar in bars_qwen:
        width = bar.get_width()
        ax.annotate(
            f"{width:.2f}%",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            ha="left",
            va="center"
        )

    fig.tight_layout()

    output_path = os.path.join(OUTPUT_DIR, "accuracy_precision_total_comparison.png")

    fig.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.show()
    plt.close(fig)

    print(f"\nGrafico salvato: {output_path}")

# ========================================== GRAFICO TOTALE LATENZA 
def plot_total_latency(gemma_stats, qwen_stats):
    """
    Crea un grafico orizzontale per la latenza
    con intervallo di confidenza al 97%.
    """

    create_output_directory()
    labels = ["Gemma", "Qwen"]
    gemma_latency = gemma_stats["latency"]
    qwen_latency = qwen_stats["latency"]
    values = [
        gemma_latency["mean"],
        qwen_latency["mean"]
    ]

    errors = [
        gemma_latency["margin"],
        qwen_latency["margin"]
    ]

    y = np.arange(len(labels))
    height = 0.5
    fig, ax = plt.subplots(figsize=(9, 4))
    bars = ax.barh(
        y,
        values,
        height,
        xerr=errors,
        capsize=4
    )

    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.set_xlabel("Latency (ms)")
    ax.set_title("Latency - Gemma vs Qwen", fontsize=14, fontweight="bold")
    ax.grid(axis="x", linestyle="--", alpha=0.4)

    for bar in bars:
        width = bar.get_width()
        ax.annotate(
            f"{width:.2f} ms",
            xy=(width, bar.get_y() + bar.get_height() / 2),
            xytext=(5, 0),
            textcoords="offset points",
            ha="left",
            va="center"
        )

    fig.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, "latency_total_comparison.png")
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

    plot_metric(gemma_stats, qwen_stats, metric="accuracy", title="Accuracy - Gemma vs Qwen", xlabel="Accuracy (%)", filename="accuracy_comparison.png", percentage=True) #Accuracy

    plot_metric(gemma_stats, qwen_stats, metric="precision", title="Precision - Gemma vs Qwen", xlabel="Precision (%)", filename="precision_comparison.png", percentage=True) #Precision

    plot_metric(gemma_stats, qwen_stats, metric="latency", title="Latency - Gemma vs Qwen", xlabel="Latency (ms)", filename="latency_comparison.png", percentage=False) #Latency

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
        gemma_stats = gemma_data["statistics"]["by_difficulty"]
        qwen_stats = qwen_data["statistics"]["by_difficulty"]
        print_statistics("Gemma", gemma_stats)
        print_statistics("Qwen", qwen_stats)
        print_comparison(gemma_stats, qwen_stats)
        create_plots(gemma_stats, qwen_stats)
    #confronto totale
    else:
        gemma_stats = gemma_data["statistics"]["overall"]
        qwen_stats = qwen_data["statistics"]["overall"]
        print_statistics("Gemma - Totale", {"Totale": gemma_stats})
        print_statistics("Qwen - Totale", {"Totale": qwen_stats})
        print_comparison({"Totale": gemma_stats}, {"Totale": qwen_stats})
        plot_total_accuracy_precision(gemma_stats, qwen_stats)
        plot_total_latency(gemma_stats,qwen_stats)
# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()  