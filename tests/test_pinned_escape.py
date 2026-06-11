import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import BASIC_CONTROL_OVERRIDES, CONTROL
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


def test_pinned_left_margin_escapes_right_even_if_geometry_points_left():
    # 贴住左侧栏杆时，escape 不能继续按几何误差往左打；单侧余量说明左边已没有空间，应右打脱离。
    stuck_left = TrackState(
        lateral_error=-0.62,
        heading_error=-0.12,
        curvature=-0.12,
        lookahead_error=-0.52,
        confidence=0.82,
        lost=False,
        red_environment=False,
    )
    stuck_left.left_margin_near = 0.0
    stuck_left.right_margin_near = 0.34

    reset_policy_state()
    t = 0.0
    max_steer = 0.0
    for _ in range(80):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(stuck_left, t, mode="fastest")
        max_steer = max(max_steer, cmd.steering)

    assert max_steer >= BASIC_CONTROL_OVERRIDES["max_abs_steering"] - 1e-6


def test_pinned_right_margin_escapes_left_even_if_geometry_points_right():
    # 对称场景：右侧贴栏时应左打脱离，不能继续向右把车顶进栏杆。
    stuck_right = TrackState(
        lateral_error=0.62,
        heading_error=0.12,
        curvature=0.12,
        lookahead_error=0.52,
        confidence=0.82,
        lost=False,
        red_environment=False,
    )
    stuck_right.left_margin_near = 0.34
    stuck_right.right_margin_near = 0.0

    reset_policy_state()
    t = 0.0
    min_steer = 0.0
    for _ in range(80):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(stuck_right, t, mode="fastest")
        min_steer = min(min_steer, cmd.steering)

    assert min_steer <= -BASIC_CONTROL_OVERRIDES["max_abs_steering"] + 1e-6


def test_centered_frozen_view_does_not_force_pinned_escape():
    # 居中、几乎不打轮的冻结画面不应被当成顶栏杆。pinned 脱困若误触发会强制大转向
    # （escape_pinned_steering≈0.8），所以用"转向是否保持很小"判定，不用速度（直道提速也会抬速）。
    centered = TrackState(
        lateral_error=0.0,
        heading_error=0.0,
        curvature=0.0,
        lookahead_error=0.0,
        confidence=0.30,
        lost=False,
        red_environment=False,
    )
    reset_policy_state()
    t = 0.0
    max_steer = 0.0
    for _ in range(80):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(centered, t, mode="fastest")
        max_steer = max(max_steer, abs(cmd.steering))
    assert max_steer < 0.3


def test_boundary_obstacle_stall_escapes_toward_open_margin():
    # complex R017 末段：近处静态车 + 右侧余量为 0，实际车速近零，但指令速度仍略高于
    # low_speed 阈值。应按单侧余量更早脱困，并朝左侧开口打轮。
    stuck = TrackState(
        lateral_error=-0.23,
        heading_error=-0.30,
        curvature=1.0,
        lookahead_error=-0.18,
        confidence=0.46,
        lost=False,
        red_environment=True,
    )
    stuck.near_obstacle = True
    stuck.left_margin_near = 0.34
    stuck.right_margin_near = 0.0

    reset_policy_state()
    t = 0.0
    max_speed = 0.0
    min_steer = 0.0
    for _ in range(40):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(stuck, t, mode="fastest")
        max_speed = max(max_speed, cmd.speed)
        min_steer = min(min_steer, cmd.steering)

    assert max_speed >= CONTROL["escape_boundary_speed"] - 1e-6
    assert min_steer <= -0.70


def test_near_obstacle_with_normal_margins_does_not_boundary_escape():
    clear = TrackState(
        lateral_error=0.0,
        heading_error=0.08,
        curvature=0.10,
        lookahead_error=0.05,
        confidence=0.80,
        lost=False,
        red_environment=True,
    )
    clear.near_obstacle = True
    clear.left_margin_near = 0.34
    clear.right_margin_near = 0.34

    reset_policy_state()
    t = 0.0
    max_steer = 0.0
    for _ in range(40):
        t += CONTROL["nominal_dt"]
        cmd = decide_control(clear, t, mode="fastest")
        max_steer = max(max_steer, abs(cmd.steering))

    assert max_steer < 0.30
