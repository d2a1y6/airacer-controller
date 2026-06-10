import importlib.util
import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import build_submission


def _load_module(path: Path):
    spec = importlib.util.spec_from_file_location("debug_team_controller", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_normal_build_source_has_no_frame_dump_probe():
    source = build_submission.build_source("fastest")

    assert "np.save" not in source
    assert "_DBG_FRAME_DIR" not in source
    assert "_DBG_FH" not in source


def test_debug_build_can_dump_left_and_right_frames(tmp_path):
    dump_dir = tmp_path / "frames"
    dump_dir.mkdir()
    module_path = tmp_path / "team_controller_debug.py"
    module_path.write_text(
        build_submission.build_source("fastest", dump_frames=str(dump_dir), dump_frame_stride=1),
        encoding="utf-8",
    )
    module = _load_module(module_path)

    left = np.zeros((32, 48, 3), dtype=np.uint8)
    right = np.full((32, 48, 3), 17, dtype=np.uint8)
    steering, speed = module.control(left, right, 12.345)

    saved = sorted(dump_dir.glob("*.npy"))
    assert len(saved) == 2
    assert "frame_000012_345_left.npy" in {path.name for path in saved}
    assert "frame_000012_345_right.npy" in {path.name for path in saved}
    assert np.array_equal(np.load(dump_dir / "frame_000012_345_left.npy"), left)
    assert np.array_equal(np.load(dump_dir / "frame_000012_345_right.npy"), right)
    assert -1.0 <= steering <= 1.0
    assert 0.0 <= speed <= 1.0
