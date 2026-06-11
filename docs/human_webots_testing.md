# 人类 Webots 实跑手册

本文给守在 Webots 前的人看。目标是把车真实跑起来，用肉眼记录现象，并把可复盘的日志和画面留给 AI。这里不要求人类跑完整的日志分析，也不要求人工逐帧看录像；AI 的离线复盘流程见 `docs/ai_offline_review.md`。

首次安装 Webots 和官方 SDK 见 `docs/official_testing.md`。

## 1. 跑前清理

先清掉上一轮可能残留的 Webots 和本地 runner，避免 telemetry 混在一起：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

如果上一轮强退过 Webots，可删除 SDK 旧遥测：

```bash
rm -f /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl
```

## 2. 构建本地调试控制器

默认带控制日志，方便 AI 跑后复盘：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/team_controller_debug.py
```

如果这轮要分析白线、撞栏、视觉误判，提前保存相机帧：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --dump-frame-stride 3 \
  --out .tmp/run/team_controller_debug.py
```

调试构建含 `open/json/np.save`，只能本地跑，必须配合 `--skip-validate`。正式提交版不要带这些开关。

## 3. 启动 Webots

basic：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world basic --car-slot car_1 --skip-validate
```

complex：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world complex --car-slot car_1 --skip-validate
```

practice 模式跑完一圈通常不会自动停，会继续第二圈。看够后退出 Webots，再清一次进程：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

## 4. 肉眼观察要记什么

人类观察比脚本更重要。请尽量记录这些事实：

- 赛道：`basic` 或 `complex`。
- 是否跑完一圈；如果没跑完，在哪里停住或撞上。
- 车相对白线的位置：车身中心骑线、长期在线左、长期在线右、入弯切内线、出弯能否回线。
- 撞车或撞栏对象：左/右栏杆、白车、黑车、其他。
- 异常行为：突然大幅打轮、无意义减速、原地挣扎、能否自行脱困。
- 大致时间或位置：Webots 时间、起终点附近、第几个弯、截图。

截图很有价值。能截就截，但不要为了截图中断关键观察。

## 5. 跑完交给 AI

跑完后，把肉眼结论告诉 AI，并说明 `.tmp/run/` 里有哪些产物，例如：

- `.tmp/run/control_basic.jsonl`
- `.tmp/run/frames_basic/`
- SDK telemetry：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`

如果需要 AI 复盘，不要先删 `.tmp`。AI 看完并把结论写进 `experiments/` 后，再清理临时产物。

如果本轮只是快速肉眼确认，不需要离线复盘，可以清理：

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
- `.tmp` 变很大：通常是 dump 帧还没清理。AI 复盘并记录结论后删除。
