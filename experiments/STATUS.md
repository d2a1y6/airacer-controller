# 当前状态（唯一活动交接文档）

> 新接手（人类或 AI）从这里开始读。本文只回答四件事：现在代码处于什么状态、哪些规矩不能破、
> 还有哪些没解决的问题、下一步做什么。
>
> **更新规则**：每轮工作结束时就地更新本文件（覆盖过时内容），不要再新建 `handoff_<date>.md`。
> 历史叙事查 `notes.md`（按 R-id 倒序）、`runs.csv` 和 git log。

最后更新：2026-06-12（白线感知 **Phase 2.2 候选已实现并完成 AI 短测 R029/R030/R031**：R028 通过第一个左弯窗口，但 `t≈32→35` 仍有短暂白线掉线和低速硬左。R029 查明原因是弯中稀疏虚线横向跳变略超门槛、单侧相机短时凑不齐双目条件。当前候选只在 complex 红色环境启用低置信单目白线兜底，放宽曲线虚线 `max_center_jump_ratio 0.24→0.32`、`min_y_span 70→60`，并把 offset-heading 冲突的回中优先阈值 `0.30→0.18`。AI complex 短测显示第一个左弯无长爬行、无 telemetry 事件，`line_conf>0` 达 `481/500`，`t≈42` 已稳定出弯；basic 短回归 R030 显示 `red_env` 全程 0、无近停或事件；R031 覆盖旧 R024/R025 后段 `130→185s` 内切窗口，也无事件、无近停。**这是走线/驾驶改动，必须下一次人上车跑 complex 终判；R026/R027 第一个左弯 case 仍 open，未合 main。**

之前（2026-06-11 仓库整理）：相机帧改无损 PNG 且 `webots_run.sh` **默认每轮存帧**，跳完不用为看某时刻重跑；删除废弃 `docs/debug_tools.md`；README 加文档地图；新增报告可视化归档 `experiments/figures/` + 生成器 `scripts/plot_run.py` / `analyze_perception_dump.py --at`。上一轮实验结论：R024 证明 complex 旧 `x≈169,y≈111` 低速/内切问题仍会复现，不能合 main。

## 阅读路径

1. 本文。
2. `README.md`（目录与命令）、`CLAUDE.md`（模块边界、提交限制）。
3. 按角色：人类实跑读 `docs/human_webots_testing.md`；AI 离线复盘读 `docs/ai_offline_review.md`。
4. 需要某次 run 的细节时，再读 `experiments/notes.md` 对应 R-id。不需要通读全部历史。

## 铁律（每条都吃过亏）

1. **实车（人类 Webots + 肉眼）是唯一裁判**；离线指标只用来提假设、抓全局回归，绝不能否决实车结论。
2. **`lost` 率不是质量指标**：车 lost 时直线滑行（不停车、不偏出），lost 多≠开得差。gate-bridge 导致的 lost 虚高是良性的，不要为降数字回退它（R005 栽过）。见 memory `on-track-truth-over-offline-proxy`。
3. 任何感知改动要用整场记录找关键窗口复盘，不能只看目标点（"局部修好全局砸锅"出现过两次：C001、R013/R014）。
4. 用领域常识 sanity check：basic 是顺时针、全程右弯（曲率应恒为正；出现"满信心左弯"必是 bug）。
5. policy/速度/走线类改动**没有离线指标**，只能人上车判断，**不要 autonomous 盲调**。感知类改动可先离线筛，但仍需人上车终判。
6. 调试构建（含 `open/json/np.save`）**禁上传**；提交只用 `submissions/final/team_controller.py`，必须过 `validate_submission.py` + 官方 validator + `pytest`。
7. **清 `.tmp` 前先看 notes 的"下一步"**：如果下一步依赖某个失败窗口的帧/日志，先裁进 `experiments/cases/` 再删（R014 撞栏帧被清掉、导致下一轮必须重跑，就是这个错）。

## 版本地图

