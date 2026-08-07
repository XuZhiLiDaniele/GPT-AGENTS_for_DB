from openai import OpenAI
client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")
system_prompt = "You are a helpful assistant."
user_input = "Ciao, quanto fa 2+2?" 
completion = client.chat.completions.create(
  model="local-model", # this field is currently unused
  messages=[
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_input}
  ],
  temperature=0.7,
)

print(completion.choices[0].message.content)