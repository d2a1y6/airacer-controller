# 转弯半径 / 入弯时机（R041 → R049）

这个 case 记录同一个问题的完整演进：早期车在还没到弯口时就响应远处弯道，切进内侧并撞栏；后续把入弯门控改成近处 lateral 判据，再加速度耦合和弯中 latch，最终得到 R049 当前最佳。

## 当前结论

**根本性问题已解决。** R049 实跑确认：转弯不再硬撞栏，速度明显提高，控制日志 lost 为 0，contact 日志只有 peak=3 / `zmax≤0.50` 的轻擦。当前最佳快照见 `baselines/R049_turn_in_speed_best_2026-06-13/`。

报告图已经拆成两组：

```text
experiments/figures/R042_to_R049_turn_in_evolution/
experiments/figures/R045_to_R049_speed_evolution/
```

第一组只讲入弯：旧门控为什么切内、R042 如何修入弯、R046 为什么删掉 curve-risk gentle 分支、R047/R048 如何处理高速半径和弯中收轮。第二组只讲提速：R045 如何放开保守限速、R047 为什么必须把速度和入弯绑定、R049 如何在不推急弯物理极限的情况下提中等弯速度。

## 根因

旧入弯门控用 `heading` 判断“弯到了没”：

```text
corner_arrival = |lateral|/0.30 + |heading|/0.45
lookahead_term *= turn_in_gate
```

但 `heading` 本身就是远处/中场 road-mask 的弯量。它在直道接近段就会涨起来，于是门提前打开，车还居中、还在线上就开始切进弯里。这个门控用“驱动入弯的信号”当“是否该入弯”的判据，等于没有真正迟滞。

R041 的最紧左弯窗口能直接看到这个机制：

| 版本 | 入弯 commit | commit 时 lateral | 弯中 line_offset 峰值 | 结果 |
|---|---:|---:|---:|---|
| R041 | t≈224.16 | ≈0，车还居中 | +0.65 | 撞栏 12 点 |
| R042 | t≈227.14 | ≈−0.14，车已到弯口 | +0.23 | 通过 |

相关证据：

- `control_window_R041_bug.jsonl`
- `control_window_R042_fixed.jsonl`
- `contact_R041_crash.jsonl`
- `turn_in_before_after.png`

## 演进

### R042 / R043：近处 lateral 入弯门控

把 arrival 改成只看近处 `|lateral|` 漂移：直道接近段 lateral≈0，远处预瞄项被压住；车真正到弯口、开始物理偏离时 lateral 才长起来，门再打开。R043 删除 floor，让远处项可以被压到 0。

这解决了“入弯太早 → 切内线 → 撞内栏”的根因。

### R044 / R046：curve-risk gentle 调制被删除

R044 试过按 `curve_risk` 判断缓弯/急弯，给缓弯更多迟滞。实跑和日志证明这条路不成立：每个弯的入口阶段 `curve_risk` 都偏低，因为弯还没在视野里发育起来。于是所有弯在最关键的入弯瞬间都会被误判成 gentle，导致过度迟滞、深入弯里才急打轮、半径反而过大。

R046 删除这条分支，保留干净的 lateral gate。

### R047：速度耦合

提速后，同一个几何 gate 在高速下会开得太晚：车在 lateral 还没涨起来前已经跑过入弯段。R047 把 arrival reference 随速度收小：

```text
arrival_ref = turn_in_lateral_ref × (1 − turn_in_speed_comp × speed_norm)
```

速度越快，门越早打开。并同步放松高速 steering cap，避免 target steering 想打大舵时被高速收舵裁掉。

### R048：latch 保持 + 出弯迟滞

纯连续 gate 还有一个问题：弯中 `lateral` 会因为 road-mask 重新居中而掉回 0，门随之收掉远处预瞄项，车出现“转到一半收轮”。R048 给 gate 加跨帧 latch：

- `hard_turn` 内 ratchet 到峰值并保持，弯中不随 lateral 回落；
- 离开 `hard_turn` 后按 `turn_in_hold_decay` 慢慢衰减，形成出弯迟滞。

这让车能持续完成弯道。

### R049：定向提速

R047/R048 已把速度大幅提上来。R049 继续只提中等弯，不推已经接近物理极限的 90° 急弯：

- `curve_power` 提高：中等弯速度因子上升，`curve_risk=1.0` 的急弯不变；
- `hard_turn_speed`、`min_confidence_factor`、`max_speed_increase_per_sec` 提高；
- 当前实跑 mean command speed≈0.85，median≈0.89，lost=0。

## 当前残留

- 个别中等弯的半径仍依赖感知给出的 `curve_risk`。两个肉眼相似的弯，如果一个被估成 `curve_risk=1.0`、另一个被估成 0.4，速度和半径会不同。这是感知一致性问题，不是入弯门控本身的问题。
- 末段会轻擦静止黑车。当前没有完整 opponent avoidance，后续应单独处理，不应把它误归因到转弯半径。

## 报告图

长期报告图分两组归档：

### 入弯图组

见 `experiments/figures/R042_to_R049_turn_in_evolution/`。其中：

- `turn_in_debug_timeline.png`：R041→R049 入弯机制演进；
- `turn_in_gate_shape.png`：旧 heading gate、纯 lateral gate、speed-coupled gate 的形状对比；
- `r041_r042_turn_in_before_after.png`：R041 撞栏与 R042 延迟入弯的直接对照；
- `tight_corner_control_progression.png`：R041/R042/R044/R049 同类紧弯控制量对比；
- `r049_*_overlay.png`：R049 关键弯道感知 overlay。

### 提速图组

见 `experiments/figures/R045_to_R049_speed_evolution/`。其中：

- `speed_tuning_timeline.png`：R044→R049 提速路线；
- `curve_power_effect.png`：R049 为什么只提中等弯、不推急弯；
- `r049_speed_distribution.png`、`r049_control_speed_profile.png`：R049 速度分布和控制剖面；
- `r049_trajectory_speed_contact.png`、`r049_contact_episodes.png`：提速后的轨迹和 contact 证据；
- `r049_opponent_contact_overlay.png`：末段静止车残留，单独归因到 opponent avoidance 缺失。
