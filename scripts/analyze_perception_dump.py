"""dump 帧感知丢线分析工具。

功能概述：对 P2.5 保存的左右相机帧逐帧重跑 perception，验证与实车控制日志对齐，并产出丢线指标。
输入输出：输入 `frame_<t>_left/right.png` 和 control JSONL，输出指标 JSON、终端摘要和可选 overlay 图。
处理流程：按时间戳配对帧 → join 控制日志 → 重算 extract_observation → 统计复现误差、丢线率和中心漂移。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.estimator import ESTIMATOR_PROFILE
from controller.perception import _build_masks, _scan_image, extract_observation


def _parse_frame_timestamp(left_path: Path) -> float:
    stem = left_path.stem
    token = stem[len("frame_"):-len("_left")]
    if token.startswith("m"):
        token = "-" + token[1:]
    head, tail = token.split("_", 1)
    return float(f"{head}.{tail}")


def _time_key(timestamp: float) -> int:
    return int(round(float(timestamp) * 1000.0))


def _frame_pairs(frame_dir: Path) -> list[tuple[float, Path, Path]]:
    pairs = []
    for left_path in sorted(frame_dir.glob("frame_*_left.png")):
        right_path = left_path.with_name(left_path.name.replace("_left.png", "_right.png"))
        if right_path.is_file():
            pairs.append((_parse_frame_timestamp(left_path), left_path, right_path))
    pairs.sort(key=lambda item: item[0])
    return pairs


def _load_control_log(path: Path) -> dict[int, dict]:
    rows = {}
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "t" in row:
                rows[_time_key(float(row["t"]))] = row
    return rows


def _round4(value: float) -> float:
    return round(float(value), 4)


def _first_center_x(obs) -> float | None:
    if len(obs.center_points) == 0:
        return None
    return float(obs.center_points[0, 0])


def _scan_debug(image: np.ndarray, timestamp: float) -> dict:
    road_mask, edge_mask, _texture, mask_fill_ratio, _near_obstacle = _build_masks(image, timestamp)
    scan = _scan_image(image, timestamp)
    return {
        "mask_fill_ratio": float(mask_fill_ratio),
        "points": int(len(scan.center_points)),
        "confidence": float(scan.confidence),
        "debug_flags": int(scan.debug_flags),
        "road_width": float(scan.road_width_est),
        "road_mask": road_mask,
        "edge_mask": edge_mask,
        "scan": scan,
    }


def _draw_side_overlay(image: np.ndarray, debug: dict) -> np.ndarray:
    overlay = image.copy()
    road = debug["road_mask"] > 0
    edge = debug["edge_mask"] > 0
    overlay[road] = (0.45 * overlay[road] + 0.55 * np.array([0, 180, 0])).astype(np.uint8)
    overlay[edge] = (0, 220, 255)
    scan = debug["scan"]
    for left, center, right in zip(scan.left_edge_points, scan.center_points, scan.right_edge_points):
        y = int(round(center[1]))
        cv2.line(overlay, (int(round(left[0])), y), (int(round(right[0])), y), (255, 180, 0), 1)
        cv2.circle(overlay, (int(round(center[0])), y), 4, (0, 0, 255), -1)
    return overlay


def _write_overlay(
    out_dir: Path,
    timestamp: float,
    left_img: np.ndarray,
    right_img: np.ndarray,
    left_debug: dict,
    right_debug: dict,
    row: dict | None,
) -> str:
    out_dir.mkdir(parents=True, exist_ok=True)
    left_overlay = _draw_side_overlay(left_img, left_debug)
    right_overlay = _draw_side_overlay(right_img, right_debug)
    combined = np.concatenate([left_overlay, right_overlay], axis=1)
    label = (
        f"t={timestamp:.3f} log_points={row.get('obs_points') if row else 'NA'} "
        f"L fill={left_debug['mask_fill_ratio']:.3f} pts={left_debug['points']} "
        f"R fill={right_debug['mask_fill_ratio']:.3f} pts={right_debug['points']}"
    )
    cv2.putText(combined, label, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (255, 255, 255), 2, cv2.LINE_AA)
    time_token = f"{timestamp:010.3f}".replace(".", "_")
    path = out_dir / f"overlay_{time_token}.png"
    cv2.imwrite(str(path), combined)
    return str(path)


def analyze_dump(
    frame_dir: Path,
    control_log: Path,
    overlay_dir: Path | None = None,
    overlay_limit: int = 12,
    baseline_json: Path | None = None,
    overlay_at: list[float] | None = None,
) -> dict:
    """分析 dump 帧感知结果。

    功能：重算每帧 perception，统计对齐可信度、感知丢线率和相对 baseline 的中心漂移。
    参数：`frame_dir` 是帧目录，`control_log` 是实车日志，`overlay_dir` 可保存例图；
        `overlay_at` 给定时只为这些时间戳最近的帧出 overlay（不论是否丢线），用于报告取证；
        为 None 时退回默认行为：自动挑前 `overlay_limit` 个丢线帧出 overlay。
    返回：可写入 JSON 的指标字典。
    逻辑：对齐字段先和日志比，再按 obs_points / confidence 判断感知丢线。
    """

    pairs = _frame_pairs(frame_dir)
    control_rows = _load_control_log(control_log)
    forced_keys: set[int] = set()
    if overlay_at and pairs:
        for req in overlay_at:
            nearest = min(pairs, key=lambda item: abs(item[0] - req))
            forced_keys.add(_time_key(nearest[0]))
    baseline = None
    if baseline_json is not None and baseline_json.is_file():
        baseline = json.loads(baseline_json.read_text(encoding="utf-8"))
    baseline_frames = {item["key"]: item for item in baseline.get("frames", [])} if baseline else {}

    frames = []
    mismatches = []
    center_deltas = []
    normal_regressions = 0
    overlay_paths = []
    lost_threshold = float(ESTIMATOR_PROFILE["lost_confidence"])

    for timestamp, left_path, right_path in pairs:
        key = _time_key(timestamp)
        row = control_rows.get(key)
        left_img = cv2.imread(str(left_path))
        right_img = cv2.imread(str(right_path))
        obs = extract_observation(left_img, right_img, timestamp)
        obs_points = int(len(obs.center_points))
        obs_conf = _round4(obs.confidence)
        debug_flags = int(obs.debug_flags)
        perception_lost = obs_points == 0 or float(obs.confidence) < lost_threshold
        center_x = _first_center_x(obs)

        if row is None:
            mismatches.append({"t": timestamp, "field": "missing_log"})
        else:
            checks = {
                "obs_points": (obs_points, int(row.get("obs_points", -1))),
                "obs_conf": (obs_conf, _round4(float(row.get("obs_conf", -1.0)))),
                "debug_flags": (debug_flags, int(row.get("debug_flags", -1))),
            }
            for field, (actual, expected) in checks.items():
                if actual != expected:
                    mismatches.append({"t": timestamp, "field": field, "actual": actual, "expected": expected})

        baseline_frame = baseline_frames.get(str(key))
        if baseline_frame and baseline_frame.get("center_x") is not None and center_x is not None:
            delta = abs(float(center_x) - float(baseline_frame["center_x"]))
            center_deltas.append(delta)
            if not baseline_frame.get("perception_lost") and perception_lost:
                normal_regressions += 1

        if overlay_at is not None:
            want_overlay = key in forced_keys
        else:
            want_overlay = perception_lost and len(overlay_paths) < overlay_limit
        if want_overlay and overlay_dir is not None:
            left_debug = _scan_debug(left_img, timestamp)
            right_debug = _scan_debug(right_img, timestamp)
            overlay_paths.append(_write_overlay(overlay_dir, timestamp, left_img, right_img, left_debug, right_debug, row))

        frames.append({
            "key": str(key),
            "t": float(timestamp),
            "obs_points": obs_points,
            "obs_conf": float(obs_conf),
            "debug_flags": debug_flags,
            "road_width": round(float(obs.road_width_est), 2),
            "perception_lost": perception_lost,
            "center_x": center_x,
        })

    lost_count = sum(1 for item in frames if item["perception_lost"])
    center_summary = {
        "count": len(center_deltas),
        "mean_abs_px": float(np.mean(center_deltas)) if center_deltas else 0.0,
        "p95_abs_px": float(np.percentile(center_deltas, 95)) if center_deltas else 0.0,
        "max_abs_px": float(np.max(center_deltas)) if center_deltas else 0.0,
        "normal_to_lost_regressions": normal_regressions,
    }
    return {
        "frame_dir": str(frame_dir),
        "control_log": str(control_log),
        "total_frames": len(frames),
        "joined_frames": sum(1 for item in frames if _time_key(item["t"]) in control_rows),
        "perception_lost_frames": lost_count,
        "perception_lost_rate": lost_count / max(len(frames), 1),
        "lost_threshold": lost_threshold,
        "mismatch_count": len(mismatches),
        "mismatches_sample": mismatches[:20],
        "center_delta_vs_baseline": center_summary,
        "overlay_paths": overlay_paths,
        "frames": frames,
    }


def _print_summary(metrics: dict) -> None:
    print("================ PERCEPTION DUMP 分析 ================")
    print(f"帧目录     : {metrics['frame_dir']}")
    print(f"控制日志   : {metrics['control_log']}")
    print(f"帧数/join  : {metrics['total_frames']} / {metrics['joined_frames']}")
    print(f"复现差异   : {metrics['mismatch_count']} 处")
    print(f"感知丢线率 : {metrics['perception_lost_frames']}/{metrics['total_frames']} "
          f"({metrics['perception_lost_rate']:.3f})")
    drift = metrics["center_delta_vs_baseline"]
    if drift["count"]:
        print(f"中心漂移   : mean={drift['mean_abs_px']:.2f}px p95={drift['p95_abs_px']:.2f}px "
              f"max={drift['max_abs_px']:.2f}px normal→lost={drift['normal_to_lost_regressions']}")
    if metrics["overlay_paths"]:
        print("overlay    : " + "  ".join(metrics["overlay_paths"][:5]))
    print("======================================================")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="分析 dump 帧 perception 复现度与丢线率。")
    parser.add_argument("frames", type=Path, help="frame_<t>_left/right.png 所在目录")
    parser.add_argument("--control-log", type=Path, required=True, help="同一次 run 的 control JSONL")
    parser.add_argument("--out", type=Path, default=None, help="输出指标 JSON")
    parser.add_argument("--baseline", type=Path, default=None, help="before 指标 JSON，用于中心漂移对比")
    parser.add_argument("--overlay-dir", type=Path, default=None, help="保存 overlay 的目录")
    parser.add_argument("--overlay-limit", type=int, default=12,
                        help="默认模式下最多自动出多少张丢线帧 overlay")
    parser.add_argument("--at", type=str, default=None,
                        help="逗号分隔的时间戳，如 145.7,177.4：只为这些时刻最近的帧出 overlay "
                             "（不论是否丢线），用于挑报告里要讲的关键画面")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.frames.is_dir():
        print(f"[error] 找不到帧目录: {args.frames}")
        return 1
    if not args.control_log.is_file():
        print(f"[error] 找不到控制日志: {args.control_log}")
        return 1
    overlay_at = None
    if args.at:
        overlay_at = [float(tok) for tok in args.at.split(",") if tok.strip()]
    metrics = analyze_dump(
        args.frames,
        args.control_log,
        overlay_dir=args.overlay_dir,
        overlay_limit=max(args.overlay_limit, 0),
        baseline_json=args.baseline,
        overlay_at=overlay_at,
    )
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_summary(metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
