#!/usr/bin/env python3
"""多车赛 KPI 汇总脚本（with_other_cars 的"评价指标"层）。

功能概述：把一次多车 Webots 实跑的 `telemetry.jsonl`(+ `metadata.json`) 压成一组
    面向"名次期望积分"的可量化指标，而不是单车的 lap time。

为什么是这些指标（见仓库讨论）：多车赛真正计分的是名次（积分 10/7/5/3/1），
    且第一名完赛后只有 60s 宽限期、累计 3 次严重碰撞即取消资格。所以目标函数是
        期望积分 ≈ P(完赛且未 DQ) × 积分(名次)  +  P(DQ/未完赛) × 1
    本脚本输出它的可观测代理：完赛/名次/积分、严重碰撞数(DQ 预算)、超车净得失、
    开局互挤、卡死、速度分布。

输入：
    telemetry.jsonl —— SDK supervisor 逐帧写出的全车位姿（x,y,speed,lap,lap_progress,status）
        + 每帧 events（collision / lap_complete / car_finished / 接触）。该文件是 **append 累积**
        的，脚本按时间戳归零自动切分多次 run，默认分析最后一次。
    metadata.json   —— 同目录，含 final_rankings / finish_reason / 每车 collision_major_count。
        修好 checkpoint 之前 final_rankings 可能为空；此时名次从 telemetry 进度临时推断。

用法：
    python scripts/analyze_multicar_kpi.py /path/to/recordings/telemetry.jsonl
    python scripts/analyze_multicar_kpi.py .tmp/multicar/telemetry.jsonl --team ours
    python scripts/analyze_multicar_kpi.py telemetry.jsonl --run 8   # 指定第几段 run

注意：名次/超车 KPI 依赖赛道进度（lap + lap_progress）。SDK checkpoint 修好前的旧
    telemetry 里进度恒 0，脚本会退化用"累计行驶距离"作进度代理并在输出里标注 [proxy]。
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

# 正式积分表（TASK.md §10.4）：名次 -> 分。第 5 名及以后 / 未完赛 = 1。
POINTS = {1: 10, 2: 7, 3: 5, 4: 3}


def points_for_rank(rank: int | None) -> int:
    if rank is None:
        return 1
    return POINTS.get(rank, 1)


def load_runs(path: Path) -> list[list[dict]]:
    """读取 telemetry.jsonl 并按时间戳归零切分成多次 run。"""

    runs: list[list[dict]] = []
    cur: list[dict] = []
    last_t = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                frame = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = frame.get("t", 0.0)
            if last_t is not None and t < last_t - 0.5:
                runs.append(cur)
                cur = []
            cur.append(frame)
            last_t = t
    if cur:
        runs.append(cur)
    return runs


def pick_team_index(team_ids: list[str], requested: str | None) -> int:
    """选择"我方"车在 cars 数组里的下标。"""

    if requested:
        for i, tid in enumerate(team_ids):
            if tid == requested:
                return i
        # 容错：按子串匹配
        for i, tid in enumerate(team_ids):
            if requested.lower() in tid.lower():
                return i
    # 默认：优先 team_id 含 "our"，否则第 0 个（run_local 把 car_1 放在首位）。
    for i, tid in enumerate(team_ids):
        if "our" in tid.lower():
            return i
    return 0


def cumulative_distance(run: list[dict], ci: int) -> list[float]:
    """某辆车逐帧累计行驶距离（进度代理，用于旧 telemetry 无 lap_progress 时排名）。"""

    out = [0.0]
    for a, b in zip(run, run[1:]):
        ca, cb = a["cars"][ci], b["cars"][ci]
        out.append(out[-1] + math.hypot(cb["x"] - ca["x"], cb["y"] - ca["y"]))
    return out


def progress_series(run: list[dict], ncars: int) -> tuple[list[list[float]], bool]:
    """每辆车逐帧的赛道进度序列。

    返回 (progress[car][frame], used_checkpoint)。优先用 lap + lap_progress（修好
    checkpoint 后才有效）；若全程为 0 则退化为累计行驶距离代理。
    """

    max_lp = 0.0
    for fr in run:
        for c in fr["cars"]:
            max_lp = max(max_lp, c.get("lap", 0) + c.get("lap_progress", 0.0))
    if max_lp > 1e-6:
        prog = [[fr["cars"][ci].get("lap", 0) + fr["cars"][ci].get("lap_progress", 0.0)
                 for fr in run] for ci in range(ncars)]
        return prog, True
    # 退化：累计行驶距离
    prog = [cumulative_distance(run, ci) for ci in range(ncars)]
    return prog, False


def rank_at(progress: list[list[float]], frame_idx: int) -> list[int]:
    """给定帧，所有车按进度降序的名次（1=领先）。返回 rank[car]。"""

    order = sorted(range(len(progress)), key=lambda ci: -progress[ci][frame_idx])
    rank = [0] * len(progress)
    for pos, ci in enumerate(order):
        rank[ci] = pos + 1
    return rank


def analyze(run: list[dict], team_index: int, args) -> dict:
    team_ids = [c["team_id"] for c in run[-1]["cars"]]
    ncars = len(team_ids)
    me = team_index
    t_end = run[-1]["t"]

    # ── 速度 ──（过滤 None/NaN：个别 telemetry 帧速度可能缺失）
    speeds = [fr["cars"][me]["speed"] for fr in run]
    speeds = [v for v in speeds if v is not None and math.isfinite(v)]
    speed_mean = statistics.fmean(speeds) if speeds else 0.0
    speed_median = statistics.median(speeds) if speeds else 0.0

    # ── 卡死 episode：连续 speed < 阈值 超过 N 秒 ──
    stall_events = 0
    stall_total_s = 0.0
    run_start_t = run[0]["t"]
    seg_start = None
    prev_t = run_start_t
    for fr in run:
        v = fr["cars"][me]["speed"]
        t = fr["t"]
        if v < args.stall_speed:
            if seg_start is None:
                seg_start = t
        else:
            if seg_start is not None and t - seg_start >= args.stall_seconds:
                stall_events += 1
                stall_total_s += t - seg_start
            seg_start = None
        prev_t = t
    if seg_start is not None and prev_t - seg_start >= args.stall_seconds:
        stall_events += 1
        stall_total_s += prev_t - seg_start

    # ── 进度 / 名次随时间 ──
    progress, used_cp = progress_series(run, ncars)
    start_rank = rank_at(progress, 0)[me]
    end_rank = rank_at(progress, len(run) - 1)[me]
    # 超车净得失：扫描我方名次变化，改善=超车成功，恶化=被超
    overtakes_made = 0
    overtakes_conceded = 0
    prev_rank = start_rank
    for fi in range(1, len(run)):
        r = rank_at(progress, fi)[me]
        if r < prev_rank:
            overtakes_made += prev_rank - r
        elif r > prev_rank:
            overtakes_conceded += r - prev_rank
        prev_rank = r

    # ── 事件：碰撞（涉及我方）、完赛、DQ ──
    sev_major = 0
    sev_minor = 0
    contact_starts = 0
    finished = False
    dq = False
    for fr in run:
        for e in fr.get("events", []):
            et = e.get("type")
            tids = e.get("team_ids") or ([e.get("team_id")] if e.get("team_id") else [])
            involves_me = team_ids[me] in tids
            if et == "collision" and involves_me:
                if e.get("severity") == "major":
                    sev_major += 1
                else:
                    sev_minor += 1
            elif et == "contact_start" and (involves_me or e.get("team_id") is None):
                contact_starts += 1
            elif et == "car_finished" and involves_me:
                finished = True
            elif et in ("disqualified", "car_disqualified") and involves_me:
                dq = True

    # ── 开局互挤：start_window 内我方到最近他车的最小中心距 + 期间碰撞/接触 ──
    squeeze_min_dist = math.inf
    squeeze_collisions = 0
    for fr in run:
        if fr["t"] - run_start_t > args.start_window:
            break
        mx, my = fr["cars"][me]["x"], fr["cars"][me]["y"]
        for ci in range(ncars):
            if ci == me:
                continue
            ox, oy = fr["cars"][ci]["x"], fr["cars"][ci]["y"]
            squeeze_min_dist = min(squeeze_min_dist, math.hypot(ox - mx, oy - my))
        for e in fr.get("events", []):
            if e.get("type") == "collision" and team_ids[me] in (e.get("team_ids") or []):
                squeeze_collisions += 1
    squeezed = squeeze_min_dist < args.squeeze_dist or squeeze_collisions > 0

    return {
        "team_ids": team_ids,
        "me": team_ids[me],
        "ncars": ncars,
        "t_end": t_end,
        "speed_mean": speed_mean,
        "speed_median": speed_median,
        "stall_events": stall_events,
        "stall_total_s": stall_total_s,
        "used_cp": used_cp,
        "max_progress": max(progress[me]) if used_cp else None,
        "start_rank": start_rank,
        "end_rank": end_rank,
        "overtakes_made": overtakes_made,
        "overtakes_conceded": overtakes_conceded,
        "sev_major": sev_major,
        "sev_minor": sev_minor,
        "contact_starts": contact_starts,
        "finished": finished,
        "dq": dq,
        "squeeze_min_dist": squeeze_min_dist,
        "squeeze_collisions": squeeze_collisions,
        "squeezed": squeezed,
    }


def load_metadata(path: Path | None, my_team: str) -> dict | None:
    """从 metadata.json 读官方名次/积分/严重碰撞（修好 checkpoint 后才会非空）。"""

    if path is None or not path.exists():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    rankings = meta.get("final_rankings") or []
    mine = next((r for r in rankings if r.get("team_id") == my_team), None)
    return {
        "finish_reason": meta.get("finish_reason"),
        "n_ranked": len(rankings),
        "my_rank": mine.get("rank") if mine else None,
        "my_laps": mine.get("laps") if mine else None,
        "my_best_lap": mine.get("best_lap") if mine else None,
        "my_total_time": mine.get("total_time") if mine else None,
        "my_major": mine.get("collision_major_count") if mine else None,
        "my_status": mine.get("status") if mine else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="多车赛 KPI 汇总")
    parser.add_argument("telemetry", type=Path, help="telemetry.jsonl 路径")
    parser.add_argument("--metadata", type=Path, default=None,
                        help="metadata.json 路径（默认 telemetry 同目录）")
    parser.add_argument("--team", default=None, help="我方 team_id（默认自动找 'our*' 或第 0 辆）")
    parser.add_argument("--run", default="last", help="分析第几段 run（整数或 'last'，默认 last）")
    parser.add_argument("--stall-speed", type=float, default=0.5, help="卡死速度阈值 m/s")
    parser.add_argument("--stall-seconds", type=float, default=3.0, help="卡死最短持续秒数")
    parser.add_argument("--start-window", type=float, default=5.0, help="开局互挤观察窗口秒数")
    parser.add_argument("--squeeze-dist", type=float, default=3.0, help="判定互挤的最近中心距 m")
    args = parser.parse_args()

    runs = load_runs(args.telemetry)
    if not runs:
        print("没有可用的 telemetry 帧。")
        return
    if args.run == "last":
        ridx = len(runs) - 1
    else:
        ridx = int(args.run)
        if ridx < 0:
            ridx += len(runs)
    if not (0 <= ridx < len(runs)):
        print(f"run 下标越界：共有 {len(runs)} 段 run。")
        return
    run = runs[ridx]

    team_ids = [c["team_id"] for c in run[-1]["cars"]]
    me = pick_team_index(team_ids, args.team)
    k = analyze(run, me, args)

    meta_path = args.metadata
    if meta_path is None:
        meta_path = args.telemetry.with_name("metadata.json")
    meta = load_metadata(meta_path, k["me"])

    # 名次/积分：优先官方 metadata，否则用本段 run 末进度临时推断
    if meta and meta["my_rank"] is not None:
        rank = meta["my_rank"]
        rank_src = "metadata(official)"
    else:
        rank = k["end_rank"]
        rank_src = "telemetry-progress[proxy]" if not k["used_cp"] else "telemetry-progress"
    pts = points_for_rank(rank)
    sev_major = meta["my_major"] if (meta and meta["my_major"] is not None) else k["sev_major"]

    print("=" * 60)
    print(f"多车 KPI  run#{ridx}/{len(runs)-1}  team={k['me']}  cars={k['ncars']}  t_end={k['t_end']:.0f}s")
    print(f"  对手: {[t for t in team_ids if t != k['me']]}")
    print("-" * 60)
    print(f"[名次/积分]  rank={rank}  →  points={pts}   ({rank_src})")
    if meta:
        print(f"             finish_reason={meta['finish_reason']}  ranked={meta['n_ranked']}  "
              f"laps={meta['my_laps']}  best_lap={meta['my_best_lap']}  total_time={meta['my_total_time']}")
    finished = (meta and meta["my_status"] == "finished") or k["finished"]
    print(f"[完赛]       finished={finished}  DQ={k['dq']}   (DQ 悬崖=3 次严重碰撞)")
    print(f"[严重碰撞]   major={sev_major}/2 预算   minor={k['sev_minor']}   本车身接触段={k['contact_starts']}")
    if k["used_cp"]:
        print(f"[进度]       max_progress={k['max_progress']:.2f} 圈")
    else:
        print(f"[进度]       lap_progress 全 0（checkpoint 未生效）→ 名次用行驶距离代理")
    print(f"[超车净值]   made={k['overtakes_made']}  conceded={k['overtakes_conceded']}  "
          f"net={k['overtakes_made'] - k['overtakes_conceded']}   (start_rank={k['start_rank']}→end={k['end_rank']})")
    sd = k["squeeze_min_dist"]
    print(f"[开局互挤]   squeezed={k['squeezed']}  最近他车距={sd:.2f}m  开局碰撞={k['squeeze_collisions']}  "
          f"(窗口 {args.start_window:.0f}s)")
    print(f"[卡死]       episodes={k['stall_events']}  累计={k['stall_total_s']:.1f}s  (<{args.stall_speed} m/s 持续 {args.stall_seconds:.0f}s)")
    print(f"[速度]       mean={k['speed_mean']:.2f}  median={k['speed_median']:.2f} m/s")
    print("=" * 60)


if __name__ == "__main__":
    main()
