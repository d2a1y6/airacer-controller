"""策略参数配置。

功能概述：集中保存采样色卡、视觉、估计和控制策略参数。
输入输出：输入任意 profile 名称，输出同一套控制参数。
处理流程：先定义从 Webots 原图采样得到的颜色配置，再定义感知、估计和控制参数。
"""

COLOR_PROFILE = {
    # 采样来源：.tmp/color_sample/color_samples.json，来自 complex/basic 原始相机帧。
    # 数组均为 OpenCV 口径：BGR / HSV / Lab；RGB 只用于人工核对。
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
    # Phase 2-A（2026-06-12，实测取证）：弯道里中心虚线是稀疏短段，旧的 5 条固定扫描行大多落在
    # 虚线"间隙"里 → 检不到线 → 车回退到道路 mask 的提前打轮 → 切内线卡路牙。实测真帧显示：
    # 扫描行加密到 12 条、ROI 上下放宽后，弯道入口（t≈29-31）的中心线能被双目稳定召回。
    "scan_top_ratio": 0.44,
    "scan_bottom_ratio": 0.92,
    "scan_count": 12,
    "confidence_full_points": 5.0,  # 置信度 = 命中点数 / 该值（与扫描行数解耦，加密行不稀释置信度）
    "row_band": 2,
    "min_segment_width": 3.0,
    "max_segment_width": 70.0,
    # Phase 1（2026-06-12，用户取证）：complex 弯道内侧护栏支柱和中心虚线一样亮，旧的纯亮度白
    # 阈值（np.all(band>=white_min)）无法区分，导致护栏支柱被当成大 offset 的"线"。真正的中心虚线
    # 有两个判别特征：① 近中性白（通道色度低，护栏偏蓝灰色度更高）；② 左右紧邻都是深灰沥青
    # （"白线在大片路面中间"，护栏支柱外侧是路牙/红地/草而非路面）。两条同时满足才算白线候选。
    "white_chroma_max": 40.0,       # 白线像素允许的最大通道色度（max-min）；护栏蓝灰色度更高被排除
    "context_window": 18,           # 线段两侧各取多宽的窗口检查是否为路面（像素）
    "context_gap": 4,               # 紧邻线段边缘跳过的像素，抗抗锯齿/白色高光外溢
    "context_min_ratio": 0.5,       # 侧窗内属于深灰路面的列占比下限，两侧都要达标
    "road_dark_min": 28.0,          # 路面上下文：最暗通道下限（排除纯黑阴影）
    "road_dark_max": 110.0,         # 路面上下文：最亮通道上限（排除亮路牙≈112/护栏/红地）
    "road_dark_chroma_max": 36.0,   # 路面上下文：最大色度（排除红地≈94、草≈84）
    "offset_near_fraction": 0.34,   # 用最近/最远各 1/3 实测点的中位数算 offset/heading，不再直线外推
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
    # 信任门控（2026-06-11 实跑取证）：白线检测会把白色护栏（complex 直道 lo≈0.4-0.93）、
    # 白车/斑马线（basic 终点 lo≈+0.35）、弯中错误线段（lo≈-0.64）当成车道线，单帧 ±0.34
    # 修正造成无意义打轮甚至抵消正常入弯舵角。骑线时 |offset| 本应很小，故：
    # 超出 trust_max 拒绝、帧间突变拒绝、连续 confirm_frames 帧有效才生效、EMA 平滑、
    # 弯中（curve_risk 接近 curve_gate）按比例压低——弯中线段不连续且直线拟合失真。
    # Phase 2-C（2026-06-12，实测取证）：车在弯道入口已偏到中心线左侧，白线 offset 实测涨到
    # +0.32→+0.50。旧的 0.30 门把这些真实"偏离中心线"的检测全拒掉，车反而无法靠白线回中。
    # 现在 Phase 1 的"两侧紧邻路面"上下文已从结构上排除护栏支柱，offset 门可以放宽用于回中。
    # R027 显示第一个左弯真实白线会到 0.62-0.71；0.75 以上仍拒（多半是路沿/远处错线）。
    # **这是走线改动，必须人上车终判。**
    "offset_trust_max": 0.75,
    "offset_jump_max": 0.12,
    "confirm_frames": 3,
    "smoothing": 0.5,
    "curve_gate": 0.35,
    # R027 取证：弯中 offset 已说明车偏离白线，但 curve_gate 会把后置白线修正压成 0。
    # 当 offset 足够大时，保留一部分纯 offset 回中力；heading 仍可被弯中门控压低。
    "offset_priority_min": 0.30,
    "offset_curve_min_scale": 0.35,
    # complex 发车时车初始在白线左侧，road mask 会把右侧大块低饱和地面误当路，导致几何中心贴左。
    # 只在开头短窗口接受“白线在右侧且斜率合理”的较大 offset，用于把车捕获回白线中间；
    # 负 offset 和接近护栏的大 offset 仍拒绝。
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
    # 白线进入主链路时仍受信任门控：普通帧只接收小 offset 的双目线；complex 发车短窗口
    # 额外接收右侧中等 offset 的单目线。road mask 置信差或饱和时，提高白线权重。
    "line_target_min_confidence": 0.30,
    "line_lateral_weight": 0.85,
    "line_heading_weight": 0.55,
    "line_lookahead_weight": 0.70,
    "line_lookahead_projection": 0.55,
    "line_target_normal_offset_max": 0.75,  # Phase 2-C/R027：与 LINE_FOLLOW offset_trust_max 同步放宽（见该处注释）
    "line_target_normal_scale": 0.55,
    "line_target_unreliable_road_scale": 1.00,
    "line_target_startup_scale": 0.76,
    "line_target_road_confidence_max": 0.60,
    "line_target_confidence_scale": 0.75,
    # R027 取证：第一个左弯里白线 offset 为正（线在右，车应右回中），但 line_heading 很负。
    # 若直接融合 heading/lookahead，会继续给大左舵。offset 足够大且与 heading 反号时，白线
    # 主要代表"回中方向"，heading 只能弱参考，lookahead 不允许被反向拉过中心。
    "line_offset_priority_min": 0.30,
    "line_conflict_heading_scale": 0.20,
    "line_conflict_projected_scale": 0.65,
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
    "far_weight_curve_boost": 0.28,
    "far_conflict_offset_start": 0.18,
    "far_conflict_offset_scale": 2.00,
    "far_conflict_min_scale": 0.22,
    "gain_lateral": 0.80,
    "gain_lookahead": 0.68,
    "gain_heading": 0.68,
    "gain_curve": 0.12,
    "gain_lateral_nonlinear": 0.22,
    "gain_curve_nonlinear": 0.02,
    "turn_in_floor": 0.55,
    "turn_in_lateral_ref": 0.30,
    "turn_in_heading_ref": 0.45,
    "steering_deadzone": 0.015,
    "max_abs_steering": 0.76,
    "hard_turn_steering_scale": 0.78,
    "steering_speed_cap_scale": 0.42,
    # 边界余量保护默认关闭（outward_gain/slowdown=0、cap=1.0 即 no-op）：余量来自
    # road-mask 边界点，mask 饱和或 fallback 时是噪声，R014 实车证明它既没拦住撞栏
    # 又会产生无意义打轮/减速。margin 字段保留为诊断输出。
    "inside_margin_warning": 0.34,
    "inside_margin_outward_gain": 0.0,
    "inside_margin_steering_cap": 1.0,
    "inside_margin_slowdown": 0.0,
    "inside_left_lateral_min": 0.05,
    "inside_left_heading_max": -0.24,
    "inside_left_curvature_max": -0.45,
    "inside_left_steering_limit": -0.40,
    "curve_slowdown": 0.70,
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
    # 几何（急弯卡边）脱困必须同时满足低指令速度：平稳巡弯也会出现"高弯量+签名稳定"
    # （complex R 实跑 t≈37.2 在正常左弯中误触发 escape，直接导致撞左栏），真卡边时
    # 指令速度必然已被弯道/转向因子压低。
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
    # complex 后段静态车 + 单侧边界贴住时，画面冻结但指令速度可能仍高于 low_speed 阈值；
    # 这条只在红色环境、近障碍、单侧余量为 0 附近时启用，避免普通巡弯误触发。
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
    """读取控制 profile。

    功能：为顶层控制器提供当前唯一维护的控制参数。
    参数：`name` 保留兼容构建脚本和提交文件中的 fastest/safe 标记。
    返回：`CONTROL` 参数字典的浅拷贝。
    逻辑：所有模式都返回同一套参数，便于先集中优化一个目标。
    """

    del name
    return dict(CONTROL)
