"""转向控制模块。

功能概述：根据赛道几何状态和驾驶模式计算方向盘比例。
输入输出：输入 `TrackState`、`ControlMode`、时间戳和 profile，输出 `SteeringCmd`。
处理流程：组合横向偏移、朝向误差、前瞻误差和曲率，再做死区、平滑和变化率限制。
"""

from controller.common import ControlMode, SteeringCmd, TrackState, clamp

_LAST_STEERING = 0.0
_LAST_TIMESTAMP = None


def reset_steering_state() -> None:
    """重置转向跨帧状态。

    功能：清空上一帧转向和时间戳。
    参数：无。
    返回：无。
    逻辑：测试或新仿真开始前调用，避免继承旧平滑状态。
    """

    global _LAST_STEERING, _LAST_TIMESTAMP
    _LAST_STEERING = 0.0
    _LAST_TIMESTAMP = None


def compute_steering(
    track: TrackState,
    mode: ControlMode,
    timestamp: float,
    profile: dict,
) -> SteeringCmd:
    """计算转向命令。

    功能：输出范围稳定的方向盘比例。
    参数：`track` 是赛道状态，`mode` 是驾驶模式，`timestamp` 是平台时间，`profile` 是策略参数。
    返回：`SteeringCmd`。
    逻辑：正常模式响应更快，风险模式加大平滑并限制单帧变化。
    """

    global _LAST_STEERING, _LAST_TIMESTAMP

    raw = (
        track.lateral_error * profile["lateral_gain"]
        + track.heading_error * profile["heading_gain"]
        + track.lookahead_error * profile["lookahead_gain"]
        + track.curvature * profile["curvature_gain"]
    )

    if abs(raw) < profile["steering_deadzone"]:
        raw = 0.0

    if mode.name in {"lost", "recovery"}:
        raw *= profile["recovery_steering_scale"]

    raw = clamp(raw, -1.0, 1.0)
    alpha = profile["caution_steering_smooth"] if mode.name != "normal" else profile["steering_smooth"]
    smoothed = _LAST_STEERING * alpha + raw * (1.0 - alpha)

    if _LAST_TIMESTAMP is None:
        max_delta = profile["max_steering_delta"]
    else:
        elapsed = max(float(timestamp) - float(_LAST_TIMESTAMP), 0.0)
        max_delta = profile["max_steering_delta"] * max(1.0, elapsed / profile["nominal_dt"])

    delta = clamp(smoothed - _LAST_STEERING, -max_delta, max_delta)
    value = clamp(_LAST_STEERING + delta, -1.0, 1.0)
    _LAST_STEERING = value
    _LAST_TIMESTAMP = timestamp

    confidence = clamp(track.confidence * (1.0 - mode.risk * 0.35), 0.0, 1.0)
    return SteeringCmd(value, confidence)
