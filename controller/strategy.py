"""速度策略和模式切换模块。

功能概述：根据赛道状态、转向命令和 profile 选择驾驶模式并计算速度。
输入输出：输入 `TrackState`、`SteeringCmd` 和参数字典，输出 `ControlMode` 或 `SpeedCmd`。
处理流程：先按丢线、置信度和风险切模式，再按风险项削减基础速度。
"""

import math

from controller.common import ControlMode, SpeedCmd, SteeringCmd, TrackState, clamp


def _risk_from_track(track: TrackState) -> float:
    curve_risk = abs(track.curvature) * 0.45
    offset_risk = abs(track.lateral_error) * 0.35
    heading_risk = abs(track.heading_error) * 0.20
    confidence_risk = 1.0 - track.confidence
    return clamp(curve_risk + offset_risk + heading_risk + confidence_risk * 0.45, 0.0, 1.0)


def select_mode(track: TrackState, timestamp: float, profile: dict) -> ControlMode:
    """选择驾驶模式。

    功能：把连续风险值转换为 normal、caution、lost 或 recovery。
    参数：`track` 是几何状态，`timestamp` 是平台时间，`profile` 是策略参数。
    返回：`ControlMode`。
    逻辑：丢线优先，其次看置信度和综合风险；启动阶段可更保守。
    """

    risk = _risk_from_track(track)
    if track.lost:
        return ControlMode("lost", max(risk, profile["lost_risk"]))
    if track.confidence < profile["recovery_confidence"]:
        return ControlMode("recovery", max(risk, 0.72))
    if timestamp < profile["start_caution_seconds"] or risk > profile["caution_risk"]:
        return ControlMode("caution", risk)
    return ControlMode("normal", risk)


def compute_speed(
    track: TrackState,
    steering: SteeringCmd,
    mode: ControlMode,
    timestamp: float,
    profile: dict,
) -> SpeedCmd:
    """计算速度命令。

    功能：在稳定直道提速，在急弯、低置信度、丢线和大转向时降速。
    参数：`track` 是赛道状态，`steering` 是转向命令，`mode` 是驾驶模式，`profile` 是策略参数。
    返回：`SpeedCmd`。
    逻辑：从基础速度出发，按曲率、偏移、转向和模式风险逐项扣减。
    """

    del timestamp

    if mode.name == "lost":
        return SpeedCmd(profile["lost_speed"], track.confidence)
    if mode.name == "recovery":
        return SpeedCmd(profile["recovery_speed"], track.confidence)

    curve_penalty = abs(track.curvature) * profile["curve_slowdown"]
    offset_penalty = abs(track.lateral_error) * profile["offset_slowdown"]
    steering_penalty = math.sqrt(abs(steering.value)) * profile["steering_slowdown"]
    risk_penalty = mode.risk * profile["risk_slowdown"]

    speed = profile["base_speed"] - curve_penalty - offset_penalty - steering_penalty - risk_penalty
    if mode.name == "caution":
        speed = min(speed, profile["caution_speed"])

    value = clamp(speed, profile["min_speed"], profile["max_speed"])
    confidence = clamp(min(track.confidence, steering.confidence), 0.0, 1.0)
    return SpeedCmd(value, confidence)
