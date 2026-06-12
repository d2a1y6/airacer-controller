# 当前状态（接手从这里开始）

最后更新：2026-06-12。当前分支：`codex/perception-dropout`。
交接基线提交：`b3188d4 Record R038 best human baseline`。

## 一句话结论

当前 `submissions/final/team_controller.py` 是目前人眼确认的最好版本，但还没完成。
R038 人工 Webots 复跑显示：绝大多数弯不再剐蹭，轻蹭也能自己擦出；残留问题是弯中转弯半径仍偏小，车身会落到中间白线内侧，至少一处轻蹭。

不要合 main。不要把 R026/R038 case 标成完成。

## 当前最好版本

- 控制代码版本：commit `ab58b74` 起的 Phase 2.2 控制器；`b3188d4` 只新增记录和归档，没有改控制代码。
- 提交文件：`submissions/final/team_controller.py`
- MD5：`f4b79c09f6811580817ecfe04d1fb11a`
- 已保存快照：`baselines/R038_phase22_best_human_2026-06-12/`
- R038 记录：`experiments/notes.md` 的 R038，`experiments/runs.csv` 最后一行。
- R038 报告图：`experiments/figures/R038_best_human_residual_tight_radius/`
- R038 open case：`experiments/cases/R038_residual_tight_radius/`

## 已解决到什么程度

R038 复跑数据：

- 时间：`t=0.03→330.14s`
- telemetry：无 collision/checkpoint 等事件，无近停，末帧 `status=normal`
- 控制日志：全程 `lost=0`，`mean|lat|=0.069`，低命令速度 `<0.3` 约 1%
- 人工观察：多数弯已经不剐蹭，轻蹭也不会卡死

这说明 Phase 2.2 已经解决了旧版本的大部分长爬行、卡栏、卡死问题。

## 还没解决的问题

核心残留：弯中仍切内线，转弯半径偏小。

R038 的代表窗口是 `t=226.0→230.2`：

- `line_offset` 中位数 `+0.374`，最高 `+0.754`
- `line_conf=0` 有 10/131 帧
- `|line_offset|>0.35` 有 74/131 帧
- overlay 显示真实虚线仍在路面内，但每侧通常只拿到 3-4 个点

驾驶含义：左弯里白线在近处偏到车右侧，说明车已经落到白线内侧。白线没有完全失效，但证据稀疏、来得偏晚。

## 为什么不是简单调大半径

这里没有独立的“转弯半径”旋钮。最终舵角来自三类东西混合：

- road-mask 的道路几何和远处弯道预判
- 中间白色虚线的 offset/heading
- 速度、hard_turn、escape 等策略门控

如果全局减小入弯舵角，真实急弯可能过不去或跑到外侧。如果继续放宽白线检测，容易重新把栏杆、车身、路牙当成中心线。R038 的机制更像：弯中白线短暂低置信时，road-mask 继续按弯道预判向内切；等白线重新稳定时，车已经在线内侧，只能事后回正。

## 下一步建议

优先做一个小而可验证的改动：

1. 在 hard_turn 且 line_conf 低/短暂为 0 时，保留上一段可信白线的 offset 记忆，不要立刻完全回到 road-mask 预判。
2. 只在“上一段可信白线显示车已在内侧”时加轻微向外保守偏置，避免全局收舵。
3. 用 R038 case 的 `t=226.0→230.2` 做回归窗口，检查 `line_offset` 是否更早回 0，overlay 是否仍没有误锁栏杆/车辆。
4. AI 先自己跑 Webots 到目标窗口并看 telemetry/control log/overlay。若结果已经接近完成，再让人类做关键验收，确认车身是否稳定骑在中间白色虚线上。

不要优先做这些：

- 不要全局降低 `max_abs_steering` 或简单减小所有弯道舵角。
- 不要继续堆 escape。R038 的问题是常规入弯走线偏内，不是卡住后脱困不够强。
- 不要只看 `lost=0` 或无 collision。R038 已经无 lost、无事件，但人眼仍能看到半径偏小。

## 必读证据

- 当前最新叙事：`experiments/notes.md` 的 R038
- 当前 residual case：`experiments/cases/R038_residual_tight_radius/README.md`
- 当前 best baseline：`baselines/R038_phase22_best_human_2026-06-12/README.md`
- 报告图说明：`experiments/figures/R038_best_human_residual_tight_radius/CAPTION.md`
- 历史第一左弯 case：`experiments/cases/R026_first_left_tight_radius/README.md`
- 人工测试流程：`docs/human_webots_testing.md`
- AI 离线复盘流程：`docs/ai_offline_review.md`

## 项目铁律

1. AI 可以自己跑 Webots、看日志和截图做日常迭代；关键验收节点再请人类肉眼确认。
2. `lost` 率不是质量指标。车 lost 时可能直线滑行，lost 多不必然差；lost 少也不代表骑线好。
3. policy/速度/走线改动不能只靠离线数字定好坏。AI 自跑必须配合 telemetry、control log 和 overlay；准备标完成、合 main 或提交 final 前要人工确认。
4. 感知改动要看整场和关键窗口，不能只看一个点。
5. 调试构建禁上传；最终只交 `submissions/final/team_controller.py`，提交前跑 validator 和测试。
6. 清 `.tmp` 前先把关键窗口裁进 `experiments/cases/` 或 `experiments/figures/`。R038 已归档，可以清理本轮 `.tmp`。

## 常用命令

```bash
pytest -q
python scripts/validate_submission.py submissions/final/team_controller.py
python scripts/analyze_control_log.py .tmp/run/control_complex.jsonl
python scripts/analyze_telemetry.py --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl --no-archive
python scripts/analyze_perception_dump.py .tmp/run/frames_complex --control-log .tmp/run/control_complex.jsonl --overlay-dir .tmp/overlays --at 226.56,228.48,229.44
```
