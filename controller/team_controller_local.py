"""本地控制器入口。

功能概述：按固定流水线串接感知、估计、模式、转向和速度模块。
输入输出：输入平台同形态的左右图像和时间戳，输出 `(steering, speed)`。
处理流程：读取 profile，提取观测，估计赛道，选择模式，计算转向和速度，最后限幅返回。
"""

from controller.common import clamp
from controller.estimator import estimate_track
from controller.params import get_profile
from controller.perception import extract_observation
from controller.steering import compute_steering
from controller.strategy import compute_speed, select_mode

PROFILE = "fastest"


def control(left_img, right_img, timestamp):
    """平台兼容的控制入口。

    功能：提供 `control(left_img, right_img, timestamp)` 接口。
    参数：`left_img`、`right_img` 是 BGR 图像，`timestamp` 是仿真时间。
    返回：`(steering, speed)`，两个值都在平台允许范围内。
    逻辑：仅负责模块接线和异常兜底，具体算法留在各职责模块中。
    """

    try:
        profile = get_profile(PROFILE)
        obs = extract_observation(left_img, right_img)
        track = estimate_track(obs, timestamp)
        mode = select_mode(track, timestamp, profile)
        steering_cmd = compute_steering(track, mode, timestamp, profile)
        speed_cmd = compute_speed(track, steering_cmd, mode, timestamp, profile)
        return clamp(steering_cmd.value, -1.0, 1.0), clamp(speed_cmd.value, 0.0, 1.0)
    except Exception:
        return 0.0, 0.0
