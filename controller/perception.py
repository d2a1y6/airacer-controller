"""视觉感知模块。

功能概述：从左右摄像头图像中分割道路表面，并沿扫描线跟踪可行驶走廊。
输入输出：输入 BGR 图像和可选时间戳，输出 `PerceptionObs`。
处理流程：估计道路颜色，生成道路 mask，逐行选择连续走廊，再融合左右摄像头结果。
"""

from dataclasses import dataclass

import cv2
import numpy as np

from controller.common import PerceptionObs, clamp
from controller.opponent import detect_near_vehicle_obstacle_state
from controller.params import COLOR_PROFILE, LINE_FOLLOW_PROFILE, OPPONENT_PROFILE, VISION_PROFILE

_RED_ENVIRONMENT_FLAG = 32

# 跨帧轨迹记忆：存储上一帧的扫描中心点，用于在道路合并（超宽段）时
# 通过时间连续性区分正确道路和干扰道路（如 complex CP3 区域）。
_LAST_FRAME_CENTERS: list[tuple[float, float]] | None = None
_LAST_FRAME_TIMESTAMP: float | None = None


def _save_frame_centers(centers: list[tuple[float, float]]) -> None:
    """保存本帧扫描中心，供下一帧跨帧锚定使用。"""
    global _LAST_FRAME_CENTERS
    if not centers:
        _LAST_FRAME_CENTERS = None
    else:
        _LAST_FRAME_CENTERS = list(centers)


def _maybe_reset_perception_by_timestamp(timestamp: float | None) -> None:
    """时间戳回退或跳跃过大时清空跨帧记忆。"""
    global _LAST_FRAME_CENTERS, _LAST_FRAME_TIMESTAMP
    if timestamp is None:
        _LAST_FRAME_CENTERS = None
        _LAST_FRAME_TIMESTAMP = None
        return
    if _LAST_FRAME_TIMESTAMP is not None:
        elapsed = float(timestamp) - float(_LAST_FRAME_TIMESTAMP)
        if elapsed < 0.0 or elapsed > 2.0:
            _LAST_FRAME_CENTERS = None
    _LAST_FRAME_TIMESTAMP = float(timestamp)


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
    near_obstacle: bool = False
    obstacle_x: float = 0.0
    obstacle_size: float = 0.0


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


def _hue_delta(hue: np.ndarray, center: float) -> np.ndarray:
    """计算 OpenCV HSV hue 的环形距离。"""

    delta = np.abs(hue.astype(np.float32) - float(center))
    return np.minimum(delta, 180.0 - delta)


def _sampled_color_mask(hsv: np.ndarray, lab: np.ndarray, color_name: str) -> np.ndarray:
    """按采样色卡生成颜色 mask。

    功能：把 Webots 原始帧采样得到的 HSV/Lab 中位数和容差转换成布尔 mask。
    参数：`hsv`、`lab` 是同一 ROI 的 OpenCV 颜色空间图，`color_name` 是 `COLOR_PROFILE` 键。
    返回：命中该颜色类别的布尔数组。
    逻辑：hue 用环形距离；Lab 同时约束亮度和色度，避免浅灰路牙/栏杆混进深灰沥青。
    """

    profile = COLOR_PROFILE[color_name]
    hsv_center = profile["hsv_median"]
    hsv_tol = profile["hsv_tolerance"]
    lab_center = profile["lab_median"]
    lab_tol = profile["lab_tolerance"]
    hsv_match = (
        (_hue_delta(hsv[:, :, 0], hsv_center[0]) <= hsv_tol[0])
        & (np.abs(hsv[:, :, 1].astype(np.float32) - hsv_center[1]) <= hsv_tol[1])
        & (np.abs(hsv[:, :, 2].astype(np.float32) - hsv_center[2]) <= hsv_tol[2])
    )
    lab_match = (
        (np.abs(lab[:, :, 0] - lab_center[0]) <= lab_tol[0])
        & (np.abs(lab[:, :, 1] - lab_center[1]) <= lab_tol[1])
        & (np.abs(lab[:, :, 2] - lab_center[2]) <= lab_tol[2])
    )
    return hsv_match & lab_match


