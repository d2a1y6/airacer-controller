"""控制策略模块。

功能概述：根据赛道状态统一规划转向和速度。
输入输出：输入 `TrackState`、时间戳和 fastest/safe 模式，输出 `ControlCmd`。
处理流程：计算风险分量，选择驾驶状态，生成目标转向和速度，再做平滑与变化率限制。
"""

import math

from controller.common import ControlCmd, TrackState, clamp
from controller.params import BASIC_CONTROL_OVERRIDES, LINE_FOLLOW_PROFILE, get_profile

_LAST_STEERING = 0.0
_LAST_SPEED = 0.0
_LAST_TIMESTAMP = None
_LOST_FRAMES = 0
_RECOVERY_FRAMES = 0
_LAST_GOOD_BIAS = 0.0
_LAST_MODE = "start"
_STALL_FRAMES = 0
_ESCAPE_FRAMES = 0
_ESCAPE_STEERING_SIGN = 1.0
_ESCAPE_STEERING_MAGNITUDE = 0.0
_ESCAPE_SPEED = 0.0
_LAST_TRACK_SIGNATURE = None
_STRAIGHT_MEMORY_FRAMES = 0
_HARD_TURN_CANDIDATE_FRAMES = 0
_RECOVERY_CANDIDATE_FRAMES = 0
_LAST_MODE_REASON = "start"
_LAST_TARGET_STEERING = 0.0
_LAST_TARGET_SPEED = 0.0
_LAST_SIGNALS = {}
_LAST_STRAIGHT_MEMORY_ACTIVE = False
_LINE_STREAK = 0
_LINE_LAST_OFFSET = 0.0
_LINE_CORRECTION = 0.0


def reset_policy_state() -> None:
    """重置策略跨帧状态。

    功能：清空上一帧转向、速度、时间戳和恢复计数。
    参数：无。
    返回：无。
    逻辑：测试或新仿真开始前调用，避免继承旧平滑状态。
    """

    global _LAST_STEERING, _LAST_SPEED, _LAST_TIMESTAMP
    global _LOST_FRAMES, _RECOVERY_FRAMES, _LAST_GOOD_BIAS, _LAST_MODE
    global _STALL_FRAMES, _ESCAPE_FRAMES, _ESCAPE_STEERING_SIGN, _ESCAPE_STEERING_MAGNITUDE, _ESCAPE_SPEED
    global _LAST_TRACK_SIGNATURE, _STRAIGHT_MEMORY_FRAMES
    global _HARD_TURN_CANDIDATE_FRAMES, _RECOVERY_CANDIDATE_FRAMES
    global _LAST_MODE_REASON, _LAST_TARGET_STEERING, _LAST_TARGET_SPEED, _LAST_SIGNALS, _LAST_STRAIGHT_MEMORY_ACTIVE
    global _LINE_STREAK, _LINE_LAST_OFFSET, _LINE_CORRECTION
    _LINE_STREAK = 0
    _LINE_LAST_OFFSET = 0.0
    _LINE_CORRECTION = 0.0
    _LAST_STEERING = 0.0
    _LAST_SPEED = 0.0
    _LAST_TIMESTAMP = None
    _LOST_FRAMES = 0
    _RECOVERY_FRAMES = 0
    _LAST_GOOD_BIAS = 0.0
    _LAST_MODE = "start"
    _STALL_FRAMES = 0
    _ESCAPE_FRAMES = 0
    _ESCAPE_STEERING_SIGN = 1.0
    _ESCAPE_STEERING_MAGNITUDE = 0.0
    _ESCAPE_SPEED = 0.0
    _LAST_TRACK_SIGNATURE = None
    _STRAIGHT_MEMORY_FRAMES = 0
    _HARD_TURN_CANDIDATE_FRAMES = 0
    _RECOVERY_CANDIDATE_FRAMES = 0
    _LAST_MODE_REASON = "start"
    _LAST_TARGET_STEERING = 0.0
    _LAST_TARGET_SPEED = 0.0
    _LAST_SIGNALS = {}
    _LAST_STRAIGHT_MEMORY_ACTIVE = False


def _maybe_reset_policy_by_timestamp(timestamp: float, profile: dict) -> None:
    """根据时间戳判断是否重置策略状态。"""

    if _LAST_TIMESTAMP is None:
        return
    elapsed = float(timestamp) - float(_LAST_TIMESTAMP)
    if elapsed < 0.0 or elapsed > profile["timestamp_reset_gap"]:
        reset_policy_state()


def _dt(timestamp: float, profile: dict) -> float:
    """计算本帧控制间隔，首帧使用 nominal_dt。"""

    if _LAST_TIMESTAMP is None:
        return profile["nominal_dt"]
    return max(float(timestamp) - float(_LAST_TIMESTAMP), profile["nominal_dt"])


