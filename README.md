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

---

# Daily availability message

`daily_availability.py` sends your availability to your clients on WhatsApp every day:

> Hi Acme, here is my availability for Thursday, 19 November: 9:00 AM - 12:00 PM,
> 2:00 PM - 5:00 PM. Reply to this message to book a time.

## 1. Set your schedule

Edit `availability.json`:
- `timezone`: your time zone, e.g. `Asia/Kolkata`, `Europe/London`, `America/New_York`.
- `send_time`: when to send each day, in that time zone. Set to `"10:00"` (10 AM).
- `weekly`: your usual hours for each day, written like `"09:00-12:00"`. Use `[]` for days off.
- `exceptions`: specific dates that differ from the usual week, e.g. `"2026-12-25": []` for a holiday.
- `send_for`: `"today"` (send in the morning) or `"tomorrow"` (send the evening before).

Run `python daily_availability.py --preview` to see exactly what will be sent.

## 2. Get the message template approved (one time)

WhatsApp only lets a business start a conversation with a template that Meta has approved.
In **Meta Business Manager → WhatsApp Manager → Message templates → Create template**:

- **Category:** Utility
- **Name:** `daily_availability`
- **Language:** English (`en`)
- **Body:**
  `Hi {{1}}, here is my availability for {{2}}: {{3}}. Reply to this message to book a time.`
- Sample values: `Acme`, `Thursday, 19 November`, `9:00 AM - 12:00 PM, 2:00 PM - 5:00 PM`

If you use a different name or language, change `template_name` / `template_language` in `availability.json`.

## 3. Send it every day automatically (free, using GitHub)

The workflow in `.github/workflows/daily-availability.yml` runs the sender once a day.

1. In the GitHub repo, open **Settings → Secrets and variables → Actions → New repository secret**
   and add:
   - `WHATSAPP_TOKEN`: a permanent System User access token (the 24-hour test token will stop working)
   - `WHATSAPP_PHONE_NUMBER_ID`: your WhatsApp phone number ID
   - `CLIENTS`: client names and numbers with country code, e.g. `Acme:919876543210;Bob:447700900000`
   - `GROUPS` (optional): group names and IDs, e.g. `Team:120363000000000000` (see *Sending to groups*)
2. The workflow runs every hour, and the script only sends during the hour that starts at
   `send_time` in your `timezone`, so you never have to work out UTC.
3. Merge the branch into your default branch. GitHub only runs scheduled workflows from there.
4. To test, open **Actions → Send daily availability on WhatsApp → Run workflow**.

Keeping client numbers in the `CLIENTS` secret keeps them out of the repository.

## Sending to WhatsApp groups

WhatsApp's official API **cannot post into groups you created in the WhatsApp app**.
It can only post to groups that your business number created through Meta's Groups API, and:
- your number must be an **Official Business Account** (the verified badge). Meta must approve this first.
- each group can have at most **8 participants**, who join through an invite link.

Once you have such a group, put its group ID in `groups` in `availability.json` or in the
`GROUPS` secret, and the same daily message is sent to it.

**If you can't get an Official Business Account:** send the message to each client one-to-one
through `CLIENTS` instead. Each client still gets it every day at 10 AM.

**Other ways to run it:** `python daily_availability.py --send` sends once, right now.
`python daily_availability.py --daemon` keeps running and sends every day at `send_time` in your time zone.
