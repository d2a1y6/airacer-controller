# 当前状态（唯一活动交接文档）

> 新接手（人类或 AI）从这里开始读。本文只回答四件事：现在代码处于什么状态、哪些规矩不能破、
> 还有哪些没解决的问题、下一步做什么。
>
> **更新规则**：每轮工作结束时就地更新本文件（覆盖过时内容），不要再新建 `handoff_<date>.md`。
> 历史叙事查 `notes.md`（按 R-id 倒序）、`runs.csv` 和 git log。

最后更新：2026-06-11（R015/R016 取证之后；已实施线修正信任门控 + 几何脱困低速门槛，待上车验证）。

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
| **工作树（待验证）** | working-tree，未提交 | 2026-06-11 Claude 修复：白线/边界余量降级为纯诊断字段，恢复 R011 的后置有界白线舵角修正（详见下方"R013/R014 退化机制"）。保留 HEAD 的诊断字段和 hard_turn/recovering 连续帧防抖。**尚未实车验证。** |
| **HEAD**（分支 `codex/perception-dropout`，未合 main） | `66f4d8b` | R013/R014 的"白线前移到 estimator/policy + 边界余量保护"重构。**用户判定为行为退化**：basic 比 R011 慢（299s vs 259s 回到起点），complex 仍切内线贴栏撞死。 |
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
- complex 在 `x≈165,y≈119` 贴内侧栏杆撞死且无法脱困（R014，最长爬行 93.8s）。
- 已试无效：入弯时机门控（C005，部分见效但接缝处被骗开）、白线前移 + `left/right_margin` 边界保护（R013/R014，没拦住向内打轮）。
- 下一步必须取证回答：撞栏前 margin 是否已变小、`margin_risk` 是否升高、`target_steering` 为何仍指向内侧、`mode_reason` 是什么、escaping 为何没触发或无效。**不要再盲调 gain/速度。**

### P2 车没有稳定骑在白线上
- 用户在 R011/R013 都肉眼确认：即使"看见白线"（`line_offset/line_conf` 正常），车身中心也没压住白线。
- 需要用 debug 帧核对"白线检测正确 → 为什么最终 steering 没把车带上线"这条链路，逐段看 steering 分解。

### P3 无意义打轮和减速
- R013/R014 仍明显，用户特别强调。可能与 P2 同根（中心目标抖动），先取证再定。

### （已大幅缓解）直道慢 / lost 限速
- R008 已修：直道判定改看 `curvature/lookahead/lateral`、加直道记忆和 lost 直道滑行后，直道真实速度稳定 >1.5（median 6.10）。不要再用 lost 率否决这个修复。

## 证据现状

- **R014 撞栏窗口的相机帧和控制日志已被 `.tmp` 清理删除**。下一轮必须用 debug 构建重跑 complex 取证（带 `--dump-frames`，撞栏短窗口 stride 1）。
- 流程已修补：`scripts/webots_run.sh` 会自动清理孤儿进程/旧遥测并把上一轮产物轮换到 `.tmp/run.prev`，最近两轮产物不会再被立即删掉。

## R015/R016 取证结论与第二轮修复（2026-06-11，已实施待上车）

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

1. **上车复验（complex 优先）**：`bash scripts/webots_run.sh complex --frames 3`。预期：直道不再左右打轮、第一左弯正常通过不撞栏。若仍异常，优先抓 `lo/lc` 与 escape 窗口。
2. **上车复验（basic）**：`bash scripts/webots_run.sh basic`。预期：弯中抖动减少、车阵处不再朝白车打轮；对比 R011 速度（约 260s 回起点区域）。
3. complex 直道左毛刺取证：用已保留的 `frames_complex` 渲 3-5 张 overlay（t≈25.1/26.2/34.3 窗口），确认是 mask 噪声还是 checkpoint 门，再对症修感知。
4. 跑通后再做提速：定位最长低速窗口逐个对症，不做全局速度盲调（iter36 教训）。
5. 验证通过后提交，按规范记 R-id。

## 验证状态

最近一次（2026-06-11 整理后）：`pytest` 70 passed；`fastest/safe/final` 三个 submission 过 `validate_submission.py`。
