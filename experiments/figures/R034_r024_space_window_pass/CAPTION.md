# R034 r024 space window pass

## trajectory_speed.png
- 展示：R034 complex 从头跑到旧 R024 空间卡点之后的轨迹与速度。
- 来源：R034，complex，car_1，telemetry=`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`；`python scripts/plot_run.py --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl --out experiments/figures/R034_r024_space_window_pass/trajectory_speed.png --title "R034 complex"`。
- 看点：车辆经过旧 `x≈-42,y≈124` 卡点附近时仍保持 normal，最近点约 `x=-44.0,y=124.0`，没有事件、近停或长时间贴栏。

## overlay_000244_992.png
- 展示：进入旧 R024 空间窗口前的左右相机感知标注。
- 来源：R034，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir experiments/figures/R034_r024_space_window_pass --at 244.99,249.57,253.89,258.11`。
- 看点：白线点沿路面虚线进入弯道，外侧栏杆没有形成中心线候选。

## overlay_000249_600.png
- 展示：接近旧 `x≈-42,y≈124` 卡点时的感知标注。
- 来源：R034，frames_complex + control_complex.jsonl；同上命令。
- 看点：两侧相机白线候选仍在路面中，弯外侧栏杆和路牙被排除在白线点之外。

## overlay_000253_952.png
- 展示：最接近旧卡点后的核心帧，telemetry 最近点约在 `t=253.15s`。
- 来源：R034，frames_complex + control_complex.jsonl；同上命令。
- 看点：白线召回稳定，红点没有贴到远处横向栏杆；这是本轮证明旧空间卡点未复现的关键图。

## overlay_000258_048.png
- 展示：通过旧卡点后的出口帧。
- 来源：R034，frames_complex + control_complex.jsonl；同上命令。
- 看点：车辆已经离开旧卡点附近，白线候选继续落在路面虚线带上，状态仍 normal。
