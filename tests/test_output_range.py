import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.estimator import reset_estimator_state
from controller.steering import reset_steering_state
from controller.team_controller_local import control


def make_lane_image(offset=0):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    center = 320 + offset
    image[230:, max(center - 100, 0) : max(center - 72, 0), :] = 255
    image[230:, min(center + 72, 639) : min(center + 100, 640), :] = 255
    return image


def test_control_output_range_on_mock_images():
    cases = [
        np.zeros((480, 640, 3), dtype=np.uint8),
        np.full((480, 640, 3), 255, dtype=np.uint8),
        make_lane_image(-80),
        make_lane_image(0),
        make_lane_image(80),
    ]
    for timestamp, image in enumerate(cases):
        reset_estimator_state()
        reset_steering_state()
        steering, speed = control(image, image, float(timestamp))
        assert -1.0 <= float(steering) <= 1.0
        assert 0.0 <= float(speed) <= 1.0
