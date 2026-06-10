# R002 丢线离线分析

## 夜间工作小结

- 已完成 P1：`scripts/analyze_control_log.py` 增加丢线诊断段，并用合成 JSONL fixture 覆盖连续 lost 段、flag 解码、进入 lost 前 mode、弯道关联对比。
- 已完成 P2：两个分析脚本都补了边界测试；control 日志分析现在支持多个文件或目录输入，并会在时间戳回退时只分析最后一段 run。
- 已完成 P2.5：调试构建新增 `--dump-frames DIR` 和 `--dump-frame-stride N`，只在本地调试单文件里注入 `.npy` 存帧，正常 submissions grep 确认不含 `np.save` / `open(`。
- 已完成 P3：新增 `scripts/replay_offline.py` 开环回放骨架，合成帧验证可输出 control 同 schema JSONL，并能直接接 `analyze_control_log.py`。
- R002 的关键结论：27% 丢线主要来自感知层没有稳定产出中心点。lost 帧里 `obs_points` 的 median/p90 都是 0，`debug_flags` 以有效扫描线过少和 mask 填充率极端为主。
- 没有跑 Webots，也没有改 controller、baselines、submissions 或实验台账。

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

---

## C001 候选：区分 mask 近空和 mask 饱和（2026-06-11）

### 离线回放可信度

数据：

- 帧目录：`.tmp/run/frames_basic/`，3019 对左右相机 `.npy`。
- 对应实车控制日志：`.tmp/run/control_frames_basic.jsonl`。
- 校验命令：`python scripts/analyze_perception_dump.py .tmp/run/frames_basic --control-log .tmp/run/control_frames_basic.jsonl --out .tmp/run/perception_basic_before.json --overlay-dir .tmp/run/perception_overlays_before`

结果：

- 3019 帧全部按时间戳 join 到控制日志。
- 离线重算 perception 后，`obs_points / obs_conf / debug_flags` 与实车日志完全一致，复现差异 0。
- 可以把这批 dump 帧当作 perception 逐帧离线指标使用。

### 根因细化

典型丢线帧不是完全没有视觉信息，而是 mask 饱和：

- 示例 overlay：`.tmp/run/perception_overlays_before/overlay_000002_208.png`
- 该帧左右相机 `mask_fill_ratio≈0.926~0.927`，ROI 几乎整块被 road mask 命中。
- 画面里实际道路在上半部可见，底部大面积草地也被暗灰/低饱和规则命中。扫描器仍能取到 3 条左右的中心线，但 `_score_scan()` 把 mask 饱和和 mask 近空都乘以 0.25，单侧置信度被压到融合门槛以下，最终 `obs_points=0`。

这说明旧逻辑把两类情况混在了一起：

- `mask_fill_ratio < 0.015`：近空，确实应重罚。
- `mask_fill_ratio > 0.92`：饱和，不可靠，但画面里仍可能有真实道路边界和车道线，不能和近空一样直接打到不可用。

试过的替代方向：

- 收紧 `early_max_segment_width_ratio`：丢线率上升，中心漂移变大，放弃。
- mask 饱和时强制转 edge fallback：丢线率上升，放弃。
- 调低 estimator 的 `min_center_points` 到 2：开环 lost 只从 14.5% 到 14.3%，收益很小，放弃。

### 改动

只改 perception 置信度缩放：

- 新增 `empty_mask_confidence_scale=0.25`，保留近空 mask 的旧重罚。
- 新增 `saturated_mask_confidence_scale=0.50`，饱和 mask 使用中等惩罚。
- `_score_scan()` 按 `mask_fill_ratio < 0.015` 和 `> 0.92` 分开处理。

这个改动不放宽扫描段选择，不改 policy，不提高速度，也不把随机区域直接当路。它只是允许已有少量稳定扫描线的饱和帧继续输出低置信观测。

### 指标

命令：

```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_basic \
  --control-log .tmp/run/control_frames_basic.jsonl \
  --baseline .tmp/run/perception_basic_before.json \
  --out .tmp/run/perception_basic_after.json \
  --overlay-dir .tmp/run/perception_overlays_after
```

Basic dump 帧：

| 指标 | before | C001 after |
|---|---:|---:|
| perception 丢线帧 | 685 / 3019 | 10 / 3019 |
| perception 丢线率 | 22.7% | 0.3% |
| 正常帧变 lost | - | 0 |
| 已有中心点 mean 漂移 | - | 0.01 px |
| 已有中心点 p95 漂移 | - | 0.00 px |
| 已有中心点最大漂移 | - | 23.50 px |

开环控制日志回放（只说明同一批固定画面下 estimator/policy 接线结果，不能当圈速判断）：

- before 实车采样控制日志：lost 2261 / 9057 = 25.0%，最长 lost 段 154 帧。
- C001 after 开环回放：lost 438 / 3019 = 14.5%，最长 lost 段 14 帧。
- after 仍 lost 的帧多为 `obs_points=2`，已经不是原来的整段 `obs_points=0`；后续如果要继续压，需要单独评估 estimator 对 2 点低置信观测的处理，但本轮不建议顺手改。

Complex holdout：

- 本地没有 `.tmp/run/frames_complex/`，所以没有 complex dump 指标。
- C001 没有使用红色场景特化逻辑；上车前建议先 basic 验证，再补 complex 存帧做 holdout。

### Overlay 复核点

- 原始典型丢线：`.tmp/run/perception_overlays_before/overlay_000002_208.png`
- C001 恢复后的同帧：`.tmp/run/perception_overlays_selected_after/overlay_000002_208.png`
- C001 后仍 lost 示例：`.tmp/run/perception_overlays_after/overlay_000079_296.png`
- 最大中心漂移示例：`.tmp/run/perception_overlays_shift_after/overlay_000236_352.png`

从 overlay 看，恢复帧的扫描点沿可见道路/车道线分布，不是随机草地区域。剩余 lost 示例里道路被护栏/视角遮挡，只剩 1 条扫描线，继续判 lost 是合理的。

### 上车建议

最建议优先验证 C001。它只动 perception 置信度，把整段 `obs_points=0` 的主要根因打掉；没有改速度/转向，也没有把正常帧推成 lost。验证时重点看 basic 是否减少长段 lost、速度是否自然回升，以及 t≈2s、5s 这类直道远路面画面是否更稳定。
