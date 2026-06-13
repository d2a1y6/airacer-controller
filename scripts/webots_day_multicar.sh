#!/usr/bin/env bash
# 6 车 Webots 实跑：复现 R052 的多车拥堵 + 卡死/夹角场景，验证倒车脱困。
#
# car_1 = 我方 debug 构建（带逐帧控制日志 + 抽帧 + 撞栏接触日志）。
# car_2..car_6 = 同一套控制器的普通构建（移动对手），制造真实多车交通与 CP3 拥堵。
#
# 用法：
#   bash scripts/webots_day_multicar.sh            # 默认 complex，6 车
#   bash scripts/webots_day_multicar.sh complex
#   bash scripts/webots_day_multicar.sh basic
#   bash scripts/webots_day_multicar.sh complex --no-frames   # 不抽帧（更快）
#
# 产物：
#   .tmp/multicar/control_<world>_car1.jsonl   ← 我方逐帧控制日志（看倒车相位/escaping）
#   .tmp/multicar/contact_<world>_car1.jsonl   ← 撞栏接触日志（看是否还撞栏）
#   .tmp/multicar/frames_<world>_car1/         ← 抽帧（感知复盘）
#   .tmp/multicar/webots_console/              ← 各车 stdout/stderr
#
# 复盘命令：
#   python scripts/analyze_control_log.py .tmp/multicar/control_complex_car1.jsonl
#   python scripts/analyze_contact_log.py .tmp/multicar/contact_complex_car1.jsonl
set -euo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:-complex}
shift || true

DUMP_FRAMES=1
STRIDE=10
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-frames) DUMP_FRAMES=0; shift ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
done

# 1. 清理孤儿进程（避免 telemetry 交错）
pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1

# 2. 准备输出目录
rm -rf .tmp/multicar
mkdir -p .tmp/multicar/frames_${WORLD}_car1
mkdir -p .tmp/multicar/webots_console

# 3. 构建我方 car_1 debug 控制器（逐帧日志 + 可选抽帧）
FRAMES_ARGS=()
if [[ "$DUMP_FRAMES" -eq 1 ]]; then
  FRAMES_ARGS+=(--dump-frames ".tmp/multicar/frames_${WORLD}_car1" --dump-frame-stride "$STRIDE")
fi
python scripts/build_submission.py --mode fastest \
  --debug-log ".tmp/multicar/control_${WORLD}_car1.jsonl" \
  ${FRAMES_ARGS[@]+"${FRAMES_ARGS[@]}"} \
  --out .tmp/multicar/team_controller_car1_debug.py

# 4. 构建对手普通控制器（无 debug I/O，5 辆共用）
python scripts/build_submission.py --mode fastest \
  --out .tmp/multicar/team_controller_opp.py

# 5. 接触日志 + console 日志环境变量
export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/multicar/webots_console"
export AIRACER_CONTACT_LOG=1
export AIRACER_CONTACT_LOG_PATH="$PWD/.tmp/multicar/contact_${WORLD}_car1.jsonl"

CAR1="$PWD/.tmp/multicar/team_controller_car1_debug.py"
OPP="$PWD/.tmp/multicar/team_controller_opp.py"

echo "world=$WORLD  6-car  frames=$DUMP_FRAMES"
echo "control log → .tmp/multicar/control_${WORLD}_car1.jsonl"
echo "contact log → .tmp/multicar/contact_${WORLD}_car1.jsonl"

# 6. 启动 6 车 Webots（多车模式只用 --car，不能同时传 --code-path）
python "$SDK/run_local.py" \
  --world "$WORLD" \
  --car "${CAR1}:car_1:fastest" \
  --car "${OPP}:car_2:opp" \
  --car "${OPP}:car_3:opp" \
  --car "${OPP}:car_4:opp" \
  --car "${OPP}:car_5:opp" \
  --car "${OPP}:car_6:opp" \
  --skip-validate 2>&1 | tee .tmp/multicar/webots_launch.log