def _signed_power(value: float, power: float) -> float:
    """保留符号的幂函数。"""

    return math.copysign(abs(value) ** power, value)


def _road_direction_sign(track: TrackState) -> float:
    """估计应朝哪一侧打轮才能回到路面（左负右正）。

    功能：为脱困提供"路在哪边"的方向，而不是写死方向或盲目反打上一帧。
    参数：`track` 是当前赛道状态。
    返回：`+1.0`（向右回到路面）或 `-1.0`（向左回到路面）。
    逻辑：优先用当前横向误差；贴墙丢线时退回最近一次可信偏置；都不可用时反打上一帧舵角脱离。
    """

    reference = track.lateral_error
    if abs(reference) <= 0.05:
        reference = _LAST_GOOD_BIAS
    if abs(reference) <= 1e-3:
        reference = -_LAST_STEERING
    if abs(reference) <= 1e-6:
        return 1.0
    return math.copysign(1.0, reference)


def _margin_escape_sign(track: TrackState, fallback: float) -> float:
    """根据单侧边界余量选择脱困方向。

    功能：在近障碍或贴栏卡死时，优先往余量更大的方向打轮。
    参数：`track` 提供左右近处余量，`fallback` 是几何偏置推断出的方向。
    返回：`+1.0` 表示右打，`-1.0` 表示左打。
    逻辑：只有左右余量差足够明显时才覆盖几何方向，避免噪声边界点造成反复换向。
    """

    margin_gap = abs(track.left_margin_near - track.right_margin_near)
    if margin_gap <= 0.08:
        return fallback
    if track.left_margin_near < track.right_margin_near:
        return 1.0
    return -1.0


def _control_signals(track: TrackState, profile: dict) -> dict:
    """计算策略使用的风险分量。

    功能：拆分弯道、偏移、置信度和丢线风险。
    参数：`track` 是赛道状态，`profile` 是控制参数。
    返回：包含各类风险和综合风险的字典。
    逻辑：速度和模式选择共享这些风险，避免重复估算。
    """

    curve_risk = clamp(max(abs(track.curvature), abs(track.heading_error), abs(track.lookahead_error)), 0.0, 1.0)
    offset_risk = clamp(abs(track.lateral_error), 0.0, 1.0)
    confidence_risk = clamp(1.0 - track.confidence, 0.0, 1.0)
    lost_risk = 1.0 if track.lost else 0.0
    min_margin = min(clamp(track.left_margin_near, 0.0, 1.0), clamp(track.right_margin_near, 0.0, 1.0))
    margin_risk = clamp((profile["inside_margin_warning"] - min_margin) / profile["inside_margin_warning"], 0.0, 1.0)
    turn_demand = clamp(curve_risk * 0.55 + offset_risk * 0.45, 0.0, 1.0)
    risk = clamp(
        curve_risk * profile["risk_curve_weight"]
        + offset_risk * profile["risk_offset_weight"]
        + confidence_risk * profile["risk_confidence_weight"]
        + lost_risk * profile["risk_lost_weight"],
        0.0,
        1.0,
    )
    return {
        "curve_risk": curve_risk,
        "offset_risk": offset_risk,
        "confidence_risk": confidence_risk,
        "lost_risk": lost_risk,
        "margin_risk": margin_risk,
        "turn_demand": turn_demand,
        "risk": risk,
    }


def _is_straight_candidate(track: TrackState, signals: dict, profile: dict) -> bool:
    """判断当前几何是否足够像直道。

    功能：给直道提速和 lost 惯性滑行提供稳定判据。
    参数：`track` 是赛道状态，`signals` 是风险分量，`profile` 是控制参数。
    返回：当前非丢线帧是否可以视为直道。
    逻辑：主要看曲率、前瞻和横向偏移；heading 只做宽松兜底，避免噪声把直道判坏。
    """

    if track.lost or track.confidence < profile["lost_confidence"]:
        return False
    stable_curve = max(abs(track.curvature), abs(track.lookahead_error)) <= profile["straight_curve_max"]
    centered = signals["offset_risk"] <= profile["straight_offset_max"]
    heading_ok = abs(track.heading_error) <= profile["straight_heading_max"]
    return stable_curve and centered and heading_ok


