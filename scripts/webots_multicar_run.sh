#!/usr/bin/env bash
# 多车极端场景 Webots 测试：构建多车 debug 控制器并启动。
#
# 用法：
#   # 双车 basic（我方 fastest vs 对手 safe）
#   bash scripts/webots_multicar_run.sh basic
#
#   # 双车 complex
#   bash scripts/webots_multicar_run.sh complex
#
#   # 只跑单一极端场景，不存帧（更快）
#   bash scripts/webots_multicar_run.sh basic --no-frames
#
#   # 自定义每个车位的控制器和 team 名称
#   bash scripts/webots_multicar_run.sh basic \
#     --slot1 submissions/with_other_cars/team_controller.py:car_1:fastest \
#     --slot2 submissions/with_other_cars/team_controller.py:car_2:opp
#
# 产物（每车独立）：
#   .tmp/multicar/control_<world>_car1.jsonl
#   .tmp/multicar/control_<world>_car2.jsonl
#   .tmp/multicar/contact_<world>_car1.jsonl
#   .tmp/multicar/frames_<world>_car1/
#   .tmp/multicar/webots_console/
#
# 极端场景可通过 --scenario 选择：
#   bash scripts/webots_multicar_run.sh basic --scenario blocked_front
#   bash scripts/webots_multicar_run.sh basic --scenario rear_rammed
#   bash scripts/webots_multicar_run.sh basic --scenario railing_stuck
#
# 场景说明见 docs/multicar_extreme_tests.md
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:?用法: scripts/webots_multicar_run.sh <basic|complex> [--scenario S] [--no-frames] [--slot1 ...] [--slot2 ...]}
shift || true

DUMP_FRAMES=1
STRIDE=10
CONTACT_LOG=1
SCENARIO=""
SLOT1=""
SLOT2=""

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
    --scenario)
      SCENARIO="${2:?--scenario 需要场景名}"
      shift 2
      ;;
    --slot1)
      SLOT1="${2:?--slot1 需要 controller_path:slot:team}"
      shift 2
      ;;
    --slot2)
      SLOT2="${2:?--slot2 需要 controller_path:slot:team}"
      shift 2
      ;;
    *)
      echo "未知参数: $1" >&2
      exit 2
      ;;
  esac
done

# 1. 清理孤儿进程
pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1

# 2. 准备输出目录
rm -rf .tmp/multicar
mkdir -p .tmp/multicar/frames_${WORLD}_car1
mkdir -p .tmp/multicar/webots_console
echo "team_controller stdout/stderr tee → $PWD/.tmp/multicar/webots_console/"

# 3. 构建我方 debug 控制器（car_1，始终构建）
FRAMES_ARGS=()
if [[ "$DUMP_FRAMES" -eq 1 ]]; then
  FRAMES_ARGS+=(--dump-frames ".tmp/multicar/frames_${WORLD}_car1" --dump-frame-stride "$STRIDE")
fi

python scripts/build_submission.py --mode with_other_cars \
  --debug-log ".tmp/multicar/control_${WORLD}_car1.jsonl" \
  ${FRAMES_ARGS[@]+"${FRAMES_ARGS[@]}"} \
  --out .tmp/multicar/team_controller_car1_debug.py

# 4. 构建对手控制器（car_2，无帧）
python scripts/build_submission.py --mode with_other_cars \
  --debug-log ".tmp/multicar/control_${WORLD}_car2.jsonl" \
  --out .tmp/multicar/team_controller_car2_debug.py

# 5. 设置 car slot 参数
if [[ -z "$SLOT1" ]]; then
  SLOT1="$PWD/.tmp/multicar/team_controller_car1_debug.py:car_1:fastest"
fi
if [[ -z "$SLOT2" ]]; then
  SLOT2="$PWD/.tmp/multicar/team_controller_car2_debug.py:car_2:safe"
fi

# 6. 启动 Webots 多车
export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/multicar/webots_console"

if [[ "$CONTACT_LOG" -eq 1 ]]; then
  export AIRACER_CONTACT_LOG=1
  export AIRACER_CONTACT_LOG_PATH="$PWD/.tmp/multicar/contact_${WORLD}_car1.jsonl"
  echo "contact (rail) log → $PWD/.tmp/multicar/contact_${WORLD}_car1.jsonl"
fi

echo "run_local/Webots launch log → $PWD/.tmp/multicar/webots_launch.log"
echo "场景: ${SCENARIO:-default}"
echo "car_1: $SLOT1"
echo "car_2: $SLOT2"

python "$SDK/run_local.py" \
  --world "$WORLD" \
  --car "$SLOT1" \
  --car "$SLOT2" \
  --skip-validate 2>&1 | tee .tmp/multicar/webots_launch.log
