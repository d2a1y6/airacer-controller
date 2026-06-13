#!/usr/bin/env bash
# 无人值守 6 车 Webots 实跑 + 看门狗：后台启动 Webots，监控控制日志增长，
# 到达硬超时 或 日志静止（比赛结束但 Webots 没自动退）即杀进程收尾。
# 供 AI 自跑（用户睡觉时）用：跑完日志留在 .tmp/multicar/，AI 离线分析。
#
# 用法：
#   bash scripts/webots_auto_multicar.sh <world> <max_sec> [idle_sec] [ncars]
#   bash scripts/webots_auto_multicar.sh complex 300
#   bash scripts/webots_auto_multicar.sh basic 70 20 1      # 探路：单车短跑
#
# 产物同 webots_day_multicar.sh：.tmp/multicar/{control,contact}_<world>_car1.jsonl 等
set -uo pipefail

SDK=/Users/day/Desktop/Github/pkudsa.airacer/sdk
WORLD=${1:-complex}
MAX=${2:-300}
IDLE=${3:-25}
NCARS=${4:-6}
OPP_SPEED_SCALE=${5:-1.0}   # <1 = 慢速对手（追上并超车的纯超车测试）

pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
sleep 1

rm -rf .tmp/multicar
mkdir -p .tmp/multicar/frames_${WORLD}_car1 .tmp/multicar/webots_console

# 我方 car_1 debug（控制日志 + 抽帧）
python scripts/build_submission.py --mode fastest \
  --debug-log ".tmp/multicar/control_${WORLD}_car1.jsonl" \
  --dump-frames ".tmp/multicar/frames_${WORLD}_car1" --dump-frame-stride 10 \
  --out .tmp/multicar/team_controller_car1_debug.py || exit 1
# 对手普通构建（无 debug I/O）
python scripts/build_submission.py --mode fastest \
  --out .tmp/multicar/team_controller_opp.py || exit 1
# 可选：给对手追加速度缩放包装（慢速对手=纯超车测试）。control 后定义者生效。
if [[ "$OPP_SPEED_SCALE" != "1.0" ]]; then
  cat >> .tmp/multicar/team_controller_opp.py <<PYEOF

_orig_control = control
def control(left_img, right_img, timestamp):
    s, v = _orig_control(left_img, right_img, timestamp)
    return s, v * ${OPP_SPEED_SCALE}
PYEOF
fi

export AIRACER_CONTROLLER_CONSOLE_LOG_DIR="$PWD/.tmp/multicar/webots_console"
export AIRACER_CONTACT_LOG=1
export AIRACER_CONTACT_LOG_PATH="$PWD/.tmp/multicar/contact_${WORLD}_car1.jsonl"

CAR1="$PWD/.tmp/multicar/team_controller_car1_debug.py"
OPP="$PWD/.tmp/multicar/team_controller_opp.py"

CAR_ARGS=(--car "${CAR1}:car_1:fastest")
for slot in 2 3 4 5 6; do
  [[ "$slot" -le "$NCARS" ]] && CAR_ARGS+=(--car "${OPP}:car_${slot}:opp")
done

echo "[auto] world=$WORLD ncars=$NCARS max=${MAX}s idle=${IDLE}s opp_speed_scale=${OPP_SPEED_SCALE}"
python "$SDK/run_local.py" --world "$WORLD" "${CAR_ARGS[@]}" --skip-validate \
  > .tmp/multicar/webots_launch.log 2>&1 &
RL_PID=$!

LOG=".tmp/multicar/control_${WORLD}_car1.jsonl"
start=$(date +%s); last_size=-1; last_change=$start
while kill -0 "$RL_PID" 2>/dev/null; do
  now=$(date +%s)
  if (( now - start >= MAX )); then echo "[auto] hard cap ${MAX}s reached"; break; fi
  size=$(stat -f%z "$LOG" 2>/dev/null || echo 0)
  if [[ "$size" != "$last_size" ]]; then last_size=$size; last_change=$now; fi
  if (( size > 0 && now - last_change >= IDLE && now - start > 45 )); then
    echo "[auto] control log idle ${IDLE}s (race likely ended)"; break
  fi
  sleep 3
done

pkill -f webots 2>/dev/null || true
pkill -f run_local 2>/dev/null || true
wait "$RL_PID" 2>/dev/null
elapsed=$(( $(date +%s) - start ))
fsize=$(stat -f%z "$LOG" 2>/dev/null || echo 0)
frames=$(wc -l < "$LOG" 2>/dev/null || echo 0)
echo "[auto] DONE world=$WORLD elapsed=${elapsed}s control_log_bytes=$fsize control_frames=$frames"