def _build_masks(
    image: np.ndarray,
    timestamp=None,
    enable_opp: bool = True,
) -> tuple[np.ndarray, np.ndarray, float, float, bool, float, float]:
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
    lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    bgr_roi = roi.astype(np.float32)
    road_color = COLOR_PROFILE["road_asphalt_dark_gray"]
    b_minus_g = bgr_roi[:, :, 0] - bgr_roi[:, :, 1]
    g_minus_r = bgr_roi[:, :, 1] - bgr_roi[:, :, 2]
    road_core = (
        _sampled_color_mask(hsv_roi, lab_roi, "road_asphalt_dark_gray")
        & (gray_roi >= VISION_PROFILE["road_gray_min"])
        & (gray_roi <= VISION_PROFILE["road_gray_max"])
        & (b_minus_g >= road_color["b_minus_g_min"])
        & (b_minus_g <= road_color["b_minus_g_max"])
        & (g_minus_r >= road_color["g_minus_r_min"])
        & (g_minus_r <= road_color["g_minus_r_max"])
    )
    non_road_roi = (
        _sampled_color_mask(hsv_roi, lab_roi, "green_grass")
        | _sampled_color_mask(hsv_roi, lab_roi, "red_ground")
        | _sampled_color_mask(hsv_roi, lab_roi, "blue_sky")
    )
    # 路牙/路肩与沥青色相接近，但采样显示 Lab 亮度明显更高；只扣高亮部分，避免阴影污染真路面。
    curb_roi = _sampled_color_mask(hsv_roi, lab_roi, "curb_shoulder_light_gray") & (
        lab_roi[:, :, 0] > COLOR_PROFILE["road_asphalt_dark_gray"]["lab_median"][0] + 10.0
    )
    dark_road_roi = (road_core & ~non_road_roi & ~curb_roi).astype(np.uint8) * 255

    road_roi = dark_road_roi.copy()

    # 统一扣除已采样的非路面颜色：草地、红地、天空、栏杆、亮路肩都不算路。
    road_roi[non_road_roi | curb_roi] = 0

    # checkpoint 蓝色门是半透明、横跨在赛道上的——门后就是可行驶路面。把门并入道路 mask，
    # 避免它把走廊在中段截断（弯道里只剩近处点 → edge fallback → 朝栏杆打/剐蹭）。
    # 注意：这会让部分含天空的帧 mask 饱和 → 被判 lost，离线 per-frame lost 率会明显升高。
    # 但 lost 时车是直线滑行（不停车、不偏出），这是良性的——实车验证（R005/C003）是迄今最好
    # 的一版：蓝门前大拐弯和过弯剐蹭都消失。**不要用离线 lost 率否决这版**（详见 notes.md R005）。
    barrier_candidate = (
        (hsv_roi[:, :, 0] >= VISION_PROFILE["barrier_hue_min"])
        & (hsv_roi[:, :, 0] <= VISION_PROFILE["barrier_hue_max"])
        & (hsv_roi[:, :, 1] >= VISION_PROFILE["barrier_sat_min"])
        & (hsv_roi[:, :, 2] >= VISION_PROFILE["barrier_value_min"])
        & (hsv_roi[:, :, 2] <= VISION_PROFILE["barrier_value_max"])
    )
    # 蓝色 checkpoint 门是横跨道路的宽水平带；侧边蓝灰栏杆也是同色系，但只出现在边缘细长区域。
    # 只桥接行内蓝色覆盖足够宽的候选，避免把侧边栏杆直接并入 road mask。
    row_ratio = np.count_nonzero(barrier_candidate, axis=1) / max(float(barrier_candidate.shape[1]), 1.0)
    barrier_rows = row_ratio >= VISION_PROFILE["barrier_bridge_row_ratio"]
    barrier_roi = barrier_candidate & barrier_rows[:, None]
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
    obstacle_x = 0.0
    obstacle_size = 0.0
    # 对手检测只在 with_other_cars profile 下进行（enable_opp）：no_other_cars 沿用 R049 驾驶底座。
    # 既不调用 detect_near_vehicle_obstacle，也不让 near_obstacle 影响 segment_gap/白线门控。
    if enable_opp and OPPONENT_PROFILE["enable_opponent_avoidance"]:
        try:
            current_time = float(timestamp)
        except (TypeError, ValueError):
            current_time = 0.0
        if current_time >= OPPONENT_PROFILE["near_obstacle_min_timestamp"]:
            near_obstacle, obstacle_x, obstacle_size = detect_near_vehicle_obstacle_state(image, OPPONENT_PROFILE)
    return road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle, obstacle_x, obstacle_size


