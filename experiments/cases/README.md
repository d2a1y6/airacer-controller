# 关键失败窗口归档规则

`experiments/cases/` 只保存会反复用于回归、交接或解释机制的小型失败窗口。它不是录像库，也不是 `.tmp` 的替代品。

## 什么时候建 case

满足至少一条才建：

- 同一失败反复出现，需要后续版本做回归。
- 单靠 `experiments/notes.md` 难以解释，需要保留少量画面证据。
- 失败窗口揭示了清楚机制，例如“白线识别正确但 policy 继续向内打轮”。
- 用户明确指出某个画面/时间窗是关键问题。

普通一次性调参、整场录像、批量 overlay 不建 case。

## 目录命名

```text
experiments/cases/R014_inner_rail_stuck/
```

格式：`R-id` + 简短英文 slug。一个 case 只对应一个问题窗口。

## 允许保存的内容

每个 case 最多保存：

| 文件 | 内容 |
|---|---|
| `README.md` | 问题描述、来源 run、时间窗、观察结论、如何复现或对照。必需。 |
| `control_window.jsonl` | 裁剪后的控制日志窗口，通常几十到几百行。 |
| `telemetry_window.jsonl` | 裁剪后的 telemetry 窗口，通常几十到几百行。 |
| `overlay_*.png` | 1-3 张关键 overlay：进入异常、异常中、异常后。 |
| `notes.txt` | 可选，放临时脚本输出摘要；优先写进 README。 |

## 禁止保存的内容

- 整场 `.npy` 左右相机帧。
- 整场 Webots 录像或整场 telemetry 复制件。
- 批量 overlay 截图。
- debug controller 单文件。
- SDK 临时克隆。
- cache、`.DS_Store`、`__pycache__`。
- 单个大文件。原则上一个 case 目录应保持在几 MB 内。

## README 模板

```markdown
# R014 inner rail stuck

- 来源：R014，world=complex，car_1，commit/working-tree 描述。
- 时间窗：t=121.1→214.9。
- 现象：车贴内侧栏杆卡住，无法脱困。
- 关键判断：
  - line_conf 是否可信：
  - left/right_margin 是否提前变小：
  - target_steering 与最终 steering 是否仍向内：
  - mode_reason / escaping 是否触发：
- 结论：
- 后续回归：
```

## 处理流程

1. 在 `.tmp` 里完成整场摘要复盘，并挑关键窗口逐帧取证。
2. 只裁剪最小窗口和少量 overlay。
3. 写 case README。
4. 把整场原始产物从 `.tmp` 删除。
