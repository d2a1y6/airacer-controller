import json
import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.perception import extract_observation
from controller.params import get_profile
from scripts.analyze_perception_dump import analyze_dump


def _lane_image() -> np.ndarray:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 110, 35)
    image[220:, 200:440, :] = (95, 95, 95)
    image[220:, 200:207, :] = 255
    image[220:, 433:440, :] = 255
    return image


def _obstacle_image() -> np.ndarray:
    image = _lane_image()
    image[300:450, 260:380, :] = 10
    return image


def _save_pair(frame_dir: Path, timestamp_token: str, image: np.ndarray) -> None:
    cv2.imwrite(str(frame_dir / f"frame_{timestamp_token}_left.png"), image)
    cv2.imwrite(str(frame_dir / f"frame_{timestamp_token}_right.png"), image)


def test_analyze_dump_reproduces_control_log_fields(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    image = _lane_image()
    _save_pair(frame_dir, "000000_096", image)
    obs = extract_observation(image, image, 0.096, profile=get_profile("no_other_cars"))
    control_log = tmp_path / "control.jsonl"
    control_log.write_text(
        json.dumps({
            "t": 0.096,
            "obs_points": int(len(obs.center_points)),
            "obs_conf": round(float(obs.confidence), 4),
            "debug_flags": int(obs.debug_flags),
        }) + "\n",
        encoding="utf-8",
    )

    metrics = analyze_dump(frame_dir, control_log, overlay_dir=tmp_path / "overlays")

    assert metrics["total_frames"] == 1
    assert metrics["joined_frames"] == 1
    assert metrics["mismatch_count"] == 0
    assert metrics["perception_lost_frames"] == 0


def test_overlay_at_forces_overlay_on_non_lost_frame(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    image = _lane_image()
    _save_pair(frame_dir, "000000_096", image)
    control_log = tmp_path / "control.jsonl"
    control_log.write_text(json.dumps({"t": 0.096}) + "\n", encoding="utf-8")
    overlay_dir = tmp_path / "overlays"

    # 这是一帧正常（未丢线）画面：默认模式不会出 overlay，但 --at 指定后必须强制出图。
    default_metrics = analyze_dump(frame_dir, control_log, overlay_dir=overlay_dir)
    assert default_metrics["overlay_paths"] == []

    forced_metrics = analyze_dump(
        frame_dir, control_log, overlay_dir=overlay_dir, overlay_at=[0.1]
    )
    assert len(forced_metrics["overlay_paths"]) == 1
    assert Path(forced_metrics["overlay_paths"][0]).is_file()


def test_analyze_dump_respects_profile_mode(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    image = _obstacle_image()
    _save_pair(frame_dir, "000000_096", image)
    control_log = tmp_path / "control.jsonl"

    obs = extract_observation(image, image, 0.096, profile=get_profile("with_other_cars"))
    control_log.write_text(
        json.dumps({
            "t": 0.096,
            "obs_points": int(len(obs.center_points)),
            "obs_conf": round(float(obs.confidence), 4),
            "debug_flags": int(obs.debug_flags),
        }) + "\n",
        encoding="utf-8",
    )

    wrong_mode = analyze_dump(frame_dir, control_log, mode="no_other_cars")
    matching_mode = analyze_dump(frame_dir, control_log, mode="with_other_cars")

    assert wrong_mode["frames"][0]["near_obstacle"] is False
    assert wrong_mode["frames"][0]["frame_motion"] >= 100.0
    assert matching_mode["frames"][0]["near_obstacle"] is True
    assert matching_mode["frames"][0]["frame_motion"] < 1.0
    assert matching_mode["mismatch_count"] == 0
