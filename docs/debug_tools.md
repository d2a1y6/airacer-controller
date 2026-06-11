# 调试工具与产物规则

本文是调试数据、工具命令、整场摘要复盘、关键窗口逐帧取证和产物归档的权威说明。AI 接手实跑问题前先读这里。

## 1. 基本原则

- 真实 Webots / 平台画面是最终裁判；日志和离线回放只用来解释原因。
- 每次实跑后都要看整场摘要，再挑关键窗口逐帧看画面。不是要求逐帧看完整场，而是要求分析必须有画面或 overlay 作证。
- `.tmp/` 是临时工作区，不是仓库归档区。看完、提炼结论后要清理。
- 长期仓库资产只保存结论、裁剪后的关键 case、稳定 baseline 和脚本。
- 调试构建含 `open/json/np.save`，只能本地跑，不能上传平台。

## 2. 数据来源

| 来源 | 常见路径 | 用途 | 保存策略 |
|---|---|---|---|
| 控制器 debug log | `.tmp/run/control_*.jsonl` | 每帧内部状态、目标、输出、mode、风险字段 | 看完全局和关键窗口后，摘要写进 notes；原始整场日志删掉 |
| dump 帧 | `.tmp/run/frames_*/*.npy` | 左右相机逐帧画面，生成 overlay 和离线回放 | 只临时保存；整场 `.npy` 不进 git |
| overlay PNG | `.tmp/run/*overlay*` | 查看画面、mask、中心线、白线、边界 | 批量图看完即删；最多裁剪 1-3 张进 case |
| supervisor telemetry | SDK `.local/recordings/telemetry.jsonl` | 真实位置、速度、爬行段、事件 | 整场复制件只临时留存；长期写摘要或裁剪窗口 |
| `live_view.jpg` | SDK `.local/recordings/live_view.jpg` | 俯视快照 | 一般不保存；关键时裁剪进 case |
| debug controller | `.tmp/run/team_controller_debug.py` | 本地带日志/存帧控制器 | 可重建，看完删 |

## 3. 调试构建

只写控制日志：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/team_controller_debug.py
```

需要逐帧看画面时再 dump 全场帧：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --dump-frame-stride 3 \
  --out .tmp/run/team_controller_debug.py
```

说明：

- 控制日志每帧都写，体积较小，应默认开启。
- dump 帧很大，通常一圈数 GB。只有定位视觉/走线问题时开启。
- `--dump-frame-stride 3` 适合整场回看；需要精确撞栏窗口时可对短跑用 stride 1。

## 4. 整场摘要 + 关键窗口取证流程

每次真实 run 结束后按这个顺序看，不要跳步。目标是从整场记录里找需要看的片段，而不是把每一帧都人工看完。

1. 看 telemetry 全局：

```bash
python scripts/analyze_telemetry.py --no-archive
```

重点看完整性、末帧位置、速度剖面、最长爬行段、事件。`interleaved` 时只能采信脚本切出的最后一段。

2. 看控制日志全局：

```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
```

重点看速度、转向震荡、mode 占比、lost 段、`margin_risk`、`line_conf`、`mode_reason`。

3. 列出关键窗口：

- 最大爬行段。
- 大 `|steering|` 或 steering 突变段。
- 持续 `hard_turn` / `recovering` / `lost` 段。
- 用户肉眼看到的撞栏、撞车、偏离白线时间窗。
- `line_conf` 高但车没压白线的窗口。
- `margin_risk` 高但仍继续向内打轮的窗口。

4. 对关键窗口渲染少量 overlay 作为证据：

- 每个窗口通常取 3-5 帧：进入前、异常中、异常后。
- overlay 至少要能看原图、道路 mask、扫描中心、白线状态、左右边界。
- 对照 debug log 的 `target_steering/steering/mode_reason/line_conf/left_margin/right_margin` 判断矛盾点。
- 结论里应写清楚看了哪个时间窗、画面显示了什么、日志字段如何对应；避免凭空推断。

5. 写结论并清理：

- 真实 run 写 `experiments/runs.csv` 和 `experiments/notes.md`。
- 机制分析写 `experiments/analysis_*.md`。
- 反复要用的失败窗口裁剪进 `experiments/cases/`。
- 删除 `.tmp` 原始产物。

## 5. 工具命令

### 控制日志分析

```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
python scripts/analyze_control_log.py .tmp/run
```

### 遥测分析

```bash
python scripts/analyze_telemetry.py --no-archive
python scripts/analyze_telemetry.py --archive basic_R015
```

`--archive` 只把原始 telemetry 临时复制到 `.tmp/recordings/<label>/`，方便本轮分析。它不是长期归档；长期记录仍写 `experiments/notes.md` 和 `runs.csv`。

### 感知 dump 分析

```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_basic \
  --control-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/perception_after.json \
  --overlay-dir .tmp/run/overlays \
  --overlay-limit 12
```

### 开环回放

```bash
python scripts/replay_offline.py .tmp/run/frames_basic --out .tmp/run/replay.jsonl
python scripts/analyze_control_log.py .tmp/run/replay.jsonl
```

开环回放只比较同一段固定画面下 perception/estimator/policy 的输出变化。它不能判断圈速、是否完赛、是否会真实撞栏。

### 提交文件校验

```bash
pytest -q
python scripts/validate_submission.py submissions/final/team_controller.py
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

## 6. 长期归档规则

| 内容 | 长期位置 | 说明 |
|---|---|---|
| 每次真实 run 摘要 | `experiments/runs.csv` | 一行一个 R-id |
| 肉眼现象和结论 | `experiments/notes.md` | 最新在上 |
| 机制分析 | `experiments/analysis_*.md` | 只保存有解释价值的分析 |
| 小型失败窗口 | `experiments/cases/<R-id>_<slug>/` | 只保存裁剪窗口和少量 overlay |
| 稳定可回退版本 | `baselines/<name>/` | 控制器、参数、证据说明 |

禁止长期保存：

- 整场 `.npy` 左右帧。
- 整场录像或批量截图。
- 整场原始 telemetry 复制件。
- 临时 debug controller。
- 临时 SDK 克隆。
- cache、`.DS_Store`、`__pycache__`。

## 7. 清理命令

确认结论已写入 `experiments/` 后：

```bash
rm -rf .tmp .pytest_cache
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -name '.DS_Store' -delete
```

清理后可检查：

```bash
git status --short --ignored
find . -maxdepth 3 \( -name '.tmp' -o -name '.pytest_cache' -o -name '__pycache__' -o -name '.DS_Store' \) -print
```
