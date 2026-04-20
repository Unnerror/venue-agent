import os
import logging
import re
from datetime import datetime, timezone, timedelta
from openai import OpenAI
from app.embedder import query_collection, query_by_date_range

logger = logging.getLogger(__name__)

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

STATIC_CONTEXT = """
You are a helpful concierge assistant for Théâtre Rialto, a historic venue in Montreal.
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


def _get_date_range(question: str, today: datetime):
    """
    Parse question to determine date range for metadata filtering.
    Returns (date_from, date_to) as ISO strings, or None if not a date query.
    """
    q = question.lower()

    # "this weekend" → upcoming Saturday + Sunday
    if "this weekend" in q or "upcoming weekend" in q or "weekend" in q:
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        saturday = today + timedelta(days=days_until_saturday)
        sunday = saturday + timedelta(days=1)
        return saturday.strftime("%Y-%m-%d"), sunday.strftime("%Y-%m-%d")

    # "this week" / "next week"
    if "this week" in q:
        end = today + timedelta(days=7)
        return today.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    if "next week" in q:
        start = today + timedelta(days=7)
        end = today + timedelta(days=14)
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # "today" / "tonight"
    if "today" in q or "tonight" in q:
        d = today.strftime("%Y-%m-%d")
        return d, d

    # "tomorrow"
    if "tomorrow" in q:
        d = (today + timedelta(days=1)).strftime("%Y-%m-%d")
        return d, d

    # "upcoming" / "soon" → next 30 days
    if "upcoming" in q or "soon" in q or "schedule" in q or "calendar" in q or "what's on" in q or "whats on" in q:
        end = today + timedelta(days=30)
        return today.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

    # Specific month name e.g. "april", "may 2026"
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4,
        "may": 5, "june": 6, "july": 7, "august": 8,
        "september": 9, "october": 10, "november": 11, "december": 12
    }
    for month_name, month_num in months.items():
        if month_name in q:
            year = today.year
            year_match = re.search(r"\b(202\d)\b", q)
            if year_match:
                year = int(year_match.group(1))
            import calendar
            last_day = calendar.monthrange(year, month_num)[1]
            return f"{year}-{month_num:02d}-01", f"{year}-{month_num:02d}-{last_day}"

    # Specific date e.g. "april 25", "25th"
    date_match = re.search(
        r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})",
        q
    )
    if date_match:
        month_name = date_match.group(1)
        day = int(date_match.group(2))
        month_num = months[month_name]
        year = today.year
        year_match = re.search(r"\b(202\d)\b", q)
        if year_match:
            year = int(year_match.group(1))
        d = f"{year}-{month_num:02d}-{day:02d}"
        return d, d

    return None


def ask_agent(question: str) -> str:
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%A, %B %d, %Y")

    date_range = _get_date_range(question, today)

    if date_range:
        # Metadata filter — precise date-based retrieval
        date_from, date_to = date_range
        docs = query_by_date_range(date_from, date_to)
        retrieval_note = f"(events from {date_from} to {date_to})"
        logger.info(f"Date range retrieval {retrieval_note}: {len(docs)} docs")
    else:
        # Semantic RAG — for specific questions
        docs = query_collection(question, n_results=5)
        retrieval_note = "(semantic search)"

    if docs:
        rag_context = "\n\n---\n\n".join(docs)
        system_prompt = (
            f"Today is {today_str}.\n\n"
            f"{STATIC_CONTEXT}\n\n"
            f"Relevant events {retrieval_note}:\n{rag_context}"
        )
    else:
        system_prompt = (
            f"Today is {today_str}.\n\n"
            f"{STATIC_CONTEXT}\n\n"
            "No events found for this period. "
            "Please check https://www.theatrerialto.ca/calendar for the full schedule."
        )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ],
        max_tokens=600,
        temperature=0.3,
    )

    return response.choices[0].message.content