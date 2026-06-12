# 脚本工具索引

这些脚本分两类：正式构建/校验工具，以及本地诊断工具。`controller/` 里的算法最终会被 `build_submission.py` 合并成单文件；`.tmp/` 里的调试产物不进 git。

## 构建与校验

| 脚本 | 输入 | 输出 | 用途 |
|---|---|---|---|
| `build_submission.py` | `controller/` 源码、`--mode fastest|safe` | 单文件 `team_controller.py` | 生成上传版或调试版控制器 |
| `validate_submission.py` | 单文件 controller | 终端校验结果 | 本仓库接口、静态规则、mock 输出检查 |

常用命令：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/validate_submission.py submissions/final/team_controller.py
pytest -q
```

调试构建可以加控制日志和相机帧输出，但不能上传：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_complex.jsonl \
  --dump-frames .tmp/run/frames_complex \
  --dump-frame-stride 10 \
  --out .tmp/run/team_controller_debug.py
```

## 一键 Webots 运行

| 脚本 | 用途 | 关键点 |
|---|---|---|
| `webots_run.sh` | 从头跑 `basic` 或 `complex`，自动构建 debug controller、清理孤儿进程、保存日志和帧 | 默认每 10 帧保存一对 PNG 到 `.tmp/run/frames_<world>/` |
| `webots_jump_run.sh` | 从已有 telemetry 的某个 `x/y/heading` 近似启动，观察当前代码从该姿态会怎么开 | 只恢复位置和朝向，不是严格续跑 |
| `make_teleport_world.py` | 给 jump run 生成临时 Webots world | 通常由 `webots_jump_run.sh` 调用 |

常用命令：

```bash
bash scripts/webots_run.sh complex
bash scripts/webots_run.sh complex --frames 1
bash scripts/webots_run.sh complex --frame-window 226 230
bash scripts/webots_run.sh complex --no-frames

bash scripts/webots_jump_run.sh complex 226.5 --duration 6 \
  --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl
```

## 诊断一轮 run

| 脚本 | 输入 | 输出 | 回答什么问题 |
|---|---|---|---|
| `analyze_telemetry.py` | SDK `telemetry.jsonl` | 位置、速度、事件、近停摘要 | 车跑到哪、有没有事件/爬行/卡住 |
| `analyze_control_log.py` | `.tmp/run/control_*.jsonl` | mode、steering、speed、line_conf 等摘要 | 控制器内部为什么这样打轮/减速 |
| `plot_run.py` | telemetry | `trajectory_speed.png` | 整场轨迹和速度长什么样 |
| `analyze_perception_dump.py` | 相机帧 + control log | 感知摘要、可选 overlay | 画面里看到了什么，白线/mask/边界是否正确 |
| `replay_offline.py` | 已保存相机帧 | 固定画面开环控制日志 | 同一批画面下，新代码的感知/策略字段怎么变 |

常用命令：

```bash
python scripts/analyze_telemetry.py --no-archive
python scripts/analyze_control_log.py .tmp/run/control_complex.jsonl

python scripts/plot_run.py \
  --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl \
  --out .tmp/run/trajectory_speed.png \
  --title "R0xx complex"

python scripts/analyze_perception_dump.py .tmp/run/frames_complex \
  --control-log .tmp/run/control_complex.jsonl \
  --overlay-dir .tmp/run/overlays \
  --at 226.56,228.48,229.44

python scripts/replay_offline.py .tmp/run/frames_complex \
  --out .tmp/run/replay_complex.jsonl
```

## 保存和清理

- 整场帧、整场 telemetry 复制件、批量 overlay 留在 `.tmp/`，不要进 git。
- 会反复回归的失败窗口裁到 `experiments/cases/`。
- 报告或长期回查要用的精选图进 `experiments/figures/`。
- 当前最好版本的单文件快照进 `baselines/`。

归档规则见 `experiments/README.md`、`experiments/cases/README.md`、`experiments/figures/README.md`。
