import ast
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BANNED_MODULES = {
    "os",
    "sys",
    "socket",
    "subprocess",
    "multiprocessing",
    "threading",
    "time",
    "datetime",
    "io",
    "builtins",
    "ctypes",
    "shutil",
    "tempfile",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "signal",
    "gc",
    "inspect",
    "importlib",
    "pickle",
    "glob",
    "fnmatch",
}
BANNED_NAMES = {
    "open",
    "eval",
    "exec",
    "compile",
    "globals",
    "locals",
    "input",
    "breakpoint",
    "__import__",
    "vars",
}


def test_generated_submission_static_contract():
    path = ROOT / "submissions" / "final" / "team_controller.py"
    subprocess.run(["python", "scripts/build_submission.py", "--mode", "no_other_cars"], cwd=ROOT, check=True)
    source = path.read_text(encoding="utf-8")
    assert "from controller" not in source
    assert "from ." not in source
    assert "# ---- steering.py ----" not in source
    assert "# ---- strategy.py ----" not in source
    assert "# ---- policy.py ----" in source

    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(alias.name.split(".")[0] not in BANNED_MODULES for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in BANNED_MODULES
        elif isinstance(node, ast.Name):
            assert node.id not in BANNED_NAMES