def _is_lost_straight_coast_candidate(track: TrackState, signals: dict, profile: dict) -> bool:
    """判断丢线帧是否仍可按直道惯性滑行。

    功能：处理蓝门/天空造成的无观测帧，避免直道速度掉回 0.24。
    参数：`track` 是已衰减的丢线状态，`signals` 是风险分量，`profile` 是控制参数。
    返回：当前 lost 帧是否可安全维持直道速度。
    逻辑：只接受居中、曲率/前瞻低、heading 不大且上一帧舵角很小的 lost 帧。
    """

    if not track.lost:
        return False
    stable_curve = max(abs(track.curvature), abs(track.lookahead_error)) <= profile["straight_curve_max"]
    centered = signals["offset_risk"] <= profile["straight_offset_max"]
    heading_ok = abs(track.heading_error) <= profile["straight_heading_max"]
    steering_ok = abs(_LAST_STEERING) <= profile["straight_lost_steering_max"]
    return stable_curve and centered and heading_ok and steering_ok


def _update_straight_memory(track: TrackState, signals: dict, mode: str, profile: dict) -> bool:
    """更新直道记忆并返回本帧是否允许直道滑行。

    功能：让蓝门/天空造成的短暂 lost 不再立刻砸到 `lost_speed`。
    参数：当前赛道状态、风险信号、驾驶状态和参数表。
    返回：是否仍处在最近确认过的直道窗口内。
    逻辑：非 lost 直道帧刷新记忆；lost 帧可消耗记忆，或在几何和上一帧舵角都很直时直接滑行。
    """

    global _STRAIGHT_MEMORY_FRAMES

    if _is_straight_candidate(track, signals, profile):
        _STRAIGHT_MEMORY_FRAMES = int(profile["straight_memory_frames"])
        return True
    if _STRAIGHT_MEMORY_FRAMES > 0 and mode == "lost":
        _STRAIGHT_MEMORY_FRAMES -= 1
        return True
    if _is_lost_straight_coast_candidate(track, signals, profile):
        return True
    _STRAIGHT_MEMORY_FRAMES = 0
    return False


def _select_mode(track: TrackState, signals: dict, timestamp: float, profile: dict) -> str:
    """选择内部驾驶状态。

    功能：在 lost、recovering、hard_turn、correcting、cruise 之间切换。
    参数：`track` 是赛道状态，`signals` 是风险分量，`timestamp` 是平台时间。
    返回：内部状态名。
    逻辑：丢线优先，其次恢复缓冲、急弯、回中和巡航。
    """

    global _HARD_TURN_CANDIDATE_FRAMES, _RECOVERY_CANDIDATE_FRAMES, _LAST_MODE_REASON

    del timestamp
    if track.lost or track.confidence < profile["lost_confidence"]:
        _HARD_TURN_CANDIDATE_FRAMES = 0
        _RECOVERY_CANDIDATE_FRAMES = 0
        _LAST_MODE_REASON = "lost_or_low_confidence"
        return "lost"
    if _RECOVERY_FRAMES > 0 or track.confidence < profile["recovery_confidence"]:
        _RECOVERY_CANDIDATE_FRAMES += 1
        _HARD_TURN_CANDIDATE_FRAMES = 0
        if _RECOVERY_FRAMES > 0 or _RECOVERY_CANDIDATE_FRAMES >= int(profile["recovery_enter_frames"]):
            _LAST_MODE_REASON = "recovery_buffer_or_confidence"
            return "recovering"
    else:
        _RECOVERY_CANDIDATE_FRAMES = 0

    hard_turn_candidate = (
        signals["curve_risk"] > profile["hard_turn_threshold"]
        or signals["turn_demand"] > profile["hard_turn_threshold"]
    )
    hard_turn_hold = _LAST_MODE == "hard_turn" and (
        signals["curve_risk"] > profile["hard_turn_exit_threshold"]
        or signals["turn_demand"] > profile["hard_turn_exit_threshold"]
    )
    if hard_turn_candidate or hard_turn_hold:
        _HARD_TURN_CANDIDATE_FRAMES += 1
    else:
        _HARD_TURN_CANDIDATE_FRAMES = 0
    if hard_turn_hold or _HARD_TURN_CANDIDATE_FRAMES >= int(profile["hard_turn_enter_frames"]):
        _LAST_MODE_REASON = "curve_or_turn_demand"
        return "hard_turn"
    if abs(track.lateral_error) > profile["correction_error"]:
        _LAST_MODE_REASON = "lateral_error"
        return "correcting"
    _LAST_MODE_REASON = "nominal"
    return "cruise"


