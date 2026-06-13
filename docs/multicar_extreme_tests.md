# 多车极端场景测试指南

本文档描述如何构建和运行多车极端场景测试，确保车辆在以下情况下能成功自救：
1. 前车堵路（blocked by front car）
2. 被撞（being hit / rear-rammed）
3. 卡进栏杆（stuck in railings）

## 前提条件

- Webots 已安装并可从命令行启动
- 官方 SDK 位于 `/Users/day/Desktop/Github/pkudsa.airacer/sdk/`
- 本仓库已正确构建 `submissions/with_other_cars/team_controller.py`

## 快速开始：默认双车测试

```bash
# 双车 basic（两个车位默认都接 with_other_cars 构建，队名只是 run_local 标签）
bash scripts/webots_multicar_run.sh basic

# 双车 complex
bash scripts/webots_multicar_run.sh complex

# 不存帧，跑得更快
bash scripts/webots_multicar_run.sh basic --no-frames
```

输出产物：
- `.tmp/multicar/control_<world>_car1.jsonl` — 我方控制日志
- `.tmp/multicar/control_<world>_car2.jsonl` — 对手控制日志
- `.tmp/multicar/contact_<world>_car1.jsonl` — 撞栏接触日志（含**所有车**，按 `car_slot` 过滤，见下「跑完后的分析」）
- `.tmp/multicar/frames_<world>_car1/` — 我方相机帧

## 极端场景

### 场景 1：前车堵路 (Blocked Front)

**目标**：验证前方有车挡住去路时，能否减速、检测障碍、主动避让。

**当前应对机制**：
| 机制 | 行为 | 参数 |
|---|---|---|
| 对手车检测 | `detect_near_vehicle_obstacle_state()` 检测近处车身色块，并输出 `obstacle_x/obstacle_size` | `OPPONENT_PROFILE` |
| 对手降速 | 正前方挡车重降速，偏侧车辆轻降速 | `opponent_speed_factor=0.72`, `opponent_side_speed_factor=0.92` |
| 主动避让转向 | 基于车身左右位置和边界余量叠加绕行舵角 | `opponent_avoid_steering_gain=0.65`, `opponent_direction_steering_gain=0.20` |

**测试方法 A（双车自然相遇）**：
```bash
# 两车在同一赛道，我方从后方追上对手
bash scripts/webots_multicar_run.sh basic
```
观察我方追上对手后是否减速并尝试转向避开。

**测试方法 B（人工制造堵路场景）**：
使用 jump run 把我方车传送到已知对手车前方不远处：
```bash
# 先跑一次双车，记录对手车在某个时间的位置
# 然后用 jump_run 把我方传送到对手车后方
bash scripts/webots_jump_run.sh basic <frame_index> \
  --telemetry <path_to_telemetry>
```

**预期行为**：
1. `near_obstacle` 变为 True（控制日志中可见）
2. 速度明显下降（target_speed 含 opponent_speed_factor）
3. 舵角朝余量更大的一侧偏置（avoid_bias）
4. 不应直接撞上前车

**已知局限**：
- 对手检测只覆盖图像下中部 ROI，远处车辆检测不到
- 如果前车完全堵住路面、两侧余量都为 0，当前只能减速无法绕行
- 没有路径规划层，无法"找路绕过去"

---

### 场景 2：被撞 (Being Hit / Rear-Rammed)

**目标**：验证被其他车撞击偏出赛道后，能否自行恢复。

**当前应对机制**：
| 机制 | 触发条件 | 行为 |
|---|---|---|
| 顶栏脱困 (pinned_escape) | `|lateral| ≥ 0.45`, `|steering| ≥ 0.55`, `speed ≤ 0.55` | 28 帧朝路面硬舵 |
| 低速脱困 (low_speed_stall) | `speed ≤ 0.22` 且画面停帧 | 120 帧朝开阔侧硬舵 |
| 边界障碍脱困 (boundary_obstacle_stall) | 近障碍 + margin ≤ 0.08, red env only | 72 帧朝开阔侧硬舵 |
| 丢线强制脱困 (force_escape) | 连续丢线 ≥ 60 帧(~2s) | 90 帧朝路面方向硬舵+低速 |
| 大偏移脱困 (large_offset_stall) | `offset ≥ 0.62`, red env only | 72 帧脱困 |

**测试方法**：
```bash
# 双车同赛道，对手可能从后方撞上我方
bash scripts/webots_multicar_run.sh basic
```

要主动制造碰撞场景比较困难（需要控制两车速度差和位置），建议：
1. **等待自然碰撞**：双车测试中如果对手快、我方慢，可能发生后撞
2. **用 jump_run 传送**：把我方传送到赛道中间（非正常位置），观察能否恢复

**预期行为**：
1. 被撞后可能短暂丢线（lost=True）
2. 根据偏离程度触发不同脱困机制
3. 应能在大约 5-10 秒内回到正常行驶
4. 不应无限期卡在原地

