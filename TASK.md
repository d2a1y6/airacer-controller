# AI Racer 控制任务、提交接口与算法目标说明

## 1. 任务基本形式

AI Racer 的核心任务是写一个自动驾驶控制函数，让一辆仿真赛车在赛道上尽可能稳定、尽可能快地完成规定圈数。

平台会在 Webots 仿真环境中运行赛车。赛车前方有左右两个摄像头。每一帧，平台把摄像头画面和当前仿真时间传给我们的代码；我们的代码根据这些信息返回两个控制量：方向和速度。平台再根据这两个控制量驱动车辆前进。

控制过程可以理解为：

```text
左右摄像头图像
-> control() 函数判断赛道方向
-> 输出 steering 和 speed
-> 平台驱动车辆移动
-> 产生下一帧摄像头图像
-> 再次调用 control()
```

我们不能直接控制仿真器，不能读取赛道地图，也不能读取车辆坐标、朝向、检查点或其他车辆位置。算法主要依赖摄像头画面判断赛道在哪里、车应该往哪边转、该开多快。

## 2. 输入信息

提交的代码必须提供下面这个函数：

```python
def control(left_img, right_img, timestamp):
    ...
```

平台调用这个函数时会传入三个参数。

| 参数 | 含义 | 格式 |
|---|---|---|
| `left_img` | 左前方摄像头图像 | `np.ndarray`，shape 为 `(480, 640, 3)`，BGR，`uint8` |
| `right_img` | 右前方摄像头图像 | `np.ndarray`，shape 为 `(480, 640, 3)`，BGR，`uint8` |
| `timestamp` | 当前仿真时间 | `float`，单位秒 |

图像是最主要的信息来源。算法通常需要从图像中识别赛道边界、可行驶区域、道路中心、弯道方向或前方障碍情况。

`timestamp` 可以用于简单的时间判断，例如启动阶段降速、控制平滑、丢线恢复计时等。它不是车辆位置，也不是当前圈数。

接口没有直接提供以下信息：

```text
赛道地图
赛道中心线
车辆绝对坐标
车辆朝向
当前检查点编号
当前圈数
其他车辆位置
```

这些信息只能在赛后结果或回放中看到，不能在 `control()` 运行时直接使用。

## 3. 输出控制

`control()` 每次必须返回两个数：

```python
return steering, speed
```

| 返回值 | 含义 | 范围 |
|---|---|---|
| `steering` | 转向比例 | `[-1.0, 1.0]` |
| `speed` | 速度比例 | `[0.0, 1.0]` |

`steering` 控制方向：

```text
steering < 0：左转
steering = 0：尽量直行
steering > 0：右转
```

`speed` 控制速度：

```text
speed = 0.0：停止
speed = 1.0：最大速度比例
```

`speed=1.0` 对应实际最高车速约 22 km/h。返回值超出范围时，平台会截断到合法范围内。

算法的本质是每一帧决定两个量：往哪边转，以及开多快。方向和速度应该配合使用。直道可以更快，弯道应适当减速；画面不清楚、偏离赛道或接近边界时，也应降低速度。

## 4. 一次控制决策

一次 `control()` 调用通常可以分成五步：

```text
读取图像
-> 识别赛道或可行驶区域
-> 估计车辆相对赛道中心的偏移和前方弯道趋势
-> 计算 steering
-> 根据弯道、偏移和置信度计算 speed
```

常见基础思路：

1. 只使用图像下半部分或中下部分，因为这里更接近车辆前方地面，对控制更直接。
2. 用颜色、边缘、轮廓、直线检测或其他视觉方法识别赛道边界和可行驶区域。
3. 估计赛道中心相对画面中心的位置。赛道中心偏左，就向左修正；偏右，就向右修正。
4. 根据偏移量和弯道趋势输出 `steering`。偏移越大，转向越强；但转向变化不宜过于跳跃。
5. 根据情况输出 `speed`。直道、识别稳定时提高速度；急弯、偏移大、识别不确定时降低速度。
6. 如果识别失败，使用保守策略，例如减速、保持上一帧方向或尝试回到赛道中心。

`control()` 会被频繁调用，必须快速返回。不要在每一帧做训练、长时间循环、大规模搜索、网络请求或大量初始化。

## 5. 两种算法目标

本组准备两套控制策略。两套策略使用完全相同的提交接口，区别在内部控制逻辑和参数选择。

