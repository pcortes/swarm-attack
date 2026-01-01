"""
Tests for state file HMAC integrity verification.

Tests verify:
- State files include signature field
- Load verifies signature before returning state
- Tampered files raise StateCorruptionError
- Signing key from config or environment
"""

import json
import os
import hmac
import hashlib
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from swarm_attack.state_store import StateStore, StateCorruptionError
from swarm_attack.models import RunState, FeaturePhase


@pytest.fixture
def temp_state_dir(tmp_path):
    """Create temporary state directory structure."""
    state_dir = tmp_path / ".swarm" / "state"
    state_dir.mkdir(parents=True)
    sessions_dir = tmp_path / ".swarm" / "sessions"
    sessions_dir.mkdir(parents=True)
    return tmp_path


@pytest.fixture
def mock_config(temp_state_dir):
    """Create a mock config for StateStore."""
    config = MagicMock()
    config.state_path = temp_state_dir / ".swarm" / "state"
    config.sessions_path = temp_state_dir / ".swarm" / "sessions"
    config.repo_root = str(temp_state_dir)
    config.sessions = MagicMock()
    config.sessions.stale_timeout_minutes = 60
    return config


@pytest.fixture
def state_store(mock_config):
    """Create a StateStore instance for testing."""
    return StateStore(mock_config)


class TestStateCorruptionError:
    """Tests for the StateCorruptionError exception."""

    def test_exception_can_be_raised(self):
        """StateCorruptionError can be raised and caught."""
        with pytest.raises(StateCorruptionError) as exc_info:
            raise StateCorruptionError("Signature verification failed")
        assert "Signature verification failed" in str(exc_info.value)

    def test_exception_inherits_from_exception(self):
        """StateCorruptionError is a proper Exception subclass."""
        assert issubclass(StateCorruptionError, Exception)


class TestSigningKeyRetrieval:
    """Tests for _get_signing_key method."""

    def test_get_signing_key_from_environment(self, state_store):
        """Signing key is retrieved from SWARM_STATE_KEY env var."""
        with patch.dict(os.environ, {"SWARM_STATE_KEY": "my-secret-key"}):
            key = state_store._get_signing_key()
            assert key == b"my-secret-key"

    def test_get_signing_key_default_when_not_set(self, state_store):
        """Default key is used when SWARM_STATE_KEY is not set."""
        env_without_key = {k: v for k, v in os.environ.items() if k != "SWARM_STATE_KEY"}
        with patch.dict(os.environ, env_without_key, clear=True):
            key = state_store._get_signing_key()
            assert key == b"default-dev-key"

    def test_signing_key_returns_bytes(self, state_store):
        """Signing key is returned as bytes."""
        key = state_store._get_signing_key()
        assert isinstance(key, bytes)


class TestStateSignature:
    """Tests for _sign_state and _verify_signature methods."""

    def test_sign_state_returns_hex_string(self, state_store):
        """_sign_state returns a hexadecimal signature string."""
        data = {"feature_id": "test", "phase": "NO_PRD"}
        signature = state_store._sign_state(data)

        # Should be a hex string (64 chars for SHA256)
        assert isinstance(signature, str)
        assert len(signature) == 64
        assert all(c in "0123456789abcdef" for c in signature)

    def test_sign_state_is_deterministic(self, state_store):
        """Same data produces same signature."""
        data = {"feature_id": "test", "phase": "NO_PRD"}
        sig1 = state_store._sign_state(data)
        sig2 = state_store._sign_state(data)
        assert sig1 == sig2

    def test_sign_state_different_data_different_signature(self, state_store):
        """Different data produces different signature."""
        data1 = {"feature_id": "test1", "phase": "NO_PRD"}
        data2 = {"feature_id": "test2", "phase": "NO_PRD"}
        sig1 = state_store._sign_state(data1)
        sig2 = state_store._sign_state(data2)
        assert sig1 != sig2

    def test_sign_state_key_order_independent(self, state_store):
        """Signature is independent of key order in dict (uses sort_keys)."""
        data1 = {"a": 1, "b": 2}
        data2 = {"b": 2, "a": 1}
        sig1 = state_store._sign_state(data1)
        sig2 = state_store._sign_state(data2)
        assert sig1 == sig2

    def test_verify_signature_valid(self, state_store):
        """_verify_signature returns True for valid signature."""
        data = {"feature_id": "test", "phase": "NO_PRD"}
        signature = state_store._sign_state(data)
        assert state_store._verify_signature(data, signature) is True

    def test_verify_signature_invalid(self, state_store):
        """_verify_signature returns False for invalid signature."""
        data = {"feature_id": "test", "phase": "NO_PRD"}
        bad_signature = "0" * 64
        assert state_store._verify_signature(data, bad_signature) is False

    def test_verify_signature_tampered_data(self, state_store):
        """_verify_signature returns False when data is tampered."""
        original_data = {"feature_id": "test", "phase": "NO_PRD"}
        signature = state_store._sign_state(original_data)

        tampered_data = {"feature_id": "TAMPERED", "phase": "NO_PRD"}
        assert state_store._verify_signature(tampered_data, signature) is False


