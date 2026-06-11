#!/usr/bin/env bash
# 从 telemetry 里的某个时间点近似启动 Webots，用于快速取相机帧/截图。
#
# 注意：这是调试取证工具，不是正式验证。它只恢复车的初始 x/y/heading，
# 不恢复速度、轮胎/悬挂物理状态、controller 内部记忆和仿真时钟。
#
# 用法：
#   scripts/webots_jump_run.sh complex 144 --duration 8 --frames 1
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:?用法: scripts/webots_jump_run.sh <basic|complex> <telemetry_time> [--duration N] [--frames N]}
TARGET_TIME=${2:?用法: scripts/webots_jump_run.sh <basic|complex> <telemetry_time> [--duration N] [--frames N]}
shift 2

DURATION=8
FRAME_STRIDE=1
TELEMETRY="$SDK/.local/recordings/telemetry.jsonl"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --duration)
      DURATION=${2:?--duration 需要秒数}
      shift 2
      ;;
    --frames)
      FRAME_STRIDE=${2:?--frames 需要 stride 数字}
      shift 2
      ;;
    --telemetry)
      TELEMETRY=${2:?--telemetry 需要 telemetry.jsonl 路径}
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
done

pkill -f Webots 2>/dev/null || true
pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1

if [[ -d .tmp/jump_run ]]; then
  rm -rf .tmp/jump_run.prev
  mv .tmp/jump_run .tmp/jump_run.prev
fi
mkdir -p .tmp/jump_run/webots_console .tmp/jump_run/frames

JUMP_WORLD="$SDK/webots/worlds/.codex_jump_${WORLD}_car_1.wbt"
cleanup() {
  if [[ -n "${RUN_PID:-}" ]]; then
    kill "$RUN_PID" 2>/dev/null || true
  fi
  pkill -f "$JUMP_WORLD" 2>/dev/null || true
  sleep 1
  if [[ -n "${RUN_PID:-}" ]]; then
    kill -9 "$RUN_PID" 2>/dev/null || true
  fi
  pkill -9 -f "$JUMP_WORLD" 2>/dev/null || true
  rm -f "$JUMP_WORLD"
}
trap cleanup EXIT

python scripts/make_teleport_world.py \
  --world "$WORLD" \
  --telemetry "$TELEMETRY" \
  --time "$TARGET_TIME" \
  --car-slot car_1 \
  --out "$JUMP_WORLD" \
  --pose-out .tmp/jump_run/pose.json

rm -f "$SDK/.local/recordings/telemetry.jsonl"

python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/jump_run/control_${WORLD}.jsonl \
  --dump-frames .tmp/jump_run/frames \
  --dump-frame-stride "$FRAME_STRIDE" \
  --dump-frame-start 0 \
  --dump-frame-end "$DURATION" \
  --out .tmp/jump_run/team_controller_debug.py

export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/jump_run/webots_console"
python "$SDK/run_local.py" \
  --code-path "$PWD/.tmp/jump_run/team_controller_debug.py" \
  --world "$JUMP_WORLD" --car-slot car_1 --skip-validate &
RUN_PID=$!

for _ in $(seq 1 600); do
  sleep 1
  current_time=$(python - <<'PY'
import json
from pathlib import Path
path = Path("/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl")
last = 0.0
if path.exists():
    for line in path.open():
        try:
            last = float(json.loads(line).get("t", 0.0))
        except Exception:
            pass
print(last)
PY
)
  if python - <<PY
import sys
sys.exit(0 if float("$current_time") >= float("$DURATION") else 1)
PY
  then
    echo "jump monitor: reached t=$current_time, stopping"
    cleanup
    break
  fi
  if ! kill -0 "$RUN_PID" 2>/dev/null; then
    break
  fi
done

wait "$RUN_PID" || true
