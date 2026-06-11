from dataclasses import dataclass
import math

import cv2
import numpy as np


# ---- common.py ----

\
\
\
\
\





@dataclass
class PerceptionObs:
\
\
\
\
\
\


    center_points: np.ndarray
    left_edge_points: np.ndarray
    right_edge_points: np.ndarray
    road_width_est: float
    confidence: float
    debug_flags: int = 0
    line_offset: float = 0.0
    line_heading: float = 0.0
    line_confidence: float = 0.0
    left_margin_near: float = 1.0
    right_margin_near: float = 1.0
    near_obstacle: bool = False


@dataclass
class TrackState:
\
\
\
\
\
\


    lateral_error: float
    heading_error: float
    curvature: float
    lookahead_error: float
    confidence: float
    lost: bool
    red_environment: bool = False
    line_offset: float = 0.0
    line_heading: float = 0.0
    line_confidence: float = 0.0
    left_margin_near: float = 1.0
    right_margin_near: float = 1.0
    near_obstacle: bool = False


@dataclass
class ControlCmd:
\
\
\
\
\
\


    steering: float
    speed: float


def clamp(value: float, low: float, high: float) -> float:
\
\
\
\
\
\


    return max(low, min(high, float(value)))


def clamp_cmd(cmd: ControlCmd) -> tuple[float, float]:
\
\
\
\
\
\


    return clamp(cmd.steering, -1.0, 1.0), clamp(cmd.speed, 0.0, 1.0)



# ---- params.py ----

"""策略参数配置。

功能概述：集中保存采样色卡、视觉、估计和控制策略参数。
输入输出：输入任意 profile 名称，输出同一套控制参数。
处理流程：先定义从 Webots 原图采样得到的颜色配置，再定义感知、估计和控制参数。
"""

COLOR_PROFILE = {


    "road_asphalt_dark_gray": {
        "rgb_median": (66.5, 77.0, 85.5),
        "bgr_median": (85.5, 77.0, 66.5),
        "hsv_median": (104.0, 57.5, 85.5),
        "lab_median": (82.0, 126.0, 121.5),
        "hsv_tolerance": (10.0, 22.0, 28.0),
        "lab_tolerance": (10.0, 3.0, 4.0),
        "b_minus_g_min": 6.0,
        "b_minus_g_max": 18.0,
        "g_minus_r_min": 6.0,
        "g_minus_r_max": 18.0,
    },
    "curb_shoulder_light_gray": {
        "rgb_median": (82.0, 92.0, 96.5),
        "bgr_median": (96.5, 92.0, 82.0),
        "hsv_median": (103.0, 42.0, 96.5),
        "lab_median": (98.5, 126.0, 123.5),
        "hsv_tolerance": (16.0, 28.0, 36.0),
        "lab_tolerance": (20.0, 6.0, 8.0),
    },
    "guardrail_light_gray": {
        "rgb_median": (93.0, 94.5, 79.5),
        "bgr_median": (79.5, 94.5, 93.0),
        "hsv_median": (102.5, 102.5, 140.5),
        "lab_median": (116.5, 125.5, 133.5),
        "hsv_tolerance": (18.0, 70.0, 70.0),
        "lab_tolerance": (38.0, 40.0, 36.0),
    },
    "green_grass": {
        "rgb_median": (86.5, 149.5, 65.5),
        "bgr_median": (65.5, 149.5, 86.5),
        "hsv_median": (52.5, 143.5, 149.5),
        "lab_median": (143.5, 91.5, 165.5),
        "hsv_tolerance": (18.0, 55.0, 70.0),
        "lab_tolerance": (35.0, 28.0, 35.0),
    },
    "red_ground": {
        "rgb_median": (168.0, 74.0, 75.0),
        "bgr_median": (75.0, 74.0, 168.0),
        "hsv_median": (179.0, 143.0, 168.0),
        "lab_median": (112.0, 167.0, 146.0),
        "hsv_tolerance": (12.0, 55.0, 70.0),
        "lab_tolerance": (35.0, 35.0, 35.0),
    },
    "blue_sky": {
        "rgb_median": (102.0, 178.0, 255.0),
        "bgr_median": (255.0, 178.0, 102.0),
        "hsv_median": (105.0, 153.0, 255.0),
        "lab_median": (181.0, 127.0, 83.0),
        "hsv_tolerance": (14.0, 45.0, 35.0),
        "lab_tolerance": (28.0, 12.0, 25.0),
    },
}

VISION_PROFILE = {
    "roi_top_ratio": 0.42,
    "scan_top_ratio": 0.50,
    "scan_bottom_ratio": 0.92,
    "scan_count": 12,
    "row_band": 2,
    "road_gray_min": 35.0,
    "road_gray_max": 115.0,
    "grass_hue_min": 35.0,
    "grass_hue_max": 95.0,
    "grass_sat_min": 60.0,
    "grass_value_min": 40.0,
    "barrier_hue_min": 92.0,
    "barrier_hue_max": 118.0,
    "barrier_sat_min": 60.0,
    "barrier_value_min": 80.0,
    "barrier_value_max": 210.0,
    "barrier_bridge_row_ratio": 0.25,
    "texture_gray_std_scale": 35.0,
    "min_segment_width": 24.0,
    "max_segment_gap": 90.0,
    "fallback_min_segment_width": 96.0,
    "fallback_initial_center_max_offset": 0.22,
    "fallback_narrow_jump_max_ratio": 0.16,
    "early_max_segment_width_ratio": 0.995,
    "red_world_min_ratio": 0.05,
    "max_segment_width_ratio": 0.90,
    "wide_segment_localize_ratio": 0.58,
    "wide_segment_window_ratio": 0.34,
    "max_center_jump_ratio": 0.35,
    "min_valid_scans": 4,
    "min_camera_confidence": 0.12,
    "empty_mask_confidence_scale": 0.25,
    "saturated_mask_confidence_scale": 0.25,
    "red_mask_fill_warning": 0.78,
    "red_mask_fill_confidence_scale": 0.45,
    "fusion_max_offset_gap": 0.18,
    "fusion_confidence_margin": 0.18,
    "fusion_merge_gap": 0.12,
    "fusion_merge_min_confidence": 0.35,
}

OPPONENT_PROFILE = {
    "enable_opponent_avoidance": True,
    "near_obstacle_segment_gap": 28.0,
    "near_obstacle_min_timestamp": 0.0,
    "near_obstacle_scan_y_ratio": 0.54,
    "near_obstacle_roi_top_ratio": 0.48,
    "near_obstacle_roi_bottom_ratio": 0.94,
    "near_obstacle_roi_x_margin_ratio": 0.08,
    "near_obstacle_white_gray_min": 150.0,
    "near_obstacle_white_sat_max": 80.0,
    "near_obstacle_black_gray_max": 30.0,
    "near_obstacle_black_value_max": 45.0,
    "near_obstacle_min_area": 700.0,
    "near_obstacle_min_width": 28.0,
    "near_obstacle_min_height": 18.0,
}

LINE_FOLLOW_PROFILE = {
    "enable": True,
    "white_min": 145.0,
    "scan_top_ratio": 0.48,
    "scan_bottom_ratio": 0.86,
    "scan_count": 5,
    "row_band": 2,
    "min_segment_width": 3.0,
    "max_segment_width": 70.0,
    "initial_center_max_offset": 0.40,
    "max_center_jump_ratio": 0.24,
    "min_points_per_camera": 3,
    "min_y_span": 70.0,
    "near_y_ratio": 0.78,
    "far_y_ratio": 0.55,
    "min_confidence": 0.30,
    "offset_gain": 0.76,
    "heading_gain": 0.18,
    "max_correction": 0.34,





    "offset_trust_max": 0.30,
    "offset_jump_max": 0.12,
    "confirm_frames": 3,
    "smoothing": 0.5,
    "curve_gate": 0.35,



    "startup_acquire_until": 14.0,
    "startup_offset_min": 0.32,
    "startup_offset_trust_max": 0.65,
    "startup_heading_min": 0.05,
    "startup_heading_max": 0.35,
    "startup_confirm_frames": 1,
    "startup_curve_gate": 0.75,
    "startup_max_correction": 0.22,
    "startup_smoothing": 0.35,
    "startup_decay": 0.86,
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
    "curvature_full_points": 12,
    "curvature_min_y_span": 150.0,
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


    "line_target_min_confidence": 0.30,
    "line_lateral_weight": 0.85,
    "line_heading_weight": 0.55,
    "line_lookahead_weight": 0.70,
    "line_lookahead_projection": 0.55,
    "line_target_normal_offset_max": 0.30,
    "line_target_normal_scale": 0.55,
    "line_target_unreliable_road_scale": 1.00,
    "line_target_startup_scale": 0.76,
    "line_target_road_confidence_max": 0.60,
    "line_target_confidence_scale": 0.75,
    "line_startup_until": 14.0,
    "line_startup_offset_min": 0.32,
    "line_startup_offset_max": 0.65,
    "line_startup_heading_min": 0.05,
    "line_startup_heading_max": 0.35,
    "line_startup_memory_frames": 120,
    "line_startup_memory_trust_scale": 0.66,
    "line_startup_memory_value_decay": 0.965,
    "timestamp_reset_gap": 2.0,
}

