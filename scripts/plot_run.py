"""整场轨迹 / 速度 / 事件 / 撞栏接触可视化工具（本地报告用）。

功能概述：把一次真实 run 的 supervisor `telemetry.jsonl` 画成两张图——顶视轨迹（按速度着色）
    和速度-时间曲线，并标注起终点、最长爬行段、状态异常、事件和可选的撞栏接触点。
输入输出：输入 `telemetry.jsonl`（默认读 SDK 的 `.local/recordings/`）和可选 `contact_*.jsonl`，
    输出单张 PNG。
处理流程：复用 `analyze_telemetry` 的流式解析与跨 run 切段 → 取最近一段 → 渲染两栏图 → 存盘。
设计目的：替代过去每次手写 matplotlib 的临时做法，让"每时刻轨迹和速度、碰撞情况的图"
    成为可复现、可放进 `experiments/figures/` 的固定产物。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # 无显示环境也能出图
import matplotlib.pyplot as plt
from matplotlib import font_manager


def _setup_cjk_font() -> None:
    """尽量启用一个能显示中文的字体，避免标签变成豆腐块。

    逻辑：从常见 macOS CJK 字体里挑第一个已安装的设为默认；都没有就保持默认字体
        （中文会显示为方块，但不影响出图）。同时关掉 unicode 负号避免显示异常。
    """

    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in ("Arial Unicode MS", "STHeiti", "Hiragino Sans GB", "Songti SC", "PingFang SC"):
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


_setup_cjk_font()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.analyze_telemetry import (
    DEFAULT_TELEMETRY,
    _load_car_frames,
    _longest_low_speed,
    _split_runs,
)

DEFAULT_CONTACT_GAP = 0.3
DEFAULT_CONTACT_MERGE_DISTANCE = 4.0


def _status_segments(frames: list[dict]) -> list[tuple[float, float, str]]:
    """把连续的非 normal 状态聚成 (t0, t1, status) 区间，用于标注碰撞/卡住。"""

    segments: list[tuple[float, float, str]] = []
    start = None
    cur_status = None
    for fr in frames:
        status = fr.get("status", "normal")
        if status != "normal":
            if start is None:
                start = fr["t"]
                cur_status = status
        else:
            if start is not None:
                segments.append((start, fr["t"], cur_status or "abnormal"))
                start = None
    if start is not None:
        segments.append((start, frames[-1]["t"], cur_status or "abnormal"))
    return segments


def _lap_marks(frames: list[dict]) -> list[tuple[float, float, float, int]]:
    """返回每次 lap 增加的 (t, x, y, lap)。"""

    marks = []
    last_lap = frames[0].get("lap", 0)
    for fr in frames:
        lap = fr.get("lap", 0)
        if lap > last_lap:
            marks.append((fr["t"], fr["x"], fr["y"], lap))
            last_lap = lap
    return marks


def _load_contact_rows(path: Path, team_id: str | None = None) -> list[dict]:
    """读取结构化接触日志。

    功能：解析 `contact_*.jsonl`，并按 `team_id` 过滤。
    参数：`path` 是接触日志路径；`team_id` 为空时保留全部车辆。
    返回：按时间排序的接触帧字典列表。
    逻辑：跳过空行；只做轻量过滤，严重程度和合并规则留给后续步骤处理。
    """

    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if team_id is None or row.get("team_id") == team_id:
                rows.append(row)
    return sorted(rows, key=lambda r: float(r.get("t", 0.0)))


def _contact_zmax(row: dict) -> float:
    points = row.get("points") or []
    return max((float(p[2]) for p in points if len(p) >= 3), default=0.0)


def _summarize_contact_episode(rows: list[dict]) -> dict:
    """把一段时间连续的接触帧压成一个 episode 摘要。

    功能：输出接触时间窗、代表位置、峰值点数、最大高度和接触类型。
    参数：`rows` 是同一 episode 的逐帧接触记录。
    返回：用于绘图和空间合并的摘要字典。
    逻辑：代表位置取峰值接触帧；峰值先按 `count`，再按 `zmax` 比较。
    """

    peak_row = max(rows, key=lambda r: (int(r.get("count", 0)), _contact_zmax(r)))
    kinds = {r.get("kind", "contact") for r in rows}
    return {
        "t0": float(rows[0]["t"]),
        "t1": float(rows[-1]["t"]),
        "x": float(peak_row["x"]),
        "y": float(peak_row["y"]),
        "frames": len(rows),
        "episodes": 1,
        "peak_count": max(int(r.get("count", 0)) for r in rows),
        "zmax": max(_contact_zmax(r) for r in rows),
        "kind": "car_car" if "car_car" in kinds else "static_geometry",
    }


def _contact_episodes(rows: list[dict], gap: float = DEFAULT_CONTACT_GAP) -> list[dict]:
    """按时间 gap 合并接触帧。

    功能：把逐帧接触日志转成时间连续的 episode。
    参数：`rows` 已按时间排序；`gap` 是相邻接触帧仍算同一 episode 的最大秒数。
    返回：episode 摘要列表。
    逻辑：两帧间隔超过 `gap` 时切开，默认 0.3s 与 `analyze_contact_log.py` 保持一致。
    """

    if not rows:
        return []
    out: list[dict] = []
    cur = [rows[0]]
    for a, b in zip(rows, rows[1:]):
        if float(b["t"]) - float(a["t"]) > gap:
            out.append(_summarize_contact_episode(cur))
            cur = [b]
        else:
            cur.append(b)
    out.append(_summarize_contact_episode(cur))
    return out


def _merge_contact_clusters(episodes: list[dict], distance: float = DEFAULT_CONTACT_MERGE_DISTANCE) -> list[dict]:
    """把空间上接近的接触 episode 合并成图上的一条标注。

    功能：避免同一处栏杆的多次轻擦在总览图上刷出一串重复标签。
    参数：`episodes` 是时间 episode 摘要；`distance` 是世界坐标欧氏距离阈值。
    返回：空间合并后的接触簇列表。
    逻辑：默认 4.0 world units 视为“比较近”，约等于同一个弯角/同一段栏杆上的重复擦碰；
        合并后保留最严重 episode 的位置作为标注点，并累计时间窗和次数。
    """

    clusters: list[dict] = []
    for ep in sorted(episodes, key=lambda r: float(r["t0"])):
        best = None
        best_dist = math.inf
        for cluster in clusters:
            dist = math.hypot(ep["x"] - cluster["x"], ep["y"] - cluster["y"])
            if dist <= distance and dist < best_dist:
                best = cluster
                best_dist = dist
        if best is None:
            clusters.append(dict(ep))
            continue

        replace_location = (
            ep["peak_count"] > best["peak_count"]
            or (ep["peak_count"] == best["peak_count"] and ep["zmax"] > best["zmax"])
        )
        if replace_location:
            best["x"] = ep["x"]
            best["y"] = ep["y"]
            best["kind"] = ep["kind"]
        best["t0"] = min(best["t0"], ep["t0"])
        best["t1"] = max(best["t1"], ep["t1"])
        best["frames"] += ep["frames"]
        best["episodes"] += ep["episodes"]
        best["peak_count"] = max(best["peak_count"], ep["peak_count"])
        best["zmax"] = max(best["zmax"], ep["zmax"])
    return clusters


def _contact_clusters(
    rows: list[dict],
    *,
    start_t: float,
    end_t: float,
    gap: float = DEFAULT_CONTACT_GAP,
    merge_distance: float = DEFAULT_CONTACT_MERGE_DISTANCE,
) -> list[dict]:
    """生成当前 telemetry 时间窗内的接触簇。

    功能：给 `render` 提供已经过滤、分段、空间合并后的接触标注。
    参数：`rows` 是接触日志；`start_t/end_t` 限定当前 run；`gap` 和 `merge_distance` 控制合并。
    返回：接触簇列表。
    逻辑：先按时间过滤，再按时间切 episode，最后按空间距离合并。
    """

    window_rows = [r for r in rows if start_t <= float(r.get("t", -math.inf)) <= end_t]
    return _merge_contact_clusters(_contact_episodes(window_rows, gap), merge_distance)


def render(
    frames: list[dict],
    events: list[tuple[float, dict]],
    out_path: Path,
    title: str,
    contacts: list[dict] | None = None,
) -> None:
    """渲染轨迹+速度两栏图并存盘。

    功能：左/上为顶视轨迹（速度着色），右/下为速度-时间曲线，叠加事件、异常与接触标注。
    参数：`frames` 是单段 run 的逐帧记录，`events` 是事件列表，`out_path` 输出 PNG，
        `title` 图标题，`contacts` 是接触簇摘要。
    返回：无（直接写文件）。
    逻辑：轨迹用 scatter 上色并加 colorbar；状态异常段、最长爬行段、lap、事件分别用不同标记。
    """

    contacts = contacts or []
    xs = [f["x"] for f in frames]
    ys = [f["y"] for f in frames]
    ts = [f["t"] for f in frames]
    speeds = [f["speed"] for f in frames]

    fig, (ax_traj, ax_speed) = plt.subplots(2, 1, figsize=(11, 12), height_ratios=[3, 2])

    # ---- 上：顶视轨迹，按速度着色 ----
    sc = ax_traj.scatter(xs, ys, c=speeds, cmap="viridis", s=10, zorder=2)
    fig.colorbar(sc, ax=ax_traj, label="speed (supervisor 单位)")
    ax_traj.plot(xs, ys, color="0.7", linewidth=0.5, zorder=1)
    ax_traj.scatter([xs[0]], [ys[0]], c="lime", s=140, marker="o",
                    edgecolors="black", zorder=5, label="start")
    ax_traj.scatter([xs[-1]], [ys[-1]], c="red", s=160, marker="*",
                    edgecolors="black", zorder=5,
                    label=f"end ({frames[-1].get('status', 'normal')})")

    crawl = _longest_low_speed(frames, 0.3)
    if crawl and crawl["dur"] > 1.0:
        ax_traj.scatter([crawl["x0"], crawl["x1"]], [crawl["y0"], crawl["y1"]],
                        facecolors="none", edgecolors="orange", s=200, linewidths=2,
                        zorder=4, label=f"longest crawl {crawl['dur']:.0f}s")

    for t0, _t1, status in _status_segments(frames):
        fr = min(frames, key=lambda f: abs(f["t"] - t0))
        ax_traj.scatter([fr["x"]], [fr["y"]], c="magenta", s=90, marker="X",
                        zorder=6)
        ax_traj.annotate(status, (fr["x"], fr["y"]), fontsize=7, color="magenta")

    for t, x, y, lap in _lap_marks(frames):
        ax_traj.annotate(f"lap{lap}", (x, y), fontsize=8, color="blue", zorder=6)

    for idx, contact in enumerate(contacts, start=1):
        label = "contact cluster" if idx == 1 else None
        size = 120 + min(contact["peak_count"], 15) * 10
        ax_traj.scatter([contact["x"]], [contact["y"]], c="crimson", s=size, marker="X",
                        edgecolors="black", linewidths=0.8, zorder=7, label=label)
        suffix = f"x{contact['episodes']}" if contact["episodes"] > 1 else ""
        ax_traj.annotate(
            f"contact{suffix}\npts={contact['peak_count']} z={contact['zmax']:.2f}",
            (contact["x"], contact["y"]),
            fontsize=7,
            color="crimson",
            zorder=8,
        )

    ax_traj.set_aspect("equal", adjustable="datalim")
    ax_traj.set_xlabel("x (world)")
    ax_traj.set_ylabel("y (world)")
    ax_traj.set_title("顶视轨迹（颜色=速度）")
    ax_traj.legend(loc="best", fontsize=8)
    ax_traj.grid(True, alpha=0.3)

    # ---- 下：速度-时间 ----
    ax_speed.plot(ts, speeds, color="tab:blue", linewidth=1.0)
    ax_speed.fill_between(ts, speeds, alpha=0.15, color="tab:blue")
    for t0, t1, status in _status_segments(frames):
        ax_speed.axvspan(t0, t1, color="magenta", alpha=0.18)
    for t, _x, _y, lap in _lap_marks(frames):
        ax_speed.axvline(t, color="blue", linestyle="--", alpha=0.6)
        ax_speed.annotate(f"lap{lap}", (t, max(speeds) * 0.95), fontsize=8, color="blue")
    for t, ev in events:
        ax_speed.axvline(t, color="red", linestyle=":", alpha=0.5)
        label = ev.get("type") or ev.get("event") or "event"
        ax_speed.annotate(str(label), (t, max(speeds) * 0.5), fontsize=7,
                          color="red", rotation=90)
    for idx, contact in enumerate(contacts, start=1):
        if contact["t1"] > contact["t0"]:
            ax_speed.axvspan(contact["t0"], contact["t1"], color="crimson", alpha=0.14)
        else:
            ax_speed.axvline(contact["t0"], color="crimson", linestyle="-", alpha=0.45)
        suffix = f"x{contact['episodes']}" if contact["episodes"] > 1 else ""
        ax_speed.annotate(
            f"contact{idx}{suffix}",
            (contact["t0"], max(speeds) * 0.72),
            fontsize=7,
            color="crimson",
            rotation=90,
        )
    ax_speed.set_xlabel("t (s)")
    ax_speed.set_ylabel("speed")
    ax_speed.set_title("速度-时间（粉=状态异常段，蓝虚线=lap，红点线=事件，深红=接触日志）")
    ax_speed.grid(True, alpha=0.3)

    span = ts[-1] - ts[0]
    dist = sum(
        math.hypot(frames[i]["x"] - frames[i - 1]["x"], frames[i]["y"] - frames[i - 1]["y"])
        for i in range(1, len(frames))
    )
    fig.suptitle(
        f"{title}\n{len(frames)} 帧, t={ts[0]:.1f}→{ts[-1]:.1f} ({span:.1f}s), "
        f"行驶距离={dist:.1f}, 接触簇={len(contacts)}, 末帧 status={frames[-1].get('status', 'normal')}",
        fontsize=11,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=130)
    plt.close(fig)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把一次 run 的 telemetry 画成轨迹+速度+事件图。")
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY,
                        help=f"telemetry.jsonl 路径（默认 {DEFAULT_TELEMETRY}）")
    parser.add_argument("--team-id", default=None, help="目标车 team_id（默认取每帧第一辆车）")
    parser.add_argument("--contact-log", type=Path, default=None,
                        help="可选：结构化撞栏接触日志 contact_<world>.jsonl")
    parser.add_argument("--contact-gap", type=float, default=DEFAULT_CONTACT_GAP,
                        help=f"时间 episode 合并间隔，默认 {DEFAULT_CONTACT_GAP}s")
    parser.add_argument("--contact-merge-distance", type=float, default=DEFAULT_CONTACT_MERGE_DISTANCE,
                        help=f"空间接触簇合并距离，默认 {DEFAULT_CONTACT_MERGE_DISTANCE} world units")
    parser.add_argument("--out", type=Path, required=True, help="输出 PNG 路径")
    parser.add_argument("--title", default="run trajectory", help="图标题（建议写 R-id + 赛道）")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.telemetry.is_file():
        print(f"[error] 找不到遥测文件: {args.telemetry}")
        return 1
    all_frames, events = _load_car_frames(args.telemetry, args.team_id)
    if not all_frames:
        print(f"[error] 未解析到任何车辆帧（team_id={args.team_id}）")
        return 1
    # 只画最近一段 run，避免跨 run 残留把轨迹连成乱线（与 analyze_telemetry 同口径）。
    frames = _split_runs(all_frames)[-1]
    t0, t1 = frames[0]["t"], frames[-1]["t"]
    window_events = [(t, ev) for t, ev in events if t0 <= t <= t1]
    contacts: list[dict] = []
    if args.contact_log is not None:
        if not args.contact_log.is_file():
            print(f"[error] 找不到接触日志: {args.contact_log}")
            return 1
        contact_rows = _load_contact_rows(args.contact_log, args.team_id)
        contacts = _contact_clusters(
            contact_rows,
            start_t=t0,
            end_t=t1,
            gap=args.contact_gap,
            merge_distance=args.contact_merge_distance,
        )
    render(frames, window_events, args.out, args.title, contacts)
    print(
        f"已生成轨迹图: {args.out}  ({len(frames)} 帧, t={t0:.1f}→{t1:.1f}, "
        f"接触簇={len(contacts)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
