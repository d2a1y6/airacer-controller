import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import cv2
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
    source = build_submission.build_source("no_other_cars")

    assert "cv2.imwrite" not in source
    assert "_DBG_FRAME_DIR" not in source
    assert "_DBG_FH" not in source
    assert "AIRACER_CONTROLLER_CONSOLE_LOG_DIR" not in source


def test_debug_build_can_dump_left_and_right_frames(tmp_path):
    dump_dir = tmp_path / "frames"
    dump_dir.mkdir()
    module_path = tmp_path / "team_controller_debug.py"
    module_path.write_text(
        build_submission.build_source("no_other_cars", dump_frames=str(dump_dir), dump_frame_stride=1),
        encoding="utf-8",
    )
    module = _load_module(module_path)

    left = np.zeros((32, 48, 3), dtype=np.uint8)
    right = np.full((32, 48, 3), 17, dtype=np.uint8)
    steering, speed = module.control(left, right, 12.345)

    saved = sorted(dump_dir.glob("*.png"))
    assert len(saved) == 2
    assert "frame_000012_345_left.png" in {path.name for path in saved}
    assert "frame_000012_345_right.png" in {path.name for path in saved}
    assert np.array_equal(cv2.imread(str(dump_dir / "frame_000012_345_left.png")), left)
    assert np.array_equal(cv2.imread(str(dump_dir / "frame_000012_345_right.png")), right)
    assert -1.0 <= steering <= 1.0
    assert 0.0 <= speed <= 1.0


def test_debug_frame_dump_defaults_to_stride_ten():
    source = build_submission.build_source("no_other_cars", dump_frames="/tmp/frames")

    assert "_DBG_FRAME_STRIDE = 10" in source


def test_debug_frame_dump_respects_time_window(tmp_path):
    dump_dir = tmp_path / "frames"
    dump_dir.mkdir()
    module_path = tmp_path / "team_controller_debug.py"
    module_path.write_text(
        build_submission.build_source(
            "no_other_cars",
            dump_frames=str(dump_dir),
            dump_frame_stride=1,
            dump_frame_start=10.0,
            dump_frame_end=11.0,
        ),
        encoding="utf-8",
    )
    module = _load_module(module_path)

    image = np.zeros((32, 48, 3), dtype=np.uint8)
    module.control(image, image, 9.9)
    module.control(image, image, 10.5)
    module.control(image, image, 11.1)

    saved_names = {path.name for path in dump_dir.glob("*.png")}
    assert saved_names == {
        "frame_000010_500_left.png",
        "frame_000010_500_right.png",
    }


def test_debug_build_can_tee_controller_console(tmp_path):
    console_dir = tmp_path / "console"
    module_path = tmp_path / "team_controller_debug.py"
    module_path.write_text(
        build_submission.build_source("no_other_cars", debug_log=str(tmp_path / "control.jsonl")),
        encoding="utf-8",
    )
    env = {**os.environ, "AIRACER_CONTROLLER_CONSOLE_LOG_DIR": str(console_dir)}
    script = (
        "import importlib.util, sys\n"
        f"spec = importlib.util.spec_from_file_location('debug_team_controller', {str(module_path)!r})\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "print('AIRACER_CONSOLE_PROBE_STDOUT')\n"
        "sys.stderr.write('AIRACER_CONSOLE_PROBE_STDERR\\n')\n"
        "sys.stderr.flush()\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    logs = list(console_dir.glob("team_controller_*.log"))
    assert len(logs) == 1
    content = logs[0].read_text(encoding="utf-8")
    assert "[team_controller] console tee enabled:" in content
    assert "AIRACER_CONSOLE_PROBE_STDOUT" in content
    assert "AIRACER_CONSOLE_PROBE_STDERR" in content
