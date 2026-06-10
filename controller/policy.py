"""控制策略模块。

功能概述：根据赛道状态统一规划转向和速度。
输入输出：输入 `TrackState`、时间戳和 fastest/safe 模式，输出 `ControlCmd`。
处理流程：计算风险分量，选择驾驶状态，生成目标转向和速度，再做平滑与变化率限制。
"""

import math

from controller.common import ControlCmd, TrackState, clamp
from controller.params import BASIC_CONTROL_OVERRIDES, get_profile

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
    global _LAST_TRACK_SIGNATURE
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
        "turn_demand": turn_demand,
        "risk": risk,
    }


def _select_mode(track: TrackState, signals: dict, timestamp: float, profile: dict) -> str:
    """选择内部驾驶状态。

    功能：在 lost、recovering、hard_turn、correcting、cruise 之间切换。
    参数：`track` 是赛道状态，`signals` 是风险分量，`timestamp` 是平台时间。
    返回：内部状态名。
    逻辑：丢线优先，其次恢复缓冲、急弯、回中和巡航。
    """

    del timestamp
    if track.lost or track.confidence < profile["lost_confidence"]:
        return "lost"
    if _RECOVERY_FRAMES > 0 or track.confidence < profile["recovery_confidence"]:
        return "recovering"
    if (
        signals["curve_risk"] > profile["hard_turn_threshold"]
        or signals["turn_demand"] > profile["hard_turn_threshold"]
    ):
        return "hard_turn"
    if abs(track.lateral_error) > profile["correction_error"]:
        return "correcting"
    return "cruise"


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
        raw = 0.75 * _LAST_STEERING + 0.25 * _LAST_GOOD_BIAS
    elif mode == "recovering":
        raw *= 0.70
    elif mode == "correcting":
        raw += track.lateral_error * 0.25
    elif mode == "hard_turn":
        raw *= 1.05

    if (
        track.red_environment
        and
        track.lateral_error > profile["inside_left_lateral_min"]
        and track.heading_error < profile["inside_left_heading_max"]
        and track.curvature < profile["inside_left_curvature_max"]
    ):
        raw = max(raw, profile["inside_left_steering_limit"])

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
    speed_factor = 1.0 - 0.35 * clamp(_LAST_SPEED / max(profile["max_speed"], 1e-6), 0.0, 1.0)
    max_delta = profile["max_steering_delta"] * dt_factor * speed_factor
    delta = clamp(smoothed - _LAST_STEERING, -max_delta, max_delta)
    max_abs = profile["max_abs_steering"]
    return clamp(_LAST_STEERING + delta, -max_abs, max_abs)


def _target_speed(track: TrackState, signals: dict, mode: str, steering: float, timestamp: float, profile: dict) -> float:
    """计算目标速度。

    功能：用乘法降速组合弯道、偏移、置信度和转向风险。
    参数：`track` 是赛道状态，`signals` 是风险分量，`mode` 是内部状态，`steering` 是当前转向。
    返回：目标速度比例。
    逻辑：模式只限制速度上限，正常速度由风险因子相乘得到。
    """

    if mode == "lost":
        return profile["lost_speed"]

    curve_factor = 1.0 - profile["curve_slowdown"] * (signals["curve_risk"] ** profile["curve_power"])
    offset_factor = 1.0 - profile["offset_slowdown"] * (signals["offset_risk"] ** profile["offset_power"])
    confidence_factor = profile["min_confidence_factor"] + (1.0 - profile["min_confidence_factor"]) * track.confidence
    steering_factor = 1.0 - profile["steering_slowdown"] * (abs(steering) ** profile["steering_power"])
    target = profile["base_speed"] * curve_factor * offset_factor * confidence_factor * steering_factor

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
) -> tuple[float, float, str]:
    """在顶住边界时短暂反打脱困。

    功能：检测急弯大转向卡边，或长时间低速且几何签名几乎不变的状态。
    参数：当前赛道状态、风险信号、已平滑的转向和速度、内部模式、参数表。
    返回：可能被覆盖后的 `(steering, speed, mode)`。
    逻辑：急弯短反打；大偏移贴边长反打；低速稳态触发更慢，并固定向右侧脱离最终卡边。
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
        mode in {"hard_turn", "correcting"}
        and signals["offset_risk"] >= profile["escape_offset_threshold"]
        and speed <= profile["escape_offset_speed_threshold"]
        and abs(track.heading_error) <= profile["escape_offset_heading_abs_max"]
        and abs(track.curvature) <= profile["escape_offset_curve_abs_max"]
        and track.lateral_error * track.lookahead_error >= profile["escape_offset_lookahead_alignment"]
    )
    low_speed_stall = speed <= profile["escape_low_speed_threshold"]
    stable_view = signature_delta <= profile["escape_signature_delta"]
    should_count_stall = False
    trigger_frames = int(profile["escape_trigger_frames"])
    escape_sign = 1.0
    escape_frames = int(profile["escape_turn_frames"])
    escape_steering = profile["escape_turn_steering"]
    escape_speed = profile["escape_turn_speed"]
    if large_offset_stall:
        should_count_stall = True
        trigger_frames = int(profile["escape_offset_trigger_frames"])
        escape_frames = int(profile["escape_offset_frames"])
        escape_steering = profile["escape_offset_steering"]
        escape_speed = profile["escape_offset_speed"]
        reference = _LAST_STEERING if abs(_LAST_STEERING) > 0.05 else steering
        if abs(reference) <= 0.05:
            reference = track.lateral_error
        escape_sign = -math.copysign(1.0, reference if reference else 1.0)
    elif mode == "hard_turn" and high_turn and not aligned_offset:
        should_count_stall = True
        reference = _LAST_STEERING if abs(_LAST_STEERING) > 0.05 else steering
        escape_sign = -math.copysign(1.0, reference if reference else 1.0)
    elif low_speed_stall:
        should_count_stall = True
        trigger_frames = int(profile["escape_low_speed_trigger_frames"])
        escape_frames = int(profile["escape_low_speed_frames"])
        escape_steering = profile["escape_low_speed_steering"]
        escape_speed = profile["escape_low_speed_speed"]
        escape_sign = -1.0

    if (
        should_count_stall
        and stable_view
        and not track.lost
        and track.confidence >= profile["escape_min_confidence"]
    ):
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

    profile = get_profile(mode if mode in {"fastest", "safe"} else "fastest")
    if not track.red_environment:
        profile.update(BASIC_CONTROL_OVERRIDES)
    timestamp = float(timestamp)
    _maybe_reset_policy_by_timestamp(timestamp, profile)
    signals = _control_signals(track, profile)
    drive_mode = _select_mode(track, signals, timestamp, profile)
    target_steering = _target_steering(track, signals, drive_mode, profile)
    steering = _smooth_steering(target_steering, drive_mode, timestamp, profile)
    target_speed = _target_speed(track, signals, drive_mode, steering, timestamp, profile)
    speed = _smooth_speed(target_speed, timestamp, profile)
    if track.red_environment:
        steering, speed, drive_mode = _escape_if_stalled(track, signals, steering, speed, drive_mode, profile)
    _update_policy_state(track, steering, speed, drive_mode, timestamp, profile)
    return ControlCmd(steering, speed)
