# AI Racer Controller

本仓库用于开发 AI Racer 控制器。最终交付物是单文件 `team_controller.py`，平台每帧传入左右摄像头图像和时间戳，控制器返回：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

`steering` 范围是 `[-1, 1]`，`speed` 范围是 `[0, 1]`。当前 `fastest`、`safe`、`final` 生成文件使用同一套 `CONTROL` 参数。

## 文档地图（先读什么）

每份文档只负责一件事，按需读，不要互相抄：

| 文档 | 负责 | 什么时候读 |
|---|---|---|
| **`experiments/STATUS.md`** | 唯一活动交接文档：当前状态、铁律、未解问题、下一步 | **新接手第一份，永远先读** |
| `CLAUDE.md` | 给 coding agent 的项目约定：模块边界、参数源、提交限制、构建机制 | 改任何代码前 |
| `README.md`（本文件） | 仓库导航：目录约定、文档地图、常用命令 | 想知道东西放在哪、有哪些命令 |
| `TASK.md` | 上游任务/平台规格（接口、规则、限制），静态参考 | 需要确认平台行为或赛制细节 |
| `docs/official_testing.md` | 官方 SDK 与 Webots 安装、官方 validator | 首次配环境、提交前跑官方校验 |
| `docs/human_webots_testing.md` | 人类守着 Webots 实跑、肉眼记录的流程 | 准备上车跑一轮 |
| `docs/ai_offline_review.md` | AI 用日志/telemetry/帧/overlay 离线复盘的流程 | 人类跑完、AI 接手分析 |
| `docs/official_test_matrix.md` | 官方赛道、测试入口、赛制清单 | 需要赛道/测试入口的完整清单 |
| `experiments/notes.md` | 按 R-id 倒序的实验叙事 | 想查某次 run 的细节，不必通读 |
| `experiments/runs.csv` | 真实 run 的结构化台账 | 想横向比较历次结果 |
| `experiments/figures/README.md` | 报告可视化归档规则（留什么图、怎么选、放哪） | 想沉淀整场轨迹图/感知标注帧等报告素材 |
| `experiments/cases/README.md` | 失败窗口归档规则（回归用，与 figures 区分） | 想保留可复现的失败窗口 |

要改控制行为：读 `controller/`，尤其是 `common.py`、`params.py`、`perception.py`、`estimator.py`、`policy.py`。

## 目录约定

| 路径 | 作用 |
|---|---|
| `controller/` | 手写控制器源码。只在这里改算法。 |
| `submissions/` | 由脚本生成的单文件提交版。不要手工改。 |
| `scripts/` | 构建、校验、日志分析、离线回放、可视化（`plot_run.py`、`analyze_perception_dump.py`）工具。 |
| `tests/` | 单元测试、脚本测试、提交文件静态检查。 |
| `docs/` | 测试、调试和官方 SDK 接入说明。 |
| `experiments/` | 真实 run 记录、机制分析、交接文档、失败窗口 case、报告可视化归档（`figures/`）。 |
| `baselines/` | 已确认值得保留的稳定策略快照。 |
| `.tmp/` | 临时工作区。可随时删除，不进 git。 |

核心流水线固定为：

```text
left_img/right_img
→ perception.extract_observation()
→ estimator.estimate_track()
→ policy.decide_control()
→ clamp_cmd()
→ steering/speed
```

模块间数据结构在 `controller/common.py`。改字段时必须同步调用方、构建脚本和测试。

## 常用命令

```bash
pytest -q

python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/build_submission.py --mode fastest --out submissions/fastest/team_controller.py
python scripts/build_submission.py --mode safe --out submissions/safe/team_controller.py

python scripts/validate_submission.py submissions/final/team_controller.py
python scripts/validate_submission.py submissions/fastest/team_controller.py
python scripts/validate_submission.py submissions/safe/team_controller.py

python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

Webots 实跑分两段：

- 人类实跑和肉眼观察：`docs/human_webots_testing.md`
- AI 离线复盘、逐帧取证和归档：`docs/ai_offline_review.md`

## 调试产物规则

整场录像和逐帧回看很重要，但它们是临时诊断材料，不是长期仓库资产。这里的“整场回看”是 AI 先看全局摘要，再从整场记录里挑关键窗口逐帧取证；不是要求人类或 AI 把完整录像逐帧看完。

- `.tmp/` 用来放 debug 构建、控制日志、整场相机帧 PNG、overlay、Webots 录像和临时 SDK 克隆。`scripts/webots_run.sh` 默认每轮保存相机帧（无损 PNG，整场约几百 MB），所以跑完后看任意时刻都不必重跑。
- 人类负责实跑和肉眼现象记录；AI 负责用日志、telemetry、帧和 overlay 解释机制。
- AI 分析时必须用关键窗口的逐帧画面或 overlay 支撑判断；不要只凭数字或猜测下结论。
- **最近一次 run 的 `.tmp/run` 产物保留到被下一次 run 覆盖**（`scripts/webots_run.sh` 自动轮换到 `.tmp/run.prev`）；清理前先确认 notes 里的"下一步"不依赖它。不要提交整场帧、整场录像、批量截图或临时 telemetry 复制件。
- 如果某个失败窗口以后还会反复用来回归，裁剪成 `experiments/cases/<R-id>_<slug>/`，只保留很小的窗口和少量关键 overlay。

## 实验记录

- `experiments/STATUS.md`：唯一活动交接文档，就地更新，不再新建 handoff 文件。
- `experiments/runs.csv`：真实 Webots/platform run 的结构化台账。`notes` 列只写一两句并以 `R0xx |` 开头，细节进 notes.md。
- `experiments/notes.md`：肉眼现象、数据摘要、结论、下一步，最新记录在最上面。
- `experiments/analysis_*.md`：有机制解释价值的长分析。
- `experiments/cases/`：少量关键失败窗口，不保存整场原始数据。

离线回放和脚本分析不单独建 R-id；只有真实 Webots/platform run 才写入 `runs.csv`。
