# 人类 Webots 实跑手册

本文给守在 Webots 前的人看。目标是把车真实跑起来，用肉眼记录现象，并把可复盘的日志和画面留给 AI。这里不要求人类跑完整的日志分析，也不要求人工逐帧看录像；AI 的离线复盘流程见 `docs/ai_offline_review.md`。

首次安装 Webots 和官方 SDK 见 `docs/official_testing.md`。

## 1. 一键启动（推荐）

```bash
# 只带控制日志
bash scripts/webots_run.sh basic
bash scripts/webots_run.sh complex

# 这轮要分析白线、撞栏、视觉误判时，加相机帧（很大，仅取证时用；撞栏短窗口用 --frames 1）
bash scripts/webots_run.sh complex --frames 3
```

脚本会自动：清理孤儿 Webots / run_local 进程和旧遥测（避免 telemetry 交错）、把上一轮 `.tmp/run` 轮换成 `.tmp/run.prev`、构建带控制日志的调试控制器、用 `--skip-validate` 启动 Webots。

调试构建含 `open/json/np.save`，只能本地跑。正式提交版不要带这些开关。

practice 模式跑完一圈通常不会自动停，会继续第二圈。看够后退出 Webots，再清一次进程：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

如需手工分步执行（自定义 mode、输出路径等），等价命令是 `scripts/build_submission.py --debug-log ... [--dump-frames ... --dump-frame-stride N] --out .tmp/run/team_controller_debug.py`，再用 SDK `run_local.py --skip-validate` 启动；细节见 `docs/ai_offline_review.md` 第 1 节。

## 2. 肉眼观察要记什么

人类观察比脚本更重要。请尽量记录这些事实：

- 赛道：`basic` 或 `complex`。
- 是否跑完一圈；如果没跑完，在哪里停住或撞上。
- 车相对白线的位置：车身中心骑线、长期在线左、长期在线右、入弯切内线、出弯能否回线。
- 撞车或撞栏对象：左/右栏杆、白车、黑车、其他。
- 异常行为：突然大幅打轮、无意义减速、原地挣扎、能否自行脱困。
- 大致时间或位置：Webots 时间、起终点附近、第几个弯、截图。

截图很有价值。能截就截，但不要为了截图中断关键观察。

## 3. 跑完交给 AI

跑完后，把肉眼结论告诉 AI，并说明 `.tmp/run/` 里有哪些产物，例如：

- `.tmp/run/control_basic.jsonl`
- `.tmp/run/frames_basic/`
- SDK telemetry：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`

**人类不要手动删 `.tmp`**。下一次 `scripts/webots_run.sh` 会自动轮换旧产物；全量清理由 AI 在确认结论已写入 `experiments/`、且 notes 的"下一步"不依赖这些产物后执行（见 `docs/ai_offline_review.md` 第 7 节）。

## 4. 正式提交版

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
