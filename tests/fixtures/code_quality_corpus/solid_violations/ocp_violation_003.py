"""Sample with OCP violation - string type checking."""
from typing import Dict, Any


class NotificationSender:
    """Notification sender with OCP violation - string type checking."""

    def send(self, notification: Dict[str, Any]) -> bool:
        """Send notification - OCP violation with string type matching."""
        channel = notification.get("channel", "")

        # OCP violation: new channels require code modification
        if channel == "email":
            return self._send_email(
                notification["to"],
                notification["subject"],
                notification["body"]
            )
        elif channel == "sms":
            return self._send_sms(
                notification["phone"],
                notification["message"]
            )
        elif channel == "push":
            return self._send_push(
                notification["device_id"],
                notification["title"],
                notification["body"]
            )
        elif channel == "slack":
            return self._send_slack(
                notification["webhook"],
                notification["message"]
            )
        elif channel == "webhook":
            return self._send_webhook(
                notification["url"],
                notification["payload"]
            )
        else:
            return False

    def _send_email(self, to: str, subject: str, body: str) -> bool:
        return True

    def _send_sms(self, phone: str, message: str) -> bool:
        return True

    def _send_push(self, device_id: str, title: str, body: str) -> bool:
        return True

    def _send_slack(self, webhook: str, message: str) -> bool:
        return True

    def _send_webhook(self, url: str, payload: Dict) -> bool:
        return True
