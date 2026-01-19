"""Ollama LLM client with OpenAI-compatible API.

Provides a client that communicates with Ollama using its OpenAI-compatible API,
with retry logic, streaming support, and proper error handling.
"""

import time
from collections.abc import Generator

from openai import APIConnectionError, APIStatusError, OpenAI
from openai.types.chat import ChatCompletionMessageParam

from config.settings import Settings, get_settings


class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""

    pass


class OllamaConnectionError(OllamaClientError):
    """Raised when Ollama server is not reachable."""

    pass


class OllamaModelNotFoundError(OllamaClientError):
    """Raised when the requested model is not available."""

    pass


class OllamaResponseError(OllamaClientError):
    """Raised when the response is empty or malformed."""

    pass


class OllamaClient:
    """OpenAI-compatible client for Ollama.

    Uses the OpenAI Python SDK to communicate with Ollama's OpenAI-compatible
    endpoint at /v1/chat/completions.

    Example:
        client = OllamaClient()
        response = client.chat("Hello, how are you?")
        print(response)

        # Streaming
        for chunk in client.chat_stream("Tell me a story"):
            print(chunk, end="", flush=True)
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize the Ollama client.

        Args:
            settings: Optional settings object. Uses global settings if not provided.
        """
        self._settings = settings or get_settings()
        self._client = OpenAI(
            base_url=f"{self._settings.ollama_url}/v1",
            api_key="ollama",  # Ollama doesn't require API key but OpenAI SDK needs one
        )

    @property
    def model(self) -> str:
        """Get the configured model name."""
        return self._settings.model

    @property
    def base_url(self) -> str:
        """Get the Ollama base URL."""
        return self._settings.ollama_url

    def _handle_connection_error(self, error: APIConnectionError) -> None:
        """Handle connection errors with clear message."""
        raise OllamaConnectionError(
            f"Ollama not running at {self._settings.ollama_url}. "
            "Please start Ollama with 'ollama serve' and try again."
        ) from error

    def _handle_status_error(self, error: APIStatusError) -> None:
        """Handle API status errors, including model not found."""
        if error.status_code == 404:
            # Model not found - try to list available models
            available_models = self._list_available_models()
            models_str = ", ".join(available_models) if available_models else "none found"
            raise OllamaModelNotFoundError(
                f"Model '{self._settings.model}' not found. "
                f"Available models: {models_str}. "
                f"Pull the model with 'ollama pull {self._settings.model}'."
            ) from error
        raise OllamaClientError(f"Ollama API error: {error.message}") from error

    def _list_available_models(self) -> list[str]:
        """Try to list available models from Ollama."""
        try:
            # Use the models endpoint
            response = self._client.models.list()
            return [model.id for model in response.data]
        except Exception:
            return []

    def _validate_response(self, content: str | None) -> str:
        """Validate that response content is not empty or malformed.

        Args:
            content: The response content to validate.

        Returns:
            The validated content string.

        Raises:
            OllamaResponseError: If content is empty or None.
        """
        if content is None or content.strip() == "":
            raise OllamaResponseError(
                "Received empty response from Ollama. "
                "The model may have failed to generate a response."
            )
        return content

    def chat(
        self,
        message: str,
        system_prompt: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Send a chat message and get a response.

        Args:
            message: The user message to send.
            system_prompt: Optional system prompt for context.
            conversation_history: Optional list of previous messages in the format
                [{"role": "user"|"assistant", "content": "..."}].

        Returns:
            The assistant's response text.

        Raises:
            OllamaConnectionError: If Ollama is not running.
            OllamaModelNotFoundError: If the model is not available.
            OllamaResponseError: If the response is empty.
        """
        messages = self._build_messages(message, system_prompt, conversation_history)

        last_error: Exception | None = None
        for attempt in range(self._settings.max_retries):
            try:
                response = self._client.chat.completions.create(
                    model=self._settings.model,
                    messages=messages,
                    timeout=self._settings.timeout,
                )
                content = response.choices[0].message.content
                return self._validate_response(content)

            except APIConnectionError as e:
                self._handle_connection_error(e)

            except APIStatusError as e:
                self._handle_status_error(e)

            except OllamaResponseError:
                # Empty response - retry with backoff
                last_error = OllamaResponseError("Empty response from model")
                if attempt < self._settings.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

            except Exception as e:
                last_error = e
                if attempt < self._settings.max_retries - 1:
                    time.sleep(2**attempt)  # Exponential backoff
                continue

        # All retries exhausted
        raise OllamaClientError(
            f"Failed after {self._settings.max_retries} attempts. Last error: {last_error}"
        )

    def chat_stream(
        self,
        message: str,
        system_prompt: str | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> Generator[str, None, None]:
        """Send a chat message and stream the response.

        Args:
            message: The user message to send.
            system_prompt: Optional system prompt for context.
            conversation_history: Optional list of previous messages.

        Yields:
            Chunks of the response text as they arrive.

        Raises:
            OllamaConnectionError: If Ollama is not running.
            OllamaModelNotFoundError: If the model is not available.
            OllamaResponseError: If the response is empty.
        """
        messages = self._build_messages(message, system_prompt, conversation_history)

        last_error: Exception | None = None
        for attempt in range(self._settings.max_retries):
            try:
                stream = self._client.chat.completions.create(
                    model=self._settings.model,
                    messages=messages,
                    stream=True,
                    timeout=self._settings.timeout,
                )

                has_content = False
                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        has_content = True
                        yield chunk.choices[0].delta.content

                if not has_content:
                    raise OllamaResponseError("Empty streaming response from model")

                return  # Success, exit retry loop

            except APIConnectionError as e:
                self._handle_connection_error(e)

            except APIStatusError as e:
                self._handle_status_error(e)

            except OllamaResponseError:
                last_error = OllamaResponseError("Empty streaming response")
                if attempt < self._settings.max_retries - 1:
                    time.sleep(2**attempt)
                continue

            except Exception as e:
                last_error = e
                if attempt < self._settings.max_retries - 1:
                    time.sleep(2**attempt)
                continue

        raise OllamaClientError(
            f"Streaming failed after {self._settings.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def _build_messages(
        self,
        message: str,
        system_prompt: str | None,
        conversation_history: list[dict[str, str]] | None,
    ) -> list[ChatCompletionMessageParam]:
        """Build the messages list for the API call.

        Args:
            message: The current user message.
            system_prompt: Optional system prompt.
            conversation_history: Optional previous messages.

        Returns:
            List of message dictionaries for the API.
        """
        messages: list[ChatCompletionMessageParam] = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if conversation_history:
            for hist_msg in conversation_history:
                role = hist_msg["role"]
                content = hist_msg["content"]
                if role == "user":
                    messages.append({"role": "user", "content": content})
                elif role == "assistant":
                    messages.append({"role": "assistant", "content": content})

        messages.append({"role": "user", "content": message})

        return messages
