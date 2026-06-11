# 手动测试流程

本文描述日常调参闭环：改代码、跑 Webots、看整场摘要和关键窗口逐帧画面、记录结论、清理临时产物。首次安装 Webots 和官方 SDK 见 `docs/official_testing.md`。

## 1. 跑前准备

清理孤儿进程，避免 telemetry 交错：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

如果上一轮强行退出过 Webots，必要时删除 SDK 录制目录里的旧 telemetry：

```bash
rm -f /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl
```

## 2. 构建调试控制器

默认每次实跑都写控制日志：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/team_controller_debug.py
```

需要看整场逐帧画面时，增加 dump 帧：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --dump-frame-stride 3 \
  --out .tmp/run/team_controller_debug.py
```

调试构建含 `open/json/np.save`，只能本地跑，必须配合 `--skip-validate`。正式提交版不要带这些开关。

## 3. 启动 Webots

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world basic --car-slot car_1 --skip-validate

python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world complex --car-slot car_1 --skip-validate
```

practice 模式跑完一圈通常不会自动停，会继续第二圈。看够后退出 Webots；退出后再跑一次：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

## 4. 整场摘要 + 关键窗口取证

每次 run 都要做全局复盘，不能只看末帧或单个指标。这里不是要求人工逐帧看完整场，而是先用全局摘要定位问题，再对关键窗口逐帧看图取证。

1. 看真实轨迹和速度：

```bash
python scripts/analyze_telemetry.py --no-archive
```

记录完整性、最长爬行段、末帧位置、速度剖面。`interleaved` 时只采信脚本切出的最后一段。

2. 看控制器内部行为：

```bash
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl
```

看 `mode`、`mode_reason`、`steering`、`target_steering`、`line_conf`、`left_margin/right_margin`、`margin_risk`、lost/recovering/hard_turn 段。

3. 挑窗口逐帧看，给分析找证据：

- 最长爬行段。
- 撞栏、撞车、偏离白线的肉眼时间窗。
- 大 steering 或 steering 突变段。
- `line_conf` 高但车没骑白线的段。
- `margin_risk` 高但仍向内打轮的段。

4. 对关键窗口生成少量 overlay，看原图、mask、中心线、白线、边界余量和控制日志是否矛盾。具体做法见 `docs/debug_tools.md`。结论里要说明看了哪个时间窗和画面证据，不能只凭数字猜。

## 5. 记录和清理

真实 run 才分配 R-id：

- 在 `experiments/runs.csv` 追加一行，`notes` 以 `R0xx |` 开头。
- 在 `experiments/notes.md` 顶部新增对应 R 区块。
- 有机制解释价值的长分析写 `experiments/analysis_*.md`。
- 只有会反复用于回归的关键失败窗口，才裁剪到 `experiments/cases/<R-id>_<slug>/`。

`analyze_telemetry.py --archive <label>` 只是把当前原始 telemetry 临时复制到 `.tmp/recordings/<label>/`，方便本轮分析。它不是长期归档。长期信息必须写进 `experiments/`。

确认结论写完后清理临时产物：

```bash
rm -rf .tmp .pytest_cache
find . -type d -name '__pycache__' -prune -exec rm -rf {} +
find . -name '.DS_Store' -delete
```

## 6. 正式提交版

确认要上传或做正式验证时，重新生成干净单文件：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/build_submission.py --mode fastest --out submissions/fastest/team_controller.py
python scripts/build_submission.py --mode safe --out submissions/safe/team_controller.py

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
- `.tmp` 变很大：正常，说明 dump 帧或录像还没清理。看完、记录后删除。
