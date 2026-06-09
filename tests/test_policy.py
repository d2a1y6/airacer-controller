import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.policy import decide_control, reset_policy_state


def make_track(
    lateral=0.0,
    heading=0.0,
    curvature=0.0,
    lookahead=0.0,
    confidence=0.95,
    lost=False,
):
    return TrackState(lateral, heading, curvature, lookahead, confidence, lost)


def warm_policy(track, mode="fastest", steps=24):
    cmd = None
    for index in range(steps):
        cmd = decide_control(track, index * 0.05, mode=mode)
    return cmd


def test_high_confidence_straight_fastest_runs_fast_and_straight():
    reset_policy_state()
    cmd = warm_policy(make_track(), mode="fastest")
    assert abs(cmd.steering) < 0.03
    assert cmd.speed > 0.55


def test_lateral_offset_controls_sign():
    reset_policy_state()
    right_cmd = warm_policy(make_track(lateral=0.35), mode="fastest")
    reset_policy_state()
    left_cmd = warm_policy(make_track(lateral=-0.35), mode="fastest")

    assert right_cmd.steering > 0.05
    assert left_cmd.steering < -0.05


def test_curves_control_sign_and_reduce_speed():
    reset_policy_state()
    straight = warm_policy(make_track(), mode="fastest")
    reset_policy_state()
    right_curve = warm_policy(make_track(heading=0.25, curvature=0.35, lookahead=0.30), mode="fastest")
    reset_policy_state()
    left_curve = warm_policy(make_track(heading=-0.25, curvature=-0.35, lookahead=-0.30), mode="fastest")

    assert right_curve.steering > 0.05
    assert left_curve.steering < -0.05
    assert right_curve.speed < straight.speed
    assert left_curve.speed < straight.speed


def test_lost_track_uses_lost_speed():
    reset_policy_state()
    cmd = warm_policy(make_track(confidence=0.0, lost=True), mode="fastest", steps=6)
    assert abs(cmd.speed - 0.10) < 0.03
    assert -1.0 <= cmd.steering <= 1.0


def test_low_confidence_stays_slow():
    reset_policy_state()
    cmd = warm_policy(make_track(confidence=0.20), mode="fastest", steps=12)
    assert cmd.speed <= 0.26


def test_all_profile_names_use_same_control_parameters():
    track = make_track(lateral=0.20, heading=0.15, curvature=0.22, lookahead=0.18, confidence=0.85)
    reset_policy_state()
    fastest = warm_policy(track, mode="fastest")
    reset_policy_state()
    safe = warm_policy(track, mode="safe")
    reset_policy_state()
    unknown = warm_policy(track, mode="unknown")

    assert safe.speed == fastest.speed
    assert safe.steering == fastest.steering
    assert unknown.speed == fastest.speed
    assert unknown.steering == fastest.steering


def test_timestamp_reset_discards_speed_state():
    reset_policy_state()
    fast = warm_policy(make_track(), mode="fastest", steps=20)
    assert fast.speed > 0.45

    reset_cmd = decide_control(make_track(), 0.10, mode="fastest")
    assert reset_cmd.speed < fast.speed
    assert reset_cmd.speed <= 0.20
