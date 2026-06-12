# 当前状态（接手从这里开始）

最后更新：2026-06-13（R052 6 车 complex 多圈完赛成功）。当前分支：`multi-car`。

## 一句话结论

**多车极端场景鲁棒性已验证通过**：6 车 complex 赛道中 car_1 成功完赛 3-4 圈，仅在 CP3 拥堵处短暂卡死~2s 后被脱困策略自救恢复。R049 单车完赛能力 + 多车安全策略已就绪。

转弯半径/入弯时机问题已**系统性解决并实跑确认**，速度也大幅提上来了。当前 `submissions/final/team_controller.py`（MD5 `79ffbdbfe1259cc41824123e296bd49b`）= **R049 当前最佳**，已存快照 `baselines/R049_turn_in_speed_best_2026-06-13/`。
实跑：转弯不撞、全程明显更快（mean 速度 0.85 / median 0.90、0 lost）、contact 日志无硬撞（全是轻擦）。

**控制器整体逻辑见 `docs/technical_manual.md`（交付版，已较稳定）。** 入弯门控的演进细节见下「核心机制」。

## 当前最好版本

- 提交文件：`submissions/final/team_controller.py`（R049，MD5 `79ffbdbfe1259cc41824123e296bd49b`）。统一策略：`fastest/safe/basic` 不再分叉，`get_profile` 只返回 `CONTROL`。
- baseline 快照：`baselines/R049_turn_in_speed_best_2026-06-13/`（含 README + 单文件）。
- 回退点：`baselines/R038_phase22_best_human_2026-06-12/`（更保守、更慢的上一代）。
- 全套测试 + 本地/官方 validator 通过；提交文件不含调试 I/O。

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

1. ~~**多车极端场景实跑验证**~~ ✅ R052 已完成：6 车 complex 中 car_1 成功完赛 3-4 圈，CP3 卡死~2s 后被脱困自救。策略验证通过。
2. **避让其他车（可进一步增强）**：已有对手降速(0.72) + 弯道叠加减速(0.55) + 主动避让转向 + 脱困链。但仍是反应式而非规划层，检测也只覆盖前下方 ROI。
3. **个别中等弯偏宽/偏内**：感知一致性问题（见 notes.md R049）。
4. **继续提速**：急弯已接近物理上限，空间在改善感知一致性 + 更好的走线。

## 工作约定（经验，不限制"改哪里"）

**想改哪里改哪里、放手大改**——任意模块（含 basic）、参数、脚本、SDK 调试层都可自由改，没有"先获人工验收才能动手"的门槛。保守微调往往没用（这几轮的教训：小步 0.2/0.3 调没用，结构性/果断的改才动得了）。

**唯一硬约束**：上传的 `submissions/final/team_controller.py` 必须过 `validate_submission.py` + 官方 validator，且不含调试 I/O（`open/json/cv2.imwrite`）和禁用模块。调试构建只在 `.tmp/` 本地跑，永不上传。

经验：① 驾驶质量以 Webots 实跑为准，`lost` 率不是质量指标；② 撞栏看 `contact_*.jsonl`，别只靠肉眼盯 GUI console；③ 走线/policy/感知改动最好跑一次 Webots 再下结论，默认流程 **AI 改 → 人跑 → 人报完成 → AI 读日志**（省 token）；④ **技术手册不要每次改参数就更新**，等结构稳定、人明确要求时再改（见手册顶部维护约定）；⑤ 改 `controller/common.py` 字段要同步所有调用方/测试/文档。

## 常用命令

```bash
pytest -q
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/validate_submission.py submissions/final/team_controller.py
bash scripts/webots_run.sh complex          # 实跑（默认存帧 + 撞栏接触日志）
python scripts/analyze_contact_log.py .tmp/run/contact_complex.jsonl
python scripts/analyze_control_log.py .tmp/run/control_complex.jsonl
```

## 关键归档

- 入弯/半径根因与演进 case：`experiments/cases/R042_turn_in_too_early/`（R041 撞栏 → R049 完整对照 + 图）。
- 叙事流水账：`experiments/notes.md`（最新在上，R049 起回看入弯门控演进）；结构化台账 `experiments/runs.csv`。
- 控制器逻辑（交付版）：`docs/technical_manual.md`。
