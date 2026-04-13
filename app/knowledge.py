import json
import os

def load_context() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, "data", "venue_info.json")

    with open(data_path, "r") as f:
        data = json.load(f)

    venue = data["venue"]
    lines = [
        f"You are a helpful assistant for {venue['name']}.",
        f"Address: {venue['address']}",
        f"Phone: {venue['phone']}",
        f"Website: {venue['website']}",
        "",
        "Upcoming events:",
    ]

    for event in data.get("upcoming_events", []):
        lines.append(
            f"- {event['title']} on {event['date']} at {event['time']}. "
            f"Tickets: {event['tickets']}"
        )

    lines.append("")
    lines.append("FAQ:")
    for item in data.get("faq", []):
        lines.append(f"Q: {item['q']}")
        lines.append(f"A: {item['a']}")

    return "\n".join(lines)