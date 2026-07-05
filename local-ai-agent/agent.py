import os
import json
import subprocess
import requests

# ---------------------------------------------------------------------------
# 1. CORE TOOL DEFINITIONS
# ---------------------------------------------------------------------------

def execute_shell(command: str) -> str:
    """Executes a shell command and returns stdout/stderr."""
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        output = result.stdout
        if result.stderr:
            output += f"\n[STDERR]: {result.stderr}"
        return output if output else "[Command executed successfully with no output]"
    except Exception as e:
        return f"Error executing command: {str(e)}"

def file_write(filepath: str, content: str) -> str:
    """Writes content to a file, overwriting it."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing to file: {str(e)}"

def file_read(filepath: str) -> str:
    """Reads the content of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

def append_log(filepath: str, log_entry: str) -> str:
    """Appends text to a file without overwriting."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(f"{log_entry}\n")
        return f"Successfully appended to {filepath}"
    except Exception as e:
        return f"Error appending to file: {str(e)}"

def list_directory(directory_path: str) -> str:
    """Lists files and folders in a directory."""
    try:
        items = os.listdir(directory_path)
        return f"Contents of '{directory_path}':\n" + "\n".join(items)
    except Exception as e:
        return f"Error listing directory: {str(e)}"


# ---------------------------------------------------------------------------
# 2. FULL JSON TOOL SCHEMAS FOR THE LLM
# ---------------------------------------------------------------------------

tools = [
    {
        "type": "function",
        "function": {
            "name": "execute_shell",
            "description": "Execute a raw shell command on the host system. Use this for terminal operations, running scripts, or interacting with the OS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The shell command to run."}
                },
                "required": ["command"]
            }
        }
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
                    "content": {"type": "string", "description": "The full text content to write."}
                },
                "required": ["filepath", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_read",
            "description": "Read and return the text content of a file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file to read."}
                },
                "required": ["filepath"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_log",
            "description": "Append a string to the end of a file without overwriting existing content. Excellent for logs or iterative coding.",
            "parameters": {
                "type": "object",
                "properties": {
                    "filepath": {"type": "string", "description": "The path to the file."},
                    "log_entry": {"type": "string", "description": "The text entry to append."}
                },
                "required": ["filepath", "log_entry"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List all files and folders in a specific directory to map out the environment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {"type": "string", "description": "The directory path (e.g., '.' for current)."}
                },
                "required": ["directory_path"]
            }
        }
    }
]


# ---------------------------------------------------------------------------
# 3. STATE MANAGEMENT & CONTEXT PRUNING
# ---------------------------------------------------------------------------

STATE_FILE = "agent_state.json"

def save_state(history):
    """Saves the conversation history to disk."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)

def load_state():
    """Loads the conversation history from disk if it exists."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def prune_context(history, max_turns=16):
    """
    Keeps the system prompt and recent turns.
    Strips orphaned tool calls from the top of the slice to prevent API crashes.
    """
    if len(history) <= max_turns + 1:
        return history

    system_prompt = history[0]
    recent = history[-max_turns:]

    # If the cutoff landed right on a tool response without its triggering assistant message,
    # the API will reject it. Pop them until we find a clean starting point.
    while recent and recent[0]["role"] == "tool":
        recent.pop(0)

    return [system_prompt] + recent


# ---------------------------------------------------------------------------
# 4. MAIN EXECUTION LOOP
# ---------------------------------------------------------------------------

def run_agent(task_prompt: str):
    print("Agent initializing...")
    history = load_state()

    if not history:
        history.append({
            "role": "system",
            "content": (
                "You are a local AI systems engineer with access to shell, file, and "
                "logging tools on this host. Accomplish tasks by using these tools directly "
                "rather than describing what you would do. If a command fails, read the "
                "error and try a different approach."
            )
        })

    # Append the new goal
    history.append({"role": "user", "content": task_prompt})

    while True:
        # Prevent context window explosion
        history = prune_context(history)
        print("\nThinking...")

        # Connect to the local Ollama instance using the OpenAI compatibility layer
        try:
            response = requests.post(
                "http://localhost:11434/v1/chat/completions",
                json={
                    "model": "hermes",
                    "messages": history,
                    "tools": tools,
                    "temperature": 0.2
                }
            )
        except Exception as e:
            print(f"Connection Error: {str(e)}. Is Ollama running?")
            break

        if response.status_code != 200:
            print(f"API Error: {response.text}")
            break

        data = response.json()
        message = data["choices"][0]["message"]
        history.append(message)

        # If no tools were called, the agent has finished its thought process
        if "tool_calls" not in message or not message["tool_calls"]:
            print("\nAgent:")
            print(message.get("content", ""))
            save_state(history)
            break

        # Execute the requested tools
        for tool_call in message["tool_calls"]:
            function_name = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])

            print(f"\nExecuting Tool: {function_name}")
            print(f"Arguments: {arguments}")

            # The execution router
            if function_name == "execute_shell":
                result = execute_shell(arguments["command"])
            elif function_name == "file_write":
                result = file_write(arguments["filepath"], arguments["content"])
            elif function_name == "file_read":
                result = file_read(arguments["filepath"])
            elif function_name == "append_log":
                result = append_log(arguments["filepath"], arguments["log_entry"])
            elif function_name == "list_directory":
                result = list_directory(arguments["directory_path"])
            else:
                result = f"Error: Unknown tool {function_name}"

            print(f"Result:\n{result[:300]}..." if len(result) > 300 else f"Result:\n{result}")

            # Feed the result back to the LLM
            history.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result
            })

        # Save progress after tool execution so nothing is lost if interrupted
        save_state(history)

if __name__ == "__main__":
    print("Local AI Agent")
    user_input = input("Enter your task: ")
    run_agent(user_input)