def _segments_from_active(active: np.ndarray) -> list[tuple[int, int]]:
    """把一维布尔扫描结果转成连续区间。"""

    if active.size == 0:
        return []
    padded = np.concatenate(([False], active.astype(bool), [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(changes[i]), int(changes[i + 1] - 1)) for i in range(0, len(changes), 2)]


def _neighbors_are_road(road_cols: np.ndarray, left: int, right: int, profile: dict) -> bool:
    """判断白线段左右紧邻是否都是深灰路面。

    功能：实现"真中心虚线在大片路面中间"的判别——护栏支柱外侧是路牙/红地/草而非路面。
    参数：`road_cols` 是本扫描带内每列是否为深灰路面的布尔数组，`left/right` 是白段列区间。
    返回：两侧侧窗内路面占比都达标时为 True。
    逻辑：紧邻边缘跳过 `context_gap` 像素（抗白色高光外溢），再各取 `context_window` 宽侧窗统计路面占比。
    """

    gap = int(profile["context_gap"])
    window = int(profile["context_window"])
    min_ratio = float(profile["context_min_ratio"])
    width = int(road_cols.shape[0])

    def _side_ratio(start: int, stop: int) -> float:
        start = max(int(start), 0)
        stop = min(int(stop), width)
        if stop - start < 1:
            return 0.0
        return float(np.count_nonzero(road_cols[start:stop])) / float(stop - start)

    left_ratio = _side_ratio(left - gap - window, left - gap)
    right_ratio = _side_ratio(right + gap + 1, right + gap + 1 + window)
    return left_ratio >= min_ratio and right_ratio >= min_ratio


def _camera_line_state(image: np.ndarray, profile: dict) -> tuple[float, float, float] | None:
    """估计单个相机里的白色中心线。

    功能：找连续的窄白色虚线，输出近处偏移、线方向和置信度。
    参数：`image` 是 BGR 图像，`profile` 是白线跟踪参数。
    返回：`(offset, heading, confidence)`；白线不足时返回 None。
    逻辑：逐行找近中性、两侧紧邻深灰路面的短白段，按连续性串起来；排除护栏支柱、车身大白块和孤立噪声。
    """

    if not _valid_image(image):
        return None
    height, width = image.shape[:2]
    lower = int(profile["white_min"])
    chroma_max = float(profile["white_chroma_max"])
    road_dark_min = float(profile["road_dark_min"])
    road_dark_max = float(profile["road_dark_max"])
    road_dark_chroma_max = float(profile["road_dark_chroma_max"])
    y_top = int(height * profile["scan_top_ratio"])
    y_bottom = int(height * profile["scan_bottom_ratio"])
    rows = np.linspace(y_bottom, y_top, int(profile["scan_count"]), dtype=np.int32)
    row_band = int(profile["row_band"])
    min_width = float(profile["min_segment_width"])
    max_width = float(profile["max_segment_width"])
    initial_limit = float(width) * profile["initial_center_max_offset"]
    jump_limit = float(width) * profile["max_center_jump_ratio"]
    image_center = float(width) * 0.5

    points = []
    previous_center = image_center
    has_previous = False
    for y in rows:
        y0 = max(int(y) - row_band, 0)
        y1 = min(int(y) + row_band + 1, height)
        band = image[y0:y1, :, :].astype(np.int16)
        band_min = band.min(axis=2)
        band_max = band.max(axis=2)
        band_chroma = band_max - band_min
        # 白线：亮（最暗通道也够亮）且近中性（色度低）；护栏蓝灰色度更高被排除。
        white = (band_min >= lower) & (band_chroma <= chroma_max)
        active = np.count_nonzero(white, axis=0) >= 2
        # 深灰路面上下文：暗灰、不太亮、低色度（排除亮路牙/红地/草），用于判断白段是否被路面包夹。
        road_dark = (
            (band_min >= road_dark_min)
            & (band_max <= road_dark_max)
            & (band_chroma <= road_dark_chroma_max)
        )
        road_cols = np.count_nonzero(road_dark, axis=0) >= 1
        candidates = []
        for left, right in _segments_from_active(active):
            segment_width = float(right - left + 1)
            if not (min_width <= segment_width <= max_width):
                continue
            if not _neighbors_are_road(road_cols, left, right, profile):
                continue
            center = (float(left) + float(right)) * 0.5
            if not has_previous and abs(center - image_center) <= initial_limit:
                candidates.append(center)
            elif has_previous and abs(center - previous_center) <= jump_limit:
                candidates.append(center)
        if not candidates:
            continue
        center = min(candidates, key=lambda value: abs(value - previous_center))
        points.append((center, float(y)))
        previous_center = center
        has_previous = True

    if len(points) < int(profile["min_points_per_camera"]):
        return None
    point_arr = np.array(points, dtype=np.float32)
    point_y = point_arr[:, 1]
    point_x = point_arr[:, 0]
    y_span = float(np.max(point_y) - np.min(point_y))
    if y_span < float(profile["min_y_span"]):
        return None
    # 用最近/最远各约 1/3 实测点的中位数算近处中心和远处中心，不再用直线拟合外推：
    # 弯道里直线外推会把近处 offset 放大，过 trust 门被误拒（实测约一半检出因此被丢）。
    order = np.argsort(-point_y)  # y 大（近处）在前
    k = max(1, int(round(len(points) * profile["offset_near_fraction"])))
    near_x = float(np.median(point_x[order[:k]]))
    far_x = float(np.median(point_x[order[-k:]]))
    offset = (near_x - image_center) / max(image_center, 1.0)
    heading = (far_x - near_x) / max(image_center, 1.0)
    # 置信度与扫描行数解耦：加密扫描行不应稀释置信度（弯道里命中 3-5 个点已是可信线）。
    confidence = clamp(len(points) / float(profile["confidence_full_points"]), 0.0, 1.0)
    return clamp(offset, -1.0, 1.0), clamp(heading, -1.0, 1.0), confidence


def _startup_single_line_candidate(
    line: tuple[float, float, float] | None,
    profile: dict,
    timestamp,
) -> tuple[float, float, float] | None:
    """判断发车阶段的单目白线是否可信。

    功能：在 complex 开头白线只落进单个相机时，保留符号和斜率合理的右侧虚线。
    参数：`line` 是单相机检测结果，`profile` 是白线参数，`timestamp` 是当前仿真时间。
    返回：可信则返回原始 line，否则返回 None。
    逻辑：只接受右侧中等 offset、正斜率的短窗口信号；负 offset 多来自左护栏，
    接近 1.0 的 offset 多来自远处护栏或路边物体，继续拒绝。
    """

    if line is None:
        return None
    try:
        current_time = float(timestamp)
    except (TypeError, ValueError):
        return None
    offset, heading, confidence = line
    if current_time > profile["startup_acquire_until"]:
        return None
    if confidence < profile["min_confidence"]:
        return None
    if not (profile["startup_offset_min"] <= offset <= profile["startup_offset_trust_max"]):
        return None
    if not (profile["startup_heading_min"] <= heading <= profile["startup_heading_max"]):
        return None
    return line


def _red_environment_single_line_candidate(
    line: tuple[float, float, float] | None,
    profile: dict,
    red_environment: bool,
) -> tuple[float, float, float] | None:
    """判断 complex 弯中单目白线是否可作低置信兜底。

    功能：在红色场地里，一侧相机可能因透视/虚线间隙漏掉白线；另一侧若已通过路面上下文过滤，
    可低置信接入，避免控制链路短暂失去中线。
    参数：`line` 是单相机检测结果，`red_environment` 来自左右画面的红色场地判定。
    返回：可信则返回置信度折扣后的 line；否则返回 None。
    逻辑：只在 complex 红色环境启用，且要求 offset 仍在主信任门内；basic 和发车单目逻辑互不影响。
    """

    if line is None or not red_environment or not profile["single_camera_enable"]:
        return None
    offset, heading, confidence = line
    if confidence < profile["single_camera_min_confidence"]:
        return None
    if abs(offset) > profile["single_camera_offset_max"]:
        return None
    scaled_confidence = confidence * profile["single_camera_confidence_scale"]
    return offset, heading, clamp(scaled_confidence, 0.0, 1.0)


def _stereo_line_state(left_img, right_img, profile: dict, timestamp=None) -> tuple[float, float, float]:
    """融合左右相机的白线状态。

    功能：估计白线相对车身中轴的位置和方向。
    参数：左右 BGR 图像和白线参数。
    返回：`(line_offset, line_heading, line_confidence)`。
    逻辑：双目都看到连续白线时才输出高置信，避免单目被车身、栏杆或断线误导。
    complex 发车窗口里允许符号/斜率受限的单目右侧白线，用于把车从初始左偏捕获回中线。
    """

    if not profile["enable"]:
        return 0.0, 0.0, 0.0
    left = _camera_line_state(left_img, profile)
    right = _camera_line_state(right_img, profile)
    if left is None or right is None:
        single = _startup_single_line_candidate(left or right, profile, timestamp)
        if single is not None:
            return single
        red_environment = _is_red_environment(left_img) or _is_red_environment(right_img)
        single = _red_environment_single_line_candidate(left or right, profile, red_environment)
        if single is not None:
            return single
        return 0.0, 0.0, 0.0
    confidence = min(left[2], right[2])
    if confidence < profile["min_confidence"]:
        return 0.0, 0.0, confidence
    offset = (left[0] + right[0]) * 0.5
    heading = (left[1] + right[1]) * 0.5
    return clamp(offset, -1.0, 1.0), clamp(heading, -1.0, 1.0), confidence


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

    # ── 跨帧轨迹锚定：超宽段（道路合并）时，优先选靠近上一帧同高度中心的分段 ──
    temporal_anchor: float | None = None
    if wide_localize_enabled and _LAST_FRAME_CENTERS:
        height = road_mask.shape[0]
        best_y_dist = float("inf")
        for cx, cy in _LAST_FRAME_CENTERS:
            dist = abs(cy - float(y))
            if dist < best_y_dist:
                best_y_dist = dist
                temporal_anchor = cx
        best_candidate_width = max(c[1] - c[0] for c in candidates)
        temporal_window = float(width) * VISION_PROFILE.get("temporal_anchor_window_ratio", 0.38)
        if best_candidate_width > float(width) * VISION_PROFILE["wide_segment_localize_ratio"] * 0.7:
            if temporal_anchor is not None and abs(temporal_anchor - previous_center) > temporal_window * 0.5:
                previous_center = previous_center * 0.35 + temporal_anchor * 0.65
                # 重新选最佳分段（因为 previous_center 已调整）
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
    red_environment: bool = False,
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
    elif red_environment and mask_fill_ratio > VISION_PROFILE["red_mask_fill_warning"]:
        confidence *= VISION_PROFILE["red_mask_fill_confidence_scale"]
        debug_flags |= 4
    if fallback_count:
        confidence *= max(0.55, 1.0 - 0.06 * fallback_count)
        debug_flags |= 2

    return clamp(confidence, 0.0, 1.0), debug_flags


def _scan_image(image: np.ndarray, timestamp=None, enable_opp: bool = True) -> _CameraScan:
    """按扫描线跟踪单张图像的道路走廊。

    功能：输出中心点、左右边界点、道路宽度和置信度。
    参数：`image` 是单个摄像头 BGR 图像，`timestamp` 用于限制末段障碍处理，
        `enable_opp` 控制是否做对手车检测（仅 with_other_cars profile）。
    返回：`_CameraScan`。
    逻辑：从近处向远处扫描，每条线选择离上一条有效中心最近的连续道路 segment。
    """

    if not _valid_image(image):
        _save_frame_centers([])
        return _empty_scan()

    _maybe_reset_perception_by_timestamp(timestamp)
    road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle, obstacle_x, obstacle_size = _build_masks(
        image,
        timestamp,
        enable_opp,
    )
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
        _save_frame_centers([])
        debug_flags = 4 if mask_fill_ratio < 0.015 or mask_fill_ratio > 0.92 else 1
        scan = _empty_scan(debug_flags=debug_flags)
        scan.near_obstacle = bool(near_obstacle)
        scan.obstacle_x = float(obstacle_x)
        scan.obstacle_size = float(obstacle_size)
        return scan

    confidence, debug_flags = _score_scan(
        centers,
        widths,
        texture_score,
        mask_fill_ratio,
        fallback_count,
        red_environment=red_environment,
    )
    if red_environment:
        debug_flags |= _RED_ENVIRONMENT_FLAG
    _save_frame_centers(centers)
    return _CameraScan(
        np.array(centers, dtype=np.float32),
        np.array(left_edges, dtype=np.float32),
        np.array(right_edges, dtype=np.float32),
        float(np.median(np.array(widths, dtype=np.float32))),
        confidence,
        debug_flags=debug_flags,
        near_obstacle=bool(near_obstacle),
        obstacle_x=float(obstacle_x),
        obstacle_size=float(obstacle_size),
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
        near_obstacle=bool(scan.near_obstacle),
        obstacle_x=float(scan.obstacle_x),
        obstacle_size=float(scan.obstacle_size),
    )


def _fused_obstacle(left_scan: _CameraScan, right_scan: _CameraScan) -> tuple[bool, float, float]:
    """融合双目近车检测结果。

    功能：给 policy 一个稳定的左/中/右对手位置。
    参数：左右 `_CameraScan`。
    返回：`(near, x, size)`。
    逻辑：只有一侧检测到就用那侧；两侧都检测到时按车身块尺寸加权，尺寸更大的近车影响更大。
    """

    candidates = [
        scan
        for scan in (left_scan, right_scan)
        if scan.near_obstacle and scan.obstacle_size > 0.0
    ]
    if not candidates:
        return bool(left_scan.near_obstacle or right_scan.near_obstacle), 0.0, 0.0
    total = sum(max(float(scan.obstacle_size), 1e-6) for scan in candidates)
    x = sum(float(scan.obstacle_x) * max(float(scan.obstacle_size), 1e-6) for scan in candidates) / total
    size = max(float(scan.obstacle_size) for scan in candidates)
    return True, clamp(x, -1.0, 1.0), size


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
        obs = _to_obs(left_scan)
        obs.near_obstacle, obs.obstacle_x, obs.obstacle_size = _fused_obstacle(left_scan, right_scan)
        return obs
    if right_ok and not left_ok:
        obs = _to_obs(right_scan)
        obs.near_obstacle, obs.obstacle_x, obs.obstacle_size = _fused_obstacle(left_scan, right_scan)
        return obs
    if not left_ok and not right_ok:
        obs = _empty_obs(debug_flags=left_scan.debug_flags | right_scan.debug_flags | 1)
        obs.near_obstacle, obs.obstacle_x, obs.obstacle_size = _fused_obstacle(left_scan, right_scan)
        return obs

    center_gap = abs(_near_center(left_scan) - _near_center(right_scan))
    merge_gap = 640.0 * VISION_PROFILE["fusion_merge_gap"]
    merge_confidence = VISION_PROFILE["fusion_merge_min_confidence"]
    confidence_gap = abs(left_scan.confidence - right_scan.confidence)
    near_obstacle, obstacle_x, obstacle_size = _fused_obstacle(left_scan, right_scan)
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
        obs = _to_obs(chosen, debug_flags=flags)
        obs.near_obstacle = near_obstacle
        obs.obstacle_x = obstacle_x
        obs.obstacle_size = obstacle_size
        return obs

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
        near_obstacle=near_obstacle,
        obstacle_x=obstacle_x,
        obstacle_size=obstacle_size,
    )


