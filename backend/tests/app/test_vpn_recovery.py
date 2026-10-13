import importlib.util
from pathlib import Path

MODULE = Path(__file__).resolve().parents[3] / "scripts/tooling/recover_gasbuddy_vpn.py"
spec = importlib.util.spec_from_file_location("vpn_recovery", MODULE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


def test_healthy_vpn_never_switches_or_accumulates_failures():
    state, switch = recovery.decide({"failures": 5, "attempts": 3}, "healthy", 0, 10000)
    assert not switch
    assert state["failures"] == state["attempts"] == 0


def test_startup_grace_and_three_sustained_failures():
    state, switch = recovery.decide({}, "starting", 9990, 10000)
    assert not switch and state["failures"] == 0
    for n in range(3):
        state, switch = recovery.decide(state, "unhealthy", 0, 10000+n*60)
        assert switch == (n == 2)


def test_recovery_cooldown_and_repeated_failure_backoff():
    state = {"failures": 4, "last_attempt": 10000, "attempts": 1}
    assert not recovery.decide(state, "unhealthy", 0, 11000)[1]
    assert recovery.decide(state, "unhealthy", 0, 11800)[1]
    state["attempts"] = 3
    assert not recovery.decide(state, "unhealthy", 0, 11800)[1]
    assert recovery.decide(state, "unhealthy", 0, 17200)[1]