def _apply_inside_margin_guard(raw: float, track: TrackState, profile: dict) -> float:
    """根据近处边界余量限制继续向内打轮。

    功能：弯中贴近内侧护栏时，把目标舵角往外侧推。
    参数：`raw` 是未限幅目标舵角，`track` 提供左右边界余量。
    返回：保护后的目标舵角。
    逻辑：只在舵角方向指向低余量一侧时生效，避免直道无端左右摆。
    """

    warning = max(float(profile["inside_margin_warning"]), 1e-6)
    if raw > 0.0:
        pressure = clamp((warning - track.right_margin_near) / warning, 0.0, 1.0)
        if pressure <= 0.0:
            return raw
        capped = min(raw, profile["inside_margin_steering_cap"])
        return capped - pressure * profile["inside_margin_outward_gain"]
    if raw < 0.0:
        pressure = clamp((warning - track.left_margin_near) / warning, 0.0, 1.0)
        if pressure <= 0.0:
            return raw
        capped = max(raw, -profile["inside_margin_steering_cap"])
        return capped + pressure * profile["inside_margin_outward_gain"]
    return raw


def _target_steering(track: TrackState, signals: dict, mode: str, profile: dict) -> float:
    """计算目标转向。

    功能：把回中项和前瞻项分开组合，并按状态修正。
    参数：`track` 是赛道状态，`signals` 是风险分量，`mode` 是内部驾驶状态。
    返回：裁剪到 `[-1, 1]` 的目标转向。
    逻辑：偏移大时更看近处，弯道明显时更看前方；两者冲突时优先回中。
    """

    center_term = track.lateral_error * profile["gain_lateral"]
    lookahead_term = (
        track.lookahead_error * profile["gain_lookahead"]
        + track.heading_error * profile["gain_heading"]
        + track.curvature * profile["gain_curve"]
    )
    # 入弯时机门控：直道上车还居中、近处还直时（lateral/heading≈0），远处的路已弯会让前瞻项
    # 提前打轮→切内线贴栏杆。用近处弯量衡量"弯到了没"，弯没到就压制前瞻项，弯真正到了再放开，
    # 让车跟着中心线、到弯了再转。带保守下限，避免压过头变成转太晚冲外侧。
    corner_arrival = clamp(
        abs(track.lateral_error) / profile["turn_in_lateral_ref"]
        + abs(track.heading_error) / profile["turn_in_heading_ref"],
        0.0,
        1.0,
    )
    turn_in_gate = profile["turn_in_floor"] + (1.0 - profile["turn_in_floor"]) * corner_arrival
    lookahead_term *= turn_in_gate
    near_weight = profile["near_weight_base"] + signals["offset_risk"] * profile["near_weight_offset_boost"]
    far_weight = profile["far_weight_base"] + signals["curve_risk"] * profile["far_weight_curve_boost"]
    if center_term * lookahead_term < 0.0:
        conflict_offset = max(0.0, signals["offset_risk"] - profile["far_conflict_offset_start"])
        far_weight *= max(
            profile["far_conflict_min_scale"],
            1.0 - conflict_offset * profile["far_conflict_offset_scale"],
        )

    raw = near_weight * center_term + far_weight * lookahead_term
    raw += profile["gain_lateral_nonlinear"] * _signed_power(track.lateral_error, 1.7)
    raw += profile["gain_curve_nonlinear"] * _signed_power(track.curvature, 1.5)

    if mode == "lost":
        # 不再死保上一帧舵角（贴墙时那正是把车怼进墙的舵），向最近可信道路方向
        # 偏置靠拢并整体衰减，让车松开栏杆等感知恢复，真正的反向由脱困状态机负责。
        raw = 0.50 * _LAST_STEERING + 0.20 * _LAST_GOOD_BIAS
    elif mode == "recovering":
        raw *= 0.70
    elif mode == "correcting":
        raw += track.lateral_error * 0.25
    elif mode == "hard_turn":
        raw *= profile["hard_turn_steering_scale"]

    if (
        track.red_environment
        and
        track.lateral_error > profile["inside_left_lateral_min"]
        and track.heading_error < profile["inside_left_heading_max"]
        and track.curvature < profile["inside_left_curvature_max"]
    ):
        raw = max(raw, profile["inside_left_steering_limit"])

    raw = _apply_inside_margin_guard(raw, track, profile)

    if abs(raw) < profile["steering_deadzone"]:
        raw = 0.0
    max_abs = profile["max_abs_steering"]
    return clamp(raw, -max_abs, max_abs)


def _steering_smoothing_for_mode(mode: str, profile: dict) -> float:
    """读取当前驾驶状态对应的转向平滑系数。"""

    if mode == "cruise":
        return profile["steering_smoothing_cruise"]
    if mode == "hard_turn":
        return profile["steering_smoothing_turn"]
    if mode == "correcting":
        return profile["steering_smoothing_correction"]
    return profile["steering_smoothing_recovery"]


