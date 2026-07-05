import argparse
import logging
import os

from agent_lib.loop import run_agent


def main():
    parser = argparse.ArgumentParser(description="Local, tool-calling AI agent backed by Ollama.")
    parser.add_argument("task", nargs="?", help="Task to run. If omitted, you'll be prompted.")
    parser.add_argument("--model", default=os.environ.get("AGENT_MODEL", "hermes3"),
                        help="Ollama model tag to use (default: hermes3, or $AGENT_MODEL).")
    parser.add_argument("--base-url", default=os.environ.get("AGENT_BASE_URL", "http://localhost:11434"),
                        help="Base URL of the Ollama server (default: http://localhost:11434).")
    parser.add_argument("--state-file", default="agent_state.json",
                        help="Path to the conversation state file (default: agent_state.json).")
    parser.add_argument("--reset", action="store_true",
                        help="Discard any existing state file before running.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(message)s",
    )

    if args.reset and os.path.exists(args.state_file):
        os.remove(args.state_file)

    task = args.task or input("Enter your task: ")

    try:
        result = run_agent(
            task,
            state_file=args.state_file,
            model=args.model,
            base_url=args.base_url,
        )
    except (ConnectionError, RuntimeError) as e:
        print(f"Error: {e}")
        raise SystemExit(1)

    print("\nAgent:")
    print(result)


if __name__ == "__main__":
    main()