| 版本 | 位置 | 实车结论 |
|---|---|---|
| **当前分支最新状态** | `codex/perception-dropout` | 控制策略等同 `313e882`；本轮新增跳点取证工具、R024/R025 日志和文档，并把跳点/调试存帧默认改为每 10 帧一次。R024 的 boundary escape 加强已撤回。**整条 complex 未跑通，不能合 main。** |
| **上一提交** | `313e882` | 已有 Webots controller console 捕获和限时存帧调试开关。控制策略包含 R021 采样色卡与 R022/R023 半径/escape 分离修复，但 R024 证明 complex 旧低速窗口仍会复现。 |
| **R011/R012 版**（白线位置优先后置修正） | commit `16ae3f3`，已快照 `baselines/R011_line_posfirst_2026-06-11/` | basic 用户验证最佳：≈259.8s 高速通过车阵不撞 car5；complex 能过第一左弯但后段 `x≈-10,y≈-27` 近停。 |
| **C004**（曲率可信度门控） | commit `0fc367e` | 更早的实车验证可靠基线（无白线逻辑），过弯不再反向打轮。 |

### R013/R014 退化机制（代码层定位，2026-06-11）

estimator `_apply_line_target` 以 0.82/0.68/0.58 权重把 `lateral/heading/lookahead` 改写成白线目标，导致：

1. `offset_risk` 被白线偏移抬高 → 频繁进 correcting/hard_turn → 速度被 cap（basic correction 0.50 / hard_turn 0.30）→ **basic 变慢 + 无意义减速（P3）**；
2. 直道判定要求 `offset_risk ≤ 0.12` → 判不成直道 → R008 的直道提速失效 → 更慢；
3. `corner_arrival = |lateral|/0.30 + |heading|/0.45` 被抬高 → **C005 入弯门控被提前骗开 → 更早向内打轮 → 切内线贴栏（P1）**；
4. margin guard 的余量来自 road-mask 边界点，mask 饱和/fallback 时是噪声 → 额外舵角推力（P3），且 R014 证明防撞失败；
5. `_lost_track` 把 `line_confidence` ×0.08 衰减 → 丢线帧（basic 53%，恰是蓝门饱和帧）白线修正失效，而 R011 在这些帧靠白线保向。

修复（全部已实现，待上车）：line 融合权重归零（仅诊断）、margin guard 参数置 no-op（仅诊断）、policy 末端恢复 R011 后置 ±0.34 有界修正（不进 risk/mode/速度/门控，跨帧状态记修正前舵角）、lost 帧透传本帧白线状态、感知白线检测不再被道路观测质量门控。

## 白线感知 Phase 1/2（2026-06-12，已实现候选，待上车）

**诊断（结合 R025 实测）**：complex 切内线撞栏的根因**不是策略权重**——estimator 在白线可信时已用 0.85 权重压过道路 mask。根因是**弯道里几乎拿不到可信白线**：全程仅 14.7% 帧有线，弯道窗口（120-180s）仅 4%，且检出的线 **48% 因 |offset|>0.30 被信任门拒**。用户取证进一步指出：弯道内侧**亮白护栏支柱**和中心虚线一样亮，旧的纯亮度白阈值 `np.all(band>=145)` 无法区分，会把支柱当成大 offset 的"线"。

**Phase 1 改动**（`perception._camera_line_state` + `params.LINE_FOLLOW_PROFILE`）：
1. 白段判定 = 亮（最暗通道≥`white_min`）**且近中性**（色度≤`white_chroma_max=40`，排除偏蓝灰护栏）。
2. 白段**两侧紧邻必须都是深灰路面**（`_neighbors_are_road`，"白线在大片路面中间"），护栏支柱外侧是路牙/红地/草 → 拒绝。
3. offset/heading 用**最近/最远各 1/3 实测点中位数**，不再直线外推（修掉弯道 offset 被放大误拒）。

**验证**：`pytest` 106 passed（新增 4 个合成帧单测：护栏支柱外侧红地→拒绝、同条但两侧路面→接受、偏蓝亮条按色度拒绝、弯道中心线被召回且 offset 不放大）；官方 validator 通过（p95 25.18ms，旧有 perf warning 未恶化）。

**用唯一一张真帧（t=144 stereo preview）离线抽查**，结论很关键：
- Phase 1 **不会误伤真白线**：真虚线像素色度仅 18-34（全部≤40），真沥青 BGR≈(83,75,65) 落在 `road_dark` 范围内，road context 成立。**无召回回退**（旧纯亮度阈值在该帧同样检不到中线）。
- 但该帧中线确实没被召回，原因是**采样问题**：虚线集中在 y≈148-303、稀疏成簇，而 5 条固定扫描行（230/275/321/366/412）大多落在虚线**间隙**里，近处行又在虚线图案下方。
- **→ Phase 2 的真正杠杆是"扫描行密度/自适应行位置 + 单目线"，不是继续放宽颜色阈值。** 这条结论已用真帧坐实，下一步直接照做。

