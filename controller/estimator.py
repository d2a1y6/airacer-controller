"""赛道几何估计模块。

功能概述：把感知中心点转换成稳定的赛道状态。
输入输出：输入 `PerceptionObs` 和时间戳，输出 `TrackState`。
处理流程：清洗中心点，按 progress 拟合中心线，估计偏移、朝向和曲率，再按置信度平滑。
"""

import numpy as np

from controller.common import PerceptionObs, TrackState, clamp
from controller.params import ESTIMATOR_PROFILE

_LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
_LAST_TIMESTAMP = None
_LAST_RED_ENVIRONMENT = False
_RED_ENVIRONMENT_STREAK = 0
_RED_ENVIRONMENT_FLAG = 32
_RED_ENVIRONMENT_LATCH_FRAMES = 3


def _lost_track(confidence: float, red_environment: bool | None = None) -> TrackState:
    """生成丢线状态。

    功能：保留上一帧估计的衰减值，避免控制量突然归零。
    参数：`confidence` 是当前可用的低置信度。
    返回：`lost=True` 的 `TrackState`。
    逻辑：各几何量使用独立衰减参数，置信度裁剪到合法范围。
    """

    if red_environment is None:
        red_environment = _LAST_TRACK.red_environment
    return TrackState(
        _LAST_TRACK.lateral_error * ESTIMATOR_PROFILE["lost_lateral_decay"],
        _LAST_TRACK.heading_error * ESTIMATOR_PROFILE["lost_heading_decay"],
        _LAST_TRACK.curvature * ESTIMATOR_PROFILE["lost_curvature_decay"],
        _LAST_TRACK.lookahead_error * ESTIMATOR_PROFILE["lost_lookahead_decay"],
        clamp(confidence, 0.0, ESTIMATOR_PROFILE["lost_confidence"]),
        True,
        red_environment,
    )


