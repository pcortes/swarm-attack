"""Clean module demonstrating Dependency Inversion Principle."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional


# Abstractions (interfaces)

class MessageSender(ABC):
    """Abstract message sender."""

    @abstractmethod
    def send(self, to: str, message: str) -> bool:
        """Send a message."""
        pass


class UserRepository(ABC):
    """Abstract user repository."""

    @abstractmethod
    def find_by_id(self, user_id: str) -> Optional[dict]:
        """Find user by ID."""
        pass


class Logger(ABC):
    """Abstract logger."""

    @abstractmethod
    def info(self, message: str) -> None:
        """Log info message."""
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        """Log error message."""
        pass


# High-level module depends on abstractions

class NotificationService:
    """Notification service depending on abstractions, not concretions."""

    def __init__(
        self,
        sender: MessageSender,
        user_repo: UserRepository,
        logger: Logger,
    ):
        """Initialize with abstract dependencies (DIP)."""
        self._sender = sender
        self._user_repo = user_repo
        self._logger = logger

    def notify_user(self, user_id: str, message: str) -> bool:
        """Notify a user."""
        user = self._user_repo.find_by_id(user_id)
        if not user:
            self._logger.error(f"User not found: {user_id}")
            return False

        success = self._sender.send(user["email"], message)
        if success:
            self._logger.info(f"Notification sent to {user_id}")
        else:
            self._logger.error(f"Failed to notify {user_id}")

        return success


# Concrete implementations

class EmailSender(MessageSender):
    """Email implementation of MessageSender."""

    def send(self, to: str, message: str) -> bool:
        """Send email."""
        # Would send actual email
        return True


class InMemoryUserRepository(UserRepository):
    """In-memory implementation of UserRepository."""

    def __init__(self):
        self._users = {}

    def find_by_id(self, user_id: str) -> Optional[dict]:
        """Find user in memory."""
        return self._users.get(user_id)


class ConsoleLogger(Logger):
    """Console implementation of Logger."""

    def info(self, message: str) -> None:
        """Print info to console."""
        print(f"[INFO] {message}")

    def error(self, message: str) -> None:
        """Print error to console."""
        print(f"[ERROR] {message}")
