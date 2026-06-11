# 当前状态（唯一活动交接文档）

> 新接手（人类或 AI）从这里开始读。本文只回答四件事：现在代码处于什么状态、哪些规矩不能破、
> 还有哪些没解决的问题、下一步做什么。
>
> **更新规则**：每轮工作结束时就地更新本文件（覆盖过时内容），不要再新建 `handoff_<date>.md`。
> 历史叙事查 `notes.md`（按 R-id 倒序）、`runs.csv` 和 git log。

最后更新：2026-06-11（R023 后补充调试能力；complex 旧 `x≈169,y≈111` 卡点已通过，basic 短跑回归正常；整条 complex 仍未证明跑通）。

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
| **工作树（候选，未完成）** | working-tree，未提交 | 控制策略等同 HEAD；本轮只补 Webots controller console 捕获和限时存帧调试开关。**整条 complex 仍未证明跑通。** |
| **HEAD**（分支 `codex/perception-dropout`，已推） | `06a915f` | R021 真实采样色卡、R022/R023 半径和 escape 分离修复已提交。旧 `x≈169,y≈111` 卡点通过，basic 短跑正常；整条 complex 仍未证明跑通。 |
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

## 未解问题（用户视角，按优先级）

> 2026-06-11 更新：下面 P1–P3 在 R013/R014 上的恶化部分已有候选修复（见"R013/R014 退化机制"），
> 但 R011/R012 时代就存在的残留（骑线精度、complex 两处低速窗口）仍需取证后对症修。

### P1 转弯半径太小 / 切内线贴内侧栏杆
- R014/R021 的典型表现是入弯半径太小，切到内圈栏杆后长时间爬行。R022 用 notes 里历史有效方向修：降低远处前瞻和急弯舵角、加强速度相关收舵、让弯道更慢一点；旧 `x≈169,y≈111` 卡点已通过。
- 当前不能写成彻底解决：R022 只跑到 `t≈197.6s` 控制日志，telemetry 证据到 `t≈177.4s`，还没覆盖整条 complex 后半程。
- 已明确不要重开普通 margin guard：R014 证明它会受 road-mask 噪声影响。边界余量只用于 escape 中的贴边方向判断。

### P2 车没有稳定骑在白线上
- 用户在 R011/R013 都肉眼确认：即使"看见白线"（`line_offset/line_conf` 正常），车身中心也没压住白线。
- 需要用 debug 帧核对"白线检测正确 → 为什么最终 steering 没把车带上线"这条链路，逐段看 steering 分解。

### P3 无意义打轮和减速
- R013/R014 仍明显，用户特别强调。可能与 P2 同根（中心目标抖动），先取证再定。

### （已大幅缓解）直道慢 / lost 限速
- R008 已修：直道判定改看 `curvature/lookahead/lateral`、加直道记忆和 lost 直道滑行后，直道真实速度稳定 >1.5（median 6.10）。不要再用 lost 率否决这个修复。

## 证据现状

- R021 颜色采样证据保留在 `.tmp/color_sample/color_samples.json` 和 `.tmp/run.prev/perception_*` 小文件中；抽稀 `.npy` 帧已删除。
- R022/R023 控制日志保留在 `.tmp/run.prev/control_complex.jsonl` 和 `.tmp/run/control_basic.jsonl`；后续 static-car 窗口帧在 `.tmp/run.prev/frames_complex/`，`.tmp` 约 436MB，清理前先确认是否还要复盘 `t≈410-430s`。
- 流程已修补：`scripts/webots_run.sh` 会自动清理孤儿进程/旧遥测并把上一轮产物轮换到 `.tmp/run.prev`，最近两轮产物不会再被立即删掉。
- Console 捕获结论：默认 `run_local > file 2>&1` 抓不到 Webots GUI/controller 面板里的学生控制器输出；debug 构建现按 `AIRACER_CONTROLLER_CONSOLE_LOG_DIR` 把 controller 进程的 stdout/stderr tee 到 `.tmp/run/webots_console/*.log`。实时读用 `tail -f .tmp/run/webots_console/*.log`，跑完也能直接读。

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

1. 继续跑 `bash scripts/webots_run.sh complex` 到更后段，确认 R022 之后是否还有新的内切/近停窗口；不要把“过旧卡点”误写成整条跑通。
2. 若后段再出现贴边，先截短窗口帧和控制日志，确认 margin、白线、目标舵角和 escape 方向，再改代码。
3. 保持当前采样色卡和保守 road mask；不要为了降低卡点把 road 重新放宽到栏杆/路外地面。
4. complex 新窗口修完后继续跑 basic 回归，确认同一策略没有破坏 R023 的短跑状态。
5. 跑通后再做提速和提交；不要把当前候选当作完成态。

## 验证状态

最近一次（2026-06-11 R023 后）：`pytest` 94 passed；`scripts/validate_submission.py submissions/final/team_controller.py` 通过；官方 `validate_controller.py` 和 `run_local.py --validate-only` 通过，但仍有性能 warning（本轮 p95 波动到 84-103ms，软上限 20ms）。`submissions/final/team_controller.py` 低于 100KB。
