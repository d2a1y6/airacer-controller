import json
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import analyze_control_log, replay_offline


CONTROL_SCHEMA = {
    "t",
    "steering",
    "speed",
    "lateral",
    "heading",
    "curvature",
    "lookahead",
    "track_conf",
    "lost",
    "red_env",
    "mode",
    "obs_conf",
    "obs_points",
    "road_width",
    "debug_flags",
}


def _lane_image() -> np.ndarray:
    image = np.zeros((480, 640, 3), dtype=np.uint8)
    image[:, :] = (35, 110, 35)
    image[220:, 200:440, :] = (95, 95, 95)
    image[220:, 200:207, :] = 255
    image[220:, 433:440, :] = 255
    return image


def _save_pair(frame_dir: Path, timestamp_name: str, left: np.ndarray, right: np.ndarray) -> None:
    np.save(frame_dir / f"frame_{timestamp_name}_left.npy", left)
    np.save(frame_dir / f"frame_{timestamp_name}_right.npy", right)


def test_iter_frame_pairs_sorts_by_timestamp(tmp_path):
    left = _lane_image()
    _save_pair(tmp_path, "000002_000", left, left)
    _save_pair(tmp_path, "000001_000", left, left)

    pairs = replay_offline.iter_frame_pairs(tmp_path)

    assert [item[0] for item in pairs] == [1.0, 2.0]


def test_replay_frames_writes_control_log_schema(tmp_path):
    frame_dir = tmp_path / "frames"
    frame_dir.mkdir()
    image = _lane_image()
    _save_pair(frame_dir, "000000_032", image, image)
    _save_pair(frame_dir, "000000_064", image, image)
    out_path = tmp_path / "replay.jsonl"

    written = replay_offline.replay_frames(frame_dir, out_path)

    rows = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert written == 2
    assert len(rows) == 2
    assert set(rows[0]) == CONTROL_SCHEMA
    assert rows[0]["t"] == 0.032
    assert -1.0 <= rows[0]["steering"] <= 1.0
    assert 0.0 <= rows[0]["speed"] <= 1.0
    assert analyze_control_log.collect_lost_diagnostics(rows)["frames"] == 2


def test_replay_main_rejects_missing_frame_dir(tmp_path, monkeypatch, capsys):
    out_path = tmp_path / "replay.jsonl"
    monkeypatch.setattr(sys, "argv", [
        "replay_offline.py",
        str(tmp_path / "missing"),
        "--out",
        str(out_path),
    ])

    assert replay_offline.main() == 1
    assert "找不到帧目录" in capsys.readouterr().out
