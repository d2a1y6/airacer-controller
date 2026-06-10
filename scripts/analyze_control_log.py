"""控制器内部日志汇总脚本（本地调试用）。

功能概述：把调试构建写出的逐帧 `control_*.jsonl` 压成约 35 行汇总。
输入输出：输入控制日志 JSONL，输出转向震荡、速度、横向偏置、各 mode 占比、速度-转向耦合。
处理流程：解析逐帧内部状态与发出命令 → 统计震荡频率/偏置/耦合 → 可选 join 遥测定位爬行点。
设计目的：回答"为什么慢/为什么左右磨/内侧偏多少"，且只打印聚合结果，token 成本极低。

日志由 `python scripts/build_submission.py --mode fastest --debug-log <PATH> --out <调试单文件>` 产生。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

DEBUG_FLAG_BITS = [
    (1, "有效扫描线过少"),
    (2, "用了边缘fallback"),
    (4, "mask填充率极端"),
    (8, "左右近处中心偏差大"),
    (16, "左右置信度接近"),
    (32, "红色环境"),
]


def _load(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _pct(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(q * (len(ordered) - 1)))))
    return ordered[idx]


def _split_runs(rows: list[dict]) -> list[list[dict]]:
    """按时间戳回退切分控制日志。

    功能：避免同一个 JSONL 里残留多次 run 时污染统计。
    参数：`rows` 是按文件顺序解析出的控制日志。
    返回：按 `t` 单调递增切出的 run 列表。
    逻辑：遇到当前 `t` 小于上一帧 `t` 时切段，调用方默认取最后一段。
    """

    segments: list[list[dict]] = []
    current: list[dict] = []
    last_t = None
    for row in rows:
        try:
            t = float(row.get("t", 0.0))
        except (TypeError, ValueError):
            t = 0.0
        if last_t is not None and t < last_t - 1e-6:
            if current:
                segments.append(current)
            current = []
        current.append(row)
        last_t = t
    if current:
        segments.append(current)
    return segments


def decode_debug_flags(flags: int) -> list[str]:
    """解码 perception / estimator 写入的 debug_flags 位。

    功能：把整数位图转成人能读的诊断标签。
    参数：`flags` 是日志中的 debug_flags 整数。
    返回：命中的中文标签列表，未知位保留为 `未知位<N>`。
    逻辑：先按已知位逐个匹配，再把剩余未知位逐位展开。
    """

    labels = [label for bit, label in DEBUG_FLAG_BITS if flags & bit]
    known_mask = 0
    for bit, _label in DEBUG_FLAG_BITS:
        known_mask |= bit
    unknown = flags & ~known_mask
    bit = 1
    while unknown:
        if unknown & bit:
            labels.append(f"未知位{bit}")
            unknown &= ~bit
        bit <<= 1
    return labels


def _numeric(rows: list[dict], field: str, absolute: bool = False) -> list[float]:
    values = []
    for row in rows:
        try:
            value = float(row.get(field, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        values.append(abs(value) if absolute else value)
    return values


def _value_stats(rows: list[dict], field: str) -> dict[str, float]:
    values = _numeric(rows, field)
    return {
        "mean": _mean(values),
        "median": _pct(values, 0.5),
        "p10": _pct(values, 0.1),
        "p90": _pct(values, 0.9),
    }


def _lost_segments(rows: list[dict]) -> list[int]:
    """统计连续 lost 段长度。

    功能：把逐帧 lost 布尔值压成连续段长度。
    参数：`rows` 是控制日志行。
    返回：每个 lost 段的帧数。
    逻辑：遇到 lost=True 累加，离开 lost 时结算当前段。
    """

    segments: list[int] = []
    current = 0
    for row in rows:
        if row.get("lost"):
            current += 1
        elif current:
            segments.append(current)
            current = 0
    if current:
        segments.append(current)
    return segments


def collect_lost_diagnostics(rows: list[dict]) -> dict:
    """汇总 lost 帧的离线诊断指标。

    功能：统计丢线占比、连续段、置信度/点数/宽度分布、flag 频率和弯道关联。
    参数：`rows` 是控制日志 JSONL 解析后的记录。
    返回：可打印也可单测断言的诊断字典。
    逻辑：只对 lost 帧做细分，同时保留 lost 与非 lost 的几何均值对比。
    """

    n = len(rows)
    lost_rows = [row for row in rows if row.get("lost")]
    non_lost_rows = [row for row in rows if not row.get("lost")]
    segments = _lost_segments(rows)

    flag_counter: Counter[int] = Counter()
    for row in lost_rows:
        flags = int(row.get("debug_flags", 0) or 0)
        for bit, _label in DEBUG_FLAG_BITS:
            if flags & bit:
                flag_counter[bit] += 1
        unknown = flags & ~sum(bit for bit, _label in DEBUG_FLAG_BITS)
        bit = 1
        while unknown:
            if unknown & bit:
                flag_counter[bit] += 1
                unknown &= ~bit
            bit <<= 1

    entry_prev_modes: Counter[str] = Counter()
    for index, row in enumerate(rows):
        if not row.get("lost"):
            continue
        if index > 0 and rows[index - 1].get("lost"):
            continue
        prev_mode = "<start>" if index == 0 else str(rows[index - 1].get("mode", "?"))
        entry_prev_modes[prev_mode] += 1

    return {
        "frames": n,
        "lost_frames": len(lost_rows),
        "lost_frac": len(lost_rows) / n if n else 0.0,
        "segments": segments,
        "segment_stats": {
            "count": len(segments),
            "max": max(segments) if segments else 0,
            "mean": _mean([float(v) for v in segments]),
            "median": _pct([float(v) for v in segments], 0.5),
            "p90": _pct([float(v) for v in segments], 0.9),
        },
        "lost_value_stats": {
            field: _value_stats(lost_rows, field)
            for field in ("track_conf", "obs_conf", "obs_points", "road_width")
        },
        "flag_counter": flag_counter,
        "entry_prev_modes": entry_prev_modes,
        "curvature_abs_mean": {
            "lost": _mean(_numeric(lost_rows, "curvature", absolute=True)),
            "non_lost": _mean(_numeric(non_lost_rows, "curvature", absolute=True)),
        },
        "heading_abs_mean": {
            "lost": _mean(_numeric(lost_rows, "heading", absolute=True)),
            "non_lost": _mean(_numeric(non_lost_rows, "heading", absolute=True)),
        },
    }


def print_lost_diagnostics(rows: list[dict]) -> None:
    """打印紧凑的丢线诊断段。"""

    diag = collect_lost_diagnostics(rows)
    lost_n = diag["lost_frames"]
    seg = diag["segment_stats"]
    print("---- 丢线诊断 ----")
    print(f"  lost 帧={lost_n}/{diag['frames']} ({diag['lost_frac']:.2f})  "
          f"连续段={seg['count']}  最长={seg['max']}帧  "
          f"段长 median={seg['median']:.0f} p90={seg['p90']:.0f} mean={seg['mean']:.1f}")
    if not lost_n:
        print("  （无 lost 帧）")
        return
    for field, label in (
        ("track_conf", "track_conf"),
        ("obs_conf", "obs_conf"),
        ("obs_points", "obs_points"),
        ("road_width", "road_width"),
    ):
        stats = diag["lost_value_stats"][field]
        print(f"  lost {label}: mean={stats['mean']:.3f} median={stats['median']:.3f} "
              f"p10={stats['p10']:.3f} p90={stats['p90']:.3f}")
    print("  debug_flags: " + "  ".join(
        f"{decode_debug_flags(bit)[0]}={count/lost_n:.2f}({count})"
        for bit, count in diag["flag_counter"].most_common()
    ))
    print("  进入 lost 前 mode: " + "  ".join(
        f"{mode}={count/seg['count']:.2f}({count})"
        for mode, count in diag["entry_prev_modes"].most_common()
    ))
    print(f"  |curvature| mean: lost={diag['curvature_abs_mean']['lost']:.3f}  "
          f"non_lost={diag['curvature_abs_mean']['non_lost']:.3f}")
    print(f"  |heading|   mean: lost={diag['heading_abs_mean']['lost']:.3f}  "
          f"non_lost={diag['heading_abs_mean']['non_lost']:.3f}")


def _print_summary(path: Path, rows: list[dict], integrity: str | None = None) -> None:
    """打印单段控制日志汇总。"""

    n = len(rows)
    t0, t1 = rows[0].get("t", 0.0), rows[-1].get("t", 0.0)
    span = max(t1 - t0, 1e-6)

    steering = [float(r.get("steering", 0.0)) for r in rows]
    speed = [float(r.get("speed", 0.0)) for r in rows]
    lateral = [float(r.get("lateral", 0.0)) for r in rows]
    heading = [float(r.get("heading", 0.0)) for r in rows]
    curvature = [float(r.get("curvature", 0.0)) for r in rows]

    # 转向震荡：符号翻转次数/秒，逐帧 |Δsteering| 的累计/秒
    sign_changes = 0
    abs_dsteer_sum = 0.0
    for i in range(1, n):
        a, b = steering[i - 1], steering[i]
        if a * b < 0 and abs(a) > 0.05 and abs(b) > 0.05:
            sign_changes += 1
        abs_dsteer_sum += abs(b - a)
    osc_per_sec = sign_changes / span
    dsteer_per_sec = abs_dsteer_sum / span

    frac = lambda vals, pred: sum(1 for v in vals if pred(v)) / n
    lost_frac = sum(1 for r in rows if r.get("lost")) / n
    modes = Counter(r.get("mode", "?") for r in rows)

    # 速度-转向 / 速度-偏移 耦合：转向小 vs 大时的均速
    sp_low_steer = [speed[i] for i in range(n) if abs(steering[i]) < 0.1]
    sp_high_steer = [speed[i] for i in range(n) if abs(steering[i]) > 0.3]
    sp_low_lat = [speed[i] for i in range(n) if abs(lateral[i]) < 0.1]
    sp_high_lat = [speed[i] for i in range(n) if abs(lateral[i]) > 0.3]

    print("================ CONTROL 日志汇总 ================")
    print(f"源文件     : {path}")
    if integrity:
        print(f"完整性     : {integrity}")
    print(f"帧数/时长  : {n} 帧, t={t0:.2f}→{t1:.2f} ({span:.1f}s)")
    print("---- 转向（震荡诊断）----")
    print(f"  mean(signed)={_mean(steering):+.3f}  mean|steer|={_mean([abs(s) for s in steering]):.3f}  "
          f"p95|steer|={_pct([abs(s) for s in steering],0.95):.3f}")
    print(f"  换向频率={osc_per_sec:.2f} 次/秒   累计|Δsteer|={dsteer_per_sec:.2f} /秒")
    print(f"  （换向频率高=左右磨；理想是低频、长段同号）")
    print("---- 速度 ----")
    print(f"  mean={_mean(speed):.3f}  median={_pct(speed,0.5):.3f}  p95={_pct(speed,0.95):.3f}  "
          f"max={max(speed):.3f}")
    print(f"  低速占比: <0.5={frac(speed, lambda v: v<0.5):.2f}  <0.3={frac(speed, lambda v: v<0.3):.2f}")
    print("---- 横向偏置（内/外侧偏移）----")
    print(f"  mean(signed)={_mean(lateral):+.3f}  (左负右正; 持续非零=系统性贴一侧)")
    print(f"  mean|lat|={_mean([abs(v) for v in lateral]):.3f}  "
          f"|lat|>0.3 占比={frac(lateral, lambda v: abs(v)>0.3):.2f}")
    print(f"  mean|heading|={_mean([abs(v) for v in heading]):.3f}  "
          f"mean|curv|={_mean([abs(v) for v in curvature]):.3f}")
    print("---- 状态 ----")
    print(f"  lost 占比={lost_frac:.2f}")
    print(f"  mode 占比: " + "  ".join(f"{m}={c/n:.2f}" for m, c in modes.most_common()))
    print_lost_diagnostics(rows)
    print("---- 速度-转向耦合（诊断是否被转向压速）----")
    print(f"  |steer|<0.1 均速={_mean(sp_low_steer):.3f}   |steer|>0.3 均速={_mean(sp_high_steer):.3f}")
    print(f"  |lat|<0.1   均速={_mean(sp_low_lat):.3f}   |lat|>0.3   均速={_mean(sp_high_lat):.3f}")
    print("=================================================")


def _expand_inputs(paths: list[Path]) -> tuple[list[Path], list[str]]:
    """把命令行输入展开成日志文件列表。"""

    files: list[Path] = []
    errors: list[str] = []
    for path in paths:
        if path.is_dir():
            found = sorted(p for p in path.glob("control*.jsonl") if p.is_file())
            if not found:
                found = sorted(p for p in path.glob("*.jsonl") if p.is_file())
            if not found:
                errors.append(f"[error] 目录内没有 JSONL 日志: {path}")
            files.extend(found)
        elif path.is_file():
            files.append(path)
        else:
            errors.append(f"[error] 找不到日志: {path}")
    return files, errors


def analyze_file(path: Path) -> int:
    """读取并汇总一个控制日志文件。"""

    rows = _load(path)
    if not rows:
        print(f"[error] 日志为空或无法解析: {path}")
        return 1

    runs = _split_runs(rows)
    active_rows = runs[-1]
    integrity = None
    if len(runs) > 1:
        integrity = f"interleaved（检测到 {len(runs)} 段 run，仅用最后一段）"
    _print_summary(path, active_rows, integrity=integrity)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总控制器内部调试日志。")
    parser.add_argument("logs", nargs="+", type=Path, help="control_*.jsonl 路径，可传多个文件或一个目录")
    args = parser.parse_args()

    files, errors = _expand_inputs(args.logs)
    for error in errors:
        print(error)
    if not files:
        return 1

    status = 0
    for index, path in enumerate(files):
        if index:
            print()
        status = max(status, analyze_file(path))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
