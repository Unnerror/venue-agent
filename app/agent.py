import os
from openai import OpenAI
from app.knowledge import load_context

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

def ask_agent(question: str) -> str:
    system_prompt = load_context()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_tokens=500,
        temperature=0.3,
    )

    return response.choices[0].message.content