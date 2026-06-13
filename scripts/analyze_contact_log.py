#!/usr/bin/env python3
"""汇总结构化撞栏接触日志（由 SDK supervisor 在 AIRACER_CONTACT_LOG=1 时写出）。

接触日志只在车身接触点高于轮子簇 0.25m 时记录（即栏杆/车身接触，已排除轮子-地面和
CarPhoenix 的底盘伪接触）。本脚本把逐帧接触合并成 episode，给出时间、位置、峰值接触点数
和最大高度，方便快速判断"在哪、撞没撞、多重"。

用法：
    python scripts/analyze_contact_log.py .tmp/run/contact_complex.jsonl
    python scripts/analyze_contact_log.py .tmp/run/contact_complex.jsonl --window 224 231
"""

import argparse
import json


def load(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def episodes(rows, gap=0.3):
    if not rows:
        return []
    out, cur = [], [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if b["t"] - a["t"] > gap:
            out.append(cur)
            cur = [b]
        else:
            cur.append(b)
    out.append(cur)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="contact_<world>.jsonl 路径")
    ap.add_argument("--window", nargs=2, type=float, metavar=("START", "END"),
                    help="只看该时间窗")
    ap.add_argument("--gap", type=float, default=0.3, help="episode 合并的最大时间间隔（秒）")
    ap.add_argument("--car-slot", default="car_1",
                    help="多车日志里只看该车位的接触（默认 car_1）；传 all 看全部车")
    args = ap.parse_args()

    rows = load(args.path)
    # 多车 contact 日志记录所有车的接触（每行带 car_slot）。默认只看本车 car_1，
    # 否则会把对手车卡栏杆误当成本车撞栏（缺 car_slot 字段的旧单车日志全保留）。
    if args.car_slot != "all":
        rows = [r for r in rows if r.get("car_slot", args.car_slot) == args.car_slot]
    if args.window:
        lo, hi = args.window
        rows = [r for r in rows if lo <= r["t"] <= hi]

    print(f"================ 撞栏接触汇总 ================")
    print(f"源文件   : {args.path}")
    print(f"接触帧   : {len(rows)}")
    if not rows:
        print("（无接触帧 → 该窗口内未记录车身/栏杆接触）")
        return

    eps = episodes(rows, args.gap)
    print(f"episode  : {len(eps)}")
    print(f"{'t_start':>8} {'t_end':>7} {'帧':>4} {'峰值点':>5} {'类型':>14}  {'pos(x,y)':>16}  {'zmax':>5}")
    for e in eps:
        zmax = max((p[2] for r in e for p in r.get("points", []) if len(p) >= 3), default=0.0)
        peak = max((r.get("count", 0) for r in e), default=0)
        kinds = {r.get("kind") for r in e}
        kind = "car_car" if "car_car" in kinds else "static_geometry"
        mid = e[len(e) // 2]
        print(f"{e[0]['t']:>8.1f} {e[-1]['t']:>7.1f} {len(e):>4} {peak:>5} {kind:>14}  "
              f"({mid['x']:>6.1f},{mid['y']:>6.1f})  {zmax:>5.2f}")
    print("=" * 46)
    print("提示：峰值点数大(>=3)且 zmax 高(>0.6) = 实打实撞栏；"
          "孤立 1-2 点、zmax≈0.49 多半是发车点底盘伪接触。")


if __name__ == "__main__":
    main()
