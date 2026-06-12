# AI Racer Controller

本仓库用于开发 AI Racer 控制器。平台每帧传入左右摄像头图像和时间戳，控制器返回方向和速度：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

最终交付物是单文件 `team_controller.py`。日常开发在 `controller/`，提交文件由脚本生成到 `submissions/`，不要手工改生成文件。

策略接口按是否有其他车分成两类：`no_other_cars` 和 `with_other_cars`。当前实现的是 `no_other_cars`；`with_other_cars` 只留入口，尚未实现。历史上的 `fastest` / `safe` / `final` 只是兼容旧输出名，不再代表策略分支。

## 新接手先读

1. **当前状态**：先读 `experiments/STATUS.md`。这里记录当前 best、已解决的问题、还剩什么、下一步怎么做。
2. **仓库结构**：读本 README，知道东西放在哪。
3. **改代码**：读 `CLAUDE.md`，里面是模块边界、构建方式、提交限制和工作约定。
4. **理解控制逻辑**：读 `docs/technical_manual.md`，它讲一帧图像如何变成舵角和速度。
5. **跑车和复盘**：跑 Webots 看 `docs/human_webots_testing.md`；跑完诊断看 `docs/ai_offline_review.md`；找脚本入口看 `scripts/README.md`。

根 README 不维护命令清单。构建、校验、Webots 实跑、日志分析、跳点回放等命令都看 `scripts/README.md`；官方 SDK / validator 看 `docs/official_testing.md`。

## 仓库地图

| 路径 | 放什么 | 什么时候看 |
|---|---|---|
| `controller/` | 控制器源码：感知、估计、策略、参数、接线 | 改算法时 |
| `submissions/` | 生成出来的单文件提交版 | 提交或校验单文件时 |
| `scripts/` | 构建、校验、Webots 实跑、日志分析、回放、画图工具 | 找命令和工具入口时 |
| `tests/` | 单元测试、脚本测试、提交文件静态检查 | 改代码后验证时 |
| `docs/` | 技术手册、测试流程、官方 SDK、人工/AI 复盘说明 | 需要流程或背景说明时 |
| `experiments/` | run 台账、叙事记录、当前状态、case、报告图 | 查历史、接手、写报告时 |
| `baselines/` | 已确认值得保留的控制器快照 | 回退或比较当前 best 时 |
| `.tmp/` | 本地临时产物：调试构建、日志、帧、overlay、录像 | 当前 run 复盘时；不进 git |

核心流水线是：

```text
left_img/right_img
→ perception.extract_observation()
→ estimator.estimate_track()
→ policy.decide_control()
→ clamp_cmd()
→ steering/speed
```

模块间数据结构在 `controller/common.py`。改字段时，要同步调用方、构建脚本、测试和相关文档。

## 当前代码结构

控制器的边界尽量保持简单：

| 文件 | 当前职责 | 接手风险 |
|---|---|---|
| `controller/common.py` | `PerceptionObs`、`TrackState`、`ControlCmd` 和限幅工具 | 字段是模块契约，改动会影响全链路 |
| `controller/perception.py` | 道路 mask、白线、边界点、近障碍感知 | 颜色阈值和白线门控直接影响所有下游信号 |
| `controller/estimator.py` | 把感知点拟合成横向误差、前瞻、方向、曲率和白线状态 | 带跨帧平滑、lost 衰减、红色环境锁存 |
| `controller/policy.py` | 状态机、入弯门控、速度规划、脱困和白线后置修正 | 复杂度最高，很多行为来自 R042-R049 实跑取证 |
| `controller/params.py` | 色卡、视觉、估计、控制参数唯一来源 | 参数密集，小改可能改变整场行为 |
| `controller/opponent.py` | 近处车身/障碍检测 | 工具已保留，避让策略还没实现 |
| `controller/team_controller_local.py` | 平台入口接线和异常兜底 | 不放算法 |

当前最值得注意的缺口：

- `with_other_cars` 没有实现，末段蹭静止车属于缺避让逻辑。
- 官方 validator 通过，但 `control()` 有 W014 性能软警告；继续上线前应 profile `perception.py`。
- R049 后个别中等弯半径不一致，优先查 `curve_risk` 感知一致性，而不是先调速度。

## 按任务找文档

| 你要做什么 | 去哪里 |
|---|---|
| 接手当前工作 | `experiments/STATUS.md` |
| 看 agent 工作规则 | `CLAUDE.md`、`AGENTS.md` |
| 理解控制器整体逻辑 | `docs/technical_manual.md` |
| 跑一次 Webots | `docs/human_webots_testing.md` |
| 跑完后诊断日志/截图 | `docs/ai_offline_review.md` |
| 找构建、校验、分析脚本 | `scripts/README.md` |
| 查官方测试和 SDK | `docs/official_testing.md`、`docs/official_test_matrix.md` |
| 查某次 run 的结论 | `experiments/runs.csv`、`experiments/notes.md` |
| 看当前问题的证据 | `experiments/cases/` |
| 找报告图 | `experiments/figures/` |
| 找可回退版本 | `baselines/README.md` |

## 实验记录怎么分工

`experiments/` 是长期证据区，不是 `.tmp/` 的复制品。

- `STATUS.md`：唯一活动交接文档。新会话从这里开始。
- `runs.csv`：结构化 run 台账，一行是一轮真实 Webots / platform run。
- `notes.md`：按 R-id 倒序写每轮 run 的现象、数据、结论和下一步。
- `cases/`：最小失败窗口，用来复现 bug 和做回归。
- `figures/`：报告图和长期回查图。

AI 分析完每个有意义的 run 后，默认要同步更新 `runs.csv` 和 `notes.md`。误启动、脚本没真正开始、超短无信息、重复跑同一版本且没有新现象，可以不记，但要说明原因。

## 临时产物和归档

`.tmp/` 可以很大，也可以清理。清理前先确认：

- 关键失败窗口已经裁进 `experiments/cases/`；
- 报告要用的图已经进 `experiments/figures/`；
- 值得回退的控制器已经存到 `baselines/`。

不要提交整场帧、整场录像、批量截图或临时 telemetry 复制件。
