import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.perception import extract_observation
from scripts.analyze_perception_dump import analyze_dump


def _lane_image() -> np.ndarray:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 110, 35)
    image[220:, 200:440, :] = (95, 95, 95)
    image[220:, 200:207, :] = 255
    image[220:, 433:440, :] = 255
    return image


def _save_pair(frame_dir: Path, timestamp_token: str, image: np.ndarray) -> None:
    np.save(frame_dir / f"frame_{timestamp_token}_left.npy", image)
    np.save(frame_dir / f"frame_{timestamp_token}_right.npy", image)


def test_analyze_dump_reproduces_control_log_fields(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    image = _lane_image()
    _save_pair(frame_dir, "000000_096", image)
    obs = extract_observation(image, image, 0.096)
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
