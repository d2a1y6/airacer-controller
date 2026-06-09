"""赛道几何估计模块。

功能概述：把感知点转换成横向偏移、方向误差、曲率和前瞻误差。
输入输出：输入 `PerceptionObs` 和时间戳，输出 `TrackState`。
处理流程：按近远扫描点分组，计算近处偏移、远处偏移和中心线斜率，再做轻量平滑。
"""

import numpy as np

from controller.common import PerceptionObs, TrackState, clamp
from controller.params import ESTIMATOR_PROFILE

_LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)


def _image_center(points: np.ndarray) -> float:
    if points.size == 0:
        return 320.0
    max_x = float(np.max(points[:, 0]))
    min_x = float(np.min(points[:, 0]))
    width_guess = max(640.0, max_x - min_x)
    return width_guess * 0.5


def _weighted_x(points: np.ndarray, near: bool) -> float:
    y = points[:, 1]
    if near:
        weights = 0.35 + y / max(float(np.max(y)), 1.0)
    else:
        weights = 1.35 - y / max(float(np.max(y)), 1.0)
    return float(np.average(points[:, 0], weights=weights))


def _smooth_value(previous: float, current: float, alpha: float) -> float:
    return previous * alpha + current * (1.0 - alpha)


def reset_estimator_state() -> None:
    """重置估计器跨帧状态。

    功能：让测试或新一轮仿真从干净状态开始。
    参数：无。
    返回：无。
    逻辑：把上一帧状态写回低置信度丢线状态。
    """

    global _LAST_TRACK
    _LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)


def estimate_track(obs: PerceptionObs, timestamp: float) -> TrackState:
    """估计赛道几何状态。

    功能：根据中心点估计控制模块需要的几何量。
    参数：`obs` 是感知结果，`timestamp` 是平台时间戳。
    返回：`TrackState`。
    逻辑：点数不足时进入丢线状态；点数足够时计算近处、远处和整体趋势并平滑输出。
    """

    del timestamp
    global _LAST_TRACK

    points = obs.center_points
    if points.size == 0 or obs.confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        recovered = TrackState(
            _LAST_TRACK.lateral_error * 0.85,
            _LAST_TRACK.heading_error * 0.80,
            _LAST_TRACK.curvature * 0.80,
            _LAST_TRACK.lookahead_error * 0.85,
            max(obs.confidence, 0.0),
            True,
        )
        _LAST_TRACK = recovered
        return recovered

    points = points[np.argsort(points[:, 1])]
    center_x = _image_center(points)
    scale = max(center_x, 1.0)

    near_x = _weighted_x(points, near=True)
    far_x = _weighted_x(points, near=False)
    lateral_error = clamp((near_x - center_x) / scale, -1.0, 1.0)
    lookahead_error = clamp((far_x - center_x) / scale, -1.0, 1.0)

    if len(points) >= 2:
        fit = np.polyfit(points[:, 1], points[:, 0], deg=1)
        heading_error = clamp(float(fit[0]) * 1.6, -1.0, 1.0)
    else:
        heading_error = 0.0

    curvature = clamp(lookahead_error - lateral_error, -1.0, 1.0)
    alpha = ESTIMATOR_PROFILE["smooth_alpha"]
    track = TrackState(
        _smooth_value(_LAST_TRACK.lateral_error, lateral_error, alpha),
        _smooth_value(_LAST_TRACK.heading_error, heading_error, alpha),
        _smooth_value(_LAST_TRACK.curvature, curvature, alpha),
        _smooth_value(_LAST_TRACK.lookahead_error, lookahead_error, alpha),
        clamp(obs.confidence, 0.0, 1.0),
        False,
    )
    _LAST_TRACK = track
    return track
