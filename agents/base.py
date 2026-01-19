"""Base agent class for MAT.

All specialized agents inherit from BaseAgent, which provides:
- Integration with the Ollama LLM client
- Conversation history management
- Context window management (truncation)
- Retry logic for malformed responses
"""

from dataclasses import dataclass, field

from llm.client import OllamaClient, OllamaClientError, OllamaResponseError

# Default context window limit (tokens). Most local models support 4K-8K.
# We use a conservative estimate for history management.
DEFAULT_MAX_CONTEXT_TOKENS = 4096
# Approximate chars per token (conservative estimate for English text)
CHARS_PER_TOKEN = 4
# Reserve tokens for system prompt and new message
RESERVED_TOKENS = 1024


@dataclass
class Message:
    """A message in the conversation history."""

    role: str  # "user" or "assistant"
    content: str


@dataclass
class BaseAgent:
    """Base class for all MAT agents.

    Attributes:
        name: Human-readable name for the agent.
        role: Description of the agent's role/purpose.
        system_prompt: The system prompt that defines agent behavior.
        client: The LLM client for making requests.
        conversation_history: List of messages in the conversation.
        max_context_tokens: Maximum tokens for context window.
        max_retries: Number of retries for malformed responses.
    """

    name: str
    role: str
    system_prompt: str
    client: OllamaClient = field(default_factory=OllamaClient)
    conversation_history: list[Message] = field(default_factory=list)
    max_context_tokens: int = DEFAULT_MAX_CONTEXT_TOKENS
    max_retries: int = 3

    def _estimate_tokens(self, text: str) -> int:
        """Estimate the number of tokens in text.

        Uses a simple character-based estimation.
        """
        return len(text) // CHARS_PER_TOKEN

    def _get_history_as_dicts(self) -> list[dict[str, str]]:
        """Convert conversation history to dict format for LLM client."""
        return [{"role": msg.role, "content": msg.content} for msg in self.conversation_history]

    def _truncate_history(self) -> None:
        """Truncate conversation history to fit within context window.

        Removes oldest messages (keeping the most recent) until the total
        estimated token count is below the limit.
        """
        available_tokens = self.max_context_tokens - RESERVED_TOKENS
        system_tokens = self._estimate_tokens(self.system_prompt)
        available_for_history = available_tokens - system_tokens

        if available_for_history <= 0:
            # System prompt alone exceeds limit - clear all history
            self.conversation_history.clear()
            return

        # Calculate total history tokens
        total_tokens = sum(self._estimate_tokens(msg.content) for msg in self.conversation_history)

        # Remove oldest messages until we're under the limit
        while total_tokens > available_for_history and self.conversation_history:
            removed = self.conversation_history.pop(0)
            total_tokens -= self._estimate_tokens(removed.content)

    def _is_response_valid(self, response: str) -> bool:
        """Check if a response is valid (not empty or clearly malformed).

        Args:
            response: The response text to validate.

        Returns:
            True if the response appears valid.
        """
        return bool(response and response.strip())

    def chat(self, message: str) -> str:
        """Send a message and get a response.

        Handles conversation history management, context window truncation,
        and retries for malformed responses.

        Args:
            message: The user message to send.

        Returns:
            The assistant's response text.

        Raises:
            OllamaClientError: If all retries fail or a non-recoverable error occurs.
        """
        # Add user message to history
        self.conversation_history.append(Message(role="user", content=message))

        # Truncate history if needed
        self._truncate_history()

        last_error: Exception | None = None
        for _attempt in range(self.max_retries):
            try:
                # Send to LLM
                response = self.client.chat(
                    message=message,
                    system_prompt=self.system_prompt,
                    conversation_history=self._get_history_as_dicts()[:-1],  # Exclude current msg
                )

                # Validate response
                if not self._is_response_valid(response):
                    raise OllamaResponseError("Received empty or malformed response")

                # Add assistant response to history
                self.conversation_history.append(Message(role="assistant", content=response))

                return response

            except OllamaResponseError as e:
                # Malformed response - retry
                last_error = e
                continue

            except OllamaClientError:
                # Non-recoverable error from client (connection, model not found, etc.)
                # Remove the user message we added since we couldn't process it
                if self.conversation_history and self.conversation_history[-1].role == "user":
                    self.conversation_history.pop()
                raise

        # All retries exhausted
        # Remove the user message since we couldn't get a valid response
        if self.conversation_history and self.conversation_history[-1].role == "user":
            self.conversation_history.pop()

        raise OllamaClientError(
            f"Failed to get valid response after {self.max_retries} attempts. "
            f"Last error: {last_error}"
        )

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self.conversation_history.clear()

    def get_history_summary(self) -> str:
        """Get a summary of the conversation history.

        Returns:
            A string summarizing the conversation (message count and estimated tokens).
        """
        total_tokens = sum(self._estimate_tokens(msg.content) for msg in self.conversation_history)
        return (
            f"Agent '{self.name}': {len(self.conversation_history)} messages, "
            f"~{total_tokens} tokens"
        )
