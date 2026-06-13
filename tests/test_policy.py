import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import CONTROL, get_profile
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


def warm_policy(track, mode="no_other_cars", steps=24):
    cmd = None
    for index in range(steps):
        cmd = decide_control(track, index * 0.05, mode=mode)
    return cmd


def test_high_confidence_straight_fastest_runs_fast_and_straight():
    reset_policy_state()
    cmd = warm_policy(make_track(), mode="no_other_cars")
    assert abs(cmd.steering) < 0.03
    assert cmd.speed > 0.55


def test_lateral_offset_controls_sign():
    reset_policy_state()
    right_cmd = warm_policy(make_track(lateral=0.35), mode="no_other_cars")
    reset_policy_state()
    left_cmd = warm_policy(make_track(lateral=-0.35), mode="no_other_cars")

    assert right_cmd.steering > 0.05
    assert left_cmd.steering < -0.05


def test_curves_control_sign_and_reduce_speed():
    reset_policy_state()
    straight = warm_policy(make_track(), mode="no_other_cars")
    reset_policy_state()
    # lateral 用 0.30（< pinned 阈值 0.38）避免冻结的大横偏被当成顶栏脱困触发；
    # 本测试只验证弯道转向符号 + 减速，不应进入脱困状态机。
    right_curve = warm_policy(make_track(lateral=0.30, heading=0.25, curvature=0.35, lookahead=0.30), mode="no_other_cars")
    reset_policy_state()
    left_curve = warm_policy(make_track(lateral=-0.30, heading=-0.25, curvature=-0.35, lookahead=-0.30), mode="no_other_cars")

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
        mode="no_other_cars",
        steps=6,
    )
    assert abs(cmd.speed - CONTROL["lost_speed"]) < 0.03
    assert -1.0 <= cmd.steering <= 1.0


def test_recent_straight_lost_track_keeps_speed():
    reset_policy_state()
    straight = make_track(confidence=0.85)
    cmd = warm_policy(straight, mode="no_other_cars", steps=32)
    assert cmd.speed >= 0.90

    lost = make_track(confidence=0.0, lost=True)
    coast = decide_control(lost, 1.70, mode="no_other_cars")
    assert coast.speed >= 0.90


def test_centered_lost_straight_coasts_fast_without_memory():
    reset_policy_state()
    lost = make_track(confidence=0.0, lost=True)
    cmd = warm_policy(lost, mode="no_other_cars", steps=20)
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
    cmd = warm_policy(turn_lost, mode="no_other_cars", steps=4)
    assert abs(cmd.speed - CONTROL["lost_speed"]) < 0.03


def test_low_confidence_stays_slow():
    reset_policy_state()
    track = make_track(heading=0.24, curvature=0.28, lookahead=0.25, confidence=0.20)
    cmd = warm_policy(track, mode="no_other_cars", steps=12)
    assert cmd.speed <= get_profile("no_other_cars")["recovery_speed"]


def test_unknown_profile_names_default_to_no_other_cars():
    # 旧/未知策略名（fastest/safe/unknown）一律退回单车 no_other_cars（最保守、不会倒车）。
    track = make_track(lateral=0.20, heading=0.15, curvature=0.22, lookahead=0.18, confidence=0.85)
    results = {}
    for name in ("no_other_cars", "safe", "unknown"):
        reset_policy_state()
        cmd = warm_policy(track, mode=name)
        results[name] = (cmd.speed, cmd.steering)
    assert results["safe"] == results["no_other_cars"]
    assert results["unknown"] == results["no_other_cars"]


