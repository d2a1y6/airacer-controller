# 官方测试和赛道清单

本文基于本机官方仓库 `/Users/day/Desktop/Github/pkudsa.airacer`，日期为 2026-06-10。这里的官方，指该仓库当前提供的 SDK、Webots 资产、后端接口文档和赛事规则。

结论先写清楚：官方 SDK 登记了 3 个 Webots world，其中 `basic` 和 `complex` 是当前应重点测试的赛道；`airacer` 是旧版演示赛道。各赛道的实跑进度（跑通/超时/未跑）以 `experiments/STATUS.md` 为准，本文不重复维护。

## 1. 官方登记的赛道

数据源是官方 `sdk/worlds.py`，也可以用下面命令查看：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --list-worlds
```

| 短名 | 文件 | 定位 | 车位 |
|---|---|---|---|
| `basic` | `sdk/webots/worlds/track_basic.wbt` | 默认赛道。两条直道 + 两段大弧弯，适合初次调参和完赛验证。 | `car_1` 到 `car_6` |
| `complex` | `sdk/webots/worlds/track_complex.wbt` | 进阶赛道。复合弯、发卡弯、S 弯，用来检验循线鲁棒性。 | `car_1` 到 `car_6` |
| `airacer` | `sdk/webots/worlds/airacer.wbt` | 旧版 demo 赛道，使用手写 Robot 节点，不是当前 Car 系列 PROTO 布局。 | `car_1` 到 `car_4` |

默认赛道是 `basic`。`run_local.py --world` 支持短名、`.wbt` 文件名，也支持完整路径。完整路径可用于自定义 world，但不属于官方 catalog，SDK 无法做车位校验。

`basic` 和 `complex` 的 6 个车位车型一致：

| 车位 | 车型 | 昵称 / 颜色 |
|---|---|---|
| `car_1` | `CarPhoenix` | 凤凰 / 烈焰红 |
| `car_2` | `CarThunder` | 雷霆 / 电光蓝 |
| `car_3` | `CarViper` | 毒蛇 / 毒蛇绿 |
| `car_4` | `CarNova` | 新星 / 新星黄 |
| `car_5` | `CarFrost` | 冰霜 / 冰霜白 |
| `car_6` | `CarShadow` | 暗影 / 暗夜黑 |

## 2. 本地可直接跑的官方测试

这些测试不需要平台账号，只需要本地官方 SDK。Webots 实跑还需要安装 Webots.app。

| 测试 | 命令 | 是否跑 Webots | 作用 |
|---|---|---:|---|
| 官方 validator | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py --code-path submissions/final/team_controller.py --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml` | 否 | 检查语法、文件大小、禁用 import、禁用内置、`control()` 接口、mock 调用耗时和返回值。 |
| `run_local --validate-only` | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --code-path submissions/final/team_controller.py --validate-only` | 否 | 走 `run_local.py` 的本地入口，只做校验，不启动仿真。适合提交前快速确认。 |
| 单车 `basic` | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --code-path submissions/final/team_controller.py --world basic --car-slot car_1 --fast --minimize` | 是 | 默认赛道实跑。用于确认能否基础完赛。 |
| 单车 `complex` | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --code-path submissions/final/team_controller.py --world complex --car-slot car_1 --fast --minimize` | 是 | 复杂赛道实跑。用于验证策略是否只过拟合 `basic`。 |
| 单车 `airacer` | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --code-path submissions/final/team_controller.py --world airacer --car-slot car_1 --fast --minimize` | 是 | 旧 demo world。可作为兼容性观察，不建议作为主指标。 |
| 多车本地测试 | `python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --world basic --car "$PWD/submissions/final/team_controller.py:car_1:ours" --car "$PWD/submissions/final/team_controller.py:car_2:copy"` | 是 | 本地观察多车启动、配置和基本交互。不能完全代表线上碰撞惩罚和赛制。 |

`run_local.py` 还支持：

- `--skip-validate`：跳过 validator，直接生成配置并启动 Webots。
- `--batch`：无弹窗批量模式。
- `--webots /path/to/webots`：手动指定 Webots 可执行文件。
- `--config-out path`：指定生成的 `race_config.json`。

## 3. 官方 SDK 自带 pytest

这些是官方 SDK 自测，不是对我们控制器的赛道成绩测试。它们用于确认官方工具本身是否一致。

当前本地收集到 63 个测试：

| 文件 | 覆盖内容 |
|---|---|
| `sdk/tests/test_validator.py` | validator 规则、语法错误、禁用 import、禁用内置、接口和报告结构。 |
| `sdk/tests/test_cli.py` | `validate_controller.py` 的 CLI 退出码、JSON 输出、官方示例控制器通过情况。 |
| `sdk/tests/test_consistency.py` | `rules.yaml`、`car_sandbox.py`、Webots `sandbox_runner.py` 的黑白名单一致性。 |
| `sdk/tests/test_multi_car.py` | 多车配置生成、slot 冲突、批量校验、单车兼容入口。 |
| `sdk/tests/test_worlds.py` | `sdk/worlds.py` 与 `.wbt` 文件中的车位和 PROTO 是否一致。 |

