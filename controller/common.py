"""公共数据结构和基础工具。

功能概述：定义模块间共享的数据契约和数值限幅函数。
输入输出：输入各模块产生的原始数值，输出带字段约束的 dataclass 或裁剪后的数值。
处理流程：先声明感知、估计、模式、转向、速度五类结构，再提供统一的 `clamp()`。
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


@dataclass
class ControlMode:
    """驾驶模式。

    功能：表达当前处于 normal、caution、lost 或 recovery 模式。
    参数：`name` 是模式名，`risk` 是 0 到 1 的风险值。
    返回：dataclass 实例。
    逻辑：策略模块根据几何状态判断风险，其他模块只消费结果。
    """

    name: str
    risk: float


@dataclass
class SteeringCmd:
    """转向命令。

    功能：保存转向值和转向决策置信度。
    参数：`value` 是方向盘比例，`confidence` 是 0 到 1 的可信度。
    返回：dataclass 实例。
    逻辑：转向模块负责限幅，顶层入口仍会做最终兜底限幅。
    """

    value: float
    confidence: float


@dataclass
class SpeedCmd:
    """速度命令。

    功能：保存速度值和速度决策置信度。
    参数：`value` 是速度比例，`confidence` 是 0 到 1 的可信度。
    返回：dataclass 实例。
    逻辑：策略模块负责降速规则，顶层入口负责最终限幅。
    """

    value: float
    confidence: float


def clamp(x: float, lo: float, hi: float) -> float:
    """把数值限制在指定区间。

    功能：防止控制量、风险值和置信度越界。
    参数：`x` 是待裁剪数值，`lo` 和 `hi` 是上下界。
    返回：落在 `[lo, hi]` 内的浮点数。
    逻辑：先转成 float，再依次应用上下界。
    """

    return max(lo, min(hi, float(x)))
