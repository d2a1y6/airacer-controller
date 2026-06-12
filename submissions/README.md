# 提交文件区

`submissions/` 存由 `scripts/build_submission.py` 生成的单文件 controller。正常不要手工改这里；先改 `controller/`，再重新构建。

| 目录 | 用途 |
|---|---|
| `final/` | 当前准备提交/正式验证的无其他车策略。 |
| `fastest/` | 旧 fastest slot 兼容输出名；实际仍是 `no_other_cars`。 |
| `safe/` | 旧 safe slot 兼容输出名；实际仍是 `no_other_cars`。 |
| `with_other_cars/` | 预留给有其他车策略；目前未实现。 |

常用构建：

```bash
python scripts/build_submission.py --mode no_other_cars --out submissions/final/team_controller.py
python scripts/build_submission.py --mode no_other_cars --out submissions/fastest/team_controller.py  # 兼容旧输出目录
python scripts/build_submission.py --mode no_other_cars --out submissions/safe/team_controller.py     # 兼容旧输出目录
```

提交前至少跑：

```bash
python scripts/validate_submission.py submissions/final/team_controller.py
pytest -q
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

调试构建应输出到 `.tmp/run/team_controller_debug.py`，不要放进本目录。