class TestStateSaveWithSignature:
    """Tests for save() including signature in state files."""

    def test_save_includes_signature_field(self, state_store, mock_config):
        """Saved state file includes _signature field."""
        state = RunState(feature_id="test-feature", phase=FeaturePhase.NO_PRD)
        state_store.save(state)

        state_path = mock_config.state_path / "test-feature.json"
        with open(state_path) as f:
            saved_data = json.load(f)

        assert "_signature" in saved_data
        assert isinstance(saved_data["_signature"], str)
        assert len(saved_data["_signature"]) == 64

    def test_save_signature_is_valid(self, state_store, mock_config):
        """Saved signature can be verified."""
        state = RunState(feature_id="test-feature", phase=FeaturePhase.NO_PRD)
        state_store.save(state)

        state_path = mock_config.state_path / "test-feature.json"
        with open(state_path) as f:
            saved_data = json.load(f)

        signature = saved_data.pop("_signature")
        assert state_store._verify_signature(saved_data, signature) is True


class TestStateLoadWithVerification:
    """Tests for load() verifying signature before returning state."""

    def test_load_valid_signature_returns_state(self, state_store, mock_config):
        """Load returns state when signature is valid."""
        state = RunState(feature_id="test-feature", phase=FeaturePhase.NO_PRD)
        state_store.save(state)

        loaded = state_store.load("test-feature")
        assert loaded is not None
        assert loaded.feature_id == "test-feature"
        assert loaded.phase == FeaturePhase.NO_PRD

    def test_load_tampered_file_raises_corruption_error(self, state_store, mock_config):
        """Load raises StateCorruptionError when file is tampered."""
        # Save valid state
        state = RunState(feature_id="test-feature", phase=FeaturePhase.NO_PRD)
        state_store.save(state)

        # Tamper with the file
        state_path = mock_config.state_path / "test-feature.json"
        with open(state_path) as f:
            data = json.load(f)

        data["feature_id"] = "TAMPERED"
        with open(state_path, "w") as f:
            json.dump(data, f)

        # Load should raise StateCorruptionError
        with pytest.raises(StateCorruptionError) as exc_info:
            state_store.load("test-feature")
        assert "signature verification failed" in str(exc_info.value).lower()

    def test_load_missing_signature_raises_corruption_error(self, state_store, mock_config):
        """Load raises StateCorruptionError when signature is missing."""
        # Write state without signature
        state_path = mock_config.state_path / "test-feature.json"
        data = {
            "feature_id": "test-feature",
            "phase": "NO_PRD",
            "tasks": [],
            "debate_rounds": [],
            "spec_score": None,
        }
        with open(state_path, "w") as f:
            json.dump(data, f)

        with pytest.raises(StateCorruptionError) as exc_info:
            state_store.load("test-feature")
        assert "signature" in str(exc_info.value).lower()

    def test_load_invalid_signature_format_raises_corruption_error(self, state_store, mock_config):
        """Load raises StateCorruptionError when signature format is invalid."""
        state_path = mock_config.state_path / "test-feature.json"
        data = {
            "feature_id": "test-feature",
            "phase": "NO_PRD",
            "tasks": [],
            "debate_rounds": [],
            "spec_score": None,
            "_signature": "not-a-valid-hex-signature",
        }
        with open(state_path, "w") as f:
            json.dump(data, f)

        with pytest.raises(StateCorruptionError) as exc_info:
            state_store.load("test-feature")
        assert "signature" in str(exc_info.value).lower()


class TestSigningKeyConfiguration:
    """Tests for signing key from config or environment."""

    def test_different_keys_produce_different_signatures(self, mock_config):
        """Different signing keys produce incompatible signatures."""
        store1 = StateStore(mock_config)

        data = {"feature_id": "test", "phase": "NO_PRD"}

        with patch.dict(os.environ, {"SWARM_STATE_KEY": "key-one"}):
            sig1 = store1._sign_state(data)

        with patch.dict(os.environ, {"SWARM_STATE_KEY": "key-two"}):
            sig2 = store1._sign_state(data)

        assert sig1 != sig2

    def test_file_saved_with_one_key_fails_with_another(self, state_store, mock_config):
        """State saved with one key cannot be loaded with different key."""
        # Save with key-one
        with patch.dict(os.environ, {"SWARM_STATE_KEY": "key-one"}):
            state = RunState(feature_id="test-feature", phase=FeaturePhase.NO_PRD)
            state_store.save(state)

        # Try to load with key-two
        with patch.dict(os.environ, {"SWARM_STATE_KEY": "key-two"}):
            with pytest.raises(StateCorruptionError):
                state_store.load("test-feature")


class TestBackwardCompatibility:
    """Tests for backward compatibility with unsigned state files."""

    def test_load_unsigned_legacy_file_raises_corruption_error(self, state_store, mock_config):
        """
        Legacy files without signature raise StateCorruptionError.

        Note: This is by design - unsigned files should not be trusted.
        Migration script should sign existing files if needed.
        """
        state_path = mock_config.state_path / "legacy-feature.json"
        legacy_data = {
            "feature_id": "legacy-feature",
            "phase": "NO_PRD",
            "tasks": [],
            "debate_rounds": [],
            "spec_score": None,
        }
        with open(state_path, "w") as f:
            json.dump(legacy_data, f)

        # Unsigned files should fail verification
        with pytest.raises(StateCorruptionError):
            state_store.load("legacy-feature")
