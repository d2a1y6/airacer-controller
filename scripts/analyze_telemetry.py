"""Supervisor 遥测汇总脚本（本地调试用）。

功能概述：把 supervisor 写出的大体量 `telemetry.jsonl` 压成约 40 行可读汇总。
输入输出：输入 `telemetry.jsonl`（默认读 SDK 的 `.local/recordings/`），输出位置/速度/爬行/事件统计。
处理流程：流式解析每帧 → 取目标车 → 统计速度分布、低速爬行段、近停点、事件 → 可选归档到 repo。
设计目的：原始文件可达十几万行，绝不整体读入上下文；本脚本只打印聚合结果，token 成本极低。
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SDK_DEFAULT = Path("/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings")
DEFAULT_TELEMETRY = SDK_DEFAULT / "telemetry.jsonl"
ARCHIVE_ROOT = ROOT / ".tmp" / "recordings"


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _load_car_frames(path: Path, team_id: str | None) -> tuple[list[dict], list[tuple[float, dict]]]:
    """流式读取遥测，返回目标车的逐帧记录与全部事件。"""

    frames: list[dict] = []
    events: list[tuple[float, dict]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            t = rec.get("t")
            cars = rec.get("cars") or []
            for ev in rec.get("events") or []:
                events.append((t, ev))
            car = None
            if team_id is None:
                car = cars[0] if cars else None
            else:
                for candidate in cars:
                    if candidate.get("team_id") == team_id:
                        car = candidate
                        break
            if car is None:
                continue
            x, y, speed = car.get("x"), car.get("y"), car.get("speed")
            if x is None or y is None or speed is None:
                continue
            if any(math.isnan(v) for v in (float(x), float(y), float(speed))):
                continue
            frames.append({
                "t": float(t),
                "x": float(x),
                "y": float(y),
                "speed": float(speed),
                "lap": car.get("lap", 0),
                "lap_progress": float(car.get("lap_progress", 0.0)),
                "status": car.get("status", "normal"),
            })
    return frames, events


def _split_runs(frames: list[dict]) -> list[list[dict]]:
    """按时间戳回退把交错的遥测切成多段 run。

    功能：supervisor 的 telemetry.jsonl 可能累积多次 run（孤儿进程/未截断），导致 t 非单调。
    参数：`frames` 是按文件顺序的逐帧记录。
    返回：每段为一次 run（t 单调递增）；最后一段即最近一次 run。
    逻辑：遇到 t 比上一帧小就切段。
    """

    segments: list[list[dict]] = []
    current: list[dict] = []
    last_t = None
    for fr in frames:
        if last_t is not None and fr["t"] < last_t - 1e-6:
            if current:
                segments.append(current)
            current = []
        current.append(fr)
        last_t = fr["t"]
    if current:
        segments.append(current)
    return segments


def _read_metadata_frames(telemetry_path: Path) -> int | None:
    """读取同目录 metadata.json 的 total_frames，用于完整性交叉校验。"""

    meta = telemetry_path.parent / "metadata.json"
    if not meta.is_file():
        return None
    try:
        return int(json.loads(meta.read_text(encoding="utf-8")).get("total_frames"))
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def _longest_low_speed(frames: list[dict], thresh: float) -> dict | None:
    """找最长的连续低速（<thresh）爬行段。"""

    best = None
    run_start = None
    for i, fr in enumerate(frames):
        if fr["speed"] < thresh:
            if run_start is None:
                run_start = i
        else:
            if run_start is not None:
                best = _take_longer(best, frames, run_start, i - 1)
                run_start = None
    if run_start is not None:
        best = _take_longer(best, frames, run_start, len(frames) - 1)
    return best


def _take_longer(best, frames, i0, i1):
    dur = frames[i1]["t"] - frames[i0]["t"]
    if best is None or dur > best["dur"]:
        return {
            "dur": dur,
            "t0": frames[i0]["t"], "t1": frames[i1]["t"],
            "x0": frames[i0]["x"], "y0": frames[i0]["y"],
            "x1": frames[i1]["x"], "y1": frames[i1]["y"],
        }
    return best


def _archive(src_dir: Path, label: str) -> Path:
    dest = ARCHIVE_ROOT / label
    dest.mkdir(parents=True, exist_ok=True)
    for name in ("telemetry.jsonl", "metadata.json", "live_view.jpg"):
        src = src_dir / name
        if src.exists():
            shutil.copy2(src, dest / name)
    return dest


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总 supervisor telemetry.jsonl。")
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY,
                        help=f"telemetry.jsonl 路径（默认 {DEFAULT_TELEMETRY}）")
    parser.add_argument("--team-id", default=None, help="目标车 team_id（默认取每帧第一辆车）")
    parser.add_argument("--archive", default=None,
                        help="归档标签：把本次原始遥测复制到 .tmp/recordings/<标签>/ 留档")
    parser.add_argument("--no-archive", action="store_true", help="不自动归档")
    args = parser.parse_args()

    path = args.telemetry
    if not path.is_file():
        print(f"[error] 找不到遥测文件: {path}")
        return 1

    all_frames, events = _load_car_frames(path, args.team_id)
    if not all_frames:
        print(f"[error] 未解析到任何车辆帧（team_id={args.team_id}）")
        return 1

    # 完整性：telemetry.jsonl 可能跨 run 残留，只取最近一段，并与 metadata 交叉校验。
    runs = _split_runs(all_frames)
    frames = runs[-1]
    meta_frames = _read_metadata_frames(path)
    integrity = "clean"
    if len(runs) > 1:
        integrity = f"interleaved（检测到 {len(runs)} 段 run，仅用最后一段）"
    elif meta_frames is not None and abs(len(frames) - meta_frames) > 2:
        integrity = f"suspect（本段 {len(frames)} 帧 vs metadata.total_frames {meta_frames}）"

    speeds = [f["speed"] for f in frames]
    moving = [s for s in speeds if s > 0.05]
    dist = sum(
        math.hypot(frames[i]["x"] - frames[i - 1]["x"], frames[i]["y"] - frames[i - 1]["y"])
        for i in range(1, len(frames))
    )
    t0, t1 = frames[0]["t"], frames[-1]["t"]
    span = t1 - t0
    n = len(frames)
    frac_lt = lambda th: sum(1 for s in speeds if s < th) / n

    # 时间分桶速度剖面（10 段）
    bins = 10
    profile = []
    for b in range(bins):
        lo = t0 + span * b / bins
        hi = t0 + span * (b + 1) / bins
        seg = [f["speed"] for f in frames if lo <= f["t"] < hi] or [0.0]
        profile.append(sum(seg) / len(seg))

    end = frames[-1]
    max_progress = max(f["lap_progress"] for f in frames)
    max_lap = max(f["lap"] for f in frames)

    archive_dir = None
    if not args.no_archive:
        label = args.archive or datetime.now().strftime("run_%Y%m%d_%H%M%S")
        archive_dir = _archive(path.parent, label)

    print("================ TELEMETRY 汇总 ================")
    print(f"源文件     : {path}")
    if archive_dir:
        print(f"已归档     : {archive_dir}")
    print(f"完整性     : {integrity}"
          + (f"  (metadata.total_frames={meta_frames})" if meta_frames is not None else ""))
    print(f"帧数/时长  : {n} 帧, t={t0:.2f}→{t1:.2f} ({span:.1f}s)")
    print(f"行驶距离   : {dist:.1f} (单位 = world 坐标)")
    print(f"终点       : x={end['x']:.2f}, y={end['y']:.2f}, speed={end['speed']:.3f}, status={end['status']}")
    print(f"圈数/进度  : lap={max_lap}, max_lap_progress={max_progress:.3f}")
    p95_speed = _pct(speeds, 0.95)
    rel_thresh = 0.15 * p95_speed
    rel_frac = sum(1 for s in speeds if s < rel_thresh) / n
    print("---- 速度 (supervisor 单位, 非 0~1 命令值) ----")
    print(f"  mean={sum(speeds)/n:.3f}  median={_pct(speeds,0.5):.3f}  "
          f"p95={p95_speed:.3f}  max={max(speeds):.3f}")
    print(f"  行进中均速(>0.05)={sum(moving)/len(moving) if moving else 0:.3f}")
    print(f"  近停占比: <0.3={frac_lt(0.3):.2f}  <0.05={frac_lt(0.05):.2f}   "
          f"相对爬行(<15%p95={rel_thresh:.2f})={rel_frac:.2f}")
    print(f"  速度剖面(10段均速): {' '.join(f'{v:.2f}' for v in profile)}")
    crawl = _longest_low_speed(frames, 0.3)
    if crawl and crawl["dur"] > 1.0:
        print(f"  最长爬行段(<0.3): {crawl['dur']:.1f}s  "
              f"t={crawl['t0']:.1f}→{crawl['t1']:.1f}  "
              f"x={crawl['x0']:.1f},y={crawl['y0']:.1f} → x={crawl['x1']:.1f},y={crawl['y1']:.1f}")
    print("---- 事件 ----")
    if events:
        for t, ev in events[:20]:
            print(f"  t={t}: {ev}")
        if len(events) > 20:
            print(f"  ... 共 {len(events)} 条事件")
    else:
        print("  （无 checkpoint/碰撞等事件）")
    print("================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
