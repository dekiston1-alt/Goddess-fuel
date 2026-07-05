# Local AI Agent

A minimal, local, tool-calling agent loop built on top of [Ollama](https://ollama.com)'s
OpenAI-compatible chat completions API. The agent can read/write files, append to logs,
list directories, and run shell commands on the host it's running on, and it persists
its conversation history to disk so a session can be resumed later.

## Requirements

- [Ollama](https://ollama.com) installed and running locally (`ollama serve`)
- A pulled model that supports tool calling, e.g. `ollama pull hermes3`
  (update the `model` field in `agent.py` if you use a different tag)
- Python 3.9+

## Setup

```bash
cd local-ai-agent
pip install -r requirements.txt
```

## Usage

```bash
python agent.py
```

You'll be prompted for a task. The agent will call tools (shell, file read/write,
append_log, list_directory) as needed until it produces a final text response.

Conversation state is saved to `agent_state.json` in the current working directory
after each turn, so re-running `agent.py` continues from where it left off. Delete
that file to start a fresh session.

## Tools

| Tool | Description |
|---|---|
| `execute_shell` | Runs a shell command and returns stdout/stderr |
| `file_write` | Overwrites a file with given content, creating parent directories as needed |
| `file_read` | Returns a file's contents |
| `append_log` | Appends a line to a file without overwriting it |
| `list_directory` | Lists the contents of a directory |

## Security note

This agent gives the model direct shell access on whatever machine runs it
(`subprocess.run(..., shell=True)`). Only run it in an environment you're
comfortable letting the model act in directly, and don't point it at
credentials or systems you don't want it modifying.
