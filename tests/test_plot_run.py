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


def _write_contact_log(path: Path) -> None:
    """写三段合成撞栏接触：前两段空间接近，第三段明显远离。"""

    rows = [
        {
            "t": 0.20, "team_id": "local_team", "car_slot": "car_1",
            "x": 2.0, "y": 0.4, "kind": "static_geometry", "count": 3,
            "points": [[2.0, 0.4, 0.65]],
        },
        {
            "t": 0.25, "team_id": "local_team", "car_slot": "car_1",
            "x": 2.1, "y": 0.5, "kind": "static_geometry", "count": 4,
            "points": [[2.1, 0.5, 0.70]],
        },
        {
            "t": 0.70, "team_id": "local_team", "car_slot": "car_1",
            "x": 3.2, "y": 0.5, "kind": "static_geometry", "count": 5,
            "points": [[3.2, 0.5, 0.62]],
        },
        {
            "t": 0.90, "team_id": "other_team", "car_slot": "car_2",
            "x": 3.4, "y": 0.7, "kind": "static_geometry", "count": 9,
            "points": [[3.4, 0.7, 0.95]],
        },
        {
            "t": 1.10, "team_id": "local_team", "car_slot": "car_1",
            "x": 15.0, "y": 3.0, "kind": "static_geometry", "count": 6,
            "points": [[15.0, 3.0, 0.80]],
        },
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_plot_run_writes_png(tmp_path):
    telemetry = tmp_path / "telemetry.jsonl"
    contact_log = tmp_path / "contact_complex.jsonl"
    _write_telemetry(telemetry)
    _write_contact_log(contact_log)
    out = tmp_path / "fig" / "trajectory_speed.png"

    sys_argv = [
        "plot_run.py",
        "--telemetry", str(telemetry),
        "--contact-log", str(contact_log),
        "--team-id", "local_team",
        "--out", str(out),
        "--title", "test run",
    ]
    import unittest.mock as mock
    with mock.patch.object(sys, "argv", sys_argv):
        assert plot_run.main() == 0

    assert out.is_file()
    assert out.stat().st_size > 1000  # 真出了一张非空 PNG


def test_contact_clusters_merge_nearby_episodes(tmp_path):
    contact_log = tmp_path / "contact_complex.jsonl"
    _write_contact_log(contact_log)

    rows = plot_run._load_contact_rows(contact_log, team_id="local_team")
    clusters = plot_run._contact_clusters(rows, start_t=0.0, end_t=1.2, merge_distance=4.0)

    assert len(clusters) == 2
    assert clusters[0]["episodes"] == 2
    assert clusters[0]["peak_count"] == 5
    assert clusters[1]["episodes"] == 1
    assert clusters[1]["peak_count"] == 6


def test_plot_run_missing_telemetry_returns_error(tmp_path, capsys):
    out = tmp_path / "fig.png"
    sys_argv = ["plot_run.py", "--telemetry", str(tmp_path / "missing.jsonl"), "--out", str(out)]
    import unittest.mock as mock
    with mock.patch.object(sys, "argv", sys_argv):
        assert plot_run.main() == 1
    assert "找不到遥测文件" in capsys.readouterr().out
    assert not out.exists()
