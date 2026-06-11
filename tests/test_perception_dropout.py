import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.params import VISION_PROFILE
from controller.perception import _build_masks, _score_scan


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


def _grass_with_center_strip(height=480, width=640, strip=(280, 360)):
    """整片高饱和绿草，中间一条灰色沥青竖条。"""

    image = np.zeros((height, width, 3), dtype=np.uint8)
    image[:, :] = (0, 200, 0)  # BGR 绿，高饱和
    image[:, strip[0]:strip[1]] = (70, 70, 70)  # 灰沥青，低饱和
    return image


def test_grass_is_excluded_from_road_mask():
    image = _grass_with_center_strip()
    road_mask, _edge, _tex, mask_fill_ratio, _near = _build_masks(image)

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

    road_mask, _edge, _tex, _fill, _near = _build_masks(image)
    bridged = road_mask[255:295, 295:345]
    assert bridged.mean() > 50.0


def test_full_grass_view_collapses_mask():
    # 偏出赛道正对草地：mask 应塌成近空，让上层进入 lost 而不是把草当路。
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (0, 200, 0)
    road_mask, _edge, _tex, mask_fill_ratio, _near = _build_masks(image)
    assert mask_fill_ratio < 0.015
