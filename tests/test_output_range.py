import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.estimator import reset_estimator_state
from controller.policy import reset_policy_state
from controller.team_controller_local import control


def make_lane_image(offset=0):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 110, 35)
    center = 320 + offset
    image[220:, max(center - 125, 0) : min(center + 125, 640), :] = (95, 95, 95)
    image[220:, max(center - 125, 0) : max(center - 118, 0), :] = 255
    image[220:, min(center + 118, 639) : min(center + 125, 640), :] = 255
    return image


def test_control_output_range_on_mock_images():
    cases = [
        np.zeros((480, 640, 3), dtype=np.uint8),
        np.full((480, 640, 3), 255, dtype=np.uint8),
        np.random.default_rng(42).integers(0, 256, size=(480, 640, 3), dtype=np.uint8),
        make_lane_image(-80),
        make_lane_image(0),
        make_lane_image(80),
    ]
    for timestamp, image in enumerate(cases):
        reset_estimator_state()
        reset_policy_state()
        steering, speed = control(image, image, float(timestamp))
        assert -1.0 <= float(steering) <= 1.0
        assert 0.0 <= float(speed) <= 1.0


def test_extract_observation_handles_common_images():
    from controller.perception import extract_observation

    cases = [
        np.zeros((480, 640, 3), dtype=np.uint8),
        np.full((480, 640, 3), 255, dtype=np.uint8),
        np.random.default_rng(7).integers(0, 256, size=(480, 640, 3), dtype=np.uint8),
        make_lane_image(0),
    ]
    for image in cases:
        obs = extract_observation(image, image, 0.0)
        assert obs.center_points.ndim == 2
        assert obs.center_points.shape[1] == 2
        assert obs.left_edge_points.ndim == 2
        assert obs.right_edge_points.ndim == 2
        assert 0.0 <= obs.confidence <= 1.0


def test_extract_observation_prefers_dark_road_over_bottom_grass():
    from controller.perception import extract_observation

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 120, 35)
    image[180:, :260, :] = (82, 74, 64)  # 采样自 complex/basic 原始帧的深灰沥青 BGR。

    obs = extract_observation(image, image, 0.0)

    assert len(obs.center_points) >= 4
    assert obs.confidence > 0.20
    assert float(np.median(obs.center_points[:, 0])) < 260.0