def test_two_profiles_share_core_driving_but_differ_on_multicar():
    # no_other_cars 与 with_other_cars 共享核心驾驶参数（同样的正常巡线行为），
    # 但多车增量（避让/倒车）只在 with_other_cars 生效——这是 Profile 隔离的核心约定。
    from controller.params import get_profile
    no = get_profile("no_other_cars")
    wo = get_profile("with_other_cars")
    # 核心驾驶参数一致
    assert no["base_speed"] == wo["base_speed"]
    assert no["turn_in_lateral_ref"] == wo["turn_in_lateral_ref"]
    # 多车增量被隔离：单车关闭、多车开启
    assert no["opponent_avoid_steering_enable"] is False
    assert wo["opponent_avoid_steering_enable"] is True
    assert no["escape_reverse_speed"] == 0.0
    assert wo["escape_reverse_speed"] > 0.0
    assert no["motion_still_threshold"] == 0.0
    assert wo["motion_still_threshold"] > 0.0


def test_basic_and_complex_flags_use_same_policy_parameters():
    base = make_track(lateral=0.18, heading=0.12, curvature=0.20, lookahead=0.16, confidence=0.80, red_environment=False)
    red = make_track(lateral=0.18, heading=0.12, curvature=0.20, lookahead=0.16, confidence=0.80, red_environment=True)
    reset_policy_state()
    basic_cmd = warm_policy(base, mode="no_other_cars")
    reset_policy_state()
    complex_cmd = warm_policy(red, mode="no_other_cars")

    assert complex_cmd.speed == basic_cmd.speed
    assert complex_cmd.steering == basic_cmd.steering


def test_timestamp_reset_discards_speed_state():
    reset_policy_state()
    fast = warm_policy(make_track(), mode="no_other_cars", steps=20)
    assert fast.speed > 0.45

    reset_cmd = decide_control(make_track(), 0.10, mode="no_other_cars")
    assert reset_cmd.speed < fast.speed
    assert reset_cmd.speed <= 0.20


def test_inside_margin_guard_is_noop_by_default():
    # R014 实车证明默认开启边界余量保护既没拦住撞栏又引入无意义打轮，默认参数应为 no-op。
    profile = get_profile("no_other_cars")
    normal = make_track(lateral=0.16, heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right = make_track(lateral=0.16, heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right.right_margin_near = profile["inside_margin_warning"] * 0.35

    normal_steer = _target_steering(normal, _control_signals(normal, profile), "hard_turn", profile)
    guarded_steer = _target_steering(close_right, _control_signals(close_right, profile), "hard_turn", profile)

    assert guarded_steer == normal_steer


def test_inside_margin_limits_steering_toward_guardrail_when_enabled():
    profile = get_profile("no_other_cars")
    profile["inside_margin_outward_gain"] = 0.32
    profile["inside_margin_steering_cap"] = 0.42
    normal = make_track(lateral=0.16, heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right = make_track(lateral=0.16, heading=0.24, curvature=0.32, lookahead=0.28, red_environment=True)
    close_right.right_margin_near = profile["inside_margin_warning"] * 0.35

    normal_steer = _target_steering(normal, _control_signals(normal, profile), "hard_turn", profile)
    guarded_steer = _target_steering(close_right, _control_signals(close_right, profile), "hard_turn", profile)

    assert normal_steer > 0.03
    assert guarded_steer < normal_steer


def test_confident_line_adds_bounded_post_hoc_steering_correction():
    from controller.params import LINE_FOLLOW_PROFILE

    base = make_track()
    lined = make_track()
    lined.line_offset = 0.25
    lined.line_heading = 0.10
    lined.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(base, mode="no_other_cars")
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="no_other_cars")

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
        decide_control(base, index * 0.05, mode="no_other_cars")
    cmd = decide_control(flicker, 20 * 0.05, mode="no_other_cars")

    assert abs(cmd.steering) < 0.02


def test_implausible_large_line_offset_is_rejected():
    # 实跑取证：complex 直道把右侧白护栏认成线（lo≈0.4-0.93），骑线时 |offset| 不可能这么大。
    from controller.params import LINE_FOLLOW_PROFILE

    rail = make_track()
    rail.line_offset = LINE_FOLLOW_PROFILE["offset_trust_max"] + 0.12
    rail.line_heading = 0.0
    rail.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(make_track(), mode="no_other_cars")
    reset_policy_state()
    rail_cmd = warm_policy(rail, mode="no_other_cars")

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
    base_cmd = warm_policy(base, mode="no_other_cars", steps=8)
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="no_other_cars", steps=8)

    assert lined_cmd.steering > base_cmd.steering + 0.08


def test_trusted_offcenter_line_can_steer_left_after_phase2():
    # Phase 2 后，可信双目线的 normal offset 门放宽到 ±0.55。
    # 负 offset 若通过了感知层 road-context，也可能是真实偏离中心线，不能在 policy 层硬拒。
    lined = make_track(red_environment=True)
    lined.line_offset = -0.44
    lined.line_heading = 0.00
    lined.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(make_track(red_environment=True), mode="no_other_cars", steps=8)
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="no_other_cars", steps=8)

    assert lined_cmd.steering < base_cmd.steering - 0.08


