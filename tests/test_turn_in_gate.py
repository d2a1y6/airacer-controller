import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import get_profile
from controller.policy import _control_signals, _target_steering, reset_policy_state


def _steer(track, profile):
    # 入弯门控现在带跨帧 latch（R048），这些单帧测试先清状态，保证每次独立。
    reset_policy_state()
    signals = _control_signals(track, profile)
    return _target_steering(track, signals, "hard_turn", profile)


def test_turn_in_gate_reduces_steering_when_centered():
    # 远处有右弯，但车还居中、近处还直（lateral=heading=0）→ 入弯门控应压低提前打轮。
    track = TrackState(
        lateral_error=0.0, heading_error=0.0, curvature=0.6, lookahead_error=0.3,
        confidence=0.7, lost=False, red_environment=False,
    )
    profile = get_profile("no_other_cars")

    gated = _steer(track, profile)
    assert abs(gated) < 0.02


def test_turn_in_gate_fully_opens_when_corner_arrived():
    # 近处的路真的弯了（lateral 大）→ corner_arrival≥1 → 远处预瞄项明显放开。
    track = TrackState(
        lateral_error=0.40, heading_error=0.30, curvature=0.6, lookahead_error=0.3,
        confidence=0.7, lost=False, red_environment=False,
    )
    profile = get_profile("no_other_cars")

    arrived = _steer(track, profile)
    centered = _steer(
        TrackState(
            lateral_error=0.0, heading_error=0.0, curvature=0.6, lookahead_error=0.3,
            confidence=0.7, lost=False, red_environment=False,
        ),
        profile,
    )
    assert abs(arrived) > abs(centered) * 10.0
