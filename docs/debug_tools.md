# 调试与自动化诊断工具全集（AI 自主作业前先读本文）

本文是当前**所有**自动化调试工具的权威清单：数据产物、脚本用法、以及——最关键——**一个 AI 在没有人类的情况下能看到什么、怎么看、不能看什么**。Codex / 任何自主 agent 在动手前先读完本文。

---

## 0. 最重要的前提：AI 能看到什么 / 看不到什么

**能（纯本地、无需 Webots）：**
- 改 `controller/`、跑 `pytest`、跑本地和官方 validator、`build_submission.py`。
- 跑全部分析脚本（见第 3 节），它们只打印**聚合摘要**（几十行），token 成本低。
- **直接看图**：用 Read 工具读 PNG/JPG（overlay 图、渲染出的逐帧画面、`live_view.jpg`）。这就是"逐帧回看录像"的能力。
- 读已有的控制日志 JSONL、dump 的 `.npy` 帧、归档的遥测。
- **离线开环回放**录制好的帧（`replay_offline.py`），看感知/估计改动对**同一段固定画面**的影响。

**不能：**
- **跑不了 Webots**。整个闭环（车实际怎么开、圈速、是否完赛、会不会贴栏杆/卡死）**只有人类能跑**。
- 因此 AI **无法验证驾驶行为**，只能验证"逐帧感知/估计"和"离线开环"层面的东西。

**由此推出的铁律（违反过两次，务必记住）：**
1. **实车（人类肉眼 + 闭环）是 ground truth；离线指标是弱代理，绝不能否决实车结论。**
2. **`lost` 率不是质量指标**：车在 lost 时是直线滑行（不停车、不偏出），lost 多≠开得差。
3. **任何改动要在整段录像 corpus 上验全局**，不能只看你想修的那个点（局部修好、全局砸锅出现过）。
4. **拿领域常识做 sanity check**：例如 basic 是顺时针全程右弯，出现"满信心左弯"必然是 bug，别信。
5. 调试构建**禁止上传**（含 `open/json/np.save`）；提交只用 `submissions/final/team_controller.py`。

---

## 1. 数据是怎么产生的：调试构建

`scripts/build_submission.py` 把 `controller/` 拼成单文件。调试用的两个开关（只注入**本地**调试单文件，正常构建不含）：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \      # 每帧写内部状态+命令到 JSONL
  --dump-frames .tmp/run/frames_basic \           # 每隔 N 帧存左右相机 .npy
  --dump-frame-stride 3 \                          # 存帧间隔（控制日志仍是每帧）
  --out .tmp/run/team_controller_debug.py
