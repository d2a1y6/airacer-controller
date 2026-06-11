import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.params import LINE_FOLLOW_PROFILE
from controller.perception import _stereo_line_state


def _line_image(x_values):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (60, 60, 60)
    rows = np.linspace(410, 240, len(x_values), dtype=np.int32)
    for x, y in zip(x_values, rows):
        cv2.rectangle(image, (int(x) - 5, int(y) - 10), (int(x) + 5, int(y) + 10), (220, 220, 220), -1)
    return image


def test_symmetric_stereo_line_has_near_zero_correction():
    left = _line_image([350, 348, 346, 344, 342, 340])
    right = _line_image([290, 292, 294, 296, 298, 300])

    offset, _heading, confidence = _stereo_line_state(left, right, LINE_FOLLOW_PROFILE)

    assert confidence >= LINE_FOLLOW_PROFILE["min_confidence"]
    assert abs(offset) < 0.03


def test_stereo_line_right_of_car_steers_right():
    left = _line_image([390, 388, 386, 384, 382, 380])
    right = _line_image([330, 332, 334, 336, 338, 340])

    offset, heading, confidence = _stereo_line_state(left, right, LINE_FOLLOW_PROFILE)

    assert confidence >= LINE_FOLLOW_PROFILE["min_confidence"]
    assert offset * LINE_FOLLOW_PROFILE["offset_gain"] + heading * LINE_FOLLOW_PROFILE["heading_gain"] > 0.04
