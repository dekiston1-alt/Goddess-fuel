import json
import os


def save_state(filepath: str, history) -> None:
    """Saves the conversation history to disk."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)


def load_state(filepath: str):
    """Loads the conversation history from disk if it exists."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def prune_context(history, max_turns: int = 16):
    """
    Keeps the system prompt and recent turns.
    Strips orphaned tool responses from the top of the slice so a cut
    that lands mid-tool-call doesn't produce an invalid message sequence.
    """
    if len(history) <= max_turns + 1:
        return history

    system_prompt = history[0]
    recent = history[-max_turns:]

    while recent and recent[0]["role"] == "tool":
        recent.pop(0)

    return [system_prompt] + recent
