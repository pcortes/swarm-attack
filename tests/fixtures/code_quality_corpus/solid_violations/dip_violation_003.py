"""Sample with DIP violation - static method dependencies."""
from typing import Dict, Optional
import requests


class UserAuthenticator:
    """User authenticator that violates DIP - static method calls."""

    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user - DIP violation with static/direct calls."""
        # DIP violation: Direct call to concrete implementation
        user = DatabaseConnection.get_user(username)
        if not user:
            return None

        # DIP violation: Direct call to password hasher
        if not PasswordHasher.verify(password, user["password_hash"]):
            return None

        # DIP violation: Direct call to token generator
        token = JwtTokenGenerator.generate(user["id"])

        # DIP violation: Direct call to audit logger
        AuditLog.log_login(user["id"])

        return token


class DatabaseConnection:
    """Static database connection."""

    @staticmethod
    def get_user(username: str) -> Optional[Dict]:
        return {"id": "user_1", "password_hash": "hash"}


class PasswordHasher:
    """Static password hasher."""

    @staticmethod
    def verify(password: str, hash: str) -> bool:
        return True


class JwtTokenGenerator:
    """Static JWT token generator."""

    @staticmethod
    def generate(user_id: str) -> str:
        return "jwt_token"


class AuditLog:
    """Static audit logger."""

    @staticmethod
    def log_login(user_id: str) -> None:
        pass
