"""整场轨迹 / 速度 / 事件可视化工具（本地报告用）。

功能概述：把一次真实 run 的 supervisor `telemetry.jsonl` 画成两张图——顶视轨迹（按速度着色）
    和速度-时间曲线，并标注起终点、最长爬行段、状态异常（碰撞/卡住）点和事件。
输入输出：输入 `telemetry.jsonl`（默认读 SDK 的 `.local/recordings/`），输出单张 PNG。
处理流程：复用 `analyze_telemetry` 的流式解析与跨 run 切段 → 取最近一段 → 渲染两栏图 → 存盘。
设计目的：替代过去每次手写 matplotlib 的临时做法，让"每时刻轨迹和速度、碰撞情况的图"
    成为可复现、可放进 `experiments/figures/` 的固定产物。
"""

from __future__ import annotations

import argparse
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


def render(frames: list[dict], events: list[tuple[float, dict]], out_path: Path, title: str) -> None:
    """渲染轨迹+速度两栏图并存盘。

    功能：左/上为顶视轨迹（速度着色），右/下为速度-时间曲线，叠加事件与异常标注。
    参数：`frames` 是单段 run 的逐帧记录，`events` 是事件列表，`out_path` 输出 PNG，`title` 图标题。
    返回：无（直接写文件）。
    逻辑：轨迹用 scatter 上色并加 colorbar；状态异常段、最长爬行段、lap、事件分别用不同标记。
    """

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
    ax_speed.set_xlabel("t (s)")
    ax_speed.set_ylabel("speed")
    ax_speed.set_title("速度-时间（粉=状态异常段，蓝虚线=lap，红点线=事件）")
    ax_speed.grid(True, alpha=0.3)

    span = ts[-1] - ts[0]
    dist = sum(
        math.hypot(frames[i]["x"] - frames[i - 1]["x"], frames[i]["y"] - frames[i - 1]["y"])
        for i in range(1, len(frames))
    )
    fig.suptitle(
        f"{title}\n{len(frames)} 帧, t={ts[0]:.1f}→{ts[-1]:.1f} ({span:.1f}s), "
        f"行驶距离={dist:.1f}, 末帧 status={frames[-1].get('status', 'normal')}",
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
    render(frames, window_events, args.out, args.title)
    print(f"已生成轨迹图: {args.out}  ({len(frames)} 帧, t={t0:.1f}→{t1:.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
