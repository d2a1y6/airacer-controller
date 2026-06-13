# Webots 实跑手册

本文给需要启动 Webots 的人或 AI 看。目标是把车真实跑起来，留下可复盘的控制日志、telemetry 和相机帧；如果是关键验收节点，再由人类肉眼确认走线质量。这里不要求人类跑完整的日志分析，也不要求人工逐帧看录像；AI 的复盘流程见 `docs/ai_offline_review.md`。

首次安装 Webots 和官方 SDK 见 `docs/official_testing.md`。

本文只讲**怎么把车跑起来**（单车、多车、接入不同控制器/策略）和产物在哪。当前跑到哪一步、哪个版本最好、未解问题，全部看 `experiments/STATUS.md` / `experiments/notes.md` / `experiments/runs.csv`，本文不维护。

## 1. 单车实跑（一个控制器，一键启动，推荐）

```bash
# 默认：控制日志 + 相机帧 PNG（每 10 帧一对，整场约几百 MB）
bash scripts/webots_run.sh basic
bash scripts/webots_run.sh complex

# 精确取证撞栏/内切窗口时改成逐帧
bash scripts/webots_run.sh complex --frames 1

# 只在某个时间窗存帧（其余时间不写盘）
bash scripts/webots_run.sh complex --frame-window 410 430

# 确定这轮不看画面、只要控制日志时可关存帧
bash scripts/webots_run.sh basic --no-frames
```

**默认就保存相机帧**：这样跑完后想看任意时间点都不用重跑。过去 codex 反复栽在「跑的时候没存帧 → 想看某个时刻只能开着帧再跑一整圈」上（R024→R025 就是这样浪费了一次 complex 实跑）。帧现在是无损 PNG，比旧的 `.npy` 小约 10 倍，整场默认保留也不会撑爆 `.tmp`。

脚本会自动：清理孤儿 Webots / run_local 进程、把旧 SDK telemetry 移到 `.tmp/run.archive/`（避免 telemetry 交错）、把上一轮 `.tmp/run` 移到 `.tmp/run.archive/run_<timestamp>/`、滚动保留最近 10 个归档、构建带控制日志和帧存储的调试控制器、用 `--skip-validate` 启动 Webots。

启动后终端会打印 team_controller stdout/stderr 镜像日志位置，例如：

```bash
team_controller stdout/stderr tee → /.../airacer-controller/.tmp/run/webots_console/*.log
```

AI 可以实时看：

```bash
tail -f .tmp/run/webots_console/*.log
```

外层 `run_local` / Webots 启动终端输出会保存到：

```bash
.tmp/run/webots_launch.log
```

这个文件能事后检索部分 Webots 启动输出，但实测不稳定包含 Webots GUI console 的物理接触提示。不要要求 AI 只靠这个文件判断碰栏。

跑完后同一个目录也能直接读取。这里抓的是 **team_controller/controller 进程里的 `stdout/stderr`**，包括学生控制器 `print` 和导入错误。它不是完整 Webots GUI console，也不是 supervisor 碰撞日志；它之外的撞栏判据现在主要看下面的**结构化接触日志**。

注意区分两类碰撞信号：

- telemetry 的 `collision` event 主要来自 supervisor 的车车碰撞判定。
- Webots GUI console 里那句
  `WARNING: Contact joints between materials 'default' and 'default' will only be created for the 10 deepest contact points instead of all the N contact points.`
  通常表示车体碰到了栏杆/路沿/静态几何。**现在这类撞栏已被结构化接触日志自动捕获**（见下），不必再只靠人眼盯 GUI console。

### 撞栏接触日志（默认开，AI/人都能用）

`scripts/webots_run.sh` 默认开启撞栏接触日志（要关加 `--no-contact`），跑完后产物：

- `.tmp/run/contact_<world>.jsonl`：每帧车身-栏杆接触的时间、世界坐标、点数、最大高度。
- telemetry 的 `events` 里也会插 `contact_start` / `contact_end`。

