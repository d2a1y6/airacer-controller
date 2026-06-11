import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import BASIC_CONTROL_OVERRIDES, get_profile
import controller.policy as policy
from controller.policy import _control_signals, _target_steering, decide_control, reset_policy_state


def make_track(
    lateral=0.0,
    heading=0.0,
    curvature=0.0,
    lookahead=0.0,
    confidence=0.95,
    lost=False,
    red_environment=False,
):
    return TrackState(lateral, heading, curvature, lookahead, confidence, lost, red_environment)


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
    cmd = warm_policy(
        make_track(
            lateral=0.22,
            heading=0.36,
            curvature=0.30,
            lookahead=0.22,
            confidence=0.0,
            lost=True,
        ),
        mode="fastest",
        steps=6,
    )
    assert abs(cmd.speed - BASIC_CONTROL_OVERRIDES["lost_speed"]) < 0.03
    assert -1.0 <= cmd.steering <= 1.0


def test_recent_straight_lost_track_keeps_speed():
    reset_policy_state()
    straight = make_track(confidence=0.85)
    cmd = warm_policy(straight, mode="fastest", steps=32)
    assert cmd.speed >= 0.90

    lost = make_track(confidence=0.0, lost=True)
    coast = decide_control(lost, 1.70, mode="fastest")
    assert coast.speed >= 0.90


def test_centered_lost_straight_coasts_fast_without_memory():
    reset_policy_state()
    lost = make_track(confidence=0.0, lost=True)
    cmd = warm_policy(lost, mode="fastest", steps=20)
    assert cmd.speed >= 0.90


def test_lost_corner_does_not_use_straight_coast():
    reset_policy_state()
    turn_lost = make_track(
        lateral=0.24,
        heading=0.34,
        curvature=0.30,
        lookahead=0.28,
        confidence=0.0,
        lost=True,
    )
    cmd = warm_policy(turn_lost, mode="fastest", steps=4)
    assert abs(cmd.speed - BASIC_CONTROL_OVERRIDES["lost_speed"]) < 0.03


def test_low_confidence_stays_slow():
    reset_policy_state()
    track = make_track(heading=0.24, curvature=0.28, lookahead=0.25, confidence=0.20)
    cmd = warm_policy(track, mode="fastest", steps=12)
    assert cmd.speed <= get_profile("fastest")["recovery_speed"]


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


