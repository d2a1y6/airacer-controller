"""本地控制器入口。

功能概述：按固定流水线串接感知、估计和控制策略模块。
输入输出：输入平台同形态的左右图像和时间戳，输出 `(steering, speed)`。
处理流程：提取观测，估计赛道，按 profile 决策控制量，最后限幅返回。
"""

import cv2
import numpy as np

from controller.common import ControlCmd, clamp, clamp_cmd
from controller.estimator import estimate_track
from controller.params import LINE_FOLLOW_PROFILE
from controller.policy import decide_control
from controller.perception import extract_observation

PROFILE = "fastest"


def _segments_from_active(active: np.ndarray) -> list[tuple[int, int]]:
    if active.size == 0:
        return []
    padded = np.concatenate(([False], active.astype(bool), [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(changes[i]), int(changes[i + 1] - 1)) for i in range(0, len(changes), 2)]


def _camera_line_state(image: np.ndarray, profile: dict) -> tuple[float, float, float] | None:
    """估计单个相机里的白色中心线。

    功能：找连续的窄白色虚线，输出近处偏移、线方向和置信度。
    参数：`image` 是 BGR 图像，`profile` 是白线跟踪参数。
    返回：`(offset, heading, confidence)`；白线不足时返回 None。
    逻辑：逐行找短白段并按连续性串起来，排除车身大白块和孤立噪声。
    """

    if image is None or not hasattr(image, "shape") or len(image.shape) != 3:
        return None
    height, width = image.shape[:2]
    lower = int(profile["white_min"])
    mask = cv2.inRange(image, (lower, lower, lower), (255, 255, 255))
    kernel = np.ones((3, 3), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

    rows = np.linspace(
        int(height * profile["scan_bottom_ratio"]),
        int(height * profile["scan_top_ratio"]),
        int(profile["scan_count"]),
        dtype=np.int32,
    )
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
        band = mask[y0:y1, :]
        active = np.count_nonzero(band, axis=0) >= 2
        candidates = []
        for left, right in _segments_from_active(active):
            segment_width = float(right - left + 1)
            if not (min_width <= segment_width <= max_width):
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

    min_points = int(profile["min_points_per_camera"])
    if len(points) < min_points:
        return None
    point_arr = np.array(points, dtype=np.float32)
    y = point_arr[:, 1]
    x = point_arr[:, 0]
    y_span = float(np.max(y) - np.min(y))
    if y_span < float(profile["min_y_span"]):
        return None
    coeffs = np.polyfit(y, x, deg=1)
    near_x = float(np.polyval(coeffs, height * profile["near_y_ratio"]))
    far_x = float(np.polyval(coeffs, height * profile["far_y_ratio"]))
    offset = (near_x - image_center) / max(image_center, 1.0)
    heading = (far_x - near_x) / max(image_center, 1.0)
    confidence = clamp(len(points) / float(profile["scan_count"]), 0.0, 1.0)
    return clamp(offset, -1.0, 1.0), clamp(heading, -1.0, 1.0), confidence


def _lane_line_correction(left_img, right_img, profile: dict) -> tuple[float, float] | None:
    """融合左右相机白线误差。

    功能：估计白线相对车身中轴的位置和方向。
    参数：左右 BGR 图像和白线参数。
    返回：`(correction, confidence)`；不可信时返回 None。
    逻辑：左右相机都看到连续白线时才强校正，避免单目被车身、栏杆或断线误导。
    """

    if not profile["enable"]:
        return None
    left = _camera_line_state(left_img, profile)
    right = _camera_line_state(right_img, profile)
    if left is None or right is None:
        return None
    offset = (left[0] + right[0]) * 0.5
    heading = (left[1] + right[1]) * 0.5
    confidence = min(left[2], right[2])
    if confidence < profile["min_confidence"]:
        return None
    correction = offset * profile["offset_gain"] + heading * profile["heading_gain"]
    correction = clamp(correction, -profile["max_correction"], profile["max_correction"])
    return correction, confidence


def _apply_lane_line_correction(cmd: ControlCmd, left_img, right_img) -> ControlCmd:
    """用白线误差小幅修正舵角。

    功能：让车身中线追向白色虚线，同时保持原道路中心控制作为兜底。
    参数：原始控制命令和左右相机图像。
    返回：修正后的控制命令。
    逻辑：白线可信时只加有限幅度的舵角修正，不直接覆盖速度和状态机。
    """

    line = _lane_line_correction(left_img, right_img, LINE_FOLLOW_PROFILE)
    if line is None:
        return cmd
    correction, _confidence = line
    return ControlCmd(clamp(cmd.steering + correction, -1.0, 1.0), cmd.speed)


def control(left_img, right_img, timestamp):
    """平台兼容的控制入口。

    功能：提供 `control(left_img, right_img, timestamp)` 接口。
    参数：`left_img`、`right_img` 是 BGR 图像，`timestamp` 是仿真时间。
    返回：`(steering, speed)`，两个值都在平台允许范围内。
    逻辑：仅负责模块接线和异常兜底，具体算法留在各职责模块中。
    """

    try:
        obs = extract_observation(left_img, right_img, timestamp)
        track = estimate_track(obs, timestamp)
        cmd = decide_control(track, timestamp, mode=PROFILE)
        cmd = _apply_lane_line_correction(cmd, left_img, right_img)
        steering, speed = clamp_cmd(cmd)
        return steering, speed
    except Exception:
        return 0.0, 0.0