```

- `--debug-log` 单独用即可拿到逐帧决策日志（最常用）。
- `--dump-frames` 才需要时再加（每帧约 1.8MB×2，stride 3 一圈约 6GB）；它是"逐帧回看"和"离线回放"的前提。
- 正常提交版构建：`build_submission.py --mode fastest --out submissions/final/team_controller.py`（**不带**调试开关）。

人类用这个调试构建在 Webots 里跑（`--skip-validate`，因为含被禁导入）；详见 [manual_testing.md](manual_testing.md)。

---

## 2. 数据产物清单（位置 + schema）

### 2.1 控制器内部日志（最可信，AI 主要看这个）
- 来源：`--debug-log <PATH>`。每帧一行 JSON，**每次 run 截断重写**，不受跨 run 污染。
- 字段（16 个）：
  `t, steering, speed, lateral, heading, curvature, lookahead, track_conf, lost, red_env, mode, obs_conf, obs_points, road_width, debug_flags`
  - `steering∈[-1,1]`（左负右正）、`speed∈[0,1]`；`lateral/heading/curvature/lookahead∈[-1,1]`（左负右正，右弯 curvature 为正）。
  - `mode∈{start,cruise,hard_turn,correcting,recovering,lost,escaping}`。
  - `obs_points`=感知中心点数，`road_width`=道路宽度估计，`track_conf`=估计置信度。
  - `debug_flags`=感知位图（见 2.5）。

### 2.2 dump 的相机帧
- 来源：`--dump-frames <DIR> --dump-frame-stride N`。
- 文件名：`frame_<TAG>_left.npy` / `frame_<TAG>_right.npy`，BGR `uint8` `480x640x3`。
- `TAG` 由时间戳编码：`("%010.3f" % t).replace("-","m").replace(".","_")`，例如 `t=202.272 → 000202_272`。**按时间戳即可 join 到控制日志**。

### 2.3 Supervisor 遥测（真值位置/速度，但会跨 run 污染）
- supervisor 默认写到 **`<SDK>/.local/recordings/`**（SDK=`/Users/day/Desktop/Github/pkudsa.airacer/sdk`），不是本仓库；`run_local.py` 没有重定向开关，每次 run 覆盖。
- `telemetry.jsonl`：每帧 `{t, cars:[{team_id,x,y,heading,speed,lap,lap_progress,status}], events}`（注意 `speed` 是 supervisor 自己的世界单位，不是 0~1 命令值）。
- `metadata.json`：`{total_frames, duration_sim, finish_reason, ...}`。
- `live_view.jpg`：俯视快照（可直接 Read 看）。
- **坑**：孤儿 Webots 进程会让多次 run 的遥测**交错**（帧数远超 `metadata.total_frames`、`t` 非单调）。分析脚本会自动切段只取最近一次，但要看它打印的"完整性"行。控制日志不受此影响。

### 2.4 归档目录（仓库内留档）
- `analyze_telemetry.py --archive <标签>` 会把当次 `telemetry.jsonl/metadata.json/live_view.jpg` 复制到 **`.tmp/recordings/<标签>/`**（`.tmp/` 已 gitignore）。

### 2.5 `debug_flags` 位含义（务必对照 `controller/perception.py`/`estimator.py` 复核）
| bit | 含义 |
|---|---|
| 1 | 有效扫描线过少 |
| 2 | 用了边缘 fallback |
| 4 | mask 填充率极端（≈0 或饱和）|
| 8 | 左右近处中心偏差大 |
| 16 | 左右置信度接近（模糊）|
| 32 | 红色环境（complex）|

---

## 3. 分析脚本清单（全部只打印摘要，token 友好）

### 3.1 `analyze_control_log.py` — 控制日志诊断（最常用）
```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
python scripts/analyze_control_log.py .tmp/run/  dir_or_multi.jsonl ...   # 支持多文件/目录
```
打印：转向震荡（换向频率/累计 |Δsteer|）、速度分布、横向偏置、各 mode 占比、速度-转向耦合，以及**丢线诊断**（lost 占比、连续段长度、lost 帧的 `track_conf/obs_points/road_width` 分布、`debug_flags` 频率、进入 lost 前的 mode、lost 与弯道的相关性）。跨 run 残留会自动取最后一段。

### 3.2 `analyze_telemetry.py` — supervisor 遥测摘要
```bash
python scripts/analyze_telemetry.py                      # 默认读 <SDK>/.local/recordings/telemetry.jsonl
python scripts/analyze_telemetry.py --telemetry <PATH> --team-id <ID> --archive <标签>
python scripts/analyze_telemetry.py --no-archive
```
打印：**完整性**（clean / interleaved，附 metadata.total_frames 对比）、帧数/时长、行驶距离、末帧位置/速度/状态、圈数/进度、速度分布与剖面、最长爬行段、事件。默认会归档到 `.tmp/recordings/<标签>/`。

### 3.3 `analyze_perception_dump.py` — 逐帧感知分析（需要 dump 帧）
```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_basic \
  --control-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/perception_after.json \
  --baseline .tmp/run/perception_before.json \   # 可选：对比中心漂移
  --overlay-dir .tmp/run/overlays \              # 可选：把丢线帧画成 overlay PNG
  --overlay-limit 12
