# AI Racer Controller

本仓库用于开发 AI Racer 控制器。最终交付物是一个可上传到平台的单文件 `team_controller.py`，文件中必须提供：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

运行时，平台提供左右摄像头图像和当前仿真时间；控制器每帧返回转向比例 `steering` 和速度比例 `speed`。仓库不复制平台源码，不依赖平台内部实现，只围绕控制器算法、构建、校验和测试组织工作。

当前只维护一套 `CONTROL` 参数。`fastest` / `safe` 生成目录和 `--mode` 参数保留为脚本兼容入口，实际都会读取同一套控制参数，方便先集中优化。

`submissions/final/team_controller.py` 是当前准备上传平台的版本，由脚本生成，不手工修改。

## 仓库结构

```text
airacer-controller/
├── README.md
├── TASK.md
├── AGENTS.md
├── requirements.txt
├── controller/
│   ├── team_controller_local.py
│   ├── common.py
│   ├── perception.py
│   ├── estimator.py
│   ├── policy.py
│   └── params.py
├── scripts/
│   ├── build_submission.py
│   └── validate_submission.py
├── submissions/
│   ├── fastest/team_controller.py
│   ├── safe/team_controller.py
│   └── final/team_controller.py
├── baselines/
│   └── webots_basic_physical_finish_2026-06-10/
│       ├── README.md
│       ├── params.json
│       └── team_controller.py
├── tests/
│   ├── test_interface.py
│   ├── test_contracts.py
│   ├── test_output_range.py
│   └── test_submission_static.py
├── experiments/
│   ├── runs.csv
│   └── notes.md
└── docs/
    └── official_testing.md
```

结构保持浅层。核心算法只放在 `controller/`；自动化脚本只放在 `scripts/`；生成后的提交文件只放在 `submissions/`。`baselines/` 只保存已经实跑确认过的策略快照，便于以后对照、回放或回退。

## 控制流水线

本地开发版控制器采用固定流水线：

```text
left_img, right_img
→ perception.extract_observation()
→ estimator.estimate_track()
→ policy.decide_control()
→ steering, speed
```

对应的核心数据结构放在 `controller/common.py`：

```python
@dataclass
class PerceptionObs:
    center_points: np.ndarray
    left_edge_points: np.ndarray
    right_edge_points: np.ndarray
    road_width_est: float
    confidence: float
    debug_flags: int = 0

@dataclass
class TrackState:
    lateral_error: float
    heading_error: float
    curvature: float
    lookahead_error: float
    confidence: float
    lost: bool

@dataclass
class ControlCmd:
    steering: float
    speed: float
```

接口一旦确定，各模块内部可以独立迭代；确需改字段时，必须同步修改所有调用方、测试和构建脚本。

## 模块职责

| 模块 | 输入 | 输出 | 职责 |
|---|---|---|---|
| `perception.py` | 左右摄像头图像 | `PerceptionObs` | 识别赛道边界、可行驶区域、中心点和感知置信度 |
| `estimator.py` | `PerceptionObs`, `timestamp` | `TrackState` | 拟合中心线，估计偏移、朝向误差、曲率、前瞻误差，处理丢线和平滑 |
| `policy.py` | `TrackState`, `timestamp`, profile | `ControlCmd` | 统一计算转向和速度，处理丢线、低置信度和急弯降速 |
| `params.py` | profile 名称 | 参数字典 | 集中保存当前唯一维护的 `CONTROL` 参数 |
| `team_controller_local.py` | 左右摄像头图像、时间戳 | `(steering, speed)` | 本地 `control()` 入口，只做接线、异常兜底和最终限幅 |
| `scripts/`、`tests/`、`experiments/` | 控制器源码 | 提交文件与测试结果 | 构建、校验、实验记录、最终版本管理 |
| `baselines/` | 已确认提交文件、参数摘要 | 可回放策略快照 | 保存跑通版本的单文件策略、参数和证据说明 |

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

生成兼容目录下的提交文件：

```bash
python scripts/build_submission.py --mode fastest
python scripts/build_submission.py --mode safe
```

生成当前准备上传的最终版本：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
```

校验提交文件：

```bash
python scripts/validate_submission.py submissions/final/team_controller.py
pytest
```

接入官方 SDK 校验：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

官方校验只需要 Python 环境。要用官方赛道做可视化实跑，macOS 上还需要先手动安装 Webots 桌面 app；SDK 会启动 Webots 图形界面。启动前先看 [docs/official_testing.md](docs/official_testing.md)。

当前 `fastest` 和 `safe` 使用同一套参数。平台测试和调参时优先看 `submissions/final/team_controller.py`。

## 开发流程

1. 在 `controller/` 内修改模块化代码。
2. 保持模块接口不变，尤其是 `common.py` 中的数据结构字段。
3. 用脚本生成 `submissions/fastest/team_controller.py` 和 `submissions/safe/team_controller.py`，两者当前使用同一套 `CONTROL` 参数。
4. 运行本地校验和测试。
5. 平台测试后，将结果写入 `experiments/runs.csv` 和 `experiments/notes.md`。
6. 确认最终策略后，生成 `submissions/final/team_controller.py`。

常用命令：

```bash
python scripts/build_submission.py --mode fastest
python scripts/build_submission.py --mode safe
python scripts/validate_submission.py submissions/fastest/team_controller.py
python scripts/validate_submission.py submissions/safe/team_controller.py
pytest
```

## 提交文件规则

平台最终只接收单个 `team_controller.py`。因此 `submissions/` 下的文件必须满足：

- 包含 `control(left_img, right_img, timestamp)`。
- 不依赖本仓库内的其他 Python 文件。
- 不使用相对 import。
- 不读写文件，不联网，不启动进程或线程。
- 返回值始终是两个数字，范围分别为 `[-1, 1]` 和 `[0, 1]`。

正常情况下不要手工修改 `submissions/`。需要修改控制逻辑时，先改 `controller/`，再运行 `scripts/build_submission.py`。

## Baseline 快照

跑通后的策略可以保存，但要分清两层：

- git commit 保存完整源码、测试、实验记录和生成脚本，是以后继续开发和回退的主依据。
- `baselines/` 保存可直接回放的策略快照，包括生成后的 `team_controller.py`、当时的参数摘要和实跑证据。

当前 baseline 位于 `baselines/webots_basic_physical_finish_2026-06-10/`。里面的 `team_controller.py` 来自同一时刻的 `submissions/final/team_controller.py`，不是手工改出的分支版本。

## 实验记录

平台或本地测试完成后，在 `experiments/runs.csv` 记录结构化结果：

```csv
date,commit,mode,track,laps_completed,best_lap,total_time,collisions_major,finish_reason,notes
```

较长的观察写入 `experiments/notes.md`，例如弯道失控、丢线位置、速度参数变化和下一步调整。

## 文档

- `TASK.md`：参赛任务、平台接口规则、算法目标和提交限制。
- `AGENTS.md`：给 Codex / AI agent 的执行规则。
- `docs/official_testing.md`：官方 SDK、validator 和 Webots 本地测试接入方式（首次安装与官方校验）。
- `docs/manual_testing.md`：日常调参的带日志迭代复测流程（构建调试单文件、防遥测交错、读日志、记账）。
- `docs/debug_tools.md`：**全部自动化诊断工具的权威清单**——数据产物、脚本用法、AI 自主复盘录像的方法与铁律（自主作业前先读）。
- `docs/offline_replay.md`：离线存帧与开环回放（只用于感知/估计诊断，不评估圈速）。