def _with_line_state(obs: PerceptionObs, left_img, right_img, timestamp=None) -> PerceptionObs:
    """把双目白线状态写入观测结果。

    不依赖道路观测质量：道路 mask 饱和（蓝门/天空）或丢线时白线往往仍可见，
    是 R011 后置修正在这些帧上唯一的方向来源。
    """

    line_offset, line_heading, line_confidence = _stereo_line_state(
        left_img,
        right_img,
        LINE_FOLLOW_PROFILE,
        timestamp,
    )
    obs.line_offset = line_offset
    obs.line_heading = line_heading
    obs.line_confidence = line_confidence
    return obs


def reset_perception_state() -> None:
    """重置感知跨帧状态。

    功能：清空跨帧轨迹记忆。
    参数：无。
    返回：无。
    逻辑：测试或新仿真开始前调用。
    """
    global _LAST_FRAME_CENTERS, _LAST_FRAME_TIMESTAMP
    _LAST_FRAME_CENTERS = None
    _LAST_FRAME_TIMESTAMP = None


def extract_observation(left_img, right_img, timestamp=None, profile=None) -> PerceptionObs:
    """提取左右摄像头的赛道观测。

    功能：输出中心点、边界点、道路宽度估计和感知置信度。
    参数：`left_img` 与 `right_img` 是平台传入的 BGR 图像，`timestamp` 是仿真时间，
        `profile` 是当前控制 profile（决定整条感知链是否启用对手检测/光流卡死，即
        no_other_cars vs with_other_cars）。`profile=None` 时退回旧行为（按 OPPONENT_PROFILE
        全局开关），供测试/replay 直接调用。
    返回：`PerceptionObs`。
    逻辑：分别扫描左右图像；单侧有效则使用单侧，双侧一致则合并，双侧冲突则选择高置信度结果。
        active profile 贯穿到这里，让 no_other_cars 真正不跑对手检测、也不算 frame_motion，
        多车感知能力不会泄漏到单车（见 CLAUDE.md「Profile 隔离」）。
    """

    if profile is None:
        enable_opp = bool(OPPONENT_PROFILE["enable_opponent_avoidance"])
    else:
        enable_opp = bool(profile.get("enable_opponent", False))

    left_scan = _scan_image(left_img, timestamp, enable_opp) if _valid_image(left_img) else _empty_scan()
    right_scan = _scan_image(right_img, timestamp, enable_opp) if _valid_image(right_img) else _empty_scan()
    obs = _fuse_scans(left_scan, right_scan)
    obs = _with_line_state(obs, left_img, right_img, timestamp)
    # 光流卡死检测（frame_motion）只属于 with_other_cars；单车不算，省每帧 resize 开销，
    # 且默认 frame_motion=100（视作在动）保证 motion-stall 永不触发。
    if enable_opp:
        obs.frame_motion = _update_frame_motion(left_img, timestamp)
    return obs


