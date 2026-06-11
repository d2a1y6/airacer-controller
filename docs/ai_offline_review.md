# AI 离线复盘手册

本文给接手实验记录的 AI 看。人类按 `docs/human_webots_testing.md` 跑过 Webots 后，AI 应该用 telemetry、控制日志、相机帧和 overlay 解释现象。人类肉眼结论是最终事实来源；离线复盘负责找机制证据、定位代码链路和整理下一步。

这里的“整场 review”不是逐帧看完整场。正确做法是先看整场摘要，再从整场记录里挑关键窗口逐帧看图、生成少量 overlay，用画面和日志支撑判断。

## 1. 先确认有什么数据

常见输入及保存策略：

| 数据 | 常见路径 | 用途 | 保存策略 |
|---|---|---|---|
| 人类反馈 | 用户消息、截图、`experiments/notes.md` | 判断真实现象，确定优先级 | 写进 notes.md 对应 R-id |
| telemetry | `/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl` | 位置、速度、爬行段、事件 | 整场复制件只临时留存；长期写摘要或裁剪窗口 |
| 控制日志 | `.tmp/run/control_*.jsonl` | 每帧内部状态、mode、目标控制量、最终输出 | 摘要写 notes；窗口可裁进 case |
| 相机帧 | `.tmp/run/frames_*/*.npy` | 逐帧看白线、道路 mask、障碍物、栏杆 | 整场 `.npy` 不进 git；关键帧渲染成 overlay 后裁进 case |
| overlay | `.tmp/run/*overlay*` | 画面、mask、中心线、白线、边界证据 | 批量图看完即删；最多裁 1-3 张进 case |
| debug 控制器 | `.tmp/run/team_controller_debug.py` | 本地带日志/存帧构建 | 可重建，不归档 |

没有帧也能先分析 telemetry 和控制日志；涉及白线、撞栏、视觉误判时，应要求下一轮 dump 帧，或使用已有帧生成 overlay。

调试构建命令（含 `open/json/np.save`，**禁上传**，跑 `run_local` 时配 `--skip-validate`）：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --out .tmp/run/team_controller_debug.py
```

控制日志体积小，应默认开启；dump 帧一圈数 GB，只在定位视觉/走线问题时开。`--dump-frame-stride` 默认是 10，约每 0.3s 留一对图，适合整场回看；精确撞栏窗口或短跳点才显式传 `--dump-frame-stride 1`。人类实跑推荐直接用 `bash scripts/webots_run.sh <basic|complex> [--frames N]`，它会自动做跑前清理、构建和启动。

## 2. 全局摘要

先看真实轨迹和速度：

```bash
python scripts/analyze_telemetry.py --no-archive
```

记录：

- telemetry 是否干净，是否 interleaved。
- 末帧位置、最长爬行段、低速段。
- 是否有 lap、finish、collision 事件。
- 与人类反馈是否一致。

再看控制器内部行为：

```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
```

重点看：

- `mode` / `mode_reason`
- `steering` / `target_steering`
- `speed` / `target_speed`
- `line_conf`、`line_offset`、`line_heading`
- `left_margin`、`right_margin`、`margin_risk`
- `lost`、`recovering`、`hard_turn` 的连续段

## 3. 选关键窗口

不要平均地看所有帧。优先挑这些窗口逐帧看：

- 人类看到撞车、撞栏、偏离白线的时间窗。
- telemetry 的最长爬行段或近停段。
- 大 `|steering|`、steering 突变、突然减速的窗口。
- `line_conf` 高但车没骑白线的窗口。
- `margin_risk` 高但仍继续向内打轮的窗口。
- `lost/recovering/hard_turn` 持续较久的窗口。

每个窗口通常取 3-5 帧：异常前、异常中、异常后。需要精确定位撞栏时，再看更密的帧。

## 4. 逐帧和 overlay

已有相机帧时，可以做感知 dump 分析并生成少量 overlay：

```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_basic \
  --control-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/perception_after.json \
  --overlay-dir .tmp/run/overlays \
  --overlay-limit 12
