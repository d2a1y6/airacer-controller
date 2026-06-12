# R042 → R049 入弯调试图组

这组图只讲“入弯 / 转弯半径”这条线。提速相关证据单独放在：

```text
experiments/figures/R045_to_R049_speed_evolution/
```

## 一句话结论

R041 以前的核心问题不是舵角不够，也不是弯中白线修正不够，而是**入弯太早**：车还在线上、还没物理到弯口，就被远处 road-mask 的 `heading/lookahead` 拉进弯内。R042 把入弯门控改成近处 `lateral` 判据，R047 再让门控随速度提前，R048 加 latch 保持弯中转向，R049 是当前最佳实跑版本。

## 调试主线

### R041：后验补救没解决入弯太早

**调了什么**：R039/R040/R041 主要在车已经切进内侧后补救，例如增强 line correction、corner relief 和 relief hold。

**当时思路**：如果白线显示车已经在内侧，就削弱 road-mask 远处预瞄，让车回到白线。

**结果**：最紧弯仍撞栏。接触日志抓到 t≈230 的硬接触，峰值 12 个 contact 点，`zmax≈0.53`。控制日志显示 commit 时 `lateral≈0`、`line_offset≈0`，车还居中；后验补救在这个阶段根本没有触发。

**证据图**：

- `r041_r042_turn_in_before_after.png`
- `tight_corner_control_progression.png`

### R042 / R043：把 arrival 改成近处 lateral

**调了什么**：入弯门控从 `heading + lateral` 改成主要看近处 `|lateral_error|`。R043 继续删掉 `turn_in_floor`，让远处预瞄在还没到弯口时可以被压到接近 0。

**思路**：`heading/lookahead` 是远处弯量，会在直道接近段提前变大；它不能同时当“要往哪转”和“弯到了没”。`lateral` 更接近物理到达弯口的信号：直道接近段接近 0，车保持中线进入弯口后才逐步长大。

**效果**：同一个最紧左弯里，commit 从 R041 的 t≈224.16 推迟到 R042 的 t≈227.14；commit 时车不再完全居中，而是已经接近弯口。弯中 `line_offset` 峰值从约 +0.65 降到 +0.23，原来的硬撞消失。

**副作用 / 残留**：R042-b 继续把 `turn_in_floor` 降到 0.11、`turn_in_lateral_ref` 调到 0.30 后，硬撞变轻，但仍有轻擦。说明根因方向对，但纯静态门控还不够。

**证据图**：

- `r041_r042_turn_in_before_after.png`
- `turn_in_gate_shape.png`

### R044：尝试按弯急缓调 delay，后来证明方向错

**调了什么**：加了 `curve_risk` 调制。急弯不额外迟滞，缓弯把 `arrival_ref` 放大，让车晚一点转。

**思路**：当时观察到 90 度急弯已经基本能过，缓一些的弯还偏内，所以想让缓弯更晚入弯。

**效果**：离线看缓弯舵角确实略小，急弯基本不变；但实跑后暴露结构问题。

**为什么删掉**：入弯瞬间 `curve_risk` 往往偏低，因为弯还没在视野里充分展开。于是急弯入口也会被误判成 gentle，导致车深入弯里才突然急打轮，半径反而过大、速度也掉。R046 删除这条分支。

**证据图**：

- `r044_gentle_corner_overlay.png`
- `turn_in_debug_timeline.png`

### R046：回到干净的 lateral gate

**调了什么**：删除 `turn_in_sharp_ref` / `turn_in_gentle_extra` 以及对应的 sharpness 分支，保留单一 lateral gate。

**思路**：入弯时机应该由近处物理到达决定，不应该由一个入弯早期不稳定的弯急缓估计决定。

**效果**：删掉了 R044 的过度迟滞问题，但新问题出现：提速后，同一个 lateral gate 在高速下开得太晚。

### R047：入弯时机和速度耦合

**调了什么**：加入 `turn_in_speed_comp`。速度越高，有效 `arrival_ref` 越小，门越早打开；同时放松高速 steering cap。

**思路**：几何门控只看 `lateral`，但车速越高，车在 `lateral` 长起来前已经多跑了很远。旧的“效果好版本”之所以好，一部分原因是更慢。提速后要保持同样入弯轨迹，就必须让高速时门更早开。

**效果**：第一个 90 度左弯不再因为高速入口 + 小舵角而明显冲外。这个修法比 `curve_risk` 调制更可靠，因为速度在入弯瞬间已经稳定可用。