**R026 进一步取证**：Phase 1 后起步居中顺、整场 lost 仅 `19/2925≈1%`，但第一个左转仍有 `14.1s` 爬行（`t=33.8→47.8, x≈188.6,y≈-27.1`）。入弯时 `lateral≈0`，但 `heading/lookahead/target_steering` 强负，说明 road-mask 远处弯道预判提前左打；旧控制日志在 `t≈31.36` 主问题帧 `line_conf=0`，没有白线把车拉回中心。保存帧用当前代码回放可在同一时刻得到 `line_offset≈+0.43,line_heading≈-0.54,line_conf≈0.8`。

**Phase 2 候选改动**（已实现，待上车）：
1. `LINE_FOLLOW_PROFILE` 扫描窗口上沿放到 `0.44`，扫描行从 `5` 加到 `12`，覆盖稀疏虚线簇。
2. 白线置信度改成 `len(points)/confidence_full_points`，与扫描行总数解耦，避免加密扫描反而稀释置信度。
3. `offset_trust_max` 和 `line_target_normal_offset_max` 从 `0.30` 放宽到 `0.55`。Phase 1 已用 road-context 结构性拒绝护栏，因此这里允许真实 off-center 白线进入主几何链路，用于回中。
4. 暂未放开普通单目白线，也暂未继续调 turn-in gate / curve gate；这些留给下一轮实跑后再决定。

**R027 复跑诊断与 Phase 2.1 候选**（2026-06-12，已实现，待上车）：
- 复跑结果：用户观察第一次左弯仍撞/擦左边；telemetry 无 collision event，未长时间卡死，`t=46.02` 手动停止。
- 机制：白线已大量召回（`t=27→37` 窗口 `191/313` 帧 `line_conf>0`），但 `line_heading` 很负，road heading/lookahead 也很负；当 `line_offset>0` 表示应右回中时，heading 仍把目标舵角推向左。另有 `line_offset≈0.62-0.71` 的真实弯中白线被旧 `0.55` 门拒掉。
- 已改：新增 `line_offset_priority_min` / `line_conflict_heading_scale` / `line_conflict_projected_scale`，让 estimator 在 offset-heading 冲突时削弱 heading 并保持 lookahead 同侧；新增 `offset_curve_min_scale`，让 policy 弯中保留部分纯 offset 回中修正；`offset_trust_max` / `line_target_normal_offset_max` 调到 `0.75`。
- 开环回放：同一批 R027 帧上，`32.64/32.96/34.88/35.20` 这些大 offset 帧能进入链路，左舵明显收小或转成右向回中。仍不能替代闭环 Webots。

**R028 AI 自主短测**（2026-06-12，已完成，只测当前问题窗口）：
- 配置：`bash scripts/webots_run.sh complex --frames 2`，AI 在 `t≈64.6s` 主动停止，没有跑完整场。
- 结果：第一个左弯窗口通过。telemetry `t=27→43` 从 `x≈170.2,y≈-29.5` 到 `x≈198.9,y≈-0.55`，状态一直 `normal`，无 collision event；全段 supervisor 近停占比 `<0.3=0.00`。
- 控制日志：`t=27→43` 中 `348/500` 帧 `line_conf>0`，`line_offset` 最高 `0.70`；残留是 `t≈32→35` 一段短暂 line/trust 降级，最小命令速度 `0.223`、最大左舵约 `-0.65`，但随后恢复，`t≈42` 已居中加速。
- 判断：当前候选不再复现 R026 的 14 秒爬行，也没有 R027 那种持续撞/擦左侧；先不盲调。case 保持 open，等待人眼/完整 run 终判。