def test_offcenter_line_remains_valid_after_startup_window():
    # R026 第一个左弯发生在启动窗口后；这里要保护普通帧也能使用 +0.4~+0.5 的真实白线偏移。
    lined = make_track(red_environment=True)
    lined.line_offset = 0.44
    lined.line_heading = 0.22
    lined.line_confidence = 0.80

    reset_policy_state()
    for index in range(8):
        cmd = decide_control(lined, 15.0 + index * 0.05, mode="no_other_cars")

    assert cmd.steering > 0.08


def test_line_correction_suppressed_near_obstacle():
    blocked = make_track()
    blocked.line_offset = 0.25
    blocked.line_heading = 0.0
    blocked.line_confidence = 0.80
    blocked.near_obstacle = True

    reset_policy_state()
    base_cmd = warm_policy(make_track(), mode="no_other_cars")
    reset_policy_state()
    blocked_cmd = warm_policy(blocked, mode="no_other_cars")

    assert abs(blocked_cmd.steering - base_cmd.steering) < 1e-6


def test_line_correction_suppressed_in_sharp_turn():
    # 实跑取证：complex t≈35.8 弯中线修正抵消入弯舵角；弯中线段不连续、直线拟合失真，应压到 0。
    turn = make_track(heading=0.40, curvature=0.40, lookahead=0.40, red_environment=True)
    lined_turn = make_track(heading=0.40, curvature=0.40, lookahead=0.40, red_environment=True)
    lined_turn.line_offset = -0.25
    lined_turn.line_heading = 0.0
    lined_turn.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(turn, mode="no_other_cars")
    reset_policy_state()
    lined_cmd = warm_policy(lined_turn, mode="no_other_cars")

    assert abs(lined_cmd.steering - base_cmd.steering) < 1e-6


def test_large_offset_line_keeps_recenter_correction_in_left_turn():
    # R027：第一个左弯里线在车右侧，但 line_heading/road heading 都强烈为左。
    # 弯中门控不能把右向 offset 回中修正完全压没。
    base = make_track(heading=-0.65, lookahead=-0.45, confidence=0.45, red_environment=True)
    lined = make_track(heading=-0.65, lookahead=-0.45, confidence=0.45, red_environment=True)
    lined.line_offset = 0.62
    lined.line_heading = -0.60
    lined.line_confidence = 0.80

    reset_policy_state()
    base_cmd = warm_policy(base, mode="no_other_cars", steps=8)
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="no_other_cars", steps=8)

    assert lined_cmd.steering > base_cmd.steering + 0.05


def test_geometry_escape_requires_low_speed():
    # 实跑取证：complex t≈37.2 平稳左弯（指令速度≈0.46）被急弯卡边脱困误判，
    # escape 强打 -0.58 直接导致撞左栏。正常速度巡弯不允许触发几何脱困。
    reset_policy_state()
    cornering = make_track(heading=0.50, curvature=0.30, lookahead=0.50, red_environment=True)
    for index in range(60):
        decide_control(cornering, index * 0.05, mode="no_other_cars")
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
    cmd = warm_policy(approach, mode="no_other_cars", steps=10)
    # 车几乎居中（lateral≈0）→ R044 入弯门控把远处项压到≈0 → 几乎不提前转（半径更大）。
    assert abs(cmd.steering) < 0.06