CONTROL = {
    "base_speed": 0.96,
    "max_speed": 1.00,
    "min_speed": 0.16,
    "straight_curve_max": 0.12,
    "straight_offset_max": 0.12,
    "straight_heading_max": 0.28,
    "straight_lost_steering_max": 0.12,
    "straight_memory_frames": 48,
    "straight_speed": 0.95,
    "straight_lost_speed": 0.92,
    "start_caution_seconds": 0.8,
    "start_speed": 0.36,
    "lost_confidence": 0.10,
    "recovery_confidence": 0.28,
    "lost_speed": 0.28,
    "recovery_speed": 0.44,
    "hard_turn_speed": 0.38,
    "hard_turn_center_speed_bonus": 0.20,
    "correction_speed": 0.58,
    "hard_turn_threshold": 0.20,
    "hard_turn_exit_threshold": 0.16,
    "hard_turn_enter_frames": 2,
    "recovery_enter_frames": 2,
    "correction_error": 0.25,
    "recovery_frames": 4,
    "risk_curve_weight": 0.42,
    "risk_offset_weight": 0.28,
    "risk_confidence_weight": 0.22,
    "risk_lost_weight": 0.80,
    "near_weight_base": 0.90,
    "near_weight_offset_boost": 0.55,
    "far_weight_base": 0.75,
    "far_weight_curve_boost": 0.36,
    "far_conflict_offset_start": 0.18,
    "far_conflict_offset_scale": 2.00,
    "far_conflict_min_scale": 0.22,
    "gain_lateral": 0.80,
    "gain_lookahead": 0.72,
    "gain_heading": 0.72,
    "gain_curve": 0.12,
    "gain_lateral_nonlinear": 0.22,
    "gain_curve_nonlinear": 0.02,
    "turn_in_floor": 0.55,
    "turn_in_lateral_ref": 0.30,
    "turn_in_heading_ref": 0.45,
    "steering_deadzone": 0.015,
    "max_abs_steering": 0.76,
    "hard_turn_steering_scale": 0.84,
    "steering_speed_cap_scale": 0.36,



    "inside_margin_warning": 0.34,
    "inside_margin_outward_gain": 0.0,
    "inside_margin_steering_cap": 1.0,
    "inside_margin_slowdown": 0.0,
    "inside_left_lateral_min": 0.05,
    "inside_left_heading_max": -0.24,
    "inside_left_curvature_max": -0.45,
    "inside_left_steering_limit": -0.40,
    "curve_slowdown": 0.64,
    "curve_power": 1.18,
    "offset_slowdown": 0.38,
    "offset_power": 1.25,
    "min_confidence_factor": 0.58,
    "steering_slowdown": 0.18,
    "steering_power": 1.15,
    "steering_smoothing_cruise": 0.16,
    "steering_smoothing_turn": 0.14,
    "steering_smoothing_correction": 0.14,
    "steering_smoothing_recovery": 0.28,
    "max_steering_delta": 0.46,
    "max_speed_increase_per_sec": 1.85,
    "max_speed_decrease_per_sec": 4.80,
    "escape_min_confidence": 0.48,
    "escape_curve_threshold": 0.45,
    "escape_steering_threshold": 0.70,
    "escape_offset_threshold": 0.62,
    "escape_offset_speed_threshold": 0.36,
    "escape_offset_heading_abs_max": 0.18,
    "escape_offset_curve_abs_max": 0.30,
    "escape_offset_lookahead_alignment": 0.30,
    "escape_offset_trigger_frames": 14,
    "escape_low_speed_threshold": 0.22,
    "escape_low_speed_trigger_frames": 120,
    "escape_signature_delta": 0.13,



    "escape_turn_speed_max": 0.36,
    "escape_trigger_frames": 18,
    "escape_turn_frames": 24,
    "escape_turn_steering": 0.58,
    "escape_turn_speed": 0.62,
    "escape_offset_frames": 72,
    "escape_offset_steering": 0.74,
    "escape_offset_speed": 0.78,
    "escape_low_speed_frames": 120,
    "escape_low_speed_steering": 0.74,
    "escape_low_speed_speed": 0.90,
    "escape_pinned_lateral_min": 0.45,
    "escape_pinned_steering_min": 0.55,
    "escape_pinned_speed_max": 0.55,
    "escape_pinned_trigger_frames": 20,
    "escape_pinned_frames": 28,
    "escape_pinned_steering": 0.80,
    "escape_pinned_speed": 0.62,


    "escape_boundary_margin_risk": 0.90,
    "escape_boundary_margin_max": 0.08,
    "escape_boundary_speed_max": 0.46,
    "escape_boundary_min_confidence": 0.35,
    "escape_boundary_trigger_frames": 8,
    "escape_boundary_frames": 72,
    "escape_boundary_steering": 0.86,
    "escape_boundary_speed": 0.86,
    "nominal_dt": 0.032,
    "timestamp_reset_gap": 2.0,
}

BASIC_CONTROL_OVERRIDES = {
    "lost_speed": 0.24,
    "recovery_speed": 0.38,
    "straight_speed": 1.00,
    "straight_lost_speed": 1.00,
    "hard_turn_speed": 0.30,
    "hard_turn_center_speed_bonus": 0.30,
    "correction_speed": 0.50,
    "far_conflict_offset_start": 0.00,
    "far_conflict_offset_scale": 3.20,
    "far_conflict_min_scale": 0.05,
    "gain_lateral": 0.86,
    "gain_lookahead": 0.68,
    "gain_heading": 0.68,
    "gain_curve": 0.10,
    "near_weight_offset_boost": 0.58,
    "far_weight_curve_boost": 0.28,
    "max_abs_steering": 0.74,
    "hard_turn_steering_scale": 0.78,
    "steering_speed_cap_scale": 0.42,
    "curve_slowdown": 0.70,
    "curve_power": 1.35,
    "steering_slowdown": 0.28,
    "max_speed_increase_per_sec": 1.60,
    "max_speed_decrease_per_sec": 2.20,
}


def get_profile(name: str) -> dict:
\
\
\
\
\
\


    del name
    return dict(CONTROL)



# ---- opponent.py ----

"""对手车辆感知模块。

功能概述：保留可提交的近处车身检测逻辑，供后续多车策略使用。
输入输出：输入单张 BGR 图像，输出是否检测到近距离车身遮挡。
处理流程：截取下半部中间 ROI，只提取亮白和近黑候选块，再用连通域尺寸过滤噪声。
"""




def detect_near_vehicle_obstacle(image: np.ndarray, profile: dict | None = None) -> bool:
\
\
\
\
\
\
\


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
    bright_body = (gray > params["near_obstacle_white_gray_min"]) & (
        saturation < params["near_obstacle_white_sat_max"]
    )
    dark_body = (gray < params["near_obstacle_black_gray_max"]) & (value < params["near_obstacle_black_value_max"])
    candidate = (bright_body | dark_body).astype(np.uint8) * 255

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



# ---- perception.py ----

"""视觉感知模块。

功能概述：从左右摄像头图像中分割道路表面，并沿扫描线跟踪可行驶走廊。
输入输出：输入 BGR 图像和可选时间戳，输出 `PerceptionObs`。
处理流程：估计道路颜色，生成道路 mask，逐行选择连续走廊，再融合左右摄像头结果。
"""




_RED_ENVIRONMENT_FLAG = 32


@dataclass
class _CameraScan:
\
\
\
\
\
\


    center_points: np.ndarray
    left_edge_points: np.ndarray
    right_edge_points: np.ndarray
    road_width_est: float
    confidence: float
    debug_flags: int = 0
    near_obstacle: bool = False


def _empty_points() -> np.ndarray:
    return np.empty((0, 2), dtype=np.float32)


def _empty_scan(debug_flags: int = 1) -> _CameraScan:
    points = _empty_points()
    return _CameraScan(points, points, points, 0.0, 0.0, debug_flags=debug_flags)


def _empty_obs(debug_flags: int = 1) -> PerceptionObs:
    points = _empty_points()
    return PerceptionObs(points, points, points, 0.0, 0.0, debug_flags=debug_flags)


def _valid_image(image) -> bool:


    return image is not None and hasattr(image, "shape") and len(image.shape) == 3 and image.shape[2] == 3


def _is_red_environment(image: np.ndarray) -> bool:


    height = image.shape[0]
    roi = image[int(height * 0.30) : int(height * 0.88), :]
    if roi.size == 0:
        return False
    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    hue = hsv[:, :, 0]
    saturation = hsv[:, :, 1]
    value = hsv[:, :, 2]
    red = ((hue < 12) | (hue > 168)) & (saturation > 80) & (value > 50)
    red_ratio = float(np.count_nonzero(red)) / max(float(red.size), 1.0)
    return red_ratio >= VISION_PROFILE["red_world_min_ratio"]


def _hue_delta(hue: np.ndarray, center: float) -> np.ndarray:


    delta = np.abs(hue.astype(np.float32) - float(center))
    return np.minimum(delta, 180.0 - delta)


def _sampled_color_mask(hsv: np.ndarray, lab: np.ndarray, color_name: str) -> np.ndarray:
\
\
\
\
\
\


    profile = COLOR_PROFILE[color_name]
    hsv_center = profile["hsv_median"]
    hsv_tol = profile["hsv_tolerance"]
    lab_center = profile["lab_median"]
    lab_tol = profile["lab_tolerance"]
    hsv_match = (
        (_hue_delta(hsv[:, :, 0], hsv_center[0]) <= hsv_tol[0])
        & (np.abs(hsv[:, :, 1].astype(np.float32) - hsv_center[1]) <= hsv_tol[1])
        & (np.abs(hsv[:, :, 2].astype(np.float32) - hsv_center[2]) <= hsv_tol[2])
    )
    lab_match = (
        (np.abs(lab[:, :, 0] - lab_center[0]) <= lab_tol[0])
        & (np.abs(lab[:, :, 1] - lab_center[1]) <= lab_tol[1])
        & (np.abs(lab[:, :, 2] - lab_center[2]) <= lab_tol[2])
    )
    return hsv_match & lab_match


def _build_masks(image: np.ndarray, timestamp=None) -> tuple[np.ndarray, np.ndarray, float, float, bool]:
\
\
\
\
\
\
\


    height = image.shape[0]
    top = int(height * VISION_PROFILE["roi_top_ratio"])
    roi = image[top:, :, :]

    gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    hsv_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    lab_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB).astype(np.float32)
    bgr_roi = roi.astype(np.float32)
    road_color = COLOR_PROFILE["road_asphalt_dark_gray"]
    b_minus_g = bgr_roi[:, :, 0] - bgr_roi[:, :, 1]
    g_minus_r = bgr_roi[:, :, 1] - bgr_roi[:, :, 2]
    road_core = (
        _sampled_color_mask(hsv_roi, lab_roi, "road_asphalt_dark_gray")
        & (gray_roi >= VISION_PROFILE["road_gray_min"])
        & (gray_roi <= VISION_PROFILE["road_gray_max"])
        & (b_minus_g >= road_color["b_minus_g_min"])
        & (b_minus_g <= road_color["b_minus_g_max"])
        & (g_minus_r >= road_color["g_minus_r_min"])
        & (g_minus_r <= road_color["g_minus_r_max"])
    )
    non_road_roi = (
        _sampled_color_mask(hsv_roi, lab_roi, "green_grass")
        | _sampled_color_mask(hsv_roi, lab_roi, "red_ground")
        | _sampled_color_mask(hsv_roi, lab_roi, "blue_sky")
    )

    curb_roi = _sampled_color_mask(hsv_roi, lab_roi, "curb_shoulder_light_gray") & (
        lab_roi[:, :, 0] > COLOR_PROFILE["road_asphalt_dark_gray"]["lab_median"][0] + 10.0
    )
    dark_road_roi = (road_core & ~non_road_roi & ~curb_roi).astype(np.uint8) * 255

    road_roi = dark_road_roi.copy()


    road_roi[non_road_roi | curb_roi] = 0






    barrier_candidate = (
        (hsv_roi[:, :, 0] >= VISION_PROFILE["barrier_hue_min"])
        & (hsv_roi[:, :, 0] <= VISION_PROFILE["barrier_hue_max"])
        & (hsv_roi[:, :, 1] >= VISION_PROFILE["barrier_sat_min"])
        & (hsv_roi[:, :, 2] >= VISION_PROFILE["barrier_value_min"])
        & (hsv_roi[:, :, 2] <= VISION_PROFILE["barrier_value_max"])
    )


    row_ratio = np.count_nonzero(barrier_candidate, axis=1) / max(float(barrier_candidate.shape[1]), 1.0)
    barrier_rows = row_ratio >= VISION_PROFILE["barrier_bridge_row_ratio"]
    barrier_roi = barrier_candidate & barrier_rows[:, None]
    road_roi[barrier_roi] = 255

    kernel = np.ones((5, 5), dtype=np.uint8)
    road_roi = cv2.morphologyEx(road_roi, cv2.MORPH_OPEN, kernel, iterations=1)
    road_roi = cv2.morphologyEx(road_roi, cv2.MORPH_CLOSE, kernel, iterations=2)

    blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    edge_roi = cv2.Canny(blurred, 45, 120)

    road_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    edge_mask = np.zeros(image.shape[:2], dtype=np.uint8)
    road_mask[top:, :] = road_roi
    edge_mask[top:, :] = edge_roi

    texture_score = clamp(float(np.std(gray_roi)) / VISION_PROFILE["texture_gray_std_scale"], 0.0, 1.0)
    mask_fill_ratio = float(np.count_nonzero(road_roi)) / max(float(road_roi.size), 1.0)
    near_obstacle = False
    if OPPONENT_PROFILE["enable_opponent_avoidance"]:
        try:
            current_time = float(timestamp)
        except (TypeError, ValueError):
            current_time = 0.0
        near_obstacle = (
            current_time >= OPPONENT_PROFILE["near_obstacle_min_timestamp"]
            and detect_near_vehicle_obstacle(image, OPPONENT_PROFILE)
        )
    return road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle


def _segments_from_active(active: np.ndarray) -> list[tuple[int, int]]:


    if active.size == 0:
        return []
    padded = np.concatenate(([False], active.astype(bool), [False]))
    changes = np.flatnonzero(padded[1:] != padded[:-1])
    return [(int(changes[i]), int(changes[i + 1] - 1)) for i in range(0, len(changes), 2)]


def _camera_line_state(image: np.ndarray, profile: dict) -> tuple[float, float, float] | None:
\
\
\
\
\
\


    if not _valid_image(image):
        return None
    height, width = image.shape[:2]
    lower = int(profile["white_min"])
    y_top = int(height * profile["scan_top_ratio"])
    y_bottom = int(height * profile["scan_bottom_ratio"])
    rows = np.linspace(y_bottom, y_top, int(profile["scan_count"]), dtype=np.int32)
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
        band = image[y0:y1, :, :]
        white = np.all(band >= lower, axis=2)
        active = np.count_nonzero(white, axis=0) >= 2
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

    if len(points) < int(profile["min_points_per_camera"]):
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


def _startup_single_line_candidate(
    line: tuple[float, float, float] | None,
    profile: dict,
    timestamp,
) -> tuple[float, float, float] | None:
\
\
\
\
\
\
\


    if line is None:
        return None
    try:
        current_time = float(timestamp)
    except (TypeError, ValueError):
        return None
    offset, heading, confidence = line
    if current_time > profile["startup_acquire_until"]:
        return None
    if confidence < profile["min_confidence"]:
        return None
    if not (profile["startup_offset_min"] <= offset <= profile["startup_offset_trust_max"]):
        return None
    if not (profile["startup_heading_min"] <= heading <= profile["startup_heading_max"]):
        return None
    return line


def _stereo_line_state(left_img, right_img, profile: dict, timestamp=None) -> tuple[float, float, float]:
\
\
\
\
\
\
\


    if not profile["enable"]:
        return 0.0, 0.0, 0.0
    left = _camera_line_state(left_img, profile)
    right = _camera_line_state(right_img, profile)
    if left is None or right is None:
        single = _startup_single_line_candidate(left or right, profile, timestamp)
        if single is not None:
            return single
        return 0.0, 0.0, 0.0
    confidence = min(left[2], right[2])
    if confidence < profile["min_confidence"]:
        return 0.0, 0.0, confidence
    offset = (left[0] + right[0]) * 0.5
    heading = (left[1] + right[1]) * 0.5
    return clamp(offset, -1.0, 1.0), clamp(heading, -1.0, 1.0), confidence


def _merge_close_segments(segments: list[tuple[int, int]], max_gap: int | None = None) -> list[tuple[int, int]]:


    if not segments:
        return []
    if max_gap is None:
        max_gap = int(VISION_PROFILE["max_segment_gap"])
    merged = [segments[0]]
    for left, right in segments[1:]:
        prev_left, prev_right = merged[-1]
        if left - prev_right - 1 <= max_gap:
            merged[-1] = (prev_left, right)
        else:
            merged.append((left, right))
    return merged


def _road_segments(mask: np.ndarray, y: int, row_band: int, max_gap: int | None = None) -> list[tuple[int, int]]:


    y0 = max(int(y) - row_band, 0)
    y1 = min(int(y) + row_band + 1, mask.shape[0])
    band = mask[y0:y1, :]
    min_hits = max(1, int(np.ceil(band.shape[0] * 0.45)))
    active = np.count_nonzero(band, axis=0) >= min_hits
    return _merge_close_segments(_segments_from_active(active), max_gap=max_gap)


def _edge_fallback_segments(edge_mask: np.ndarray, y: int, row_band: int) -> list[tuple[int, int]]:
\
\
\
\
\
\


    y0 = max(int(y) - row_band, 0)
    y1 = min(int(y) + row_band + 1, edge_mask.shape[0])
    band = edge_mask[y0:y1, :]
    active = np.count_nonzero(band, axis=0) > 0
    edge_segments = _segments_from_active(active)
    if len(edge_segments) < 2:
        return []

    edge_centers = [int((left + right) * 0.5) for left, right in edge_segments]
    return [(edge_centers[index], edge_centers[index + 1]) for index in range(len(edge_centers) - 1)]


def _filter_segments(
    segments: list[tuple[int, int]],
    width: int,
    max_width_ratio: float | None = None,
) -> list[tuple[int, int]]:


    min_width = float(VISION_PROFILE["min_segment_width"])
    if max_width_ratio is None:
        max_width_ratio = VISION_PROFILE["max_segment_width_ratio"]
    max_width = float(width) * float(max_width_ratio)
    filtered = []
    for left, right in segments:
        segment_width = float(right - left + 1)
        if min_width <= segment_width <= max_width:
            filtered.append((left, right))
    return filtered


def _filter_fallback_segments(
    segments: list[tuple[int, int]],
    width: int,
    previous_center: float,
    has_previous: bool,
) -> list[tuple[int, int]]:
\
\
\
\
\
\


    if not segments:
        return []

    min_width = float(VISION_PROFILE["fallback_min_segment_width"])
    initial_center_limit = float(width) * VISION_PROFILE["fallback_initial_center_max_offset"]
    narrow_jump_limit = float(width) * VISION_PROFILE["fallback_narrow_jump_max_ratio"]
    image_center = float(width) * 0.5

    filtered = []
    for left, right in segments:
        segment_width = float(right - left + 1)
        center = (float(left) + float(right)) * 0.5
        if segment_width >= min_width:
            filtered.append((left, right))
        elif not has_previous and abs(center - image_center) <= initial_center_limit:
            filtered.append((left, right))
        elif has_previous and abs(center - previous_center) <= narrow_jump_limit:
            filtered.append((left, right))
    return filtered


def _localize_wide_segment(
    segment: tuple[int, int],
    previous_center: float,
    width: int,
    enabled: bool = True,
) -> tuple[int, int]:
\
\
\
\
\
\


    left, right = segment
    segment_width = float(right - left + 1)
    if not enabled:
        return segment
    if segment_width <= float(width) * VISION_PROFILE["wide_segment_localize_ratio"]:
        return segment

    target_width = max(
        VISION_PROFILE["min_segment_width"],
        float(width) * VISION_PROFILE["wide_segment_window_ratio"],
    )
    half = target_width * 0.5
    center = previous_center
    center = clamp(center, float(left) + half, float(right) - half)
    localized_left = max(left, int(round(center - half)))
    localized_right = min(right, int(round(center + half)))
    if localized_right <= localized_left:
        return segment
    return localized_left, localized_right


def _pick_segment(
    road_mask: np.ndarray,
    edge_mask: np.ndarray,
    y: int,
    previous_center: float,
    has_previous: bool,
    near_obstacle: bool,
    wide_localize_enabled: bool,
) -> tuple[tuple[int, int] | None, bool]:
\
\
\
\
\
\


    width = road_mask.shape[1]
    row_band = int(VISION_PROFILE["row_band"])
    max_width_ratio = (
        VISION_PROFILE["max_segment_width_ratio"]
        if wide_localize_enabled
        else VISION_PROFILE["early_max_segment_width_ratio"]
    )
    max_gap = None
    if near_obstacle and y >= int(road_mask.shape[0] * OPPONENT_PROFILE["near_obstacle_scan_y_ratio"]):
        max_gap = int(OPPONENT_PROFILE["near_obstacle_segment_gap"])
    candidates = _filter_segments(
        _road_segments(road_mask, y, row_band, max_gap=max_gap),
        width,
        max_width_ratio=max_width_ratio,
    )
    used_fallback = False
    if not candidates:
        candidates = _filter_segments(
            _edge_fallback_segments(edge_mask, y, row_band),
            width,
            max_width_ratio=max_width_ratio,
        )
        candidates = _filter_fallback_segments(candidates, width, previous_center, has_previous)
        used_fallback = bool(candidates)
    if not candidates:
        return None, used_fallback

    best = min(candidates, key=lambda item: abs(((item[0] + item[1]) * 0.5) - previous_center))
    best = _localize_wide_segment(best, previous_center, width, enabled=wide_localize_enabled)
    center = (best[0] + best[1]) * 0.5
    max_jump = float(width) * VISION_PROFILE["max_center_jump_ratio"]
    if has_previous and abs(center - previous_center) > max_jump:
        return None, used_fallback
    return best, used_fallback


def _score_scan(
    centers: list[tuple[float, float]],
    widths: list[float],
    texture_score: float,
    mask_fill_ratio: float,
    fallback_count: int,
    red_environment: bool = False,
) -> tuple[float, int]:
\
\
\
\
\
\
\


    debug_flags = 0
    scan_count = float(VISION_PROFILE["scan_count"])
    valid_count = len(centers)
    valid_ratio = valid_count / max(scan_count, 1.0)

    width_arr = np.array(widths, dtype=np.float32)
    width_median = max(float(np.median(width_arr)), 1.0)
    width_stability = clamp(1.0 - float(np.std(width_arr)) / width_median, 0.0, 1.0)

    center_arr = np.array([point[0] for point in centers], dtype=np.float32)
    if center_arr.size >= 2:
        center_jump = np.abs(np.diff(center_arr))
        center_stability = clamp(
            1.0 - float(np.mean(center_jump)) / (640.0 * VISION_PROFILE["max_center_jump_ratio"]),
            0.0,
            1.0,
        )
    else:
        center_stability = 0.0

    confidence = (
        valid_ratio * 0.38
        + width_stability * 0.22
        + center_stability * 0.22
        + texture_score * 0.18
    )

    min_valid = int(VISION_PROFILE["min_valid_scans"])
    if valid_count < min_valid:
        confidence *= valid_count / max(float(min_valid), 1.0)
        debug_flags |= 1
    if mask_fill_ratio < 0.015:
        confidence *= VISION_PROFILE["empty_mask_confidence_scale"]
        debug_flags |= 4
    elif mask_fill_ratio > 0.92:
        confidence *= VISION_PROFILE["saturated_mask_confidence_scale"]
        debug_flags |= 4
    elif red_environment and mask_fill_ratio > VISION_PROFILE["red_mask_fill_warning"]:
        confidence *= VISION_PROFILE["red_mask_fill_confidence_scale"]
        debug_flags |= 4
    if fallback_count:
        confidence *= max(0.55, 1.0 - 0.06 * fallback_count)
        debug_flags |= 2

    return clamp(confidence, 0.0, 1.0), debug_flags


