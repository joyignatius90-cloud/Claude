"""WhatsApp bot that answers messages with Claude.

Uses Meta's official WhatsApp Cloud API. Meta calls /webhook for every incoming
message; the bot asks Claude for a reply and sends it back to the sender.

Run:  python whatsapp_bot.py   (see README.md for the Meta setup steps)
"""

import hashlib
import hmac
import logging
import os
import threading
from collections import OrderedDict, defaultdict

import anthropic
import requests
from flask import Flask, abort, request

# --- Configuration --------------------------------------------------------
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")            # Meta access token
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN", "")  # any secret string you choose
WHATSAPP_APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET", "")  # Meta app secret, for signature checks
GRAPH_API_VERSION = os.environ.get("GRAPH_API_VERSION", "v21.0")
PORT = int(os.environ.get("PORT", "8000"))

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "low")  # chat replies rarely need deep thinking
SYSTEM_PROMPT = os.environ.get(
    "CLAUDE_SYSTEM_PROMPT",
    "You are a friendly, helpful assistant chatting over WhatsApp. "
    "Keep replies short and conversational, and use plain text: WhatsApp "
    "only supports *bold*, _italic_ and ~strikethrough~, not Markdown headings or tables.",
)
MAX_TURNS = int(os.environ.get("MAX_TURNS", "40"))  # start a fresh conversation after this many replies
WHATSAPP_TEXT_LIMIT = 4096

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("whatsapp_bot")

app = Flask(__name__)
claude = anthropic.Anthropic()

# Conversation memory, kept in RAM per WhatsApp number (lost on restart).
histories: dict[str, list] = defaultdict(list)
user_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
seen_message_ids: "OrderedDict[str, None]" = OrderedDict()
seen_lock = threading.Lock()


# --- Claude -----------------------------------------------------------------
def ask_claude(history: list) -> str:
    response = claude.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT,
        output_config={"effort": EFFORT},
        # If Claude declines for policy reasons, the API retries on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=history,
    )
    # Keep the full content (thinking blocks included) so the conversation stays valid.
    history.append({"role": "assistant", "content": response.content})

    if response.stop_reason == "refusal":
        return "Sorry, I can't help with that one."
    text = "".join(block.text for block in response.content if block.type == "text").strip()
    if response.stop_reason == "max_tokens":
        text += "\n\n(reply cut off)"
    return text or "(no reply)"


# --- WhatsApp ---------------------------------------------------------------
def send_whatsapp_text(to: str, text: str) -> None:
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {WHATSAPP_TOKEN}"}
    for start in range(0, len(text), WHATSAPP_TEXT_LIMIT):
        chunk = text[start:start + WHATSAPP_TEXT_LIMIT]
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "text",
            "text": {"body": chunk},
        }
        r = requests.post(url, json=payload, headers=headers, timeout=30)
        if r.status_code >= 400:
            log.error("WhatsApp send failed (%s): %s", r.status_code, r.text)
            return


def handle_message(sender: str, text: str) -> None:
    with user_locks[sender]:  # one reply at a time per person, in order
        history = histories[sender]
        command = text.strip().lower()
        if command in ("/reset", "reset"):
            history.clear()
            send_whatsapp_text(sender, "Conversation cleared. What's on your mind?")
            return

        # Start fresh rather than trimming old turns, so history only ever grows.
        if len(history) >= MAX_TURNS * 2:
            history.clear()

        history.append({"role": "user", "content": text})
        try:
            reply = ask_claude(history)
        except anthropic.RateLimitError:
            history.pop()
            reply = "I'm a bit busy right now. Please try again in a minute."
        except (anthropic.APIStatusError, anthropic.APIConnectionError) as e:
            history.pop()
            log.exception("Claude API error: %s", e)
            reply = "Sorry, something went wrong on my side. Please try again."
        send_whatsapp_text(sender, reply)


def already_seen(message_id: str) -> bool:
    """Meta can deliver the same webhook more than once; reply only once."""
    with seen_lock:
        if message_id in seen_message_ids:
            return True
        seen_message_ids[message_id] = None
        if len(seen_message_ids) > 5000:
            seen_message_ids.popitem(last=False)
        return False


def signature_is_valid(raw_body: bytes, header: str) -> bool:
    if not WHATSAPP_APP_SECRET:
        return True  # signature checks disabled (not recommended outside local testing)
    expected = "sha256=" + hmac.new(WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


# --- Webhook routes -----------------------------------------------------------
@app.get("/webhook")
def verify_webhook():
    """Meta calls this once when you register the webhook URL."""
    if (
        request.args.get("hub.mode") == "subscribe"
        and WHATSAPP_VERIFY_TOKEN
        and request.args.get("hub.verify_token") == WHATSAPP_VERIFY_TOKEN
    ):
        return request.args.get("hub.challenge", ""), 200
    abort(403)


@app.post("/webhook")
def receive_webhook():
    if not signature_is_valid(request.get_data(), request.headers.get("X-Hub-Signature-256", "")):
        abort(403)

    data = request.get_json(silent=True) or {}
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                if already_seen(msg.get("id", "")):
                    continue
                sender = msg.get("from")
                if msg.get("type") == "text":
                    text = msg["text"]["body"]
                    # Reply in the background so Meta gets its 200 straight away.
                    threading.Thread(target=handle_message, args=(sender, text), daemon=True).start()
                elif sender:
                    threading.Thread(
                        target=send_whatsapp_text,
                        args=(sender, "For now I can only read text messages."),
                        daemon=True,
                    ).start()
    return "ok", 200


@app.get("/")
def health():
    return "WhatsApp Claude bot is running.", 200


if __name__ == "__main__":
    missing = [name for name in ("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN")
               if not os.environ.get(name)]
    if missing:
        log.warning("Missing settings: %s (see README.md)", ", ".join(missing))
    if not WHATSAPP_APP_SECRET:
        log.warning("WHATSAPP_APP_SECRET is not set: incoming webhooks are not verified.")
    app.run(host="0.0.0.0", port=PORT)
