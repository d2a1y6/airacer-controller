"""视觉感知模块。

功能概述：从左右摄像头图像中提取赛道边界、中心点和感知置信度。
输入输出：输入 BGR 图像，输出 `PerceptionObs`。
处理流程：裁剪中下部 ROI，生成轻量二值掩膜，按扫描线提取左右边界并估计中心点。
"""

import cv2
import numpy as np

from controller.common import PerceptionObs, clamp
from controller.params import VISION_PROFILE


def _empty_obs() -> PerceptionObs:
    points = np.empty((0, 2), dtype=np.float32)
    return PerceptionObs(points, points, points, 0.0, 0.0, debug_flags=1)


def _valid_image(image) -> bool:
    return image is not None and hasattr(image, "shape") and len(image.shape) == 3 and image.shape[2] == 3


def _make_mask(image: np.ndarray) -> np.ndarray:
    """生成赛道线索掩膜。

    功能：把亮色区域、灰度高对比区域和边缘线索合并成二值图。
    参数：`image` 是单个摄像头 BGR 图像。
    返回：uint8 掩膜，非零像素表示可能的赛道边界或可行驶区域。
    逻辑：多线索融合比单一颜色阈值更抗赛道材质变化。
    """

    height = image.shape[0]
    top = int(height * VISION_PROFILE["roi_top_ratio"])
    roi = image[top:, :, :]

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

    bright = cv2.inRange(hsv, np.array([0, 0, 125]), np.array([180, 100, 255]))
    _, adaptive = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 45, 120)

    mask = cv2.bitwise_or(cv2.bitwise_or(bright, adaptive), edges)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)

    padded = np.zeros(image.shape[:2], dtype=np.uint8)
    padded[top:, :] = mask
    return padded


def _scan_image(image: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, float]:
    """按扫描线提取单张图中的边界和中心点。

    功能：在若干水平扫描线上寻找左右边界，并估计赛道中心。
    参数：`image` 是单个摄像头图像。
    返回：中心点、左边界点、右边界点、道路宽度、置信度。
    逻辑：从近处到远处扫描，点数和道路宽度稳定性共同决定置信度。
    """

    mask = _make_mask(image)
    height, width = mask.shape
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

    for y in rows:
        xs = np.flatnonzero(mask[y])
        if xs.size < VISION_PROFILE["min_pixels_per_scan"]:
            continue
        left = float(xs[0])
        right = float(xs[-1])
        road_width = right - left
        if road_width < VISION_PROFILE["min_road_width"]:
            continue
        center = (left + right) * 0.5
        centers.append((center, float(y)))
        left_edges.append((left, float(y)))
        right_edges.append((right, float(y)))
        widths.append(road_width)

    if not centers:
        empty = np.empty((0, 2), dtype=np.float32)
        return empty, empty, empty, 0.0, 0.0

    center_arr = np.array(centers, dtype=np.float32)
    left_arr = np.array(left_edges, dtype=np.float32)
    right_arr = np.array(right_edges, dtype=np.float32)
    width_est = float(np.median(np.array(widths, dtype=np.float32)))
    confidence = clamp(len(centers) / float(VISION_PROFILE["scan_count"]), 0.0, 1.0)
    return center_arr, left_arr, right_arr, width_est, confidence


def extract_observation(left_img, right_img) -> PerceptionObs:
    """提取左右摄像头的赛道观测。

    功能：输出中心点、边界点、道路宽度估计和感知置信度。
    参数：`left_img` 与 `right_img` 是平台传入的 BGR 图像。
    返回：`PerceptionObs`。
    逻辑：分别扫描有效图像，合并结果；全部失败时返回低置信度空观测。
    """

    chunks = []
    widths = []
    confidences = []

    for image in (left_img, right_img):
        if not _valid_image(image):
            continue
        centers, left_edges, right_edges, width_est, confidence = _scan_image(image)
        chunks.append((centers, left_edges, right_edges))
        if width_est > 0:
            widths.append(width_est)
        confidences.append(confidence)

    if not chunks:
        return _empty_obs()

    center_points = np.concatenate([item[0] for item in chunks], axis=0)
    left_edge_points = np.concatenate([item[1] for item in chunks], axis=0)
    right_edge_points = np.concatenate([item[2] for item in chunks], axis=0)

    if center_points.size == 0:
        return _empty_obs()

    confidence = clamp(float(np.mean(confidences)), 0.0, 1.0)
    road_width_est = float(np.median(np.array(widths, dtype=np.float32))) if widths else 0.0
    return PerceptionObs(center_points, left_edge_points, right_edge_points, road_width_est, confidence)
