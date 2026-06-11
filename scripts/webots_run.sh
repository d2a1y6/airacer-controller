#!/usr/bin/env bash
# 一键本地 Webots 调试实跑：清理残留 → 轮换上一轮产物 → 构建 debug 控制器 → 启动 run_local。
#
# 用法：
#   scripts/webots_run.sh basic
#   scripts/webots_run.sh complex --frames 3   # 同时按 stride=3 保存相机帧（很大，仅取证时用）
#
# 产物：
#   .tmp/run/control_<world>.jsonl       控制日志（默认开启）
#   .tmp/run/frames_<world>/             相机帧（仅 --frames 时）
#   .tmp/run.prev/                       上一轮产物（自动轮换保留一轮，再上一轮删除）
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:?用法: scripts/webots_run.sh <basic|complex> [--frames N]}
shift || true

FRAMES_ARGS=()
if [[ "${1:-}" == "--frames" ]]; then
  STRIDE=${2:?--frames 需要 stride 数字，例如 --frames 3}
  FRAMES_ARGS=(--dump-frames ".tmp/run/frames_${WORLD}" --dump-frame-stride "$STRIDE")
fi

# 1. 清理孤儿进程和旧遥测，避免 telemetry 交错（历史上 3/14 次 run 因此不可信）
pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1
rm -f "$SDK/.local/recordings/telemetry.jsonl"

# 2. 轮换上一轮产物：保留一轮供继续复盘，再上一轮删除（清理前先确认 notes 的"下一步"不依赖它）
rm -rf .tmp/run.prev
if [[ -d .tmp/run ]]; then
  mv .tmp/run .tmp/run.prev
fi
mkdir -p .tmp/run

# 3. 构建 debug 控制器（含 open/json/np.save，禁止上传）
python scripts/build_submission.py --mode fastest \
  --debug-log ".tmp/run/control_${WORLD}.jsonl" \
  ${FRAMES_ARGS[@]+"${FRAMES_ARGS[@]}"} \
  --out .tmp/run/team_controller_debug.py

# 4. 启动 Webots（debug 构建必须 --skip-validate）
python "$SDK/run_local.py" \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world "$WORLD" --car-slot car_1 --skip-validate
