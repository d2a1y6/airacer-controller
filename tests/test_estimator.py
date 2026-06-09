import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import PerceptionObs
from controller.estimator import estimate_track, reset_estimator_state


def make_obs(fn, count=12, confidence=0.95, y_min=220.0, y_max=450.0, road_width=240.0):
    progress = np.linspace(0.0, 1.0, count, dtype=np.float32)
    x_norm = np.array([fn(float(item)) for item in progress], dtype=np.float32)
    x = 320.0 + x_norm * 320.0
    y = y_max - progress * (y_max - y_min)
    points = np.column_stack([x, y]).astype(np.float32)
    return PerceptionObs(points, points, points, road_width, confidence)


def assert_track_range(track):
    assert -1.0 <= track.lateral_error <= 1.0
    assert -1.0 <= track.heading_error <= 1.0
    assert -1.0 <= track.curvature <= 1.0
    assert -1.0 <= track.lookahead_error <= 1.0
    assert 0.0 <= track.confidence <= 1.0


def test_centerline_straight_track_is_near_zero():
    reset_estimator_state()
    track = estimate_track(make_obs(lambda progress: 0.0), 0.0)
    assert track.lost is False
    assert abs(track.lateral_error) < 0.03
    assert abs(track.lookahead_error) < 0.03
    assert abs(track.heading_error) < 0.03
    assert abs(track.curvature) < 0.03
    assert_track_range(track)


def test_offset_left_and_right_keep_sign():
    reset_estimator_state()
    left_track = estimate_track(make_obs(lambda progress: -0.22), 0.0)
    reset_estimator_state()
    right_track = estimate_track(make_obs(lambda progress: 0.22), 0.0)

    assert left_track.lateral_error < -0.05
    assert left_track.lookahead_error < -0.05
    assert right_track.lateral_error > 0.05
    assert right_track.lookahead_error > 0.05
    assert_track_range(left_track)
    assert_track_range(right_track)


def test_left_and_right_curves_keep_heading_and_curvature_sign():
    reset_estimator_state()
    left_curve = estimate_track(make_obs(lambda progress: -0.30 * progress * progress), 0.0)
    reset_estimator_state()
    right_curve = estimate_track(make_obs(lambda progress: 0.30 * progress * progress), 0.0)

    assert left_curve.heading_error < -0.05
    assert left_curve.curvature < -0.05
    assert left_curve.lookahead_error < left_curve.lateral_error
    assert right_curve.heading_error > 0.05
    assert right_curve.curvature > 0.05
    assert right_curve.lookahead_error > right_curve.lateral_error
    assert_track_range(left_curve)
    assert_track_range(right_curve)


def test_too_few_points_enter_lost():
    reset_estimator_state()
    track = estimate_track(make_obs(lambda progress: 0.0, count=2), 0.0)
    assert track.lost is True
    assert_track_range(track)


def test_low_confidence_enters_lost():
    reset_estimator_state()
    track = estimate_track(make_obs(lambda progress: 0.0, confidence=0.02), 0.0)
    assert track.lost is True
    assert_track_range(track)


def test_timestamp_reset_discards_previous_smoothing_state():
    reset_estimator_state()
    previous = estimate_track(make_obs(lambda progress: 0.35), 10.0)
    assert previous.lateral_error > 0.05

    reset_by_time = estimate_track(make_obs(lambda progress: 0.0), 9.5)
    assert reset_by_time.lost is False
    assert abs(reset_by_time.lateral_error) < 0.03
    assert abs(reset_by_time.lookahead_error) < 0.03


def test_estimator_outputs_stay_in_range_for_extreme_points():
    reset_estimator_state()
    obs = make_obs(lambda progress: 2.5 - 5.0 * progress, count=14, confidence=0.85)
    track = estimate_track(obs, 0.0)
    assert_track_range(track)