def _scan_image(image: np.ndarray, timestamp=None) -> _CameraScan:
\
\
\
\
\
\


    if not _valid_image(image):
        return _empty_scan()

    road_mask, edge_mask, texture_score, mask_fill_ratio, near_obstacle = _build_masks(image, timestamp)
    red_environment = _is_red_environment(image)
    wide_localize_enabled = red_environment
    height, width = road_mask.shape
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
    previous_center = width * 0.5
    has_previous = False
    fallback_count = 0

    for y in rows:
        segment, used_fallback = _pick_segment(
            road_mask,
            edge_mask,
            int(y),
            previous_center,
            has_previous,
            near_obstacle,
            wide_localize_enabled,
        )
        if segment is None:
            continue
        left, right = segment
        center = (left + right) * 0.5
        road_width = float(right - left + 1)
        centers.append((center, float(y)))
        left_edges.append((float(left), float(y)))
        right_edges.append((float(right), float(y)))
        widths.append(road_width)
        previous_center = center
        has_previous = True
        if used_fallback:
            fallback_count += 1

    if not centers:
        debug_flags = 4 if mask_fill_ratio < 0.015 or mask_fill_ratio > 0.92 else 1
        scan = _empty_scan(debug_flags=debug_flags)
        scan.near_obstacle = bool(near_obstacle)
        return scan

    confidence, debug_flags = _score_scan(
        centers,
        widths,
        texture_score,
        mask_fill_ratio,
        fallback_count,
        red_environment=red_environment,
    )
    if red_environment:
        debug_flags |= _RED_ENVIRONMENT_FLAG
    return _CameraScan(
        np.array(centers, dtype=np.float32),
        np.array(left_edges, dtype=np.float32),
        np.array(right_edges, dtype=np.float32),
        float(np.median(np.array(widths, dtype=np.float32))),
        confidence,
        debug_flags=debug_flags,
        near_obstacle=bool(near_obstacle),
    )


def _usable(scan: _CameraScan) -> bool:


    return scan.center_points.size > 0 and scan.confidence >= VISION_PROFILE["min_camera_confidence"]


def _near_center(scan: _CameraScan) -> float:


    if scan.center_points.size == 0:
        return 320.0
    return float(scan.center_points[0, 0])


def _to_obs(scan: _CameraScan, debug_flags: int | None = None) -> PerceptionObs:


    flags = scan.debug_flags if debug_flags is None else debug_flags
    return PerceptionObs(
        scan.center_points,
        scan.left_edge_points,
        scan.right_edge_points,
        scan.road_width_est,
        clamp(scan.confidence, 0.0, 1.0),
        debug_flags=flags,
        near_obstacle=bool(scan.near_obstacle),
    )


def _fuse_scans(left_scan: _CameraScan, right_scan: _CameraScan) -> PerceptionObs:
\
\
\
\
\
\


    left_ok = _usable(left_scan)
    right_ok = _usable(right_scan)
    if left_ok and not right_ok:
        return _to_obs(left_scan)
    if right_ok and not left_ok:
        return _to_obs(right_scan)
    if not left_ok and not right_ok:
        obs = _empty_obs(debug_flags=left_scan.debug_flags | right_scan.debug_flags | 1)
        obs.near_obstacle = bool(left_scan.near_obstacle or right_scan.near_obstacle)
        return obs

    center_gap = abs(_near_center(left_scan) - _near_center(right_scan))
    merge_gap = 640.0 * VISION_PROFILE["fusion_merge_gap"]
    merge_confidence = VISION_PROFILE["fusion_merge_min_confidence"]
    confidence_gap = abs(left_scan.confidence - right_scan.confidence)
    if (
        center_gap >= merge_gap
        or left_scan.confidence < merge_confidence
        or right_scan.confidence < merge_confidence
    ):
        chosen = left_scan if left_scan.confidence >= right_scan.confidence else right_scan
        flags = chosen.debug_flags
        if center_gap > 640.0 * VISION_PROFILE["fusion_max_offset_gap"]:
            flags |= 8
        if confidence_gap < VISION_PROFILE["fusion_confidence_margin"]:
            flags |= 16
        return _to_obs(chosen, debug_flags=flags)

    center_points = np.concatenate([left_scan.center_points, right_scan.center_points], axis=0)
    left_edge_points = np.concatenate([left_scan.left_edge_points, right_scan.left_edge_points], axis=0)
    right_edge_points = np.concatenate([left_scan.right_edge_points, right_scan.right_edge_points], axis=0)
    weights = np.array([len(left_scan.center_points), len(right_scan.center_points)], dtype=np.float32)
    confidences = np.array([left_scan.confidence, right_scan.confidence], dtype=np.float32)
    width_values = np.array([left_scan.road_width_est, right_scan.road_width_est], dtype=np.float32)
    confidence = float(np.average(confidences, weights=weights))
    road_width_est = float(np.average(width_values, weights=weights))
    return PerceptionObs(
        center_points,
        left_edge_points,
        right_edge_points,
        road_width_est,
        clamp(confidence, 0.0, 1.0),
        debug_flags=left_scan.debug_flags | right_scan.debug_flags,
        near_obstacle=bool(left_scan.near_obstacle or right_scan.near_obstacle),
    )


def _with_line_state(obs: PerceptionObs, left_img, right_img, timestamp=None) -> PerceptionObs:
\
\
\
\


    line_offset, line_heading, line_confidence = _stereo_line_state(
        left_img,
        right_img,
        LINE_FOLLOW_PROFILE,
        timestamp,
    )
    obs.line_offset = line_offset
    obs.line_heading = line_heading
    obs.line_confidence = line_confidence
    return obs


def extract_observation(left_img, right_img, timestamp=None) -> PerceptionObs:
\
\
\
\
\
\


    left_scan = _scan_image(left_img, timestamp) if _valid_image(left_img) else _empty_scan()
    right_scan = _scan_image(right_img, timestamp) if _valid_image(right_img) else _empty_scan()
    obs = _fuse_scans(left_scan, right_scan)
    return _with_line_state(obs, left_img, right_img, timestamp)



# ---- estimator.py ----

"""赛道几何估计模块。

功能概述：把感知中心点转换成稳定的赛道状态。
输入输出：输入 `PerceptionObs` 和时间戳，输出 `TrackState`。
处理流程：清洗中心点，按 progress 拟合中心线，估计偏移、朝向和曲率，再按置信度平滑。
"""



_LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
_LAST_TIMESTAMP = None
_LAST_RED_ENVIRONMENT = False
_RED_ENVIRONMENT_STREAK = 0
_RED_ENVIRONMENT_FLAG = 32
_RED_ENVIRONMENT_LATCH_FRAMES = 3
_LINE_MEMORY_FRAMES = 0
_LINE_MEMORY_OFFSET = 0.0
_LINE_MEMORY_HEADING = 0.0
_LINE_MEMORY_CONFIDENCE = 0.0


def _lost_track(
    confidence: float,
    red_environment: bool | None = None,
    obs: PerceptionObs | None = None,
) -> TrackState:
\
\
\
\
\
\
\
\


    if red_environment is None:
        red_environment = _LAST_TRACK.red_environment
    if obs is not None:
        line_offset = clamp(float(obs.line_offset), -1.0, 1.0)
        line_heading = clamp(float(obs.line_heading), -1.0, 1.0)
        line_confidence = clamp(float(obs.line_confidence), 0.0, 1.0)
        near_obstacle = bool(obs.near_obstacle)
    else:
        line_offset = _LAST_TRACK.line_offset
        line_heading = _LAST_TRACK.line_heading
        line_confidence = 0.0
        near_obstacle = _LAST_TRACK.near_obstacle
    return TrackState(
        _LAST_TRACK.lateral_error * ESTIMATOR_PROFILE["lost_lateral_decay"],
        _LAST_TRACK.heading_error * ESTIMATOR_PROFILE["lost_heading_decay"],
        _LAST_TRACK.curvature * ESTIMATOR_PROFILE["lost_curvature_decay"],
        _LAST_TRACK.lookahead_error * ESTIMATOR_PROFILE["lost_lookahead_decay"],
        clamp(confidence, 0.0, ESTIMATOR_PROFILE["lost_confidence"]),
        True,
        red_environment,
        line_offset,
        line_heading,
        line_confidence,
        _LAST_TRACK.left_margin_near,
        _LAST_TRACK.right_margin_near,
        near_obstacle,
    )


def _clean_points(points) -> np.ndarray:
\
\
\
\
\
\


    try:
        array = np.asarray(points, dtype=np.float32)
    except (TypeError, ValueError):
        return np.empty((0, 2), dtype=np.float32)
    if array.ndim != 2 or array.shape[1] != 2:
        return np.empty((0, 2), dtype=np.float32)
    return array[np.isfinite(array).all(axis=1)]


