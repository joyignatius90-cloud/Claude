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
