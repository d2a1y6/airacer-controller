# Agent Instructions

## 项目定位

本仓库只开发 AI Racer 控制器。不要复制平台源码，不依赖平台内部实现，也不要把平台 SDK 或 Webots 工程混进来。

最终交付物是单个 `team_controller.py`，其中必须提供：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

`controller/` 是本地模块化开发区；`submissions/` 是脚本生成的提交文件区。正常情况下不要手工修改 `submissions/`。

## 提交安全边界

`controller/` 下的代码会被合并进最终提交文件，因此必须遵守平台限制：

- 不读写文件。
- 不访问系统环境。
- 不联网。
- 不启动进程、线程或多进程。
- 不动态执行代码。

最终提交文件中不要出现这些典型禁止项：

```text
os, sys, socket, subprocess, multiprocessing, threading,
time, datetime, io, builtins, ctypes, shutil, tempfile,
requests, urllib, http, pickle, importlib,
open, eval, exec, compile, globals, locals
```

`scripts/` 和 `tests/` 可以使用本地开发所需的标准库，但不要把这些能力带进 `controller/` 或生成后的 `team_controller.py`。

## 当前结构

```text
controller/
  common.py                 公共 dataclass 和 clamp
  perception.py             图像感知，输出 PerceptionObs
  estimator.py              赛道几何估计，输出 TrackState
  strategy.py               模式选择和速度策略
  steering.py               转向控制
  params.py                 fastest / safe 参数
  team_controller_local.py  本地 control() 入口
scripts/
  build_submission.py       生成单文件提交版本
  validate_submission.py    本地轻量校验
submissions/
  fastest/ safe/ final/     生成后的 team_controller.py
tests/                      接口、契约、范围和静态检查
experiments/                测试记录和观察
docs/official_testing.md    官方 SDK / Webots 测试接入说明
```

保持结构浅层。没有明确需要时，不新增 `src/`、`data/`、`config/`、深层实验目录或重型框架。

## 控制流水线

本地入口 `controller/team_controller_local.py` 应保持这个顺序：

```text
left_img, right_img
-> extract_observation()
-> estimate_track()
-> select_mode()
-> compute_steering()
-> compute_speed()
-> steering, speed
```

公共数据结构定义在 `controller/common.py`。字段名是模块间契约，改字段时必须同步更新调用方、测试、README 和 TASK。

误差符号统一为左负右正。图像坐标按 OpenCV 约定：`x` 向右，`y` 向下。模块失败时返回低置信度结果，不要让异常一路传到平台。

## 模块边界

- `perception.py` 只处理图像，不计算最终转向和速度。
- `estimator.py` 只从感知结果估计几何状态，不接触原图，不计算最终控制量。
- `steering.py` 只计算转向，不计算速度。
- `strategy.py` 负责驾驶模式和速度，不处理图像，不改转向公式。
- `params.py` 集中放参数，不把调参值散落到各模块。
- `team_controller_local.py` 只做接线、异常兜底和最终限幅。

## 开发流程

修改控制逻辑时：

```bash
python scripts/build_submission.py --mode fastest
python scripts/build_submission.py --mode safe
python scripts/validate_submission.py submissions/fastest/team_controller.py
python scripts/validate_submission.py submissions/safe/team_controller.py
pytest
```

准备上传平台时：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/validate_submission.py submissions/final/team_controller.py
pytest
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

如果最终选择 `safe` 作为上传版本，把上面的 `--mode fastest` 改为 `--mode safe`。

官方仓库位于 `/Users/day/Desktop/Github/pkudsa.airacer`。不要把官方平台源码复制进本仓库；只通过相邻目录调用 `sdk/validate_controller.py`、`sdk/run_local.py` 和 Webots 资产。官方 validator 不需要 Webots；真正打开赛道可视化实跑时，macOS 必须先手动安装 Webots.app，并确保 SDK 能找到它。

## 代码和文档习惯

- 新增或大改 Python 文件时，保留简洁中文模块 docstring；公开函数和非平凡函数写清楚参数、返回和核心逻辑。
- 注释只解释设计意图、假设和复杂逻辑，不写显而易见的逐行说明。
- 不保留调试打印。脚本输出只保留构建、校验和结果摘要。
- 文档用自然、简洁的中文。少写模板句，少堆抽象词。
- 大文件、视频、大量截图、长日志和本地结果不要提交。

## 实验记录

平台测试或重要本地测试后，结构化结果写入 `experiments/runs.csv`，较长观察写入 `experiments/notes.md`。

记录至少说明：模式、赛道、完成圈数、最快单圈、总时间、严重碰撞、结束原因和主要改动。