def _clean_points(points) -> np.ndarray:
    """清洗感知中心点。

    功能：把输入转为 `float32` 的 `N x 2` 数组，并过滤 NaN / inf。
    参数：`points` 是 `PerceptionObs.center_points`。
    返回：只含有限坐标的二维数组。
    逻辑：异常形状直接返回空数组，由上层进入 lost。
    """

    try:
        array = np.asarray(points, dtype=np.float32)
    except (TypeError, ValueError):
        return np.empty((0, 2), dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != 2:
        return np.empty((0, 2), dtype=np.float32)
    return array[np.isfinite(array).all(axis=1)]


def _normalize_points(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """把图像坐标转换成横向误差和前后进度。

    功能：固定图像中心为 320，把 x 归一化到 `[-1, 1]`，把 y 转成 progress。
    参数：`points` 是清洗后的中心点。
    返回：`x_norm`、`progress` 和 y 跨度。
    逻辑：progress=0 表示近处，progress=1 表示远处。
    """

    y = points[:, 1].astype(np.float32)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_span = max(y_max - y_min, 0.0)
    progress = (y_max - y) / max(y_span, 1.0)

    x = points[:, 0].astype(np.float32)
    x_norm = (x - ESTIMATOR_PROFILE["image_center_x"]) / ESTIMATOR_PROFILE["x_scale"]
    x_norm = np.clip(x_norm, -1.0, 1.0)
    return x_norm.astype(np.float32), progress.astype(np.float32), y_span


def _fit_centerline(progress: np.ndarray, x_norm: np.ndarray) -> tuple[np.ndarray, int]:
    """拟合归一化中心线。

    功能：用 progress 作为自变量拟合 `x_norm`。
    参数：`progress` 是前后进度，`x_norm` 是横向归一化中心。
    返回：`np.polyval()` 可用的系数和拟合阶数。
    逻辑：点数足够时用二次曲线，点数不足时用直线。
    """

    degree = 2 if len(progress) >= ESTIMATOR_PROFILE["poly2_min_points"] else 1
    coeffs = np.polyfit(progress, x_norm, deg=degree)
    return coeffs.astype(np.float32), degree


def _value_from_band(
    progress: np.ndarray,
    x_norm: np.ndarray,
    coeffs: np.ndarray,
    mask: np.ndarray,
    fallback_progress: float,
) -> float:
    """从指定 progress 区间估计横向误差。"""

    if np.any(mask):
        return float(np.median(x_norm[mask]))
    return float(np.polyval(coeffs, fallback_progress))


def _heading_from_fit(coeffs: np.ndarray, degree: int) -> float:
    """由中心线导数估计朝向误差。"""

    eval_progress = ESTIMATOR_PROFILE["heading_eval_progress"]
    if degree == 2:
        derivative = float(2.0 * coeffs[0] * eval_progress + coeffs[1])
    else:
        derivative = float(coeffs[0])
    return clamp(derivative * ESTIMATOR_PROFILE["heading_gain"], -1.0, 1.0)


def _curvature_trust(n_points: int, y_span: float, fit_score: float) -> float:
    """计算曲率可信度。

    功能：当扫描点少、纵向跨度小或拟合误差大时，二次项不可信，可信度趋近 0。
    参数：`n_points` 是中心点数，`y_span` 是纵向像素跨度，`fit_score` 是拟合质量分。
    返回：`[0, 1]` 的可信度。
    逻辑：远端被遮挡时只剩近处少量聚簇点，deg-2 二次系数是数值噪声（常被钳到 ±1、
    甚至符号相反——在全程右弯的赛道上凭空出现"满信心左弯"）。三项必须同时达标才信曲率。
    """

    span = max(ESTIMATOR_PROFILE["curvature_full_points"] - ESTIMATOR_PROFILE["poly2_min_points"], 1.0)
    n_score = clamp((float(n_points) - ESTIMATOR_PROFILE["poly2_min_points"]) / span, 0.0, 1.0)
    span_score = clamp(y_span / ESTIMATOR_PROFILE["curvature_min_y_span"], 0.0, 1.0)
    return clamp(n_score * span_score * clamp(fit_score, 0.0, 1.0), 0.0, 1.0)


def _curvature_from_fit(
    coeffs: np.ndarray,
    degree: int,
    lateral_error: float,
    lookahead_error: float,
    trust: float,
) -> float:
    """估计中心线曲率。

    功能：二次拟合时用二次项，其他情况用远近误差差值兜底，并按可信度收缩。
    参数：拟合系数、阶数、近处误差、远处误差和曲率可信度 `trust`。
    返回：右弯为正、左弯为负的曲率值。
    逻辑：用 `trust` 把不可信的二次系数收向 0，避免幻觉急弯；再裁剪到 `[-1, 1]`。
    """

    if degree == 2:
        value = float(coeffs[0]) * ESTIMATOR_PROFILE["curvature_gain"]
    else:
        value = (lookahead_error - lateral_error) * ESTIMATOR_PROFILE["fallback_curvature_gain"]
    return clamp(value * trust, -1.0, 1.0)


def _fit_error_score(progress: np.ndarray, x_norm: np.ndarray, coeffs: np.ndarray) -> float:
    """把中心线拟合误差转换成置信度分数。"""

    fitted = np.polyval(coeffs, progress)
    rmse = float(np.sqrt(np.mean((x_norm - fitted) ** 2)))
    return clamp(1.0 - rmse / ESTIMATOR_PROFILE["max_fit_error"], 0.0, 1.0)


def _geometry_confidence(obs: PerceptionObs, points: np.ndarray, y_span: float, fit_score: float) -> float:
    """计算几何置信度。

    功能：综合感知置信度、点数、y 覆盖范围、拟合误差和道路宽度。
    参数：`obs` 是感知结果，`points` 是清洗点，`y_span` 是纵向覆盖，`fit_score` 是拟合质量。
    返回：`[0, 1]` 内的几何置信度。
    逻辑：几何质量差时不会直接照抄感知置信度。
    """

    obs_score = clamp(obs.confidence, 0.0, 1.0)
    point_score = clamp(len(points) / float(ESTIMATOR_PROFILE["min_good_points"]), 0.0, 1.0)
    span_score = clamp(y_span / ESTIMATOR_PROFILE["min_y_span_good"], 0.0, 1.0)
    width_score = clamp(obs.road_width_est / ESTIMATOR_PROFILE["min_road_width_for_conf"], 0.0, 1.0)
    quality = (
        0.30
        + point_score * 0.20
        + span_score * 0.20
        + fit_score * 0.25
        + width_score * 0.05
    )
    confidence = obs_score * quality
    return clamp(min(confidence, obs_score + 0.20), 0.0, 1.0)


def _smooth_alpha(confidence: float) -> float:
    """按置信度选择普通误差平滑强度。"""

    low_conf = 1.0 - clamp(confidence, 0.0, 1.0)
    alpha = (
        ESTIMATOR_PROFILE["min_smooth_alpha"]
        + (ESTIMATOR_PROFILE["max_smooth_alpha"] - ESTIMATOR_PROFILE["min_smooth_alpha"]) * low_conf
        + ESTIMATOR_PROFILE["low_conf_extra_smoothing"] * low_conf
    )
    return clamp(alpha, ESTIMATOR_PROFILE["min_smooth_alpha"], ESTIMATOR_PROFILE["max_smooth_alpha"])


def _smooth_limited(previous: float, current: float, alpha: float, max_delta: float) -> float:
    """平滑单个值并限制单帧变化。"""

    smoothed = previous * alpha + current * (1.0 - alpha)
    delta = clamp(smoothed - previous, -max_delta, max_delta)
    return clamp(previous + delta, -1.0, 1.0)


def reset_estimator_state() -> None:
    """重置估计器跨帧状态。

    功能：让测试或新一轮仿真从干净状态开始。
    参数：无。
    返回：无。
    逻辑：清空上一帧几何状态和时间戳。
    """

    global _LAST_TRACK, _LAST_TIMESTAMP, _LAST_RED_ENVIRONMENT, _RED_ENVIRONMENT_STREAK
    _LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
    _LAST_TIMESTAMP = None
    _LAST_RED_ENVIRONMENT = False
    _RED_ENVIRONMENT_STREAK = 0


def _maybe_reset_estimator_by_timestamp(timestamp: float) -> None:
    """根据时间戳判断是否重置跨帧状态。"""

    if _LAST_TIMESTAMP is None:
        return
    elapsed = float(timestamp) - float(_LAST_TIMESTAMP)
    if elapsed < 0.0 or elapsed > ESTIMATOR_PROFILE["timestamp_reset_gap"]:
        reset_estimator_state()


def estimate_track(obs: PerceptionObs, timestamp: float) -> TrackState:
    """估计赛道几何状态。

    功能：把感知中心点转换成 policy 可直接使用的赛道状态。
    参数：`obs` 是感知结果，`timestamp` 是平台时间戳。
    返回：`TrackState`。
    逻辑：点集无效时返回衰减 lost 状态；有效时按 progress 拟合中心线并做自适应平滑。
    """

    global _LAST_TRACK, _LAST_TIMESTAMP, _LAST_RED_ENVIRONMENT, _RED_ENVIRONMENT_STREAK

    timestamp = float(timestamp)
    _maybe_reset_estimator_by_timestamp(timestamp)

    observed_red = bool(obs.debug_flags & _RED_ENVIRONMENT_FLAG)
    if observed_red:
        _RED_ENVIRONMENT_STREAK += 1
    elif not _LAST_RED_ENVIRONMENT:
        _RED_ENVIRONMENT_STREAK = 0
    if _RED_ENVIRONMENT_STREAK >= _RED_ENVIRONMENT_LATCH_FRAMES:
        _LAST_RED_ENVIRONMENT = True
    red_environment = observed_red or _LAST_RED_ENVIRONMENT

    points = _clean_points(obs.center_points)
    if len(points) < ESTIMATOR_PROFILE["min_center_points"] or obs.confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = _lost_track(obs.confidence, red_environment)
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    x_norm, progress, y_span = _normalize_points(points)
    if y_span < ESTIMATOR_PROFILE["min_y_span"]:
        track = _lost_track(obs.confidence, red_environment)
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    coeffs, degree = _fit_centerline(progress, x_norm)
    lateral_error = clamp(
        _value_from_band(
            progress,
            x_norm,
            coeffs,
            progress <= ESTIMATOR_PROFILE["near_progress_max"],
            ESTIMATOR_PROFILE["near_eval_progress"],
        ),
        -1.0,
        1.0,
    )
    lookahead_error = clamp(
        _value_from_band(
            progress,
            x_norm,
            coeffs,
            progress >= ESTIMATOR_PROFILE["far_progress_min"],
            ESTIMATOR_PROFILE["far_eval_progress"],
        ),
        -1.0,
        1.0,
    )
    heading_error = _heading_from_fit(coeffs, degree)
    fit_score = _fit_error_score(progress, x_norm, coeffs)
    curvature_trust = _curvature_trust(len(points), y_span, fit_score)
    curvature = _curvature_from_fit(coeffs, degree, lateral_error, lookahead_error, curvature_trust)

    confidence = _geometry_confidence(obs, points, y_span, fit_score)
    if confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = _lost_track(confidence, red_environment)
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    alpha = _smooth_alpha(confidence)
    curve_alpha = clamp(
        ESTIMATOR_PROFILE["curve_smooth_alpha"]
        + ESTIMATOR_PROFILE["low_conf_extra_smoothing"] * (1.0 - confidence),
        ESTIMATOR_PROFILE["min_smooth_alpha"],
        ESTIMATOR_PROFILE["max_smooth_alpha"],
    )
    track = TrackState(
        _smooth_limited(_LAST_TRACK.lateral_error, lateral_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        _smooth_limited(_LAST_TRACK.heading_error, heading_error, alpha, ESTIMATOR_PROFILE["max_heading_delta"]),
        _smooth_limited(_LAST_TRACK.curvature, curvature, curve_alpha, ESTIMATOR_PROFILE["max_curvature_delta"]),
        _smooth_limited(_LAST_TRACK.lookahead_error, lookahead_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        confidence,
        False,
        red_environment,
    )
    _LAST_TRACK = track
    _LAST_TIMESTAMP = timestamp
    return track
