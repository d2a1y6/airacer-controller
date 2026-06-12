# R045 → R049 提速调试图组

这组图只讲“提速”这条线。入弯 / 转弯半径相关证据单独放在：

```text
experiments/figures/R042_to_R049_turn_in_evolution/
```

## 一句话结论

提速不是单纯把目标速度调大。R045 先去掉过保守的全局限速，R047 发现“速度变快会反过来改变入弯半径”，于是把速度和入弯门控绑定；R048 通过 latch 减少弯后找线损失；R049 再只提高中等弯速度，避免把 90 度急弯推过物理极限。

## 调试主线

### R044：提速前的基线

**状态**：入弯半径已经基本能跑，但速度慢。R044 控制日志显示 mean command speed≈0.62，约 28% 时间低于 0.45，`hard_turn` 占比很高。

**慢在哪里**：

- 感知置信度 `track_conf` 中位不高，`confidence_factor` 把很多本来可开的段落压慢；
- 中等弯被过早归进 `hard_turn`，速度被 `hard_turn_speed` cap 住；
- `curve_slowdown`、`offset_slowdown`、`steering_slowdown` 都偏保守；
- 出弯回速慢。

### R045：四阶段激进提速

**调了什么**：

1. `min_confidence_factor` 大幅提高，弱化感知置信对速度的压制；
2. 提高 `hard_turn_threshold` / `hard_turn_speed` / `correction_speed` / `recovery_speed`，减少中等弯被当成慢速硬弯；
3. 减弱 `curve_slowdown`、`offset_slowdown`、`steering_slowdown`；
4. 提高 `max_speed_increase_per_sec`，出弯更快回到高速。

**思路**：先拿掉明显保守的速度限制。这个阶段不精细分弯，目标是把速度平台整体抬起来。

**离线效果**：同一批控制帧重算目标速度，median +43%、mean +38%，91% 帧更快。

**风险**：速度上去后，过弯半径会变大。如果入弯门控不跟着变，就会出现偏外。

**证据图**：

- `speed_tuning_timeline.png`
- `speed_progression_r044_to_r049.png`

### R047：速度和入弯时机必须绑定

**调了什么**：

- 加 `turn_in_speed_comp`：速度越高，有效 `arrival_ref` 越小，入弯 gate 越早打开；
- 放松 `steering_speed_cap_scale`，避免高速时 target steering 被 cap 砍太狠；
- 继续提高 `hard_turn_speed`，减小 `curve_slowdown`。

**思路**：车速高时，车在 `lateral` 长起来之前已经跑了更远。如果沿用低速下调好的 gate，就会“几何上同样晚、物理上更晚”，表现为弯外偏、半径过大。R047 把速度纳入 gate，保证提速后仍能在合适位置开始转。

**效果**：解决“提速后偏外”的主要原因。这个版本说明提速和入弯不是两个完全独立的旋钮。

### R048：减少弯中收轮和弯后找线损失

**调了什么**：给入弯 gate 加 latch，`hard_turn` 内保持 gate 峰值，退出后慢慢衰减。

**思路**：慢不只来自目标速度低，也来自弯中突然收轮、出弯偏离中线后再慢慢找回。latch 让车持续完成转弯，减少出弯后恢复成本。

**效果**：它不是直接提速参数，但减少了“弯后跑偏 → 修正 → 掉速”的隐性损失。

### R049：只提中等弯，不推急弯

**调了什么**：

- `curve_power` 提高：`curve_risk` 在 0.4–0.8 的中等弯速度因子上升；
- `curve_risk=1.0` 的急弯速度因子不变；
- `hard_turn_speed`、`min_confidence_factor`、`max_speed_increase_per_sec` 继续上调。

**思路**：R048 已经让 mean speed 到 0.83 左右，剩下慢在弯里。90 度急弯接近速度-半径物理边界，再快会更宽甚至撞；中等弯还有空间。`curve_power` 是一个比较干净的工具：提高中等弯速度，但急弯 `curve_risk=1.0` 时因子不变。

**效果**：离线估算 median 0.85→0.90，mean +5%。R049 实跑 mean command speed≈0.850、median≈0.893、lost=0；contact 只有轻擦，没有硬撞。

**证据图**：

- `curve_power_effect.png`
- `r049_speed_distribution.png`
- `r049_control_speed_profile.png`
- `r049_trajectory_speed_contact.png`
- `r049_contact_episodes.png`

## 图片说明

### `speed_tuning_timeline.png`

R044→R049 的提速版本路线。它把提速分成四个动作：全局放开、速度耦合、弯中保持、定向提中等弯。

### `speed_progression_r044_to_r049.png`

R044 到 R049 的均速进展。适合报告里放在提速章节开头，说明速度平台确实抬起来了。

### `curve_power_effect.png`

R049 最关键的提速图。绿色区域表示 `curve_power` 提高后，中等 `curve_risk` 的速度因子上升；`curve_risk=1.0` 的急弯端点保持不变。它解释了为什么 R049 不是盲目全局加速。

### `r049_speed_distribution.png`

R049 command speed 的直方图和按 `curve_risk` 分桶的均速。用于说明当前大多数帧已经在高速度区间，剩余慢段集中在弯道。

### `r049_control_speed_profile.png`

R049 全程控制日志剖面。展示 command speed、`curve_risk`、`|steering|`、`|line_offset|` 和 mode。红色竖线是 contact 帧，便于看速度提升是否带来连续卡住或硬撞。

### `r049_trajectory_speed_contact.png`

R049 顶视轨迹，按速度着色并标 contact。适合报告里给全局直观结论：车能跑完全程，速度整体高，接触点只是零散轻擦。

### `r049_contact_episodes.png`

R049 contact episode 汇总。7 个 episode 全部 peak=3，`zmax≤0.50`，低于硬撞参考线。它是“提速后没有重新引入硬撞”的关键证据。

### `r049_opponent_contact_overlay.png`

末段静止黑车附近的 overlay。它应该作为已知残留单独说明：当前没有 opponent avoidance，末段擦黑车不应归因到提速或入弯半径。

## 数据来源

- R049 控制日志与 contact：`.tmp/run.archive/run_basic_20260613_011637/control_complex.jsonl`、`contact_complex.jsonl`
- R049 telemetry：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl` 生成的已归档图
- 速度阶段叙事：`experiments/notes.md` R045/R047/R048/R049；`/Users/day/Downloads/claude聊天记录.md` 只是生成图组时参考过的外部聊天记录，不属于仓库证据。后续接手以仓库内 notes、case 和日志摘要为准。

## 报告建议

这组图适合按三段讲：

1. **为什么慢**：R044 的低均速、置信压速、hard_turn 过多。
2. **怎么提速**：R045 四阶段放开，R047 处理速度和半径耦合。
3. **为什么没盲目加速**：R049 用 `curve_power` 只抬中等弯，并用 contact episode 证明没有硬撞回归。
