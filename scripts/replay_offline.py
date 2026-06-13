"""离线开环回放工具。

功能概述：读取调试构建保存的左右相机帧，离线跑控制器感知、估计和策略接线。
输入输出：输入 `frame_<t>_left.png/right.png` 成对帧，输出和 control 调试日志同 schema 的 JSONL。
处理流程：按时间排序帧对 → reset 跨帧状态 → 执行 extract_observation/estimate_track/decide_control → 写逐帧 JSONL。

限制：这是开环回放固定输入帧，只能用于筛同一段录制画面下感知/估计改动对丢线率、置信度和几何量的影响。
它不能评估速度或控制策略效果，因为真实转向会改变后续画面，开环重放无法体现轨迹反馈。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from controller.common import clamp_cmd
from controller.estimator import estimate_track, reset_estimator_state
from controller.params import get_profile
from controller.perception import extract_observation
from controller.policy import decide_control, reset_policy_state
import controller.policy as policy_state


def _parse_frame_timestamp(left_path: Path) -> float:
    """从 P2.5 存帧文件名解析时间戳。

    功能：把 `frame_000012_345_left.png` 还原为 `12.345`。
    参数：`left_path` 是左图 `.png` 路径。
    返回：浮点时间戳。
    逻辑：文件名中的负号写成 `m`，小数点写成 `_`；解析失败时抛出 `ValueError`。
    """

    stem = left_path.stem
    if not stem.startswith("frame_") or not stem.endswith("_left"):
        raise ValueError(f"无法解析左帧文件名: {left_path.name}")
    token = stem[len("frame_"):-len("_left")]
    if token.startswith("m"):
        token = "-" + token[1:]
    if "_" in token:
        head, tail = token.split("_", 1)
        token = f"{head}.{tail}"
    return float(token)


def iter_frame_pairs(frame_dir: Path) -> list[tuple[float, Path, Path]]:
    """查找并排序左右帧对。

    功能：在目录内收集调试构建生成的左右 `.png` 帧。
    参数：`frame_dir` 是存帧目录。
    返回：`(timestamp, left_path, right_path)` 列表，按时间升序。
    逻辑：以左帧为主，要求同名右帧存在；缺右帧时直接跳过。
    """

    pairs: list[tuple[float, Path, Path]] = []
    for left_path in sorted(frame_dir.glob("frame_*_left.png")):
        right_path = left_path.with_name(left_path.name.replace("_left.png", "_right.png"))
        if not right_path.is_file():
            continue
        pairs.append((_parse_frame_timestamp(left_path), left_path, right_path))
    pairs.sort(key=lambda item: item[0])
    return pairs


def replay_frames(frame_dir: Path, out_path: Path, mode: str = "no_other_cars", limit: int | None = None) -> int:
    """执行开环回放并写出 control 日志同 schema JSONL。

    功能：把保存帧转成可被 `analyze_control_log.py` 直接分析的日志。
    参数：`frame_dir` 是帧目录，`out_path` 是输出 JSONL，`mode` 是 profile，`limit` 可限制帧数。
    返回：写出的帧数。
    逻辑：每次回放前 reset 估计器和策略状态；单帧异常写 fallback 行并继续。
    """

    pairs = iter_frame_pairs(frame_dir)
    if limit is not None:
        pairs = pairs[:max(limit, 0)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    reset_estimator_state()
    reset_policy_state()
    profile = get_profile(mode)  # 让 perception 的对手检测/光流卡死按 profile 门控

    written = 0
    with out_path.open("w", encoding="utf-8") as handle:
        for timestamp, left_path, right_path in pairs:
            try:
                left_img = cv2.imread(str(left_path))
                right_img = cv2.imread(str(right_path))
                obs = extract_observation(left_img, right_img, timestamp, profile=profile)
                track = estimate_track(obs, timestamp)
                cmd = decide_control(track, timestamp, mode=mode)
                steering, speed = clamp_cmd(cmd)
                row = {
                    "t": float(timestamp),
                    "steering": round(float(steering), 4),
                    "speed": round(float(speed), 4),
                    "lateral": round(float(track.lateral_error), 4),
                    "heading": round(float(track.heading_error), 4),
                    "curvature": round(float(track.curvature), 4),
                    "lookahead": round(float(track.lookahead_error), 4),
                    "track_conf": round(float(track.confidence), 4),
                    "lost": bool(track.lost),
                    "red_env": bool(track.red_environment),
                    "mode": policy_state._LAST_MODE,
                    "mode_reason": policy_state._LAST_MODE_REASON,
                    "target_steering": round(float(policy_state._LAST_TARGET_STEERING), 4),
                    "target_speed": round(float(policy_state._LAST_TARGET_SPEED), 4),
                    "curve_risk": round(float(policy_state._LAST_SIGNALS.get("curve_risk", 0.0)), 4),
                    "offset_risk": round(float(policy_state._LAST_SIGNALS.get("offset_risk", 0.0)), 4),
                    "margin_risk": round(float(policy_state._LAST_SIGNALS.get("margin_risk", 0.0)), 4),
                    "straight_memory": bool(policy_state._LAST_STRAIGHT_MEMORY_ACTIVE),
                    "obs_conf": round(float(obs.confidence), 4),
                    "obs_points": int(len(obs.center_points)),
                    "road_width": round(float(obs.road_width_est), 2),
                    "debug_flags": int(obs.debug_flags),
                    "line_offset": round(float(track.line_offset), 4),
                    "line_heading": round(float(track.line_heading), 4),
                    "line_conf": round(float(track.line_confidence), 4),
                    "left_margin": round(float(track.left_margin_near), 4),
                    "right_margin": round(float(track.right_margin_near), 4),
                    "near_obstacle": bool(track.near_obstacle),
                    "obstacle_x": round(float(track.obstacle_x), 4),
                    "obstacle_size": round(float(track.obstacle_size), 5),
                }
            except Exception:
                row = {
                    "t": float(timestamp),
                    "steering": 0.0,
                    "speed": 0.0,
                    "lateral": 0.0,
                    "heading": 0.0,
                    "curvature": 0.0,
                    "lookahead": 0.0,
                    "track_conf": 0.0,
                    "lost": True,
                    "red_env": False,
                    "mode": "exception",
                    "mode_reason": "exception",
                    "target_steering": 0.0,
                    "target_speed": 0.0,
                    "curve_risk": 0.0,
                    "offset_risk": 0.0,
                    "margin_risk": 0.0,
                    "straight_memory": False,
                    "obs_conf": 0.0,
                    "obs_points": 0,
                    "road_width": 0.0,
                    "debug_flags": 0,
                    "line_offset": 0.0,
                    "line_heading": 0.0,
                    "line_conf": 0.0,
                    "left_margin": 1.0,
                    "right_margin": 1.0,
                    "near_obstacle": False,
                    "obstacle_x": 0.0,
                    "obstacle_size": 0.0,
                }
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="离线开环回放 P2.5 保存的左右相机帧。")
    parser.add_argument("frames", type=Path, help="包含 frame_<t>_left.png/right.png 的目录")
    parser.add_argument("--out", type=Path, required=True, help="输出 control 同 schema JSONL")
    parser.add_argument("--mode", choices=("no_other_cars", "with_other_cars"), default="no_other_cars")
    parser.add_argument("--limit", type=int, default=None, help="最多回放多少帧，默认不限")
    return parser.parse_args()


def main() -> int:
    """脚本入口。"""

    args = parse_args()
    if not args.frames.is_dir():
        print(f"[error] 找不到帧目录: {args.frames}")
        return 1
    written = replay_frames(args.frames, args.out, mode=args.mode, limit=args.limit)
    if written == 0:
        print(f"[error] 没有找到完整左右帧对: {args.frames}")
        return 1
    print(f"已回放 {written} 帧，输出: {args.out}")
    print("说明：这是开环固定画面回放，只用于比较感知/估计输出；不能评估速度、控制策略或圈速。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