def _smooth_steering(target: float, mode: str, timestamp: float, profile: dict) -> float:
    """平滑转向并限制变化率。

    功能：按驾驶状态和速度限制方向盘跳变。
    参数：`target` 是目标转向，`mode` 是内部状态，`timestamp` 是平台时间。
    返回：平滑后的转向值。
    逻辑：高速时限制更强，恢复状态更平滑。
    """

    alpha = _steering_smoothing_for_mode(mode, profile)
    smoothed = _LAST_STEERING * alpha + target * (1.0 - alpha)
    dt_factor = max(1.0, _dt(timestamp, profile) / profile["nominal_dt"])
    speed_norm = clamp(_LAST_SPEED / max(profile["max_speed"], 1e-6), 0.0, 1.0)
    speed_factor = 1.0 - 0.35 * speed_norm
    max_delta = profile["max_steering_delta"] * dt_factor * speed_factor
    delta = clamp(smoothed - _LAST_STEERING, -max_delta, max_delta)
    # 速度相关的转向幅值上限：高速时收舵，避免同样舵角在高速下半径过小切内线。
    max_abs = profile["max_abs_steering"] * (1.0 - profile["steering_speed_cap_scale"] * speed_norm)
    return clamp(_LAST_STEERING + delta, -max_abs, max_abs)


def _target_speed(
    track: TrackState,
    signals: dict,
    mode: str,
    steering: float,
    timestamp: float,
    profile: dict,
    straight_memory_active: bool = False,
) -> float:
    """计算目标速度。

    功能：用乘法降速组合弯道、偏移、置信度和转向风险。
    参数：`track` 是赛道状态，`signals` 是风险分量，`mode` 是内部状态，`steering` 是当前转向；
        `straight_memory_active` 表示最近刚确认过直道。
    返回：目标速度比例。
    逻辑：模式只限制速度上限，正常速度由风险因子相乘得到。
    """

    if mode == "lost":
        if straight_memory_active:
            return profile["straight_lost_speed"]
        return profile["lost_speed"]

    curve_factor = 1.0 - profile["curve_slowdown"] * (signals["curve_risk"] ** profile["curve_power"])
    offset_factor = 1.0 - profile["offset_slowdown"] * (signals["offset_risk"] ** profile["offset_power"])
    confidence_factor = profile["min_confidence_factor"] + (1.0 - profile["min_confidence_factor"]) * track.confidence
    steering_factor = 1.0 - profile["steering_slowdown"] * (abs(steering) ** profile["steering_power"])
    margin_factor = 1.0 - profile["inside_margin_slowdown"] * signals["margin_risk"]
    target = profile["base_speed"] * curve_factor * offset_factor * confidence_factor * steering_factor * margin_factor

    if mode == "recovering":
        target = min(target, profile["recovery_speed"])
    elif mode == "hard_turn":
        centered_bonus = (
            profile["hard_turn_center_speed_bonus"]
            * (1.0 - signals["offset_risk"])
            * track.confidence
        )
        target = min(target, profile["hard_turn_speed"] + centered_bonus)
    elif mode == "correcting":
        target = min(target, profile["correction_speed"])
    # 直道提速：几何明确为直时，速度不该被偏低的 mask 置信度或 recovering 限速压住。
    # 判断主要看 curvature/lookahead/offset，heading 只做宽松兜底，避免噪声挡住直道加速。
    straight = straight_memory_active or _is_straight_candidate(track, signals, profile)
    if straight:
        target = max(target, profile["straight_speed"])
    if timestamp < profile["start_caution_seconds"]:
        target = min(target, profile["start_speed"])
    return clamp(target, profile["min_speed"], profile["max_speed"])


def _smooth_speed(target: float, timestamp: float, profile: dict) -> float:
    """平滑速度并限制加减速。

    功能：让加速慢、减速快，减少速度跳变。
    参数：`target` 是目标速度，`timestamp` 是平台时间，`profile` 是控制参数。
    返回：平滑后的速度比例。
    逻辑：上升和下降使用不同变化率，入弯能更快降速。
    """

    dt = _dt(timestamp, profile)
    delta = target - _LAST_SPEED
    if delta >= 0.0:
        delta = min(delta, profile["max_speed_increase_per_sec"] * dt)
    else:
        delta = max(delta, -profile["max_speed_decrease_per_sec"] * dt)
    return clamp(_LAST_SPEED + delta, min(profile["min_speed"], target), profile["max_speed"])


def _track_signature(track: TrackState) -> tuple[float, float, float, float, float]:
    """提取用于判断画面是否停滞的几何签名。"""

    return (
        track.lateral_error,
        track.heading_error,
        track.curvature,
        track.lookahead_error,
        track.confidence,
    )