def test_inside_margin_guard_is_noop_by_default():
    # R014 实车证明默认开启边界余量保护既没拦住撞栏又引入无意义打轮，默认参数应为 no-op。
    profile = get_profile("fastest")
    normal = make_track(heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right = make_track(heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right.right_margin_near = profile["inside_margin_warning"] * 0.35

    normal_steer = _target_steering(normal, _control_signals(normal, profile), "hard_turn", profile)
    guarded_steer = _target_steering(close_right, _control_signals(close_right, profile), "hard_turn", profile)

    assert guarded_steer == normal_steer


def test_inside_margin_limits_steering_toward_guardrail_when_enabled():
    profile = get_profile("fastest")
    profile["inside_margin_outward_gain"] = 0.32
    profile["inside_margin_steering_cap"] = 0.42
    normal = make_track(heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right = make_track(heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right.right_margin_near = profile["inside_margin_warning"] * 0.35

    normal_steer = _target_steering(normal, _control_signals(normal, profile), "hard_turn", profile)
    guarded_steer = _target_steering(close_right, _control_signals(close_right, profile), "hard_turn", profile)

    assert normal_steer > 0.05
    assert guarded_steer < normal_steer


def test_confident_line_adds_bounded_post_hoc_steering_correction():
    from controller.params import LINE_FOLLOW_PROFILE

    base = make_track()
    lined = make_track()
    lined.line_offset = 0.25
    lined.line_heading = 0.10
    lined.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(base, mode="fastest")
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="fastest")

    expected = (
        lined.line_offset * LINE_FOLLOW_PROFILE["offset_gain"]
        + lined.line_heading * LINE_FOLLOW_PROFILE["heading_gain"]
    )
    expected = min(expected, LINE_FOLLOW_PROFILE["max_correction"])
    # 修正只作用于最终舵角输出：速度与无白线时一致，持续可信白线下舵角差收敛到有界修正量。
    assert lined_cmd.speed == base_cmd.speed
    assert abs((lined_cmd.steering - base_cmd.steering) - expected) < 1e-3


def test_single_frame_line_detection_adds_no_correction():
    # 实跑取证：basic t≈140.9 单帧把白车/斑马线认成线（lo=+0.35）导致 +0.5 舵角突跳；
    # 修正必须连续 confirm_frames 帧有效才生效。
    reset_policy_state()
    base = make_track()
    flicker = make_track()
    flicker.line_offset = 0.25
    flicker.line_heading = 0.0
    flicker.line_confidence = 0.80

    for index in range(20):
        decide_control(base, index * 0.05, mode="fastest")
    cmd = decide_control(flicker, 20 * 0.05, mode="fastest")

    assert abs(cmd.steering) < 0.02


def test_implausible_large_line_offset_is_rejected():
    # 实跑取证：complex 直道把右侧白护栏认成线（lo≈0.4-0.93），骑线时 |offset| 不可能这么大。
    from controller.params import LINE_FOLLOW_PROFILE

    rail = make_track()
    rail.line_offset = LINE_FOLLOW_PROFILE["offset_trust_max"] + 0.12
    rail.line_heading = 0.0
    rail.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(make_track(), mode="fastest")
    reset_policy_state()
    rail_cmd = warm_policy(rail, mode="fastest")

    assert abs(rail_cmd.steering - base_cmd.steering) < 1e-6


def test_startup_line_acquisition_allows_right_side_line():
    # complex 发车时主 road mask 会把车右侧低饱和区域当路，几何中心贴左；
    # 白线在右侧且斜率合理时，开头短窗口应允许较大 offset 把车拉回中线。
    base = make_track(red_environment=True)
    lined = make_track(red_environment=True)
    lined.line_offset = 0.44
    lined.line_heading = 0.22
    lined.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(base, mode="fastest", steps=8)
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="fastest", steps=8)

    assert lined_cmd.steering > base_cmd.steering + 0.08


def test_startup_line_acquisition_rejects_left_side_line():
    # 开头误检常来自左侧护栏/边线，offset 为负；不能因此继续往左贴。
    rail = make_track(red_environment=True)
    rail.line_offset = -0.44
    rail.line_heading = 0.22
    rail.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(make_track(red_environment=True), mode="fastest", steps=8)
    reset_policy_state()
    rail_cmd = warm_policy(rail, mode="fastest", steps=8)

    assert abs(rail_cmd.steering - base_cmd.steering) < 1e-6


def test_startup_line_acquisition_expires():
    lined = make_track(red_environment=True)
    lined.line_offset = 0.44
    lined.line_heading = 0.22
    lined.line_confidence = 0.80

    reset_policy_state()
    for index in range(8):
        cmd = decide_control(lined, 15.0 + index * 0.05, mode="fastest")

    assert abs(cmd.steering) < 0.03


def test_line_correction_suppressed_near_obstacle():
    blocked = make_track()
    blocked.line_offset = 0.25
    blocked.line_heading = 0.0
    blocked.line_confidence = 0.80
    blocked.near_obstacle = True

    reset_policy_state()
    base_cmd = warm_policy(make_track(), mode="fastest")
    reset_policy_state()
    blocked_cmd = warm_policy(blocked, mode="fastest")

    assert abs(blocked_cmd.steering - base_cmd.steering) < 1e-6


def test_line_correction_suppressed_in_sharp_turn():
    # 实跑取证：complex t≈35.8 弯中线修正抵消入弯舵角；弯中线段不连续、直线拟合失真，应压到 0。
    turn = make_track(heading=0.40, curvature=0.40, lookahead=0.40, red_environment=True)
    lined_turn = make_track(heading=0.40, curvature=0.40, lookahead=0.40, red_environment=True)
    lined_turn.line_offset = -0.25
    lined_turn.line_heading = 0.0
    lined_turn.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(turn, mode="fastest")
    reset_policy_state()
    lined_cmd = warm_policy(lined_turn, mode="fastest")

    assert abs(lined_cmd.steering - base_cmd.steering) < 1e-6


def test_geometry_escape_requires_low_speed():
    # 实跑取证：complex t≈37.2 平稳左弯（指令速度≈0.46）被急弯卡边脱困误判，
    # escape 强打 -0.58 直接导致撞左栏。正常速度巡弯不允许触发几何脱困。
    reset_policy_state()
    cornering = make_track(heading=0.50, curvature=0.30, lookahead=0.50, red_environment=True)
    for index in range(60):
        decide_control(cornering, index * 0.05, mode="fastest")
        assert policy._LAST_MODE != "escaping"


def test_centered_complex_turn_in_keeps_wide_radius():
    # R021 后段入口：车身几乎居中，但远处右弯已经很明显。历史有效修法是收远处前瞻项，
    # 让车到弯里再转，避免提前切到内圈栏杆。
    reset_policy_state()
    approach = make_track(
        lateral=0.012,
        heading=0.244,
        curvature=0.252,
        lookahead=0.142,
        confidence=0.53,
        red_environment=True,
    )
    cmd = warm_policy(approach, mode="fastest", steps=10)
    assert 0.04 < cmd.steering < 0.18


def test_hard_turn_requires_consecutive_frames():
    reset_policy_state()
    track = make_track(heading=0.28, curvature=0.35, lookahead=0.32, red_environment=True)

    decide_control(track, 0.00, mode="fastest")
    assert policy._LAST_MODE != "hard_turn"

    decide_control(track, 0.05, mode="fastest")
    assert policy._LAST_MODE == "hard_turn"