```
对每个 dump 帧重跑 `extract_observation`，按时间戳 join 控制日志：打印**复现差异**（离线 vs 实车）、**感知丢线率**、**中心漂移**（vs baseline）、`normal→lost` 数，并生成 overlay 图（扫描线+中心点）。
**注意**：这里的"感知丢线率"是**逐帧代理指标**，受铁律 #1/#2 约束——不能据它判定驾驶好坏。

### 3.4 `replay_offline.py` — 离线开环回放（需要 dump 帧）
```bash
python scripts/replay_offline.py .tmp/run/frames_basic --out .tmp/run/replay.jsonl
python scripts/analyze_control_log.py .tmp/run/replay.jsonl
```
按时间排序帧 → `reset_*_state()` → `extract_observation→estimate_track→decide_control` → 输出与控制日志**同 schema** 的 JSONL。
**唯一有效用途**：比较"感知/估计改动"对**同一段固定画面**的 `lost/track_conf/obs_points/curvature` 等的影响。**不能**评估速度/转向/圈速/是否完赛（开环固定输入，没有轨迹反馈）。详见 [offline_replay.md](offline_replay.md)。

### 3.5 `validate_submission.py` — 本地合规校验
```bash
python scripts/validate_submission.py submissions/final/team_controller.py
```
检查接口、禁用导入/内置、范围等。提交前必跑。官方 validator：
```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

---

## 4. AI 如何"自己看整场录像"（逐帧回看配方）

这是本项目最强的自主诊断能力，步骤：

1. **在控制日志里定位问题段**：扫 `control_*.jsonl`，找异常 episode（大 `|lateral|` 摆动、持续 `hard_turn`、`lost` 扎堆、`curvature` 饱和、速度骤降等），拿到时间窗。
2. **把那一刻的相机帧渲染出来看**：写一段 inline Python——按时间戳找最近的 `frame_<TAG>_{left,right}.npy`，用 `controller.perception._build_masks`/`_scan_image` 叠加**道路 mask（红）+ 检测中心点（绿）+ 图像中线**，存成 PNG，再用 **Read 工具读这张 PNG**。
3. **对照判断**：摄像头实际看到什么（路往哪弯、有没有蓝门/草地遮挡）vs 控制器算出的 `lateral/heading/curvature` 和发出的 `steering/speed`——找"画面 ↔ 判断"的矛盾。
4. **sanity check**：用领域常识验证（basic 全程右弯；车 lost 时应直线滑行；等）。**别用数字去反推画面**（吃过亏：把 `curvature=-1.0` 脑补成"左弯"，其实是右弯+不稳定拟合的幻觉）。

> 已有的渲染样例在 `.tmp/run/`（`corner*.png`、`bluebar*.png`、`perception_overlays_*`）。这些是一次性产物（`.tmp/` 不入 git），需要时按上面配方重新生成。

---

## 5. 实验记账（只对**真实 Webots run**，人类跑完后）

- `experiments/runs.csv`：一行 = 一次真实测试，字段 `date,commit,mode,track,laps_completed,best_lap,total_time,collisions_major,finish_reason,notes`，`notes` 以 `R0xx |` 开头。
- `experiments/notes.md`：顶部有「记录规范」，每次真实 run 一个 **R0xx** 区块（构建/配置/记录完整性/结果/现象/结论），最新在上。
- **离线分析不建 R-id、不写 runs.csv**（没跑赛道）。离线诊断结论写独立文档（如 `experiments/analysis_*.md`）。
- 改动→测试的迭代闭环流程见 [manual_testing.md](manual_testing.md)。

---

## 6. 一页速查

| 我想… | 用 |
|---|---|
| 看控制器每帧发了什么、为什么慢/丢线/打错方向 | `--debug-log` + `analyze_control_log.py` |
| 看车真实跑到哪、多快、完整性如何 | `analyze_telemetry.py`（看"完整性"行）|
| 看某一帧摄像头看到什么 + 感知输出 | `--dump-frames` → inline 渲染 mask+中心点 PNG → Read 图（第 4 节）|
| 量化感知改动对录制画面的影响 | `--dump-frames` + `analyze_perception_dump.py` 或 `replay_offline.py` |
| 判断一版改动好不好 | **只能人类上车**（铁律 #1）；离线只用来提假设/抓全局回归 |
| 提交前合规 | `validate_submission.py` + 官方 validator |
