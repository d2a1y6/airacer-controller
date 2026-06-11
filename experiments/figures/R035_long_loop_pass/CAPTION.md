# R035 long loop pass

## trajectory_speed.png
- 展示：R035 complex 长跑到 `t≈399.7s` 的轨迹与速度。
- 来源：R035，complex，car_1，telemetry=`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`；`python scripts/plot_run.py --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl --out experiments/figures/R035_long_loop_pass/trajectory_speed.png --title "R035 complex long loop"`。
- 看点：车辆通过旧 `x≈-42,y≈124`、旧起点前 `x≈-10,y≈-27` / `x≈28,y≈-28`，并进入下一轮早段；全程无事件、无近停。

## overlay_000316_800.png
- 展示：接近旧起点前卡点和车阵区域的左右相机感知标注。
- 来源：R035，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir experiments/figures/R035_long_loop_pass --at 316.8,324.4,357.8,384.3,393.7`。
- 看点：白线点落在中间虚线，旁边车辆和栏杆没有被当成中心线。

## overlay_000324_480.png
- 展示：通过旧起点前卡点附近的直道感知标注。
- 来源：R035，frames_complex + control_complex.jsonl；同上命令。
- 看点：车辆以正常速度穿过旧 `x≈28,y≈-28` 附近，白线候选居中且连续。

## overlay_000357_888.png
- 展示：进入下一轮第一个左弯前后的感知标注。
- 来源：R035，frames_complex + control_complex.jsonl；同上命令。
- 看点：新一轮入弯仍能召回路面虚线，远处栏杆没有形成候选。

## overlay_000393_600.png
- 展示：下一轮上方复合弯入口附近的感知标注。
- 来源：R035，frames_complex + control_complex.jsonl；同上命令。
- 看点：弯道里白线点仍沿路面虚线分布，未见横向栏杆误锁。
