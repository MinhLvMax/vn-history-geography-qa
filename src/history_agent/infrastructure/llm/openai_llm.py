from openai import OpenAI
client = OpenAI()

response = client.responses.create(
  model="gpt-5.5",
  input=[],
  text={
    "format": {
      "type": "text"
    },
    "verbosity": "medium"
  },
  reasoning={
    "effort": "medium",
    "mode": "standard",
    "summary": "auto"
  },
  tools=[],
  store=True,
  include=[
    "reasoning.encrypted_content",
    "web_search_call.action.sources"
  ]
)

print(response.output_text)