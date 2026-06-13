"""Profile 隔离测试：no_other_cars(单车=R049) 不跑任何多车感知/策略路径。

锁定 CLAUDE.md「Profile 隔离」约定：active profile 贯穿 perception → policy，
no_other_cars 下既不调用对手检测、也不算 frame_motion，policy 不触发避让/倒车/force_escape。
"""

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import TrackState
from controller.params import get_profile
from controller.perception import extract_observation, reset_frame_motion_state
from controller.policy import decide_control, reset_policy_state


def _obstacle_image() -> np.ndarray:
    # 前下方中央一大块近黑色 = 对手车身候选块。
    img = np.full((480, 640, 3), 120, np.uint8)
    img[300:460, 250:390] = 10
    return img


def test_no_other_cars_perception_skips_opponent_and_motion():
    img = _obstacle_image()
    reset_frame_motion_state()
    p = get_profile("no_other_cars")
    extract_observation(img, img, 0.0, profile=p)
    obs = extract_observation(img, img, 0.032, profile=p)
    # 单车不做对手检测
    assert obs.near_obstacle is False
    assert obs.obstacle_x == 0.0
    assert obs.obstacle_size == 0.0
    # 单车不算 frame_motion（保持默认 100 = 视作在动，motion-stall 永不触发）
    assert obs.frame_motion >= 100.0


def test_with_other_cars_perception_detects_opponent_and_motion():
    img = _obstacle_image()
    reset_frame_motion_state()
    p = get_profile("with_other_cars")
    extract_observation(img, img, 0.0, profile=p)
    obs = extract_observation(img, img, 0.032, profile=p)
    assert obs.near_obstacle is True
    assert abs(obs.obstacle_x) < 0.15
    assert obs.obstacle_size > 0.0
    # 两帧相同 → frame_motion≈0（真在算）
    assert obs.frame_motion < 1.0


def test_profile_none_keeps_backward_compatible_detection():
    # 不传 profile（测试/replay 直接调用）退回旧行为：按全局开关跑检测。
    img = _obstacle_image()
    reset_frame_motion_state()
    obs = extract_observation(img, img, 0.0)
    assert obs.near_obstacle is True


def test_no_other_cars_policy_never_reverses_or_force_escapes():
    # 即使喂一个会让 with_other_cars 倒车/触发 force_escape 的卡死/丢线场景，
    # no_other_cars 也不应输出负速度。
    pinned = TrackState(
        lateral_error=-0.62, heading_error=0.14, curvature=0.09,
        lookahead_error=-0.52, confidence=0.83, lost=False, red_environment=False,
    )
    lost = TrackState(
        lateral_error=0.0, heading_error=0.0, curvature=0.0,
        lookahead_error=0.0, confidence=0.0, lost=True, red_environment=False,
    )
    for track in (pinned, lost):
        reset_policy_state()
        t = 0.0
        for _ in range(200):
            t += 0.032
            cmd = decide_control(track, t, mode="no_other_cars")
            assert cmd.speed >= 0.0  # 绝不倒车


def test_with_other_cars_motion_stall_triggers_reverse_escape_on_jitter():
    """轻微画面抖动但车身不前进时，多车 profile 应主动倒车脱困。"""

    stalled = TrackState(
        lateral_error=0.05,
        heading_error=0.05,
        curvature=0.03,
        lookahead_error=0.05,
        confidence=0.90,
        lost=False,
        red_environment=True,
        left_margin_near=0.08,
        right_margin_near=0.75,
        frame_motion=0.25,
    )
    reset_policy_state()
    t = 0.0
    cmd = None
    for _ in range(130):
        t += 0.032
        cmd = decide_control(stalled, t, mode="with_other_cars")

    assert cmd is not None
    assert cmd.speed < 0.0
