"""Clean module with proper HTTP error handling."""
from dataclasses import dataclass
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ApiError(Exception):
    """Base exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


class ConnectionError(ApiError):
    """Raised when connection to API fails."""

    pass


class AuthenticationError(ApiError):
    """Raised when authentication fails."""

    pass


class NotFoundError(ApiError):
    """Raised when resource is not found."""

    pass


@dataclass
class ApiResponse:
    """API response wrapper."""

    success: bool
    data: Optional[dict] = None
    error: Optional[str] = None


class ApiClient:
    """HTTP API client with proper error handling."""

    def __init__(self, base_url: str, api_key: str):
        """Initialize the API client."""
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    def get(self, endpoint: str) -> ApiResponse:
        """Make a GET request with proper error handling.

        Args:
            endpoint: The API endpoint to call.

        Returns:
            ApiResponse with success status and data or error.

        Raises:
            ConnectionError: If unable to connect.
            AuthenticationError: If API key is invalid.
            NotFoundError: If resource doesn't exist.
        """
        # Simulated implementation
        try:
            # Would make actual HTTP request here
            response_code = 200
            response_data = {"result": "success"}

            if response_code == 401:
                logger.warning(f"Authentication failed for {endpoint}")
                raise AuthenticationError("Invalid API key", status_code=401)

            if response_code == 404:
                logger.info(f"Resource not found: {endpoint}")
                raise NotFoundError(f"Resource not found: {endpoint}", status_code=404)

            return ApiResponse(success=True, data=response_data)

        except OSError as e:
            logger.error(f"Connection error: {e}")
            raise ConnectionError(f"Failed to connect: {e}")
