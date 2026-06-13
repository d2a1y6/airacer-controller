# 当前状态（接手从这里开始）

最后更新：2026-06-13（no_other_cars 已用当前 SDK 单车入口拿到官方 metadata；SDK checkpoint/单车入口已验证）。当前分支：`day-with_other_cars`（从 `with_other_cars` 派生）。

## 本次会话新增（2026-06-13 多车 KPI 度量基建）

确立了 `with_other_cars` 的**目标函数 = 名次期望积分**（TASK.md §10.4：10/7/5/3/1；第一名完赛后 60s 宽限期；累计 3 次严重碰撞 = DQ），不是单车的 lap time。为了能客观度量，做了三件事：

1. **修好 SDK checkpoint（根因，必读）**：`pkudsa.airacer/sdk/webots/controllers/supervisor/supervisor.py` 的 `CHECKPOINTS` 一直是占位坐标（cx 0~50），真实赛道上从没命中 → `lap`/`lap_progress` 恒 0、`final_rankings` 恒空。已改为**按 `world` 分派**、坐标取自各 `.wbt` 里的 `checkpoint_N` 门 Solid（整路宽、不可漏过）。两个连带修复：① 门沿行进方向加厚到 ~2.5m（原 0.1m 在 6m/s≈0.4m/帧下被跨过，所以连起跑线都没触发）；② `checkpoint_next` 初值 1→0（否则发车后第一次过起跑线不被当作计时起点）。方向由 in-order 序列隐式保证，去掉了 per-gate heading 要求。R062 先验证进度 0→0.44；R063 完整验证 6 车均完赛 1 圈、`metadata.final_rankings` 非空、ours rank=2。SDK 工作树中同一文件还含早前 contact logger 调试改动，审查时把 checkpoint hunk 和 contact logger hunk 分开看。
2. **KPI 脚本**：`scripts/analyze_multicar_kpi.py` 消费 `telemetry.jsonl`(+`metadata.json`)，输出名次/积分、完赛/DQ、严重碰撞(/2 预算)、超车净得失、**开局互挤**(已能量化用户描述的挤中线：R061 最近他车距 1.89m)、卡死、速度。telemetry 是 append 累积，脚本按 t 归零自动切 run。旧 telemetry 无进度时退化用行驶距离代理排名(标 `[proxy]`)。`tests/test_analyze_multicar_kpi.py` 8 项锁定。
3. **多车脚本接线**：`webots_auto_multicar.sh` 跑前清 `sdk/.local/recordings` 的旧 telemetry、跑后把 `telemetry.jsonl`/`metadata.json` 拷进 `.tmp/multicar/` 并自动打印 KPI。

**已补验证（R062-R065）**：6 车 complex 已确认 `lap_progress` 从 0 增长、`metadata.final_rankings` 非空、官方名次/完赛生效。R063：6 车均完赛 1 圈，ours rank=2、points=7、无 DQ/严重碰撞。R064 在新增对手方向感知后跑到 0.78 圈，rank 代理=1、无卡死/严重碰撞，但因墙钟硬超时未产生 metadata。R065 用 R064 后的新 policy 完整复测：ours 仍 rank=2、points=7、0 严重碰撞，total_time 256.767s，比 R063 快约 2.27s。

**单车官方 metadata（R066-R068）**：旧 SDK 单车入口 `--code-path/--car-slot` 没把 `--world` 写进 `race_config.json`，导致 supervisor 退回旧占位 checkpoint，R066 的 `lap_progress` 恒 0，已判 invalid。已修 SDK `run_local.py` 的单车配置生成，R068 用真正单车入口复测通过：`no_other_cars` complex 官方 rank=1，`total_time=252.863s`，`best_lap=252.928s`，0 major，status=normal，`finish_reason=grace_period_expired`。

**下一步（接手从这里继续）**：在已有 `obstacle_x/obstacle_size` 基础上继续做更强的不对称占位：目前只是“偏侧车少让速 + 按方向绕行”，还不是完整的防守/逼让策略。目标应从稳定 rank=2 转向争 rank=1，同时守住 0 major / 不 DQ。

## 一句话结论（day-with_other_cars 最新）

