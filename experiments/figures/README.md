# 报告可视化归档（figures）

`experiments/figures/` 是**长期保留、进 git、面向最终报告和开发回查**的可视化精选区。
它专门解决一个问题：过去 AI 复盘时看的那些图（整场轨迹/速度图、带 mask 和白线点的感知标注帧……）
都生成在 `.tmp/` 里，跑完就被轮换/删掉，写报告时无图可用，只能重跑或重画。这里就是**把值得留的图沉淀下来的地方**。

## 和其它机制的分工

修改记录（代码、参数、结论）已经由 `experiments/notes.md` / `runs.csv` / git 负责，本目录只管**可视化**。三个存图相关的地方分工如下，不要混用：

| 位置 | 存什么 | 目的 | 生命周期 |
|---|---|---|---|
| `.tmp/run/` | 整场相机帧 PNG、控制日志、临时 overlay、Webots 录像 | 当轮复盘的原始素材 | 跑下一轮自动轮换，确认无依赖后删 |
| `experiments/cases/` | 最小失败窗口 + 1–3 张 overlay + 裁剪日志 | **回归/调试复现**（修好可能就删） | 中期，问题解决后可清 |
| `experiments/figures/`（本目录） | 每个里程碑版本的精选图（整场概览 + 关键时刻 + 对比） | **最终报告 + 开发回查的叙事** | 长期保留，进 git |

判断归哪儿的简单规则：
- 「这张图是为了下次还能复现某个 bug」→ `cases/`。
- 「这张图我写报告会贴出来，或之后想回看这版开得怎么样」→ `figures/`。
- 「这张图只是这次复盘扫一眼」→ 留在 `.tmp/`，别归档。

## 值得留下的可视化类型

下面每类都注明**展示什么**、**生成命令**、**留几张**。生成命令里的 `<run>` 指 `R-id`，
`telemetry` 默认在 SDK 的 `.local/recordings/telemetry.jsonl`，跑完后建议先 `analyze_telemetry.py --archive <R-id>` 或直接指定路径。

### 1. 整场轨迹 + 速度 + 事件图 `trajectory_speed.png`（必留，每个归档 run 一张）
顶视 x-y 轨迹按速度着色，叠加起终点、最长爬行段、状态异常（碰撞/卡住）点、lap、事件和可选撞栏接触点；
下方是速度-时间曲线。这是「这一版整体开得怎么样、在哪卡住、哪段慢」的总览图，报告里讲每个版本都用它。
```bash
python scripts/plot_run.py --telemetry <telemetry.jsonl> \
  --contact-log .tmp/run/contact_<track>.jsonl \
  --out experiments/figures/<run>_<slug>/trajectory_speed.png \
  --title "<R-id> <track>"
```
如果没有 contact log，可以省略 `--contact-log`。有 contact log 时，深红 X 是撞栏接触位置，深红时间窗是接触时段；
相距不超过 4.0 world units 的多个接触 episode 会合并为一条标注。

### 2. 感知标注帧 `overlay_<t>_<slug>.png`（关键时刻 1–4 张）
左右相机画面 + 道路 mask（绿）+ 边缘（黄）+ 扫描线 + 中心/白线点（红），带时间戳和 fill/points 标注。
这是「车在那一刻到底看到了什么、mask 和白线点对不对」的证据图，用来解释某个走线/卡住为什么发生。
**只在报告会讲到的决策时刻出图**（第一个左弯、卡住点、白线漏检处……），用 `--at` 精确指定时间，
不要把整场 overlay 都倒进来。需要先有该窗口的相机帧 PNG（`webots_run.sh` 默认就存）。
```bash
python scripts/analyze_perception_dump.py .tmp/run/frames_<track> \
  --control-log .tmp/run/control_<track>.jsonl \
  --overlay-dir experiments/figures/<run>_<slug> \
  --at 145.7,177.4
```

### 3. 立体原图 `stereo_<t>.png`（可选，≤2 张）
仅左右原始画面拼接、不加任何标注，作为 overlay 的「标注前」对照。只在原图本身能说明问题（如画面冻结、对向白车）时留。

### 4. 顶视快照 `live_view.png`（可选，1 张）
SDK 录制目录里的 `live_view.jpg`（supervisor 顶视），直观显示车在赛道上的位置。报告里需要真实场景截图时留一张。
```bash
cp /Users/day/Desktop/Github/pkudsa.airacer/sdk/.local/recordings/live_view.jpg \
  experiments/figures/<run>_<slug>/live_view.png
```