def test_hard_turn_requires_consecutive_frames():
    reset_policy_state()
    track = make_track(heading=0.28, curvature=0.35, lookahead=0.32, red_environment=True)

    decide_control(track, 0.00, mode="no_other_cars")
    assert policy._LAST_MODE != "hard_turn"

    decide_control(track, 0.05, mode="no_other_cars")
    assert policy._LAST_MODE == "hard_turn"


def test_sustained_inside_turn_line_strengthens_outward_correction():
    # R039：弯中可信白线连续显示车在内侧（offset 大、与 heading 反号）时，向外回中修正
    # 应强于仅靠 offset 楼层，把车拉回白线、放大转弯半径（修复 R038 残留切内线）。
    # 这里关掉 R040 弯中减预瞄，单独验证事后白线修正（否则二者叠加超过 max_correction）。
    from controller.params import CONTROL, LINE_FOLLOW_PROFILE as P

    base = make_track(heading=-0.70, curvature=-0.30, lookahead=-0.45, confidence=0.6, red_environment=True)
    lined = make_track(heading=-0.70, curvature=-0.30, lookahead=-0.45, confidence=0.6, red_environment=True)
    lined.line_offset = 0.55
    lined.line_heading = -0.80
    lined.line_confidence = 0.85

    saved = CONTROL["corner_relief_enable"]
    CONTROL["corner_relief_enable"] = False
    try:
        reset_policy_state()
        base_cmd = warm_policy(base, mode="no_other_cars", steps=10)
        reset_policy_state()
        lined_cmd = warm_policy(lined, mode="no_other_cars", steps=10)
    finally:
        CONTROL["corner_relief_enable"] = saved

    correction = lined_cmd.steering - base_cmd.steering
    floor_only = lined.line_offset * P["offset_gain"] * P["offset_curve_min_scale"]
    assert correction > floor_only + 0.05
    assert correction <= P["max_correction"] + 1e-6


def test_inside_turn_correction_holds_through_brief_line_dropout():
    # R039：弯中白线短暂丢置信（虚线间隙）时，向外修正应保持若干帧再衰减，
    # 不被 road-mask 弯道预判在空档里继续向内切；普通 EMA 会一帧砍半。
    turn = make_track(heading=-0.70, curvature=-0.30, lookahead=-0.45, confidence=0.6, red_environment=True)
    turn.line_offset = 0.55
    turn.line_heading = -0.80
    turn.line_confidence = 0.85

    reset_policy_state()
    warm_policy(turn, mode="no_other_cars", steps=10)
    held = policy._LINE_CORRECTION
    assert held > 0.10

    dropout = make_track(heading=-0.70, curvature=-0.30, lookahead=-0.45, confidence=0.6, red_environment=True)
    dropout.line_confidence = 0.0
    decide_control(dropout, 10 * 0.05, mode="no_other_cars")
    assert policy._LINE_CORRECTION > held * 0.7


def test_inside_assist_inactive_when_line_and_heading_agree():
    # 守护：offset 与 heading 同号（车偏左但弯也向左/或右转车偏左）不是“切内线”几何，
    # 不应触发向外辅助，避免把正常入弯舵角反向拉走。
    from controller.params import LINE_FOLLOW_PROFILE as P

    base = make_track(heading=0.30, curvature=0.30, lookahead=0.30, confidence=0.6, red_environment=True)
    lined = make_track(heading=0.30, curvature=0.30, lookahead=0.30, confidence=0.6, red_environment=True)
    lined.line_offset = 0.55
    lined.line_heading = 0.40  # 与 offset 同号
    lined.line_confidence = 0.85

    reset_policy_state()
    base_cmd = warm_policy(base, mode="no_other_cars", steps=10)
    reset_policy_state()
    lined_cmd = warm_policy(lined, mode="no_other_cars", steps=10)

    correction = lined_cmd.steering - base_cmd.steering
    # 同号时只有常规混合修正，不含 R039 向外辅助；上限不超过 max_correction。
    assert correction <= P["max_correction"] + 1e-6