**多车避让/超车/脱困三件事都推进且实跑验证**。R061 最新 3 车 complex 复测跑过 R059 绿车卡死窗口：三车无持续近停，`car_1/car_3` 控制均速约 0.83，`escaping≈1%`，lost 0，绿车没有复现贴边卡死。
1. **早避让（最大突破，R055）**：把对手避让转向调强调早（gain 0.65 / cap 0.42 / blob 检测阈降）后，car_1 **不再陷进 CP3 对手车堆**——escaping 18.5%→0.7%、lost 13%→0%、均速 0.67→0.85，绕开并超过卡死的对手堆，自身只在 CP3 轻擦栏 1.5s。
2. **真倒车脱困（R053）**：`clamp_cmd` 放宽 speed 下界到 -1.0（本地 Driver API 倒车有效、线上 clamp 退化为前进兜底，见 [[reverse-speed-feasibility]]）；pinned 顶栏用 K-turn 反打、force_escape 朝开阔侧倒出。对刚性陷阱（车+栏杆夹角）有效。
3. **光流卡死检测（R061）**：control() 无速度反馈，车被顶住空转会自以为在巡航→既有零速脱困抓不到；`frame_motion`（64×48 灰度帧间 MAD，阈值 0.28 / 30 帧）识别"命令在前进但画面静止"。0.32 在 R060 会误触发，0.28 在复测中没有正常行驶连续触发。
4. **车身颜色 mask 纠错（R061）**：官方彩色车身用 HSV profile；白车/黑车只走亮度分支。原因是 Shadow black HSV 容差会把 complex 深灰沥青吃成车身，导致 `near_obstacle=True` 长期污染速度和白线门控。

**重要纠错**：`analyze_contact_log.py` 原不按 `car_slot` 过滤，把对手车卡栏误当本车撞栏（曾误判 car_1 撞栏 44–76s，实为对手 car_5）。已修加 `--car-slot`（默认 car_1）。**多车 contact 分析必须按目标车位过滤**；评估 car_1 就看 `--car-slot car_1`，复查绿车就看 `--car-slot car_3`。

> 注：上面这套是 day 分支的新增层；下面 R049/R052 的入弯门控/单车完赛口径仍是底座，未改。

转弯半径/入弯时机问题已**系统性解决并实跑确认**，速度也大幅提上来了。`submissions/no_other_cars/team_controller.py` 现在是 **no_other_cars = R049 驾驶底座 + 多车增量全关**（按当前代码重建，MD5 会与旧快照不同），快照见 `baselines/R049_turn_in_speed_best_2026-06-13/`。
R049 实跑证明了这套驾驶底座转弯不撞、速度明显提升（mean 速度 0.85 / median 0.90、0 lost）。当前 SDK 官方单车成绩以 R068 为准：complex `total_time=252.863s`，`best_lap=252.928s`，rank=1，0 major。

**控制器整体逻辑见 `docs/technical_manual.md`（交付版，已较稳定）。** 入弯门控的演进细节见下「核心机制」。

## 当前最好版本

- **两个 profile（2026-06-13 拆分，见 CLAUDE.md「Profile 隔离」）**：
  - `submissions/no_other_cars/team_controller.py` = `no_other_cars` = R049 驾驶底座（多车增量全关）；当前官方 complex 单车成绩是 R068：`total_time=252.863s` / `best_lap=252.928s` / 0 major。
  - `submissions/with_other_cars/team_controller.py` = `with_other_cars` = R049 + 对手避让/倒车/force_escape/光流卡死 + 收紧后的车身颜色 mask（R053–R061 自跑迭代）。
- baseline 快照：`baselines/R049_turn_in_speed_best_2026-06-13/`（含 README + 单文件）。
- 回退点：`baselines/R038_phase22_best_human_2026-06-12/`（更保守、更慢的上一代）。
- 最近全套 pytest 已通过（149 tests，见本轮前序验证）；R068 后重建两个 submission，并重跑本地/官方 validator，两个 profile 都通过。提交文件不含调试 I/O。官方 validator 仍有 W014 性能软警告。

## 核心机制（接手必读：入弯门控是这几轮的重点）

"转弯半径"由入弯门控主导，它在 `policy._target_steering` 里给远处预瞄项 `lookahead_term` 乘一个 `corner_arrival`：

1. **判据只看近处 `|lateral|` 漂移**（R042/R043）：`instant_arrival = |lateral|/arrival_ref`。直道接近段 lateral≈0 → 远处项被压到≈0 → 不提前切内；车沿线开到弯口、真正偏离时 lateral 才长起来 → 再转（out-in-out）。**不用 heading/curve_risk 当判据**——它们在接近段就大、会让门提前开（早切内）；弯急缓在入弯瞬间也无法从未发育的视野里判别（R046 删掉了按 curve_risk 调制的尝试）。
2. **速度耦合**（R047）：`arrival_ref = turn_in_lateral_ref×(1−turn_in_speed_comp×speed_norm)`。过弯越快半径越大，高速早开门补偿。
3. **latch 保持 + 出弯迟滞**（R048）：门是连续乘子，但 lateral 在弯中会反复回落→门收掉远处项→"转一半收轮、转不到位"。所以 hard_turn 里把 `_TURN_IN_LATCH` ratchet 到峰值并保持（弯中持续转）、出弯按 `turn_in_hold_decay` 迟滞收门。
- 旋钮：`turn_in_lateral_ref 0.75`（小=早转/半径小）、`turn_in_speed_comp 0.6`、`turn_in_hold_decay 0.92`。
- 配套（弯中走线）：白线后置修正 `inside_assist_*`/`hold_*`、弯中减预瞄 `corner_relief_*`（只动最终舵角/远处项，不污染 risk/速度）。

