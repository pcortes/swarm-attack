"""Database query function to retrieve user login history from auth logs."""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def get_db_connection():
    """Get database connection. This should be mocked in tests."""
    raise NotImplementedError("Database connection not configured")


def get_user_login_history(user_id: str) -> Optional[dict]:
    """Retrieve login history for a user from the auth logs database.
    
    Args:
        user_id: The unique identifier of the user.
        
    Returns:
        A dictionary containing:
            - login_history: List of login timestamps (most recent first)
            - last_active: Timestamp of last activity
            - total_actions: Count of total actions
        Returns None if user is not found or on database error.
    """
    if not user_id:
        return None
    
    try:
        conn = get_db_connection()
        with conn:
            cursor = conn.cursor()
            with cursor:
                # Query login events from auth logs, ordered by timestamp descending
                cursor.execute(
                    "SELECT timestamp FROM auth_logs WHERE user_id = %s AND event_type = 'login' ORDER BY timestamp DESC",
                    (user_id,)
                )
                login_results = cursor.fetchall()
                
                # Query user data for last_active and total_actions
                cursor.execute(
                    "SELECT last_active, total_actions FROM users WHERE user_id = %s",
                    (user_id,)
                )
                user_data = cursor.fetchone()
                
                if user_data is None:
                    return None
                
                # Extract login timestamps
                login_history = [row["timestamp"] for row in login_results]
                
                return {
                    "login_history": login_history,
                    "last_active": user_data["last_active"],
                    "total_actions": user_data.get("total_actions", 0)
                }
    except Exception as e:
        logger.error(f"Database error while fetching login history for user {user_id}: {e}")
        return None