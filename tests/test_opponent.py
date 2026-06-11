import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.opponent import detect_near_vehicle_obstacle


def _road_image():
    """Medium-gray road with no vehicle-colored blobs."""
    return np.full((480, 640, 3), 85, dtype=np.uint8)


def _vehicle_image():
    """Large bright-white block inside the detector ROI (rows 250-451, cols 51-589)."""
    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[290:400, 200:380] = 255
    return image


def test_no_obstacle_on_plain_road():
    assert detect_near_vehicle_obstacle(_road_image()) is False


def test_detects_large_white_vehicle_block():
    assert detect_near_vehicle_obstacle(_vehicle_image()) is True


def test_saturated_background_is_not_a_vehicle():
    """红色场地和天空这类高饱和大块不能触发近障碍。"""

    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[250:430, 80:560] = (255, 178, 102)
    assert detect_near_vehicle_obstacle(image) is False
