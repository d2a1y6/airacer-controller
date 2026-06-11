# Handoff — R008 之后的 Codex 工作汇总（2026-06-11）

这份文档补充 `experiments/handoff_2026-06-11.md` 之后的工作，供下一个 AI 接手时快速了解：做了什么、实跑结果如何、哪些判断已经被推翻、当前应该从哪里继续。

## 先读顺序

1. `README.md`：仓库入口和产物规则。
2. `CLAUDE.md`：模块边界、命令、提交限制。
3. `docs/human_webots_testing.md`：人类如何守着 Webots 实跑、截图、记录肉眼现象。
4. `docs/ai_offline_review.md`：AI 如何复盘日志、telemetry、相机帧和 overlay。
5. `docs/debug_tools.md`：调试产物类型和 `.tmp` 生命周期。
6. `experiments/notes.md` 最新 R-id：R013/R014 是当前最近实跑结论。
7. 本文。

## 已提交 checkpoint

- 已在开始重构前提交 checkpoint：`16ae3f3 checkpoint: stabilize line following baseline`。
- 该 checkpoint 记录了当时 P1/P2、basic 避车、后置白线修正等工作树状态。
- checkpoint 之后的改动目前集中在当前工作树，并将在本轮整理后提交。

## 代码层改动

本轮尝试把白线和边界从入口层后处理提升到主控制链路：

- `PerceptionObs` 增加：
  - `line_offset`
  - `line_heading`
  - `line_confidence`
  - `left_margin_near`
  - `right_margin_near`
  - `near_obstacle`
- `TrackState` 增加对应字段，供 policy 直接使用。
- `perception.py`：
  - 把白线检测从 `team_controller_local.py` 后置 steering patch 前移到 perception。
  - 白线检测改为扫描少量横带，降低官方 validator 的 p95 耗时。
  - 输出近处静态车标记和白线状态。
- `estimator.py`：
  - 白线可信时融合到目标横向误差、方向误差、lookahead。
  - 估计左右近处边界余量。
- `policy.py`：
  - 增加内侧边界保护，尝试在贴近内侧栏杆时限制继续向内打轮。
  - `hard_turn/recovering` 增加连续帧确认，减少单帧噪声直接触发。
  - debug 状态保存 `mode_reason`、`target_steering`、`target_speed`、风险分量等。
- `team_controller_local.py`：
  - 删除后置白线 steering patch，只保留主链路接线。
- `scripts/build_submission.py` / `scripts/replay_offline.py`：
  - debug/replay JSONL 增加白线、边界、mode reason、目标控制量字段。
- 测试增加或更新：
  - 白线状态输出。
  - estimator 白线融合。
  - policy 内侧边界保护。
  - hard_turn 连续帧确认。
  - replay JSONL 新 schema。

## 实跑结果

### R013 basic

- 结果：按历史坐标代理仍能完成一圈。
- 关键数据：`t≈299.36s` 回到 basic 起点区域，速度 mean=5.238、median=6.090、p95=6.100，近停占比 `<0.3=0.00`。
- 用户反馈：basic 相比 R011 变慢；视觉上仍没有稳定骑在白线上；仍会有不必要打轮和减速。
- 结论：不能写成“basic 无退化”。真实结论是没撞停，但速度和视觉走线都不达标。

### R014 complex

- 结果：未跑通。
- 旧第一左弯卡点 `x≈186,y≈-27` 只爬行约 2.9s 后通过。
- 后续在 `x≈165,y≈119` 贴内侧栏杆撞车/卡死，无法脱困。
- 用户截图确认：本质仍是转弯半径太小、切内线、贴内侧栏杆，不是普通低速点。
- 结论：白线前移和边界保护没有修好核心行为，只能算诊断字段和接口铺垫。

## 重要结论

- “让车沿白线走”还没有真正实现。当前系统即使有 `line_offset/line_heading`，policy 仍可能在弯中继续向内打轮。
- “内侧边界保护”没有在 R014 撞栏前起到足够作用。下一步要用 debug 帧确认：
  - 撞栏前 `left_margin/right_margin` 是否已经变小。
  - `margin_risk` 是否升高。
  - `target_steering` 和最终 `steering` 是否仍指向内侧。
  - `mode_reason` 是 `curve_or_turn_demand`、`recovery_buffer_or_confidence` 还是其他。
  - `escaping` 为什么没有触发或触发无效。
- 不要继续只调速度或全局 gain。下一步要抓 R014 这种撞栏窗口的相机帧和 overlay，用画面证明问题链路。

## 文档和仓库整理

本轮还做了文件管理整理：

- 删除 `docs/repository_map.md`，避免和 README 双维护。
- 精简 `README.md`，只保留入口信息、目录约定、常用命令、产物规则。
- 重写并改名 `docs/human_webots_testing.md`：
  - 只写人类守着 Webots 实跑的流程：构建调试控制器、启动 Webots、肉眼记录车身相对白线/栏杆/障碍物的位置，把 `.tmp/run` 产物交给 AI。
  - 不再要求人类跑完整日志分析，也不要求人工逐帧看完整场。
- 重写并改名 `docs/ai_offline_review.md`：
  - AI 接手人类反馈、telemetry、控制日志、相机帧和截图后，先看全局摘要，再挑关键窗口逐帧取证。
  - 明确“整场 review”不是逐帧看完整场，而是分析必须能被关键窗口画面或 overlay 支撑。
- 更新 `docs/debug_tools.md`：
  - 它只保留调试数据来源、产物生命周期、常用命令和归档规则。
  - 人类实跑流程与 AI 离线复盘流程分别跳转到上面两份文档。
- 新增 `experiments/cases/README.md`：
  - 只允许保存裁剪后的关键失败窗口。
  - 禁止提交整场 `.npy` 帧、整场录像、批量 overlay。
- `.gitignore` 增加 `*.npy`、`*.npz`，避免整场相机帧误提交。
- 已清理 `.tmp`、`.pytest_cache`、`__pycache__`、`.DS_Store`。

## 当前推荐下一步

1. 生成 debug 构建，针对 R014 `x≈165,y≈119` 重新跑 complex。
2. 开启 `--debug-log`；需要视觉证据时开启 `--dump-frames`，stride 可先用 3，撞栏短窗口再用 1。
3. 用 telemetry 找最长爬行/撞栏窗口，用控制日志找对应 `mode_reason/target_steering/margin_risk/line_conf`。
4. 渲染 3-5 张 overlay，必须看图判断：
   - 白线是否在画面中。
   - 白线识别是否符号正确。
   - 道路中心/边界是否被污染。
   - policy 为什么继续向内打轮。
5. 把结论写入 `experiments/notes.md`。只有这个窗口会反复用于回归时，才裁剪到 `experiments/cases/`。
6. 清理 `.tmp`。

## 验证状态

最近一次整理后运行过：

```bash
pytest -q
python scripts/validate_submission.py submissions/final/team_controller.py
python scripts/validate_submission.py submissions/fastest/team_controller.py
python scripts/validate_submission.py submissions/safe/team_controller.py
```

结果：70 个测试通过，三个 submission validator 通过。