def _normalize_points(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
\
\
\
\
\
\


    y = points[:, 1].astype(np.float32)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_span = max(y_max - y_min, 0.0)
    progress = (y_max - y) / max(y_span, 1.0)

    x = points[:, 0].astype(np.float32)
    x_norm = (x - ESTIMATOR_PROFILE["image_center_x"]) / ESTIMATOR_PROFILE["x_scale"]
    x_norm = np.clip(x_norm, -1.0, 1.0)
    return x_norm.astype(np.float32), progress.astype(np.float32), y_span


def _near_edge_margin(edge_points, side: str) -> float:


    points = _clean_points(edge_points)
    if len(points) == 0:
        return 1.0
    y = points[:, 1].astype(np.float32)
    y_min = float(np.min(y))
    y_max = float(np.max(y))
    y_span = max(y_max - y_min, 1.0)
    near_mask = y >= y_min + y_span * 0.62
    if not np.any(near_mask):
        near_mask = np.ones(len(points), dtype=bool)
    x = float(np.median(points[near_mask, 0]))
    center = ESTIMATOR_PROFILE["image_center_x"]
    scale = ESTIMATOR_PROFILE["x_scale"]
    if side == "left":
        return clamp((center - x) / scale, 0.0, 1.0)
    return clamp((x - center) / scale, 0.0, 1.0)


def _line_weight(line_confidence: float) -> float:


    min_confidence = ESTIMATOR_PROFILE["line_target_min_confidence"]
    if line_confidence < min_confidence:
        return 0.0
    usable = (line_confidence - min_confidence) / max(1.0 - min_confidence, 1e-6)
    return clamp(usable, 0.0, 1.0)


def _line_target_trust(obs: PerceptionObs, timestamp: float, red_environment: bool) -> float:
\
\
\
\
\
\
\


    base = _line_weight(obs.line_confidence)
    if base <= 0.0:
        return 0.0

    startup_valid = (
        red_environment
        and timestamp <= ESTIMATOR_PROFILE["line_startup_until"]
        and ESTIMATOR_PROFILE["line_startup_offset_min"]
        <= obs.line_offset
        <= ESTIMATOR_PROFILE["line_startup_offset_max"]
        and ESTIMATOR_PROFILE["line_startup_heading_min"]
        <= obs.line_heading
        <= ESTIMATOR_PROFILE["line_startup_heading_max"]
    )
    normal_valid = abs(obs.line_offset) <= ESTIMATOR_PROFILE["line_target_normal_offset_max"]
    if not startup_valid and not normal_valid:
        return 0.0

    if startup_valid:
        scale = ESTIMATOR_PROFILE["line_target_startup_scale"]
    elif obs.confidence <= ESTIMATOR_PROFILE["line_target_road_confidence_max"] or obs.debug_flags & 4:
        scale = ESTIMATOR_PROFILE["line_target_unreliable_road_scale"]
    else:
        scale = ESTIMATOR_PROFILE["line_target_normal_scale"]
    return clamp(base * scale, 0.0, 1.0)


def _update_line_memory(obs: PerceptionObs, line_trust: float, timestamp: float, red_environment: bool) -> float:
\
\
\
\
\
\


    global _LINE_MEMORY_FRAMES, _LINE_MEMORY_OFFSET, _LINE_MEMORY_HEADING, _LINE_MEMORY_CONFIDENCE

    in_startup = red_environment and timestamp <= ESTIMATOR_PROFILE["line_startup_until"]
    startup_line = (
        ESTIMATOR_PROFILE["line_startup_offset_min"]
        <= obs.line_offset
        <= ESTIMATOR_PROFILE["line_startup_offset_max"]
        and ESTIMATOR_PROFILE["line_startup_heading_min"]
        <= obs.line_heading
        <= ESTIMATOR_PROFILE["line_startup_heading_max"]
    )
    if line_trust > 0.0 and in_startup and startup_line:
        _LINE_MEMORY_FRAMES = int(ESTIMATOR_PROFILE["line_startup_memory_frames"])
        _LINE_MEMORY_OFFSET = clamp(float(obs.line_offset), -1.0, 1.0)
        _LINE_MEMORY_HEADING = clamp(float(obs.line_heading), -1.0, 1.0)
        _LINE_MEMORY_CONFIDENCE = clamp(float(obs.line_confidence), 0.0, 1.0)
        return line_trust

    if not in_startup or _LINE_MEMORY_FRAMES <= 0:
        if not in_startup:
            _LINE_MEMORY_FRAMES = 0
        return line_trust

    _LINE_MEMORY_FRAMES -= 1
    _LINE_MEMORY_OFFSET *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    _LINE_MEMORY_HEADING *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    _LINE_MEMORY_CONFIDENCE *= ESTIMATOR_PROFILE["line_startup_memory_value_decay"]
    obs.line_offset = _LINE_MEMORY_OFFSET
    obs.line_heading = _LINE_MEMORY_HEADING
    obs.line_confidence = _LINE_MEMORY_CONFIDENCE
    remembered_trust = _line_target_trust(obs, timestamp, red_environment)
    return clamp(remembered_trust * ESTIMATOR_PROFILE["line_startup_memory_trust_scale"], 0.0, 1.0)


def _apply_line_target(
    lateral_error: float,
    heading_error: float,
    lookahead_error: float,
    obs: PerceptionObs,
    line_trust: float,
) -> tuple[float, float, float]:


    if line_trust <= 0.0:
        return lateral_error, heading_error, lookahead_error
    lateral_weight = line_trust * ESTIMATOR_PROFILE["line_lateral_weight"]
    heading_weight = line_trust * ESTIMATOR_PROFILE["line_heading_weight"]
    lookahead_weight = line_trust * ESTIMATOR_PROFILE["line_lookahead_weight"]
    projected_lookahead = clamp(
        obs.line_offset + obs.line_heading * ESTIMATOR_PROFILE["line_lookahead_projection"],
        -1.0,
        1.0,
    )
    return (
        clamp(lateral_error * (1.0 - lateral_weight) + obs.line_offset * lateral_weight, -1.0, 1.0),
        clamp(heading_error * (1.0 - heading_weight) + obs.line_heading * heading_weight, -1.0, 1.0),
        clamp(lookahead_error * (1.0 - lookahead_weight) + projected_lookahead * lookahead_weight, -1.0, 1.0),
    )


def _line_only_track(obs: PerceptionObs, timestamp: float, red_environment: bool, line_trust: float) -> TrackState:
\
\
\
\
\
\


    del timestamp
    confidence = clamp(
        max(ESTIMATOR_PROFILE["lost_confidence"] + 0.04, obs.line_confidence * ESTIMATOR_PROFILE["line_target_confidence_scale"]),
        0.0,
        1.0,
    )
    lateral_error = clamp(obs.line_offset * line_trust, -1.0, 1.0)
    heading_error = clamp(obs.line_heading * line_trust, -1.0, 1.0)
    lookahead_error = clamp(
        (obs.line_offset + obs.line_heading * ESTIMATOR_PROFILE["line_lookahead_projection"]) * line_trust,
        -1.0,
        1.0,
    )
    alpha = _smooth_alpha(confidence)
    track = TrackState(
        _smooth_limited(_LAST_TRACK.lateral_error, lateral_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        _smooth_limited(_LAST_TRACK.heading_error, heading_error, alpha, ESTIMATOR_PROFILE["max_heading_delta"]),
        _smooth_limited(_LAST_TRACK.curvature, 0.0, ESTIMATOR_PROFILE["curve_smooth_alpha"], ESTIMATOR_PROFILE["max_curvature_delta"]),
        _smooth_limited(_LAST_TRACK.lookahead_error, lookahead_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        confidence,
        False,
        red_environment,
        clamp(float(obs.line_offset), -1.0, 1.0),
        clamp(float(obs.line_heading), -1.0, 1.0),
        clamp(float(obs.line_confidence), 0.0, 1.0),
        _LAST_TRACK.left_margin_near,
        _LAST_TRACK.right_margin_near,
        bool(obs.near_obstacle),
    )
    return track


def _fit_centerline(progress: np.ndarray, x_norm: np.ndarray) -> tuple[np.ndarray, int]:
\
\
\
\
\
\


    degree = 2 if len(progress) >= ESTIMATOR_PROFILE["poly2_min_points"] else 1
    coeffs = np.polyfit(progress, x_norm, deg=degree)
    return coeffs.astype(np.float32), degree


def _value_from_band(
    progress: np.ndarray,
    x_norm: np.ndarray,
    coeffs: np.ndarray,
    mask: np.ndarray,
    fallback_progress: float,
) -> float:


    if np.any(mask):
        return float(np.median(x_norm[mask]))
    return float(np.polyval(coeffs, fallback_progress))


def _heading_from_fit(coeffs: np.ndarray, degree: int) -> float:


    eval_progress = ESTIMATOR_PROFILE["heading_eval_progress"]
    if degree == 2:
        derivative = float(2.0 * coeffs[0] * eval_progress + coeffs[1])
    else:
        derivative = float(coeffs[0])
    return clamp(derivative * ESTIMATOR_PROFILE["heading_gain"], -1.0, 1.0)


def _curvature_trust(n_points: int, y_span: float, fit_score: float) -> float:
\
\
\
\
\
\
\


    span = max(ESTIMATOR_PROFILE["curvature_full_points"] - ESTIMATOR_PROFILE["poly2_min_points"], 1.0)
    n_score = clamp((float(n_points) - ESTIMATOR_PROFILE["poly2_min_points"]) / span, 0.0, 1.0)
    span_score = clamp(y_span / ESTIMATOR_PROFILE["curvature_min_y_span"], 0.0, 1.0)
    return clamp(n_score * span_score * clamp(fit_score, 0.0, 1.0), 0.0, 1.0)


def _curvature_from_fit(
    coeffs: np.ndarray,
    degree: int,
    lateral_error: float,
    lookahead_error: float,
    trust: float,
) -> float:
\
\
\
\
\
\


    if degree == 2:
        value = float(coeffs[0]) * ESTIMATOR_PROFILE["curvature_gain"]
    else:
        value = (lookahead_error - lateral_error) * ESTIMATOR_PROFILE["fallback_curvature_gain"]
    return clamp(value * trust, -1.0, 1.0)


def _fit_error_score(progress: np.ndarray, x_norm: np.ndarray, coeffs: np.ndarray) -> float:


    fitted = np.polyval(coeffs, progress)
    rmse = float(np.sqrt(np.mean((x_norm - fitted) ** 2)))
    return clamp(1.0 - rmse / ESTIMATOR_PROFILE["max_fit_error"], 0.0, 1.0)


def _geometry_confidence(obs: PerceptionObs, points: np.ndarray, y_span: float, fit_score: float) -> float:
\
\
\
\
\
\


    obs_score = clamp(obs.confidence, 0.0, 1.0)
    point_score = clamp(len(points) / float(ESTIMATOR_PROFILE["min_good_points"]), 0.0, 1.0)
    span_score = clamp(y_span / ESTIMATOR_PROFILE["min_y_span_good"], 0.0, 1.0)
    width_score = clamp(obs.road_width_est / ESTIMATOR_PROFILE["min_road_width_for_conf"], 0.0, 1.0)
    quality = (
        0.30
        + point_score * 0.20
        + span_score * 0.20
        + fit_score * 0.25
        + width_score * 0.05
    )
    confidence = obs_score * quality
    return clamp(min(confidence, obs_score + 0.20), 0.0, 1.0)


def _smooth_alpha(confidence: float) -> float:


    low_conf = 1.0 - clamp(confidence, 0.0, 1.0)
    alpha = (
        ESTIMATOR_PROFILE["min_smooth_alpha"]
        + (ESTIMATOR_PROFILE["max_smooth_alpha"] - ESTIMATOR_PROFILE["min_smooth_alpha"]) * low_conf
        + ESTIMATOR_PROFILE["low_conf_extra_smoothing"] * low_conf
    )
    return clamp(alpha, ESTIMATOR_PROFILE["min_smooth_alpha"], ESTIMATOR_PROFILE["max_smooth_alpha"])


def _smooth_limited(previous: float, current: float, alpha: float, max_delta: float) -> float:


    smoothed = previous * alpha + current * (1.0 - alpha)
    delta = clamp(smoothed - previous, -max_delta, max_delta)
    return clamp(previous + delta, -1.0, 1.0)


def reset_estimator_state() -> None:
\
\
\
\
\
\


    global _LAST_TRACK, _LAST_TIMESTAMP, _LAST_RED_ENVIRONMENT, _RED_ENVIRONMENT_STREAK
    global _LINE_MEMORY_FRAMES, _LINE_MEMORY_OFFSET, _LINE_MEMORY_HEADING, _LINE_MEMORY_CONFIDENCE
    _LAST_TRACK = TrackState(0.0, 0.0, 0.0, 0.0, 0.0, True)
    _LAST_TIMESTAMP = None
    _LAST_RED_ENVIRONMENT = False
    _RED_ENVIRONMENT_STREAK = 0
    _LINE_MEMORY_FRAMES = 0
    _LINE_MEMORY_OFFSET = 0.0
    _LINE_MEMORY_HEADING = 0.0
    _LINE_MEMORY_CONFIDENCE = 0.0


def _maybe_reset_estimator_by_timestamp(timestamp: float) -> None:


    if _LAST_TIMESTAMP is None:
        return
    elapsed = float(timestamp) - float(_LAST_TIMESTAMP)
    if elapsed < 0.0 or elapsed > ESTIMATOR_PROFILE["timestamp_reset_gap"]:
        reset_estimator_state()


def estimate_track(obs: PerceptionObs, timestamp: float) -> TrackState:
\
\
\
\
\
\


    global _LAST_TRACK, _LAST_TIMESTAMP, _LAST_RED_ENVIRONMENT, _RED_ENVIRONMENT_STREAK

    timestamp = float(timestamp)
    _maybe_reset_estimator_by_timestamp(timestamp)

    observed_red = bool(obs.debug_flags & _RED_ENVIRONMENT_FLAG)
    if observed_red:
        _RED_ENVIRONMENT_STREAK += 1
    elif not _LAST_RED_ENVIRONMENT:
        _RED_ENVIRONMENT_STREAK = 0
    if _RED_ENVIRONMENT_STREAK >= _RED_ENVIRONMENT_LATCH_FRAMES:
        _LAST_RED_ENVIRONMENT = True
    red_environment = observed_red or _LAST_RED_ENVIRONMENT
    line_trust = _line_target_trust(obs, timestamp, red_environment)
    line_trust = _update_line_memory(obs, line_trust, timestamp, red_environment)

    points = _clean_points(obs.center_points)
    if len(points) < ESTIMATOR_PROFILE["min_center_points"] or obs.confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = (
            _line_only_track(obs, timestamp, red_environment, line_trust)
            if line_trust > 0.0
            else _lost_track(obs.confidence, red_environment, obs)
        )
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    x_norm, progress, y_span = _normalize_points(points)
    if y_span < ESTIMATOR_PROFILE["min_y_span"]:
        track = _lost_track(obs.confidence, red_environment, obs)
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    coeffs, degree = _fit_centerline(progress, x_norm)
    lateral_error = clamp(
        _value_from_band(
            progress,
            x_norm,
            coeffs,
            progress <= ESTIMATOR_PROFILE["near_progress_max"],
            ESTIMATOR_PROFILE["near_eval_progress"],
        ),
        -1.0,
        1.0,
    )
    lookahead_error = clamp(
        _value_from_band(
            progress,
            x_norm,
            coeffs,
            progress >= ESTIMATOR_PROFILE["far_progress_min"],
            ESTIMATOR_PROFILE["far_eval_progress"],
        ),
        -1.0,
        1.0,
    )
    heading_error = _heading_from_fit(coeffs, degree)
    lateral_error, heading_error, lookahead_error = _apply_line_target(
        lateral_error,
        heading_error,
        lookahead_error,
        obs,
        line_trust,
    )
    fit_score = _fit_error_score(progress, x_norm, coeffs)
    curvature_trust = _curvature_trust(len(points), y_span, fit_score)
    curvature = _curvature_from_fit(coeffs, degree, lateral_error, lookahead_error, curvature_trust)
    left_margin_near = _near_edge_margin(obs.left_edge_points, "left")
    right_margin_near = _near_edge_margin(obs.right_edge_points, "right")

    confidence = _geometry_confidence(obs, points, y_span, fit_score)
    if line_trust > 0.0:
        confidence = max(confidence, obs.line_confidence * ESTIMATOR_PROFILE["line_target_confidence_scale"])
    if confidence < ESTIMATOR_PROFILE["lost_confidence"]:
        track = _lost_track(confidence, red_environment, obs)
        _LAST_TRACK = track
        _LAST_TIMESTAMP = timestamp
        return track

    alpha = _smooth_alpha(confidence)
    curve_alpha = clamp(
        ESTIMATOR_PROFILE["curve_smooth_alpha"]
        + ESTIMATOR_PROFILE["low_conf_extra_smoothing"] * (1.0 - confidence),
        ESTIMATOR_PROFILE["min_smooth_alpha"],
        ESTIMATOR_PROFILE["max_smooth_alpha"],
    )
    track = TrackState(
        _smooth_limited(_LAST_TRACK.lateral_error, lateral_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        _smooth_limited(_LAST_TRACK.heading_error, heading_error, alpha, ESTIMATOR_PROFILE["max_heading_delta"]),
        _smooth_limited(_LAST_TRACK.curvature, curvature, curve_alpha, ESTIMATOR_PROFILE["max_curvature_delta"]),
        _smooth_limited(_LAST_TRACK.lookahead_error, lookahead_error, alpha, ESTIMATOR_PROFILE["max_error_delta"]),
        confidence,
        False,
        red_environment,
        clamp(float(obs.line_offset), -1.0, 1.0),
        clamp(float(obs.line_heading), -1.0, 1.0),
        clamp(float(obs.line_confidence), 0.0, 1.0),
        left_margin_near,
        right_margin_near,
        bool(obs.near_obstacle),
    )
    _LAST_TRACK = track
    _LAST_TIMESTAMP = timestamp
    return track



# ---- policy.py ----

"""控制策略模块。

功能概述：根据赛道状态统一规划转向和速度。
输入输出：输入 `TrackState`、时间戳和 fastest/safe 模式，输出 `ControlCmd`。
处理流程：计算风险分量，选择驾驶状态，生成目标转向和速度，再做平滑与变化率限制。
"""



_LAST_STEERING = 0.0
_LAST_SPEED = 0.0
_LAST_TIMESTAMP = None
_LOST_FRAMES = 0
_RECOVERY_FRAMES = 0
_LAST_GOOD_BIAS = 0.0
_LAST_MODE = "start"
_STALL_FRAMES = 0
_ESCAPE_FRAMES = 0
_ESCAPE_STEERING_SIGN = 1.0
_ESCAPE_STEERING_MAGNITUDE = 0.0
_ESCAPE_SPEED = 0.0
_LAST_TRACK_SIGNATURE = None
_STRAIGHT_MEMORY_FRAMES = 0
_HARD_TURN_CANDIDATE_FRAMES = 0
_RECOVERY_CANDIDATE_FRAMES = 0
_LAST_MODE_REASON = "start"
_LAST_TARGET_STEERING = 0.0
_LAST_TARGET_SPEED = 0.0
_LAST_SIGNALS = {}
_LAST_STRAIGHT_MEMORY_ACTIVE = False
_LINE_STREAK = 0
_LINE_LAST_OFFSET = 0.0
_LINE_CORRECTION = 0.0


def reset_policy_state() -> None:
\
\
\
\
\
\


    global _LAST_STEERING, _LAST_SPEED, _LAST_TIMESTAMP
    global _LOST_FRAMES, _RECOVERY_FRAMES, _LAST_GOOD_BIAS, _LAST_MODE
    global _STALL_FRAMES, _ESCAPE_FRAMES, _ESCAPE_STEERING_SIGN, _ESCAPE_STEERING_MAGNITUDE, _ESCAPE_SPEED
    global _LAST_TRACK_SIGNATURE, _STRAIGHT_MEMORY_FRAMES
    global _HARD_TURN_CANDIDATE_FRAMES, _RECOVERY_CANDIDATE_FRAMES
    global _LAST_MODE_REASON, _LAST_TARGET_STEERING, _LAST_TARGET_SPEED, _LAST_SIGNALS, _LAST_STRAIGHT_MEMORY_ACTIVE
    global _LINE_STREAK, _LINE_LAST_OFFSET, _LINE_CORRECTION
    _LINE_STREAK = 0
    _LINE_LAST_OFFSET = 0.0
    _LINE_CORRECTION = 0.0
    _LAST_STEERING = 0.0
    _LAST_SPEED = 0.0
    _LAST_TIMESTAMP = None
    _LOST_FRAMES = 0
    _RECOVERY_FRAMES = 0
    _LAST_GOOD_BIAS = 0.0
    _LAST_MODE = "start"
    _STALL_FRAMES = 0
    _ESCAPE_FRAMES = 0
    _ESCAPE_STEERING_SIGN = 1.0
    _ESCAPE_STEERING_MAGNITUDE = 0.0
    _ESCAPE_SPEED = 0.0
    _LAST_TRACK_SIGNATURE = None
    _STRAIGHT_MEMORY_FRAMES = 0
    _HARD_TURN_CANDIDATE_FRAMES = 0
    _RECOVERY_CANDIDATE_FRAMES = 0
    _LAST_MODE_REASON = "start"
    _LAST_TARGET_STEERING = 0.0
    _LAST_TARGET_SPEED = 0.0
    _LAST_SIGNALS = {}
    _LAST_STRAIGHT_MEMORY_ACTIVE = False


def _maybe_reset_policy_by_timestamp(timestamp: float, profile: dict) -> None:


    if _LAST_TIMESTAMP is None:
        return
    elapsed = float(timestamp) - float(_LAST_TIMESTAMP)
    if elapsed < 0.0 or elapsed > profile["timestamp_reset_gap"]:
        reset_policy_state()


def _dt(timestamp: float, profile: dict) -> float:


    if _LAST_TIMESTAMP is None:
        return profile["nominal_dt"]
    return max(float(timestamp) - float(_LAST_TIMESTAMP), profile["nominal_dt"])


def _signed_power(value: float, power: float) -> float:


    return math.copysign(abs(value) ** power, value)


def _road_direction_sign(track: TrackState) -> float:
\
\
\
\
\
\


    reference = track.lateral_error
    if abs(reference) <= 0.05:
        reference = _LAST_GOOD_BIAS
    if abs(reference) <= 1e-3:
        reference = -_LAST_STEERING
    if abs(reference) <= 1e-6:
        return 1.0
    return math.copysign(1.0, reference)


def _margin_escape_sign(track: TrackState, fallback: float) -> float:
\
\
\
\
\
\


    margin_gap = abs(track.left_margin_near - track.right_margin_near)
    if margin_gap <= 0.08:
        return fallback
    if track.left_margin_near < track.right_margin_near:
        return 1.0
    return -1.0


def _control_signals(track: TrackState, profile: dict) -> dict:
\
\
\
\
\
\


    curve_risk = clamp(max(abs(track.curvature), abs(track.heading_error), abs(track.lookahead_error)), 0.0, 1.0)
    offset_risk = clamp(abs(track.lateral_error), 0.0, 1.0)
    confidence_risk = clamp(1.0 - track.confidence, 0.0, 1.0)
    lost_risk = 1.0 if track.lost else 0.0
    min_margin = min(clamp(track.left_margin_near, 0.0, 1.0), clamp(track.right_margin_near, 0.0, 1.0))
    margin_risk = clamp((profile["inside_margin_warning"] - min_margin) / profile["inside_margin_warning"], 0.0, 1.0)
    turn_demand = clamp(curve_risk * 0.55 + offset_risk * 0.45, 0.0, 1.0)
    risk = clamp(
        curve_risk * profile["risk_curve_weight"]
        + offset_risk * profile["risk_offset_weight"]
        + confidence_risk * profile["risk_confidence_weight"]
        + lost_risk * profile["risk_lost_weight"],
        0.0,
        1.0,
    )
    return {
        "curve_risk": curve_risk,
        "offset_risk": offset_risk,
        "confidence_risk": confidence_risk,
        "lost_risk": lost_risk,
        "margin_risk": margin_risk,
        "turn_demand": turn_demand,
        "risk": risk,
    }


def _is_straight_candidate(track: TrackState, signals: dict, profile: dict) -> bool:
\
\
\
\
\
\


    if track.lost or track.confidence < profile["lost_confidence"]:
        return False
    stable_curve = max(abs(track.curvature), abs(track.lookahead_error)) <= profile["straight_curve_max"]
    centered = signals["offset_risk"] <= profile["straight_offset_max"]
    heading_ok = abs(track.heading_error) <= profile["straight_heading_max"]
    return stable_curve and centered and heading_ok


def _is_lost_straight_coast_candidate(track: TrackState, signals: dict, profile: dict) -> bool:
\
\
\
\
\
\


    if not track.lost:
        return False
    stable_curve = max(abs(track.curvature), abs(track.lookahead_error)) <= profile["straight_curve_max"]
    centered = signals["offset_risk"] <= profile["straight_offset_max"]
    heading_ok = abs(track.heading_error) <= profile["straight_heading_max"]
    steering_ok = abs(_LAST_STEERING) <= profile["straight_lost_steering_max"]
    return stable_curve and centered and heading_ok and steering_ok


def _update_straight_memory(track: TrackState, signals: dict, mode: str, profile: dict) -> bool:
\
\
\
\
\
\


    global _STRAIGHT_MEMORY_FRAMES

    if _is_straight_candidate(track, signals, profile):
        _STRAIGHT_MEMORY_FRAMES = int(profile["straight_memory_frames"])
        return True
    if _STRAIGHT_MEMORY_FRAMES > 0 and mode == "lost":
        _STRAIGHT_MEMORY_FRAMES -= 1
        return True
    if _is_lost_straight_coast_candidate(track, signals, profile):
        return True
    _STRAIGHT_MEMORY_FRAMES = 0
    return False


def _select_mode(track: TrackState, signals: dict, timestamp: float, profile: dict) -> str:
\
\
\
\
\
\


    global _HARD_TURN_CANDIDATE_FRAMES, _RECOVERY_CANDIDATE_FRAMES, _LAST_MODE_REASON

    del timestamp
    if track.lost or track.confidence < profile["lost_confidence"]:
        _HARD_TURN_CANDIDATE_FRAMES = 0
        _RECOVERY_CANDIDATE_FRAMES = 0
        _LAST_MODE_REASON = "lost_or_low_confidence"
        return "lost"
    if _RECOVERY_FRAMES > 0 or track.confidence < profile["recovery_confidence"]:
        _RECOVERY_CANDIDATE_FRAMES += 1
        _HARD_TURN_CANDIDATE_FRAMES = 0
        if _RECOVERY_FRAMES > 0 or _RECOVERY_CANDIDATE_FRAMES >= int(profile["recovery_enter_frames"]):
            _LAST_MODE_REASON = "recovery_buffer_or_confidence"
            return "recovering"
    else:
        _RECOVERY_CANDIDATE_FRAMES = 0

    hard_turn_candidate = (
        signals["curve_risk"] > profile["hard_turn_threshold"]
        or signals["turn_demand"] > profile["hard_turn_threshold"]
    )
    hard_turn_hold = _LAST_MODE == "hard_turn" and (
        signals["curve_risk"] > profile["hard_turn_exit_threshold"]
        or signals["turn_demand"] > profile["hard_turn_exit_threshold"]
    )
    if hard_turn_candidate or hard_turn_hold:
        _HARD_TURN_CANDIDATE_FRAMES += 1
    else:
        _HARD_TURN_CANDIDATE_FRAMES = 0
    if hard_turn_hold or _HARD_TURN_CANDIDATE_FRAMES >= int(profile["hard_turn_enter_frames"]):
        _LAST_MODE_REASON = "curve_or_turn_demand"
        return "hard_turn"
    if abs(track.lateral_error) > profile["correction_error"]:
        _LAST_MODE_REASON = "lateral_error"
        return "correcting"
    _LAST_MODE_REASON = "nominal"
    return "cruise"


def _apply_inside_margin_guard(raw: float, track: TrackState, profile: dict) -> float:
\
\
\
\
\
\


    warning = max(float(profile["inside_margin_warning"]), 1e-6)
    if raw > 0.0:
        pressure = clamp((warning - track.right_margin_near) / warning, 0.0, 1.0)
        if pressure <= 0.0:
            return raw
        capped = min(raw, profile["inside_margin_steering_cap"])
        return capped - pressure * profile["inside_margin_outward_gain"]
    if raw < 0.0:
        pressure = clamp((warning - track.left_margin_near) / warning, 0.0, 1.0)
        if pressure <= 0.0:
            return raw
        capped = max(raw, -profile["inside_margin_steering_cap"])
        return capped + pressure * profile["inside_margin_outward_gain"]
    return raw


def _target_steering(track: TrackState, signals: dict, mode: str, profile: dict) -> float:
\
\
\
\
\
\


    center_term = track.lateral_error * profile["gain_lateral"]
    lookahead_term = (
        track.lookahead_error * profile["gain_lookahead"]
        + track.heading_error * profile["gain_heading"]
        + track.curvature * profile["gain_curve"]
    )



    corner_arrival = clamp(
        abs(track.lateral_error) / profile["turn_in_lateral_ref"]
        + abs(track.heading_error) / profile["turn_in_heading_ref"],
        0.0,
        1.0,
    )
    turn_in_gate = profile["turn_in_floor"] + (1.0 - profile["turn_in_floor"]) * corner_arrival
    lookahead_term *= turn_in_gate
    near_weight = profile["near_weight_base"] + signals["offset_risk"] * profile["near_weight_offset_boost"]
    far_weight = profile["far_weight_base"] + signals["curve_risk"] * profile["far_weight_curve_boost"]
    if center_term * lookahead_term < 0.0:
        conflict_offset = max(0.0, signals["offset_risk"] - profile["far_conflict_offset_start"])
        far_weight *= max(
            profile["far_conflict_min_scale"],
            1.0 - conflict_offset * profile["far_conflict_offset_scale"],
        )

    raw = near_weight * center_term + far_weight * lookahead_term
    raw += profile["gain_lateral_nonlinear"] * _signed_power(track.lateral_error, 1.7)
    raw += profile["gain_curve_nonlinear"] * _signed_power(track.curvature, 1.5)

    if mode == "lost":


        raw = 0.50 * _LAST_STEERING + 0.20 * _LAST_GOOD_BIAS
    elif mode == "recovering":
        raw *= 0.70
    elif mode == "correcting":
        raw += track.lateral_error * 0.25
    elif mode == "hard_turn":
        raw *= profile["hard_turn_steering_scale"]

    if (
        track.red_environment
        and
        track.lateral_error > profile["inside_left_lateral_min"]
        and track.heading_error < profile["inside_left_heading_max"]
        and track.curvature < profile["inside_left_curvature_max"]
    ):
        raw = max(raw, profile["inside_left_steering_limit"])

    raw = _apply_inside_margin_guard(raw, track, profile)

    if abs(raw) < profile["steering_deadzone"]:
        raw = 0.0
    max_abs = profile["max_abs_steering"]
    return clamp(raw, -max_abs, max_abs)


def _steering_smoothing_for_mode(mode: str, profile: dict) -> float:


    if mode == "cruise":
        return profile["steering_smoothing_cruise"]
    if mode == "hard_turn":
        return profile["steering_smoothing_turn"]
    if mode == "correcting":
        return profile["steering_smoothing_correction"]
    return profile["steering_smoothing_recovery"]


def _smooth_steering(target: float, mode: str, timestamp: float, profile: dict) -> float:
\
\
\
\
\
\


    alpha = _steering_smoothing_for_mode(mode, profile)
    smoothed = _LAST_STEERING * alpha + target * (1.0 - alpha)
    dt_factor = max(1.0, _dt(timestamp, profile) / profile["nominal_dt"])
    speed_norm = clamp(_LAST_SPEED / max(profile["max_speed"], 1e-6), 0.0, 1.0)
    speed_factor = 1.0 - 0.35 * speed_norm
    max_delta = profile["max_steering_delta"] * dt_factor * speed_factor
    delta = clamp(smoothed - _LAST_STEERING, -max_delta, max_delta)

    max_abs = profile["max_abs_steering"] * (1.0 - profile["steering_speed_cap_scale"] * speed_norm)
    return clamp(_LAST_STEERING + delta, -max_abs, max_abs)


def _target_speed(
    track: TrackState,
    signals: dict,
    mode: str,
    steering: float,
    timestamp: float,
    profile: dict,
    straight_memory_active: bool = False,
) -> float:
\
\
\
\
\
\
\


    if mode == "lost":
        if straight_memory_active:
            return profile["straight_lost_speed"]
        return profile["lost_speed"]

    curve_factor = 1.0 - profile["curve_slowdown"] * (signals["curve_risk"] ** profile["curve_power"])
    offset_factor = 1.0 - profile["offset_slowdown"] * (signals["offset_risk"] ** profile["offset_power"])
    confidence_factor = profile["min_confidence_factor"] + (1.0 - profile["min_confidence_factor"]) * track.confidence
    steering_factor = 1.0 - profile["steering_slowdown"] * (abs(steering) ** profile["steering_power"])
    margin_factor = 1.0 - profile["inside_margin_slowdown"] * signals["margin_risk"]
    target = profile["base_speed"] * curve_factor * offset_factor * confidence_factor * steering_factor * margin_factor

    if mode == "recovering":
        target = min(target, profile["recovery_speed"])
    elif mode == "hard_turn":
        centered_bonus = (
            profile["hard_turn_center_speed_bonus"]
            * (1.0 - signals["offset_risk"])
            * track.confidence
        )
        target = min(target, profile["hard_turn_speed"] + centered_bonus)
    elif mode == "correcting":
        target = min(target, profile["correction_speed"])


    straight = straight_memory_active or _is_straight_candidate(track, signals, profile)
    if straight:
        target = max(target, profile["straight_speed"])
    if timestamp < profile["start_caution_seconds"]:
        target = min(target, profile["start_speed"])
    return clamp(target, profile["min_speed"], profile["max_speed"])


def _smooth_speed(target: float, timestamp: float, profile: dict) -> float:
\
\
\
\
\
\


    dt = _dt(timestamp, profile)
    delta = target - _LAST_SPEED
    if delta >= 0.0:
        delta = min(delta, profile["max_speed_increase_per_sec"] * dt)
    else:
        delta = max(delta, -profile["max_speed_decrease_per_sec"] * dt)
    return clamp(_LAST_SPEED + delta, min(profile["min_speed"], target), profile["max_speed"])


def _track_signature(track: TrackState) -> tuple[float, float, float, float, float]:


    return (
        track.lateral_error,
        track.heading_error,
        track.curvature,
        track.lookahead_error,
        track.confidence,
    )


def _escape_if_stalled(
    track: TrackState,
    signals: dict,
    steering: float,
    speed: float,
    mode: str,
    profile: dict,
    allow_geometry_escape: bool,
) -> tuple[float, float, str]:
\
\
\
\
\
\
\
\


    global _STALL_FRAMES, _ESCAPE_FRAMES, _ESCAPE_STEERING_SIGN, _ESCAPE_STEERING_MAGNITUDE, _ESCAPE_SPEED
    global _LAST_TRACK_SIGNATURE

    signature = _track_signature(track)
    if _LAST_TRACK_SIGNATURE is None:
        signature_delta = 1.0
    else:
        signature_delta = sum(abs(a - b) for a, b in zip(signature, _LAST_TRACK_SIGNATURE))
    _LAST_TRACK_SIGNATURE = signature

    if _ESCAPE_FRAMES > 0:
        _ESCAPE_FRAMES -= 1
        escape_steering = _ESCAPE_STEERING_SIGN * _ESCAPE_STEERING_MAGNITUDE
        max_abs = profile["max_abs_steering"]
        return (
            clamp(escape_steering, -max_abs, max_abs),
            max(speed, _ESCAPE_SPEED),
            "escaping",
        )

    high_turn = (
        signals["curve_risk"] >= profile["escape_curve_threshold"]
        or abs(steering) >= profile["escape_steering_threshold"]
    )
    aligned_offset = (
        signals["offset_risk"] >= profile["escape_offset_threshold"]
        and track.lateral_error * track.lookahead_error >= profile["escape_offset_lookahead_alignment"]
    )
    large_offset_stall = (
        allow_geometry_escape
        and mode in {"hard_turn", "correcting"}
        and signals["offset_risk"] >= profile["escape_offset_threshold"]
        and speed <= profile["escape_offset_speed_threshold"]
        and abs(track.heading_error) <= profile["escape_offset_heading_abs_max"]
        and abs(track.curvature) <= profile["escape_offset_curve_abs_max"]
        and track.lateral_error * track.lookahead_error >= profile["escape_offset_lookahead_alignment"]
    )
    low_speed_stall = speed <= profile["escape_low_speed_threshold"]

    pinned_stall = (
        abs(track.lateral_error) >= profile["escape_pinned_lateral_min"]
        and abs(steering) >= profile["escape_pinned_steering_min"]
        and speed <= profile["escape_pinned_speed_max"]
    )
    boundary_obstacle_stall = (
        allow_geometry_escape
        and track.near_obstacle
        and mode in {"hard_turn", "correcting"}
        and signals["margin_risk"] >= profile["escape_boundary_margin_risk"]
        and min(track.left_margin_near, track.right_margin_near) <= profile["escape_boundary_margin_max"]
        and speed <= profile["escape_boundary_speed_max"]
        and not track.lost
        and track.confidence >= profile["escape_boundary_min_confidence"]
    )
    stable_view = signature_delta <= profile["escape_signature_delta"]


    escape_sign = _road_direction_sign(track)

    should_count_stall = False
    require_confidence = True
    trigger_frames = int(profile["escape_trigger_frames"])
    escape_frames = int(profile["escape_turn_frames"])
    escape_steering = profile["escape_turn_steering"]
    escape_speed = profile["escape_turn_speed"]
    if large_offset_stall:
        should_count_stall = True
        trigger_frames = int(profile["escape_offset_trigger_frames"])
        escape_frames = int(profile["escape_offset_frames"])
        escape_steering = profile["escape_offset_steering"]
        escape_speed = profile["escape_offset_speed"]
    elif boundary_obstacle_stall:


        should_count_stall = True
        require_confidence = False
        trigger_frames = int(profile["escape_boundary_trigger_frames"])
        escape_frames = int(profile["escape_boundary_frames"])
        escape_steering = profile["escape_boundary_steering"]
        escape_speed = profile["escape_boundary_speed"]
        escape_sign = _margin_escape_sign(track, escape_sign)
    elif (
        allow_geometry_escape
        and mode == "hard_turn"
        and high_turn
        and not aligned_offset
        and speed <= profile["escape_turn_speed_max"]
    ):


        should_count_stall = True
    elif pinned_stall:

        should_count_stall = True
        trigger_frames = int(profile["escape_pinned_trigger_frames"])
        escape_frames = int(profile["escape_pinned_frames"])
        escape_steering = profile["escape_pinned_steering"]
        escape_speed = profile["escape_pinned_speed"]
    elif low_speed_stall:
        should_count_stall = True

        require_confidence = False
        trigger_frames = int(profile["escape_low_speed_trigger_frames"])
        escape_frames = int(profile["escape_low_speed_frames"])
        escape_steering = profile["escape_low_speed_steering"]
        escape_speed = profile["escape_low_speed_speed"]

    confidence_ok = (not require_confidence) or (
        not track.lost and track.confidence >= profile["escape_min_confidence"]
    )
    if should_count_stall and stable_view and confidence_ok:
        _STALL_FRAMES += 1
    else:
        _STALL_FRAMES = 0

    if _STALL_FRAMES >= trigger_frames:
        _STALL_FRAMES = 0
        _ESCAPE_STEERING_SIGN = escape_sign
        _ESCAPE_STEERING_MAGNITUDE = escape_steering
        _ESCAPE_SPEED = escape_speed
        _ESCAPE_FRAMES = escape_frames

    return steering, speed, mode


def _lane_line_correction(
    track: TrackState,
    signals: dict,
    mode: str,
    profile: dict,
    timestamp: float,
) -> float:
\
\
\
\
\
\
\
\
\
\


    global _LINE_STREAK, _LINE_LAST_OFFSET, _LINE_CORRECTION

    normal_valid = (
        profile["enable"]
        and track.line_confidence >= profile["min_confidence"]
        and abs(track.line_offset) <= profile["offset_trust_max"]
        and not track.near_obstacle
        and mode != "escaping"
    )
    startup_valid = (
        profile["enable"]
        and track.red_environment
        and timestamp <= profile["startup_acquire_until"]
        and track.line_confidence >= profile["min_confidence"]
        and profile["startup_offset_min"] <= track.line_offset <= profile["startup_offset_trust_max"]
        and profile["startup_heading_min"] <= track.line_heading <= profile["startup_heading_max"]
        and not track.near_obstacle
        and mode != "escaping"
    )
    valid = normal_valid or startup_valid
    if valid and _LINE_STREAK > 0 and abs(track.line_offset - _LINE_LAST_OFFSET) > profile["offset_jump_max"]:
        valid = False
        _LINE_STREAK = 0
    if valid:
        _LINE_STREAK += 1
        _LINE_LAST_OFFSET = track.line_offset
    else:
        _LINE_STREAK = 0

    target = 0.0
    confirm_frames = int(profile["startup_confirm_frames"] if startup_valid and not normal_valid else profile["confirm_frames"])
    if valid and _LINE_STREAK >= confirm_frames:
        target = track.line_offset * profile["offset_gain"] + track.line_heading * profile["heading_gain"]
        max_correction = profile["startup_max_correction"] if startup_valid and not normal_valid else profile["max_correction"]
        curve_gate = profile["startup_curve_gate"] if startup_valid and not normal_valid else profile["curve_gate"]
        target = clamp(target, -max_correction, max_correction)
        target *= 1.0 - clamp(signals["curve_risk"] / curve_gate, 0.0, 1.0)

    if startup_valid and not normal_valid:
        alpha = profile["startup_smoothing"]
    elif not valid and timestamp <= profile["startup_acquire_until"] and _LINE_CORRECTION > 0.0:
        alpha = profile["startup_decay"]
    else:
        alpha = profile["smoothing"]
    _LINE_CORRECTION = _LINE_CORRECTION * alpha + target * (1.0 - alpha)
    return clamp(_LINE_CORRECTION, -profile["max_correction"], profile["max_correction"])


def _update_policy_state(track: TrackState, steering: float, speed: float, mode: str, timestamp: float, profile: dict) -> None:
\
\
\
\
\
\


    global _LAST_STEERING, _LAST_SPEED, _LAST_TIMESTAMP
    global _LOST_FRAMES, _RECOVERY_FRAMES, _LAST_GOOD_BIAS, _LAST_MODE

    if track.lost:
        _LOST_FRAMES += 1
    else:
        if _LOST_FRAMES > 0:
            _RECOVERY_FRAMES = int(profile["recovery_frames"])
        _LOST_FRAMES = 0
    if _RECOVERY_FRAMES > 0 and not track.lost:
        _RECOVERY_FRAMES -= 1

    if not track.lost and track.confidence >= profile["recovery_confidence"]:
        _LAST_GOOD_BIAS = clamp(
            track.lateral_error * 0.55 + track.lookahead_error * 0.25 + track.curvature * 0.20,
            -1.0,
            1.0,
        )

    _LAST_STEERING = steering
    _LAST_SPEED = speed
    _LAST_TIMESTAMP = timestamp
    _LAST_MODE = mode


def decide_control(track: TrackState, timestamp: float, mode: str = "fastest") -> ControlCmd:
\
\
\
\
\
\


    global _LAST_TARGET_STEERING, _LAST_TARGET_SPEED, _LAST_SIGNALS, _LAST_STRAIGHT_MEMORY_ACTIVE

    profile = get_profile(mode if mode in {"fastest", "safe"} else "fastest")
    if not track.red_environment:
        profile.update(BASIC_CONTROL_OVERRIDES)
    timestamp = float(timestamp)
    _maybe_reset_policy_by_timestamp(timestamp, profile)
    signals = _control_signals(track, profile)
    drive_mode = _select_mode(track, signals, timestamp, profile)
    straight_memory_active = _update_straight_memory(track, signals, drive_mode, profile)
    target_steering = _target_steering(track, signals, drive_mode, profile)
    _LAST_TARGET_STEERING = target_steering
    steering = _smooth_steering(target_steering, drive_mode, timestamp, profile)
    target_speed = _target_speed(
        track,
        signals,
        drive_mode,
        steering,
        timestamp,
        profile,
        straight_memory_active=straight_memory_active,
    )
    _LAST_TARGET_SPEED = target_speed
    _LAST_SIGNALS = dict(signals)
    _LAST_STRAIGHT_MEMORY_ACTIVE = bool(straight_memory_active)
    speed = _smooth_speed(target_speed, timestamp, profile)

    steering, speed, drive_mode = _escape_if_stalled(
        track, signals, steering, speed, drive_mode, profile, track.red_environment
    )


    _update_policy_state(track, steering, speed, drive_mode, timestamp, profile)
    line_correction = _lane_line_correction(track, signals, drive_mode, LINE_FOLLOW_PROFILE, timestamp)
    final_steering = clamp(steering + line_correction, -1.0, 1.0)
    return ControlCmd(final_steering, speed)



# ---- team_controller_local.py ----

"""本地控制器入口。

功能概述：按固定流水线串接感知、估计和控制策略模块。
输入输出：输入平台同形态的左右图像和时间戳，输出 `(steering, speed)`。
处理流程：提取观测，估计赛道，按 profile 决策控制量，最后限幅返回。
"""


PROFILE = "fastest"


def control(left_img, right_img, timestamp):
\
\
\
\
\
\


    try:
        obs = extract_observation(left_img, right_img, timestamp)
        track = estimate_track(obs, timestamp)
        cmd = decide_control(track, timestamp, mode=PROFILE)
        steering, speed = clamp_cmd(cmd)
        return steering, speed
    except Exception:
        return 0.0, 0.0
