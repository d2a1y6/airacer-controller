# R026 first left tight radius

## trajectory_speed.png
- 展示：R026 complex 整场轨迹与速度。
- 来源：R026，complex，car_1，telemetry=`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`；`python scripts/plot_run.py --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl --out experiments/figures/R026_first_left_tight_radius/trajectory_speed.png --title "R026 complex Phase1 first-left tight radius"`。
- 看点：最长爬行段在第一个左转，`t≈33.8→47.8`，位置约 `x=188.6,y=-27.1 → x=188.9,y=-26.9`，说明问题集中在转弯半径过小和内切后低速爬行。

## overlay_000031_360.png
- 展示：第一个左转主问题帧的左右相机感知标注。
- 来源：R026 保存帧 `.tmp/run/frames_complex` + 控制日志 `.tmp/run/control_complex.jsonl`；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir experiments/figures/R026_first_left_tight_radius --at 31.36,33.8,47.8`。
- 看点：原控制日志此刻 `line_conf=0`，但保存帧用当前 Phase 2 代码回放可得到 `line_offset≈+0.43,line_conf≈0.8`，说明旧问题是弯中虚线漏检和 offset 信任门过窄。

## overlay_000033_920.png
- 展示：车进入最长爬行段后的感知标注。
- 来源：同上，最近帧 `t≈33.92`。
- 看点：控制日志里 `line_conf=0`，`target_steering≈0`，车辆已经处在低速窗口，说明入弯阶段没有被白线及时带回中心。

## overlay_000047_680.png
- 展示：最长爬行段尾部的感知标注。
- 来源：同上，最近帧 `t≈47.68`。
- 看点：控制日志仍为 `line_conf=0`，车靠恢复/道路几何慢慢离开爬行段；该图用于和修复后同一窗口对比。

## live_view.png
- 展示：本轮停止时的 Webots 顶视图。
- 来源：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/live_view.jpg` 复制而来。
- 看点：作为整场位置对照，不用于判断 case 是否已修复。