### 5. 颜色采样卡 `color_calibration_<date>.png` + `.json`（每次重大感知改动一组）
道路/路牙/栏杆/草/天等采样色块，配 `color_samples.json`。说明「mask 阈值是怎么标定的」。放 `calibration/` 子目录。

### 6. 对比图 `compare/<slug>.png`（按报告需要）
跨版本同一赛道区域的并排对比（如 R011 vs R024 在内圈），用来讲「这次改动好转/恶化在哪」。多为手工拼接，放 `compare/`。

## 不要留下

- 整场相机帧 PNG、整场 overlay（几十上百张）、整场 telemetry/控制日志复制件。
- Webots 屏幕录像、批量截图。
- 调试单文件、SDK 临时克隆、cache/`.DS_Store`/`__pycache__`。
- 「好看但讲不清一个点」的图。报告图的价值在于支撑一个结论，不在数量。

## 文件架构

```text
experiments/figures/
  README.md                         # 本文件（规则）
  <R-id>_<slug>/                    # 一个归档 run 一个目录，slug 用简短英文
    trajectory_speed.png            # 必有
    overlay_000145_700_corner.png   # 关键时刻，0–4 张
    stereo_000145_700.png           # 可选
    live_view.png                   # 可选
    CAPTION.md                      # 必有：每张图一条说明
  R042_to_R049_turn_in_evolution/   # 跨版本主题图组：入弯调试
  R045_to_R049_speed_evolution/     # 跨版本主题图组：提速调试
  compare/
    R011_vs_R024_inner_rail.png
    CAPTION.md
  calibration/
    color_calibration_2026-06-11.png
    color_samples.json
```

文件名里的时间戳沿用存帧/overlay 的 `_HHMMSS_mmm`（与 `.tmp` 一致），便于和控制日志、telemetry 对齐。

## 选择标准（留多少、怎么选）

1. **建哪个目录**：只给「值得写进报告或之后会回查」的内容建目录。单次 run 用 `<R-id>_<slug>/`；
   像 R042→R049 这种跨版本机制复盘，可以按主题建目录，例如 `*_turn_in_evolution/`、`*_speed_evolution/`。
   普通一次性调参、回归小跑**不建**。
2. **每个目录留多少**：轨迹图 ×1（必），关键 overlay 0–4 张，stereo/live_view 合计 ≤2，整目录控制在**几 MB 内**。
   如果觉得要留 5 张以上 overlay，多半是还没想清楚报告里到底讲哪个点——先收敛结论再选图。
3. **`CAPTION.md` 是硬门槛**：每张图一条，写清三件事——
   - **展示什么**（一句话）；
   - **来源**：R-id + 赛道 + 时间戳 + 生成命令（可复现）；
   - **结论/看点**：这张图支撑报告里的哪个判断。
   没有 caption 的图等于噪声，不要留。
4. **优先「能讲清一个点」的图**，而不是「画面好看」的图。

CAPTION.md 模板：
```markdown
# <R-id> <slug>

## trajectory_speed.png
- 展示：R024 complex 整场轨迹与速度。
- 来源：R024，complex，car_1，telemetry=.tmp/r024.../telemetry.jsonl；
  `python scripts/plot_run.py --telemetry ... --out ... --title "R024 complex"`。
- 看点：x≈169,y≈112 长 37s 近停（橙圈），对应报告里"入弯半径太小切内线"。

## overlay_000145_700_corner.png
- 展示：t≈145.7s 左右相机感知标注。
- 来源：R024，frames_complex + control_complex.jsonl；`analyze_perception_dump.py ... --at 145.7`。
- 看点：白线点缺失、road mask 把内侧栏杆吃进来 → 解释为什么没把车带回中心。
```

## 工作流（跑完一轮、决定归档时）

1. 先按 `docs/ai_offline_review.md` 在 `.tmp` 里复盘，挑出报告要讲的 1–2 个结论和对应时刻。
2. `plot_run.py` 出整场轨迹图；`analyze_perception_dump.py --at <t...>` 出关键 overlay。
3. 建 `experiments/figures/<R-id>_<slug>/`，把选中的图放进去，写 `CAPTION.md`。
4. `git add` 这个目录（图会进版本库，所以才要控制数量和体积）。
5. 之后再清 `.tmp`——此时报告需要的图已经沉淀，不怕被轮换删掉。
