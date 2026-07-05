import os
import re
import subprocess

import requests

# Commands that are almost never intentional in an autonomous loop and are
# hard or impossible to undo. Blocked unless AGENT_ALLOW_DANGEROUS=1 is set.
_DANGEROUS_PATTERNS = [
    r"rm\s+-[a-zA-Z]*r[a-zA-Z]*f",       # rm -rf / -fr / etc.
    r"rm\s+-[a-zA-Z]*f[a-zA-Z]*r",
    r"mkfs\.",
    r"dd\s+if=",
    r"\bshutdown\b",
    r"\breboot\b",
    r":\(\)\s*\{.*:\|:.*\};:",           # fork bomb
    r">\s*/dev/sd[a-z]",
]


def _is_dangerous(command: str) -> bool:
    return any(re.search(p, command) for p in _DANGEROUS_PATTERNS)


def execute_shell(command: str, timeout: int = 120) -> str:
    """Executes a shell command and returns stdout/stderr."""
    if _is_dangerous(command) and os.environ.get("AGENT_ALLOW_DANGEROUS") != "1":
        return (
            "Blocked: this command matches a destructive pattern "
            "(e.g. rm -rf, dd, mkfs, shutdown, fork bomb). "
            "Set AGENT_ALLOW_DANGEROUS=1 in the environment to allow it."
        )
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]: {result.stderr}"
        output += f"\n[EXIT CODE]: {result.returncode}"
        return output.strip() if output.strip() else "[Command executed successfully with no output]"
    except subprocess.TimeoutExpired:
        return f"Error: command timed out after {timeout}s"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def file_write(filepath: str, content: str) -> str:
    """Writes content to a file, overwriting it."""
    try:
        directory = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(directory, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"


def file_read(filepath: str) -> str:
    """Reads the content of a file."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"


def append_log(filepath: str, log_entry: str) -> str:
    """Appends text to a file without overwriting."""
    try:
        directory = os.path.dirname(os.path.abspath(filepath))
        os.makedirs(directory, exist_ok=True)
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(f"{log_entry}\n")
        return f"Successfully appended to {filepath}"
    except Exception as e:
        return f"Error appending to file: {str(e)}"


def list_directory(directory_path: str) -> str:
    """Lists files and folders in a directory."""
    try:
        items = sorted(os.listdir(directory_path))
        return f"Contents of '{directory_path}':\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


def search_text(pattern: str, directory_path: str = ".", max_results: int = 200) -> str:
    """Recursively greps for a regex pattern under a directory."""
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"Error: invalid regex pattern: {e}"

    matches = []
    done = False
    for root, dirs, files in os.walk(directory_path):
        if done:
            break
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    for lineno, line in enumerate(f, start=1):
                        if regex.search(line):
                            matches.append(f"{path}:{lineno}: {line.rstrip()}")
                            if len(matches) >= max_results:
                                done = True
                                break
            except (IsADirectoryError, PermissionError):
                continue
            if done:
                break
    if not matches:
        return "No matches found."
    return "\n".join(matches)


def http_get(url: str, timeout: int = 30) -> str:
    """Fetches a URL over HTTP(S) and returns the response body, truncated."""
    if not url.startswith(("http://", "https://")):
        return "Error: url must start with http:// or https://"
    try:
        response = requests.get(url, timeout=timeout)
        body = response.text
        truncated = body[:5000]
        suffix = "\n...[truncated]" if len(body) > 5000 else ""
        return f"[STATUS]: {response.status_code}\n{truncated}{suffix}"
    except Exception as e:
        return f"Error fetching URL: {str(e)}"


TOOL_IMPLEMENTATIONS = {
    "execute_shell": lambda args: execute_shell(args["command"], args.get("timeout", 120)),
    "file_write": lambda args: file_write(args["filepath"], args["content"]),
    "file_read": lambda args: file_read(args["filepath"]),
    "append_log": lambda args: append_log(args["filepath"], args["log_entry"]),
    "list_directory": lambda args: list_directory(args["directory_path"]),
    "search_text": lambda args: search_text(
        args["pattern"], args.get("directory_path", "."), args.get("max_results", 200)
    ),
    "http_get": lambda args: http_get(args["url"], args.get("timeout", 30)),
}


TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a shell command on the host and return stdout/stderr/exit code. Destructive commands (rm -rf, dd, mkfs, shutdown, etc.) are blocked by default.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."},
                    "timeout": {"type": "integer", "description": "Max seconds to wait before killing the command. Defaults to 120."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_write",
            "description": "Write text content to a file. Overwrites the file if it exists. Automatically creates missing directories.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file."},
                    "content": {"type": "string", "description": "The full text content to write."},
                },
                "required": ["filepath", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read and return the text content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file to read."},
                },
                "required": ["filepath"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_log",
            "description": "Append a string to the end of a file without overwriting existing content. Useful for logs or iterative notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file."},
                    "log_entry": {"type": "string", "description": "The text entry to append."},
                },
                "required": ["filepath", "log_entry"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List all files and folders in a specific directory to map out the environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "The directory path (e.g., '.' for current)."},
                },
                "required": ["directory_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_text",
            "description": "Recursively search files under a directory for a regex pattern, returning matching file:line:content entries.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search for."},
                    "directory_path": {"type": "string", "description": "Directory to search under. Defaults to '.'."},
                    "max_results": {"type": "integer", "description": "Maximum number of matches to return. Defaults to 200."},
                },
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "http_get",
            "description": "Fetch a URL over HTTP(S) and return its response status and body (truncated to 5000 characters).",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch, including http:// or https://."},
                    "timeout": {"type": "integer", "description": "Max seconds to wait for a response. Defaults to 30."},
                },
                "required": ["url"],
            },
        },
    },
]
