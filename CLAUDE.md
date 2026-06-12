# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) and other coding agents (such as Codex) when working with code in this repository.

## 项目定位

本地开发 AI Racer 控制器，最终交付物是单个可上传的 `team_controller.py`，必须提供：

```python
def control(left_img, right_img, timestamp):
    return steering, speed  # steering ∈ [-1,1], speed ∈ [0,1]
```

`controller/` 是模块化开发区，`submissions/` 是脚本生成的提交文件区，正常情况下不手工修改 `submissions/`。

## 常用命令

```bash
# 安装依赖
pip install -r requirements.txt

# 修改 controller/ 后重新构建
python scripts/build_submission.py --mode no_other_cars

# 生成准备上传的最终版本
python scripts/build_submission.py --mode no_other_cars --out submissions/final/team_controller.py

# 本地校验 + 测试
python scripts/validate_submission.py submissions/final/team_controller.py
pytest

# 运行单个测试文件或测试函数
pytest tests/test_contracts.py
pytest tests/test_estimator.py::test_centerline_straight_track_is_near_zero

# 官方 validator（不需要 Webots）
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml

# 官方 run_local 校验层（不启动 Webots）
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/final/team_controller.py" \
  --validate-only

# Webots 单车实跑（需要已安装 Webots.app）
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/final/team_controller.py" \
  --world basic --car-slot car_1
```

**控制器整体逻辑（一帧画面怎么变成舵角/油门）的详细说明见 [docs/technical_manual.md](docs/technical_manual.md)。** 它是面向交付的稳定逻辑说明，**不要每次改参数/策略就更新它**（尤其改动没跑通时）；调参过程写 `experiments/`，等策略结构稳定、人明确要求时再更新手册。

官方 SDK 和 Webots 安装见 [docs/official_testing.md](docs/official_testing.md)。AI 或人类跑 Webots 时读 [docs/human_webots_testing.md](docs/human_webots_testing.md)；AI 用日志、telemetry、帧和截图复盘时读 [docs/ai_offline_review.md](docs/ai_offline_review.md)。脚本入口和诊断工具速查见 [scripts/README.md](scripts/README.md)。

**新会话接手前先读 [experiments/STATUS.md](experiments/STATUS.md)**：它是唯一的活动交接文档（当前状态、铁律、未解问题、下一步），每轮工作结束时就地更新，不要另建 handoff 文件。实验目录怎么留档见 [experiments/README.md](experiments/README.md)；case 和 figure 的细则分别见 `experiments/cases/README.md`、`experiments/figures/README.md`。

**每个有意义的 Webots / 平台 run 分析完后，AI 默认要同步记账**：结构化结果写 `experiments/runs.csv`，叙事诊断写 `experiments/notes.md`。不需要用户单独提醒。误启动、脚本没真正开始、超短无信息、重复跑同一版本且没有新现象，可以不记，但要在回复里说清楚为什么不记。

## 工作约定（经验为主，不限制"改哪里"）

**想改哪里就改哪里、放手大改。** controller 任意模块（含 basic 分支）、参数、脚本、SDK 调试层都可自由改。没有"必须先获人工批准/关键验收"才能动手这回事，也没有"basic 不许碰"这种保护。大胆做结构性的改动——历史经验是：保守的微调往往没用。

**唯一硬约束（违反会让提交直接作废，不是自我设限）**：上传的 `submissions/final/team_controller.py` 必须通过 `validate_submission.py` 和官方 validator，且**不含调试 I/O**（`open/json/cv2.imwrite` 等）和**禁用模块**（见下"提交文件约束"）。调试构建只在本地 `.tmp/` 跑，永不上传。

**经验（帮判断好坏，不拦你动手）**：
- 驾驶质量以 Webots 实跑为准；离线数字会骗人——`lost` 率尤其不是质量指标。撞栏现在能靠 `contact_*.jsonl` 离线看（见 `docs/ai_offline_review.md`）。
- 走线/policy 改动最好跑一次 Webots 看真实效果再下结论。出于 token 考虑，默认流程是 **AI 改 → 人跑 → 人报完成 → AI 读日志**（见 `docs/human_webots_testing.md`）；这是证据闭环，不是审批门槛。合 main / 提交 final 由人触发即可。
- 清 `.tmp` 前确认 notes 的"下一步"不依赖其中帧/日志；依赖的窗口先裁进 `experiments/cases/`。

