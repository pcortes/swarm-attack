"""
Manual integration test for chief-of-staff configuration.
Run with: python -m swarm_attack.hello_autopilot
"""

from swarm_attack.chief_of_staff.config import (
    ChiefOfStaffConfig,
    AutopilotConfig,
    AutopilotConfigPrefs,  # Test backwards compatibility
    CheckpointConfig,
)
from swarm_attack.chief_of_staff.checkpoints import CheckpointSystem
from swarm_attack.chief_of_staff.models import AutopilotSession, CheckpointTrigger


def test_config_loading():
    """Test that config loads correctly."""
    print("=" * 60)
    print("TEST 1: Config Loading")
    print("=" * 60)

    # Default config
    config = ChiefOfStaffConfig()
    print(f"  Default budget: ${config.autopilot.default_budget}")
    print(f"  Default duration: {config.autopilot.default_duration}")
    print(f"  Pause on approval: {config.autopilot.pause_on_approval}")
    print(f"  Storage path: {config.storage_path}")

    # Custom config
    custom = ChiefOfStaffConfig(
        autopilot=AutopilotConfig(default_budget=25.0, default_duration="4h"),
        checkpoints=CheckpointConfig(budget_usd=5.0, duration_minutes=30),
    )
    print(f"\n  Custom budget: ${custom.autopilot.default_budget}")
    print(f"  Custom checkpoint threshold: ${custom.checkpoints.budget_usd}")

    return True


def test_backwards_compatibility():
    """Test that AutopilotConfigPrefs alias works."""
    print("\n" + "=" * 60)
    print("TEST 2: Backwards Compatibility")
    print("=" * 60)

    # Old name should still work
    old_config = AutopilotConfigPrefs()
    new_config = AutopilotConfig()

    assert type(old_config) == type(new_config), "Types should match!"
    print(f"  AutopilotConfigPrefs is AutopilotConfig: {AutopilotConfigPrefs is AutopilotConfig}")
    print(f"  Old config type: {type(old_config).__name__}")
    print(f"  Instance equality: {old_config == new_config}")

    return True


def test_checkpoint_system():
    """Test checkpoint threshold detection using actual CheckpointSystem API."""
    print("\n" + "=" * 60)
    print("TEST 3: Checkpoint System")
    print("=" * 60)

    # Create config with specific thresholds
    config = ChiefOfStaffConfig(
        checkpoints=CheckpointConfig(budget_usd=10.0, duration_minutes=60, error_streak=3)
    )
    checkpoint = CheckpointSystem(config)

    # Create a test session under budget
    session_under = AutopilotSession(
        session_id="test-1",
        started_at="2024-01-01T00:00:00Z",
        budget_usd=10.0,
        duration_limit_seconds=3600,  # 60 min
        cost_spent_usd=5.0,
        duration_seconds=0,
    )

    trigger = checkpoint.check_triggers(session_under, "normal action")
    print(f"  Cost $5 (under $10 limit): trigger={trigger}")
    assert trigger is None, "Should not trigger under budget"

    # Create a session over budget
    session_over = AutopilotSession(
        session_id="test-2",
        started_at="2024-01-01T00:00:00Z",
        budget_usd=10.0,
        duration_limit_seconds=3600,
        cost_spent_usd=15.0,
        duration_seconds=0,
    )

    trigger = checkpoint.check_triggers(session_over, "normal action")
    print(f"  Cost $15 (over $10 limit): trigger={trigger}")
    assert trigger == CheckpointTrigger.COST_THRESHOLD, "Should trigger cost threshold"

    # Test duration threshold
    session_time_under = AutopilotSession(
        session_id="test-3",
        started_at="2024-01-01T00:00:00Z",
        budget_usd=100.0,
        duration_limit_seconds=3600,
        cost_spent_usd=0,
        duration_seconds=30 * 60,  # 30 min
    )
    trigger = checkpoint.check_triggers(session_time_under, "normal action")
    print(f"  Duration 30min (under 60min limit): trigger={trigger}")

    session_time_over = AutopilotSession(
        session_id="test-4",
        started_at="2024-01-01T00:00:00Z",
        budget_usd=100.0,
        duration_limit_seconds=3600,
        cost_spent_usd=0,
        duration_seconds=90 * 60,  # 90 min
    )
    trigger = checkpoint.check_triggers(session_time_over, "normal action")
    print(f"  Duration 90min (over 60min limit): trigger={trigger}")
    assert trigger == CheckpointTrigger.TIME_THRESHOLD, "Should trigger time threshold"

    # Test high risk action detection
    session_ok = AutopilotSession(
        session_id="test-5",
        started_at="2024-01-01T00:00:00Z",
        budget_usd=100.0,
        duration_limit_seconds=7200,
        cost_spent_usd=0,
        duration_seconds=0,
    )
    trigger = checkpoint.check_triggers(session_ok, "push to main branch")
    print(f"  High-risk action 'push to main': trigger={trigger}")
    assert trigger == CheckpointTrigger.HIGH_RISK_ACTION, "Should detect high-risk action"

    # Test error streak
    checkpoint2 = CheckpointSystem(config)
    checkpoint2.record_error()
    checkpoint2.record_error()
    trigger = checkpoint2.check_triggers(session_ok, "normal action")
    print(f"  After 2 errors: trigger={trigger}")

    checkpoint2.record_error()  # 3rd error
    trigger = checkpoint2.check_triggers(session_ok, "normal action")
    print(f"  After 3 errors (streak threshold): trigger={trigger}")
    assert trigger == CheckpointTrigger.ERROR_RATE_SPIKE, "Should trigger error spike"

    return True


def test_serialization():
    """Test config round-trip serialization."""
    print("\n" + "=" * 60)
    print("TEST 4: Serialization Round-Trip")
    print("=" * 60)

    original = ChiefOfStaffConfig(
        autopilot=AutopilotConfig(default_budget=42.0),
        checkpoints=CheckpointConfig(error_streak=5),
    )

    # Serialize
    data = original.to_dict()
    print(f"  Serialized: autopilot.default_budget = {data['autopilot']['default_budget']}")

    # Deserialize
    restored = ChiefOfStaffConfig.from_dict(data)
    print(f"  Restored: autopilot.default_budget = {restored.autopilot.default_budget}")

    assert original.autopilot.default_budget == restored.autopilot.default_budget
    assert original.checkpoints.error_streak == restored.checkpoints.error_streak
    print("  Round-trip successful!")

    return True


def main():
    """Run all manual integration tests."""
    print("\n" + "=" * 60)
    print("CHIEF OF STAFF - MANUAL INTEGRATION TEST")
    print("=" * 60)

    tests = [
        ("Config Loading", test_config_loading),
        ("Backwards Compatibility", test_backwards_compatibility),
        ("Checkpoint System", test_checkpoint_system),
        ("Serialization", test_serialization),
    ]

    results = []
    for name, test_fn in tests:
        try:
            result = test_fn()
            results.append((name, "PASS" if result else "FAIL"))
        except Exception as e:
            print(f"\n  ERROR in {name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((name, f"ERROR: {e}"))

    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for name, status in results:
        icon = "[PASS]" if status == "PASS" else "[FAIL]"
        print(f"{icon} {name}: {status}")

    all_passed = all(s == "PASS" for _, s in results)
    print("\n" + ("ALL TESTS PASSED!" if all_passed else "SOME TESTS FAILED"))
    return all_passed


if __name__ == "__main__":
    import sys
    success = main()
    sys.exit(0 if success else 1)
