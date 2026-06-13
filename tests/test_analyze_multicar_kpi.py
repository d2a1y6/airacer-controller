import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_multicar_kpi import (
    POINTS,
    analyze,
    load_runs,
    pick_team_index,
    points_for_rank,
    progress_series,
    rank_at,
)


class _Args:
    stall_speed = 0.5
    stall_seconds = 3.0
    start_window = 5.0
    squeeze_dist = 3.0


def _frame(t, cars, events=None):
    return {"t": t, "cars": cars, "events": events or []}


def _car(team, x, y, speed=5.0, lap=0, lap_progress=0.0, status="normal"):
    return {
        "team_id": team,
        "x": x,
        "y": y,
        "speed": speed,
        "lap": lap,
        "lap_progress": lap_progress,
        "status": status,
    }


def test_points_table():
    assert points_for_rank(1) == 10
    assert points_for_rank(2) == 7
    assert points_for_rank(3) == 5
    assert points_for_rank(4) == 3
    assert points_for_rank(5) == 1
    assert points_for_rank(None) == 1
    assert POINTS[1] == 10


def test_load_runs_splits_on_timestamp_reset(tmp_path):
    p = tmp_path / "telemetry.jsonl"
    lines = [
        '{"t": 5.0, "cars": [], "events": []}',
        '{"t": 5.1, "cars": [], "events": []}',
        '{"t": 0.1, "cars": [], "events": []}',  # reset (>0.5s drop) -> new run
        '{"t": 0.2, "cars": [], "events": []}',
        "",  # blank line tolerated
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    runs = load_runs(p)
    assert len(runs) == 2
    assert len(runs[0]) == 2 and len(runs[1]) == 2


def test_pick_team_index_prefers_ours_then_first():
    assert pick_team_index(["oppA", "ours", "oppB"], None) == 1
    assert pick_team_index(["a", "b", "c"], None) == 0  # no 'our*' -> first
    assert pick_team_index(["a", "b", "c"], "b") == 1   # explicit
    assert pick_team_index(["alpha", "beta"], "BET") == 1  # substring, case-insensitive


def test_progress_series_uses_checkpoint_when_available():
    run = [
        _frame(0.0, [_car("ours", 0, 0, lap_progress=0.0), _car("opp", 0, 0, lap_progress=0.1)]),
        _frame(0.1, [_car("ours", 1, 0, lap_progress=0.5), _car("opp", 1, 0, lap_progress=0.2)]),
    ]
    prog, used_cp = progress_series(run, 2)
    assert used_cp is True
    assert prog[0][-1] == 0.5 and prog[1][-1] == 0.2
    # ours overtook on progress -> rank 1 at last frame
    assert rank_at(prog, 1)[0] == 1


def test_progress_series_falls_back_to_distance():
    run = [
        _frame(0.0, [_car("ours", 0, 0), _car("opp", 0, 0)]),
        _frame(0.1, [_car("ours", 10, 0), _car("opp", 1, 0)]),
    ]
    prog, used_cp = progress_series(run, 2)
    assert used_cp is False
    assert prog[0][-1] > prog[1][-1]  # ours traveled farther


def test_analyze_overtake_collision_and_squeeze():
    # ours starts leading, gets passed (conceded), suffers one major collision,
    # and is squeezed close at the start.
    run = [
        _frame(0.0, [_car("ours", 0, 0, lap_progress=0.20), _car("opp", 0, 1.0, lap_progress=0.10)],
               events=[{"type": "collision", "severity": "major", "team_ids": ["ours", "opp"]}]),
        _frame(0.1, [_car("ours", 1, 0, lap_progress=0.30), _car("opp", 1, 0, lap_progress=0.50)]),
    ]
    k = analyze(run, team_index=0, args=_Args())
    assert k["me"] == "ours"
    assert k["sev_major"] == 1
    assert k["start_rank"] == 1 and k["end_rank"] == 2
    assert k["overtakes_conceded"] >= 1
    assert k["squeezed"] is True  # opp within 1.0m at start


def test_analyze_stall_episode():
    # stalled (<0.5 m/s) for ~4s -> one stall episode
    frames = [_frame(i * 0.5, [_car("ours", 0, 0, speed=0.0)]) for i in range(9)]  # t 0..4.0
    frames.append(_frame(5.0, [_car("ours", 0, 0, speed=5.0)]))
    k = analyze(frames, team_index=0, args=_Args())
    assert k["stall_events"] == 1
    assert k["stall_total_s"] >= 3.0


def test_analyze_handles_nonfinite_speed():
    run = [
        _frame(0.0, [_car("ours", 0, 0, speed=float("nan"))]),
        _frame(0.1, [_car("ours", 1, 0, speed=5.0)]),
    ]
    k = analyze(run, team_index=0, args=_Args())
    assert k["speed_mean"] == 5.0  # nan filtered out
