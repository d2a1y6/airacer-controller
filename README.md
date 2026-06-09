# AI Racer Controller

本仓库用于协作开发 AI Racer 控制器。最终交付物是一个可上传到平台的单文件 `team_controller.py`，文件中必须提供：

```python
def control(left_img, right_img, timestamp):
    return steering, speed
```

运行时，平台只向我们提供左右摄像头图像和当前仿真时间；我们的代码每帧返回转向比例 `steering` 和速度比例 `speed`。仓库不复制平台源码，不依赖平台内部实现，只围绕控制器算法、构建、校验和测试组织工作。

当前保留两套策略：

- `fastest`：单车最快完赛，优先追求速度和单圈时间。
- `safe`：多车或碰撞稳健，优先降低失控、停滞和严重碰撞风险。

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
│   ├── steering.py
│   ├── strategy.py
│   └── params.py
├── scripts/
│   ├── build_submission.py
│   └── validate_submission.py
├── submissions/
│   ├── fastest/team_controller.py
│   ├── safe/team_controller.py
│   └── final/team_controller.py
├── tests/
│   ├── test_interface.py
│   ├── test_contracts.py
│   ├── test_output_range.py
│   └── test_submission_static.py
├── experiments/
│   ├── runs.csv
│   └── notes.md
```

结构保持浅层。核心算法只放在 `controller/`；自动化脚本只放在 `scripts/`；生成后的提交文件只放在 `submissions/`。

## 控制流水线

本地开发版控制器采用固定流水线：

```text
left_img, right_img
→ perception.extract_observation()
→ estimator.estimate_track()
→ strategy.select_mode()
→ steering.compute_steering()
→ strategy.compute_speed()
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
class ControlMode:
    name: str
    risk: float

@dataclass
class SteeringCmd:
    value: float
    confidence: float

@dataclass
class SpeedCmd:
    value: float
    confidence: float
```

接口一旦确定，各模块内部可以独立迭代；确需改字段时，必须同步修改所有调用方、测试和构建脚本。

## 模块职责

| 模块 | 输入 | 输出 | 职责 |
|---|---|---|---|
| `perception.py` | 左右摄像头图像 | `PerceptionObs` | 识别赛道边界、可行驶区域、中心点和感知置信度 |
| `estimator.py` | `PerceptionObs`, `timestamp` | `TrackState` | 拟合中心线，估计偏移、朝向误差、曲率、前瞻误差，处理丢线和平滑 |
| `steering.py` | `TrackState`, `ControlMode` | `SteeringCmd` | 根据偏移、朝向和弯道趋势计算转向，限制抖动和转向变化率 |
| `strategy.py` | `TrackState`, `SteeringCmd` | `ControlMode`, `SpeedCmd` | 选择驾驶模式，按 `fastest` / `safe` 参数计算速度 |
| `team_controller_local.py`、`scripts/`、`tests/`、`experiments/` | 全部模块 | 提交文件与测试结果 | 接线、构建、校验、实验记录、最终版本管理 |

## 快速开始

安装依赖：

```bash
pip install -r requirements.txt
```

生成两个策略的提交文件：

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

如果实际考核只要求单车完赛，优先使用 `fastest`。如果需要按多车/碰撞规则运行，优先使用 `safe` 或以 `safe` 为基线调参。

## 开发流程

1. 在 `controller/` 内修改模块化代码。
2. 保持模块接口不变，尤其是 `common.py` 中的数据结构字段。
3. 用脚本生成 `submissions/fastest/team_controller.py` 和 `submissions/safe/team_controller.py`。
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

## 实验记录

平台或本地测试完成后，在 `experiments/runs.csv` 记录结构化结果：

```csv
date,commit,mode,track,laps_completed,best_lap,total_time,collisions_major,finish_reason,notes
```

较长的观察写入 `experiments/notes.md`，例如弯道失控、丢线位置、速度参数变化和下一步调整。

## 文档

- `TASK.md`：参赛任务、平台接口规则、算法目标和提交限制。
- `AGENTS.md`：给 Codex / AI agent 的执行规则。
