"""策略参数配置。

功能概述：集中保存采样色卡、视觉、估计和控制策略参数。
输入输出：输入策略名称，输出对应控制参数。
处理流程：先定义从 Webots 原图采样得到的颜色配置，再定义无其他车策略；有其他车策略仅留占位。
"""

STRATEGY_NO_OTHER_CARS = "no_other_cars"
STRATEGY_WITH_OTHER_CARS = "with_other_cars"

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
    "enable_opponent_avoidance": False,
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
    "max_center_jump_ratio": 0.32,
    "min_points_per_camera": 3,
    "min_y_span": 60.0,
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
    "offset_priority_min": 0.18,
    "offset_curve_min_scale": 0.35,
    # R039（2026-06-12，R038 残留弯中切内线取证）：弯中（curve_risk≈0.67 ≫ curve_gate 0.35）
    # curve_scale 把混合回中修正压到 0，只剩很弱的 offset 楼层（≈0.10-0.19），不足以抵消
    # road-mask 的弯道向内预判 → 半径偏小、车落到白线内侧贴/撞内栏。当可信白线连续多帧显示
    # 车确在内侧（|offset| 大、offset 与 heading 反号）时，叠加一个有界“向外辅助”，方向恒为把车
    # 推回白线一侧；并在白线短暂丢置信（虚线间隙）时按固定帧数保持上一段向外修正。全程仍受
    # max_correction 上限约束，不会越过既有舵角包络。**这是走线改动，必须人上车终判。**
    "inside_assist_enable": True,
    "inside_assist_offset_min": 0.30,   # 车被判定“已在内侧”的 |offset| 下限
    "inside_assist_streak_min": 4,      # 连续多少帧可信内侧才允许辅助（抗单帧误检）
    "inside_assist_gain": 0.55,         # 超出阈值部分换算成向外偏置的增益
    "inside_assist_max": 0.20,          # 向外辅助偏置上限（叠加后仍受 max_correction 钳制）
    "hold_offset_min": 0.30,            # 触发“丢置信保持”所需的上一段可信 |offset|
    "hold_frames": 8,                   # 丢置信后保持向外修正的最大帧数
    "hold_decay": 0.90,                 # 保持期内每帧衰减系数
    # R028 残留瞬态：第一个左弯中段常只有一侧相机能凑够弯中虚线点，双目硬要求会让
    # `line_conf` 短暂归零。只在 complex 红色环境里接受单目兜底，并打置信折扣；basic 不受影响。
    "single_camera_enable": True,
    "single_camera_min_confidence": 0.60,
    "single_camera_confidence_scale": 0.65,
    "single_camera_offset_max": 0.75,
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
    "line_offset_priority_min": 0.18,
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

