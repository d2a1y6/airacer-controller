#!/usr/bin/env bash
# 从 telemetry 里的某个时间点近似启动 Webots，用于快速取相机帧/截图。
#
# 注意：这是调试取证工具，不是正式验证。它只恢复车的初始 x/y/heading，
# 不恢复速度、轮胎/悬挂物理状态、controller 内部记忆和仿真时钟。
#
# 用法：
#   scripts/webots_jump_run.sh complex 144 --duration 8
#   scripts/webots_jump_run.sh complex 144 --duration 8 --frames 1  # 逐帧存图
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
ARCHIVE_KEEP=10
WORLD=${1:?用法: scripts/webots_jump_run.sh <basic|complex> <telemetry_time> [--duration N] [--frames N]}
TARGET_TIME=${2:?用法: scripts/webots_jump_run.sh <basic|complex> <telemetry_time> [--duration N] [--frames N]}
shift 2

DURATION=8
FRAME_STRIDE=10
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

archive_jump_path() {
  local src="$1"
  local prefix="$2"
  local ext="${3:-}"
  if [[ ! -e "$src" ]]; then
    return
  fi
  if should_discard_jump_archive_source "$src" "$prefix"; then
    rm -rf "$src"
    echo "discarded empty $prefix archive source → $src"
    return
  fi
  mkdir -p .tmp/jump_run.archive
  local ts
  ts=$(date +%Y%m%d_%H%M%S)
  local dest=".tmp/jump_run.archive/${prefix}_${ts}${ext}"
  local idx=1
  while [[ -e "$dest" ]]; do
    dest=".tmp/jump_run.archive/${prefix}_${ts}_${idx}${ext}"
    idx=$((idx + 1))
  done
  mv "$src" "$dest"
  echo "archived previous $prefix → $PWD/$dest"
  prune_jump_archives ".tmp/jump_run.archive/${prefix}_*"
}

should_discard_jump_archive_source() {
  local src="$1"
  local prefix="$2"
  if [[ -d "$src" ]]; then
    case "$prefix" in
      jump_run_*)
        if find "$src" -type f \( -name 'control_*.jsonl' -o -name 'contact_*.jsonl' -o -name '*.png' \) -size +0 -print -quit | grep -q .; then
          return 1
        fi
        return 0
        ;;
    esac
    return 1
  fi
  if [[ ! -s "$src" ]]; then
    return 0
  fi
  return 1
}

prune_jump_archives() {
  local pattern="$1"
  local archived=()
  local item
  while IFS= read -r item; do
    archived+=("$item")
  done < <(compgen -G "$pattern" | sort -r)
  if (( ${#archived[@]} <= ARCHIVE_KEEP )); then
    return
  fi
  for item in "${archived[@]:ARCHIVE_KEEP}"; do
    rm -rf "$item"
    echo "deleted old archive → $PWD/$item"
  done
}

archive_jump_path .tmp/jump_run "jump_run_${WORLD}"
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

archive_jump_path "$SDK/.local/recordings/telemetry.jsonl" "telemetry_${WORLD}" ".jsonl"

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
  --world "$JUMP_WORLD" --car-slot car_1 --skip-validate > .tmp/jump_run/webots_launch.log 2>&1 &
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
