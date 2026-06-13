"""脱困/倒车段分析器（本地调试用）。

功能概述：从调试构建的 control_*.jsonl 里切出"脱困段"（mode==escaping）和"疑似卡死段"
（速度持续很低但没进脱困），量化每段时长、是否真倒车、倒车后是否恢复，以及有没有
在正常驾驶里误触发倒车。供倒车脱困迭代快速判读。

用法：
  python scripts/analyze_escape_episodes.py .tmp/multicar/control_complex_car1.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_last_segment(path: Path) -> list[dict]:
    rows = []
    for line in path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    # 按时间戳回退切最后一段（去掉残留旧 run）
    seg: list[dict] = []
    last_t = None
    for r in rows:
        t = float(r.get("t", 0.0))
        if last_t is not None and t < last_t - 1e-6:
            seg = []
        seg.append(r)
        last_t = t
    return seg


def _episodes(rows: list[dict], pred) -> list[tuple[int, int]]:
    """返回满足 pred 的连续帧区间 [start_idx, end_idx]（含端点）。"""
    out = []
    i = 0
    n = len(rows)
    while i < n:
        if pred(rows[i]):
            j = i
            while j + 1 < n and pred(rows[j + 1]):
                j += 1
            out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path)
    ap.add_argument("--stuck-speed", type=float, default=0.12,
                    help="疑似卡死的速度阈值（默认 0.12）")
    ap.add_argument("--stuck-min-frames", type=int, default=20,
                    help="疑似卡死最少持续帧（默认 20，约 0.6s）")
    args = ap.parse_args()

    rows = _load_last_segment(args.path)
    n = len(rows)
    if n == 0:
        print("（空日志）")
        return
    t0, t1 = float(rows[0]["t"]), float(rows[-1]["t"])
    dt = (t1 - t0) / max(n - 1, 1)

    speeds = [float(r.get("speed", 0.0)) for r in rows]
    neg = [s for s in speeds if s < 0]
    esc_frames = [i for i, r in enumerate(rows) if r.get("mode") == "escaping"]

    print("================ 脱困/倒车段分析 ================")
    print(f"源文件   : {args.path}")
    print(f"帧数/时长: {n} 帧, t={t0:.2f}→{t1:.2f} ({t1-t0:.1f}s, dt≈{dt:.3f}s)")
    print(f"倒车帧   : {len(neg)} ({len(neg)/n*100:.1f}%)  speed_min={min(speeds):.3f}  speed_max={max(speeds):.3f}")
    print(f"escaping : {len(esc_frames)} 帧 ({len(esc_frames)/n*100:.1f}%)")

    # ── 脱困段 ──
    esc_eps = _episodes(rows, lambda r: r.get("mode") == "escaping")
    print(f"\n---- 脱困段（mode==escaping）：{len(esc_eps)} 段 ----")
    for k, (a, b) in enumerate(esc_eps):
        seg = rows[a:b + 1]
        seg_sp = speeds[a:b + 1]
        rev = [s for s in seg_sp if s < 0]
        ta, tb = float(seg[0]["t"]), float(seg[-1]["t"])
        # 进入前速度（前 5 帧均值）
        pre = speeds[max(0, a - 5):a]
        pre_sp = sum(pre) / len(pre) if pre else float("nan")
        # 退出后 2s 恢复速度（峰值）
        post_idx = [i for i in range(b + 1, n) if float(rows[i]["t"]) - tb <= 2.0]
        post_max = max((speeds[i] for i in post_idx), default=float("nan"))
        lat0 = float(seg[0].get("lateral", 0.0))
        print(f"  [{k}] t={ta:6.2f}→{tb:6.2f} ({tb-ta:4.1f}s, {len(seg)}帧)  "
              f"倒车帧={len(rev):3d}  进入前速={pre_sp:.2f}  段内min={min(seg_sp):+.2f}  "
              f"退出后2s峰值={post_max:.2f}  lateral@start={lat0:+.2f}  "
              f"{'✓恢复' if post_max==post_max and post_max>0.5 else '✗未恢复/末段'}")

    # ── 疑似卡死但没进脱困 ──
    stuck_eps = _episodes(
        rows,
        lambda r: 0.0 <= float(r.get("speed", 1.0)) < args.stuck_speed and r.get("mode") != "escaping",
    )
    stuck_eps = [(a, b) for a, b in stuck_eps if (b - a + 1) >= args.stuck_min_frames]
    print(f"\n---- 疑似卡死但未触发脱困（speed<{args.stuck_speed}, ≥{args.stuck_min_frames}帧, mode≠escaping）：{len(stuck_eps)} 段 ----")
    for k, (a, b) in enumerate(stuck_eps):
        seg = rows[a:b + 1]
        ta, tb = float(seg[0]["t"]), float(seg[-1]["t"])
        modes = {}
        for r in seg:
            modes[r.get("mode")] = modes.get(r.get("mode"), 0) + 1
        top = sorted(modes.items(), key=lambda x: -x[1])[:3]
        lat = sum(abs(float(r.get("lateral", 0.0))) for r in seg) / len(seg)
        lost_f = sum(1 for r in seg if r.get("lost"))
        print(f"  [{k}] t={ta:6.2f}→{tb:6.2f} ({tb-ta:4.1f}s, {len(seg)}帧)  "
              f"mean|lat|={lat:.2f}  lost帧={lost_f}  modes={top}")

    # ── 正常驾驶里是否出现倒车（误触发）──
    bad_rev = [i for i in range(n) if speeds[i] < 0 and rows[i].get("mode") != "escaping"]
    print(f"\n---- 误倒车检查：非 escaping 状态下的负速度帧 = {len(bad_rev)} "
          f"{'⚠ 有误触发！' if bad_rev else '✓ 无'} ----")
    if bad_rev:
        for i in bad_rev[:5]:
            print(f"    t={float(rows[i]['t']):.2f}  speed={speeds[i]:+.2f}  mode={rows[i].get('mode')}")


if __name__ == "__main__":
    main()
