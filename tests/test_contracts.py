import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import ControlMode, PerceptionObs, SpeedCmd, SteeringCmd, TrackState
from controller.estimator import estimate_track, reset_estimator_state
from controller.params import get_profile
from controller.perception import extract_observation
from controller.steering import compute_steering, reset_steering_state
from controller.strategy import compute_speed, select_mode


def make_lane_image(offset=0):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    center = 320 + offset
    image[240:, max(center - 95, 0) : max(center - 70, 0), :] = 255
    image[240:, min(center + 70, 639) : min(center + 95, 640), :] = 255
    return image


def test_module_contracts_on_mock_lane():
    reset_estimator_state()
    reset_steering_state()
    image = make_lane_image()
    profile = get_profile("fastest")

    obs = extract_observation(image, image)
    assert isinstance(obs, PerceptionObs)
    assert obs.center_points.ndim == 2
    assert obs.center_points.shape[1] == 2
    assert 0.0 <= obs.confidence <= 1.0

    track = estimate_track(obs, 0.0)
    assert isinstance(track, TrackState)
    assert -1.0 <= track.lateral_error <= 1.0
    assert 0.0 <= track.confidence <= 1.0

    mode = select_mode(track, 0.0, profile)
    assert isinstance(mode, ControlMode)
    assert mode.name in {"normal", "caution", "lost", "recovery"}
    assert 0.0 <= mode.risk <= 1.0

    steering = compute_steering(track, mode, 0.0, profile)
    assert isinstance(steering, SteeringCmd)
    assert -1.0 <= steering.value <= 1.0
    assert 0.0 <= steering.confidence <= 1.0

    speed = compute_speed(track, steering, mode, 0.0, profile)
    assert isinstance(speed, SpeedCmd)
    assert 0.0 <= speed.value <= 1.0
    assert 0.0 <= speed.confidence <= 1.0


def test_estimator_lost_contract_on_empty_observation():
    reset_estimator_state()
    points = np.empty((0, 2), dtype=np.float32)
    obs = PerceptionObs(points, points, points, 0.0, 0.0)
    track = estimate_track(obs, 1.0)
    assert track.lost is True
    assert 0.0 <= track.confidence <= 1.0
