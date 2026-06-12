# 转弯半径 / 入弯时机（R041→R044，同一件事的完整演进）

- 主题：全场"转弯半径太小/切内线/撞内栏"都是同一个根因——**入弯太早**。这个 case 记录从发现根因到基本解决的整条线（R041 撞栏 → R042/R043 改门控 → R044 加"弯有多急"调制 + 回调）。
- 来源：complex，car_1。before 窗 = R041 实跑（最紧左弯 t≈230 撞栏 12 点）；after 窗 = R044 实跑同弯（`control_window_R044_best.jsonl`，line_offset 全程≈0）。
- **状态：根本性问题已解决**。R044+回调 是目前最好版本——90° 急弯不再切内、缓弯也基本骑线。剩下只是微调（见末尾），不再是根本问题。
- 对照图 `turn_in_before_after.png`：左 R041（车还居中 lat≈0 就转 → 切到 +0.65 → 撞），右 R044（等 lateral 涨起来才转 → line_offset 贴着 0 骑线）。

## 这是什么问题

全场所有"转弯半径太小/贴内栏"都是同一个机制：**车在直道接近段就开始转，物理还没到弯口就切进内侧。**

入弯门控本来想迟滞入弯：
```
corner_arrival = |lateral|/0.30 + |heading|/0.45      # “弯到了没”
turn_in_gate   = 0.55 + 0.45·corner_arrival           # 越接近 1，远处预瞄项越放开
lookahead_term *= turn_in_gate
```
但它用 `|heading|` 当"弯到了没"的判据——而 `heading` 是**远处/中场**的路弯量，在直道**接近段就涨起来**。于是 heading 一涨门就全开，车还居中、还骑在白线上就被远处预瞄项打进弯里。**这个门用"驱动入弯的信号"当"该不该入弯的判据"，等于自废、零迟滞。**

## 数据（同一弯，bug vs 修复）

| | 入弯 commit（steer<−0.10） | 那一刻 lateral | 那一刻 heading | 弯中 line_offset 峰值 | 结果 |
|---|---|---|---|---|---|
| R041（旧门控） | t=224.16 | **−0.01（还居中！）** | −0.25 | **+0.65（深切内）** | t230 撞栏 12 点 |
| R042（新门控） | t=227.14（晚 ~3s） | **−0.14（已偏入弯）** | −0.16 | **+0.23** | 无剐蹭通过 |

`control_window_R041_bug.jsonl` 看 t222.6 起：lateral/line_offset≈0、只有 heading 在涨，steering 就跟着转——这就是"太早"。
`contact_R041_crash.jsonl` 是 t230 的 12 点撞栏（zmax 0.53）。
`control_window_R042_fixed.jsonl` 是修复后同一弯：入弯晚了、commit 时 lateral 已经长起来（车真到弯口了）、切内深度减半。

## 修复（R042，仅 complex）

`policy._target_steering` 的 arrival 改为主要看近处 `|lateral|` 漂移（直道≈0，开到弯口真正偏离才长起来），heading 几乎退出（`turn_in_heading_ref` 6.0）。R043 按用户要求删除 `turn_in_floor`，远处预瞄项直接乘 `corner_arrival`。车先沿线开进弯口、略外移，外移把 lateral 顶起来后再"晚而狠"地转（out-in-out）。
**不要用 `|line_offset|` 当 arrival**：它分不清"外移到弯口"和"已经切到内侧"，后者会把门开更大、越切越深（实测会让 R039 回中测试反号）。
basic 经 `BASIC_CONTROL_OVERRIDES` 保留旧门控（R037 已确认良好、未在新门控下实测）。

## 对照图

`turn_in_before_after.png`：同一最紧左弯，左 = R041 旧门控（撞栏 12 点），右 = R042-b（`turn_in_floor=0.11`，轻擦 7 点）。看上图 turn-in commit 紫线那一刻 `lateral`：旧门控≈0（车还居中就转），新门控已明显非 0（车真到弯口才转）；下图 `line_offset` 峰值从冲破 0.35 内切阈值降到贴着阈值。

## 演进 R042 → R043 → R044（门控逐步收敛）

- **R042**：arrival 改用近处 `|lateral|`、heading 几乎退出、加 `turn_in_floor` 迟滞。最紧弯从撞栏变通过但仍 close。
- **R043**（用户）：删除 `turn_in_floor`，直接 `lookahead_term *= corner_arrival`；`turn_in_lateral_ref` 调到 1。急弯（90°）半径已基本不用再改。
- **R044**（"弯有多急"调制，**后被 R046 删除**）：曾想按 `curve_risk` 给缓弯更多迟滞。**移除 `turn_in_heading_ref`**（heading 退出 arrival）保留至今。
- **R046**（删除 R044 调制）：实测发现该调制有**原理性缺陷**——入弯初期 `curve_risk` 还低（远处弯量没在视野发育），所有弯都被判成缓弯、`arrival_ref` 被放大 1.4-1.97×、过度迟滞；等 `curve_risk` 涨上来车已深入弯里才急打轮，**半径反而很大、冲到外侧（line_offset≈−0.5）、掉速**。入弯瞬间无信号能区分缓/急弯，故删。回到纯 `lateral` 门控：`corner_arrival = clamp(|lateral|/turn_in_lateral_ref, 0, 1)`，`turn_in_lateral_ref` 为唯一旋钮。

### 急弯 vs 缓弯证据（R043 实跑，按弯分类）

| 弯类型 | peak \|lookahead\|（急缓） | peak line_offset（切内深度） |
|---|---|---|
| **急弯** 90°（t31/t247/t345…） | 0.7–0.9 | **+0.00**（不切内，已修好） |
| **缓弯**（t139/t297-323…） | 0.4–0.55 | **+0.27 ~ +0.41**（仍偏内） |

`gentle_corner_t300.png` 是一个缓弯帧的感知 overlay。注意：缓弯段 `left_margin≈right_margin≈0.34`、contact 日志无撞栏——缓弯是"半径偏小/略偏"而非贴栏，所以观感上"还有点小"但不危险。真正还在轻擦的是**中等急度**弯（peak\|look\|≈0.6，contact 峰值 3、`zmax≈0.48`，已远轻于 R041 的 z0.90）。

## 现状与微调（已不是根本问题）

- **R044 实跑**：半径整体不错。`turn_in_gentle_extra=1.5` 略过头——急弯偶有外偏（line_offset 偶到 −0.79）、缓弯 line_offset 中位翻负（−0.07，略偏外）。→ **回调** `turn_in_lateral_ref 1.0→0.9`、`turn_in_gentle_extra 1.5→1.0`（待复跑确认）。
- **唯一新问题**：R044 末段蹭到右侧**静止黑车**——这是"半径略大"的副作用，不是切内。**当前完全没有"避让其他车"逻辑**，后续单独叠加；现在不必为它改半径。
- 调参旋钮：缓弯偏内→调大 `turn_in_gentle_extra`；偏外→调小它；急弯偏外→调小 `turn_in_lateral_ref` 或调大 `turn_in_sharp_ref`。
- 裁剪窗口：`control_window_R041_bug.jsonl`（before 撞栏）、`control_window_R044_best.jsonl`（after 骑线）；中间过程 `control_window_R042*.jsonl`；缓弯感知帧 `gentle_corner_t300.png`。
