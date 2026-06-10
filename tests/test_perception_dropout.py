import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.params import VISION_PROFILE
from controller.perception import _score_scan


def _three_stable_scan_lines():
    centers = [(320.0, 440.0), (321.0, 400.0), (322.0, 360.0)]
    widths = [220.0, 218.0, 216.0]
    return centers, widths


def test_saturated_mask_is_penalized_less_than_empty_mask():
    centers, widths = _three_stable_scan_lines()

    empty_conf, empty_flags = _score_scan(centers, widths, texture_score=0.5, mask_fill_ratio=0.0, fallback_count=0)
    saturated_conf, saturated_flags = _score_scan(
        centers,
        widths,
        texture_score=0.5,
        mask_fill_ratio=0.95,
        fallback_count=0,
    )

    assert empty_flags & 4
    assert saturated_flags & 4
    assert empty_conf < VISION_PROFILE["min_camera_confidence"]
    assert saturated_conf >= VISION_PROFILE["min_camera_confidence"]
