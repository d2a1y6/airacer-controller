import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import ControlCmd, PerceptionObs, TrackState, clamp_cmd
from controller.estimator import estimate_track, reset_estimator_state
from controller.params import OPPONENT_PROFILE, VISION_PROFILE
from controller.policy import decide_control, reset_policy_state
import controller.perception as perception
from controller.perception import extract_observation


def make_lane_image(offset=0):
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 110, 35)
    center = 320 + offset
    image[220:, max(center - 125, 0) : min(center + 125, 640), :] = (95, 95, 95)
    image[220:, max(center - 125, 0) : max(center - 118, 0), :] = 255
    image[220:, min(center + 118, 639) : min(center + 125, 640), :] = 255
    return image


def test_module_contracts_on_mock_lane():
    reset_estimator_state()
    reset_policy_state()
    image = make_lane_image()

    obs = extract_observation(image, image, 0.0)
    assert isinstance(obs, PerceptionObs)
    assert obs.center_points.ndim == 2
    assert obs.center_points.shape[1] == 2
    assert len(obs.center_points) >= 4
    assert 0.0 <= obs.confidence <= 1.0

    track = estimate_track(obs, 0.0)
    assert isinstance(track, TrackState)
    assert -1.0 <= track.lateral_error <= 1.0
    assert 0.0 <= track.confidence <= 1.0

    cmd = decide_control(track, 0.0, mode="fastest")
    assert isinstance(cmd, ControlCmd)
    steering, speed = clamp_cmd(cmd)
    assert -1.0 <= steering <= 1.0
    assert 0.0 <= speed <= 1.0


def test_opponent_detection_is_disabled_by_default(monkeypatch):
    assert OPPONENT_PROFILE["enable_opponent_avoidance"] is False
    assert "near_obstacle_min_timestamp" not in VISION_PROFILE

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("opponent detector should stay disabled")

    monkeypatch.setattr(perception, "detect_near_vehicle_obstacle", fail_if_called)
    image = make_lane_image()
    obs = extract_observation(image, image, 999.0)
    assert isinstance(obs, PerceptionObs)
    assert len(obs.center_points) >= 4


def test_estimator_lost_contract_on_empty_observation():
    reset_estimator_state()
    points = np.empty((0, 2), dtype=np.float32)
    obs = PerceptionObs(points, points, points, 0.0, 0.0)
    track = estimate_track(obs, 1.0)
    assert track.lost is True
    assert 0.0 <= track.confidence <= 1.0


def test_estimator_lost_contract_on_too_few_points():
    reset_estimator_state()
    points = np.array([[320.0, 440.0], [321.0, 420.0]], dtype=np.float32)
    obs = PerceptionObs(points, points, points, 240.0, 0.9)
    track = estimate_track(obs, 1.0)
    assert track.lost is True


def test_policy_invalid_mode_uses_fastest_defaults():
    reset_policy_state()
    track = TrackState(0.0, 0.0, 0.0, 0.0, 1.0, False)
    cmd = decide_control(track, 2.0, mode="unknown")
    assert isinstance(cmd, ControlCmd)
    assert 0.0 <= cmd.speed <= 1.0
