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
    half_width = road_width * 0.5
    left_edges = np.column_stack([x - half_width, y]).astype(np.float32)
    right_edges = np.column_stack([x + half_width, y]).astype(np.float32)
    return PerceptionObs(points, left_edges, right_edges, road_width, confidence)


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


def test_red_environment_stays_latched_until_reset():
    reset_estimator_state()
    red_obs = make_obs(lambda progress: 0.0)
    red_obs.debug_flags = 32
    one_red_track = estimate_track(red_obs, 0.0)
    assert one_red_track.red_environment is True

    plain_after_single_red = estimate_track(make_obs(lambda progress: 0.0), 0.032)
    assert plain_after_single_red.red_environment is False

    estimate_track(red_obs, 0.064)
    estimate_track(red_obs, 0.096)
    estimate_track(red_obs, 0.128)
    latched_track = estimate_track(make_obs(lambda progress: 0.0), 0.160)
    assert latched_track.red_environment is True

    reset_estimator_state()
    reset_track = estimate_track(make_obs(lambda progress: 0.0), 0.0)
    assert reset_track.red_environment is False


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


def test_line_state_is_diagnostic_only_by_default():
    # 默认融合权重为 0：白线只透传到 TrackState，不改写控制目标
    # （R013/R014 实车证明目标改写会污染 offset_risk/直道判定/入弯门控）。
    reset_estimator_state()
    obs = make_obs(lambda progress: 0.0)
    obs.line_offset = 0.32
    obs.line_heading = 0.08
    obs.line_confidence = 0.90

    track = estimate_track(obs, 0.0)

    assert track.lost is False
    assert track.line_offset == obs.line_offset
    assert track.line_heading == obs.line_heading
    assert track.line_confidence == obs.line_confidence
    assert abs(track.lateral_error) < 0.03
    assert abs(track.heading_error) < 0.03
    assert abs(track.lookahead_error) < 0.03


def test_line_fusion_mechanism_works_when_weights_enabled(monkeypatch):
    from controller.estimator import ESTIMATOR_PROFILE

    monkeypatch.setitem(ESTIMATOR_PROFILE, "line_lateral_weight", 0.82)
    monkeypatch.setitem(ESTIMATOR_PROFILE, "line_heading_weight", 0.68)
    monkeypatch.setitem(ESTIMATOR_PROFILE, "line_lookahead_weight", 0.58)

    reset_estimator_state()
    obs = make_obs(lambda progress: 0.0)
    obs.line_offset = 0.32
    obs.line_heading = 0.08
    obs.line_confidence = 0.90

    track = estimate_track(obs, 0.0)

    assert track.lost is False
    assert track.lateral_error > 0.12
    assert track.heading_error > 0.02
    assert track.lookahead_error > 0.08
