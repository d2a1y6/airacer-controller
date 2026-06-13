# 提交文件区

`submissions/` 存由 `scripts/build_submission.py` 生成的单文件 controller。正常不要手工改这里；先改 `controller/`，再重新构建。

赛事有两类场次，对应两个控制策略 profile（见 `controller/params.py` 与 CLAUDE.md「Profile 隔离」）：

| 目录 | profile | 用途 |
|---|---|---|
| `final/` | `no_other_cars` | 单车场次（计时赛）。= R049 单车最佳，无对手避让/倒车/光流卡死。 |
| `with_other_cars/` | `with_other_cars` | 多车场次。在 R049 驾驶之上加对手避让、倒车脱困、force_escape、光流卡死检测。 |

构建（`--mode` 决定 profile + 默认输出路径，并把 `PROFILE` 注入提交文件）：

```bash
python scripts/build_submission.py --mode no_other_cars     # → submissions/final/
python scripts/build_submission.py --mode with_other_cars   # → submissions/with_other_cars/
```

提交前对要上传的那份至少跑：

```bash
python scripts/validate_submission.py submissions/final/team_controller.py
pytest -q
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/final/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

（多车场次把上面路径换成 `submissions/with_other_cars/team_controller.py`。）

调试构建应输出到 `.tmp/`，不要放进本目录。