**R029 Phase 2.2 候选**（2026-06-12，已完成，只测当前问题窗口）：
- 机制补充：R028 `t≈32→35` 的短掉线来自曲线虚线召回门槛过紧，不是护栏误锁。`t=32` 左相机命中 3 点但 y 跨度 63px，旧门槛 70px；`t=34.4` 虚线从近右到远左，横向跳变略超 0.24 宽度门。
- 已改：只在 complex 红色环境里启用低置信单目白线兜底；`max_center_jump_ratio 0.24→0.32`，`min_y_span 70→60`；offset-heading 冲突优先阈值 `0.30→0.18`，避免召回的强负 heading 抢走回中方向。
- 闭环短测：`t=27→43` 中 `line_conf>0` 为 `481/500`，telemetry 从 `x≈170.4,y≈-29.5` 到 `x≈199.0,y≈5.6`，状态一直 `normal`，无事件，窗口最低 supervisor 速度约 `1.36`，`t≈42` 已出弯。
- 白线居中证据：同窗口 `|line_offset|` 中位数 `0.102`；出弯段 `t=37→43` 中位数降到 `0.028`，`t≈41→43` 连续接近 0。
- 判断：比 R028 更接近“沿中间白色虚线”目标；仍需人眼确认是否还有轻微擦左或视觉上没骑线。

**R030 basic 短回归**（2026-06-12，已完成，只测早段）：
- 配置：`bash scripts/webots_run.sh basic --frames 4`，AI 在 `t≈46.8s` 主动停止。
- 结果：telemetry clean，无事件、无近停，末帧 `x=84.69,y=265.23,speed=5.95,status=normal`。
- 判断：`red_env` 全程 0，说明 R029 的红色环境单目白线兜底没有污染 basic；控制日志 `mean|lat|=0.039`，`|lat|>0.3=0.00`，basic 早段未见明显回归。

**R031 后段内切窗口短测**（2026-06-12，已完成，不跑完整场）：
- 配置：`bash scripts/webots_run.sh complex --frames 4`，AI 在 `t≈220.35s` 主动停止，覆盖旧 R024/R025 的 `130→185s` 窗口。
- 结果：telemetry clean，无事件、无近停；旧窗口从 `x≈118.5,y≈98.3` 到 `x≈79.6,y≈5.4`，最低真实速度约 `1.74`。
- 判断：旧 `x≈169,y≈111` 长爬行未复现；overlay 显示 `t≈149→155` 的白线候选仍在路面中，没有明显锁到远处栏杆。

**回归门槛**：下一次人跑 `bash scripts/webots_run.sh complex` 必须确认第一个左转不再出现 R026 的 `14.1s` 爬行，也不能重新锁白色护栏。若肉眼仍见擦左，优先复盘 R029 的 `t≈34→36` 正常左弯舵角是否仍切得过内。case：`experiments/cases/R026_first_left_tight_radius/`（open）。

## 未解问题（用户视角，按优先级）

> 2026-06-11 更新：下面 P1–P3 在 R013/R014 上的恶化部分已有候选修复（见"R013/R014 退化机制"），
> 但 R011/R012 时代就存在的残留（骑线精度、complex 两处低速窗口）仍需取证后对症修。

### P1 转弯半径太小 / 切内线贴内侧栏杆
- R014/R021/R024 的典型表现都是入弯半径太小，切到内圈栏杆后长时间爬行。R022 曾短跑通过旧 `x≈169,y≈111`，但 R024 长跑复现了同一区域 37.4s 近停，说明它不是稳定修好。
- R026 显示 Phase 1 后早段已有改善，但第一个左转仍出现 `14.1s` 爬行；已归档 open case `experiments/cases/R026_first_left_tight_radius/` 和报告图 `experiments/figures/R026_first_left_tight_radius/`。
- R024 的“更早触发 boundary escape”失败并已撤回；继续堆 escape 不是主线。优先查为什么常规驾驶没有把白线保持在车身中心。
- 已明确不要重开普通 margin guard：R014 证明它会受 road-mask 噪声影响。边界余量只用于 escape 中的贴边方向判断。

### P2 车没有稳定骑在白线上
- 用户在 R011/R013 都肉眼确认：车没有稳定骑在白线上。
- R025 把 `130-185s` 补帧后，控制日志显示 `line_conf=0`、`mode_reason=no_line_conf`。这一段不是“看见白线但不优先用”，而是白线感知链路没有提供目标。
- 另一个窗口 `380-420s` 会出现白线候选，但 `line_offset≈0.5-0.86`，被信任门控拒绝。下一步要区分“真白线漏检”和“护栏/白车误锁被正确拒绝”。

### P3 无意义打轮和减速
- R013/R014 仍明显，用户特别强调。可能与 P2 同根（中心目标抖动），先取证再定。

