"""Clean configuration handling module."""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import os


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    port: int
    database: str
    username: str
    password: str

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """Create config from environment variables."""
        return cls(
            host=os.getenv("DB_HOST", "localhost"),
            port=int(os.getenv("DB_PORT", "5432")),
            database=os.getenv("DB_NAME", "app"),
            username=os.getenv("DB_USER", ""),
            password=os.getenv("DB_PASS", ""),
        )


@dataclass
class AppConfig:
    """Application configuration."""

    debug: bool = False
    log_level: str = "INFO"
    database: Optional[DatabaseConfig] = None
    features: Dict[str, bool] = field(default_factory=dict)

    def is_feature_enabled(self, feature: str) -> bool:
        """Check if a feature flag is enabled."""
        return self.features.get(feature, False)
