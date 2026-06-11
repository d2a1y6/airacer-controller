# 调试工具与产物规则

本文是调试数据和产物生命周期说明。具体流程分两份：

- 人类守着 Webots 跑车、截图、记录肉眼现象：`docs/human_webots_testing.md`
- AI 接手日志、telemetry、帧和截图后做离线复盘：`docs/ai_offline_review.md`

## 1. 基本原则

- 真实 Webots / 平台画面是最终裁判；日志和离线回放只用来解释原因。
- 人类负责实跑和肉眼判断；AI 负责复盘日志、telemetry、帧和 overlay。
- AI 的“整场 review”不是逐帧看完整场，而是先看全局摘要，再挑关键窗口逐帧看画面。分析必须有画面或 overlay 作证。
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

## 4. AI 离线复盘入口

真实 run 结束后，AI 按 `docs/ai_offline_review.md` 复盘。目标是从整场记录里找需要看的片段，而不是把每一帧都人工看完。下面只保留常用命令索引。

看 telemetry 全局：

```bash
python scripts/analyze_telemetry.py --no-archive
```

看控制日志全局：

```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
```

生成关键窗口 overlay：

```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_basic \
  --control-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/perception_after.json \
  --overlay-dir .tmp/run/overlays \
  --overlay-limit 12
```

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