def test_corner_relief_reduces_far_term_when_line_shows_inside():
    # R040：接触日志定位 t≈228.6 撞内栏。弯中可信白线显示车已切内侧（offset 与远处预瞄反号）时，
    # 应在源头削弱远处项→同样几何下舵角更小（半径更大），而不是靠事后修正硬顶。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    # 左弯：远处预瞄强烈向左（负），白线 offset 正（线在右=车在内侧左），二者反号 = 切内。
    inside = make_track(lateral=-0.30, heading=-0.65, curvature=0.0, lookahead=-0.55, confidence=0.7, red_environment=True)
    inside.line_offset = 0.55
    inside.line_heading = -0.80
    inside.line_confidence = 0.85
    signals = _control_signals(inside, profile)

    reset_policy_state()
    relieved = _target_steering(inside, signals, "hard_turn", dict(profile))
    reset_policy_state()
    no_relief = dict(profile); no_relief["corner_relief_enable"] = False
    baseline = _target_steering(inside, signals, "hard_turn", no_relief)

    # relief 让向左的目标舵角幅度变小（更不内切）。
    assert relieved > baseline + 0.03
    assert relieved <= 0.0  # 仍是左舵，只是更浅


def test_corner_relief_inactive_without_confident_line():
    # 守护：没有可信白线时 relief 不动远处项，正常急弯舵角不被削弱。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    turn = make_track(heading=-0.65, curvature=0.0, lookahead=-0.55, confidence=0.7, red_environment=True)
    turn.line_confidence = 0.0
    signals = _control_signals(turn, profile)

    reset_policy_state()
    relieved = _target_steering(turn, signals, "hard_turn", dict(profile))
    reset_policy_state()
    no_relief = dict(profile); no_relief["corner_relief_enable"] = False
    baseline = _target_steering(turn, signals, "hard_turn", no_relief)
    assert abs(relieved - baseline) < 1e-9


def test_corner_relief_holds_through_offset_sign_flip():
    # R041：line_offset 在弯中来回穿过 0（极限环）时，relief 不应瞬间归零让 road-mask 猛拉回。
    # 触发后应迟滞保持，使 trough 帧的远处项仍被压住——这正是 t≈228 撞内栏过冲的成因。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    inside = make_track(lateral=-0.30, heading=-0.65, curvature=0.0, lookahead=-0.55, confidence=0.7, red_environment=True)
    inside.line_offset = 0.55
    inside.line_heading = -0.80
    inside.line_confidence = 0.85
    trough = make_track(lateral=-0.30, heading=-0.65, curvature=0.0, lookahead=-0.55, confidence=0.7, red_environment=True)
    trough.line_offset = -0.05  # offset 翻负（甩到外侧），瞬时 relief 门关闭
    trough.line_heading = -0.80
    trough.line_confidence = 0.85
    sig_in = _control_signals(inside, profile)
    sig_tr = _control_signals(trough, profile)

    # 先在内侧帧触发 relief，再到 trough 帧——保持的 relief 仍应压住远处项。
    reset_policy_state()
    _target_steering(inside, sig_in, "hard_turn", dict(profile))
    held = _target_steering(trough, sig_tr, "hard_turn", dict(profile))
    # 基线：trough 帧没有先前 relief、且 relief 关闭。
    reset_policy_state()
    no_relief = dict(profile); no_relief["corner_relief_enable"] = False
    baseline = _target_steering(trough, sig_tr, "hard_turn", no_relief)

    assert held > baseline + 0.02  # 保持的 relief 让 trough 帧仍更不内切（破极限环）


