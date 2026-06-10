# 离线存帧与开环回放

这套工具只服务丢线诊断，不用于评估圈速。

## 存帧

调试构建可以同时写控制日志和保存左右相机原始 BGR 帧：

```bash
python scripts/build_submission.py --mode fastest \
  --debug-log .tmp/run/control_basic.jsonl \
  --dump-frames .tmp/run/frames_basic \
  --dump-frame-stride 1 \
  --out .tmp/run/team_controller_debug.py
```

`--dump-frames` 只注入本地调试单文件。正常构建不包含 `open`、`np.save` 或存帧变量，不能把调试单文件上传平台。

## 回放

已有帧后，可以离线重跑同一段画面：

```bash
python scripts/replay_offline.py .tmp/run/frames_basic \
  --out .tmp/run/replay_basic.jsonl

python scripts/analyze_control_log.py .tmp/run/replay_basic.jsonl
```

回放脚本会在开始前调用 `reset_estimator_state()` 和 `reset_policy_state()`，再按
`extract_observation → estimate_track → decide_control → clamp_cmd` 接线逐帧输出 JSONL。
输出字段和 `--debug-log` 控制日志一致，可以直接交给 `analyze_control_log.py`。

## 限制

这是开环固定输入帧回放。它适合比较同一段录制画面下，感知或估计改动对 `lost`、`track_conf`、
`obs_conf`、`obs_points`、`road_width` 和 `debug_flags` 的影响。

它不能评估速度、转向策略、圈速或是否会跑完赛道。真实 Webots 中，控制输出会改变车的位置和后续画面；
开环回放的后续画面已经固定，无法体现这种轨迹反馈。
