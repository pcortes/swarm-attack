"""User metrics data model."""
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


@dataclass
class UserMetrics:
    """Data model for user activity metrics."""
    
    user_id: str
    login_history: List[datetime]
    last_active: Optional[datetime]
    total_actions: int