**已知局限**：
- 无后方/侧方碰撞检测（opponent.py 只看前下方）
- 无碰撞冲击后的瞬时稳定控制
- 脱困依赖于能感知到"路面在哪"，如果完全偏离赛道可能无法恢复

---

### 场景 3：卡进栏杆 (Stuck in Railings)

**目标**：验证车卡在栏杆夹角中时能否自行脱困。

**当前应对机制**：
| 机制 | 触发条件 | 行为 |
|---|---|---|
| 顶栏脱困 (pinned_escape) | `|lateral| ≥ 0.45`, `|steering| ≥ 0.55` | 朝远离栏杆侧硬舵 + 中速 |
| 边界障碍脱困 (boundary_obstacle_stall) | margin ≤ 0.08 + near_obstacle | 朝开阔侧硬舵 |
| 低速脱困 (low_speed_stall) | speed ≤ 0.22 持续 120 帧 | 朝开阔侧硬舵 + 高速 |
| 丢线强制脱困 (force_escape) | 连续丢线 ≥ 60 帧 | 硬舵 + 低速前进（兜底） |

**测试方法 A（自然触发）**：
```bash
bash scripts/webots_multicar_run.sh complex
```
complex 赛道有多个急弯，车可能自然卡进栏杆。

**测试方法 B（jump run 传送到卡死位置）**：
```bash
# 从已知的卡死位置的 telemetry 传送到附近
bash scripts/webots_jump_run.sh complex <frame_index> \
  --telemetry <path_to_telemetry> \
  --duration 10
```

**预期行为**：
1. 卡进栏杆后速度降到很低（触发 low_speed_stall 或 pinned_stall）
2. 画面可能丢线（触发 force_escape 作为最后兜底）
3. 脱困应朝远离栏杆侧（margin 更大侧）打硬舵
4. 应在 3-10 秒内脱离
5. 脱困后应能恢复正常行驶

**脱困优先级链**：
```
1. pinned_escape        (28 帧, steering=0.80) — 明确顶栏姿态
2. boundary_obstacle    (72 帧, steering=0.86) — 近处障碍+单侧边界
3. low_speed_stall      (120 帧, steering=0.74) — 低速卡死
4. large_offset_stall   (72 帧, steering=0.74) — 大偏移卡边 (complex only)
5. force_escape         (90 帧, steering=0.82) — 丢线兜底，不依赖任何几何条件
```

---

## 跑完后的分析

### 控制日志
```bash
python scripts/analyze_control_log.py .tmp/multicar/control_basic_car1.jsonl
python scripts/analyze_control_log.py .tmp/multicar/control_basic_car2.jsonl
```

### 撞栏接触日志
接触日志记录的是**所有车**的接触（每行带 `car_slot`）。只看本车要加 `--car-slot`，否则会把对手车卡栏误当成本车撞栏：
```bash
python scripts/analyze_contact_log.py .tmp/multicar/contact_basic_car1.jsonl --car-slot car_1
```

### 脱困 / 倒车段
```bash
python scripts/analyze_escape_episodes.py .tmp/multicar/control_basic_car1.jsonl
```

### 轨迹总览（需要 telemetry）
```bash
python scripts/plot_run.py \
  --telemetry <path_to_telemetry> \
  --contact-log .tmp/multicar/contact_basic_car1.jsonl \
  --out .tmp/multicar/trajectory_speed.png \
  --title "Multi-car basic test"
```

### 感知 overlay（需要帧）
```bash
python scripts/analyze_perception_dump.py .tmp/multicar/frames_basic_car1 \
  --mode with_other_cars \
  --control-log .tmp/multicar/control_basic_car1.jsonl \
  --overlay-dir .tmp/multicar/overlays \
  --at <timestamps>
```

## 关键观察点

跑多车测试时，重点观察：
1. **near_obstacle 何时变为 True/False**（控制日志 `track.near_obstacle` 字段）
2. **脱困期间 mode 是否为 escaping**（控制日志 `mode` 字段）
3. **脱困方向和持续时间**
4. **脱困后是否立即恢复正常行驶**（mode 从 escaping → cruise/hard_turn）
5. **接触日志中是否有真实碰撞**

## 更新实验记录

测试完成后，按以下模板更新 `experiments/notes.md`：

```
### R0xx — 多车极端场景测试 (2026-06-XX, <world>)
- **构建**: commit <sha>, multi-car 分支
- **场景**: 前车堵路 / 被撞 / 卡栏杆
- **配置**: <world>, car_1=ours, car_2=opponent（均为 with_other_cars 构建，除非手工指定 baseline）
- **结果**:
  - 前车堵路: 减速 OK / 避让 OK/NG / 碰撞 有/无
  - 被撞: 恢复 OK/NG / 耗时 ~Xs
  - 卡栏杆: 触发 <mechanism> / 脱困耗时 ~Xs
- **现象**: ...
- **结论/下一步**: ...
```

同时在 `experiments/runs.csv` 追加一行。
