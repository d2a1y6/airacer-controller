# R002 丢线离线分析

## 夜间工作小结

- 已完成 P1：`scripts/analyze_control_log.py` 增加丢线诊断段，并用合成 JSONL fixture 覆盖连续 lost 段、flag 解码、进入 lost 前 mode、弯道关联对比。
- R002 的关键结论：27% 丢线主要来自感知层没有稳定产出中心点。lost 帧里 `obs_points` 的 median/p90 都是 0，`debug_flags` 以有效扫描线过少和 mask 填充率极端为主。
- 还没做：P2 工具加固、P2.5 存帧调试构建、P3 离线回放骨架。

## 数据来源

- 控制日志：`.tmp/run/control_basic.jsonl`
- 记录：R002 basic 干净基线，10222 帧，`t=0.03→327.10`
- 工具：`python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl`

这份分析只用本地已有日志，没有跑 Webots，不往 `experiments/runs.csv` 记账。

## 关键数字

- lost 帧：2744 / 10222，占比 0.27。
- 连续 lost 段：114 段，最长 154 帧，段长 median=30 帧，p90=39 帧，mean=24.1 帧。
- lost 帧置信度和点数：
  - `track_conf`: mean=0.007，median=0.000，p90=0.000。
  - `obs_conf`: mean=0.019，median=0.000，p90=0.000。
  - `obs_points`: mean=0.190，median=0.000，p90=0.000。
  - `road_width`: mean=37.653，median=0.000，p90=0.000。
- lost 帧 `debug_flags`：
  - 有效扫描线过少：2716 帧，占 lost 帧 0.99。
  - mask 填充率极端：2519 帧，占 lost 帧 0.92。
  - 用了边缘 fallback：238 帧，占 lost 帧 0.09。
  - 左右置信度接近：185 帧，占 lost 帧 0.07。
  - 左右近处中心偏差大：7 帧，基本可以忽略。
- 进入 lost 前一帧 mode：
  - `cruise`: 52 段，占 0.46。
  - `recovering`: 33 段，占 0.29。
  - `hard_turn`: 26 段，占 0.23。
  - `lost`: 3 段，占 0.03。这个来自日志中短暂断续的 lost 标记，不影响大趋势。
- 弯道相关：
  - `|curvature|` mean：lost=0.014，non_lost=0.191。
  - `|heading|` mean：lost=0.016，non_lost=0.105。

## 根因初判

R002 的 27% 丢线不像是急弯几何导致的控制层问题。lost 帧的 `|curvature|` 和 `|heading|` 都低于非 lost 帧，进入 lost 前也只有 23% 来自 `hard_turn`。更多 lost 段从 `cruise` 或 `recovering` 进入。

更像的链路是：`perception.py` 里道路 mask 或扫描段选择先失败，导致有效扫描线几乎没有，`obs_points` 归零，估计器只能进入 lost。`debug_flags` 同时显示 mask 填充率常处于极端状态，说明要优先查 `_build_masks()` 到 `_scan_camera()` 这段，而不是先调 `policy.py` 的速度或转向参数。

## 明早建议

1. 先定位 `mask填充率极端 + 有效扫描线过少` 同时出现的画面。P2.5 的存帧和 P3 的离线回放就是为这个准备的。
2. 重点看 `perception.py` 中 `_build_masks()` 的道路 mask 覆盖率、`_pick_segment()` 的候选段过滤、以及 `_score_scan()` 对低点数的降权路径。
3. 暂时不要改速度、丢线速度或急弯参数。当前慢的直接原因是 lost 触发后的限速，但根因在感知输出中断。
