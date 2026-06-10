"""策略参数配置。

功能概述：集中保存视觉、估计和控制策略参数。
输入输出：输入任意 profile 名称，输出同一套控制参数。
处理流程：先定义通用感知和估计参数，再定义唯一的 CONTROL 控制参数。
"""

VISION_PROFILE = {
    "roi_top_ratio": 0.42,
    "scan_top_ratio": 0.50,
    "scan_bottom_ratio": 0.92,
    "scan_count": 12,
    "row_band": 2,
    "road_lab_threshold": 34.0,
    "road_gray_min": 35.0,
    "road_gray_max": 105.0,
    "road_sat_max": 80.0,
    "dark_mask_min_fill": 0.04,
    "texture_gray_std_scale": 35.0,
    "min_segment_width": 24.0,
    "max_segment_gap": 90.0,
    "max_segment_width_ratio": 0.995,
    "max_center_jump_ratio": 0.35,
    "min_valid_scans": 4,
    "min_camera_confidence": 0.12,
    "fusion_max_offset_gap": 0.18,
    "fusion_confidence_margin": 0.18,
    "fusion_merge_gap": 0.12,
    "fusion_merge_min_confidence": 0.35,
}

ESTIMATOR_PROFILE = {
    "image_center_x": 320.0,
    "x_scale": 320.0,
    "lost_confidence": 0.08,
    "min_center_points": 3,
    "min_good_points": 8,
    "min_y_span": 30.0,
    "min_y_span_good": 220.0,
    "min_road_width_for_conf": 20.0,
    "near_progress_max": 0.35,
    "far_progress_min": 0.60,
    "near_eval_progress": 0.15,
    "far_eval_progress": 0.75,
    "heading_eval_progress": 0.45,
    "poly2_min_points": 5,
    "heading_gain": 1.25,
    "curvature_gain": 1.45,
    "fallback_curvature_gain": 0.70,
    "max_fit_error": 0.22,
    "smooth_alpha": 0.28,
    "low_conf_extra_smoothing": 0.30,
    "min_smooth_alpha": 0.18,
    "max_smooth_alpha": 0.70,
    "curve_smooth_alpha": 0.46,
    "max_error_delta": 0.22,
    "max_heading_delta": 0.20,
    "max_curvature_delta": 0.18,
    "lost_lateral_decay": 0.85,
    "lost_heading_decay": 0.78,
    "lost_curvature_decay": 0.76,
    "lost_lookahead_decay": 0.82,
    "timestamp_reset_gap": 2.0,
}

CONTROL = {
    "base_speed": 0.96,
    "max_speed": 1.00,
    "min_speed": 0.16,
    "start_caution_seconds": 0.8,
    "start_speed": 0.36,
    "lost_confidence": 0.10,
    "recovery_confidence": 0.28,
    "lost_speed": 0.24,
    "recovery_speed": 0.38,
    "hard_turn_speed": 0.30,
    "hard_turn_center_speed_bonus": 0.30,
    "correction_speed": 0.50,
    "hard_turn_threshold": 0.20,
    "correction_error": 0.25,
    "recovery_frames": 4,
    "risk_curve_weight": 0.42,
    "risk_offset_weight": 0.28,
    "risk_confidence_weight": 0.22,
    "risk_lost_weight": 0.80,
    "near_weight_base": 0.90,
    "near_weight_offset_boost": 0.55,
    "far_weight_base": 0.75,
    "far_weight_curve_boost": 0.45,
    "far_conflict_offset_scale": 3.20,
    "far_conflict_min_scale": 0.05,
    "gain_lateral": 0.65,
    "gain_lookahead": 0.90,
    "gain_heading": 0.98,
    "gain_curve": 0.25,
    "gain_lateral_nonlinear": 0.18,
    "gain_curve_nonlinear": 0.04,
    "steering_deadzone": 0.015,
    "curve_slowdown": 0.66,
    "curve_power": 1.35,
    "offset_slowdown": 0.38,
    "offset_power": 1.25,
    "min_confidence_factor": 0.58,
    "steering_slowdown": 0.28,
    "steering_power": 1.15,
    "steering_smoothing_cruise": 0.16,
    "steering_smoothing_turn": 0.14,
    "steering_smoothing_correction": 0.14,
    "steering_smoothing_recovery": 0.28,
    "max_steering_delta": 0.46,
    "max_speed_increase_per_sec": 1.60,
    "max_speed_decrease_per_sec": 2.20,
    "nominal_dt": 0.032,
    "timestamp_reset_gap": 2.0,
}


def get_profile(name: str) -> dict:
    """读取控制 profile。

    功能：为顶层控制器提供当前唯一维护的控制参数。
    参数：`name` 保留兼容构建脚本和提交文件中的 fastest/safe 标记。
    返回：`CONTROL` 参数字典的浅拷贝。
    逻辑：所有模式都返回同一套参数，便于先集中优化一个目标。
    """

    del name
    return dict(CONTROL)
