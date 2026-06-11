"""生成 Webots 跳点取证 world。

功能概述：从 telemetry 中取指定时间附近的车辆姿态，把原始 `.wbt` 复制成临时 world，
并把某个 car slot 的初始位置/朝向改到该姿态。
输入输出：输入 telemetry、源 world、目标时间和车位；输出临时 `.wbt`。
处理流程：读取最近 telemetry 帧，换算 Webots z 轴旋转角，替换 DEF 车辆块内的
translation/rotation 字段。
"""

from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path


SDK_DIR = Path("/Users/day/Desktop/Github/pkudsa.airacer/sdk")
DEFAULT_TELEMETRY = SDK_DIR / ".local" / "recordings" / "telemetry.jsonl"
DEFAULT_WORLDS = {
    "basic": SDK_DIR / "webots" / "worlds" / "track_basic.wbt",
    "complex": SDK_DIR / "webots" / "worlds" / "track_complex.wbt",
}


def _load_pose(telemetry: Path, target_time: float, team_id: str | None = None) -> dict:
    """从 telemetry 中读取最接近目标时间的一帧车辆姿态。

    参数：`telemetry` 是 supervisor 写出的 JSONL；`target_time` 是目标仿真时间；
        `team_id` 可限定队伍，默认取第一辆车。
    返回：包含 `t/x/y/heading/speed/status` 的字典。
    逻辑：逐行扫描即可，telemetry 规模不大；按时间差选最近帧。
    """

    best: dict | None = None
    best_gap = float("inf")
    with telemetry.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            cars = row.get("cars") or []
            for car in cars:
                if team_id and car.get("team_id") != team_id:
                    continue
                try:
                    sim_time = float(row["t"])
                    pose = {
                        "t": sim_time,
                        "x": float(car["x"]),
                        "y": float(car["y"]),
                        "heading": float(car["heading"]),
                        "speed": float(car.get("speed", 0.0)),
                        "status": car.get("status", ""),
                    }
                except (KeyError, TypeError, ValueError):
                    continue
                gap = abs(sim_time - target_time)
                if gap < best_gap:
                    best = pose
                    best_gap = gap
                break
    if best is None:
        raise ValueError(f"telemetry 中找不到车辆姿态: {telemetry}")
    return best


def _replace_field(block: str, field: str, value: str) -> str:
    """替换或插入 Webots 节点块中的单行字段。"""

    pattern = re.compile(rf"(?m)^(\s*){re.escape(field)}\s+.+$")
    match = pattern.search(block)
    if match:
        indent = match.group(1)
        return pattern.sub(f"{indent}{field} {value}", block, count=1)
    open_brace = block.find("{")
    if open_brace < 0:
        raise ValueError("车辆节点块缺少左花括号")
    insert_at = block.find("\n", open_brace)
    if insert_at < 0:
        raise ValueError("车辆节点块不是多行格式")
    return block[: insert_at + 1] + f"  {field} {value}\n" + block[insert_at + 1 :]


def _find_def_block(source: str, def_name: str) -> tuple[int, int, str]:
    """定位指定 DEF 节点的花括号块。"""

    match = re.search(rf"\bDEF\s+{re.escape(def_name)}\s+\w+\s*\{{", source)
    if not match:
        raise ValueError(f"world 中找不到 DEF {def_name}")
    start = match.start()
    index = source.find("{", match.start())
    depth = 0
    for pos in range(index, len(source)):
        char = source[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return start, pos + 1, source[start : pos + 1]
    raise ValueError(f"DEF {def_name} 节点花括号未闭合")


def build_teleport_world(source_world: Path, output_world: Path, car_slot: str, pose: dict, z: float) -> None:
    """写出临时跳点 world。

    参数：`source_world` 是原始赛道；`output_world` 是临时 world；`car_slot` 是 DEF 名；
        `pose` 来自 telemetry；`z` 是车体初始高度。
    返回：无。
    逻辑：telemetry heading 与 Webots z 轴 rotation 的符号相反，故 rotation angle = -heading。
    """

    source = source_world.read_text(encoding="utf-8")
    start, end, block = _find_def_block(source, car_slot)
    heading = float(pose["heading"])
    block = _replace_field(block, "translation", f"{pose['x']:.6f} {pose['y']:.6f} {z:.6f}")
    block = _replace_field(block, "rotation", f"0 0 1 {-heading:.9f}")
    output_world.parent.mkdir(parents=True, exist_ok=True)
    output_world.write_text(source[:start] + block + source[end:], encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""

    parser = argparse.ArgumentParser(description="Create a temporary Webots world with one car teleported.")
    parser.add_argument("--world", default="complex", help="basic/complex 或 .wbt 路径")
    parser.add_argument("--telemetry", type=Path, default=DEFAULT_TELEMETRY)
    parser.add_argument("--time", type=float, required=True, help="目标 telemetry 时间")
    parser.add_argument("--team-id", default=None, help="可选：限定 telemetry 中的 team_id")
    parser.add_argument("--car-slot", default="car_1")
    parser.add_argument("--z", type=float, default=0.4)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pose-out", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    """脚本入口。"""

    args = parse_args()
    source_world = DEFAULT_WORLDS.get(args.world, Path(args.world).expanduser())
    source_world = source_world.resolve()
    telemetry = args.telemetry.expanduser().resolve()
    output_world = args.out.expanduser().resolve()
    pose = _load_pose(telemetry, args.time, team_id=args.team_id)
    build_teleport_world(source_world, output_world, args.car_slot, pose, args.z)
    if args.pose_out:
        args.pose_out.parent.mkdir(parents=True, exist_ok=True)
        args.pose_out.write_text(json.dumps(pose, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"teleport world: {output_world} "
        f"(source={source_world.name}, t={pose['t']:.3f}, x={pose['x']:.3f}, "
        f"y={pose['y']:.3f}, heading={pose['heading']:.4f}, speed={pose['speed']:.2f})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
