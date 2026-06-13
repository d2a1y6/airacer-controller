"""本地控制器入口。

功能概述：按固定流水线串接感知、估计和控制策略模块。
输入输出：输入平台同形态的左右图像和时间戳，输出 `(steering, speed)`。
处理流程：提取观测，估计赛道，按 profile 决策控制量，最后限幅返回。
"""

from controller.common import clamp_cmd
from controller.estimator import estimate_track
from controller.policy import decide_control
from controller.perception import extract_observation
from controller.params import get_profile

# 选择控制策略：no_other_cars（单车=R049）或 with_other_cars（多车）。
# build_submission.py 按 --mode 注入对应值；本地默认单车。两个 profile 共享核心驾驶参数，
# 只在对手避让/倒车/脱困激进度上不同（见 controller/params.py 与 CLAUDE.md「Profile 隔离」）。
PROFILE = "no_other_cars"


def control(left_img, right_img, timestamp):
    """平台兼容的控制入口。

    功能：提供 `control(left_img, right_img, timestamp)` 接口。
    参数：`left_img`、`right_img` 是 BGR 图像，`timestamp` 是仿真时间。
    返回：`(steering, speed)`，两个值都在平台允许范围内。
    逻辑：仅负责模块接线和异常兜底，具体算法留在各职责模块中。
        active profile 贯穿整条流水线：传给 perception 决定是否跑对手检测/光流卡死，
        传给 policy 决定避让/倒车/脱困——让 no_other_cars 彻底不走多车路径。
    """

    try:
        profile = get_profile(PROFILE)
        obs = extract_observation(left_img, right_img, timestamp, profile=profile)
        track = estimate_track(obs, timestamp)
        cmd = decide_control(track, timestamp, mode=PROFILE)
        steering, speed = clamp_cmd(cmd)
        return steering, speed
    except Exception:
        return 0.0, 0.0
