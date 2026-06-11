# R031 old window pass

## trajectory_speed.png
- 展示：R031 complex 短测轨迹与速度，覆盖旧 R024/R025 后段内切窗口后主动停止。
- 来源：R031，complex，car_1，telemetry=/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl；`python scripts/plot_run.py --telemetry ... --out experiments/figures/R031_old_window_pass/trajectory_speed.png --title "R031 complex old inner-window pass"`。
- 看点：`t=130→185` 没有旧 `x≈169,y≈111` 长爬行，状态一直 normal；这张图不证明整场跑通。

## overlay_000149_120.png
- 展示：t=149.120s，旧后段窗口内强左舵附近的感知标注。
- 来源：R031，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir .tmp/diagnose_r031_old_window --at 149.1,154.8,168.99,184.8,204.9`。
- 看点：白线候选在路面虚线处，远处栏杆没有进入白线点。

## overlay_000154_752.png
- 展示：t=154.752s，旧后段窗口内低速左弯继续阶段。
- 来源：同上。
- 看点：弯中仍能看到路面虚线，控制日志无 lost，telemetry 无近停。

## overlay_000168_960.png
- 展示：t=168.960s，旧窗口出弯后的直道。
- 来源：同上。
- 看点：车辆已回到直道视角，白线在中间附近，旧长爬行窗口已通过。