速度：R047/R049 把 mean 速度从 0.62 提到 0.85。关键 `min_confidence_factor 0.95`（解耦感知置信压速）、`curve_power 1.5`（提中等弯、急弯=物理上限不变）、`hard_turn_speed 0.72`、`max_speed_increase_per_sec 5.0`。

## 调试基建（重要，接手会用到）

- **撞栏接触日志**（让 AI 离线就能"看见撞栏"）：SDK supervisor（`pkudsa.airacer/sdk/webots/controllers/supervisor/supervisor.py`，env 开关 `AIRACER_CONTACT_LOG=1`，**未提交在 SDK 仓库工作树**）。`scripts/webots_run.sh` 默认开 → `.tmp/run/contact_<world>.jsonl`。看：`scripts/analyze_contact_log.py`。判读：峰值点数≥3 且 `zmax>0.6` = 真撞栏；孤立 1-2 点 / `zmax≈0.49` = 发车点底盘伪接触。
- 离线复盘流程 `docs/ai_offline_review.md`；人工实跑 `docs/human_webots_testing.md`；脚本速查 `scripts/README.md`。

## 已知残留 / 下一步（给接手的 AI）

1. ~~**多车避让 car_1 被夹**~~ ✅ R055 早避让基本解决：car_1 绕开 CP3 对手堆、不再被夹。
2. ~~**绿车弯中贴边卡死**~~ ✅ R061 3 车复测覆盖 `t=120–145`：oppB 无持续近停，末段高速行驶。
3. ~~**6 车长跑需回归**~~ ✅ R063/R065 已跑完整 6 车 complex，官方 `metadata.final_rankings` 非空，ours rank=2，0 major。
4. **起步格挤压 + 个别轻触可再收**：R061 `car_3` 只剩短静态接触（峰值 z≈0.50/0.46），但 6 车起步格仍可能拥挤。可试更平滑绕行 / 按可用余量约束避让强度。
5. **不对称占位仍只是第一版**：`obstacle_x/obstacle_size` 已打通，policy 已区分正前挡车与偏侧车辆；但还没有基于车位/比赛阶段/相对速度的主动防守线选择。现在的目标仍偏安全绕行。
6. **性能**：frame_motion 和颜色 mask 有每帧开销，官方 validator p95 仍超过 20ms（W014 软警告，未阻塞）。线上若严格计时需 profile `perception.py/opponent.py`。
7. **个别中等弯偏宽/偏内** + **继续提速**：单车底座的老问题（见 notes.md R049），未动。

## 工作约定（经验，不限制"改哪里"）

**想改哪里改哪里、放手大改**——任意模块（含 basic）、参数、脚本、SDK 调试层都可自由改，没有"先获人工验收才能动手"的门槛。保守微调往往没用（这几轮的教训：小步 0.2/0.3 调没用，结构性/果断的改才动得了）。

**唯一硬约束**：上传的 `submissions/no_other_cars/team_controller.py` 或 `submissions/with_other_cars/team_controller.py` 必须过 `validate_submission.py` + 官方 validator，且不含调试 I/O（`open/json/cv2.imwrite`）和禁用模块。调试构建只在 `.tmp/` 本地跑，永不上传。

经验：① 驾驶质量以 Webots 实跑为准，`lost` 率不是质量指标；② 撞栏看 `contact_*.jsonl`，别只靠肉眼盯 GUI console；③ 走线/policy/感知改动最好跑一次 Webots 再下结论，默认流程 **AI 改 → 人跑 → 人报完成 → AI 读日志**（省 token）；④ **技术手册不要每次改参数就更新**，等结构稳定、人明确要求时再改（见手册顶部维护约定）；⑤ 改 `controller/common.py` 字段要同步所有调用方/测试/文档。

## 常用命令

```bash
pytest -q
python scripts/build_submission.py --mode no_other_cars     # 单车 → submissions/no_other_cars/
python scripts/build_submission.py --mode with_other_cars   # 多车 → submissions/with_other_cars/
python scripts/validate_submission.py submissions/no_other_cars/team_controller.py
bash scripts/webots_run.sh complex              # 单车实跑（no_other_cars，默认存帧 + 撞栏接触日志）
bash scripts/webots_auto_multicar.sh complex 300 30 6   # 6 车自跑（with_other_cars）
python scripts/analyze_contact_log.py .tmp/multicar/contact_complex_car1.jsonl --car-slot car_1
python scripts/analyze_control_log.py .tmp/run/control_complex.jsonl
```

## 关键归档

- 入弯/半径根因与演进 case：`experiments/cases/R042_turn_in_too_early/`（R041 撞栏 → R049 完整对照 + 图）。
- 叙事流水账：`experiments/notes.md`（最新在上，R049 起回看入弯门控演进）；结构化台账 `experiments/runs.csv`。
- 控制器逻辑（交付版）：`docs/technical_manual.md`。