查看测试清单：

```bash
pytest --collect-only -q /Users/day/Desktop/Github/pkudsa.airacer/sdk/tests
```

运行官方 SDK 自测：

```bash
pytest /Users/day/Desktop/Github/pkudsa.airacer/sdk/tests
```

## 4. 线上平台可见的测试入口

这些需要平台后端、账号和队伍配置。我们本地不能只靠 SDK 复现完整线上环境。

| 测试入口 | 接口 | 说明 |
|---|---|---|
| 提交校验 | `POST /api/submit` | 上传某个 slot 的代码。后端会做密码验证、Base64 解码、调用 `sdk/validate_controller.py`，通过后写入提交目录和数据库。 |
| 激活版本 | `POST /api/activate` | 切换当前参赛 slot。不是仿真测试，但决定正式比赛用哪份代码。 |
| 单车测试队列 | `POST /api/test-request` | 为指定 slot 申请单车测试。队列由后端 worker 消费；赛程正在运行时会拒绝新测试。 |
| 测试状态 | `GET /api/test-status/{team_id}` | 查询三槽位状态和最近测试报告。 |
| 用户自建测试赛 | `POST /api/races` | 2 到 4 队测试赛，支持指定 `world` 和 `total_laps`。官方示例里用 `world: complex`、`total_laps: 3`。 |
| 比赛查询 | `GET /api/races/{race_id}` / `GET /api/races?team_id=...` | 查询单场测试赛或历史记录。 |
| 录像和遥测 | `GET /api/recordings/...` | 查看 `metadata.json` 和 `telemetry.jsonl`，用于复盘位置、碰撞和进度。 |

线上测试比本地更接近正式环境，因为它包含后端队列、SimNode、Linux 沙箱、记录归档和平台判定。但本地 SDK 文档也说明：本地工具不能保证本地能跑就等于线上成绩稳定。

## 5. 正式赛制阶段

先说赛道：当前公开代码里，正式场次表和比赛计划表的 `world_key` 默认值都是 `complex`，管理员创建正式场次的代码路径也直接写入 `world_key="complex"`。提交接口允许的 world 只有 `basic` 和 `complex`，不包含 `airacer`。另外，SimNode 接口文档说明 Webots world 由 SimNode 配置里的 `WEBOTS_WORLD` 决定，当前版本不支持通过 API 动态切换。

所以按这份官方仓库判断：正式比赛主要应按 `complex` 准备；`basic` 是本地默认和基础验证赛道；`airacer` 不应当作正式提交目标。若比赛当天管理员改了 SimNode 配置，最终赛道以现场配置为准。

赛事规则文档里列出的正式阶段如下。每场最多 4 辆车。

| 阶段 | 圈数 | 作用 |
|---|---:|---|
| `placement` 排位赛 | 2 | 取最快单圈作为分组种子。 |
| `group_stage` 小组赛 | 3 | 小组晋级。 |
| `semi` 半决赛 | 3 | 每场前 2 名晋级。 |
| `final` 决赛 | 5 | 决出最终名次。 |

赛制按队伍数自动选择：

| 队伍数 | 阶段 |
|---:|---|
| `<= 4` | 排位赛 -> 决赛 |
| `5-8` | 排位赛 -> 半决赛 -> 决赛 |
| `>= 9` | 排位赛 -> 小组赛 -> 半决赛 -> 决赛 |

这些是正式比赛流程，不等同于我们本地跑的 `pytest` 或 `validate_controller.py`。本地测试应该尽量覆盖 `basic` 和 `complex`，正式前再依赖线上测试队列和测试赛确认。

## 6. 当前项目已覆盖情况

本文是**赛道和测试入口的静态清单**，不维护"当前跑到哪一步"——那会和 `experiments/STATUS.md` 漂移。
本仓库的实时状态（哪些赛道跑通、最新 baseline、未解问题、下一步、最近一次校验/`pytest` 结果）**只看 `experiments/STATUS.md`**，历次结果看 `experiments/runs.csv` 和 `experiments/notes.md`。

固定不变的事实：

- 本地可直接跑的官方测试见本文第 2 节；本仓库自己的校验链是 `scripts/validate_submission.py` + `pytest` + 官方 `validate_controller.py`（命令见 `docs/official_testing.md`）。
- 正式比赛主要按 `complex` 准备，`basic` 是默认和基础验证赛道，`airacer` 不作为正式目标（见第 5 节）。

## 7. 信息来源

- `/Users/day/Desktop/Github/pkudsa.airacer/sdk/worlds.py`
- `/Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py`
- `/Users/day/Desktop/Github/pkudsa.airacer/sdk/tests/`
- `/Users/day/Desktop/Github/pkudsa.airacer/sdk/docs/local_test_guide.md`
- `/Users/day/Desktop/Github/pkudsa.airacer/READMEs/README_blueprints.md`
- `/Users/day/Desktop/Github/pkudsa.airacer/READMEs/README_demo_testing.md`
- `/Users/day/Desktop/Github/pkudsa.airacer/READMEs/README_race_rules.md`