def _escape_if_stalled(
    track: TrackState,
    signals: dict,
    steering: float,
    speed: float,
    mode: str,
    profile: dict,
    allow_geometry_escape: bool,
) -> tuple[float, float, str]:
    """在顶住边界时短暂脱困。

    功能：检测急弯大转向卡边，或长时间低速且几何签名几乎不变的状态。
    参数：当前赛道状态、风险信号、已平滑的转向和速度、内部模式、参数表，
        `allow_geometry_escape` 控制是否启用依赖可靠几何的急弯/大偏移脱困（仅 complex）。
    返回：可能被覆盖后的 `(steering, speed, mode)`。
    逻辑：脱困方向统一朝感知到的路面一侧（远离顶住的栏杆），不再写死方向或盲目反打；
        低速贴墙本就是低置信状态，所以低速脱困放宽置信度门槛，basic 也启用。
    """

    global _STALL_FRAMES, _ESCAPE_FRAMES, _ESCAPE_STEERING_SIGN, _ESCAPE_STEERING_MAGNITUDE, _ESCAPE_SPEED
    global _LAST_TRACK_SIGNATURE

    signature = _track_signature(track)
    if _LAST_TRACK_SIGNATURE is None:
        signature_delta = 1.0
    else:
        signature_delta = sum(abs(a - b) for a, b in zip(signature, _LAST_TRACK_SIGNATURE))
    _LAST_TRACK_SIGNATURE = signature

    if _ESCAPE_FRAMES > 0:
        _ESCAPE_FRAMES -= 1
        escape_steering = _ESCAPE_STEERING_SIGN * _ESCAPE_STEERING_MAGNITUDE
        max_abs = profile["max_abs_steering"]
        return (
            clamp(escape_steering, -max_abs, max_abs),
            max(speed, _ESCAPE_SPEED),
            "escaping",
        )

    high_turn = (
        signals["curve_risk"] >= profile["escape_curve_threshold"]
        or abs(steering) >= profile["escape_steering_threshold"]
    )
    aligned_offset = (
        signals["offset_risk"] >= profile["escape_offset_threshold"]
        and track.lateral_error * track.lookahead_error >= profile["escape_offset_lookahead_alignment"]
    )
    large_offset_stall = (
        allow_geometry_escape
        and mode in {"hard_turn", "correcting"}
        and signals["offset_risk"] >= profile["escape_offset_threshold"]
        and speed <= profile["escape_offset_speed_threshold"]
        and abs(track.heading_error) <= profile["escape_offset_heading_abs_max"]
        and abs(track.curvature) <= profile["escape_offset_curve_abs_max"]
        and track.lateral_error * track.lookahead_error >= profile["escape_offset_lookahead_alignment"]
    )
    low_speed_stall = speed <= profile["escape_low_speed_threshold"]
    # 顶住栏杆但速度还没塌到低速阈值（落在 low_speed 覆盖空档）：几何冻结 + 大偏移 + 大反向打轮。
    pinned_stall = (
        abs(track.lateral_error) >= profile["escape_pinned_lateral_min"]
        and abs(steering) >= profile["escape_pinned_steering_min"]
        and speed <= profile["escape_pinned_speed_max"]
    )
    boundary_obstacle_stall = (
        allow_geometry_escape
        and track.near_obstacle
        and mode in {"hard_turn", "correcting"}
        and signals["margin_risk"] >= profile["escape_boundary_margin_risk"]
        and min(track.left_margin_near, track.right_margin_near) <= profile["escape_boundary_margin_max"]
        and speed <= profile["escape_boundary_speed_max"]
        and not track.lost
        and track.confidence >= profile["escape_boundary_min_confidence"]
    )
    stable_view = signature_delta <= profile["escape_signature_delta"]

    # 统一脱困方向：朝感知到的路面一侧打，远离顶住的栏杆。
    escape_sign = _road_direction_sign(track)

    should_count_stall = False
    require_confidence = True
    trigger_frames = int(profile["escape_trigger_frames"])
    escape_frames = int(profile["escape_turn_frames"])
    escape_steering = profile["escape_turn_steering"]
    escape_speed = profile["escape_turn_speed"]
    if large_offset_stall:
        should_count_stall = True
        trigger_frames = int(profile["escape_offset_trigger_frames"])
        escape_frames = int(profile["escape_offset_frames"])
        escape_steering = profile["escape_offset_steering"]
        escape_speed = profile["escape_offset_speed"]
    elif boundary_obstacle_stall:
        # complex 后段 R017：近处静态车和右侧边界同时进入视野，车物理近停但策略速度仍在
        # 0.22-0.23，既没进 low_speed，也达不到 pinned 的大横向偏移。单侧余量为 0 时应更早脱困。
        should_count_stall = True
        require_confidence = False
        trigger_frames = int(profile["escape_boundary_trigger_frames"])
        escape_frames = int(profile["escape_boundary_frames"])
        escape_steering = profile["escape_boundary_steering"]
        escape_speed = profile["escape_boundary_speed"]
        escape_sign = _margin_escape_sign(track, escape_sign)
    elif (
        allow_geometry_escape
        and mode == "hard_turn"
        and high_turn
        and not aligned_offset
        and speed <= profile["escape_turn_speed_max"]
    ):
        # 平稳巡弯同样满足"高弯量+签名稳定+高置信"，必须加低速门槛才算卡边
        # （complex 实跑在正常左弯中误触发过本路径，escape 强行打轮导致撞栏）。
        should_count_stall = True
    elif pinned_stall:
        # basic/complex 都启用：几何冻结地顶住栏杆、speed 又没低到触发 low_speed 时的兜底。
        should_count_stall = True
        trigger_frames = int(profile["escape_pinned_trigger_frames"])
        escape_frames = int(profile["escape_pinned_frames"])
        escape_steering = profile["escape_pinned_steering"]
        escape_speed = profile["escape_pinned_speed"]
    elif low_speed_stall:
        should_count_stall = True
        # 贴墙被卡本就是低置信/丢线状态，放宽门槛，否则脱困永远进不来。
        require_confidence = False
        trigger_frames = int(profile["escape_low_speed_trigger_frames"])
        escape_frames = int(profile["escape_low_speed_frames"])
        escape_steering = profile["escape_low_speed_steering"]
        escape_speed = profile["escape_low_speed_speed"]

    confidence_ok = (not require_confidence) or (
        not track.lost and track.confidence >= profile["escape_min_confidence"]
    )
    if should_count_stall and stable_view and confidence_ok:
        _STALL_FRAMES += 1
    else:
        _STALL_FRAMES = 0

    if _STALL_FRAMES >= trigger_frames:
        _STALL_FRAMES = 0
        _ESCAPE_STEERING_SIGN = escape_sign
        _ESCAPE_STEERING_MAGNITUDE = escape_steering
        _ESCAPE_SPEED = escape_speed
        _ESCAPE_FRAMES = escape_frames

    return steering, speed, mode


