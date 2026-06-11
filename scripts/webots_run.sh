#!/usr/bin/env bash
# 一键本地 Webots 调试实跑：清理残留 → 轮换上一轮产物 → 构建 debug 控制器 → 启动 run_local。
#
# 默认每轮都保存相机帧（无损 PNG，每 10 帧一对，整场约几百 MB），这样跑完后想看任意时间点
# 都不需要重跑——这是过去 codex 反复栽的坑（R024 没存帧 → R025 为看一个窗口又跑了一整圈）。
#
# 用法：
#   scripts/webots_run.sh basic                       # 控制日志 + 默认 PNG 帧（stride 10）
#   scripts/webots_run.sh complex --frames 1          # 改成逐帧保存（精确取证撞栏窗口）
#   scripts/webots_run.sh complex --frame-window 410 430   # 只在该时间窗存帧
#   scripts/webots_run.sh basic --no-frames           # 关掉存帧（只要控制日志、跑得更轻）
#
# 产物：
#   .tmp/run/control_<world>.jsonl       控制日志（始终开启）
#   .tmp/run/frames_<world>/             相机帧 PNG（默认开启，可用 --no-frames 关闭）
#   .tmp/run/webots_console/*.log        Webots controller console 输出
#   .tmp/run.prev/                       上一轮产物（自动轮换保留一轮，再上一轮删除）
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:?用法: scripts/webots_run.sh <basic|complex> [--frames N] [--frame-window S E] [--no-frames]}
shift || true

DUMP_FRAMES=1
STRIDE=10
WINDOW_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-frames)
      DUMP_FRAMES=0
      shift
      ;;
    --frames)
      STRIDE=${2:?--frames 需要 stride 数字，例如 --frames 1}
      DUMP_FRAMES=1
      shift 2
      ;;
    --frame-window)
      START=${2:?--frame-window 需要开始时间}
      END=${3:?--frame-window 需要结束时间}
      WINDOW_ARGS+=(--dump-frame-start "$START" --dump-frame-end "$END")
      DUMP_FRAMES=1
      shift 3
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
done

FRAMES_ARGS=()
if [[ "$DUMP_FRAMES" -eq 1 ]]; then
  FRAMES_ARGS+=(--dump-frames ".tmp/run/frames_${WORLD}" --dump-frame-stride "$STRIDE")
  FRAMES_ARGS+=(${WINDOW_ARGS[@]+"${WINDOW_ARGS[@]}"})
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
mkdir -p .tmp/run/webots_console
echo "Webots controller console → $PWD/.tmp/run/webots_console/*.log"

# 3. 构建 debug 控制器（含 open/json/cv2.imwrite，禁止上传）
python scripts/build_submission.py --mode fastest \
  --debug-log ".tmp/run/control_${WORLD}.jsonl" \
  ${FRAMES_ARGS[@]+"${FRAMES_ARGS[@]}"} \
  --out .tmp/run/team_controller_debug.py

# 4. 启动 Webots（debug 构建必须 --skip-validate）
export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/run/webots_console"
python "$SDK/run_local.py" \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world "$WORLD" --car-slot car_1 --skip-validate
