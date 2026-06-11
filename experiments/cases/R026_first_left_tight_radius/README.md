# R026 first left tight radius

- 状态：**未完成 / open**。这是回归 case，不要在没有新一轮 Webots complex 实跑前标记完成。
- 来源：R026，world=complex，car_1，practice，调试构建；记录来自 `.tmp/run/control_complex.jsonl` 和 SDK `.local/recordings/telemetry.jsonl`。
- 时间窗：`t=29.0→48.0`，第一个左转入口到爬行段结束。
- 现象：车在第一个左转半径过小，切到内侧后进入约 `14.1s` 的低速爬行；telemetry 最长爬行段为 `t=33.8→47.8`，位置约 `x=188.6,y=-27.1 → x=188.9,y=-26.9`。
- 保存内容：
  - `control_window.jsonl`：`t=29→48` 的控制日志窗口。
  - `telemetry_window.jsonl`：同时间窗 telemetry。
  - `overlay_000031_360.png`：入弯主问题帧。
  - `overlay_000033_920.png`：进入爬行段附近。
  - `overlay_000047_680.png`：爬行段尾部。

## 关键判断

- `lost` 已大幅下降：整场控制日志 `lost=19/2925≈1%`，说明 Phase 1 起步和道路 mask 稳定性有明显改善。
- 问题不是永久丢线，而是**第一个左转入口线信号不连续**：`t=29.37/29.79` 附近短暂出现 `line_offset≈+0.44~0.46`，但到 `t≈31.36` 主转向发生时，原控制日志又回到 `line_conf=0`。
- `t≈31.36` 时 `lateral≈-0.04`，车在 road-mask 口径里几乎居中；但 `heading≈-0.56`、`lookahead≈-0.37`、`target_steering≈-0.42`，策略按远处左弯预判提前左打，导致切入半径过小。
- 从保存帧用当前代码回放，`t=31.36` 已可得到 `line_offset≈+0.43, line_heading≈-0.54, line_conf≈0.8`。这支持 Phase 2 的修法：更密扫描先找回弯中虚线，再放宽 `0.30→0.55` 的白线信任门，让车用这条真实 off-center 白线回中。

## 结论

这个 case 记录的是“左转半径过小 / 提前切内线”的最小复现窗口。根因链条是：弯道虚线稀疏，旧扫描行在关键帧漏掉白线；没有白线目标时，road-mask 的远处弯道预判在车仍接近居中时提前给大左舵；车切到内侧后进入长时间低速爬行。

## 后续回归

- R027 复跑补充：Phase 2 后第一个左弯仍撞/擦左边，但不再长时间卡死。白线已大量召回，问题变成 `line_heading` / road heading 强左压过 `line_offset` 回中；同时 `line_offset≈0.62-0.71` 的真实弯中白线被旧 `0.55` 门拒掉。当前 Phase 2.1 候选已改为 offset 优先融合，并把信任门放到 `0.75`。本 case 仍 open。
- R028 AI 自主短测补充：Phase 2.1 候选只跑到当前问题窗口之后，`t≈64.6s` 主动停止。第一个左弯没有复现 `14.1s` 长爬行，也没有 telemetry 事件，`t≈42` 已回到直道中央；残留是 `t≈32→35` 的短暂低速硬左瞬态。由于这不是完整场，也没有人眼终判，本 case 仍 open。
- 请人用当前 Phase 2.1 候选重新跑 `bash scripts/webots_run.sh complex`。
- 通过标准：
  - 第一个左转不再出现 `t≈33.8→47.8` 这种长爬行。
  - `t≈31` 左右的弯中线信号能稳定进入控制链路，不能只在一两帧闪现。
  - 没有重新锁到白色护栏或路肩。
- 未通过时优先继续查白线扫描密度、单目召回和弯中门控；不要先加 escape。