def _lane_line_correction(
    track: TrackState,
    signals: dict,
    mode: str,
    profile: dict,
    timestamp: float,
) -> float:
    """白线可信时计算后置舵角修正（R011 验证的形态 + 信任门控）。

    功能：让车身中线追向白色虚线，作为最终舵角上的有界微调。
    参数：`track` 携带感知层的双目白线状态，`signals` 提供弯道风险，`mode` 是本帧驾驶状态，
    `timestamp` 用于限制发车捕获窗口。
    返回：平滑后的舵角修正；白线不可信时向 0 衰减。
    逻辑：只修正最终输出，不进入 risk/mode/速度/入弯门控——R013/R014 证明
    白线一旦改写控制目标，会抬高 offset_risk、骗开入弯门控并压低直道速度。
    信任门控针对 2026-06-11 实跑取证的三类误锁：白色护栏（|offset| 大）、
    白车/斑马线（near_obstacle）、弯中错误线段（单帧出现、帧间突变、高弯量时直线拟合失真）。
    """

    global _LINE_STREAK, _LINE_LAST_OFFSET, _LINE_CORRECTION

    normal_valid = (
        profile["enable"]
        and track.line_confidence >= profile["min_confidence"]
        and abs(track.line_offset) <= profile["offset_trust_max"]
        and not track.near_obstacle
        and mode != "escaping"
    )
    startup_valid = (
        profile["enable"]
        and track.red_environment
        and timestamp <= profile["startup_acquire_until"]
        and track.line_confidence >= profile["min_confidence"]
        and profile["startup_offset_min"] <= track.line_offset <= profile["startup_offset_trust_max"]
        and profile["startup_heading_min"] <= track.line_heading <= profile["startup_heading_max"]
        and not track.near_obstacle
        and mode != "escaping"
    )
    valid = normal_valid or startup_valid
    if valid and _LINE_STREAK > 0 and abs(track.line_offset - _LINE_LAST_OFFSET) > profile["offset_jump_max"]:
        valid = False
        _LINE_STREAK = 0
    if valid:
        _LINE_STREAK += 1
        _LINE_LAST_OFFSET = track.line_offset
    else:
        _LINE_STREAK = 0

    target = 0.0
    confirm_frames = int(profile["startup_confirm_frames"] if startup_valid and not normal_valid else profile["confirm_frames"])
    if valid and _LINE_STREAK >= confirm_frames:
        target = track.line_offset * profile["offset_gain"] + track.line_heading * profile["heading_gain"]
        max_correction = profile["startup_max_correction"] if startup_valid and not normal_valid else profile["max_correction"]
        curve_gate = profile["startup_curve_gate"] if startup_valid and not normal_valid else profile["curve_gate"]
        target = clamp(target, -max_correction, max_correction)
        target *= 1.0 - clamp(signals["curve_risk"] / curve_gate, 0.0, 1.0)

    if startup_valid and not normal_valid:
        alpha = profile["startup_smoothing"]
    elif not valid and timestamp <= profile["startup_acquire_until"] and _LINE_CORRECTION > 0.0:
        alpha = profile["startup_decay"]
    else:
        alpha = profile["smoothing"]
    _LINE_CORRECTION = _LINE_CORRECTION * alpha + target * (1.0 - alpha)
    return clamp(_LINE_CORRECTION, -profile["max_correction"], profile["max_correction"])