## 控制流水线

```
left_img, right_img
  → perception.extract_observation()   →  PerceptionObs
  → estimator.estimate_track()         →  TrackState
  → policy.decide_control()            →  ControlCmd
  → clamp_cmd()                        →  (steering, speed)
```

数据结构定义在 `controller/common.py`，字段名是模块间契约。**改字段时必须同步更新所有调用方、测试和文档。**

## 模块职责边界

| 模块 | 只能做 | 不能做 |
|---|---|---|
| `perception.py` | 图像处理，输出 `PerceptionObs` | 计算转向/速度 |
| `estimator.py` | 从 `PerceptionObs` 估计几何状态 | 接触原图，输出控制量 |
| `policy.py` | 计算转向和速度 | 处理原图 |
| `params.py` | 集中存放参数 | 运行算法逻辑 |
| `opponent.py` | 近处车身检测 | 道路分割或控制决策 |
| `team_controller_local.py` | 接线、异常兜底、最终限幅 | 算法实现 |

`opponent.py` 的 `detect_near_vehicle_obstacle` 只作为后续有其他车策略的感知工具保留；当前 `no_other_cars` 策略默认不启用它。

## 关键约定

**误差符号**：左负右正。图像坐标按 OpenCV：`x` 向右，`y` 向下。

**参数唯一源**：所有控制参数集中在 `params.py`，不在模块内硬编码调参值。当前实现的是 `no_other_cars` 策略；`with_other_cars` 只留命名入口，尚未实现。`fastest` / `safe` / `final` 只可能出现在旧输出目录、平台槽位或历史记录里，不再是策略名。

**场景感知**：`estimator.py` 会在连续红色环境帧后锁存 `red_environment = True`（写入 `TrackState`）。它现在是感知/诊断特征，不再用于切换 basic/complex 控制参数。单帧误检不会触发锁存；`reset_estimator_state()` 或时间戳回退会清空。

**提交文件约束**：`controller/` 代码最终会被合并进单文件提交，**禁止**使用以下模块：`os, sys, socket, subprocess, multiprocessing, threading, time, datetime, io, builtins, ctypes, shutil, tempfile, requests, urllib, http, pickle, importlib`，以及 `open, eval, exec, compile, globals, locals`。`scripts/` 和 `tests/` 可以使用标准库。

## 构建机制

`scripts/build_submission.py` 按固定顺序拼接 `controller/` 各模块（`common → params → opponent → perception → estimator → policy → team_controller_local`），删除本地 import，输出自包含的单文件。`--mode no_other_cars` 是当前主入口；`with_other_cars` 入口已留但会显式报未实现。需要写入旧目录时，用 `--mode no_other_cars --out submissions/fastest/team_controller.py` 这类显式输出路径。

## Baseline 与实验记录

`baselines/` 保存已实跑确认的策略快照（单文件 + 参数摘要 + 证据说明），供对比和回退。

平台或 Webots 测试后，结构化结果写入 `experiments/runs.csv`（`date,commit,mode,track,laps_completed,best_lap,total_time,collisions_major,finish_reason,notes`），较长观察写入 `experiments/notes.md`。AI 自跑和人类实跑都按 `docs/human_webots_testing.md` 留下可复盘产物；AI 机制分析按 `docs/ai_offline_review.md` 取证。判断一个 run 是否“有意义”的标准见 `experiments/notes.md` 顶部记录规范。

可视化产物分两类归档：复现某个 bug 的最小失败窗口进 `experiments/cases/`；要放进最终报告或回查的精选图（整场轨迹/速度图用 `scripts/plot_run.py`，关键感知标注帧用 `scripts/analyze_perception_dump.py --at`）进 `experiments/figures/`。规则见两个目录各自的 `README.md`。
