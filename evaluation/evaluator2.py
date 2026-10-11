
import json
import sys
from pathlib import Path


def parse_json_if_string(value):
    """Interpreta una stringa JSON, lasciando invariati i valori non JSON."""
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def normalize_sql_value(value):
    """
    Converte ricorsivamente stringhe numeriche in numeri.
    Le altre stringhe, comprese le date, restano invariate.
    """
    if isinstance(value, dict):
        return {
            key: normalize_sql_value(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [normalize_sql_value(item) for item in value]

    if isinstance(value, str):
        # Converte soltanto stringhe che rappresentano numeri.
        try:
            number = float(value)
            if value.strip() and value.strip() == value:
                if number.is_integer() and not any(
                    char in value.lower() for char in (".", "e")
                ):
                    return int(number)
                return number
        except ValueError:
            pass

    return value


def extract_sql_answer(run):
    """Estrae le righe dell'ultima execute_sql riuscita."""
    for call in reversed(run.get("tool_calls", [])):
        if call.get("tool") not in ("execute_sql", "mysql_execute_sql"):
            continue

        output = parse_json_if_string(call.get("output"))

        if not isinstance(output, dict):
            output = parse_json_if_string(call.get("raw_output"))

        if not isinstance(output, dict):
            continue

        if output.get("success") is not True:
            continue

        rows = output.get("rows")
        if isinstance(rows, list):
            return normalize_sql_value(rows)

    return None


def normalize_tool_calls(run):
    """
    Porta i log delle chiamate al formato:
    tool_call_number, tool, arguments, output, raw_output, latency.
    """
    normalized = []

    for index, call in enumerate(run.get("tool_calls", []), start=1):
        raw_output = call.get("raw_output")

        if raw_output is None:
            original_output = call.get("output")
            if isinstance(original_output, str):
                raw_output = original_output
            else:
                raw_output = json.dumps(
                    original_output,
                    ensure_ascii=False,
                    indent=2
                )

        parsed_output = parse_json_if_string(call.get("output"))

        normalized.append({
            "tool_call_number": index,
            "tool": call.get("tool"),
            "arguments": call.get("arguments", {}),
            "output": parsed_output,
            "raw_output": raw_output,
            "latency": call.get("latency")
        })

    return normalized


def convert_file(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)

    with input_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    converted = {
        "num_runs": data.get("num_runs", 0),
        "results": []
    }

    total_runs = 0
    extracted_runs = 0
    missing_runs = 0

    for result in data.get("results", []):
        converted_result = {
            "id": result.get("id"),
            "question": result.get("question"),
            "ground_truth": result.get("ground_truth"),
            "runs": []
        }

        for run in result.get("runs", []):
            total_runs += 1

            answer = extract_sql_answer(run)

            if answer is None:
                missing_runs += 1
            else:
                extracted_runs += 1

            converted_run = {
                "run": run.get("run"),
                "answer": answer,
                "agent_completion": run.get("agent_completion", False),
                "latency_total": run.get("latency_total"),
                "tool_calls_count": run.get(
                    "tool_calls_count",
                    len(run.get("tool_calls", []))
                ),
                "tool_calls": normalize_tool_calls(run)
            }

            if answer is None:
                converted_run["answer_extraction_error"] = (
                    "No successful SQL query result found"
                )

            converted_result["runs"].append(converted_run)

        converted["results"].append(converted_result)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(converted, file, ensure_ascii=False, indent=4)

    print(f"File creato: {output_path}")
    print(f"Run totali: {total_runs}")
    print(f"Risposte estratte: {extracted_runs}")
    print(f"Risposte non recuperate: {missing_runs}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(
            "Uso: python convert_results.py "
            "risultati_originali.json risultati_convertiti.json"
        )
        sys.exit(1)

    convert_file(sys.argv[1], sys.argv[2])
