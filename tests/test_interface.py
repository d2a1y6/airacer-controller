import importlib.util
import subprocess
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]


def load_submission(path):
    spec = importlib.util.spec_from_file_location("candidate", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_generated_submission_has_callable_control():
    path = ROOT / "submissions" / "fastest" / "team_controller.py"
    subprocess.run(["python", "scripts/build_submission.py", "--mode", "fastest"], cwd=ROOT, check=True)
    module = load_submission(path)
    assert callable(module.control)

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    steering, speed = module.control(image, image, 0.0)
    assert isinstance(float(steering), float)
    assert isinstance(float(speed), float)


def test_local_control_has_callable_interface():
    from controller.team_controller_local import control

    image = np.zeros((480, 640, 3), dtype=np.uint8)
    steering, speed = control(image, image, 0.0)
    assert isinstance(float(steering), float)
    assert isinstance(float(speed), float)