_PREV_MOTION_GRAY = None
_PREV_MOTION_T = None


def _update_frame_motion(image, timestamp=None) -> float:
    """估计帧间图像变化量（下采样灰度平均绝对差）。

    功能：给一个"画面在不在流动"的标量——高=车在动，低≈被顶住不动（物理卡死）。
    参数：`image` 单张 BGR 图（用左相机），`timestamp` 用于检测仿真重启清状态。
    返回：MAD（约 0~50）；首帧或无上一帧时返回高值（视作在动）。
    逻辑：几何签名在直路和顶栏时都稳定、区分不了卡死；原始像素帧差能区分——
        车真在开时场景流动、MAD 大，被顶住不动时画面几乎不变、MAD≈传感器噪声。
    """

    global _PREV_MOTION_GRAY, _PREV_MOTION_T
    if not _valid_image(image):
        return 100.0
    small = cv2.resize(
        cv2.cvtColor(image, cv2.COLOR_BGR2GRAY), (64, 48), interpolation=cv2.INTER_AREA
    )
    if (
        _PREV_MOTION_T is not None
        and timestamp is not None
        and float(timestamp) < _PREV_MOTION_T - 1e-6
    ):
        _PREV_MOTION_GRAY = None  # 仿真重启/时间回退：清上一帧
    prev = _PREV_MOTION_GRAY
    _PREV_MOTION_GRAY = small
    _PREV_MOTION_T = None if timestamp is None else float(timestamp)
    if prev is None:
        return 100.0
    return float(np.mean(np.abs(small.astype(np.int16) - prev.astype(np.int16))))


def reset_frame_motion_state() -> None:
    """清空帧间运动检测的跨帧状态（新仿真/测试前调用）。"""

    global _PREV_MOTION_GRAY, _PREV_MOTION_T
    _PREV_MOTION_GRAY = None
    _PREV_MOTION_T = None
