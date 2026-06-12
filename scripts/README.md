# 脚本工具索引

这些脚本分两类：正式构建/校验工具，以及本地诊断工具。`controller/` 里的算法最终会被 `build_submission.py` 合并成单文件；`.tmp/` 里的调试产物不进 git。

## 构建与校验

| 脚本 | 输入 | 输出 | 用途 |
|---|---|---|---|
| `build_submission.py` | `controller/` 源码、`--mode fastest|safe` | 单文件 `team_controller.py` | 生成上传版或调试版控制器；`--mode` 只决定默认输出路径，策略内容相同 |
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
| `webots_run.sh` | 从头跑 `basic` 或 `complex`，自动构建 debug controller、清理孤儿进程、保存日志、帧和**撞栏接触日志** | 默认每 10 帧保存一对 PNG（`--no-frames` 关）；默认开撞栏接触日志 → `.tmp/run/contact_<world>.jsonl`（`--no-contact` 关）；新 run 开始前会把旧 `.tmp/run` 和旧 SDK telemetry 移到 `.tmp/run.archive/`，滚动保留最近 10 个 |
| `webots_jump_run.sh` | 从已有 telemetry 的某个 `x/y/heading` 近似启动，观察当前代码从该姿态会怎么开 | 只恢复位置和朝向，不是严格续跑；新 jump run 开始前会把旧 `.tmp/jump_run` 和旧 SDK telemetry 移到 `.tmp/jump_run.archive/`，滚动保留最近 10 个 |
| `make_teleport_world.py` | 给 jump run 生成临时 Webots world | 通常由 `webots_jump_run.sh` 调用 |
| `webots_multicar_run.sh` | 双车 Webots 测试（多车极端场景） | 构建两车 debug 控制器并启动；默认 car_1=fastest, car_2=safe；产物在 `.tmp/multicar/`；极端场景说明见 `docs/multicar_extreme_tests.md` |

常用命令：

```bash
bash scripts/webots_run.sh complex
bash scripts/webots_run.sh complex --frames 1
bash scripts/webots_run.sh complex --frame-window 226 230
bash scripts/webots_run.sh complex --no-frames

bash scripts/webots_jump_run.sh complex 226.5 --duration 6 \
  --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl

bash scripts/webots_multicar_run.sh basic
bash scripts/webots_multicar_run.sh complex --no-frames
```

## 诊断一轮 run

| 脚本 | 输入 | 输出 | 回答什么问题 |
|---|---|---|---|
| `analyze_telemetry.py` | SDK `telemetry.jsonl` | 位置、速度、事件、近停摘要 | 车跑到哪、有没有事件/爬行/卡住 |
| `analyze_control_log.py` | `.tmp/run/control_*.jsonl` | mode、steering、speed、line_conf 等摘要 | 控制器内部为什么这样打轮/减速 |
| `analyze_contact_log.py` | `.tmp/run/contact_*.jsonl` | 撞栏 episode（时间、位置、点数、高度） | **撞没撞栏、在哪、多重**（峰值点数≥3 且 zmax>0.6 = 真撞栏） |
| `plot_run.py` | telemetry，可选 contact log | `trajectory_speed.png` | 整场轨迹、速度、事件和撞栏位置长什么样 |
| `analyze_perception_dump.py` | 相机帧 + control log | 感知摘要、可选 overlay | 画面里看到了什么，白线/mask/边界是否正确 |
| `replay_offline.py` | 已保存相机帧 | 固定画面开环控制日志 | 同一批画面下，新代码的感知/策略字段怎么变 |

常用命令：

```bash
python scripts/analyze_telemetry.py --no-archive
python scripts/analyze_control_log.py .tmp/run/control_complex.jsonl

python scripts/plot_run.py \
  --telemetry /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/telemetry.jsonl \
  --contact-log .tmp/run/contact_complex.jsonl \
  --out .tmp/run/trajectory_speed.png \
  --title "R0xx complex"

python scripts/analyze_perception_dump.py .tmp/run/frames_complex \
  --control-log .tmp/run/control_complex.jsonl \
  --overlay-dir .tmp/run/overlays \
  --at 226.56,228.48,229.44

python scripts/replay_offline.py .tmp/run/frames_complex \
  --out .tmp/run/replay_complex.jsonl
```

`plot_run.py --contact-log` 会把接触日志画到同一张总览图上：轨迹图用深红 X 标碰栏位置，
速度图用深红时间窗标接触时段。接触先按时间 gap 0.3s 聚成 episode，再把世界坐标距离
不超过 4.0 的 episode 合并成同一条标注；这个距离大致表示同一个弯角或同一段栏杆上的重复擦碰。

## 保存和清理

- 整场帧、整场 telemetry 复制件、批量 overlay 留在 `.tmp/`，不要进 git。`webots_run.sh` / `webots_jump_run.sh` 会把旧产物移到 `.tmp/run.archive/` 或 `.tmp/jump_run.archive/`，并滚动保留最近 10 个归档。
- 会反复回归的失败窗口裁到 `experiments/cases/`。
- 报告或长期回查要用的精选图进 `experiments/figures/`。
- 当前最好版本的单文件快照进 `baselines/`。

归档规则见 `experiments/README.md`、`experiments/cases/README.md`、`experiments/figures/README.md`。

碰撞信号不要混用：telemetry `collision` 主要是车车碰撞；Webots GUI console 中如果由人眼看到类似
`WARNING: Contact joints between materials 'default' and 'default' will only be created for the 10 deepest contact points instead of all the 12 contact points.`
的提示，要按栏杆/静态几何接触记录。但当前 `.tmp/run/webots_console/*.log` 和 `.tmp/run/webots_launch.log` 通常读不到这类 GUI console 文本，AI 自动复盘不能依赖它；优先看 `.tmp/run/contact_*.jsonl`，再结合画面、轨迹、速度和控制日志判断。
