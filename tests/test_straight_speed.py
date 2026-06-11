import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import get_profile
from controller.policy import _control_signals, _target_speed


def test_straight_line_boost_overrides_low_confidence_recovering_cap():
    # 直道（curve/offset 风险都低）但 mask 置信度偏低（会被判 recovering 限速）。
    # 直道提速应把速度抬到 straight_speed，而不是被 recovery_speed 压住。
    profile = get_profile("fastest")
    track = TrackState(
        lateral_error=0.0, heading_error=0.0, curvature=0.0, lookahead_error=0.0,
        confidence=0.15, lost=False, red_environment=True,
    )
    signals = _control_signals(track, profile)
    speed = _target_speed(track, signals, "recovering", 0.0, 5.0, profile)
    assert speed >= profile["straight_speed"] - 1e-6


def test_straight_boost_not_applied_in_corner():
    # 前方有弯（curve_risk 高）→ 不该提速。
    profile = get_profile("fastest")
    track = TrackState(
        lateral_error=0.05, heading_error=0.2, curvature=0.6, lookahead_error=0.4,
        confidence=0.7, lost=False, red_environment=True,
    )
    signals = _control_signals(track, profile)
    speed = _target_speed(track, signals, "hard_turn", 0.4, 5.0, profile)
    assert speed < profile["straight_speed"]


def test_lost_still_slow():
    # lost 帧仍走 lost_speed，不受直道提速影响（看不见就不能瞎快）。
    profile = get_profile("fastest")
    track = TrackState(0.0, 0.0, 0.0, 0.0, 0.05, True, True)
    signals = _control_signals(track, profile)
    speed = _target_speed(track, signals, "lost", 0.0, 5.0, profile)
    assert abs(speed - profile["lost_speed"]) < 1e-6
