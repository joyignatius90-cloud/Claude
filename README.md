# Claude

A small command-line chatbot that talks to Claude through the Anthropic API.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # or run `ant auth login`
```

## Run

```bash
python chat.py
```

Commands inside the chat: `/reset` clears the conversation, `/exit` quits.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `CLAUDE_MODEL` | `claude-opus-5-5` | Model to chat with |
| `CLAUDE_EFFORT` | `medium` | How hard Claude thinks: `low`, `medium`, `high`, `xhigh`, `max` |
| `CLAUDE_SYSTEM_PROMPT` | friendly assistant | Personality and instructions for Claude |

If Claude declines a request for policy reasons, the API automatically retries it on a
fallback model (`fallbacks="default"`).

---

# WhatsApp bot

`whatsapp_bot.py` connects Claude to WhatsApp: people message your WhatsApp
Business number and Claude replies. It uses Meta's official
[WhatsApp Cloud API](https://developers.facebook.com/docs/whatsapp/cloud-api).

## 1. Set up WhatsApp on Meta

1. Go to <https://developers.facebook.com/apps>, create an app, choose **Business**,
   and add the **WhatsApp** product.
2. Under **WhatsApp → API Setup**, note the **Phone number ID** and copy the
   **access token**. The test token expires after 24 hours; for a lasting one,
   create a System User token in Meta Business Settings with the
   `whatsapp_business_messaging` permission.
3. While testing, add your own phone number under **To** so the test number can message it.
4. Under **App settings → Basic**, copy the **App secret**.

## 2. Run the bot

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
export WHATSAPP_TOKEN=...              # access token from step 2
export WHATSAPP_PHONE_NUMBER_ID=...    # phone number ID from step 2
export WHATSAPP_APP_SECRET=...         # app secret from step 4
export WHATSAPP_VERIFY_TOKEN=pick-any-secret-word
python whatsapp_bot.py                 # listens on port 8000
```

Meta has to reach the bot over public HTTPS. On your own computer, use a tunnel such as
`ngrok http 8000`, which gives you a URL like `https://abc123.ngrok-free.app`.
For something that runs all the time, deploy it to a host such as Render, Railway or Fly.io.

## 3. Connect the webhook

1. In your Meta app, open **WhatsApp → Configuration → Webhook → Edit**.
2. **Callback URL:** `https://<your-public-url>/webhook`
3. **Verify token:** the same word you used for `WHATSAPP_VERIFY_TOKEN`.
4. Click **Verify and save**, then **subscribe** to the `messages` field.

Send a WhatsApp message to the bot's number and Claude should reply.
Send `/reset` to start a new conversation.

## Bot settings

| Variable | Default | Meaning |
|---|---|---|
| `CLAUDE_EFFORT` | `low` | Thinking depth; raise it for harder questions |
| `MAX_TURNS` | `40` | Replies before a conversation automatically starts fresh |
| `GRAPH_API_VERSION` | `v21.0` | Meta Graph API version |
| `PORT` | `8000` | Port the server listens on |

`CLAUDE_MODEL` and `CLAUDE_SYSTEM_PROMPT` work the same as for the command-line chat.

**Limitations:** the bot reads text messages only. Conversations are kept in memory,
so they're lost when the server restarts. Run the bot as a single process: with several
workers, each one keeps separate memory.