### （已大幅缓解）直道慢 / lost 限速
- R008 已修：直道判定改看 `curvature/lookahead/lateral`、加直道记忆和 lost 直道滑行后，直道真实速度稳定 >1.5（median 6.10）。不要再用 lost 率否决这个修复。

## 证据现状

- R021 颜色采样证据保留在 `.tmp/color_sample/color_samples.json`、`complex_sample.png`、`sample.png`。
- R024 static-car 小窗口只保留 3 张 stereo preview：`.tmp/r024_static_grid_case/preview/`。
- R025 证据保留在 `.tmp/r025_line_priority_run/`：控制日志、telemetry、trajectory 图、live_view，以及 7 组 `130-185s` overlay/stereo PNG。原始帧已删。
- `.tmp` 已从约 700MB 清到约 18MB；当前保留的都是下一轮可能直接用到的小型证据。
- 流程已修补：`scripts/webots_run.sh` 会自动清理孤儿进程/旧遥测并把上一轮产物轮换到 `.tmp/run.prev`，最近两轮产物不会再被立即删掉。
- **相机帧默认每轮都存**（无损 PNG，每 10 帧一对，整场约几百 MB）：`scripts/webots_run.sh basic|complex` 不加参数就存帧；逐帧用 `--frames 1`，限窗用 `--frame-window S E`，不看画面用 `--no-frames`。再也不需要"跑完发现没存帧 → 为看一个时刻重跑一整圈"（R024→R025 的坑已堵死）。帧从 `.npy` 换成 PNG，消费脚本 `analyze_perception_dump.py`/`replay_offline.py` 已同步改读 PNG。
- **报告可视化归档机制**（2026-06-11 新增）：精选图进 `experiments/figures/<R-id>_<slug>/`（进 git、长期保留），规则/选择标准见 `experiments/figures/README.md`。新增/扩展两个生成器：`scripts/plot_run.py`（整场轨迹+速度+事件总览图，替代过去手写 matplotlib）、`scripts/analyze_perception_dump.py --at <t...>`（为指定时刻出感知标注帧 overlay，不再只挑丢线帧）。`matplotlib` 已加入 `requirements.txt`。与 `experiments/cases/`（复现 bug 用）分工明确。
- R026 第一个左转半径过小已按规则归档：case 在 `experiments/cases/R026_first_left_tight_radius/`，精选图在 `experiments/figures/R026_first_left_tight_radius/`。case 明确标记 open，不能当作已修复证据。
- Console 捕获结论：默认 `run_local > file 2>&1` 抓不到 Webots GUI/controller 面板里的学生控制器输出；debug 构建现按 `AIRACER_CONTROLLER_CONSOLE_LOG_DIR` 把 controller 进程的 stdout/stderr tee 到 `.tmp/run/webots_console/*.log`。实时读用 `tail -f .tmp/run/webots_console/*.log`，跑完也能直接读。
- 跳点取证工具：`scripts/webots_jump_run.sh` 可从已有 telemetry 的某个 `t` 近似启动 Webots。因为帧已默认每轮都存，它**不再用于"补存帧"**，真正用途是看**当前（已改过的）代码**从某个历史姿态出发会怎么开（上一轮录制帧只反映上一轮代码）。它只恢复 `x/y/heading`，不恢复速度、物理状态、controller 记忆或仿真时钟；可以近似往前跑几秒看趋势，不能当真实续跑或正式验证。

## R024/R025 最新结论（2026-06-11）

R024：尝试把 boundary escape 触发提前、速度门槛放宽，结果失败。complex 仍在 `x≈169,y≈111` 低速 37.4s，后续还出现 `x≈-42,y≈124` 和起点前长时间近停，最终 `t=622.016` 手动停止。该策略改动已撤回。

R025：专门重跑 `130-185s` 相机帧窗口。控制日志显示该窗口 `line_conf=0`，line correction 为 0；所以“白线优先”没有被执行，是因为没有白线目标输入。下一步要修 `_camera_line_state`/ROI/信任链路，让真实中心虚线在这类弯道能被检测到，同时不能把白栏杆、白车、斑马线放进来。

## R022/R023 半径与 escape 分离结论（2026-06-11）

提交接口只有 `control(left_img, right_img, timestamp)`，没有碰撞、速度、IMU 或接触传感器；“发生碰撞”只能从图像余量、画面冻结、低速命令和持续大舵角间接推断。

