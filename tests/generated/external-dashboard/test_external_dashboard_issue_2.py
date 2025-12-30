"""Tests for database query function to retrieve user login history.

These tests verify the database query function that retrieves login events
from existing auth logs for a given user. Tests MUST FAIL before implementation.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock


class TestLoginHistoryQueryFileExists:
    """Tests that verify the query module file exists."""

    def test_query_module_file_exists(self):
        """Test that the login history query module exists."""
        query_path = Path.cwd() / "external_dashboard" / "queries" / "login_history.py"
        assert query_path.exists(), "external_dashboard/queries/login_history.py must exist"

    def test_queries_directory_exists(self):
        """Test that the queries directory exists."""
        queries_dir = Path.cwd() / "external_dashboard" / "queries"
        assert queries_dir.is_dir(), "external_dashboard/queries/ directory must exist"

    def test_queries_init_file_exists(self):
        """Test that queries package has __init__.py."""
        init_path = Path.cwd() / "external_dashboard" / "queries" / "__init__.py"
        assert init_path.exists(), "external_dashboard/queries/__init__.py must exist"


class TestLoginHistoryQueryStructure:
    """Tests that verify the query module has required structure."""

    def test_module_defines_query_function(self):
        """Test that module defines the main query function."""
        query_path = Path.cwd() / "external_dashboard" / "queries" / "login_history.py"
        content = query_path.read_text()
        # Function definition is structural
        assert "def get_user_login_history" in content or "def get_login_history" in content, \
            "Module must define a login history query function"

    def test_module_has_error_handling(self):
        """Test that module includes try/except for database calls."""
        query_path = Path.cwd() / "external_dashboard" / "queries" / "login_history.py"
        content = query_path.read_text()
        assert "try:" in content and "except" in content, \
            "Module must include try/except around database calls"


class TestGetUserLoginHistoryFunction:
    """Tests for the get_user_login_history function behavior."""

    def test_function_can_be_imported(self):
        """Test that the query function can be imported from the module."""
        from external_dashboard.queries.login_history import get_user_login_history
        assert callable(get_user_login_history), "get_user_login_history must be callable"

    def test_returns_login_timestamps_for_valid_user(self):
        """Test that function returns list of login timestamps for a valid user."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        # Mock the database connection
        mock_db_result = [
            {"timestamp": datetime(2025, 1, 15, 10, 30, 0)},
            {"timestamp": datetime(2025, 1, 14, 9, 15, 0)},
        ]
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = mock_db_result
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            result = get_user_login_history("user123")
            
            assert result is not None, "Should return result for valid user"
            assert "login_history" in result, "Result must contain login_history"
            assert isinstance(result["login_history"], list), "login_history must be a list"

    def test_returns_timestamps_in_descending_order(self):
        """Test that login timestamps are returned most recent first."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        mock_db_result = [
            {"timestamp": datetime(2025, 1, 15, 10, 30, 0)},
            {"timestamp": datetime(2025, 1, 14, 9, 15, 0)},
            {"timestamp": datetime(2025, 1, 13, 8, 0, 0)},
        ]
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = mock_db_result
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            result = get_user_login_history("user123")
            
            login_history = result["login_history"]
            assert len(login_history) >= 2, "Should have multiple timestamps"
            # Verify descending order (most recent first)
            for i in range(len(login_history) - 1):
                assert login_history[i] >= login_history[i + 1], \
                    "Login timestamps must be in descending order (most recent first)"

    def test_returns_last_active_timestamp(self):
        """Test that function retrieves and returns last_active timestamp."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {
                "last_active": datetime(2025, 1, 15, 14, 22, 0)
            }
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            result = get_user_login_history("user123")
            
            assert "last_active" in result, "Result must contain last_active"
            assert isinstance(result["last_active"], datetime), "last_active must be a datetime"

    def test_returns_total_actions_count(self):
        """Test that function retrieves and returns total_actions count."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = {
                "last_active": datetime(2025, 1, 15, 14, 22, 0),
                "total_actions": 42
            }
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            result = get_user_login_history("user123")
            
            assert "total_actions" in result, "Result must contain total_actions"
            assert isinstance(result["total_actions"], int), "total_actions must be an integer"


class TestGetUserLoginHistoryUserNotFound:
    """Tests for handling user not found scenarios."""

    def test_returns_none_for_nonexistent_user(self):
        """Test that function returns None when user is not found."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchone.return_value = None
            mock_cursor.fetchall.return_value = []
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            result = get_user_login_history("nonexistent_user")
            
            assert result is None, "Should return None for nonexistent user"

    def test_handles_empty_user_id(self):
        """Test that function handles empty user_id appropriately."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        # Should either return None or raise ValueError for empty user_id
        result = get_user_login_history("")
        
        # Accept None as valid response for empty user_id
        assert result is None, "Should return None for empty user_id"


class TestGetUserLoginHistoryErrorHandling:
    """Tests for database error handling."""

    def test_handles_database_connection_error(self):
        """Test that function handles database connection errors gracefully."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_db.side_effect = Exception("Database connection failed")
            
            # Should not raise, should handle gracefully
            try:
                result = get_user_login_history("user123")
                # If it returns, should be None or raise specific exception
                assert result is None, "Should return None on database error"
            except Exception as e:
                # If it raises, should be a specific database error type
                assert "database" in str(e).lower() or "connection" in str(e).lower(), \
                    "Should raise descriptive database error"

    def test_handles_query_execution_error(self):
        """Test that function handles query execution errors gracefully."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.execute.side_effect = Exception("Query execution failed")
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            # Should not propagate raw exception
            try:
                result = get_user_login_history("user123")
                assert result is None, "Should return None on query error"
            except Exception as e:
                # Should be handled, not raw exception
                assert "Query execution failed" not in str(e), \
                    "Should wrap or handle raw database exceptions"

    def test_logs_error_on_database_failure(self):
        """Test that errors are logged when database query fails."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_db.side_effect = Exception("Database error")
            
            with patch('external_dashboard.queries.login_history.logger') as mock_logger:
                try:
                    get_user_login_history("user123")
                except Exception:
                    pass
                
                # Verify error was logged
                assert mock_logger.error.called or mock_logger.exception.called, \
                    "Should log error when database query fails"