```

看图时要回答：

- 白线在画面里是否清楚。
- 识别到的白线 offset/heading 符号是否正确。
- 道路 mask、中心线、边界点是否被白车、接缝、栏杆污染。
- debug log 里的 `target_steering` 和最终 `steering` 是否朝错误方向。
- 如果车贴内栏，`left_margin/right_margin` 和 `margin_risk` 是否提前反映风险。

结论必须写清楚证据来源，例如“看了 t=92.4-96.0 的 overlay，白线在车身左侧，但 `target_steering` 仍为右打”。不要只凭一组均值推断。

## 5. 跳点取证 / 近似续跑

如果 telemetry 有目标时间点，但原始相机帧没存下来，可以用跳点工具补短窗口画面：

```bash
bash scripts/webots_jump_run.sh complex 144 --duration 5 \
  --telemetry .tmp/r025_line_priority_run/telemetry.jsonl
```

脚本会生成临时 Webots world，把 `car_1` 放到 telemetry 最近帧的 `x/y/heading`，再跑几秒并保存相机帧到 `.tmp/jump_run/frames/`。临时 world 放在 SDK 的 `webots/worlds/` 下，跑完自动删除。默认每 10 帧存一对图；如果要逐帧看画面，显式加 `--frames 1`。

它可以从跳点继续往前跑几秒，适合看“从这个姿态出发，当前代码大概会怎么打轮、画面里有没有白线、mask 是否把栏杆当路面”。但这不是严格续跑：它只恢复位置和朝向，不恢复线速度/角速度、轮胎/悬挂/接触状态、controller 内部记忆、Webots 物理随机状态、checkpoint/赛事计时和其它车辆的真实历史状态。长时间续跑会很快偏离原 run，不能证明策略能从该状态真实脱困。策略验证仍要从头跑正式 world。

## 6. 开环回放

已有帧后，可以离线重跑同一段固定画面：

```bash
python scripts/replay_offline.py .tmp/run/frames_basic \
  --out .tmp/run/replay_basic.jsonl

python scripts/analyze_control_log.py .tmp/run/replay_basic.jsonl
```

回放脚本会在开始前调用 `reset_estimator_state()` 和 `reset_policy_state()`，再按：

```text
extract_observation → estimate_track → decide_control → clamp_cmd
```

逐帧输出 JSONL。输出字段和 `--debug-log` 控制日志一致，可以直接交给 `analyze_control_log.py`。

开环回放适合比较同一批画面下，感知、估计或 policy 改动如何影响 `line_conf`、`lost`、`target_steering`、`margin_risk` 等字段。

开环回放不能判断圈速、是否完赛、是否真实撞栏。真实 Webots 中，控制输出会改变车的位置和后续画面；回放里的后续画面已经固定。

## 7. 记录和归档

真实 Webots / 平台 run 才分配 R-id。AI 复盘后应把结论写回：

- `experiments/runs.csv`：一行结构化摘要，`notes` 以 `R0xx |` 开头。
- `experiments/notes.md`：肉眼现象、数据摘要、看过的关键窗口、结论、下一步。
- `experiments/analysis_*.md`：有机制解释价值的长分析。
- `experiments/cases/<R-id>_<slug>/`：只保存会反复用于回归的小型失败窗口。

`analyze_telemetry.py --archive <label>` 只把当前原始 telemetry 临时复制到 `.tmp/recordings/<label>/`，方便本轮分析。它不是长期归档。

## 8. 清理与保留

`.tmp` 的保留规则（吃过亏：R014 撞栏帧被提前清掉，下一轮只能重跑取证）：

- **最近一次 run 的产物保留到被下一次 run 覆盖**。`scripts/webots_run.sh` 会自动把上一轮 `.tmp/run` 轮换成 `.tmp/run.prev`，再上一轮才删除。
- 清理前先看 `notes.md` 最新 R-id 的"下一步"：如果它依赖某个失败窗口的帧/日志，先裁进 `experiments/cases/<R-id>_<slug>/` 再删。
- 结论写进 `experiments/` 且确认无依赖后，才做全量清理：

```bash
rm -rf .tmp .pytest_cache
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -name '.DS_Store' -delete
```

长期不要保存：

- 整场 `.npy` 左右相机帧。
- 整场 Webots 录像或批量截图。
- 整场原始 telemetry 复制件。
- 临时 debug controller。
- cache、`.DS_Store`、`__pycache__`。
