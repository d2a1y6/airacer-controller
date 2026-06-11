"""提交文件构建脚本。

功能概述：把 `controller/` 的模块化代码合并成单个 `team_controller.py`。
输入输出：读取本地控制器源码，输出平台可上传的自包含文件。
处理流程：按固定顺序拼接模块，删除本地 import，把 `PROFILE` 固定为命令传入的模式。
"""

from __future__ import annotations

import argparse
import io
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTROLLER_DIR = ROOT / "controller"
DEFAULT_OUTPUTS = {
    "fastest": ROOT / "submissions" / "fastest" / "team_controller.py",
    "safe": ROOT / "submissions" / "safe" / "team_controller.py",
}
MODULE_ORDER = [
    "common.py",
    "params.py",
    "opponent.py",
    "perception.py",
    "estimator.py",
    "policy.py",
    "team_controller_local.py",
]


def strip_local_imports(source: str) -> str:
    """移除提交文件不应保留的本地 import。

    功能：让生成文件不依赖 `controller/` 包。
    参数：`source` 是单个模块源码。
    返回：删除本地 import 行后的源码。
    逻辑：外部允许库由构建头部统一导入，模块间依赖由拼接顺序解决。
    """

    kept_lines = []
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("from __future__"):
            continue
        if stripped.startswith("from controller.") or stripped.startswith("from ."):
            continue
        if stripped in {
            "import cv2",
            "import math",
            "import numpy as np",
            "from dataclasses import dataclass",
        }:
            continue
        kept_lines.append(line)
    return "\n".join(kept_lines).strip()


def strip_submission_text(source: str) -> str:
    """压缩提交源码里的说明文本。

    功能：删除注释和独立字符串 docstring，降低最终单文件大小。
    参数：`source` 是已经拼好的提交源码。
    返回：保留可执行代码后的源码。
    逻辑：用 tokenizer 处理，避免误删字符串字面量里的 `#` 或中文内容。
    """

    kept_tokens = []
    previous_type = tokenize.INDENT
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        token_type, token_text, start, end, line = token
        if token_type == tokenize.COMMENT and not token_text.startswith("# ----"):
            continue
        if token_type == tokenize.STRING and previous_type in {
            tokenize.INDENT,
            tokenize.NEWLINE,
            tokenize.NL,
        }:
            previous_type = token_type
            continue
        kept_tokens.append((token_type, token_text, start, end, line))
        if token_type not in {tokenize.NL, tokenize.COMMENT}:
            previous_type = token_type
    stripped = tokenize.untokenize(kept_tokens)
    return "\n".join(line.rstrip() for line in stripped.splitlines())


_DEBUG_CONTROL_BLOCK = '''    try:
        obs = extract_observation(left_img, right_img, timestamp)
        track = estimate_track(obs, timestamp)
        cmd = decide_control(track, timestamp, mode=PROFILE)
        steering, speed = clamp_cmd(cmd)
        return steering, speed
    except Exception:
        return 0.0, 0.0'''


def _debug_control_block(
    log_path: str | None = None,
    dump_frames: str | None = None,
    dump_frame_stride: int = 1,
) -> str:
    """生成带调试探针的 control() 实现（仅本地调试构建，禁止上传）。

    功能：在不改变驾驶行为的前提下，写逐帧状态日志，并可定期保存左右相机原始帧。
    参数：`log_path` 是日志输出路径；`dump_frames` 是帧目录；`dump_frame_stride` 是存帧间隔。
    返回：替换 team_controller_local.control() 主体的源码块。
    逻辑：所有调试 I/O 异常都被吞掉，绝不影响 control 返回。
    """

    stride = max(int(dump_frame_stride), 1)
    return f'''    try:
        global _DBG_FRAME_INDEX
        if _DBG_FRAME_DIR is not None:
            try:
                _DBG_FRAME_INDEX += 1
                if _DBG_FRAME_INDEX % _DBG_FRAME_STRIDE == 0:
                    _dbg_t = ("%010.3f" % float(timestamp)).replace("-", "m").replace(".", "_")
                    np.save(_DBG_FRAME_DIR + "frame_" + _dbg_t + "_left.npy", left_img)
                    np.save(_DBG_FRAME_DIR + "frame_" + _dbg_t + "_right.npy", right_img)
            except Exception:
                pass
        obs = extract_observation(left_img, right_img, timestamp)
        track = estimate_track(obs, timestamp)
        cmd = decide_control(track, timestamp, mode=PROFILE)
        steering, speed = clamp_cmd(cmd)
        if _DBG_FH is not None:
            try:
                _DBG_FH.write(_dbg_json.dumps({{
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
                    "mode": _LAST_MODE,
                    "mode_reason": _LAST_MODE_REASON,
                    "target_steering": round(float(_LAST_TARGET_STEERING), 4),
                    "target_speed": round(float(_LAST_TARGET_SPEED), 4),
                    "curve_risk": round(float(_LAST_SIGNALS.get("curve_risk", 0.0)), 4),
                    "offset_risk": round(float(_LAST_SIGNALS.get("offset_risk", 0.0)), 4),
                    "margin_risk": round(float(_LAST_SIGNALS.get("margin_risk", 0.0)), 4),
                    "straight_memory": bool(_LAST_STRAIGHT_MEMORY_ACTIVE),
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
                }}) + "\\n")
                _DBG_FH.flush()
            except Exception:
                pass
        return steering, speed
    except Exception:
        return 0.0, 0.0'''


