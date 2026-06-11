# R011 白线位置优先修正版（basic 实车最佳）

- 来源 commit：`16ae3f3`（checkpoint: stabilize line following baseline）。文件由
  `git show 16ae3f3:submissions/final/team_controller.py` 提取，对应 R011/R012 实跑用的
  "白线后置位置优先修正 + 近车检测"版本，即后续 R013/R014 白线前移重构之前的状态。
- 证据（见 `experiments/notes.md` R011/R012、`runs.csv`）：
  - **R011 basic**：手动中止于 `t≈259.84s` 仍正常行驶；速度 mean=5.469、median=6.090；
    末段静态车阵不再撞 car5，车速保持 ≈6.10 m/s。用户后续确认 R013（重构版）比它明显变慢，
    因此本版是 basic 的速度参照基线。
  - **R012 complex**：通过原第一左弯卡点 `x≈183,y≈-27`，但 `t≈360.7s` 后在 `x≈-10,y≈-27` 近停，
    未完整跑通。
- 残留问题：用户肉眼仍指出若干路段车身没有完全骑在白线上；complex 后段近停未解决。
- 用途：与 HEAD 重构版做 A/B 对比（先确认 R013 的变慢确实来自重构），以及 basic 回归的速度参照。
