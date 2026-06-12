# AI 离线复盘手册

本文给接手实验记录的 AI 看。Webots 可以由 AI 自己跑，也可以由人类跑；跑完后，AI 应该用 telemetry、控制日志、相机帧和 overlay 解释现象。日常迭代不必每轮都等人工，AI 可以自跑、自查、自筛候选；准备标完成、合 main、提交 final，或 AI 判断已接近解决时，再让人类做关键验收。

这里的“整场 review”不是逐帧看完整场。正确做法是先看整场摘要，再从整场记录里挑关键窗口逐帧看图、生成少量 overlay，用画面和日志支撑判断。

## 1. 先确认有什么数据

常见输入及保存策略：

| 数据 | 常见路径 | 用途 | 保存策略 |
|---|---|---|---|
| 观察反馈 | 用户消息、AI 自跑观察、截图、`experiments/notes.md` | 判断真实现象，确定优先级 | 写进 notes.md 对应 R-id |
| telemetry | `/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl` | 位置、速度、爬行段、事件 | 整场复制件只临时留存；长期写摘要或裁剪窗口 |
| 控制日志 | `.tmp/run/control_*.jsonl` | 每帧内部状态、mode、目标控制量、最终输出 | 摘要写 notes；窗口可裁进 case |
| 相机帧 | `.tmp/run/frames_*/*.png` | 逐帧看白线、道路 mask、障碍物、栏杆 | 整场 PNG 不进 git；关键帧渲染成 overlay 后裁进 case |
| overlay | `.tmp/run/*overlay*` | 画面、mask、中心线、白线、边界证据 | 批量图看完即删；最多裁 1-3 张进 case |
| debug 控制器 | `.tmp/run/team_controller_debug.py` | 本地带日志/存帧构建 | 可重建，不归档 |
| controller console tee | `.tmp/run/webots_console/*.log` | team_controller 进程的 stdout/stderr | 不是完整 Webots/supervisor console，不保证包含碰栏/碰撞日志 |
| Webots GUI / physics console | Webots 窗口或启动终端里的物理引擎提示 | 静态几何接触、接触点裁剪等提示 | 若出现“发生碰撞，只计算其中最重要的 N 个碰撞点”这类提示，按碰栏/静态几何接触记录 |

`scripts/webots_run.sh` 默认就保存相机帧，所以正常情况下**每一轮都有整场帧可看，不需要为了看某个时刻重跑**。只有人类显式用 `--no-frames` 跑、或要看的窗口在 `--frame-window` 之外时才会缺帧。

调试构建命令（含 `open/json/np.save`，**禁上传**，跑 `run_local` 时配 `--skip-validate`）：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --out .tmp/run/team_controller_debug.py
```

帧保存为无损 PNG（不是旧的 `.npy`），整场约几百 MB，所以可以默认每轮都存。`--dump-frame-stride` 默认是 10，约每 0.3s 留一对图，适合整场回看；精确撞栏窗口才显式传 `--dump-frame-stride 1`。AI 或人类实跑直接用 `bash scripts/webots_run.sh <basic|complex>` 即可（帧默认开启，自动做跑前清理、构建和启动）；只在确定不看画面时加 `--no-frames`。

## 2. 全局摘要

先看真实轨迹和速度（文字汇总）：

```bash
python scripts/analyze_telemetry.py --no-archive
```

要一张能直接看的总览图（顶视轨迹按速度着色 + 速度-时间 + 卡住/事件标注），用：

```bash
python scripts/plot_run.py --telemetry <telemetry.jsonl> --out .tmp/run/trajectory.png --title "<R-id> <track>"
```

这张图也是报告里讲每个版本的总览图；要留进报告时按 `experiments/figures/README.md` 归档。

记录：

- telemetry 是否干净，是否 interleaved。
- 末帧位置、最长爬行段、低速段。
- 是否有 lap、finish、collision 事件。注意：本地 telemetry 的 collision 事件主要来自 supervisor 的车车距离判定；擦栏/碰栏可能不进入 telemetry 事件。
- Webots/物理引擎 console 是否出现接触点提示。类似“发生碰撞，只计算其中最重要的 N 个碰撞点”的信息应单独记为栏杆/静态几何接触。
- 与观察反馈是否一致。

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

- 人类或 AI 看到撞车、撞栏、偏离白线的时间窗。
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

帧默认每轮都存，所以这个工具**不再用于"补存帧"**。它的用途是：拿一个 telemetry 里的历史姿态当起点，看**当前（已改过的）代码**从那里出发会怎么开——上一轮的录制帧只能反映上一轮的代码行为，不能回答"我这次的改动在那个弯会不会好转"。

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

真实 Webots / 平台 run 才分配 R-id。AI 自跑和人类实跑都算真实 run；AI 复盘后应把结论写回：

- `experiments/runs.csv`：一行结构化摘要，`notes` 以 `R0xx |` 开头。
- `experiments/notes.md`：观察现象、数据摘要、看过的关键窗口、结论、下一步。
- `experiments/analysis_*.md`：有机制解释价值的长分析。
- `experiments/cases/<R-id>_<slug>/`：只保存会反复用于回归的小型失败窗口。
- `experiments/figures/<R-id>_<slug>/`：报告要用或之后会回查的**精选可视化**（整场轨迹图、关键感知标注帧、对比图），规则和生成命令见 `experiments/figures/README.md`。和 `cases/` 区分：`cases/` 是为复现 bug，`figures/` 是为报告叙事。

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

- 整场左右相机帧 PNG。
- 整场 Webots 录像或批量截图。
- 整场原始 telemetry 复制件。
- 临时 debug controller。
- cache、`.DS_Store`、`__pycache__`。
