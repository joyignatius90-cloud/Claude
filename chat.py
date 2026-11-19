"""A small command-line chatbot built on the Claude API.

Run:  python chat.py
Type /reset to start over, /exit (or Ctrl-D) to quit.
"""

import os
import sys

import anthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("CLAUDE_EFFORT", "medium")  # low | medium | high | xhigh | max
SYSTEM_PROMPT = os.environ.get(
    "CLAUDE_SYSTEM_PROMPT",
    "You are a friendly, helpful assistant. Answer clearly and concisely.",
)


def ask(client: anthropic.Anthropic, history: list) -> None:
    """Stream Claude's reply to the terminal and append it to the history."""
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=64000,
        system=SYSTEM_PROMPT,
        output_config={"effort": EFFORT},
        # If Claude declines for policy reasons, let the API retry on a fallback model.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=history,
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
        response = stream.get_final_message()
    print()

    if response.stop_reason == "refusal":
        print("[Claude declined to answer this one.]")
    elif response.stop_reason == "max_tokens":
        print("[Reply was cut off at the token limit.]")

    # Keep the full content (including thinking blocks) so the conversation stays valid.
    history.append({"role": "assistant", "content": response.content})


def main() -> None:
    client = anthropic.Anthropic()
    history: list = []
    print(f"Chatting with {MODEL}. Type /reset to start over, /exit to quit.\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input in ("/exit", "/quit"):
            break
        if user_input == "/reset":
            history.clear()
            print("[Conversation cleared.]\n")
            continue

        history.append({"role": "user", "content": user_input})
        print("Claude: ", end="", flush=True)
        try:
            ask(client, history)
        except anthropic.AuthenticationError:
            print("\n[No valid credentials. Set ANTHROPIC_API_KEY or run `ant auth login`.]")
            sys.exit(1)
        except anthropic.RateLimitError:
            print("\n[Rate limited. Wait a moment and try again.]")
            history.pop()
        except anthropic.APIStatusError as e:
            print(f"\n[API error {e.status_code}: {e.message}]")
            history.pop()
        except anthropic.APIConnectionError:
            print("\n[Could not reach the API. Check your network.]")
            history.pop()
        print()


if __name__ == "__main__":
    main()
