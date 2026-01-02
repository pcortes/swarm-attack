"""Sample with SRP violation - class doing too many things."""
import json
import smtplib
from email.mime.text import MIMEText
from typing import Dict, List, Optional
import logging


class UserManager:
    """User manager that violates SRP - handles users, email, persistence, logging."""

    def __init__(self, db_path: str, smtp_host: str):
        self.db_path = db_path
        self.smtp_host = smtp_host
        self.users: Dict[str, Dict] = {}
        self.logger = logging.getLogger(__name__)

    # User management (responsibility 1)
    def create_user(self, username: str, email: str) -> bool:
        self.users[username] = {"email": email, "active": True}
        self.logger.info(f"Created user: {username}")
        self._save_to_disk()
        self._send_welcome_email(email, username)
        return True

    def delete_user(self, username: str) -> bool:
        if username in self.users:
            email = self.users[username]["email"]
            del self.users[username]
            self.logger.info(f"Deleted user: {username}")
            self._save_to_disk()
            self._send_goodbye_email(email, username)
            return True
        return False

    # Persistence (responsibility 2)
    def _save_to_disk(self) -> None:
        with open(self.db_path, "w") as f:
            json.dump(self.users, f)

    def _load_from_disk(self) -> None:
        try:
            with open(self.db_path) as f:
                self.users = json.load(f)
        except FileNotFoundError:
            self.users = {}

    # Email (responsibility 3)
    def _send_welcome_email(self, email: str, username: str) -> None:
        msg = MIMEText(f"Welcome {username}!")
        msg["Subject"] = "Welcome"
        msg["To"] = email
        # Would send email here

    def _send_goodbye_email(self, email: str, username: str) -> None:
        msg = MIMEText(f"Goodbye {username}")
        msg["Subject"] = "Account Deleted"
        msg["To"] = email
        # Would send email here

    # Reporting (responsibility 4)
    def generate_user_report(self) -> str:
        report = "User Report\n"
        for username, data in self.users.items():
            report += f"- {username}: {data['email']}\n"
        return report
