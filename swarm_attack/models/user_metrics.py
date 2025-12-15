"""UserMetrics data model for the external dashboard.

This module provides the UserMetrics class for representing user activity metrics.
"""
from datetime import datetime
from typing import List


class UserMetrics:
    """Data model representing user activity metrics for the dashboard.
    
    Attributes:
        user_id: Unique identifier for the user (string).
        login_history: List of datetime objects representing recent login timestamps.
        last_active: Datetime of the user's last activity.
        total_actions: Total number of actions performed by the user (non-negative int).
    """
    
    user_id: str
    login_history: List[datetime]
    last_active: datetime
    total_actions: int
    
    def __init__(
        self,
        user_id: str,
        login_history: List[datetime],
        last_active: datetime,
        total_actions: int
    ) -> None:
        """Initialize a UserMetrics instance.
        
        Args:
            user_id: Unique identifier for the user.
            login_history: List of datetime objects for login timestamps.
            last_active: Datetime of last user activity.
            total_actions: Total number of user actions.
            
        Raises:
            TypeError: If any field has incorrect type.
            ValueError: If total_actions is negative.
        """
        if not isinstance(user_id, str):
            raise TypeError("user_id must be a string")
        if not isinstance(login_history, list):
            raise TypeError("login_history must be a list")
        if not isinstance(last_active, datetime):
            raise TypeError("last_active must be a datetime")
        if not isinstance(total_actions, int) or isinstance(total_actions, bool):
            raise TypeError("total_actions must be an integer")
        if total_actions < 0:
            raise ValueError("total_actions must be non-negative")
        
        self.user_id = user_id
        self.login_history = login_history
        self.last_active = last_active
        self.total_actions = total_actions
    
    def to_dict(self) -> dict:
        """Serialize the UserMetrics to a JSON-compatible dictionary.
        
        Returns:
            Dictionary with all fields, datetime values as ISO format strings.
        """
        return {
            'user_id': self.user_id,
            'login_history': [dt.isoformat() for dt in self.login_history],
            'last_active': self.last_active.isoformat(),
            'total_actions': self.total_actions
        }