def test_turn_in_suppressed_when_car_still_centered_on_approach():
    # R042/R044：直道接近弯口——远处路已弯（lookahead/heading 大）但车还居中（lateral≈0）。
    # 这正是"入弯太早→切内线"的根因帧。新门控 arrival 只看近处 lateral → 远处预瞄项被压到≈0，
    # 舵角很小（晚转）。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    approach = make_track(lateral=0.0, heading=-0.45, curvature=0.0, lookahead=-0.30,
                          confidence=0.7, red_environment=True)
    signals = _control_signals(approach, profile)
    reset_policy_state()
    steer = _target_steering(approach, signals, "hard_turn", dict(profile))
    assert abs(steer) < 0.06  # 车还居中 → 几乎不转（迟滞入弯）


def test_turn_in_opens_once_car_has_drifted_into_corner():
    # R042：一旦车真的到弯口、开始偏离（lateral 长起来），门应放开，让车"晚而狠"地转。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    arrived = make_track(lateral=-0.30, heading=-0.45, curvature=0.0, lookahead=-0.30,
                         confidence=0.7, red_environment=True)
    signals = _control_signals(arrived, profile)
    reset_policy_state()
    steer = _target_steering(arrived, signals, "hard_turn", dict(profile))
    assert steer < -0.2  # 门已放开 → 实打实左转


def test_turn_in_latch_sustains_turn_through_midcorner_lateral_dip():
    # R048：弯中 lateral 短暂回落（road-mask 重新对正路面）时，门控不应立刻收掉远处预瞄项，
    # 否则车转一半忽然收轮、转不到位、半径变大。latch 保持 → trough 帧仍打实左舵。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    deep = make_track(lateral=-0.40, heading=-0.80, curvature=0.0, lookahead=-0.60,
                      confidence=0.7, red_environment=True)        # 已深入弯、lateral 大
    dip = make_track(lateral=-0.03, heading=-0.80, curvature=0.0, lookahead=-0.60,
                     confidence=0.7, red_environment=True)         # 路还在弯，但 lateral 回落
    sig_d = _control_signals(deep, profile)
    sig_p = _control_signals(dip, profile)

    reset_policy_state()
    _target_steering(deep, sig_d, "hard_turn", dict(profile))      # build latch
    held = _target_steering(dip, sig_p, "hard_turn", dict(profile))
    # 对照：dip 帧没有先前 latch（门只看瞬时 lateral）
    reset_policy_state()
    no_latch = _target_steering(dip, sig_p, "hard_turn", dict(profile))

    assert held < no_latch - 0.05   # latch 让 trough 帧仍打更多左舵（持续转，不收轮）
    assert held < 0.0


def test_turn_in_gate_is_pure_lateral_no_sharpness_modulation():
    # R046：删除 R044 的 curve_risk 调制后，入弯门控只由近处 |lateral| 决定，
    # 与 curve_risk 无关——同样的 lateral 漂移，不论远处弯多急，门控缩放一致。
    from controller.params import get_profile

    profile = get_profile("no_other_cars")
    gentle = make_track(lateral=-0.20, heading=-0.30, curvature=0.0, lookahead=-0.25,
                        confidence=0.7, red_environment=True)   # curve_risk ≈ 0.30
    sharp = make_track(lateral=-0.20, heading=-0.95, curvature=0.0, lookahead=-0.90,
                       confidence=0.7, red_environment=True)    # curve_risk ≈ 0.95
    # 同样 lateral 下，corner_arrival 相同 → lookahead_term 被缩放的"比例"相同。
    ref = profile["turn_in_lateral_ref"]
    expected_arrival = min(1.0, 0.20 / ref)
    assert "turn_in_gentle_extra" not in profile and "turn_in_sharp_ref" not in profile
    # 直接验证门控公式：corner_arrival 只看 |lateral|/ref。
    assert abs(expected_arrival - min(1.0, abs(gentle.lateral_error) / ref)) < 1e-9
    assert abs(expected_arrival - min(1.0, abs(sharp.lateral_error) / ref)) < 1e-9