当前工作树把两套逻辑分开：

- 常规驾驶继续由 road/白线几何决定，目标是让车身中心追白线；偏左时白线在右侧，舵角应往右。
- escape 只在推断贴边/卡住时介入，方向先按几何兜底；若单侧近处余量接近 0，就强制远离低余量侧，避免“贴左还左打、贴右还右打”。

R022 complex：旧 `x≈169,y≈111` 长爬行已消失，`t≈145.7s` 到 `x=137.25,y=90.97,status=normal`，`t≈177.4s` 到 `x=91.12,y=155.50,status=normal`；最长近停仍是早段固定 5.0s。R023 basic：短跑 `t≈130.6s` 控制日志正常，`mean|lat|=0.033`，未见新误触发。

## R021 采样色卡修复结论（2026-06-11）

用户指出之前没有真实采样颜色，这个判断是对的。当前已把深灰路面、浅灰路牙、浅灰栏杆、绿草、红地、蓝天写入 `COLOR_PROFILE`，道路 mask 只认采样暗灰路面核心；侧边蓝灰栏杆不再靠蓝门桥接逻辑混进 road mask。

关键修复不是放宽 road，而是修掉误降置信：采样暗灰路面在 complex 开头和 90s 窗口能形成完整 mask，但之前被 `red_mask_fill_warning=0.34` 打成低置信，融合阶段丢成空观测。R021 把阈值提高到异常饱和区间后，同批真实帧离线重放 lost 从 `194/203` 降到 `0/203`。

闭环验证：complex 前 95.8s lost 仅 `23/2995`，横向均值 `+0.001`，第一左弯未撞；但 155s 手动停止时仍在 `x≈169,y≈111` 低速卡住。目标还没完成。

## R017-R020 复验结论（2026-06-11）

R017 复验 `656b222`：直道左右摆动和第一左弯撞栏已明显改善，但后段仍在 `x≈-10,y≈-27` 近停。日志显示卡死画面 `right_margin=0`、`near_obstacle=true`，指令速度多在 `0.22-0.4`，低速脱困不稳定触发。

R018 当前保留的候选修复：新增边界障碍脱困路径。它让 `x≈169,y≈111` 旧卡边段能通过，但后段在 `x≈9,y≈87` 卡死。关键入口是 `t≈289.98`：`lat≈0`、`heading≈+0.64`、`curvature≈-0.26`、`near_obstacle=true`、`track_conf≈0.46`，策略给了 `st≈+0.59` 大右舵，切进内侧；顶住后再 `escaping st=-0.76 sp=0.86` 已经太晚。

已撤回两条反例：

- R019：escape 执行中按实时边界余量翻向。会把早段重新卡在 `x≈166,y≈117`，撤回。
- R020：低置信/居中入弯限舵和几何冲突限舵。仍卡 `x≈165,y≈119`，撤回。

结论：当前问题不是“escape 不够强”，而是 **R018 后段入口的感知/几何信号让车还居中时突然大右舵切内线**。下一步必须围绕 `t≈288-296` 的帧做感知链路修复，避免重复盲调 escape。

## R015/R016 取证结论与第二轮修复（2026-06-11，已实施）

R015（basic）/R016（complex）首跑暴露后置白线修正的三类误锁（详见 notes.md）：

1. **白色护栏当线**（complex 直道 `lo` 闪烁 0↔0.4-0.93 → steering 0↔+0.30 反复跳 = "直道左右打轮"）；
2. **白车/斑马线当线**（basic 车阵 `near_obstacle=true` 时单帧 `lo=+0.35` → steering 突跳 +0.51 = "朝白车打轮"）；
3. **弯中三段不连续白线闪烁**（basic 第二弯 `lo` 0/-0.3/-0.64 跳变；complex 左弯 +0.34 修正抵消入弯舵角）。

另发现 **escape 误触发 bug**：急弯卡边几何脱困把"平稳巡弯（sp≈0.46）+ 高弯量 + 签名稳定"误判为卡边，
t=37.2 强制 -0.58 舵角 0.8s，是 R016 撞左栏的直接原因。

修复（policy/params，全部有单测）：

