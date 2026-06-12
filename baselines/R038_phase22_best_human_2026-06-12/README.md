# R038 Phase 2.2 best human baseline

- 来源：commit `ab58b745b48a3cdac2c6c71371c8420823ca4ca4`，分支 `codex/perception-dropout`。
- 文件：`team_controller.py` 直接复制自 `submissions/final/team_controller.py`。
- MD5：`f4b79c09f6811580817ecfe04d1fb11a`。
- SHA256：`7c1ab7106c83781f7f7b4a9487ca831ba0c7721f4a305c12aab58c50e544ce79`。

## 结论

这是 2026-06-12 人工 Webots 复跑确认的当前最佳版本。相比 R026/R027，它已经消除了大多数内侧剐蹭和卡死；人工观察为：绝大多数弯不再剐蹭，但转弯半径仍偏小，弯中偶尔丢线，车身会落到白线内侧；R038 仍有碰栏/轻蹭，但能自行擦出，没有卡住。

这不是完成版。它是后续继续调“弯中保持白线居中/增大有效转弯半径”的回退基线。

## 配套记录

- 实跑记录：`experiments/notes.md` 的 R038。
- 结构化台账：`experiments/runs.csv` 的 R038。
- 报告图：`experiments/figures/R038_best_human_residual_tight_radius/`。
- open case：`experiments/cases/R038_residual_tight_radius/`。
