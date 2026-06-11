import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import CONTROL
from controller.policy import decide_control, reset_policy_state


def _run_frozen(track: TrackState, frames: int = 80) -> float:
    """把同一个（冻结的）TrackState 连续喂给 policy，返回出现过的最大速度。"""

    reset_policy_state()
    max_speed = 0.0
    t = 0.0
    for _ in range(frames):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(track, t, mode="fastest")
        max_speed = max(max_speed, cmd.speed)
    return max_speed


def test_pinned_against_rail_triggers_escape_on_basic():
    # basic（red_environment=False）：顶住右栏（路在左 lateral<0）、几何冻结、速度落在 low_speed 覆盖空档。
    # 旧逻辑不会脱困；现在 pinned_stall 应触发，把速度顶到 escape_pinned_speed 推离栏杆。
    pinned = TrackState(
        lateral_error=-0.62,
        heading_error=0.14,
        curvature=0.09,
        lookahead_error=-0.52,
        confidence=0.83,
        lost=False,
        red_environment=False,
    )
    max_speed = _run_frozen(pinned, frames=80)
    assert max_speed >= CONTROL["escape_pinned_speed"] - 1e-6


def test_centered_frozen_view_does_not_force_pinned_escape():
    # 居中、几乎不打轮的冻结画面不应被当成顶栏杆。用低置信度把正常速度压在 recovery_speed
    # 之下，这样一旦 pinned 脱困误触发把速度顶到 0.62 就会暴露出来。
    centered = TrackState(
        lateral_error=0.0,
        heading_error=0.0,
        curvature=0.0,
        lookahead_error=0.0,
        confidence=0.15,
        lost=False,
        red_environment=False,
    )
    max_speed = _run_frozen(centered, frames=80)
    assert max_speed < CONTROL["escape_pinned_speed"] - 1e-6
