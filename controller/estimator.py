"""赛道几何估计模块。

功能概述：把感知中心点转换成稳定的赛道状态。
输入输出：输入 `PerceptionObs` 和时间戳，输出 `TrackState`。
处理流程：清洗中心点，按 progress 拟合中心线，估计偏移、朝向和曲率，再按置信度平滑。
"""

import math

import numpy as np

from controller.common import PerceptionObs, TrackState, clamp
from controller.params import ESTIMATOR_PROFILE

_LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
_LAST_TIMESTAMP = None
_LAST_RED_ENVIRONMENT = False
_RED_ENVIRONMENT_STREAK = 0
_RED_ENVIRONMENT_FLAG = 32
_RED_ENVIRONMENT_LATCH_FRAMES = 3
_LINE_MEMORY_FRAMES = 0
_LINE_MEMORY_OFFSET = 0.0
_LINE_MEMORY_HEADING = 0.0
_LINE_MEMORY_CONFIDENCE = 0.0


def _lost_track(
    confidence: float,
    red_environment: bool | None = None,
    obs: PerceptionObs | None = None,
) -> TrackState:
    """生成丢线状态。

    功能：保留上一帧估计的衰减值，避免控制量突然归零。
    参数：`confidence` 是当前可用的低置信度，`obs` 提供本帧白线状态。
    返回：`lost=True` 的 `TrackState`。
    逻辑：各几何量使用独立衰减参数，置信度裁剪到合法范围。白线状态透传本帧
    感知结果而不衰减：道路 mask 饱和（蓝门/天空）导致的 lost 帧白线往往仍可见，
    是后置白线修正在这些帧上保持方向的唯一来源。
    """

    if red_environment is None:
        red_environment = _LAST_TRACK.red_environment
    if obs is not None:
        line_offset = clamp(float(obs.line_offset), -1.0, 1.0)
        line_heading = clamp(float(obs.line_heading), -1.0, 1.0)
        line_confidence = clamp(float(obs.line_confidence), 0.0, 1.0)
        near_obstacle = bool(obs.near_obstacle)
        obstacle_x = clamp(float(obs.obstacle_x), -1.0, 1.0)
        obstacle_size = max(float(obs.obstacle_size), 0.0)
    else:
        line_offset = _LAST_TRACK.line_offset
        line_heading = _LAST_TRACK.line_heading
        line_confidence = 0.0
        near_obstacle = _LAST_TRACK.near_obstacle
        obstacle_x = _LAST_TRACK.obstacle_x
        obstacle_size = _LAST_TRACK.obstacle_size
    return TrackState(
        _LAST_TRACK.lateral_error * ESTIMATOR_PROFILE["lost_lateral_decay"],
        _LAST_TRACK.heading_error * ESTIMATOR_PROFILE["lost_heading_decay"],
        _LAST_TRACK.curvature * ESTIMATOR_PROFILE["lost_curvature_decay"],
        _LAST_TRACK.lookahead_error * ESTIMATOR_PROFILE["lost_lookahead_decay"],
        clamp(confidence, 0.0, ESTIMATOR_PROFILE["lost_confidence"]),
        True,
        red_environment,
        line_offset,
        line_heading,
        line_confidence,
        _LAST_TRACK.left_margin_near,
        _LAST_TRACK.right_margin_near,
        near_obstacle,
        obstacle_x,
        obstacle_size,
        obs.frame_motion,
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


def _near_edge_margin(edge_points, side: str) -> float:
    """估计近处车身中线到某侧边界的归一化余量。"""

    points = _clean_points(edge_points)
    if len(points) == 0:
        return 1.0
    y = points[:, 1].astype(np.float32)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_span = max(y_max - y_min, 1.0)
    near_mask = y >= y_min + y_span * 0.62
    if not np.any(near_mask):
        near_mask = np.ones(len(points), dtype=bool)
    x = float(np.median(points[near_mask, 0]))
    center = ESTIMATOR_PROFILE["image_center_x"]
    scale = ESTIMATOR_PROFILE["x_scale"]
    if side == "left":
        return clamp((center - x) / scale, 0.0, 1.0)
    return clamp((x - center) / scale, 0.0, 1.0)


def _line_weight(line_confidence: float) -> float:
    """把白线置信度转换成目标线融合权重。"""

    min_confidence = ESTIMATOR_PROFILE["line_target_min_confidence"]
    if line_confidence < min_confidence:
        return 0.0
    usable = (line_confidence - min_confidence) / max(1.0 - min_confidence, 1e-6)
    return clamp(usable, 0.0, 1.0)


def _line_target_trust(obs: PerceptionObs, timestamp: float, red_environment: bool) -> float:
    """计算白线目标是否足以进入主几何链路。

    功能：把白线置信度、offset 形态和 road mask 质量合成融合权重。
    参数：`obs` 是感知结果，`timestamp` 是当前时间，`red_environment` 表示 complex 红色场地。
    返回：`[0, 1]` 的融合强度。
    逻辑：普通帧只接收小 offset 白线；发车短窗口接收右侧中等 offset 白线。
    road mask 过宽/低置信时白线权重更高，避免假 road center 压过真实虚线。
    """

    base = _line_weight(obs.line_confidence)
    if base <= 0.0:
        return 0.0

    startup_valid = (
        red_environment
        and timestamp <= ESTIMATOR_PROFILE["line_startup_until"]
        and ESTIMATOR_PROFILE["line_startup_offset_min"]
        <= obs.line_offset
        <= ESTIMATOR_PROFILE["line_startup_offset_max"]
        and ESTIMATOR_PROFILE["line_startup_heading_min"]
        <= obs.line_heading
        <= ESTIMATOR_PROFILE["line_startup_heading_max"]
    )
    normal_valid = abs(obs.line_offset) <= ESTIMATOR_PROFILE["line_target_normal_offset_max"]
    if not startup_valid and not normal_valid:
        return 0.0

    if startup_valid:
        scale = ESTIMATOR_PROFILE["line_target_startup_scale"]
    elif obs.confidence <= ESTIMATOR_PROFILE["line_target_road_confidence_max"] or obs.debug_flags & 4:
        scale = ESTIMATOR_PROFILE["line_target_unreliable_road_scale"]
    else:
        scale = ESTIMATOR_PROFILE["line_target_normal_scale"]
    return clamp(base * scale, 0.0, 1.0)


def _update_line_memory(obs: PerceptionObs, line_trust: float, timestamp: float, red_environment: bool) -> float:
    """维护发车阶段的可信白线记忆。

    功能：白线短暂丢失时继续使用最近一次可信白线，避免 fake road center 抢回主目标。
    参数：`obs` 是本帧观测，`line_trust` 是本帧白线融合强度，`timestamp` 和 `red_environment` 限制记忆窗口。
    返回：可用于本帧的白线融合强度。
    逻辑：只记住已经通过信任门控的右侧发车白线；窗口外或记忆耗尽后自动失效。
    """

    global _LINE_MEMORY_FRAMES, _LINE_MEMORY_OFFSET, _LINE_MEMORY_HEADING, _LINE_MEMORY_CONFIDENCE

    in_startup = red_environment and timestamp <= ESTIMATOR_PROFILE["line_startup_until"]
    startup_line = (
        ESTIMATOR_PROFILE["line_startup_offset_min"]
        <= obs.line_offset
        <= ESTIMATOR_PROFILE["line_startup_offset_max"]
        and ESTIMATOR_PROFILE["line_startup_heading_min"]
        <= obs.line_heading
        <= ESTIMATOR_PROFILE["line_startup_heading_max"]
    )
    if line_trust > 0.0 and in_startup and startup_line:
        _LINE_MEMORY_FRAMES = int(ESTIMATOR_PROFILE["line_startup_memory_frames"])
        _LINE_MEMORY_OFFSET = clamp(float(obs.line_offset), -1.0, 1.0)
        _LINE_MEMORY_HEADING = clamp(float(obs.line_heading), -1.0, 1.0)
        _LINE_MEMORY_CONFIDENCE = clamp(float(obs.line_confidence), 0.0, 1.0)
        return line_trust

    if not in_startup or _LINE_MEMORY_FRAMES <= 0:
        if not in_startup:
            _LINE_MEMORY_FRAMES = 0
        return line_trust

    _LINE_MEMORY_FRAMES -= 1
    _LINE_MEMORY_OFFSET *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    _LINE_MEMORY_HEADING *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    _LINE_MEMORY_CONFIDENCE *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    obs.line_offset = _LINE_MEMORY_OFFSET
    obs.line_heading = _LINE_MEMORY_HEADING
    obs.line_confidence = _LINE_MEMORY_CONFIDENCE
    remembered_trust = _line_target_trust(obs, timestamp, red_environment)
    return clamp(remembered_trust * ESTIMATOR_PROFILE["line_startup_memory_trust_scale"], 0.0, 1.0)


def _line_guidance_targets(obs: PerceptionObs) -> tuple[float, float]:
    """把白线 offset/heading 转成主几何链路可用的方向目标。

    功能：在车明显偏离白线时，让 offset 回中优先于弯中斜率。
    参数：`obs` 提供白线 offset 和 heading。
    返回：削弱后的 `line_heading` 与 `projected_lookahead`。
    逻辑：R027 第一个左弯里，白线在车右侧（offset>0）但虚线向左弯（heading<0）。
    若直接融合 heading/lookahead，会继续左打并撞左栏。offset 足够大且与 heading 反号时，
    heading 只作弱参考，lookahead 保持在 offset 同侧，用于把车先拉回白线附近。
    """

    line_offset = clamp(float(obs.line_offset), -1.0, 1.0)
    line_heading = clamp(float(obs.line_heading), -1.0, 1.0)
    projected = line_offset + line_heading * ESTIMATOR_PROFILE["line_lookahead_projection"]
    conflict = (
        abs(line_offset) >= ESTIMATOR_PROFILE["line_offset_priority_min"]
        and line_offset * line_heading < 0.0
    )
    if conflict:
        line_heading *= ESTIMATOR_PROFILE["line_conflict_heading_scale"]
        min_projected = abs(line_offset) * ESTIMATOR_PROFILE["line_conflict_projected_scale"]
        projected = math.copysign(max(abs(projected), min_projected), line_offset)
    return clamp(line_heading, -1.0, 1.0), clamp(projected, -1.0, 1.0)


def _apply_line_target(
    lateral_error: float,
    heading_error: float,
    lookahead_error: float,
    obs: PerceptionObs,
    line_trust: float,
) -> tuple[float, float, float]:
    """白线可信时，把道路中心估计融合到白线目标上。"""

    if line_trust <= 0.0:
        return lateral_error, heading_error, lookahead_error
    lateral_weight = line_trust * ESTIMATOR_PROFILE["line_lateral_weight"]
    heading_weight = line_trust * ESTIMATOR_PROFILE["line_heading_weight"]
    lookahead_weight = line_trust * ESTIMATOR_PROFILE["line_lookahead_weight"]
    line_heading, projected_lookahead = _line_guidance_targets(obs)
    return (
        clamp(lateral_error * (1.0 - lateral_weight) + obs.line_offset * lateral_weight, -1.0, 1.0),
        clamp(heading_error * (1.0 - heading_weight) + line_heading * heading_weight, -1.0, 1.0),
        clamp(lookahead_error * (1.0 - lookahead_weight) + projected_lookahead * lookahead_weight, -1.0, 1.0),
    )


def _line_only_track(obs: PerceptionObs, timestamp: float, red_environment: bool, line_trust: float) -> TrackState:
    """在 road mask 不可信但白线可信时生成路线状态。

    功能：避免 fake road center 把车带到路外；无可靠 road 时仍让车朝白线回中。
    参数：`obs` 提供白线，`timestamp` 是当前时间，`red_environment` 表示场地，`line_trust` 是融合强度。
    返回：非 lost 的 `TrackState`。
    逻辑：只用白线 offset/heading 生成近处和前瞻目标，边界余量沿用上一帧，曲率收 0。
    """

    del timestamp
    confidence = clamp(
        max(ESTIMATOR_PROFILE["lost_confidence"] + 0.04, obs.line_confidence * ESTIMATOR_PROFILE["line_target_confidence_scale"]),
        0.0,
        1.0,
    )
    line_heading, projected_lookahead = _line_guidance_targets(obs)
    lateral_error = clamp(obs.line_offset * line_trust, -1.0, 1.0)
    heading_error = clamp(line_heading * line_trust, -1.0, 1.0)
    lookahead_error = clamp(projected_lookahead * line_trust, -1.0, 1.0)
    alpha = _smooth_alpha(confidence)
    track = TrackState(
        _smooth_limited(_LAST_TRACK.lateral_error, lateral_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        _smooth_limited(_LAST_TRACK.heading_error, heading_error, alpha, ESTIMATOR_PROFILE["max_heading_delta"]),
        _smooth_limited(_LAST_TRACK.curvature, 0.0, ESTIMATOR_PROFILE["curve_smooth_alpha"], ESTIMATOR_PROFILE["max_curvature_delta"]),
        _smooth_limited(_LAST_TRACK.lookahead_error, lookahead_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        confidence,
        False,
        red_environment,
        clamp(float(obs.line_offset), -1.0, 1.0),
        clamp(float(obs.line_heading), -1.0, 1.0),
        clamp(float(obs.line_confidence), 0.0, 1.0),
        _LAST_TRACK.left_margin_near,
        _LAST_TRACK.right_margin_near,
        bool(obs.near_obstacle),
        clamp(float(obs.obstacle_x), -1.0, 1.0),
        max(float(obs.obstacle_size), 0.0),
        obs.frame_motion,
    )
    return track


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
    global _LINE_MEMORY_FRAMES, _LINE_MEMORY_OFFSET, _LINE_MEMORY_HEADING, _LINE_MEMORY_CONFIDENCE
    _LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
    _LAST_TIMESTAMP = None
    _LAST_RED_ENVIRONMENT = False
    _RED_ENVIRONMENT_STREAK = 0
    _LINE_MEMORY_FRAMES = 0
    _LINE_MEMORY_OFFSET = 0.0
    _LINE_MEMORY_HEADING = 0.0
    _LINE_MEMORY_CONFIDENCE = 0.0


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
    line_trust = _line_target_trust(obs, timestamp, red_environment)
    line_trust = _update_line_memory(obs, line_trust, timestamp, red_environment)

    points = _clean_points(obs.center_points)
    if len(points) < ESTIMATOR_PROFILE["min_center_points"] or obs.confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = (
            _line_only_track(obs, timestamp, red_environment, line_trust)
            if line_trust > 0.0
            else _lost_track(obs.confidence, red_environment, obs)
        )
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    x_norm, progress, y_span = _normalize_points(points)
    if y_span < ESTIMATOR_PROFILE["min_y_span"]:
        track = _lost_track(obs.confidence, red_environment, obs)
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
    lateral_error, heading_error, lookahead_error = _apply_line_target(
        lateral_error,
        heading_error,
        lookahead_error,
        obs,
        line_trust,
    )
    fit_score = _fit_error_score(progress, x_norm, coeffs)
    curvature_trust = _curvature_trust(len(points), y_span, fit_score)
    curvature = _curvature_from_fit(coeffs, degree, lateral_error, lookahead_error, curvature_trust)
    left_margin_near = _near_edge_margin(obs.left_edge_points, "left")
    right_margin_near = _near_edge_margin(obs.right_edge_points, "right")

    confidence = _geometry_confidence(obs, points, y_span, fit_score)
    if line_trust > 0.0:
        confidence = max(confidence, obs.line_confidence * ESTIMATOR_PROFILE["line_target_confidence_scale"])

    # 红色环境（complex 赛道）感知难度更大，自然置信度偏低，
    # 给小幅加成减少误丢线，但仅在几何本身不算太差时生效。
    if red_environment and confidence > ESTIMATOR_PROFILE["lost_confidence"] * 0.6:
        confidence = min(confidence + 0.08, 1.0)

    if confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = _lost_track(confidence, red_environment, obs)
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
        clamp(float(obs.line_offset), -1.0, 1.0),
        clamp(float(obs.line_heading), -1.0, 1.0),
        clamp(float(obs.line_confidence), 0.0, 1.0),
        left_margin_near,
        right_margin_near,
        bool(obs.near_obstacle),
        clamp(float(obs.obstacle_x), -1.0, 1.0),
        max(float(obs.obstacle_size), 0.0),
        obs.frame_motion,
    )
    _LAST_TRACK = track
    _LAST_TIMESTAMP = timestamp
    return track