- 线修正信任门控：`|line_offset| > 0.30` 拒绝（骑线时不可能这么大）、帧间突变 >0.12 拒绝、连续 3 帧确认、EMA 0.5 平滑、`curve_risk ≥ 0.35` 压零（弯中线段不连续）、`near_obstacle` 拒绝、escaping 帧不叠加；
- 几何脱困加低速门槛 `escape_turn_speed_max=0.36`：指令速度高于它不算卡边。

未取证残留：complex 直道每 ~0.6s 一次道路中心向左毛刺（lat 短暂 -0.2~-0.38 自恢复，疑红环境 mask 噪声
或蓝色 checkpoint 门），`.tmp/run/frames_complex/` 436 对帧已保留，待渲 overlay 定位。

## 下一步（建议顺序）

1. 请人用当前 Phase 2.2 候选从头跑 `bash scripts/webots_run.sh complex`。重点看 R026/R027 case 窗口：`t≈29→36` 第一个左转是否还撞/擦左边，视觉上是否沿中间白色虚线。AI 自主短测 R029 已通过这个窗口，但不能替代人眼终判。
2. 若仍失败，先对比 R029 控制日志：确认是 `t≈34→36` 的常规左弯舵角仍切内，还是白线误锁到护栏/路肩。前者再调 heading/turn-in 权重，后者回到 `_camera_line_state` 的 road-context 和单目兜底门控。
3. 修白线检测时继续保留误锁防护：白栏杆、白车、斑马线仍要拒绝，不能靠全局放宽阈值蒙混通过。
4. complex 新窗口修完后跑 basic 回归，确认没有破坏 R023/R026 的起步居中和 basic 通过状态。
5. complex 稳定跑通前不要合 main；跑通后再做提速和正式提交。

## 验证状态

最近一次（2026-06-12 Phase 2.2 候选后）：`pytest -q` 为 **113 passed**；`python -m py_compile controller/*.py scripts/*.py tests/*.py` 通过；`bash -n scripts/webots_run.sh scripts/webots_jump_run.sh` 通过；`scripts/validate_submission.py submissions/final/team_controller.py` 通过；官方 `validate_controller.py` 通过但有软性能 warning（p95 `36.24ms` > 20ms）。正常构建 md5：fastest/final=`f4b79c09f6811580817ecfe04d1fb11a`，safe=`db16a4ac92af6082fcc2396ee46fe9be`。这是驾驶行为改动，必须人上车跑 complex 终判。

上一次（2026-06-12 Phase 2.1 候选后）：`pytest -q` 为 **110 passed**；`python -m py_compile controller/*.py scripts/*.py tests/*.py` 通过；`bash -n scripts/webots_run.sh scripts/webots_jump_run.sh` 通过；`scripts/validate_submission.py submissions/final/team_controller.py` 通过；官方 `validate_controller.py` 通过但有软性能 warning（p95 `32.29ms` > 20ms）。正常构建 md5：fastest/final=`c85e845cddfbd072daf17150688b9782`，safe=`bca1f6f4a494b3e160f5c6fa598dfb2e`。这是驾驶行为改动，必须人上车跑 complex 终判。

上一次（2026-06-12 Phase 2 候选 + R026 case/figures 归档后）：`pytest -q` 为 **108 passed**；`python -m py_compile controller/*.py scripts/*.py tests/*.py` 通过；`bash -n scripts/webots_run.sh scripts/webots_jump_run.sh` 通过；`scripts/validate_submission.py submissions/final/team_controller.py` 通过；官方 `validate_controller.py` 通过但有软性能 warning（p95 `40.57ms` > 20ms）。正常构建 md5：fastest/final=`1ee8ae55e1ec142710ba63e09b9435d8`，safe=`c4aa823bcde0d52d5b52437b6d43c4df`。这是驾驶行为改动，必须人上车跑 complex 终判。

最近一次（2026-06-11 仓库整理：帧改 PNG + 默认存帧 + 文档去重后）：`py_compile` + `bash -n` 通过；`pytest -q` 为 99 passed；`scripts/validate_submission.py submissions/final/team_controller.py` 通过。**正常构建 `fastest`/`safe` 的 md5 与整理前完全一致**（`d76e84..` / `784f4d..`），即上传文件和驾驶行为字节不变，官方 `validate_controller.py` 结论与上一轮相同（通过，p95 性能 warning 不变）。`submissions/final/team_controller.py` 低于 100KB。
