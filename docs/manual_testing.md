# 手动测试流程（带日志的迭代复测）

本文件是**日常调参的迭代回路**：改完 `controller/` 代码 → 在 Webots 里实跑看现象 → 拿到结构化日志 → 记账。

首次安装 Webots、官方 SDK 和 Python 依赖见 [official_testing.md](official_testing.md)；本文默认这些已就绪，只讲"改一版、测一版"的循环。

---

## 0. 数据来源与可信度（先理解，再操作）

一次 Webots 实跑会产生三份数据，可信度不同：

| 来源 | 路径 | 内容 | 可信度 |
|---|---|---|---|
| **控制器内部日志** | `--debug-log` 指定的 JSONL（如 `.tmp/run/control_basic.jsonl`） | 每帧发出的 `steering/speed` + 内部 `lateral/heading/curvature/conf/lost/mode` | **最高**：只由控制器进程写，每次截断重写，不受交错影响 |
| supervisor 元数据 | `<SDK>/.local/recordings/metadata.json` | 本次 run 的 `total_frames / duration_sim / finish_reason` | 高：每次 run 覆盖 |
| supervisor 遥测 | `<SDK>/.local/recordings/telemetry.jsonl` | 每帧真实 `x/y/speed/lap` | **会跨 run 残留**：孤儿进程/未截断会让多次 run 的数据交错（`t` 非单调）。分析脚本会自动切段只取最近一次，但仍要警惕 |

> 默认录制目录是 **SDK 自己的** `<SDK>/.local/recordings/`（不是本仓库），因为 `run_local.py` 没有重定向开关。`analyze_telemetry.py` 默认读那里并归档到本仓库 `.tmp/recordings/<标签>/`。

**结论**：诊断"控制行为为什么这样"以控制日志为准；遥测只用来确认"车物理上在哪、跑多快"，且要看脚本打印的 `完整性` 行。

---

## 1. 改代码 + 构建调试单文件

```bash
cd /Users/day/Desktop/Github/airacer-controller

# 改 controller/ 下的模块后，构建一个【带逐帧日志的本地调试单文件】
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --out .tmp/run/team_controller_debug.py
```

- `--debug-log` 会注入 `open()/json` 写日志——**这是本地调试专用文件，禁止上传平台**（validator 会拦）。
- 正式提交版另外单独构建（见第 6 节），不带 `--debug-log`。

## 2. 跑前清理孤儿 Webots（关键）

```bash
pkill -f webots; pkill -f run_local; sleep 1
```

上一次如果是**强行退出** Webots，可能残留进程继续往 `telemetry.jsonl` 追加，导致下一次遥测交错。每次跑前清一遍最稳。

## 3. 启动 Webots 实跑（调试构建必须 `--skip-validate`）

```bash
# basic
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world basic --car-slot car_1 --skip-validate

# complex（单车；若要排除发车格静止车，用你的 car1-only 临时 world）
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/.tmp/run/team_controller_debug.py" \
  --world complex --car-slot car_1 --skip-validate
```

- 调试构建含 `open/json`，**不加 `--skip-validate` 会被 run_local 的合规校验拦下**。
- Webots 图形界面会打开并加载控制器，逐帧喂图像、执行返回的 `steering/speed`。
- 确认 Webots 使用的 Python 能 `import cv2, numpy`（否则控制器每帧异常兜底返回 0）；环境自检见 [official_testing.md](official_testing.md) 第 5 节 / `sdk/check_env.py`。

## 4. 观察并退出

- 一圈是 practice 模式：**跑完一圈不会自动停**，会继续第二圈。看够了就停。
- 退出方式（推荐由轻到重）：
  1. Webots 窗口左上角暂停 → `Cmd+Q` 关闭 Webots 窗口（最干净，supervisor 会正常写 `metadata.json`）。
  2. 终端 `Ctrl+C` 中断 `run_local`。
  3. 兜底：`pkill -f webots`。
- **退出后再补一次 `pkill -f webots`**，确认没有残留进程（避免污染下次遥测）。
- 强行退出本身不会损坏控制日志（它实时 flush），但可能让遥测残留——所以才有第 2 步和脚本的自动切段。

## 5. 读日志 + 记账

```bash
# 控制日志（最可信）：震荡/速度/偏置/各 mode 占比/速度-转向耦合
python scripts/analyze_control_log.py .tmp/run/control_basic.jsonl

# 遥测（位置/真实速度）：自动切段只取最近一次 run，并归档留档
python scripts/analyze_telemetry.py --archive basic_R<编号>
```

- 看 `analyze_telemetry` 输出的 `完整性` 行：`clean` 才放心用坐标；`interleaved（检测到 N 段）` 说明有残留，脚本已只取最后一段。
- 然后按 [../experiments/notes.md](../experiments/notes.md) 顶部「记录规范」：分配一个 **Run ID（R0xx）**，在 notes.md 加一个区块，并在 `experiments/runs.csv` 追加同 ID 的一行（`notes` 以 `R0xx |` 开头）。

## 6. 正式提交版测试（不带日志）

确认一版要上传时，构建**干净**单文件并走完整校验：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/validate_submission.py submissions/final/team_controller.py
pytest
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

正式版**不能**含 `open/json`，所以不要用 `--debug-log` 构建它。

---

## 常见坑速查

- **遥测数字很离谱 / 出现末段时间外的"爬行段"**：跨 run 残留。先 `pkill -f webots`，必要时删 `<SDK>/.local/recordings/telemetry.jsonl` 再跑。
- **车一直返回 (0,0) 不动**：Webots 的 Python 缺 `cv2`/`numpy`，控制器每帧异常兜底；跑 `sdk/check_env.py`。
- **run_local 报合规错误**：调试构建忘了 `--skip-validate`。
- **不小心把调试构建当成提交**：`.tmp/run/team_controller_debug.py` 永远只在本地；上传用 `submissions/final/team_controller.py`。
