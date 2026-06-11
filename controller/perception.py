"""视觉感知模块。

功能概述：从左右摄像头图像中分割道路表面，并沿扫描线跟踪可行驶走廊。
输入输出：输入 BGR 图像和可选时间戳，输出 `PerceptionObs`。
处理流程：估计道路颜色，生成道路 mask，逐行选择连续走廊，再融合左右摄像头结果。
"""

from dataclasses import dataclass

import cv2
import numpy as np

from controller.common import PerceptionObs, clamp
from controller.opponent import detect_near_vehicle_obstacle
from controller.params import OPPONENT_PROFILE, VISION_PROFILE

_RED_ENVIRONMENT_FLAG = 32


@dataclass
class _CameraScan:
    """单侧摄像头扫描结果。

    功能：保存单张图像的中心点、边界点、道路宽度、置信度和调试标记。
    参数：字段由 `_scan_image()` 生成。
    返回：内部 dataclass。
    逻辑：融合阶段只读取这些稳定字段，不依赖扫描过程的中间变量。
    """

    center_points: np.ndarray
    left_edge_points: np.ndarray
    right_edge_points: np.ndarray
    road_width_est: float
    confidence: float
    debug_flags: int = 0


def _empty_points() -> np.ndarray:
    return np.empty((0, 2), dtype=np.float32)


def _empty_scan(debug_flags: int = 1) -> _CameraScan:
    points = _empty_points()
    return _CameraScan(points, points, points, 0.0, 0.0, debug_flags=debug_flags)


def _empty_obs(debug_flags: int = 1) -> PerceptionObs:
    points = _empty_points()
    return PerceptionObs(points, points, points, 0.0, 0.0, debug_flags=debug_flags)


def _valid_image(image) -> bool:
    """检查输入是否是三通道 BGR 图像。"""

    return image is not None and hasattr(image, "shape") and len(image.shape) == 3 and image.shape[2] == 3