class TestGetUserLoginHistoryQueryBehavior:
    """Tests for correct query behavior against auth logs."""

    def test_queries_auth_logs_table(self):
        """Test that function queries the auth logs table."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = None
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            get_user_login_history("user123")
            
            # Verify execute was called (query was made)
            assert mock_cursor.execute.called, "Should execute database query"

    def test_filters_by_user_id(self):
        """Test that function filters login events by user_id."""
        from external_dashboard.queries.login_history import get_user_login_history
        
        with patch('external_dashboard.queries.login_history.get_db_connection') as mock_db:
            mock_cursor = MagicMock()
            mock_cursor.fetchall.return_value = []
            mock_cursor.fetchone.return_value = None
            mock_db.return_value.__enter__ = Mock(return_value=mock_db)
            mock_db.return_value.__exit__ = Mock(return_value=False)
            mock_db.return_value.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
            mock_db.return_value.cursor.return_value.__exit__ = Mock(return_value=False)
            
            get_user_login_history("specific_user_123")
            
            # Verify user_id was passed to query
            call_args = mock_cursor.execute.call_args
            assert call_args is not None, "Should execute query with parameters"
            # Check that user_id appears in parameters (could be positional or keyword)
            args, kwargs = call_args
            params = args[1] if len(args) > 1 else kwargs.get('parameters', kwargs.get('params', ()))
            
            # User ID should be in the parameters somewhere
            param_str = str(params)
            assert "specific_user_123" in param_str or any(
                "specific_user_123" in str(p) for p in (params if isinstance(params, (list, tuple)) else [params])
            ), "Query should filter by the provided user_id"