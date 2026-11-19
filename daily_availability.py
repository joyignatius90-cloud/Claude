"""Send your availability to clients on WhatsApp once a day.

Your schedule lives in availability.json: a normal weekly schedule, plus
"exceptions" for specific dates (an empty list means you're not available).

Usage:
  python daily_availability.py --preview      show the message, send nothing
  python daily_availability.py --send         send it now
  python daily_availability.py --daemon 08:00 keep running, send every day at 08:00
"""

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

CONFIG_PATH = Path(os.environ.get("AVAILABILITY_FILE", Path(__file__).with_name("availability.json")))
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")


def load_config() -> dict:
    config = json.loads(CONFIG_PATH.read_text())
    # Keep client numbers out of the repo: CLIENTS="Name:919876543210;Other:447700900000"
    if os.environ.get("CLIENTS"):
        config["clients"] = [
            {"name": name.strip(), "phone": phone.strip()}
            for name, phone in (item.split(":", 1) for item in os.environ["CLIENTS"].split(";") if ":" in item)
        ]
    return config


def target_day(config: dict) -> date:
    today = datetime.now(ZoneInfo(config.get("timezone", "UTC"))).date()
    return today + timedelta(days=1) if config.get("send_for") == "tomorrow" else today


def slots_for(config: dict, day: date) -> list[str]:
    exceptions = config.get("exceptions", {})
    if day.isoformat() in exceptions:
        return exceptions[day.isoformat()]
    return config.get("weekly", {}).get(day.strftime("%A").lower(), [])


def format_slot(slot: str) -> str:
    """'14:00-17:00' -> '2:00 PM - 5:00 PM'"""
    def fmt(t: str) -> str:
        return datetime.strptime(t.strip(), "%H:%M").strftime("%I:%M %p").lstrip("0")
    start, end = slot.split("-")
    return f"{fmt(start)} - {fmt(end)}"


def build_parts(config: dict, client_name: str) -> tuple[str, str, str]:
    day = target_day(config)
    slots = slots_for(config, day)
    # Template values can't contain line breaks, so slots go on one line.
    slots_text = ", ".join(format_slot(s) for s in slots) if slots else "not available"
    return client_name, day.strftime("%A, %d %B"), slots_text


def preview_text(config: dict, client_name: str) -> str:
    name, day, slots = build_parts(config, client_name)
    return f"Hi {name}, here is my availability for {day}: {slots}. Reply to this message to book a time."


def send_template(config: dict, phone: str, params: tuple[str, str, str]) -> None:
    token = os.environ["WHATSAPP_TOKEN"]
    phone_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    payload = {
        "messaging_product": "whatsapp",
        "to": phone,
        "type": "template",
        "template": {
            "name": config.get("template_name", "daily_availability"),
            "language": {"code": config.get("template_language", "en")},
            "components": [{
                "type": "body",
                "parameters": [{"type": "text", "text": p} for p in params],
            }],
        },
    }
    r = requests.post(
        f"https://graph.facebook.com/{GRAPH_API_VERSION}/{phone_id}/messages",
        json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=30,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"WhatsApp refused the message ({r.status_code}): {r.text}")


def send_all(config: dict) -> int:
    failures = 0
    for client in config.get("clients", []):
        phone = client["phone"].lstrip("+").replace(" ", "")
        if not phone.isdigit():
            print(f"Skipping {client['name']}: phone number not set ({client['phone']!r})")
            failures += 1
            continue
        try:
            send_template(config, phone, build_parts(config, client["name"]))
            print(f"Sent to {client['name']}")
        except Exception as e:  # keep going for the other clients
            print(f"Failed for {client['name']}: {e}")
            failures += 1
    return failures


def run_daemon(config: dict, send_at: str) -> None:
    tz = ZoneInfo(config.get("timezone", "UTC"))
    hour, minute = map(int, send_at.split(":"))
    while True:
        now = datetime.now(tz)
        next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        print(f"Next send: {next_run:%Y-%m-%d %H:%M %Z}")
        time.sleep((next_run - now).total_seconds())
        send_all(load_config())  # re-read so schedule edits take effect


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--preview", action="store_true")
    group.add_argument("--send", action="store_true")
    group.add_argument("--daemon", metavar="HH:MM")
    args = parser.parse_args()

    config = load_config()
    if args.preview:
        for client in config.get("clients", []):
            print(f"To {client['name']} ({client['phone']}):\n  {preview_text(config, client['name'])}\n")
    elif args.send:
        sys.exit(1 if send_all(config) else 0)
    else:
        run_daemon(config, args.daemon)


if __name__ == "__main__":
    main()