def _road_color_from_patch(lab_roi: np.ndarray) -> np.ndarray:
    """估计道路表面 Lab 颜色。

    功能：从 ROI 底部中心 patch 估计道路颜色。
    参数：`lab_roi` 是中下部 ROI 的 Lab 图像。
    返回：三通道 Lab 中位数颜色。
    逻辑：中位数能降低车道线、阴影和零星高光对颜色估计的影响。
    """

    height, width = lab_roi.shape[:2]
    y0 = int(height * 0.72)
    y1 = max(y0 + 1, int(height * 0.96))
    x_margin = int(width * 0.18)
    x0 = max(width // 2 - x_margin, 0)
    x1 = min(width // 2 + x_margin, width)
    patch = lab_roi[y0:y1, x0:x1]
    return np.median(patch.reshape(-1, 3).astype(np.float32), axis=0)


def _is_red_environment(image: np.ndarray) -> bool:
    """判断当前摄像头是否处在 complex 的红色场地环境。"""

    height = image.shape[0]
    roi = image[int(height * 0.30) : int(height * 0.88), :]
    if roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red = ((hue < 12) | (hue > 168)) & (saturation > 80) & (value > 50)
    red_ratio = float(np.count_nonzero(red)) / max(float(red.size), 1.0)
    return red_ratio >= VISION_PROFILE["red_world_min_ratio"]


def _build_masks(image: np.ndarray, timestamp=None) -> tuple[np.ndarray, np.ndarray, float, float, bool]:
    """生成道路表面 mask 和边缘 fallback mask。

    功能：优先用暗灰低饱和特征分割沥青路面，并单独保留 Canny 边缘作为兜底。
    参数：`image` 是单张 BGR 图像。
    返回：完整尺寸的 `road_mask`、`edge_mask`、灰度纹理分数、主 mask 命中率和近处障碍标记。
    逻辑：暗灰 mask 分割低饱和灰色沥青；草地是高饱和绿，统一从道路 mask 扣除，
    避免颜色种子落在草上时把整片草当成路；边缘不混入主 mask，避免把背景强边缘误当成道路表面。
    """

    height = image.shape[0]
    top = int(height * VISION_PROFILE["roi_top_ratio"])
    roi = image[top:, :, :]

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    dark_road_roi = (
        (gray_roi >= VISION_PROFILE["road_gray_min"])
        & (gray_roi <= VISION_PROFILE["road_gray_max"])
        & (hsv_roi[:, :, 1] <= VISION_PROFILE["road_sat_max"])
    ).astype(np.uint8) * 255

    # 草地 mask：高饱和绿。沥青是低饱和灰，必不落在此区间；用于从道路 mask 中扣除草地。
    grass_roi = (
        (hsv_roi[:, :, 0] >= VISION_PROFILE["grass_hue_min"])
        & (hsv_roi[:, :, 0] <= VISION_PROFILE["grass_hue_max"])
        & (hsv_roi[:, :, 1] >= VISION_PROFILE["grass_sat_min"])
        & (hsv_roi[:, :, 2] >= VISION_PROFILE["grass_value_min"])
    )

    lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    road_lab = _road_color_from_patch(lab_roi)
    distance = np.sqrt(np.sum((lab_roi - road_lab) ** 2, axis=2))
    color_roi = (distance <= VISION_PROFILE["road_lab_threshold"]).astype(np.uint8) * 255

    dark_fill_ratio = float(np.count_nonzero(dark_road_roi)) / max(float(dark_road_roi.size), 1.0)
    if dark_fill_ratio >= VISION_PROFILE["dark_mask_min_fill"]:
        road_roi = dark_road_roi.copy()
    else:
        # 暗沥青 mask 稀疏（远处只剩细条路面）才回退颜色 mask；并入暗 mask 保住那条沥青，
        # 颜色种子可能落在草上，靠下一步扣草兜底。
        road_roi = color_roi | dark_road_roi

    # 统一扣除草地：无论用哪条 mask，草都不算路。偏出赛道正对草地时 mask 会塌到近空 → 低置信 → lost。
    road_roi[grass_roi] = 0

    # checkpoint 蓝色门是半透明、横跨在赛道上的——门后就是可行驶路面。把门并入道路 mask，
    # 避免它把走廊在中段截断（弯道里只剩近处点 → edge fallback → 朝栏杆打/剐蹭）。
    # 注意：这会让部分含天空的帧 mask 饱和 → 被判 lost，离线 per-frame lost 率会明显升高。
    # 但 lost 时车是直线滑行（不停车、不偏出），这是良性的——实车验证（R005/C003）是迄今最好
    # 的一版：蓝门前大拐弯和过弯剐蹭都消失。**不要用离线 lost 率否决这版**（详见 notes.md R005）。
    barrier_roi = (
        (hsv_roi[:, :, 0] >= VISION_PROFILE["barrier_hue_min"])
        & (hsv_roi[:, :, 0] <= VISION_PROFILE["barrier_hue_max"])
        & (hsv_roi[:, :, 1] >= VISION_PROFILE["barrier_sat_min"])
        & (hsv_roi[:, :, 2] >= VISION_PROFILE["barrier_value_min"])
        & (hsv_roi[:, :, 2] <= VISION_PROFILE["barrier_value_max"])
    )
    road_roi[barrier_roi] = 255

    kernel = np.ones((5, 5), dtype=np.uint8)
    road_roi = cv2.morphologyEx(road_roi, cv2.MORPH_OPEN, kernel, iterations=1)
    road_roi = cv2.morphologyEx(road_roi, cv2.MORPH_CLOSE, kernel, iterations=2)

    blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    edge_roi = cv2.Canny(blurred, 45, 120)

    road_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    edge_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    road_mask[top:, :] = road_roi
    edge_mask[top:, :] = edge_roi

    texture_score = clamp(float(np.std(gray_roi)) / VISION_PROFILE["texture_gray_std_scale"], 0.0, 1.0)
    mask_fill_ratio = float(np.count_nonzero(road_roi)) / max(float(road_roi.size), 1.0)
    near_obstacle = False
    if OPPONENT_PROFILE["enable_opponent_avoidance"]:
        try:
            current_time = float(timestamp)
        except (TypeError, ValueError):
            current_time = 0.0
        near_obstacle = (
            current_time >= OPPONENT_PROFILE["near_obstacle_min_timestamp"]
            and detect_near_vehicle_obstacle(image, OPPONENT_PROFILE)
        )
    return road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle


def _segments_from_active(active: np.ndarray) -> list[tuple[int, int]]:
    """把一维布尔扫描结果转成连续区间。"""

    if active.size == 0:
        return []
    padded = np.concatenate(([False], active.astype(bool), [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(changes[i]), int(changes[i + 1] - 1)) for i in range(0, len(changes), 2)]


def _merge_close_segments(segments: list[tuple[int, int]], max_gap: int | None = None) -> list[tuple[int, int]]:
    """合并被车道虚线或护栏细缝切开的相邻道路段。"""

    if not segments:
        return []
    if max_gap is None:
        max_gap = int(VISION_PROFILE["max_segment_gap"])
    merged = [segments[0]]
    for left, right in segments[1:]:
        prev_left, prev_right = merged[-1]
        if left - prev_right - 1 <= max_gap:
            merged[-1] = (prev_left, right)
        else:
            merged.append((left, right))
    return merged


def _road_segments(mask: np.ndarray, y: int, row_band: int, max_gap: int | None = None) -> list[tuple[int, int]]:
    """从道路 mask 的水平横带中提取连续道路区间。"""

    y0 = max(int(y) - row_band, 0)
    y1 = min(int(y) + row_band + 1, mask.shape[0])
    band = mask[y0:y1, :]
    min_hits = max(1, int(np.ceil(band.shape[0] * 0.45)))
    active = np.count_nonzero(band, axis=0) >= min_hits
    return _merge_close_segments(_segments_from_active(active), max_gap=max_gap)


def _edge_fallback_segments(edge_mask: np.ndarray, y: int, row_band: int) -> list[tuple[int, int]]:
    """从边缘横带中推断候选走廊。

    功能：在道路 mask 没有可用区间时，用相邻边缘之间的区域做兜底。
    参数：`edge_mask` 是 Canny 结果，`y` 是扫描线，`row_band` 是横带半宽。
    返回：候选 `(left, right)` 区间。
    逻辑：只取相邻边缘，避免随机纹理生成大量跨越式组合。
    """

    y0 = max(int(y) - row_band, 0)
    y1 = min(int(y) + row_band + 1, edge_mask.shape[0])
    band = edge_mask[y0:y1, :]
    active = np.count_nonzero(band, axis=0) > 0
    edge_segments = _segments_from_active(active)
    if len(edge_segments) < 2:
        return []

    edge_centers = [int((left + right) * 0.5) for left, right in edge_segments]
    return [(edge_centers[index], edge_centers[index + 1]) for index in range(len(edge_centers) - 1)]


def _filter_segments(
    segments: list[tuple[int, int]],
    width: int,
    max_width_ratio: float | None = None,
) -> list[tuple[int, int]]:
    """按道路宽度约束过滤候选区间。"""

    min_width = float(VISION_PROFILE["min_segment_width"])
    if max_width_ratio is None:
        max_width_ratio = VISION_PROFILE["max_segment_width_ratio"]
    max_width = float(width) * float(max_width_ratio)
    filtered = []
    for left, right in segments:
        segment_width = float(right - left + 1)
        if min_width <= segment_width <= max_width:
            filtered.append((left, right))
    return filtered


def _filter_fallback_segments(
    segments: list[tuple[int, int]],
    width: int,
    previous_center: float,
    has_previous: bool,
) -> list[tuple[int, int]]:
    """过滤容易由白线碎片生成的窄 fallback 走廊。

    功能：避免近处孤立车道线/接缝小段把扫描 seed 拉到内侧。
    参数：`segments` 是边缘 fallback 候选，`previous_center` 是上一条中心。
    返回：过滤后的候选区间。
    逻辑：宽 fallback 正常保留；窄 fallback 只有在靠近画面中心或延续上一中心时才可用。
    """

    if not segments:
        return []

    min_width = float(VISION_PROFILE["fallback_min_segment_width"])
    initial_center_limit = float(width) * VISION_PROFILE["fallback_initial_center_max_offset"]
    narrow_jump_limit = float(width) * VISION_PROFILE["fallback_narrow_jump_max_ratio"]
    image_center = float(width) * 0.5

    filtered = []
    for left, right in segments:
        segment_width = float(right - left + 1)
        center = (float(left) + float(right)) * 0.5
        if segment_width >= min_width:
            filtered.append((left, right))
        elif not has_previous and abs(center - image_center) <= initial_center_limit:
            filtered.append((left, right))
        elif has_previous and abs(center - previous_center) <= narrow_jump_limit:
            filtered.append((left, right))
    return filtered


def _localize_wide_segment(
    segment: tuple[int, int],
    previous_center: float,
    width: int,
    enabled: bool = True,
) -> tuple[int, int]:
    """把过宽道路段截成上一扫描中心附近的局部走廊。

    功能：处理复合弯中多条道路被暗色 mask 连成一片的情况。
    参数：`segment` 是候选暗区，`previous_center` 是近处已选中心，`width` 是图像宽度。
    返回：可能被截窄后的 `(left, right)`。
    逻辑：正常宽度道路不处理；过宽时保留靠近上一中心的一段，避免用整块暗区中心。
    """

    left, right = segment
    segment_width = float(right - left + 1)
    if not enabled:
        return segment
    if segment_width <= float(width) * VISION_PROFILE["wide_segment_localize_ratio"]:
        return segment

    target_width = max(
        VISION_PROFILE["min_segment_width"],
        float(width) * VISION_PROFILE["wide_segment_window_ratio"],
    )
    half = target_width * 0.5
    center = previous_center
    center = clamp(center, float(left) + half, float(right) - half)
    localized_left = max(left, int(round(center - half)))
    localized_right = min(right, int(round(center + half)))
    if localized_right <= localized_left:
        return segment
    return localized_left, localized_right


def _pick_segment(
    road_mask: np.ndarray,
    edge_mask: np.ndarray,
    y: int,
    previous_center: float,
    has_previous: bool,
    near_obstacle: bool,
    wide_localize_enabled: bool,
) -> tuple[tuple[int, int] | None, bool]:
    """选择当前扫描线的最佳走廊 segment。

    功能：优先从道路表面 mask 选连续区间，失败时再用边缘区间兜底。
    参数：`road_mask` 和 `edge_mask` 是完整尺寸 mask，`previous_center` 是上一条有效扫描线中心。
    返回：选中的 `(left, right)` 和是否使用边缘 fallback。
    逻辑：候选区间必须满足宽度约束，并尽量靠近上一条有效扫描线。
    """

    width = road_mask.shape[1]
    row_band = int(VISION_PROFILE["row_band"])
    max_width_ratio = (
        VISION_PROFILE["max_segment_width_ratio"]
        if wide_localize_enabled
        else VISION_PROFILE["early_max_segment_width_ratio"]
    )
    max_gap = None
    if near_obstacle and y >= int(road_mask.shape[0] * OPPONENT_PROFILE["near_obstacle_scan_y_ratio"]):
        max_gap = int(OPPONENT_PROFILE["near_obstacle_segment_gap"])
    candidates = _filter_segments(
        _road_segments(road_mask, y, row_band, max_gap=max_gap),
        width,
        max_width_ratio=max_width_ratio,
    )
    used_fallback = False
    if not candidates:
        candidates = _filter_segments(
            _edge_fallback_segments(edge_mask, y, row_band),
            width,
            max_width_ratio=max_width_ratio,
        )
        candidates = _filter_fallback_segments(candidates, width, previous_center, has_previous)
        used_fallback = bool(candidates)
    if not candidates:
        return None, used_fallback

    best = min(candidates, key=lambda item: abs(((item[0] + item[1]) * 0.5) - previous_center))
    best = _localize_wide_segment(best, previous_center, width, enabled=wide_localize_enabled)
    center = (best[0] + best[1]) * 0.5
    max_jump = float(width) * VISION_PROFILE["max_center_jump_ratio"]
    if has_previous and abs(center - previous_center) > max_jump:
        return None, used_fallback
    return best, used_fallback


def _score_scan(
    centers: list[tuple[float, float]],
    widths: list[float],
    texture_score: float,
    mask_fill_ratio: float,
    fallback_count: int,
) -> tuple[float, int]:
    """计算单侧摄像头置信度。

    功能：综合有效扫描线、宽度稳定性、中心稳定性和纹理分数。
    参数：扫描点、宽度序列、纹理分数、mask 命中率和 fallback 次数。
    返回：置信度和调试标记。
    逻辑：有效线太少、整图近似全不命中时重降权；饱和 mask 保留中等降权，
    避免远处路面可见但底部草地铺满 ROI 时整段丢线。
    """

    debug_flags = 0
    scan_count = float(VISION_PROFILE["scan_count"])
    valid_count = len(centers)
    valid_ratio = valid_count / max(scan_count, 1.0)

    width_arr = np.array(widths, dtype=np.float32)
    width_median = max(float(np.median(width_arr)), 1.0)
    width_stability = clamp(1.0 - float(np.std(width_arr)) / width_median, 0.0, 1.0)

    center_arr = np.array([point[0] for point in centers], dtype=np.float32)
    if center_arr.size >= 2:
        center_jump = np.abs(np.diff(center_arr))
        center_stability = clamp(
            1.0 - float(np.mean(center_jump)) / (640.0 * VISION_PROFILE["max_center_jump_ratio"]),
            0.0,
            1.0,
        )
    else:
        center_stability = 0.0

    confidence = (
        valid_ratio * 0.38
        + width_stability * 0.22
        + center_stability * 0.22
        + texture_score * 0.18
    )

    min_valid = int(VISION_PROFILE["min_valid_scans"])
    if valid_count < min_valid:
        confidence *= valid_count / max(float(min_valid), 1.0)
        debug_flags |= 1
    if mask_fill_ratio < 0.015:
        confidence *= VISION_PROFILE["empty_mask_confidence_scale"]
        debug_flags |= 4
    elif mask_fill_ratio > 0.92:
        confidence *= VISION_PROFILE["saturated_mask_confidence_scale"]
        debug_flags |= 4
    if fallback_count:
        confidence *= max(0.55, 1.0 - 0.06 * fallback_count)
        debug_flags |= 2

    return clamp(confidence, 0.0, 1.0), debug_flags


def _scan_image(image: np.ndarray, timestamp=None) -> _CameraScan:
    """按扫描线跟踪单张图像的道路走廊。

    功能：输出中心点、左右边界点、道路宽度和置信度。
    参数：`image` 是单个摄像头 BGR 图像，`timestamp` 用于限制末段障碍处理。
    返回：`_CameraScan`。
    逻辑：从近处向远处扫描，每条线选择离上一条有效中心最近的连续道路 segment。
    """

    if not _valid_image(image):
        return _empty_scan()

    road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle = _build_masks(image, timestamp)
    red_environment = _is_red_environment(image)
    wide_localize_enabled = red_environment
    height, width = road_mask.shape
    rows = np.linspace(
        int(height * VISION_PROFILE["scan_bottom_ratio"]),
        int(height * VISION_PROFILE["scan_top_ratio"]),
        int(VISION_PROFILE["scan_count"]),
        dtype=np.int32,
    )

    centers = []
    left_edges = []
    right_edges = []
    widths = []
    previous_center = width * 0.5
    has_previous = False
    fallback_count = 0

    for y in rows:
        segment, used_fallback = _pick_segment(
            road_mask,
            edge_mask,
            int(y),
            previous_center,
            has_previous,
            near_obstacle,
            wide_localize_enabled,
        )
        if segment is None:
            continue
        left, right = segment
        center = (left + right) * 0.5
        road_width = float(right - left + 1)
        centers.append((center, float(y)))
        left_edges.append((float(left), float(y)))
        right_edges.append((float(right), float(y)))
        widths.append(road_width)
        previous_center = center
        has_previous = True
        if used_fallback:
            fallback_count += 1

    if not centers:
        debug_flags = 4 if mask_fill_ratio < 0.015 or mask_fill_ratio > 0.92 else 1
        return _empty_scan(debug_flags=debug_flags)

    confidence, debug_flags = _score_scan(centers, widths, texture_score, mask_fill_ratio, fallback_count)
    if red_environment:
        debug_flags |= _RED_ENVIRONMENT_FLAG
    return _CameraScan(
        np.array(centers, dtype=np.float32),
        np.array(left_edges, dtype=np.float32),
        np.array(right_edges, dtype=np.float32),
        float(np.median(np.array(widths, dtype=np.float32))),
        confidence,
        debug_flags=debug_flags,
    )


def _usable(scan: _CameraScan) -> bool:
    """判断单侧扫描结果是否足以参与融合。"""

    return scan.center_points.size > 0 and scan.confidence >= VISION_PROFILE["min_camera_confidence"]


def _near_center(scan: _CameraScan) -> float:
    """读取最靠近车辆的扫描中心。"""

    if scan.center_points.size == 0:
        return 320.0
    return float(scan.center_points[0, 0])


def _to_obs(scan: _CameraScan, debug_flags: int | None = None) -> PerceptionObs:
    """把单侧扫描结果转换为公开观测结构。"""

    flags = scan.debug_flags if debug_flags is None else debug_flags
    return PerceptionObs(
        scan.center_points,
        scan.left_edge_points,
        scan.right_edge_points,
        scan.road_width_est,
        clamp(scan.confidence, 0.0, 1.0),
        debug_flags=flags,
    )


def _fuse_scans(left_scan: _CameraScan, right_scan: _CameraScan) -> PerceptionObs:
    """融合左右摄像头扫描结果。

    功能：根据单侧可用性、近处中心一致性和置信度选择或合并观测。
    参数：`left_scan` 和 `right_scan` 是两侧扫描结果。
    返回：融合后的 `PerceptionObs`。
    逻辑：单侧有效时直接使用；双侧冲突时选高置信度；一致时合并点集并平均置信度。
    """

    left_ok = _usable(left_scan)
    right_ok = _usable(right_scan)
    if left_ok and not right_ok:
        return _to_obs(left_scan)
    if right_ok and not left_ok:
        return _to_obs(right_scan)
    if not left_ok and not right_ok:
        return _empty_obs(debug_flags=left_scan.debug_flags | right_scan.debug_flags | 1)

    center_gap = abs(_near_center(left_scan) - _near_center(right_scan))
    merge_gap = 640.0 * VISION_PROFILE["fusion_merge_gap"]
    merge_confidence = VISION_PROFILE["fusion_merge_min_confidence"]
    confidence_gap = abs(left_scan.confidence - right_scan.confidence)
    if (
        center_gap >= merge_gap
        or left_scan.confidence < merge_confidence
        or right_scan.confidence < merge_confidence
    ):
        chosen = left_scan if left_scan.confidence >= right_scan.confidence else right_scan
        flags = chosen.debug_flags
        if center_gap > 640.0 * VISION_PROFILE["fusion_max_offset_gap"]:
            flags |= 8
        if confidence_gap < VISION_PROFILE["fusion_confidence_margin"]:
            flags |= 16
        return _to_obs(chosen, debug_flags=flags)

    center_points = np.concatenate([left_scan.center_points, right_scan.center_points], axis=0)
    left_edge_points = np.concatenate([left_scan.left_edge_points, right_scan.left_edge_points], axis=0)
    right_edge_points = np.concatenate([left_scan.right_edge_points, right_scan.right_edge_points], axis=0)
    weights = np.array([len(left_scan.center_points), len(right_scan.center_points)], dtype=np.float32)
    confidences = np.array([left_scan.confidence, right_scan.confidence], dtype=np.float32)
    width_values = np.array([left_scan.road_width_est, right_scan.road_width_est], dtype=np.float32)
    confidence = float(np.average(confidences, weights=weights))
    road_width_est = float(np.average(width_values, weights=weights))
    return PerceptionObs(
        center_points,
        left_edge_points,
        right_edge_points,
        road_width_est,
        clamp(confidence, 0.0, 1.0),
        debug_flags=left_scan.debug_flags | right_scan.debug_flags,
    )


def extract_observation(left_img, right_img, timestamp=None) -> PerceptionObs:
    """提取左右摄像头的赛道观测。

    功能：输出中心点、边界点、道路宽度估计和感知置信度。
    参数：`left_img` 与 `right_img` 是平台传入的 BGR 图像，`timestamp` 预留给后续时间上下文。
    返回：`PerceptionObs`。
    逻辑：分别扫描左右图像；单侧有效则使用单侧，双侧一致则合并，双侧冲突则选择高置信度结果。
    """

    left_scan = _scan_image(left_img, timestamp) if _valid_image(left_img) else _empty_scan()
    right_scan = _scan_image(right_img, timestamp) if _valid_image(right_img) else _empty_scan()
    return _fuse_scans(left_scan, right_scan)