跑完直接看汇总（人和 AI 都用这个，不用肉眼盯 console）：

```bash
python scripts/analyze_contact_log.py .tmp/run/contact_complex.jsonl
```

判读：**峰值点数 ≥3 且 `zmax` > 0.6 = 真撞栏**；孤立 1-2 点、`zmax`≈0.49 是发车点底盘伪接触，忽略。底层由 SDK supervisor 的 `AIRACER_CONTACT_LOG=1` 用 Webots `getContactPoints()` 实现，只在调试层、不进提交文件。

调试构建含 `open/json/np.save`，只能本地跑。正式提交版不要带这些开关。

practice 模式跑完一圈通常不会自动停，会继续第二圈。看够后退出 Webots，再清一次进程：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

如需手工分步执行（自定义 mode、输出路径等），等价命令是 `scripts/build_submission.py --debug-log ... [--dump-frames ... --dump-frame-stride N] --out .tmp/run/team_controller_debug.py`，再用 SDK `run_local.py --skip-validate` 启动；细节见 `docs/ai_offline_review.md` 第 1 节。

## 2. 多车实跑 / 接入不同策略

`basic` 和 `complex` 都是 **6 车布局**（`car_1`…`car_6`）。多车的底层机制是给 `run_local.py` 重复传 `--car`，**每个车位接入一个控制器单文件**：

```bash
# 通用形式：--car 控制器文件:车位:队名（可重复，最多 6 个车位）
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --world complex \
  --car .tmp/multicar/car1_debug.py:car_1:fastest \
  --car .tmp/multicar/oppA.py:car_2:teamA \
  --car .tmp/multicar/oppB.py:car_3:teamB \
  --skip-validate
```

- **没指定的车位会停在原地**（变成静态障碍）；要它们当移动对手就得显式 `--car` 接入控制器。
- **多车模式只用 `--car`，不能再同时传 `--code-path`**（两者互斥，run_local 会报错）。
- 调试构建含 `open/json`，所以多车一律加 `--skip-validate`。

**接入不同策略 = 给不同车位放不同的控制器单文件**。当前构建是统一策略（`fastest/safe/basic` 内容相同，`--mode` 只决定默认输出路径），所以"不同策略"实际指不同的**文件**，常见三种：

| 想测什么 | 怎么接入 |
|---|---|
| 本控制器 vs 历史基线 | 一个车位放当前构建，另一个放 `baselines/<快照>/team_controller.py` |
| 本控制器 vs 较慢对手（纯超车场景） | 对手用速度缩放版（见下 `webots_auto_multicar.sh` 第 5 参数） |
| 本控制器自我对抗（真实交通/拥堵） | 所有车位放同一份当前构建 |

手工生成多个单文件：`python scripts/build_submission.py --mode fastest --out .tmp/multicar/<名字>.py`，再按上面的 `--car` 逐个接入。

### 一键多车脚本

| 脚本 | 场景 | 命令 |
|---|---|---|
| `webots_day_multicar.sh` | 6 车都跑本控制器（car_1 带 debug 日志），复现真实交通 / CP3 拥堵 | `bash scripts/webots_day_multicar.sh complex` |
| `webots_auto_multicar.sh` | **AI 无人值守**：后台启动 Webots + 看门狗（超时或日志静止自动收尾），可降速对手 | `bash scripts/webots_auto_multicar.sh complex 300 30 6 0.55` |
| `webots_multicar_run.sh` | 双车（car_1=fastest, car_2=safe） | `bash scripts/webots_multicar_run.sh complex` |

`webots_auto_multicar.sh` 的参数：`<world> <最大秒数> <日志静止判定秒数> <车数> [对手速度缩放]`。第 5 个参数 `<1` 会给对手单文件追加一层速度缩放（如 `0.55` = 对手半速），让全速的 car_1 追上并超车——纯超车效率测试。它供 AI 自跑用（人睡觉时也能跑），看门狗保证不会无限挂着。

