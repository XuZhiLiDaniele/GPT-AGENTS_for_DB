import copy

def normalize_agent_result(agent_result):
    """
    Normalizza il risultato dell'agente MongoDB
    nel formato standard del benchmark.
    """

    tool_calls = agent_result.get("tool_calls", [])
    final_answer = agent_result.get("answer")

    # DATABASE UTILIZZATI
    databases = []

    for tool_call in tool_calls:
        database = (tool_call.get("arguments",{}).get("database"))
        if database and database not in databases:
            databases.append(database)

    # RISULTATO INVALIDO
    if not isinstance(final_answer, dict):
        return {
            "database": databases,
            "answer": []
        }

    # DOCUMENTI DEL TOOL FINALE
    documents = final_answer.get("documents", [])

    # RISULTATO
    return {
        "database": databases,
        "answer": copy.deepcopy(documents)
    }