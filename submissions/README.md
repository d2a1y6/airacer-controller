# 提交文件区

`submissions/` 存由 `scripts/build_submission.py` 生成的单文件 controller。正常不要手工改这里；先改 `controller/`，再重新构建。

| 目录 | 用途 |
|---|---|
| `final/` | 当前准备提交/正式验证的版本。 |
| `fastest/` | fastest slot 版本。 |
| `safe/` | safe slot 版本。当前参数通常和 fastest 相同，除非明确分流。 |

常用构建：

```bash
python scripts/build_submission.py --mode fastest --out submissions/final/team_controller.py
python scripts/build_submission.py --mode fastest --out submissions/fastest/team_controller.py
python scripts/build_submission.py --mode safe --out submissions/safe/team_controller.py
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
