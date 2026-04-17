import re
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://www.theatrerialto.ca/calendar"


@dataclass
class Event:
    title: str
    date: str          # ISO format: YYYY-MM-DD
    time: str          # e.g. "6:00 PM"
    url: str
    tickets: Optional[str] = None


def scrape_calendar() -> list[Event]:
    """
    Fetch and parse upcoming events from theatrerialto.ca/calendar.
    Returns a list of Event dataclasses.
    """
    try:
        response = httpx.get(CALENDAR_URL, timeout=15, follow_redirects=True)
        response.raise_for_status()
    except httpx.HTTPError as e:
        logger.error(f"Failed to fetch calendar: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    events: list[Event] = []

    # Each event block is an <article> or a section with a heading + date block
    # Structure observed: h1/h2 with event title, date block with "Apr 17 6:00 PM"
    # and a "TICKETS: <url>" paragraph

    # Find all event entries — each has an <a> linking to /calendar/YYYY/...
    event_links = soup.find_all("a", href=re.compile(r"/calendar/\d{4}/"))

    seen_urls = set()
    for link in event_links:
        url = "https://www.theatrerialto.ca" + link["href"] if link["href"].startswith("/") else link["href"]

        # Skip duplicates (same event linked multiple times — image + text)
        if url in seen_urls:
            continue
        seen_urls.add(url)

        # Title: find the nearest h1/h2/h3 inside or near the link
        title_tag = link.find(["h1", "h2", "h3"])
        if not title_tag:
            # Try the parent container
            parent = link.find_parent(["article", "div", "li"])
            if parent:
                title_tag = parent.find(["h1", "h2", "h3"])

        title = title_tag.get_text(strip=True) if title_tag else link.get_text(strip=True)
        if not title:
            continue

        # Date and time: look for text patterns like "Friday, April 17, 2026" and "6:00 PM"
        parent_block = link.find_parent(["article", "div", "li", "section"])
        date_str = ""
        time_str = ""
        tickets_url = None

        if parent_block:
            text = parent_block.get_text(" ", strip=True)

            # Extract date: "Friday, April 17, 2026" or "April 17, 2026"
            date_match = re.search(
                r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+"
                r"(\w+ \d{1,2},\s*\d{4})",
                text
            )
            if date_match:
                try:
                    parsed = datetime.strptime(date_match.group(1).strip(), "%B %d, %Y")
                    date_str = parsed.strftime("%Y-%m-%d")
                except ValueError:
                    date_str = date_match.group(1).strip()

            # Extract time: "6:00 PM" / "18:00"
            time_match = re.search(r"\b(\d{1,2}:\d{2}\s*(?:AM|PM))\b", text)
            if time_match:
                time_str = time_match.group(1)

            # Extract tickets URL
            tickets_match = re.search(r"TICKETS:\s*(https?://\S+)", text)
            if tickets_match:
                tickets_url = tickets_match.group(1)

        if title and date_str:
            events.append(Event(
                title=title,
                date=date_str,
                time=time_str,
                url=url,
                tickets=tickets_url,
            ))

    logger.info(f"Scraped {len(events)} events from {CALENDAR_URL}")
    return events


def events_to_documents(events: list[Event]) -> list[dict]:
    """
    Convert Event objects to ChromaDB-ready documents.
    Each document is a dict with 'text' (for embedding) and 'metadata'.
    """
    docs = []
    for event in events:
        text = f"Event: {event.title}\nDate: {event.date}\nTime: {event.time}"
        if event.tickets:
            text += f"\nTickets: {event.tickets}"
        text += f"\nMore info: {event.url}"

        docs.append({
            "id": event.url,  # stable unique ID
            "text": text,
            "metadata": {
                "title": event.title,
                "date": event.date,
                "time": event.time,
                "url": event.url,
                "tickets": event.tickets or "",
            }
        })

    return docs