def read_module(
    name: str,
    mode: str,
    debug_log: str | None = None,
    dump_frames: str | None = None,
    dump_frame_stride: int = 1,
) -> str:
    """读取并清理控制器模块。

    功能：按文件名读取 `controller/` 下的模块源码。
    参数：`name` 是模块文件名，`mode` 是构建策略；调试参数非空时注入本地探针。
    返回：可拼接到提交文件中的源码片段。
    逻辑：读取文本后移除本地 import；入口模块里把 PROFILE 替换为固定模式，并按需注入调试日志。
    """

    source = (CONTROLLER_DIR / name).read_text(encoding="utf-8")
    source = strip_local_imports(source)
    if name == "team_controller_local.py":
        source = source.replace('PROFILE = "fastest"', f'PROFILE = "{mode}"')
        source = source.replace('PROFILE = "safe"', f'PROFILE = "{mode}"')
        if debug_log or dump_frames:
            header_lines = []
            if debug_log:
                header_lines.extend([
                    "import json as _dbg_json",
                    f"try:\n    _DBG_FH = open({repr(str(debug_log))}, \"w\", encoding=\"utf-8\")\n"
                    "except Exception:\n    _DBG_FH = None",
                ])
            else:
                header_lines.append("_DBG_FH = None")
            if dump_frames:
                header_lines.extend([
                    f"_DBG_FRAME_DIR = {repr(str(dump_frames).rstrip('/') + '/')}",
                    f"_DBG_FRAME_STRIDE = {max(int(dump_frame_stride), 1)}",
                    "_DBG_FRAME_INDEX = 0",
                ])
            else:
                header_lines.extend([
                    "_DBG_FRAME_DIR = None",
                    "_DBG_FRAME_STRIDE = 1",
                    "_DBG_FRAME_INDEX = 0",
                ])
            header = "\n".join(header_lines) + "\n"
            source = header + "\n" + source
            source = source.replace(
                _DEBUG_CONTROL_BLOCK,
                _debug_control_block(
                    log_path=debug_log,
                    dump_frames=dump_frames,
                    dump_frame_stride=dump_frame_stride,
                ),
            )
    return source


def build_source(
    mode: str,
    debug_log: str | None = None,
    dump_frames: str | None = None,
    dump_frame_stride: int = 1,
) -> str:
    """构建单文件控制器源码。

    功能：为指定模式生成自包含 Python 源码。
    参数：`mode` 为构建模式；调试参数非空则生成本地调试构建。
    返回：完整源码字符串。
    逻辑：写入允许 import，再按契约顺序拼接所有控制器模块。
    """

    parts = [
        "# Generated by scripts/build_submission.py. Edit controller/ instead.\n"
        "from dataclasses import dataclass\n"
        "import math\n\n"
        "import cv2\n"
        "import numpy as np\n"
    ]
    for module in MODULE_ORDER:
        parts.append(f"\n# ---- {module} ----\n")
        parts.append(read_module(
            module,
            mode,
            debug_log=debug_log,
            dump_frames=dump_frames,
            dump_frame_stride=dump_frame_stride,
        ))
        parts.append("\n")
    source = "\n".join(parts).strip() + "\n"
    if not (debug_log or dump_frames):
        source = strip_submission_text(source)
    return source.strip() + "\n"


def parse_args():
    """解析命令行参数。

    功能：读取构建模式和输出路径。
    参数：无。
    返回：`argparse.Namespace`。
    逻辑：模式只允许 fastest 和 safe，未指定输出时写入对应 submissions 目录。
    """

    parser = argparse.ArgumentParser(description="Build single-file AI Racer submission.")
    parser.add_argument("--mode", choices=sorted(DEFAULT_OUTPUTS), default="fastest")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--debug-log", type=Path, default=None,
                        help="本地调试构建：把每帧内部状态与命令写到该 JSONL（含 open/json，禁止上传）")
    parser.add_argument("--dump-frames", type=Path, default=None,
                        help="本地调试构建：每隔 N 帧把 left/right BGR 保存为 .npy（禁止上传）")
    parser.add_argument("--dump-frame-stride", type=int, default=1,
                        help="--dump-frames 的存帧间隔，默认每帧保存")
    return parser.parse_args()


def main() -> int:
    """脚本入口。

    功能：生成指定模式的提交文件。
    参数：来自命令行。
    返回：进程退出码。
    逻辑：确定输出路径，创建父目录，写入源码并打印结果摘要。
    """

    args = parse_args()
    output = args.out or DEFAULT_OUTPUTS[args.mode]
    output = output if output.is_absolute() else ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    debug_log = None
    if args.debug_log is not None:
        debug_log = args.debug_log if args.debug_log.is_absolute() else ROOT / args.debug_log
        debug_log.parent.mkdir(parents=True, exist_ok=True)
        debug_log = str(debug_log)
    dump_frames = None
    if args.dump_frames is not None:
        dump_frames_path = args.dump_frames if args.dump_frames.is_absolute() else ROOT / args.dump_frames
        dump_frames_path.mkdir(parents=True, exist_ok=True)
        dump_frames = str(dump_frames_path)
    output.write_text(
        build_source(
            args.mode,
            debug_log=debug_log,
            dump_frames=dump_frames,
            dump_frame_stride=args.dump_frame_stride,
        ),
        encoding="utf-8",
    )
    suffix_parts = []
    if debug_log:
        suffix_parts.append(f"调试日志 → {debug_log}")
    if dump_frames:
        suffix_parts.append(f"存帧目录 → {dump_frames} (stride={max(int(args.dump_frame_stride), 1)})")
    suffix = f"  ({'; '.join(suffix_parts)})" if suffix_parts else ""
    print(f"已生成 {args.mode}: {output}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