NO_OTHER_CARS_CONTROL = {
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
    # 速度提升 Phase 2（激进）：少把中等弯当 hard_turn（threshold 0.20→0.30），且 hard_turn/恢复/
    # 回中各状态的速度上限大幅抬高——半径已稳，弯里可以更快。
    "recovery_speed": 0.55,
    "hard_turn_speed": 0.72,
    "hard_turn_center_speed_bonus": 0.28,
    "correction_speed": 0.72,
    "hard_turn_threshold": 0.30,
    "hard_turn_exit_threshold": 0.24,
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
    # 入弯时机门控（R042/R043/R044，接触日志+控制日志定位"入弯太早"是切内线/撞内栏根因）：
    # arrival 只看"车已物理到弯"= 近处 |lateral| 漂移（直道≈0，开到弯口才长起来）。R043 删除
    # floor、且 R044 移除 heading 项后，arrival 纯由 lateral 决定，policy 直接用它缩放远处预瞄项；
    # 车未到弯口时预瞄项可被压到 0。R046 删除了 R044 的"弯有多急(curve_risk)"调制——它在入弯初期
    # curve_risk 还低时把所有弯误判成缓弯、过度迟滞，等 curve_risk 涨上来车已深入弯里才急打轮（半径
    # 反而大、冲外侧、掉速）。入弯瞬间没有信号能区分缓/急弯，故这种调制原理上修不好，已删。
    # 现在 arrival 纯由近处 |lateral| 漂移决定：`corner_arrival = clamp(|lateral|/turn_in_lateral_ref, 0, 1)`。
    "turn_in_lateral_ref": 0.75,     # arrival 参考基准（调小=更早转/半径更小，调大=更晚转/半径更大）
    # R047：过弯越快半径越大——把入弯参考随速度收小，speed_norm 时参考 = lateral_ref×(1−此值×speed_norm)，
    # 高速早开门、早转，弥补高速入口多走的距离。0=不耦合（纯 lateral）。
    "turn_in_speed_comp": 0.6,
    # R048：入弯门控是 lookahead_term 上的连续乘子，但 lateral 在弯中会反复回落→门收掉远处项→车转
    # 一半收轮、转不到位、出弯提前收。用 latch 保持 arrival 峰值并按此衰减：弯中 lateral 短暂回落
    # 不收门（持续转）、出弯迟滞收轮。越大保持越久（出弯 lag 越长，过头会出弯过转），0=不保持。
    "turn_in_hold_decay": 0.92,
    # R040/R041（2026-06-12，接触日志定位 t≈228.6 撞内栏）：弯中可信白线显示车已切内侧时，按
    # (|line_offset|−offset_min)·gain×置信度 成比例削弱远处预瞄项（lookahead+heading），上限
    # corner_relief_max。直接在源头放大半径并消除"road-mask 拉内 vs 白线拉外"的来回甩。
    # 只缩远处转向项，不进 risk/mode/速度/入弯门控。
    # R041 关键：relief 加"保持/迟滞"。接触日志显示撞栏发生在 line_offset 来回穿过 0 的极限环里——
    # offset 一翻负 relief 就瞬间归零、road-mask 立刻猛拉回 -0.76、过冲撞内栏。所以 relief 触发后
    # 按 hold_decay 衰减保持，trough 里也压住远处项，打破极限环。同时调激进（gain/max 调大、门降到
    # 0.45）——之前保守微调没用。**走线改动，需人上车终判。**
    "corner_relief_enable": True,
    "corner_relief_conf_min": 0.45,
    "corner_relief_offset_min": 0.25,
    "corner_relief_gain": 2.0,
    "corner_relief_max": 0.85,
    "corner_relief_hold_decay": 0.85,   # relief 触发后每帧保持衰减系数（迟滞，破极限环）
    "steering_deadzone": 0.015,
    "max_abs_steering": 0.76,
    "hard_turn_steering_scale": 0.78,
    "steering_speed_cap_scale": 0.20,   # R047：高速收舵放松——速度上调后它在弯里把舵卡死、导致打不动/冲外
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
    # 速度提升 Phase 3（激进）：弯道/横偏/转向降速因子整体减弱——半径已稳，不需要刹这么狠。
    "curve_slowdown": 0.42,
    "curve_power": 1.5,    # 提高指数：中等弯(curve_risk 0.4-0.6)提速，急弯(=1.0)降速不变(物理上限)
    "offset_slowdown": 0.28,
    "offset_power": 1.25,
    # 速度提升 Phase 1（最安全、收益最大）：解耦感知置信对速度的惩罚。track_conf 中位仅 0.60，
    # 几何没问题也被压速；min_confidence_factor 0.58→0.90 → 中等置信几乎不再压速。
    "min_confidence_factor": 0.95,
    "steering_slowdown": 0.12,
    "steering_power": 1.15,
    "steering_smoothing_cruise": 0.16,
    "steering_smoothing_turn": 0.14,
    "steering_smoothing_correction": 0.14,
    "steering_smoothing_recovery": 0.28,
    "max_steering_delta": 0.46,
    # 速度提升 Phase 4（激进）：出弯后更快回速，缩短低速段。
    "max_speed_increase_per_sec": 5.0,
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

# 有其他车策略尚未实现。这里保留命名入口，避免继续把旧名字当成策略名。
WITH_OTHER_CARS_CONTROL = None

# 兼容旧测试和局部脚本里直接导入 CONTROL 的用法。新代码应使用 NO_OTHER_CARS_CONTROL。
CONTROL = NO_OTHER_CARS_CONTROL

def get_profile(name: str) -> dict:
    """读取控制 profile。

    功能：为顶层控制器提供当前选择的策略参数。
    参数：`name` 是策略名，目前只接受 no_other_cars / with_other_cars。
    返回：策略参数字典的浅拷贝。
    逻辑：当前只实现无其他车策略；有其他车策略保留名称但显式报未实现。
    """

    profile_name = str(name)
    if profile_name == STRATEGY_NO_OTHER_CARS:
        return dict(NO_OTHER_CARS_CONTROL)
    if profile_name == STRATEGY_WITH_OTHER_CARS:
        raise NotImplementedError("with_other_cars strategy is not implemented yet")
    raise ValueError(f"unknown strategy profile: {name}")