def _update_policy_state(track: TrackState, steering: float, speed: float, mode: str, timestamp: float, profile: dict) -> None:
    """写回策略跨帧状态。

    功能：维护丢线计数、恢复缓冲、最近可信方向和上一帧控制量。
    参数：`track` 是赛道状态，`steering` 和 `speed` 是本帧输出。
    返回：无。
    逻辑：刚从丢线恢复时保守若干帧；高置信时更新恢复方向偏置。
    """

    global _LAST_STEERING, _LAST_SPEED, _LAST_TIMESTAMP
    global _LOST_FRAMES, _RECOVERY_FRAMES, _LAST_GOOD_BIAS, _LAST_MODE

    if track.lost:
        _LOST_FRAMES += 1
    else:
        if _LOST_FRAMES > 0:
            _RECOVERY_FRAMES = int(profile["recovery_frames"])
        _LOST_FRAMES = 0
    if _RECOVERY_FRAMES > 0 and not track.lost:
        _RECOVERY_FRAMES -= 1

    if not track.lost and track.confidence >= profile["recovery_confidence"]:
        _LAST_GOOD_BIAS = clamp(
            track.lateral_error * 0.55 + track.lookahead_error * 0.25 + track.curvature * 0.20,
            -1.0,
            1.0,
        )

    _LAST_STEERING = steering
    _LAST_SPEED = speed
    _LAST_TIMESTAMP = timestamp
    _LAST_MODE = mode


def decide_control(track: TrackState, timestamp: float, mode: str = "fastest") -> ControlCmd:
    """计算最终控制命令。

    功能：按 fastest 或 safe 参数统一生成转向和速度。
    参数：`track` 是赛道状态，`timestamp` 是平台时间，`mode` 是参数模式。
    返回：`ControlCmd`，包含 `steering` 和 `speed`。
    逻辑：非法模式回退 fastest；内部用状态机协同转向、速度和恢复策略。
    """

    global _LAST_TARGET_STEERING, _LAST_TARGET_SPEED, _LAST_SIGNALS, _LAST_STRAIGHT_MEMORY_ACTIVE

    profile = get_profile(mode if mode in {"fastest", "safe"} else "fastest")
    if not track.red_environment:
        profile.update(BASIC_CONTROL_OVERRIDES)
    timestamp = float(timestamp)
    _maybe_reset_policy_by_timestamp(timestamp, profile)
    signals = _control_signals(track, profile)
    drive_mode = _select_mode(track, signals, timestamp, profile)
    straight_memory_active = _update_straight_memory(track, signals, drive_mode, profile)
    target_steering = _target_steering(track, signals, drive_mode, profile)
    _LAST_TARGET_STEERING = target_steering
    steering = _smooth_steering(target_steering, drive_mode, timestamp, profile)
    target_speed = _target_speed(
        track,
        signals,
        drive_mode,
        steering,
        timestamp,
        profile,
        straight_memory_active=straight_memory_active,
    )
    _LAST_TARGET_SPEED = target_speed
    _LAST_SIGNALS = dict(signals)
    _LAST_STRAIGHT_MEMORY_ACTIVE = bool(straight_memory_active)
    speed = _smooth_speed(target_speed, timestamp, profile)
    # 低速贴墙脱困两条赛道都启用；依赖可靠几何的急弯/大偏移脱困仍只在 complex(red)。
    steering, speed, drive_mode = _escape_if_stalled(
        track, signals, steering, speed, drive_mode, profile, track.red_environment
    )
    # 跨帧状态记录修正前的舵角：白线修正只作用于最终输出，平滑、限速和脱困
    # 判据都不感知它（与 R011 在入口层后置修正时的动力学一致）。
    _update_policy_state(track, steering, speed, drive_mode, timestamp, profile)
    line_correction = _lane_line_correction(track, signals, drive_mode, LINE_FOLLOW_PROFILE, timestamp)
    final_steering = clamp(steering + line_correction, -1.0, 1.0)
    return ControlCmd(final_steering, speed)
