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


def main() -> int:
    parser = argparse.ArgumentParser(description="汇总控制器内部调试日志。")
    parser.add_argument("log", type=Path, help="control_*.jsonl 路径")
    args = parser.parse_args()

    if not args.log.is_file():
        print(f"[error] 找不到日志: {args.log}")
        return 1
    rows = _load(args.log)
    if not rows:
        print("[error] 日志为空或无法解析")
        return 1

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
    print(f"源文件     : {args.log}")
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
    print("---- 速度-转向耦合（诊断是否被转向压速）----")
    print(f"  |steer|<0.1 均速={_mean(sp_low_steer):.3f}   |steer|>0.3 均速={_mean(sp_high_steer):.3f}")
    print(f"  |lat|<0.1   均速={_mean(sp_low_lat):.3f}   |lat|>0.3   均速={_mean(sp_high_lat):.3f}")
    print("=================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
