# R029 first left candidate

## trajectory_speed.png
- 展示：R029 complex 短测轨迹与速度，AI 在第一个左弯窗口之后主动停止。
- 来源：R029，complex，car_1，telemetry=/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl；`python scripts/plot_run.py --telemetry ... --out experiments/figures/R029_first_left_candidate/trajectory_speed.png --title "R029 complex first-left candidate"`。
- 看点：第一个左弯窗口没有 R026 的长爬行，状态一直 normal；这张图只证明当前窗口通过，不证明整场跑通。

## overlay_000032_000.png
- 展示：t=32.000s 左弯中段感知标注。
- 来源：R029，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir .tmp/diagnose_r029_first_left --at 31.2,32.0,34.43,35.2,36.03,42.43`。
- 看点：弯中虚线仍在路面内，单目/双目召回后 `line_conf` 不再像 R028 那样长段归零。

## overlay_000034_432.png
- 展示：t=34.432s，R028 残留低速硬左附近。
- 来源：同上。
- 看点：画面中主要白色候选仍是路面虚线，不是护栏支柱；本帧仍有左弯舵角，但 telemetry 没有近停或事件。

## overlay_000042_432.png
- 展示：t=42.432s，出弯后直道。
- 来源：同上。
- 看点：车辆已回到直道中央，高速稳定行驶，是本轮短测通过第一个左弯窗口的收尾证据。
