# Webots 实跑手册

本文给需要启动 Webots 的人或 AI 看。目标是把车真实跑起来，留下可复盘的控制日志、telemetry 和相机帧；如果是关键验收节点，再由人类肉眼确认走线质量。这里不要求人类跑完整的日志分析，也不要求人工逐帧看录像；AI 的复盘流程见 `docs/ai_offline_review.md`。

首次安装 Webots 和官方 SDK 见 `docs/official_testing.md`。

## 1. 一键启动（推荐）

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

脚本会自动：清理孤儿 Webots / run_local 进程和旧遥测（避免 telemetry 交错）、把上一轮 `.tmp/run` 轮换成 `.tmp/run.prev`、构建带控制日志和帧存储的调试控制器、用 `--skip-validate` 启动 Webots。

启动后终端会打印 team_controller stdout/stderr 镜像日志位置，例如：

```bash
team_controller stdout/stderr tee → /.../airacer-controller/.tmp/run/webots_console/*.log
```

AI 可以实时看：

```bash
tail -f .tmp/run/webots_console/*.log
```

跑完后同一个目录也能直接读取。这里抓的是 **team_controller/controller 进程里的 `stdout/stderr`**，包括学生控制器 `print` 和导入错误。它不是完整 Webots GUI console，也不是 supervisor 碰撞日志；擦栏/碰栏仍要靠肉眼、截图、overlay、车身位置和 telemetry 综合判断。

注意区分两类碰撞信号：

- telemetry 的 `collision` event 主要来自 supervisor 的车车碰撞判定。
- Webots/物理引擎 console 里类似“发生碰撞，只计算其中最重要的 N 个碰撞点”的提示，通常表示车体碰到了栏杆、路沿或其它静态几何。即使 telemetry 没有 collision event，也要把它记成碰栏/接触。

调试构建含 `open/json/np.save`，只能本地跑。正式提交版不要带这些开关。

practice 模式跑完一圈通常不会自动停，会继续第二圈。看够后退出 Webots，再清一次进程：

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

如需手工分步执行（自定义 mode、输出路径等），等价命令是 `scripts/build_submission.py --debug-log ... [--dump-frames ... --dump-frame-stride N] --out .tmp/run/team_controller_debug.py`，再用 SDK `run_local.py --skip-validate` 启动；细节见 `docs/ai_offline_review.md` 第 1 节。

## 2. 观察要记什么

日常迭代可以由 AI 自己跑 Webots、看日志和截图。关键验收时，人类观察仍很重要。请尽量记录这些事实：

- 赛道：`basic` 或 `complex`。
- 是否跑完一圈；如果没跑完，在哪里停住或撞上。
- 车相对白线的位置：车身中心骑线、长期在线左、长期在线右、入弯切内线、出弯能否回线。
- 撞车或撞栏对象：左/右栏杆、白车、黑车、其他。
- Webots console 是否出现接触点提示，例如“发生碰撞，只计算其中最重要的 N 个碰撞点”。
- 异常行为：突然大幅打轮、无意义减速、原地挣扎、能否自行脱困。
- 大致时间或位置：Webots 时间、起终点附近、第几个弯、截图。

截图很有价值。能截就截，但不要为了截图中断关键观察。

### 当前 Phase 2.2 complex 验收清单

这轮只需要回答一个核心问题：车在 complex 过弯时，视觉上是否沿着中间白色虚线走，而不是切到内侧栏杆。AI 可以先自跑并筛候选；当 AI 判断已经接近解决，或准备标完成/合 main/提交 final 时，再让人类按这张表确认。

建议从头跑：

```bash
bash scripts/webots_run.sh complex
```

重点看这些窗口，看到异常就记时间/截图：

| 窗口 | 大致时间/位置 | 要看什么 |
|---|---|---|
| 第一个左弯 | `t≈27→43`，`x≈170→199,y≈-30→6` | 是否还擦左栏；车身是否从偏离虚线回到中间虚线附近 |
| 旧后段内切点 | `t≈130→185`，旧 `x≈169,y≈111` 附近 | 是否再次贴内侧栏杆或长时间慢爬 |
| 旧 R018 风险窗 | `t≈280→330`，`x≈9,y≈87` 到起点前 | 是否突然切进内侧、是否把栏杆/白车当虚线 |
| 旧 R024 空间点 | `x≈-42,y≈124` 附近 | 是否能顺着虚线过弯，不贴栏停住 |
| 旧起点前 | `x≈-10,y≈-27` / `x≈28,y≈-28` | 是否还有起点前长时间近停或贴栏挣扎 |

反馈时尽量用下面的格式：

```text
R0xx human complex:
- 第一个左弯：通过 / 擦左 / 撞左 / 没骑线，时间约 ...
- 旧 x≈169,y≈111：通过 / 贴栏 / 慢爬，时间约 ...
- 旧 x≈-42,y≈124：通过 / 贴栏 / 慢爬，时间约 ...
- 起点前：通过 / 近停 / 撞栏，时间约 ...
- 总体走线：车身中心基本压白色虚线 / 长期在线左 / 长期在线右 / 入弯切内
- 截图或备注：
```

## 3. 跑完交给 AI 或进入复盘

跑完后，把观察结论告诉 AI，并说明 `.tmp/run/` 里有哪些产物。如果是 AI 自跑，也要把这些结论写进 notes 或下一步分析里，例如：

- `.tmp/run/control_basic.jsonl`
- `.tmp/run/webots_console/*.log`（team_controller stdout/stderr，不保证包含 Webots/supervisor 碰撞日志）
- `.tmp/run/frames_basic/`
- SDK telemetry：`/Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl`
- 如果 Webots GUI/物理引擎 console 出现接触点提示，也要把原文或大意写进反馈。

**不要手动删 `.tmp`**。下一次 `scripts/webots_run.sh` 会自动轮换旧产物；全量清理由 AI 在确认结论已写入 `experiments/`、且 notes 的"下一步"不依赖这些产物后执行（见 `docs/ai_offline_review.md` 第 8 节）。

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
