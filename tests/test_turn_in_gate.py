import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import get_profile
from controller.policy import _control_signals, _target_steering


def _steer(track, profile):
    signals = _control_signals(track, profile)
    return _target_steering(track, signals, "hard_turn", profile)


def test_turn_in_gate_reduces_steering_when_centered():
    # 远处有右弯，但车还居中、近处还直（lateral=heading=0）→ 入弯门控应压低提前打轮。
    track = TrackState(
        lateral_error=0.0, heading_error=0.0, curvature=0.6, lookahead_error=0.3,
        confidence=0.7, lost=False, red_environment=False,
    )
    profile = get_profile("fastest")
    no_gate = dict(profile)
    no_gate["turn_in_floor"] = 1.0  # 门控关闭（下限拉满）

    gated = _steer(track, profile)
    ungated = _steer(track, no_gate)
    assert abs(gated) < abs(ungated)


def test_turn_in_gate_fully_opens_when_corner_arrived():
    # 近处的路真的弯了（lateral/heading 大）→ corner_arrival≥1 → 门控全开，与不门控一致。
    track = TrackState(
        lateral_error=0.40, heading_error=0.30, curvature=0.6, lookahead_error=0.3,
        confidence=0.7, lost=False, red_environment=False,
    )
    profile = get_profile("fastest")
    no_gate = dict(profile)
    no_gate["turn_in_floor"] = 1.0

    gated = _steer(track, profile)
    ungated = _steer(track, no_gate)
    assert abs(gated - ungated) < 1e-6
