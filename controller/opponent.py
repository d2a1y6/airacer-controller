"""对手车辆感知模块。

功能概述：保留可提交的近处车身检测逻辑，供后续多车策略使用。
输入输出：输入单张 BGR 图像，输出是否检测到近距离车身遮挡。
处理流程：截取下半部中间 ROI，提取高饱和、亮白和近黑候选块，再用连通域尺寸过滤噪声。
"""

import cv2
import numpy as np

from controller.params import OPPONENT_PROFILE


def detect_near_vehicle_obstacle(image: np.ndarray, profile: dict | None = None) -> bool:
    """检测近处是否有大块车身遮挡。

    功能：识别发车格静止车辆或近距离对手车这类大块遮挡。
    参数：`image` 是单张 BGR 摄像头图像，`profile` 可覆盖默认检测参数。
    返回：检测到较大车身色块时返回 True。
    逻辑：只看图像下半部中间区域，用高饱和、亮白和近黑色块做候选，再用连通域面积过滤车道线。
    """

    params = OPPONENT_PROFILE if profile is None else profile
    height, width = image.shape[:2]
    y0 = int(height * params["near_obstacle_roi_top_ratio"])
    y1 = int(height * params["near_obstacle_roi_bottom_ratio"])
    x_margin = int(width * params["near_obstacle_roi_x_margin_ratio"])
    roi = image[y0:y1, x_margin : width - x_margin]
    if roi.size == 0:
        return False

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    candidate = (
        ((saturation > 85) & (value > 80))
        | ((gray > 135) & (saturation < 95))
        | ((gray < 35) & (value < 55))
    ).astype(np.uint8) * 255

    kernel = np.ones((5, 5), dtype=np.uint8)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN, kernel, iterations=1)
    count, _, stats, _ = cv2.connectedComponentsWithStats(candidate, 8)
    min_area = float(params["near_obstacle_min_area"])
    min_width = float(params["near_obstacle_min_width"])
    min_height = float(params["near_obstacle_min_height"])
    for index in range(1, count):
        _, _, comp_width, comp_height, area = stats[index]
        if area >= min_area and comp_width >= min_width and comp_height >= min_height:
            return True
    return False