### 5.1 `no_other_cars`：无其他车策略

`no_other_cars` 适用于只要求本车完成赛道、没有其他车辆同场干扰的考核方式。当前仓库已经实现并主要维护这套策略。

目标：

```text
稳定完赛
缩短总用时
提高最快单圈
减少冲出赛道、停滞、识别失败等异常
```

策略重点：

```text
赛道识别稳定
转向响应及时
直道尽量提速
弯道提前减速
偏离赛道后能够恢复
```

单车场景下不需要重点考虑其他车辆、抢线、避让和碰撞风险。因此可以更关注路线效率和速度上限。但过于激进的速度会导致弯道失控、丢线或冲出赛道，最终反而影响完赛。

### 5.2 `with_other_cars`：有其他车策略

`with_other_cars` 适用于平台按正式竞赛规则运行、多辆车同场比赛的情况。当前只保留接口名，避让和抢线逻辑还没有实现。

目标：

```text
尽量完赛
尽量缩短完赛时间
降低严重碰撞风险
避免长时间停滞
避免被取消资格
```

策略重点：

```text
弯道更保守
视野不确定时降速
避免极限贴边
避免在复杂场景中高速冲入弯道
优先保证车辆持续前进并完成圈数
```

正式竞赛中，完赛车辆通常优先按完赛时间排序；未完赛车辆再按完成圈数和赛道进度排序。严重碰撞、长时间未通过检查点等情况可能导致停车惩罚或取消资格。因此，多车稳健策略不应只追求单圈速度，还要减少高风险动作。

### 5.3 两套策略如何提交

两套策略都写成 `team_controller.py` 形式，入口都是 `control()`。当前可生成的是 `no_other_cars`；`with_other_cars` 入口会显式报未实现，避免误以为已经有多车避让策略。

平台或历史脚本里可能还会出现 `fastest`、`safe`、`final` 这些名字。它们现在只当作旧输出名或提交槽位名，不代表三套不同控制逻辑。需要上传时，把已经验证过的 `no_other_cars` 版本生成到对应槽位即可。

平台槽位可以按比赛安排使用，例如：

```text
main：稳定完赛版本
dev：激进提速版本
backup：保守备用版本
```

正式使用哪个版本，取决于当前被激活的参赛槽位。

## 6. 代码文件格式

提交文件通常命名为：

```text
team_controller.py
```

最小可运行结构如下：

```python
def control(left_img, right_img, timestamp):
    steering = 0.0
    speed = 0.5
    return steering, speed
```

文件中可以定义辅助函数、常量和少量全局状态，例如上一帧的转向值、上一次识别到的赛道中心、平滑参数等。

示例结构：

```python
last_steering = 0.0

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def control(left_img, right_img, timestamp):
    global last_steering

    # 1. 图像处理
    # 2. 估计赛道方向
    # 3. 计算转向和速度

    steering = 0.0
    speed = 0.5

    steering = clamp(steering, -1.0, 1.0)
    speed = clamp(speed, 0.0, 1.0)

    last_steering = steering
    return steering, speed
```

`control()` 应该是轻量的实时决策函数。不要在里面训练模型、访问文件、联网、启动外部程序或等待输入。

## 7. 代码运行限制

平台会对提交代码做检查，并在受限环境中运行。

允许使用的常见库包括：

```text
numpy
cv2
math
collections
heapq
functools
itertools
typing
pathlib
dataclasses
re
```

禁止使用的能力包括：

```text
读写文件
访问系统环境
联网
启动外部进程
多线程或多进程
动态执行代码
沙箱逃逸相关操作
```

常见禁止项包括：

```text
os, sys, socket, subprocess, multiprocessing, threading,
requests, urllib, http, pickle, importlib,
open, eval, exec, compile, globals, locals
```

线上环境有资源限制。文档给出的限制包括：

```text
内存限制：512 MB
CPU 时间限制：30 秒
单帧控制：应尽量在毫秒级返回
```

算法应以轻量图像处理和简单控制逻辑为主。每帧过重的模型推理、大量数组复制、复杂搜索或长循环都可能影响仿真运行。

## 8. 提交与版本管理

提交时上传一个 `.py` 文件。平台会做即时校验，主要检查：

```text
Python 语法是否合法
是否存在可调用的 control 函数
是否使用了禁止 import
返回值类型和范围是否正确
```

如果有官方 SDK，可以本地运行官方校验：

