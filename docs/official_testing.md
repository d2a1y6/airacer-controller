# 官方 SDK 与 Webots 本地测试接入

本仓库不复制官方平台源码。官方仓库放在相邻目录：

```text
/Users/day/Desktop/Github/pkudsa.airacer
```

我们的控制器先由本仓库生成单文件 `team_controller.py`，再交给官方 SDK 校验或启动 Webots。

## 1. 准备官方仓库

如果本地还没有官方仓库：

```bash
cd /Users/day/Desktop/Github
git clone https://github.com/pkulab409/pkudsa.airacer.git
```

如果已经存在，更新到最新版本：

```bash
git -C /Users/day/Desktop/Github/pkudsa.airacer pull --ff-only
```

官方本地测试主要用这些文件：

```text
sdk/check_env.py              环境自检
sdk/validate_controller.py    提交前合规校验
sdk/rules.yaml                官方校验规则
sdk/run_local.py              校验、生成配置并启动 Webots
sdk/worlds.py                 赛道和车位目录
sdk/webots/                   Webots 赛道、车型和控制器资产
```

## 2. 生成我们的提交文件

在本仓库根目录执行：

```bash
# 单车场次（计时赛）：R049驾驶底座；当前官方 complex 成绩见 experiments R068
python scripts/build_submission.py --mode no_other_cars --out submissions/no_other_cars/team_controller.py
```

如果要测多车场次版本（对手避让/倒车脱困）：

```bash
python scripts/build_submission.py --mode with_other_cars --out submissions/with_other_cars/team_controller.py
```

后面的官方测试都使用：

```text
submissions/no_other_cars/team_controller.py
```

## 3. 先跑本仓库校验

```bash
python scripts/validate_submission.py submissions/no_other_cars/team_controller.py
pytest
```

这一步检查本仓库自己的接口、静态规则和 mock 图像输出范围。

## 4. 跑官方 validator

官方 validator 的实际参数是 `--rules`，不是 `--rules-path`。

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/no_other_cars/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
```

需要机器可读结果时：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/no_other_cars/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml \
  --json
```

更严格的提交前检查：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/no_other_cars/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml \
  --strict
```

## 5. 检查 Webots 本地环境

官方 SDK 要求 Python 3.10+，并需要 `numpy`、`pyyaml`。如果控制器使用 OpenCV，还需要 `opencv-python` 或 `opencv-python-headless`。

只跑 `validate_controller.py` 或 `run_local.py --validate-only` 不需要 Webots。要用官方赛道做真实可视化仿真，macOS 上必须先手动安装 Webots 桌面 app。安装后，SDK 会启动 Webots 图形界面并打开官方 `.wbt` 赛道。

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/check_env.py
```

如果 `which webots` 找不到，且 `/Applications/Webots.app` 不存在，就说明还没安装或 SDK 找不到 Webots。

macOS 如果提示 “Apple could not verify `webots-R2025a.dmg` is free of malware”，通常是下载文件带有 quarantine 标记。确认安装包来自 Webots 官方来源后，可以只对这个安装包移除标记再打开：

```bash
xattr -d com.apple.quarantine ~/Downloads/webots-R2025a.dmg
```

如果复制到 `/Applications` 后第一次启动仍被拦截，可以再对应用包移除一次：

```bash
xattr -dr com.apple.quarantine /Applications/Webots.app
```

如果 Webots 不在默认路径，设置 `WEBOTS_HOME`，或后续运行时显式传 `--webots`。

macOS 常见路径示例：

```bash
export WEBOTS_HOME=/Applications/Webots.app
```

## 6. 只跑官方 run_local 校验层

这一步调用官方 `run_local.py`，但不启动 Webots：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/no_other_cars/team_controller.py" \
  --validate-only
```

它适合放在提交前检查或 CI 中。

## 7. 启动 Webots 单车测试

先查看官方 SDK 当前支持的赛道和车位：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py --list-worlds
```

默认基础赛道：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/no_other_cars/team_controller.py" \
  --world basic \
  --car-slot car_1
```

复杂赛道：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/no_other_cars/team_controller.py" \
  --world complex \
  --car-slot car_1
```

无弹窗批量模式：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/no_other_cars/team_controller.py" \
  --world basic \
  --car-slot car_1 \
  --batch
```

Webots 启动后，官方车端控制器会加载 `submissions/no_other_cars/team_controller.py`，不断传入左右摄像头图像和时间戳，再执行我们返回的 `steering`、`speed`。

## 8. 多车本地测试

官方 `run_local.py` 支持重复传 `--car`。格式是：

```text
controller_path:slot:team
```

示例：

```bash
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --world basic \
  --car "$PWD/submissions/with_other_cars/team_controller.py:car_1:ours" \
  --car "$PWD/submissions/with_other_cars/team_controller.py:car_2:opp"
```

本地多车测试可以观察基本交互，但仍不能完全替代线上平台的碰撞判定、赛制和测试队列。

## 9. 常见问题

- `validate_controller.py` 报禁止 import：改 `controller/` 里的源模块，然后重新运行 `scripts/build_submission.py`。
- `control()` 超时或平均耗时高：减少每帧大数组分配，优先使用 `numpy` 或 `cv2` 原生函数，避免 Python 像素循环。
- Webots 找不到：检查 `WEBOTS_HOME`，或用 `--webots /path/to/webots`。
- 本地能跑不等于线上成绩稳定：本地测试主要排除接口、沙箱和基础驾驶问题，最终仍要上传平台槽位并申请测试。

## 10. 推荐提交前顺序

```bash
python scripts/build_submission.py --mode no_other_cars --out submissions/no_other_cars/team_controller.py
python scripts/validate_submission.py submissions/no_other_cars/team_controller.py
pytest
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/validate_controller.py \
  --code-path submissions/no_other_cars/team_controller.py \
  --rules /Users/day/Desktop/Github/pkudsa.airacer/sdk/rules.yaml
python /Users/day/Desktop/Github/pkudsa.airacer/sdk/run_local.py \
  --code-path "$PWD/submissions/no_other_cars/team_controller.py" \
  --validate-only
```

如果这几步都通过，再用 Webots 跑 `basic` 和 `complex`，并把测试结果写入 `experiments/runs.csv` 和 `experiments/notes.md`。

完整赛道、测试入口和正式赛制清单见 [official_test_matrix.md](official_test_matrix.md)。
