# R038 best human residual tight radius

## trajectory_speed.png
- 展示：R038 complex 人工复跑的整场轨迹和速度。
- 来源：R038，complex，car_1，telemetry=`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`；`python scripts/plot_run.py --telemetry ... --out experiments/figures/R038_best_human_residual_tight_radius/trajectory_speed.png --title "R038 complex current best with residual tight-radius turns"`。
- 看点：全程 `t=0.03→330.14s` 无 telemetry 事件、无近停，和人工观察的“能自己蹭出去、没有卡死”一致。

## overlay_000033_600.png
- 展示：第一个左弯中的感知标注。
- 来源：R038，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir experiments/figures/R038_best_human_residual_tight_radius --at 33.57,226.46,315.94`。
- 看点：虚线可见但点数少，弯中仍依赖稀疏白线点纠正，解释为什么第一个左弯已经明显好转但视觉上仍贴内。

## overlay_000226_560.png
- 展示：后段左弯中，白线在近处偏到车右侧。
- 来源：同上，t≈226.56s。
- 看点：这是残余问题的代表帧。控制日志附近 `line_offset` 可到 `0.66` 以上，说明车已经落到白线内侧；白线还没完全丢，但证据少、纠正晚。

## overlay_000315_840.png
- 展示：起点前静态车阵附近的近障碍窗口。
- 来源：同上，t≈315.84s。
- 看点：这不是内弯半径问题；它说明当前最佳版经过车阵附近时触发近障碍感知但没有卡死，和历史起点前卡点不同。
