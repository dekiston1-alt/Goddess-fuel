# Local AI Agent

A local, tool-calling agent loop built on top of [Ollama](https://ollama.com)'s
OpenAI-compatible chat completions API. The agent can read/write files, append
to logs, list directories, search file contents, fetch URLs, and run shell
commands on the host it's running on. It persists conversation history to disk
so a session can be resumed later, and retries transient connection failures
to the Ollama server.

## Requirements

- [Ollama](https://ollama.com) installed and running locally (`ollama serve`)
- A pulled model that supports tool calling, e.g. `ollama pull hermes3`
- Python 3.9+

## Setup

```bash
cd local-ai-agent
pip install -r requirements.txt
```

## Usage

```bash
python agent.py "your task here"
```

Or omit the task to be prompted interactively:

```bash
python agent.py
```

### CLI flags

| Flag | Description |
|---|---|
| `--model` | Ollama model tag to use (default: `hermes3`, or `$AGENT_MODEL`) |
| `--base-url` | Ollama server URL (default: `http://localhost:11434`, or `$AGENT_BASE_URL`) |
| `--state-file` | Path to the conversation state file (default: `agent_state.json`) |
| `--reset` | Discard any existing state file before running |
| `-v`, `--verbose` | Enable debug logging |

Conversation state is saved to the state file after each turn, so re-running
`agent.py` continues from where it left off. Use `--reset` (or delete the
state file) to start a fresh session.

## Project layout

```
local-ai-agent/
  agent.py            CLI entrypoint (argument parsing, logging setup)
  agent_lib/
    client.py          Ollama API client with retry/backoff
    loop.py            Agent loop: prompts model, dispatches tool calls
    state.py           History persistence and context pruning
    tools.py           Tool implementations and their JSON schemas
```

## Tools

| Tool | Description |
|---|---|
| `execute_shell` | Runs a shell command, returns stdout/stderr/exit code. Blocks obviously destructive commands (see below). |
| `file_write` | Overwrites a file with given content, creating parent directories as needed |
| `file_read` | Returns a file's contents |
| `append_log` | Appends a line to a file without overwriting it |
| `list_directory` | Lists the contents of a directory |
| `search_text` | Recursively greps files under a directory for a regex pattern |
| `http_get` | Fetches a URL and returns its status and body (truncated) |

## Safety

This agent gives the model direct shell access on whatever machine runs it
(`subprocess.run(..., shell=True)`). Only run it in an environment you're
comfortable letting the model act in directly, and don't point it at
credentials or systems you don't want it modifying.

As a baseline guard, `execute_shell` refuses commands matching a small set of
destructive patterns (`rm -rf`, `dd if=`, `mkfs.*`, `shutdown`, `reboot`, fork
bombs, writes to raw block devices). Set `AGENT_ALLOW_DANGEROUS=1` in the
environment to disable this check if you explicitly need one of those
commands — understand that doing so removes the only safety net this tool has.

The agent loop also caps itself at a configurable number of tool-calling
iterations per task (default 25) so a confused model can't loop forever.
