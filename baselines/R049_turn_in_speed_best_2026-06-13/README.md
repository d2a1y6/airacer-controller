# R049 — 入弯门控重做 + 提速后的当前最佳 (2026-06-13)

- **MD5**：`79ffbdbfe1259cc41824123e296bd49b`（= 当时的 `submissions/final/team_controller.py`）。
- **来源**：用户人工 Webots 实跑确认为当前最好版本（complex, car_1）。
- **实跑结论**：转弯不再撞栏；全程速度明显更快；末段会蹭一次右侧静止黑车（无避让逻辑，已知、非半径问题）。
- **离线指标（该 run）**：mean 速度 0.85 / median 0.90、0 lost；contact 日志 7 个 episode 全是峰值 3 点、`zmax`≤0.50 的轻擦（无 `zmax>0.6` 硬撞）。

## 这版相对之前的关键改动（入弯门控的完整演进）

转弯半径/入弯时机经过 R041→R049 一连串改动，核心是把入弯门控做对：

- **R042/R043**：入弯门控 `corner_arrival` 改为只看近处 `|lateral|` 漂移（不再用 `heading` 当"弯到没"的判据），删掉 floor，直接 `lookahead_term *= corner_arrival`。修好了系统性"入弯太早→切内线/撞内栏"。
- **R046**：删除 R044 试过的"按 curve_risk 调制"（入弯瞬间分不清缓/急弯，原理上修不好）。
- **R047**：入弯参考随速度收小 `arrival_ref = turn_in_lateral_ref×(1−turn_in_speed_comp×speed_norm)`（过弯快→半径大，高速早开门补偿）；放松高速收舵 `steering_speed_cap_scale`。
- **R048**：入弯门控加 latch——hard_turn 里 ratchet 保持峰值（弯中 `lateral` 回落不收门→不再"转一半收轮"）、出弯按 `turn_in_hold_decay` 迟滞收门。
- **R049**：定向提速——`curve_power`↑（提中等弯、急弯=物理上限不变）、`hard_turn_speed`↑、`min_confidence_factor`↑（解耦感知置信压速）、`max_speed_increase`↑。

参数全部在 `controller/params.py` 的 `CONTROL`（turn_in_* / 速度因子）。基建：SDK supervisor 的结构化撞栏接触日志（`contact_*.jsonl`）。

## 适用范围 / 为什么保留

- 当前唯一"半径稳 + 速度快 + 不硬撞"的实跑确认版本，作为后续提速/避让的回退点。
- 已知残留：① 个别中等弯偏宽/偏内（感知 curve_risk 不一致所致，见 notes.md R049）；② 末段蹭静止黑车（需要单独加"避让其他车"逻辑）。
