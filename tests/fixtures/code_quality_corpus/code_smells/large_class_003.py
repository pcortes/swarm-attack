"""Sample with large class code smell - HTTP client doing too much."""
from typing import Any, Dict, List, Optional
import json
import time


class HttpClient:
    """HTTP client class that has grown too large."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {}
        self.cookies = {}
        self.timeout = 30
        self.retries = 3
        self.retry_delay = 1
        self.auth_token = None
        self.api_key = None
        self.last_response = None
        self.last_request = None
        self.request_count = 0
        self.error_count = 0
        self.interceptors = []
        self.middleware = []
        self.cache = {}
        self.rate_limit_remaining = None
        self.rate_limit_reset = None

    def set_header(self, name: str, value: str) -> None:
        """Set header."""
        self.headers[name] = value

    def remove_header(self, name: str) -> None:
        """Remove header."""
        self.headers.pop(name, None)

    def set_cookie(self, name: str, value: str) -> None:
        """Set cookie."""
        self.cookies[name] = value

    def clear_cookies(self) -> None:
        """Clear cookies."""
        self.cookies = {}

    def set_timeout(self, seconds: int) -> None:
        """Set timeout."""
        self.timeout = seconds

    def set_retries(self, count: int) -> None:
        """Set retry count."""
        self.retries = count

    def set_auth_token(self, token: str) -> None:
        """Set auth token."""
        self.auth_token = token
        self.headers["Authorization"] = f"Bearer {token}"

    def set_api_key(self, key: str) -> None:
        """Set API key."""
        self.api_key = key
        self.headers["X-API-Key"] = key

    def get(self, path: str, params: Optional[Dict] = None) -> Dict:
        """GET request."""
        self.request_count += 1
        return {"status": 200, "data": {}}

    def post(self, path: str, data: Optional[Dict] = None) -> Dict:
        """POST request."""
        self.request_count += 1
        return {"status": 201, "data": {}}

    def put(self, path: str, data: Optional[Dict] = None) -> Dict:
        """PUT request."""
        self.request_count += 1
        return {"status": 200, "data": {}}

    def patch(self, path: str, data: Optional[Dict] = None) -> Dict:
        """PATCH request."""
        self.request_count += 1
        return {"status": 200, "data": {}}

    def delete(self, path: str) -> Dict:
        """DELETE request."""
        self.request_count += 1
        return {"status": 204, "data": {}}

    def head(self, path: str) -> Dict:
        """HEAD request."""
        self.request_count += 1
        return {"status": 200, "headers": {}}

    def options(self, path: str) -> Dict:
        """OPTIONS request."""
        self.request_count += 1
        return {"status": 200, "allowed": []}

    def upload_file(self, path: str, file_path: str) -> Dict:
        """Upload file."""
        self.request_count += 1
        return {"status": 200, "file_id": "abc"}

    def download_file(self, path: str, save_path: str) -> bool:
        """Download file."""
        self.request_count += 1
        return True

    def stream(self, path: str) -> Any:
        """Stream response."""
        self.request_count += 1
        return iter([])

    def add_interceptor(self, interceptor: Any) -> None:
        """Add interceptor."""
        self.interceptors.append(interceptor)

    def add_middleware(self, middleware: Any) -> None:
        """Add middleware."""
        self.middleware.append(middleware)

    def cache_response(self, key: str, response: Dict, ttl: int = 300) -> None:
        """Cache response."""
        self.cache[key] = {"response": response, "expires": time.time() + ttl}

    def get_cached(self, key: str) -> Optional[Dict]:
        """Get cached response."""
        cached = self.cache.get(key)
        if cached and cached["expires"] > time.time():
            return cached["response"]
        return None

    def clear_cache(self) -> None:
        """Clear cache."""
        self.cache = {}

    def get_stats(self) -> Dict:
        """Get request stats."""
        return {
            "total_requests": self.request_count,
            "errors": self.error_count,
            "cache_size": len(self.cache),
            "rate_limit_remaining": self.rate_limit_remaining,
        }

    def reset_stats(self) -> None:
        """Reset stats."""
        self.request_count = 0
        self.error_count = 0

    def health_check(self) -> bool:
        """Health check."""
        try:
            self.get("/health")
            return True
        except Exception:
            return False

    def get_last_response(self) -> Optional[Dict]:
        """Get last response."""
        return self.last_response

    def get_last_request(self) -> Optional[Dict]:
        """Get last request."""
        return self.last_request

    def serialize_params(self, params: Dict) -> str:
        """Serialize params."""
        return "&".join(f"{k}={v}" for k, v in params.items())

    def parse_response(self, raw: str) -> Dict:
        """Parse response."""
        return json.loads(raw)

    def handle_rate_limit(self) -> None:
        """Handle rate limiting."""
        if self.rate_limit_reset:
            wait_time = max(0, self.rate_limit_reset - time.time())
            time.sleep(wait_time)

    def retry_request(self, method: str, path: str, **kwargs) -> Dict:
        """Retry failed request."""
        for i in range(self.retries):
            try:
                return getattr(self, method)(path, **kwargs)
            except Exception:
                time.sleep(self.retry_delay * (i + 1))
        return {"status": 500, "error": "Max retries exceeded"}
