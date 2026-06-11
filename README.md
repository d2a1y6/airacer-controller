# AI Racer Controller

本仓库用于开发 AI Racer 控制器。最终交付物是单文件 `team_controller.py`，平台每帧传入左右摄像头图像和时间戳，控制器返回：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

`steering` 范围是 `[-1, 1]`，`speed` 范围是 `[0, 1]`。当前 `fastest`、`safe`、`final` 生成文件使用同一套 `CONTROL` 参数。

## 先读什么

- 新接手先读：`CLAUDE.md`、`docs/debug_tools.md`、`experiments/notes.md` 最新记录。
- 要改控制行为：读 `controller/`，尤其是 `common.py`、`params.py`、`perception.py`、`estimator.py`、`policy.py`。
- 要跑 Webots 或看录像：读 `docs/manual_testing.md` 和 `docs/debug_tools.md`。
- 要理解当前失败点：读 `experiments/notes.md` 的最新 R-id 和 `experiments/handoff_2026-06-11.md`。

## 目录约定

| 路径 | 作用 |
|---|---|
| `controller/` | 手写控制器源码。只在这里改算法。 |
| `submissions/` | 由脚本生成的单文件提交版。不要手工改。 |
| `scripts/` | 构建、校验、日志分析、离线回放工具。 |
| `tests/` | 单元测试、脚本测试、提交文件静态检查。 |
| `docs/` | 测试、调试和官方 SDK 接入说明。 |
| `experiments/` | 真实 run 记录、机制分析、交接文档、小型裁剪 case。 |
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

Webots 实跑和 debug 构建流程见 `docs/manual_testing.md`。

## 调试产物规则

整场录像和逐帧回看很重要，但它们是临时诊断材料，不是长期仓库资产。这里的“整场回看”不是逐帧看完整场，而是先看全局摘要，再从整场记录里挑关键窗口逐帧取证。

- `.tmp/` 用来放 debug 构建、控制日志、整场 `.npy` 帧、overlay、Webots 录像和临时 SDK 克隆。
- 每次实跑后必须看整场摘要，并用关键窗口的逐帧 overlay 支撑分析；不要只凭数字或猜测下结论。
- 看完后清理 `.tmp/`。不要提交整场帧、整场录像、批量截图或临时 telemetry 复制件。
- 如果某个失败窗口以后还会反复用来回归，裁剪成 `experiments/cases/<R-id>_<slug>/`，只保留很小的窗口和少量关键 overlay。

## 实验记录

- `experiments/runs.csv`：真实 Webots/platform run 的结构化台账。
- `experiments/notes.md`：肉眼现象、数据摘要、结论、下一步，最新记录在最上面。
- `experiments/analysis_*.md`：有机制解释价值的长分析。
- `experiments/cases/`：少量关键失败窗口，不保存整场原始数据。

离线回放和脚本分析不单独建 R-id；只有真实 Webots/platform run 才写入 `runs.csv`。
