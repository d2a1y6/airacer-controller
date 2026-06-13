# 控制器源码索引

`controller/` 是手写算法源码。正常只改这里，然后用 `scripts/build_submission.py` 生成 `submissions/` 下的单文件。

主流水线：

```text
left_img/right_img
→ perception.extract_observation()
→ estimator.estimate_track()
→ policy.decide_control()
→ clamp_cmd()
→ steering/speed
```

| 文件 | 职责 |
|---|---|
| `common.py` | 模块间数据结构和限幅工具。字段名是契约，改字段要同步所有调用方和测试。 |
| `params.py` | 参数唯一来源。调参优先放这里，不在算法模块里硬编码。 |
| `perception.py` | 图像处理：道路 mask、白线、近障碍/对手方向的感知输入。不能直接算控制量。 |
| `estimator.py` | 从感知结果估计道路几何、白线状态、模式需要的状态。不能接触原图。 |
| `policy.py` | 根据 `TrackState` 输出转向和速度。不能处理原图。 |
| `opponent.py` | 近处车辆检测，输出是否有车、左右位置和近似尺寸。当前由 profile 开关控制。 |
| `team_controller_local.py` | `control()` 接线、异常兜底、最终限幅。 |

改控制行为前先读根目录 `CLAUDE.md` 和 `experiments/STATUS.md`。改完通常要跑：

```bash
python scripts/build_submission.py --mode no_other_cars --out submissions/no_other_cars/team_controller.py
python scripts/validate_submission.py submissions/no_other_cars/team_controller.py
pytest -q
```
