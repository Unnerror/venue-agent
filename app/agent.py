import os
import logging
from datetime import datetime, timezone
from openai import OpenAI
from app.embedder import query_collection

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

STATIC_CONTEXT = """
You are a helpful assistant for Théâtre Rialto, a historic venue in Montreal.
Address: 5723 Avenue du Parc, Montréal, QC, H2V 4H2
Phone: (514) 268-7069
Website: https://www.theatrerialto.ca

FAQ:
Q: Is there parking nearby?
A: Street parking is available on Park Ave. Paid lot at 5700 Park Ave, 2 min walk.

Q: What time do doors open?
A: Doors typically open 30 minutes before showtime.

Q: Is the venue accessible?
A: Yes, wheelchair accessible entrance on the south side of the building.
""".strip()


def ask_agent(question: str) -> str:
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")

    relevant_docs = query_collection(question, n_results=3)

    if relevant_docs:
        rag_context = "\n\n".join(relevant_docs)
        system_prompt = (
            f"Today's date is {today}.\n\n"
            f"{STATIC_CONTEXT}\n\n"
            f"Upcoming events (retrieved from knowledge base):\n{rag_context}"
        )
    else:
        system_prompt = (
            f"Today's date is {today}.\n\n"
            f"{STATIC_CONTEXT}\n\n"
            "Note: Event schedule is currently unavailable. "
            "Please check https://www.theatrerialto.ca/calendar for upcoming shows."
        )

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