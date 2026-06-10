import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts import analyze_telemetry


def _telemetry_row(t: float, *, team_id: str = "car_1", speed: float = 1.0) -> dict:
    return {
        "t": t,
        "cars": [
            {
                "team_id": team_id,
                "x": t,
                "y": t + 1.0,
                "speed": speed,
                "lap": 0,
                "lap_progress": 0.0,
                "status": "normal",
            }
        ],
        "events": [],
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_load_car_frames_handles_single_frame(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    _write_jsonl(path, [_telemetry_row(0.0, speed=2.0)])

    frames, events = analyze_telemetry._load_car_frames(path, "car_1")

    assert len(frames) == 1
    assert frames[0]["speed"] == 2.0
    assert events == []


def test_load_car_frames_ignores_empty_file(tmp_path):
    path = tmp_path / "telemetry.jsonl"
    path.write_text("", encoding="utf-8")

    frames, events = analyze_telemetry._load_car_frames(path, None)

    assert frames == []
    assert events == []


def test_split_runs_uses_timestamp_regression():
    frames = [
        {"t": 10.0},
        {"t": 10.1},
        {"t": 0.0},
        {"t": 0.1},
    ]

    runs = analyze_telemetry._split_runs(frames)

    assert [len(run) for run in runs] == [2, 2]
    assert runs[-1][0]["t"] == 0.0


def test_main_reports_empty_telemetry(tmp_path, monkeypatch, capsys):
    path = tmp_path / "telemetry.jsonl"
    path.write_text("", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["analyze_telemetry.py", "--telemetry", str(path), "--no-archive"])

    assert analyze_telemetry.main() == 1
    assert "未解析到任何车辆帧" in capsys.readouterr().out


def test_main_uses_latest_run_when_telemetry_is_interleaved(tmp_path, monkeypatch, capsys):
    path = tmp_path / "telemetry.jsonl"
    _write_jsonl(path, [
        _telemetry_row(5.0, speed=1.0),
        _telemetry_row(5.1, speed=1.0),
        _telemetry_row(0.0, speed=2.0),
    ])
    (tmp_path / "metadata.json").write_text(json.dumps({"total_frames": 1}), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["analyze_telemetry.py", "--telemetry", str(path), "--no-archive"])

    assert analyze_telemetry.main() == 0
    out = capsys.readouterr().out
    assert "interleaved" in out
    assert "1 帧" in out
