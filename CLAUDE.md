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
python scripts/build_submission.py --mode fastest
python scripts/build_submission.py --mode safe

# 生成准备上传的最终版本
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py

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

完整 Webots 测试流程见 [docs/official_testing.md](docs/official_testing.md)。

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

`opponent.py` 的 `detect_near_vehicle_obstacle` 由 `OPPONENT_PROFILE["enable_opponent_avoidance"]` 控制；当前为开启，用于 basic/complex 近处静态车避让。

## 关键约定

**误差符号**：左负右正。图像坐标按 OpenCV：`x` 向右，`y` 向下。

**参数唯一源**：所有控制参数集中在 `params.py`，不在模块内硬编码调参值。`fastest` 和 `safe` 当前读取同一套 `CONTROL` 参数。

**场景感知**：`estimator.py` 会在连续红色环境帧后锁存 `red_environment = True`（写入 `TrackState`）。`policy.py` 和 `perception.py` 用该标志在 basic/complex 赛道间切换策略分支。单帧误检不会触发锁存；`reset_estimator_state()` 或时间戳回退会清空。

**提交文件约束**：`controller/` 代码最终会被合并进单文件提交，**禁止**使用以下模块：`os, sys, socket, subprocess, multiprocessing, threading, time, datetime, io, builtins, ctypes, shutil, tempfile, requests, urllib, http, pickle, importlib`，以及 `open, eval, exec, compile, globals, locals`。`scripts/` 和 `tests/` 可以使用标准库。

## 构建机制

`scripts/build_submission.py` 按固定顺序拼接 `controller/` 各模块（`common → params → opponent → perception → estimator → policy → team_controller_local`），删除本地 import，将 `PROFILE` 固定为 `--mode` 参数值，输出自包含的单文件。

## Baseline 与实验记录

`baselines/` 保存已实跑确认的策略快照（单文件 + 参数摘要 + 证据说明），供对比和回退。

平台或 Webots 测试后，结构化结果写入 `experiments/runs.csv`（`date,commit,mode,track,laps_completed,best_lap,total_time,collisions_major,finish_reason,notes`），较长观察写入 `experiments/notes.md`。