**证据图**：

- `turn_in_gate_shape.png`
- `r049_first_left_overlay.png`

### R048：给 gate 加 latch，避免弯中突然收轮

**调了什么**：给入弯 gate 加跨帧 latch。在 `hard_turn` 内，gate ratchet 到峰值后保持；离开 `hard_turn` 后按 `turn_in_hold_decay` 缓慢衰减。

**思路**：连续 gate 原本只想延迟入弯，但它也会在弯中杀掉远处预瞄。日志显示 `heading/lookahead` 还在强烈要求继续转，`lateral` 却因为 road-mask 重新居中掉回 0，gate 跟着塌掉，车就转到一半收轮。

**效果**：弯中保持转向，出弯再慢慢收轮。它解决的是“入弯后半段 / 出弯”的半径问题，不是入口时机。

**证据图**：

- `tight_corner_control_progression.png`
- `r049_first_left_light_contact_overlay.png`

### R049：当前最佳入弯状态

**调了什么**：入弯结构沿用 R047/R048，速度侧继续定向提中等弯速度。

**效果**：当前最佳 complex run 的控制日志 `lost=0`，mean command speed≈0.850，contact 只有 peak=3 / `zmax≤0.50` 的轻擦，没有 R041 那种硬撞卡死。入弯根因已经解决。

**残留**：两个肉眼类似的弯仍可能半径不同。原因不是 gate 本身，而是感知给出的 `curve_risk` 不一致，导致速度不同，物理半径也不同。这是下一阶段的感知一致性问题。

**证据图**：

- `r049_first_left_overlay.png`
- `r049_mid_corner_overlay.png`

## 图片说明

### `turn_in_debug_timeline.png`

R041→R049 的入弯调试路线图。它把这段工作拆成几个机制节点：后验 relief、R042 根因修复、R044 失败分支、R046 简化、R047 速度耦合、R048 latch、R049 当前最佳。

### `turn_in_gate_shape.png`

门控形状示意图。红线表示旧逻辑里 `heading` 会提前打开 gate；蓝线是纯 lateral gate；紫线是高速下的 speed-coupled gate。它解释为什么 R047 不是乱加复杂度，而是在提速后补偿物理距离。

### `r041_r042_turn_in_before_after.png`

R041 与 R042 在同一最紧左弯的对照。重点看 commit 时机、`lateral` 和 `line_offset`：R041 在车还居中时就开始切入，R042 等车真正到弯口后再转。

### `tight_corner_control_progression.png`

R041/R042/R044/R049 的同类紧弯控制量对比。用于报告里展示“不是一次调参运气好，而是一串机制修正逐步压住 line_offset 峰值”。

### `r044_gentle_corner_overlay.png`

R044 试图处理缓弯时保留的画面。它适合放在报告里讲失败分支：缓弯调制看似合理，但 `curve_risk` 在入弯入口不稳定，最后被删。

### `r049_first_left_overlay.png`

R049 第一个急左弯中段 overlay。红点是 road center 采样，黄色是白线候选。用于证明当前版本在急弯里仍有可用感知输入，不是盲转。

### `r049_first_left_light_contact_overlay.png`

R049 第一个急左弯出弯 / 轻擦附近。contact episode 的峰值只有 3、`zmax≈0.50`，可用于区分“轻擦边界”和 R041 的硬撞。

### `r049_mid_corner_overlay.png`

R049 中段代表性弯道。用于说明当前残留更像速度 / 半径边界与感知一致性问题，不是入弯根因复发。

## 数据来源

- R041/R042/R042-b/R044 控制窗口：`experiments/cases/R042_turn_in_too_early/*.jsonl`
- R049 控制日志与 contact：`.tmp/run.archive/run_basic_20260613_011637/control_complex.jsonl`、`contact_complex.jsonl`
- R049 overlay：`.tmp/run.archive/run_basic_20260613_011637/frames_complex`
- 叙事来源：`experiments/notes.md` R042–R049；`/Users/day/Downloads/claude聊天记录.md` 只是生成图组时参考过的外部聊天记录，不属于仓库证据。后续接手以仓库内 notes、case 和日志摘要为准。

## 报告建议

这组图适合按三段讲：

1. **发现根因**：R041/R042 对照说明“入弯太早”。
2. **排除错误路线**：R044/R046 说明 `curve_risk` 入弯调制为什么被删。
3. **稳定机制**：R047/R048/R049 说明高速和弯中保持怎样补上最后的动态问题。