堵路 / 被撞 / 卡栏这类**极端场景**需要把对手车手动布置到特定位置（用 `webots_jump_run.sh` 传送），不是一个开关能自动摆好的；做法见 `docs/multicar_extreme_tests.md`。

多车产物在 `.tmp/multicar/`（`control_<world>_car1.jsonl`、`contact_<world>_car1.jsonl`、`frames_<world>_car1/`）。

> **多车看日志的铁律**：`contact_*.jsonl` 记录的是**所有车**的接触，每行带 `car_slot`。只看本车要加过滤，否则会把对手车卡栏误当成本车撞栏：
> ```bash
> python scripts/analyze_contact_log.py .tmp/multicar/contact_complex_car1.jsonl --car-slot car_1
> python scripts/analyze_escape_episodes.py .tmp/multicar/control_complex_car1.jsonl  # 脱困/倒车段
> ```

## 3. 观察要记什么

日常迭代可以由 AI 自己跑 Webots、看日志和截图。关键验收时，人类观察仍很重要。请尽量记录这些事实：

- 赛道：`basic` 或 `complex`。
- 是否跑完一圈；如果没跑完，在哪里停住或撞上。
- 车相对白线的位置：车身中心骑线、长期在线左、长期在线右、入弯切内线、出弯能否回线。
- 撞车或撞栏对象：左/右栏杆、白车、黑车、其他。
- 人眼是否看到 Webots GUI console 的接触点提示，例如 `WARNING: Contact joints between materials 'default' and 'default' will only be created for the 10 deepest contact points instead of all the 12 contact points.`。这条目前不是 AI 能从文件日志稳定读取的信号。
- 异常行为：突然大幅打轮、无意义减速、原地挣扎、能否自行脱困。
- 大致时间或位置：Webots 时间、起终点附近、第几个弯、截图。

截图很有价值。能截就截，但不要为了截图中断关键观察。

## 4. 跑完交给 AI 或进入复盘

跑完后，把观察结论告诉 AI，并说明 `.tmp/run/` 里有哪些产物。如果是 AI 自跑，也要把这些结论写进 notes 或下一步分析里，例如：

- `.tmp/run/control_basic.jsonl`
- `.tmp/run/webots_console/*.log`（team_controller stdout/stderr，不包含完整 Webots/supervisor 碰撞日志）
- `.tmp/run/webots_launch.log`（外层 run_local/Webots 启动终端输出；实测不能稳定读到 GUI console 的接触点 warning）
- `.tmp/run/frames_basic/`
- SDK telemetry：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`
- 如果人眼在 Webots GUI console 里看到接触点提示，也要把原文或大意写进反馈。

**不要手动删 `.tmp`**。下一次 `scripts/webots_run.sh` 会把旧产物移到 `.tmp/run.archive/`，并滚动保留最近 10 个归档；全量清理由 AI 在确认结论已写入 `experiments/`、且 notes 的"下一步"不依赖这些产物后执行（见 `docs/ai_offline_review.md` 第 8 节）。

## 5. 正式提交版

确认要上传或做正式验证时，重新生成干净单文件：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/build_submission.py --mode fastest --out submissions/fastest/team_controller.py
python scripts/build_submission.py --mode safe --out submissions/safe/team_controller.py  # 兼容输出名；策略内容相同

pytest -q
python scripts/validate_submission.py submissions/final/team_controller.py
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

正式提交文件不能含调试 I/O。

## 常见坑

- telemetry 时间非单调或帧数离谱：有残留 Webots，先 `pkill`，必要时删旧 telemetry。
- 车不动且控制输出像 `(0, 0)`：Webots Python 可能缺 `cv2` 或 `numpy`，跑官方 `sdk/check_env.py`。
- `run_local` 合规错误：调试构建忘了加 `--skip-validate`。
- `.tmp` 变很大：通常是 dump 帧还没清理。AI 复盘并记录结论后删除。