```bash
python sdk/validate_controller.py --code-path my_controller.py --rules-path sdk/rules.yaml
```

每个队伍有三个代码槽位：

```text
main：主力版本
dev：开发版本
backup：备用版本
```

上传新代码到某个槽位后，该槽位旧版本会失效。上传成功不等于正式比赛一定使用该版本；需要把某个槽位设为参赛版本。

提交锁定规则：

```text
赛区处于 REGISTRATION 状态时允许上传
管理员锁定提交后不再接受新提交
锁定后使用最后一次成功上传并激活的版本参赛
没有有效提交的队伍，车辆会静止不动
```

## 9. 测试与反馈

提交后可以申请测试。测试完成后，平台会给出测试报告，常见字段包括：

```text
完成圈数
最快单圈时间
轻微碰撞次数
严重碰撞次数
结束原因
```

比赛结束后，平台会生成比赛结果，常见信息包括：

```text
最终排名
队伍 ID
完成圈数
最好单圈
总用时
车辆状态
严重碰撞次数
```

平台还会保存回放数据。回放数据可以帮助分析车辆在哪里偏离赛道、哪里减速不足、哪里识别失败、哪里发生碰撞或停滞。

回放和结果数据是赛后反馈，不是 `control()` 运行时的输入。运行时可直接使用的信息仍然只有左右摄像头图像和 `timestamp`。

## 10. 正式规则摘要

实际运行时采用平台部署的比赛配置。仓库赛事规则文档中的通用规则如下。

### 10.1 赛制阶段

系统根据参赛队伍数量选择赛制：

```text
4 队以内：排位赛 -> 决赛
5-8 队：排位赛 -> 半决赛 -> 决赛
9 队及以上：排位赛 -> 小组赛 -> 半决赛 -> 决赛
```

排位赛通常用于确定种子排位或后续分组。小组赛、半决赛和决赛用于正式竞速和晋级。

### 10.2 排名规则

竞速赛中：

```text
第一辆车完成规定圈数后，启动 60 秒宽限期
宽限期内完赛的车辆，按完赛时间升序排名
宽限期结束仍未完赛的车辆，按完成圈数和赛道进度排名
```

排位赛中：

```text
车辆完成规定圈数
通常取最快单圈时间作为种子排位依据
```

### 10.3 碰撞与违规

规则文档中列出的处罚包括：

```text
轻微碰撞：记录次数，无即时惩罚
严重碰撞：触发停车惩罚
累计 3 次严重碰撞：取消资格
60 秒内未通过任何检查点：取消资格
```

在单车完赛场景下，车辆间碰撞通常不是主要约束；在多车竞赛场景下，碰撞和滞留会明显影响策略选择。

### 10.4 积分规则

正式积分表为：

```text
第 1 名：10 分
第 2 名：7 分
第 3 名：5 分
第 4 名：3 分
第 5 名及以后 / 未完赛：1 分
```

积分主要用于正式多队赛事。如果考核只要求单车完赛，通常更应关注完赛、总用时和最快单圈。

## 11. 本仓库对应实现

本仓库用模块化结构协作开发，最后由脚本生成单文件提交版本。

控制流水线：

```text
controller/perception.py  : 图像 -> PerceptionObs
controller/estimator.py   : PerceptionObs -> TrackState
controller/policy.py      : TrackState -> ControlCmd
```

公共数据结构放在 `controller/common.py`：

- `PerceptionObs`：中心点、左右边界、道路宽度和感知置信度。
- `TrackState`：横向偏移、方向误差、曲率、前瞻误差、置信度和丢线状态。
- `ControlCmd`：转向和速度命令。

生成当前无其他车策略：

```bash
python scripts/build_submission.py --mode no_other_cars --out submissions/final/team_controller.py
```

`with_other_cars` 还没实现。不要把旧的 `fastest` / `safe` 当成新策略目标；它们只用于兼容旧输出路径。

生成旧输出名兼容文件时，可以显式指定输出路径：

```bash
python scripts/build_submission.py --mode no_other_cars --out submissions/fastest/team_controller.py
python scripts/build_submission.py --mode no_other_cars --out submissions/safe/team_controller.py
```

校验：

```bash
python scripts/validate_submission.py submissions/final/team_controller.py
pytest
```

平台测试或本地重要测试完成后，把结果写入 `experiments/runs.csv`，把较长观察写入 `experiments/notes.md`。
