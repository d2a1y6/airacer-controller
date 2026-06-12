# 测试索引

`tests/` 覆盖接口契约、构建脚本、感知/估计/policy 关键行为、诊断脚本和提交文件静态规则。

常用命令：

```bash
pytest -q
pytest tests/test_lane_line_follow.py
pytest tests/test_policy.py::test_name
```

大致分组：

| 测试文件 | 覆盖内容 |
|---|---|
| `test_contracts.py`、`test_interface.py`、`test_output_range.py` | `control()` 接口、输出范围、基础契约 |
| `test_submission_static.py`、`test_build_submission_debug.py` | 单文件构建、禁用 import/内置、debug 构建 |
| `test_perception_dropout.py`、`test_lane_line_follow.py` | 道路/白线感知和丢线相关行为 |
| `test_estimator.py`、`test_policy.py`、`test_turn_in_gate.py`、`test_straight_speed.py` | 几何估计、控制策略、入弯/直道行为 |
| `test_pinned_escape.py`、`test_opponent.py` | 脱困和近车检测 |
| `test_analyze_*.py`、`test_plot_run.py`、`test_replay_offline.py`、`test_make_teleport_world.py` | 诊断脚本、可视化、开环回放、跳点 world |

新增控制行为时，优先给对应模块加窄测试；跨模块行为或真实 run 机制再写入 `experiments/`。
