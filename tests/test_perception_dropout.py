import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.params import VISION_PROFILE
from controller.perception import (
    _build_masks,
    _filter_fallback_segments,
    _score_scan,
)


def _three_stable_scan_lines():
    centers = [(320.0, 440.0), (321.0, 400.0), (322.0, 360.0)]
    widths = [220.0, 218.0, 216.0]
    return centers, widths


def test_empty_and_saturated_masks_penalized_equally():
    # C001 曾把饱和 mask 的惩罚放宽，导致"草地被当成路"的饱和帧被放行。
    # 现在草地在 mask 层被扣除，置信度层对近空/饱和一视同仁（都重罚）。
    centers, widths = _three_stable_scan_lines()

    empty_conf, empty_flags = _score_scan(centers, widths, texture_score=0.5, mask_fill_ratio=0.0, fallback_count=0)
    saturated_conf, saturated_flags = _score_scan(
        centers, widths, texture_score=0.5, mask_fill_ratio=0.95, fallback_count=0
    )

    assert empty_flags & 4
    assert saturated_flags & 4
    assert empty_conf < VISION_PROFILE["min_camera_confidence"]
    assert saturated_conf < VISION_PROFILE["min_camera_confidence"]
    assert abs(empty_conf - saturated_conf) < 1e-9


def test_red_world_wide_mask_is_low_confidence():
    # complex 开头路外低饱和地面会让 mask 大面积铺满；这种 road center 不应高置信压过白线。
    centers, widths = _three_stable_scan_lines()

    normal_conf, normal_flags = _score_scan(
        centers,
        widths,
        texture_score=0.8,
        mask_fill_ratio=0.80,
        fallback_count=0,
        red_environment=False,
    )
    red_conf, red_flags = _score_scan(
        centers,
        widths,
        texture_score=0.8,
        mask_fill_ratio=0.80,
        fallback_count=0,
        red_environment=True,
    )

    assert red_flags & 4
    assert red_conf < normal_conf * 0.5


def _grass_with_center_strip(height=480, width=640, strip=(280, 360)):
    """整片高饱和绿草，中间一条灰色沥青竖条。"""

    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = (0, 200, 0)  # BGR 绿，高饱和
    image[:, strip[0]:strip[1]] = (82, 74, 64)  # complex 原图采样得到的深灰沥青（BGR）
    return image


def test_grass_is_excluded_from_road_mask():
    image = _grass_with_center_strip()
    road_mask, _edge, _tex, mask_fill_ratio, _near, _x, _size = _build_masks(image)

    top = int(image.shape[0] * VISION_PROFILE["roi_top_ratio"])
    # 草地列（远离中间条）几乎不应进入道路 mask。
    grass_cols = road_mask[top:, 0:200]
    assert grass_cols.mean() < 5.0
    # 中间灰条应被保留为道路。
    strip_cols = road_mask[top:, 290:350]
    assert strip_cols.mean() > 50.0


def test_blue_checkpoint_barrier_is_bridged_as_road():
    # 半透明蓝色 checkpoint 门横跨道路：门后是可行驶路面，应被并入道路 mask，避免把走廊在门处截断。
    # 实车验证（R005）此修复是迄今最好版本——离线 lost 率升高是良性的，不要据此移除。
    image = _grass_with_center_strip()
    barrier_bgr = cv2.cvtColor(np.uint8([[[102, 111, 149]]]), cv2.COLOR_HSV2BGR)[0, 0]
    image[250:300, :] = barrier_bgr  # 横跨整幅的蓝门带

    road_mask, _edge, _tex, _fill, _near, _x, _size = _build_masks(image)
    bridged = road_mask[255:295, 295:345]
    assert bridged.mean() > 50.0


def test_side_blue_guardrail_is_not_bridged_as_road():
    # 蓝灰侧边栏杆与 checkpoint 门色相相近，但不是横跨道路的大水平带，不能并入 road mask。
    image = _grass_with_center_strip()
    barrier_bgr = cv2.cvtColor(np.uint8([[[102, 111, 149]]]), cv2.COLOR_HSV2BGR)[0, 0]
    image[:, 0:80] = barrier_bgr

    road_mask, _edge, _tex, _fill, _near, _x, _size = _build_masks(image)

    top = int(image.shape[0] * VISION_PROFILE["roi_top_ratio"])
    assert road_mask[top:, 0:80].mean() < 5.0


def test_full_grass_view_collapses_mask():
    # 偏出赛道正对草地：mask 应塌成近空，让上层进入 lost 而不是把草当路。
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (0, 200, 0)
    road_mask, _edge, _tex, mask_fill_ratio, _near, _x, _size = _build_masks(image)
    assert mask_fill_ratio < 0.015


def test_narrow_far_fallback_segment_is_rejected_without_history():
    # 第二个弯白线接缝会在近处生成远离中心的窄 edge fallback 段。
    # 没有上一条中心线时不能用它当 seed，否则后续中心线会被拉向内侧栏杆。
    assert _filter_fallback_segments([(512, 541)], 640, 320.0, has_previous=False) == []


def test_narrow_fallback_segment_must_continue_previous_center():
    # 有历史中心时，窄 fallback 只能做小幅延续；大跳变通常来自孤立白线/接缝。
    assert _filter_fallback_segments([(205, 278)], 640, 411.0, has_previous=True) == []
    assert _filter_fallback_segments([(382, 430)], 640, 411.0, has_previous=True) == [(382, 430)]
