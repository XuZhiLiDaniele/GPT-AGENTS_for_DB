#
# Script per testare il modello locale Gemma 4, collegato con LLMStudio, con cui interagiamo tramite prompt su terminale.
# Il modello mantiene memoria della sola conversazione corrente.
#

from openai import OpenAI

# Point to the local server
client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

messages = [
    {"role": "system", 
    "content": "You are a helpful assistant."
    }
]

print("Insert exit or quit to end chat.")

while True:
    user_input = input("\nYou:")

    if user_input.lower() in ["exit", "quit"]:
        print("Goodbye!")
        break
    
    messages.append(
        {"role": "user", 
         "content": user_input}
    )

    completion = client.chat.completions.create(
      model="local-model", # this field is currently unused
      messages = messages, 
      temperature=0.7,
    )
    response = completion.choices[0].message.content
    print(" \nAssistant:", response)

    messages.append(
        {"role": "assistant", 
         "content": response}
    )

