# R032 R018 window pass

## trajectory_speed.png
- 展示：R032 complex 从头短测轨迹与速度，覆盖 R018 的 `t≈289→296` 风险窗口后主动停止。
- 来源：R032，complex，car_1，telemetry=/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl；`python scripts/plot_run.py --telemetry ... --out experiments/figures/R032_r018_window_pass/trajectory_speed.png --title "R032 complex R018-window pass"`。
- 看点：`t=280→330` 无事件、无近停，旧 `x≈9,y≈87` 内切卡点未复现；这张图不证明整场跑通。

## overlay_000289_344.png
- 展示：t=289.344s，R018 旧风险入口附近的感知标注。
- 来源：R032，frames_complex + control_complex.jsonl；`python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir .tmp/diagnose_r032_r018_window --at 289.4,296.0,314.3,329.9,351.0`。
- 看点：白线点在路面中间虚线附近，远处栏杆没有被当成中心线。

## overlay_000296_064.png
- 展示：t=296.064s，R018 旧“居中时突然大舵切内线”窗口附近。
- 来源：同上。
- 看点：弯中白线仍可见，控制日志 lost 为 0，telemetry 状态 normal。

## overlay_000329_856.png
- 展示：t=329.856s，R018 风险窗口之后的直道段。
- 来源：同上。
- 看点：车已离开风险窗口并高速行驶，作为本轮短测的收尾证据。
