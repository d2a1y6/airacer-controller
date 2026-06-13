import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.opponent import detect_near_vehicle_obstacle, detect_near_vehicle_obstacle_state
from controller.params import COLOR_PROFILE


def _road_image():
    """Medium-gray road with no vehicle-colored blobs."""
    return np.full((480, 640, 3), 85, dtype=np.uint8)


def _vehicle_image():
    """Large bright-white block inside the detector ROI (rows 250-451, cols 51-589)."""
    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[290:400, 200:380] = 255
    return image


def _side_vehicle_image(x0: int, x1: int):
    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[290:400, x0:x1] = 255
    return image


def _colored_vehicle_image(color_name: str):
    """在近车 ROI 中放一块官方车身颜色。"""

    colors = {
        "car_phoenix_red": 0,
        "car_thunder_blue": 1,
        "car_viper_green": 2,
        "car_nova_yellow": 3,
    }
    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[290:400, 200:380] = COLOR_PROFILE["car_body_colors"][colors[color_name]][0]
    return image


def test_no_obstacle_on_plain_road():
    assert detect_near_vehicle_obstacle(_road_image()) is False


def test_dark_asphalt_is_not_shadow_black_vehicle():
    """complex 深灰路面不能被 Shadow black 颜色 profile 当成车身。"""

    image = np.full((480, 640, 3), (80, 72, 63), dtype=np.uint8)
    assert detect_near_vehicle_obstacle(image) is False


def test_detects_large_white_vehicle_block():
    assert detect_near_vehicle_obstacle(_vehicle_image()) is True


def test_vehicle_state_reports_left_and_right_position():
    near_left, x_left, size_left = detect_near_vehicle_obstacle_state(_side_vehicle_image(90, 230))
    near_right, x_right, size_right = detect_near_vehicle_obstacle_state(_side_vehicle_image(410, 550))

    assert near_left is True
    assert near_right is True
    assert x_left < -0.25
    assert x_right > 0.25
    assert size_left > 0.0
    assert size_right > 0.0


def test_vehicle_state_is_zero_without_obstacle():
    near, x, size = detect_near_vehicle_obstacle_state(_road_image())
    assert near is False
    assert x == 0.0
    assert size == 0.0


def test_detects_official_colored_vehicle_blocks():
    for color_name in (
        "car_phoenix_red",
        "car_thunder_blue",
        "car_viper_green",
        "car_nova_yellow",
    ):
        assert detect_near_vehicle_obstacle(_colored_vehicle_image(color_name)) is True


def test_saturated_background_is_not_a_vehicle():
    """红色场地和天空这类高饱和大块不能触发近障碍。"""

    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    image[250:430, 80:560] = (255, 178, 102)
    assert detect_near_vehicle_obstacle(image) is False


def test_track_background_colors_are_not_vehicle_blocks():
    image = np.full((480, 640, 3), 85, dtype=np.uint8)
    for color_name in ("red_ground", "blue_sky", "green_grass"):
        image[250:430, 80:560] = COLOR_PROFILE[color_name]["bgr_median"]
        assert detect_near_vehicle_obstacle(image) is False
