"""策略参数配置。

功能概述：集中保存视觉、估计、转向和速度策略参数。
输入输出：输入 profile 名称，输出对应参数字典。
处理流程：先定义通用感知和估计参数，再定义 fastest/safe 两套控制 profile。
"""

VISION_PROFILE = {
    "roi_top_ratio": 0.42,
    "scan_top_ratio": 0.50,
    "scan_bottom_ratio": 0.92,
    "scan_count": 12,
    "min_pixels_per_scan": 8,
    "min_road_width": 18.0,
}

ESTIMATOR_PROFILE = {
    "lost_confidence": 0.08,
    "smooth_alpha": 0.28,
}

FAST_PROFILE = {
    "base_speed": 0.86,
    "max_speed": 1.0,
    "min_speed": 0.20,
    "lost_speed": 0.18,
    "recovery_speed": 0.26,
    "caution_speed": 0.58,
    "curve_slowdown": 0.42,
    "offset_slowdown": 0.20,
    "steering_slowdown": 0.08,
    "risk_slowdown": 0.24,
    "lateral_gain": 1.05,
    "heading_gain": 0.34,
    "lookahead_gain": 0.28,
    "curvature_gain": 0.38,
    "steering_deadzone": 0.018,
    "steering_smooth": 0.30,
    "caution_steering_smooth": 0.42,
    "max_steering_delta": 0.22,
    "nominal_dt": 0.032,
    "recovery_steering_scale": 0.72,
    "caution_risk": 0.58,
    "lost_risk": 0.92,
    "recovery_confidence": 0.28,
    "start_caution_seconds": 0.8,
}

SAFE_PROFILE = {
    "base_speed": 0.66,
    "max_speed": 0.82,
    "min_speed": 0.16,
    "lost_speed": 0.12,
    "recovery_speed": 0.20,
    "caution_speed": 0.44,
    "curve_slowdown": 0.54,
    "offset_slowdown": 0.30,
    "steering_slowdown": 0.12,
    "risk_slowdown": 0.34,
    "lateral_gain": 0.98,
    "heading_gain": 0.30,
    "lookahead_gain": 0.24,
    "curvature_gain": 0.42,
    "steering_deadzone": 0.022,
    "steering_smooth": 0.40,
    "caution_steering_smooth": 0.56,
    "max_steering_delta": 0.16,
    "nominal_dt": 0.032,
    "recovery_steering_scale": 0.62,
    "caution_risk": 0.46,
    "lost_risk": 0.96,
    "recovery_confidence": 0.36,
    "start_caution_seconds": 1.2,
}


def get_profile(name: str) -> dict:
    """按名称读取控制 profile。

    功能：为顶层控制器提供 fastest 或 safe 参数。
    参数：`name` 只能是 `fastest` 或 `safe`。
    返回：对应参数字典的浅拷贝。
    逻辑：浅拷贝可避免调用方误改全局参数；未知名称直接回退到 safe。
    """

    if name == "fastest":
        return dict(FAST_PROFILE)
    if name == "safe":
        return dict(SAFE_PROFILE)
    return dict(SAFE_PROFILE)
