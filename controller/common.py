"""公共数据结构和基础工具。

功能概述：定义控制流水线共享的数据契约和数值限幅函数。
输入输出：输入各模块产生的原始数值，输出 dataclass 或平台可用的控制二元组。
处理流程：声明感知结果、赛道状态和控制命令，再提供统一的裁剪工具。
"""

from dataclasses import dataclass

import numpy as np


@dataclass
class PerceptionObs:
    """视觉感知结果。

    功能：承载扫描线中心点、左右边界点、道路宽度和感知置信度。
    参数：各字段由 `perception.extract_observation()` 生成。
    返回：dataclass 实例。
    逻辑：字段名作为模块契约，后续估计模块只读取这些字段。
    """

    center_points: np.ndarray
    left_edge_points: np.ndarray
    right_edge_points: np.ndarray
    road_width_est: float
    confidence: float
    debug_flags: int = 0


@dataclass
class TrackState:
    """赛道几何状态。

    功能：保存控制所需的偏移、方向、曲率、前瞻误差和丢线状态。
    参数：字段由 `estimator.estimate_track()` 估计。
    返回：dataclass 实例。
    逻辑：统一使用左负右正的误差符号，便于转向和速度策略复用。
    """

    lateral_error: float
    heading_error: float
    curvature: float
    lookahead_error: float
    confidence: float
    lost: bool
    red_environment: bool = False


@dataclass
class ControlCmd:
    """控制命令。

    功能：保存平台需要的转向和速度比例。
    参数：`steering` 是方向盘比例，`speed` 是速度比例。
    返回：dataclass 实例。
    逻辑：`policy.decide_control()` 产生命令，入口层用 `clamp_cmd()` 做最终限幅。
    """

    steering: float
    speed: float


def clamp(value: float, low: float, high: float) -> float:
    """把数值限制在指定区间。

    功能：防止控制量、风险值和置信度越界。
    参数：`value` 是待裁剪数值，`low` 和 `high` 是上下界。
    返回：落在 `[low, high]` 内的浮点数。
    逻辑：先转成 float，再依次应用上下界。
    """

    return max(low, min(high, float(value)))


def clamp_cmd(cmd: ControlCmd) -> tuple[float, float]:
    """裁剪平台控制二元组。

    功能：把控制命令转换成平台要求的 `(steering, speed)`。
    参数：`cmd` 是策略层输出的控制命令。
    返回：转向位于 `[-1.0, 1.0]`、速度位于 `[0.0, 1.0]` 的二元组。
    逻辑：入口层统一调用，避免各模块重复写最终范围保护。
    """

    return clamp(cmd.steering, -1.0, 1.0), clamp(cmd.speed, 0.0, 1.0)
