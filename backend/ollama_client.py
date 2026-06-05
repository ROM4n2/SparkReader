"""
Ollama HTTP API client.
Handles chat completion and embedding requests.
"""
import httpx
from config import OLLAMA_BASE_URL, CHAT_MODEL, EMBED_MODEL, SYSTEM_PROMPT


class OllamaClient:
    """Thin wrapper around Ollama's HTTP API."""

    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = CHAT_MODEL, embed_model: str = EMBED_MODEL):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.embed_model = embed_model
        self.client = httpx.Client(timeout=120.0)  # LLMs can be slow

    def chat(self, user_message: str, system_prompt: str = SYSTEM_PROMPT) -> str:
        """
        Send a chat message to Ollama and return the response text.

        Args:
            user_message: The user's question or input.
            system_prompt: System instruction for the model.

        Returns:
            The model's response as a string.

        Raises:
            ConnectionError: If Ollama is not running or unreachable.
            RuntimeError: If the API returns an error.
        """
        try:
            resp = self.client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "stream": False,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]
        except httpx.ConnectError:
            raise ConnectionError(
                f"无法连接到 Ollama（{self.base_url}）。\n"
                "请确保 Ollama 正在运行。"
            )
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Ollama API 返回错误: {e.response.status_code} {e.response.text}")

    def embed(self, text: str) -> list[float]:
        """
        Generate embeddings for a text string.

        Args:
            text: The text to embed.

        Returns:
            A list of floats (the embedding vector).

        Raises:
            ConnectionError: If Ollama is not running.
        """
        try:
            resp = self.client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.embed_model,
                    "prompt": text,
                },
            )
            resp.raise_for_status()
            return resp.json()["embedding"]
        except httpx.ConnectError:
            raise ConnectionError(f"无法连接到 Ollama（{self.base_url}）。")

    def close(self):
        self.client.close()
