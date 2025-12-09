"""
GPT-5 Client for Feature Swarm.

This module provides a client for calling OpenAI's GPT-5 Responses API.
GPT-5 is used for independent review tasks (SpecCriticAgent, IssueValidatorAgent)
to avoid Claude reviewing its own work.

The client uses subprocess to call curl directly, matching the confirmed working
implementation pattern.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from swarm_attack.config import SwarmConfig


# GPT-5 pricing (estimated): $2/1M input tokens, $8/1M output tokens
GPT5_INPUT_PRICE_PER_MILLION = 2.0
GPT5_OUTPUT_PRICE_PER_MILLION = 8.0


class GPT5ClientError(Exception):
    """Base exception for GPT-5 client errors."""
    pass


class GPT5APIError(GPT5ClientError):
    """Raised when the GPT-5 API returns an error response."""
    pass


class GPT5TimeoutError(GPT5ClientError):
    """Raised when the GPT-5 API request times out."""
    pass


@dataclass
class GPT5Result:
    """
    Result from a GPT-5 API call.

    Captures the response text, token usage, model information, and cost.
    """

    text: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    response_id: str
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "response_id": self.response_id,
            "cost_usd": self.cost_usd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GPT5Result:
        """Create from dictionary."""
        return cls(
            text=data.get("text", ""),
            input_tokens=data.get("input_tokens", 0),
            output_tokens=data.get("output_tokens", 0),
            total_tokens=data.get("total_tokens", 0),
            model=data.get("model", ""),
            response_id=data.get("response_id", ""),
            cost_usd=data.get("cost_usd", 0.0),
        )

    def calculate_cost(self) -> float:
        """
        Calculate the cost of this API call based on token usage.

        Uses GPT-5 pricing: $2/1M input, $8/1M output.

        Returns:
            Cost in USD.
        """
        input_cost = (self.input_tokens / 1_000_000) * GPT5_INPUT_PRICE_PER_MILLION
        output_cost = (self.output_tokens / 1_000_000) * GPT5_OUTPUT_PRICE_PER_MILLION
        return input_cost + output_cost


class GPT5Client:
    """
    Client for calling OpenAI's GPT-5 Responses API.

    Uses subprocess to call curl, matching the confirmed working implementation.
    This approach ensures compatibility with the tested API format.
    """

    API_ENDPOINT = "https://api.openai.com/v1/responses"

    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[SwarmConfig] = None,
    ) -> None:
        """
        Initialize the GPT-5 client.

        Args:
            api_key: OpenAI API key. If not provided, reads from OPENAI_API_KEY env var.
            config: Optional SwarmConfig for accessing OpenAI settings.

        Raises:
            GPT5ClientError: If no API key is available.
        """
        self._config = config

        # Get API key from argument, config, or environment
        if api_key:
            self._api_key = api_key
        elif config and hasattr(config, 'openai'):
            try:
                self._api_key = config.openai.get_api_key()
            except Exception:
                # Fall back to environment variable
                self._api_key = os.environ.get("OPENAI_API_KEY", "")
        else:
            self._api_key = os.environ.get("OPENAI_API_KEY", "")

        if not self._api_key:
            raise GPT5ClientError(
                "No OpenAI API key provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )

    def run(
        self,
        prompt: str,
        reasoning_effort: str = "medium",
        max_output_tokens: int = 3000,
        timeout_seconds: int = 120,
    ) -> GPT5Result:
        """
        Call the GPT-5 Responses API.

        Args:
            prompt: The prompt to send to GPT-5.
            reasoning_effort: Reasoning effort level ("low", "medium", "high").
            max_output_tokens: Maximum tokens in the response.
            timeout_seconds: Request timeout in seconds.

        Returns:
            GPT5Result with the response text and metadata.

        Raises:
            GPT5APIError: If the API returns an error response.
            GPT5TimeoutError: If the request times out.
            GPT5ClientError: For other errors (network, JSON parsing, etc.).
        """
        # Build the request payload
        payload = {
            "model": "gpt-5",
            "input": prompt,
            "reasoning": {"effort": reasoning_effort},
            "max_output_tokens": max_output_tokens,
        }

        # Build curl command
        curl_cmd = [
            "curl", "-s",
            self.API_ENDPOINT,
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: Bearer {self._api_key}",
            "-d", json.dumps(payload),
        ]

        # Execute curl with timeout
        try:
            result = subprocess.run(
                curl_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            raise GPT5TimeoutError(f"GPT-5 request timed out after {timeout_seconds} seconds")

        # Check for curl failure
        if result.returncode != 0:
            raise GPT5ClientError(
                f"Curl command failed with return code {result.returncode}: {result.stderr}"
            )

        # Parse JSON response
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            raise GPT5ClientError(f"Failed to parse JSON response: {e}")

        # Check for API error (note: successful responses have "error": null)
        if data.get("error") is not None:
            error_obj = data["error"]
            if isinstance(error_obj, dict):
                error_msg = error_obj.get("message", "Unknown API error")
            else:
                error_msg = str(error_obj)
            raise GPT5APIError(f"GPT-5 API error: {error_msg}")

        # Extract text from response
        text = self._extract_text(data)
        if not text:
            raise GPT5ClientError("No output text found in GPT-5 response (empty response)")

        # Extract usage information
        usage = data.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        # Build result
        gpt5_result = GPT5Result(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            model=data.get("model", "gpt-5"),
            response_id=data.get("id", ""),
        )

        # Calculate and set cost
        gpt5_result.cost_usd = gpt5_result.calculate_cost()

        return gpt5_result

    def _extract_text(self, data: dict[str, Any]) -> str:
        """
        Extract the output text from a GPT-5 response.

        The response format has nested output array with message content.

        Args:
            data: Parsed JSON response from GPT-5 API.

        Returns:
            Extracted text content, or empty string if not found.
        """
        for item in data.get("output", []):
            if item.get("type") == "message":
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        return content.get("text", "")
        return ""
