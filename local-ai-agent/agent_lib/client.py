import time

import requests


class OllamaClient:
    """Thin wrapper around Ollama's OpenAI-compatible chat completions endpoint,
    with retry/backoff for transient connection failures."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "hermes3",
                 max_retries: int = 3, backoff_seconds: float = 2.0):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds

    def chat(self, messages, tools, temperature: float = 0.2):
        url = f"{self.base_url}/v1/chat/completions"
        payload = {
            "model": self.model,
            "messages": messages,
            "tools": tools,
            "temperature": temperature,
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.post(url, json=payload, timeout=300)
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
                    continue
                raise ConnectionError(
                    f"Could not reach Ollama at {url} after {self.max_retries} attempts. "
                    f"Is 'ollama serve' running? ({last_error})"
                )

            if response.status_code == 200:
                return response.json()

            if response.status_code >= 500 and attempt < self.max_retries:
                time.sleep(self.backoff_seconds * attempt)
                continue

            raise RuntimeError(f"Ollama API error {response.status_code}: {response.text}")

        raise ConnectionError(f"Could not reach Ollama at {url} after {self.max_retries} attempts.")
