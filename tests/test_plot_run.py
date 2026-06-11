import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import plot_run


def _write_telemetry(path: Path) -> None:
    """写一小段合成 telemetry：直行加速 → 一段卡住（status 异常）→ 恢复。"""

    rows = []
    for i in range(20):
        t = round(0.05 * (i + 1), 3)
        x = round(1.0 * i, 3)
        y = round(0.2 * i, 3)
        speed = 0.0 if 8 <= i <= 11 else 3.0
        status = "stuck" if 8 <= i <= 11 else "normal"
        rows.append({
            "t": t,
            "cars": [{
                "team_id": "local_team", "x": x, "y": y, "heading": 0.0,
                "speed": speed, "lap": 0, "lap_progress": 0.0, "status": status,
            }],
            "events": [],
        })
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_plot_run_writes_png(tmp_path):
    telemetry = tmp_path / "telemetry.jsonl"
    _write_telemetry(telemetry)
    out = tmp_path / "fig" / "trajectory_speed.png"

    sys_argv = ["plot_run.py", "--telemetry", str(telemetry), "--out", str(out), "--title", "test run"]
    import unittest.mock as mock
    with mock.patch.object(sys, "argv", sys_argv):
        assert plot_run.main() == 0

    assert out.is_file()
    assert out.stat().st_size > 1000  # 真出了一张非空 PNG


def test_plot_run_missing_telemetry_returns_error(tmp_path, capsys):
    out = tmp_path / "fig.png"
    sys_argv = ["plot_run.py", "--telemetry", str(tmp_path / "missing.jsonl"), "--out", str(out)]
    import unittest.mock as mock
    with mock.patch.object(sys, "argv", sys_argv):
        assert plot_run.main() == 1
    assert "找不到遥测文件" in capsys.readouterr().out
    assert not out.exists()
