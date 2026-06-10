import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import json

from scripts import analyze_control_log
from scripts.analyze_control_log import collect_lost_diagnostics, decode_debug_flags


def _row(
    t: float,
    *,
    lost: bool,
    mode: str,
    curvature: float = 0.0,
    heading: float = 0.0,
    track_conf: float = 0.8,
    obs_conf: float = 0.8,
    obs_points: int = 8,
    road_width: float = 240.0,
    debug_flags: int = 0,
) -> dict:
    return {
        "t": t,
        "lost": lost,
        "mode": mode,
        "curvature": curvature,
        "heading": heading,
        "track_conf": track_conf,
        "obs_conf": obs_conf,
        "obs_points": obs_points,
        "road_width": road_width,
        "debug_flags": debug_flags,
    }


def test_decode_debug_flags_names_known_bits():
    assert decode_debug_flags(1 | 2 | 4 | 8 | 16 | 32) == [
        "有效扫描线过少",
        "用了边缘fallback",
        "mask填充率极端",
        "左右近处中心偏差大",
        "左右置信度接近",
        "红色环境",
    ]


def test_decode_debug_flags_keeps_unknown_bits():
    assert decode_debug_flags(64) == ["未知位64"]


def test_collect_lost_diagnostics_segments_flags_and_entry_modes():
    rows = [
        _row(0.0, lost=False, mode="cruise", curvature=0.05, heading=0.02),
        _row(0.1, lost=True, mode="lost", curvature=0.30, heading=-0.20, track_conf=0.1, obs_conf=0.2, obs_points=2, road_width=80, debug_flags=1 | 4),
        _row(0.2, lost=True, mode="lost", curvature=-0.20, heading=0.10, track_conf=0.2, obs_conf=0.1, obs_points=3, road_width=90, debug_flags=1 | 2),
        _row(0.3, lost=False, mode="hard_turn", curvature=0.40, heading=0.30),
        _row(0.4, lost=True, mode="lost", curvature=0.50, heading=0.40, track_conf=0.0, obs_conf=0.0, obs_points=0, road_width=0, debug_flags=16),
    ]

    diag = collect_lost_diagnostics(rows)

    assert diag["frames"] == 5
    assert diag["lost_frames"] == 3
    assert diag["lost_frac"] == 0.6
    assert diag["segments"] == [2, 1]
    assert diag["segment_stats"]["count"] == 2
    assert diag["segment_stats"]["max"] == 2
    assert diag["flag_counter"][1] == 2
    assert diag["flag_counter"][2] == 1
    assert diag["flag_counter"][4] == 1
    assert diag["flag_counter"][16] == 1
    assert diag["entry_prev_modes"]["cruise"] == 1
    assert diag["entry_prev_modes"]["hard_turn"] == 1
    assert diag["lost_value_stats"]["obs_points"]["median"] == 2.0
    assert diag["curvature_abs_mean"]["lost"] > diag["curvature_abs_mean"]["non_lost"]
    assert diag["heading_abs_mean"]["lost"] > diag["heading_abs_mean"]["non_lost"]


def test_collect_lost_diagnostics_handles_no_lost_frames():
    rows = [
        _row(0.0, lost=False, mode="cruise"),
        _row(0.1, lost=False, mode="hard_turn"),
    ]

    diag = collect_lost_diagnostics(rows)

    assert diag["lost_frames"] == 0
    assert diag["lost_frac"] == 0.0
    assert diag["segments"] == []
    assert diag["segment_stats"]["max"] == 0
    assert not diag["flag_counter"]
    assert not diag["entry_prev_modes"]


def test_collect_lost_diagnostics_handles_single_lost_frame():
    diag = collect_lost_diagnostics([
        _row(0.0, lost=True, mode="lost", debug_flags=1),
    ])

    assert diag["lost_frames"] == 1
    assert diag["segments"] == [1]
    assert diag["entry_prev_modes"]["<start>"] == 1


def test_split_runs_uses_timestamp_regression():
    rows = [
        _row(5.0, lost=False, mode="cruise"),
        _row(5.1, lost=True, mode="lost"),
        _row(0.0, lost=False, mode="cruise"),
        _row(0.1, lost=False, mode="hard_turn"),
    ]

    runs = analyze_control_log._split_runs(rows)

    assert [len(run) for run in runs] == [2, 2]
    assert runs[-1][0]["t"] == 0.0


def test_analyze_file_rejects_empty_log(tmp_path, capsys):
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    assert analyze_control_log.analyze_file(path) == 1
    assert "日志为空" in capsys.readouterr().out


def test_main_accepts_directory_input(tmp_path, monkeypatch, capsys):
    path = tmp_path / "control_a.jsonl"
    path.write_text(json.dumps(_row(0.0, lost=False, mode="cruise")) + "\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["analyze_control_log.py", str(tmp_path)])

    assert analyze_control_log.main() == 0
    out = capsys.readouterr().out
    assert "control_a.jsonl" in out
    assert "lost 帧=0/1" in out
