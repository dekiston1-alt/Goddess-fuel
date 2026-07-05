import json
import logging

from .client import OllamaClient
from .state import load_state, save_state, prune_context
from .tools import TOOL_IMPLEMENTATIONS, TOOL_SCHEMAS

logger = logging.getLogger("local_ai_agent")

DEFAULT_SYSTEM_PROMPT = (
    "You are a local AI systems engineer with access to shell, file, and "
    "logging tools on this host. Accomplish tasks by using these tools "
    "directly rather than describing what you would do. If a command fails, "
    "read the error and try a different approach."
)


def run_agent(task_prompt: str, state_file: str = "agent_state.json",
              model: str = "hermes3", base_url: str = "http://localhost:11434",
              max_iterations: int = 25) -> str:
    """Runs the agent loop to completion for a single task prompt.
    Returns the agent's final text response."""
    history = load_state(state_file)

    if not history:
        history.append({"role": "system", "content": DEFAULT_SYSTEM_PROMPT})

    history.append({"role": "user", "content": task_prompt})

    client = OllamaClient(base_url=base_url, model=model)

    for iteration in range(max_iterations):
        history = prune_context(history)
        logger.info("Thinking (iteration %d)...", iteration + 1)

        data = client.chat(history, TOOL_SCHEMAS)
        message = data["choices"][0]["message"]
        history.append(message)

        tool_calls = message.get("tool_calls")
        if not tool_calls:
            save_state(state_file, history)
            return message.get("content", "")

        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            try:
                arguments = json.loads(tool_call["function"]["arguments"])
            except json.JSONDecodeError as e:
                result = f"Error: could not parse arguments for {function_name}: {e}"
            else:
                logger.info("Executing tool: %s(%s)", function_name, arguments)
                implementation = TOOL_IMPLEMENTATIONS.get(function_name)
                if implementation is None:
                    result = f"Error: unknown tool {function_name}"
                else:
                    try:
                        result = implementation(arguments)
                    except Exception as e:
                        result = f"Error: tool {function_name} raised an exception: {e}"

            logger.info("Result: %s", result[:300] + ("..." if len(result) > 300 else ""))

            history.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "name": function_name,
                "content": result,
            })

        save_state(state_file, history)

    save_state(state_file, history)
    return f"Stopped after {max_iterations} tool-calling iterations without a final answer."
