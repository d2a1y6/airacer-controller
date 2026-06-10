# Webots Basic Physical Finish Baseline

这套 baseline 保存了 2026-06-10 在官方 Webots `basic` 赛道上物理跑完一圈的策略。

## 存储设计

- `team_controller.py`：策略本身的单文件快照，可直接上传或用官方 SDK 复跑。
- `params.json`：视觉、估计器和控制策略参数快照，方便后续调参时对比。
- 当前 git commit：仍是最权威的源码快照，包含模块化源码、测试、提交文件和实验记录。

也就是说，策略本身可以存。最稳妥的方式是同时存两层：

1. Git commit 保存模块化源码和历史。
2. Baseline 目录保存可直接复跑的单文件控制器和参数摘要。

## 实测证据

- 控制器：非 debug 单文件 `.tmp/run/team_controller.py`，内容和本目录 `team_controller.py` 一致。
- 赛道：`track_basic.wbt`
- 结果：telemetry 显示 `t=288.187s` 从左侧穿过起点区域 `x=-19.498,y=122.6`。
- 300 秒结束位置：`x=-19.741,y=155.472`。
- 重大碰撞：0。

本地 metadata 仍显示 `timeout/laps=0`。原因是当前官方 SDK supervisor 的 checkpoint 坐标和 `track_basic.wbt` 实际赛道坐标不一致，所以这里以 telemetry 穿过起点区域作为跑完一圈的证据。

## 快照校验

`team_controller.py` sha256：

```text
0c7c74b0c390ceadbe2938c2c475308f9441048c8252c57ea1bcd5d97688b0d7
```

## 复跑方式

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/make_local_config.py \
  --code-path baselines/webots_basic_physical_finish_2026-06-10/team_controller.py \
  --team-id baseline --car-slot car_1 --world basic \
  --race-id baseline_basic --session-type qualifying --total-laps 1 \
  --recording-path .tmp/run/recordings_baseline_basic \
  --out .tmp/run/race_config_baseline_basic.json --force

RACE_CONFIG_PATH=/Users/day/Desktop/Github/airacer-controller/.tmp/run/race_config_baseline_basic.json \
  /Applications/Webots.app/Contents/MacOS/webots --mode=fast --minimize \
  /Users/day/Desktop/Github/pkudsa.airacer/sdk/webots/worlds/track_basic.wbt
```
