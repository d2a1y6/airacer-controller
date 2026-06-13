"""对手车辆感知模块。

功能概述：保留可提交的近处车身检测逻辑，供多车策略使用。
输入输出：输入单张 BGR 图像，输出是否检测到近距离车身遮挡，以及遮挡的左右位置/尺寸。
处理流程：截取下半部中间 ROI，合并亮白/近黑块和官方车身颜色 mask，再用连通域尺寸过滤噪声。
"""

import cv2
import numpy as np

from controller.params import COLOR_PROFILE, OPPONENT_PROFILE


def _hue_delta(hue, center):
    """计算 OpenCV hue 环形距离。"""

    delta = np.abs(hue.astype(np.float32) - float(center))
    return np.minimum(delta, 180.0 - delta)


def _vehicle_color_mask(hsv, hsv_center, hsv_tol):
    """按 `COLOR_PROFILE` 的 HSV 容差生成车身颜色 mask。

    功能：匹配官方车身基础色，避免只靠亮度把白线、天空或红色场地误判为车辆。
    参数：`hsv` 是 ROI 的 HSV 图，`hsv_center`/`hsv_tol` 是车身颜色中心和容差。
    返回：布尔 mask。
    逻辑：Hue 用环形距离；红地面、蓝天、绿草主要靠更高的车身饱和度门槛排除。
    """

    return (
        (_hue_delta(hsv[:, :, 0], hsv_center[0]) <= hsv_tol[0])
        & (np.abs(hsv[:, :, 1].astype(np.float32) - hsv_center[1]) <= hsv_tol[1])
        & (np.abs(hsv[:, :, 2].astype(np.float32) - hsv_center[2]) <= hsv_tol[2])
    )


def vehicle_body_mask(image, profile=None):
    """生成近处车身候选 mask。

    功能：把白/黑车身和官方 6 车颜色合并为一个候选图。
    参数：`image` 是单张 BGR 摄像头图像，`profile` 可覆盖默认检测参数。
    返回：与原图同宽高的 `uint8` mask，车身候选为 255。
    逻辑：只在检测 ROI 内置位；后续仍需连通域面积/宽高过滤才判定为障碍。
    """

    params = OPPONENT_PROFILE if profile is None else profile
    height, width = image.shape[:2]
    y0 = int(height * params["near_obstacle_roi_top_ratio"])
    y1 = int(height * params["near_obstacle_roi_bottom_ratio"])
    x_margin = int(width * params["near_obstacle_roi_x_margin_ratio"])
    mask = np.zeros((height, width), dtype=np.uint8)
    roi = image[y0:y1, x_margin : width - x_margin]
    if roi.size == 0:
        return mask

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    bright_body = (gray > params["near_obstacle_white_gray_min"]) & (
        saturation < params["near_obstacle_white_sat_max"]
    )
    dark_body = (gray < params["near_obstacle_black_gray_max"]) & (value < params["near_obstacle_black_value_max"])
    color_body = np.zeros(roi.shape[:2], dtype=bool)
    for _bgr, hsv_center, hsv_tol in COLOR_PROFILE["car_body_colors"]:
        # 白车/黑车已由亮度分支处理；低饱和 HSV 容差过宽，容易把深灰沥青吃进来。
        if hsv_center[1] < 80:
            continue
        color_body |= _vehicle_color_mask(hsv, hsv_center, hsv_tol)

    candidate = (bright_body | dark_body | color_body).astype(np.uint8) * 255
    kernel = np.ones((5, 5), dtype=np.uint8)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel, iterations=1)
    mask[y0:y1, x_margin : width - x_margin] = candidate
    return mask


def detect_near_vehicle_obstacle_state(image: np.ndarray, profile: dict | None = None) -> tuple[bool, float, float]:
    """检测近处车身遮挡，并给出横向位置和块尺寸。

    功能：识别发车格静止车辆或近距离对手车这类大块遮挡。
    参数：`image` 是单张 BGR 摄像头图像，`profile` 可覆盖默认检测参数。
    返回：`(near, x, size)`；`x` 为 -1 左 / +1 右，`size` 为最大车身块占 ROI 的比例。
    逻辑：只看图像下半部中间区域，用亮白/近黑和官方车身颜色做候选，再用连通域面积过滤车道线。
    complex 红色场地、天空和草地会被颜色容差排除，不能把高饱和本身当成车身证据。
    """

    params = OPPONENT_PROFILE if profile is None else profile
    candidate = vehicle_body_mask(image, params)
    if not np.any(candidate):
        return False, 0.0, 0.0

    count, _, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
    min_area = float(params["near_obstacle_min_area"])
    min_width = float(params["near_obstacle_min_width"])
    min_height = float(params["near_obstacle_min_height"])
    best = None
    for index in range(1, count):
        left, top, comp_width, comp_height, area = stats[index]
        if area >= min_area and comp_width >= min_width and comp_height >= min_height:
            if best is None or area > best[-1]:
                best = (left, top, comp_width, comp_height, area)
    if best is None:
        return False, 0.0, 0.0

    left, _top, comp_width, _comp_height, area = best
    height, width = candidate.shape[:2]
    roi_top = int(height * params["near_obstacle_roi_top_ratio"])
    roi_bottom = int(height * params["near_obstacle_roi_bottom_ratio"])
    x_margin = int(width * params["near_obstacle_roi_x_margin_ratio"])
    roi_area = max((roi_bottom - roi_top) * max(width - 2 * x_margin, 1), 1)
    center_x = left + comp_width * 0.5
    x_norm = (center_x / max(width - 1, 1) - 0.5) * 2.0
    size = float(area) / float(roi_area)
    return True, float(np.clip(x_norm, -1.0, 1.0)), float(size)


def detect_near_vehicle_obstacle(image: np.ndarray, profile: dict | None = None) -> bool:
    """检测近处是否有大块车身遮挡。

    功能：保留旧 bool 接口，供现有测试和脚本兼容。
    参数：`image` 是单张 BGR 摄像头图像，`profile` 可覆盖默认检测参数。
    返回：检测到较大车身色块时返回 True。
    逻辑：内部使用 `detect_near_vehicle_obstacle_state()`，丢弃方向和尺寸。
    """

    near, _x, _size = detect_near_vehicle_obstacle_state(image, profile)
    return near
