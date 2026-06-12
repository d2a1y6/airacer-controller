# 实验和证据索引

`experiments/` 保存真实 run 的状态、台账、叙事、失败窗口和报告图。它不是 `.tmp/` 的替代品；整场原始帧、整场录像、批量 overlay 默认只放 `.tmp/`。

## 先读什么

| 文件或目录 | 作用 |
|---|---|
| `STATUS.md` | 唯一活动交接文档。新接手先读这里，了解当前 best、未解问题、下一步。 |
| `runs.csv` | 结构化台账。一行是一轮真实 Webots/platform run。 |
| `notes.md` | 按 R-id 倒序的实验叙事：肉眼观察、数据摘要、结论、下一步。 |
| `cases/README.md` | 失败窗口归档规则。 |
| `figures/README.md` | 报告图/长期可视化归档规则。 |
| `analysis_*.md` | 有机制解释价值的专题分析。 |

只有真实 Webots/platform run 才分配 R-id 并写入 `runs.csv`。离线回放、脚本分析和开环试验只写进对应 R-id 的 notes 或临时 `.tmp`，不单独建 R-id。

## cases 和 figures 的区别

| 目录 | 存什么 | 目的 | 生命周期 |
|---|---|---|---|
| `cases/` | 最小失败窗口、裁剪 control/telemetry、1-3 张关键 overlay | 复现 bug、做回归、交接机制 | 问题解决后可关闭或删除 |
| `figures/` | 整场轨迹图、关键感知标注帧、报告对比图 | 报告叙事和长期回查 | 长期保留，进 git |

判断规则：

- 以后还要拿它验证 bug 有没有复现：放 `cases/`。
- 报告要贴、或之后想回看这版开得怎么样：放 `figures/`。
- 只是这次分析用的整场帧、批量 overlay、原始 telemetry 复制件：留在 `.tmp/`，不要提交。

当前重要 case：

- `cases/R026_first_left_tight_radius/`：第一左弯半径过小历史失败，open。
- `cases/R038_residual_tight_radius/`：当前 best 的残留弯中半径偏小窗口，open。

当前重要 figure：

- `figures/R038_best_human_residual_tight_radius/`：当前最好版本 R038 的总览和关键 overlay。

## 一轮 run 后怎么记录

1. 人类按 `docs/human_webots_testing.md` 跑 Webots，记录肉眼现象。
2. AI 按 `docs/ai_offline_review.md` 看 telemetry、控制日志、帧和 overlay。
3. 在 `runs.csv` 追加一行，`notes` 以 `R0xx |` 开头，只写短结论。
4. 在 `notes.md` 顶部追加对应 R-id 的完整叙事。
5. 如果有可复现失败窗口，按 `cases/README.md` 裁剪；如果有报告图，按 `figures/README.md` 归档。
6. 更新 `STATUS.md`，只保留当前接手需要知道的状态和下一步。

## 清理原则

`.tmp/` 可以删除，但删前要确认：

- 关键失败窗口已经裁进 `cases/`。
- 报告要用的图已经进 `figures/`。
- 当前最好版本如果需要回退，已经快照到 `baselines/`。

R038 已完成这些归档，所以本轮 `.tmp` 可清理。
