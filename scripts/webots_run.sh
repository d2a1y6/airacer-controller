#!/usr/bin/env bash
# 一键本地 Webots 调试实跑：清理残留 → 归档上一轮产物 → 构建 debug 控制器 → 启动 run_local。
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
#   .tmp/run/webots_console/*.log        team_controller stdout/stderr 镜像；不是 supervisor/Webots 碰撞日志
#   .tmp/run/webots_launch.log           run_local/Webots 启动终端 stdout/stderr；不保证包含 Webots GUI console 的接触 warning
#   .tmp/run.archive/run_<timestamp>/    旧 run 归档；滚动保留最近 10 个
#   .tmp/run.archive/telemetry_<timestamp>.jsonl 旧 SDK telemetry 归档；滚动保留最近 10 个
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
ARCHIVE_KEEP=10
WORLD=${1:?用法: scripts/webots_run.sh <basic|complex> [--frames N] [--frame-window S E] [--no-frames]}
shift || true

DUMP_FRAMES=1
STRIDE=10
CONTACT_LOG=1          # 结构化撞栏接触日志，默认开（debug-only，由 SDK supervisor 的 env 开关驱动）
WINDOW_ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-frames)
      DUMP_FRAMES=0
      shift
      ;;
    --no-contact)
      CONTACT_LOG=0
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

archive_path() {
  local src="$1"
  local prefix="$2"
  local ext="${3:-}"
  if [[ ! -e "$src" ]]; then
    return
  fi
  if should_discard_archive_source "$src" "$prefix"; then
    rm -rf "$src"
    echo "discarded empty $prefix archive source → $src"
    return
  fi
  mkdir -p .tmp/run.archive
  local ts
  ts=$(date +%Y%m%d_%H%M%S)
  local dest=".tmp/run.archive/${prefix}_${ts}${ext}"
  local idx=1
  while [[ -e "$dest" ]]; do
    dest=".tmp/run.archive/${prefix}_${ts}_${idx}${ext}"
    idx=$((idx + 1))
  done
  mv "$src" "$dest"
  echo "archived previous $prefix → $PWD/$dest"
  prune_archives ".tmp/run.archive/${prefix}_*"
}

should_discard_archive_source() {
  local src="$1"
  local prefix="$2"
  if [[ -d "$src" ]]; then
    case "$prefix" in
      run_*)
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

prune_archives() {
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

FRAMES_ARGS=()
if [[ "$DUMP_FRAMES" -eq 1 ]]; then
  FRAMES_ARGS+=(--dump-frames ".tmp/run/frames_${WORLD}" --dump-frame-stride "$STRIDE")
  FRAMES_ARGS+=(${WINDOW_ARGS[@]+"${WINDOW_ARGS[@]}"})
fi

# 1. 清理孤儿进程和旧遥测，避免 telemetry 交错（历史上 3/14 次 run 因此不可信）
pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1
archive_path "$SDK/.local/recordings/telemetry.jsonl" "telemetry_${WORLD}" ".jsonl"

# 2. 归档上一轮产物：滚动保留最近 10 轮，避免无限增长。
archive_path .tmp/run "run_${WORLD}"
mkdir -p .tmp/run
mkdir -p .tmp/run/webots_console
echo "team_controller stdout/stderr tee → $PWD/.tmp/run/webots_console/*.log"

# 3. 构建 debug 控制器（含 open/json/cv2.imwrite，禁止上传）
#    单车 harness 默认测 no_other_cars(R049) profile；要单车里看多车控制器改 with_other_cars。
python scripts/build_submission.py --mode no_other_cars \
  --debug-log ".tmp/run/control_${WORLD}.jsonl" \
  ${FRAMES_ARGS[@]+"${FRAMES_ARGS[@]}"} \
  --out .tmp/run/team_controller_debug.py

# 4. 启动 Webots（debug 构建必须 --skip-validate）
export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/run/webots_console"
# 结构化撞栏接触日志（SDK supervisor 的 env 开关；不影响提交文件）。撞栏 → contact_<world>.jsonl
# + telemetry events 里的 contact_start/end。判定：车身接触点高于轮子簇 0.25m 才算栏杆/车身接触。
if [[ "$CONTACT_LOG" -eq 1 ]]; then
  export AIRACER_CONTACT_LOG=1
  export AIRACER_CONTACT_LOG_PATH="$PWD/.tmp/run/contact_${WORLD}.jsonl"
  echo "contact (rail) log → $PWD/.tmp/run/contact_${WORLD}.jsonl"
else
  unset AIRACER_CONTACT_LOG
fi
echo "run_local/Webots launch log → $PWD/.tmp/run/webots_launch.log"
python "$SDK/run_local.py" \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world "$WORLD" --car-slot car_1 --skip-validate 2>&1 | tee .tmp/run/webots_launch.log
