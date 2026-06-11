# 实验记录

> 本文件与 `experiments/runs.csv` 配对：runs.csv 是结构化台账（一行 = 一次真实测试），
> 本文件是配套的叙事观察。两者用 **Run ID（R001、R002…）** 交叉引用。

## 记录规范（2026-06-11 起）

- 一次真实 Webots / 平台测试 = 一个 Run ID；**只有跑了测试才建区块**，纯代码改动不建。
- 每个区块对应 runs.csv 中同 Run ID 的一行（该行 `notes` 以 `R0xx |` 开头）。
- runs.csv 的 `notes` 只写一两句结论 + `详见 notes.md R0xx`，**不要**把整段叙事复制进 csv（历史行曾双写导致维护成本和漂移，新行不再这样）。
- 叙事、诊断、下一步只写在本文件；当前总体状态和未解问题清单维护在 `experiments/STATUS.md`（就地更新）。
- 新区块加在「当前记录」**最上面**（倒序，最新在上）。
- 区块模板：

  ```
  ### R0xx — <一句话标题> (<date>, <track>)
  - **构建**: commit / working-tree；相对上一次测试改了什么
  - **配置**: world / car_slot / 单车·多车 / practice·qualifying
  - **记录完整性**: clean | interleaved（读到帧数 vs metadata.total_frames；有无孤儿 Webots）
  - **结果**: 是否完赛；末帧位置/时间；关键 telemetry / 控制日志数字（注明来源工具）
  - **现象**: 肉眼 + 数据看到的问题
  - **结论/下一步**: 本次说明了什么；下一步动哪个旋钮
  ```

- 测量纪律：每次跑前确认无孤儿 Webots 进程，否则 supervisor 的 `telemetry.jsonl` 会交错
  （帧数远超 `metadata.total_frames`、`t` 非单调），坐标/速度统计不可信。控制器内部日志
  （`scripts/analyze_control_log.py` 读 `--debug-log` 产出的 JSONL）只由控制器进程写，
  **不受 supervisor 交错影响**，优先采信。
- 工具：`scripts/analyze_telemetry.py`（遥测汇总 + 归档到 `.tmp/recordings/<标签>/`）、
  `scripts/analyze_control_log.py`（控制日志汇总）、
  `build_submission.py --debug-log <PATH>`（生成带逐帧日志的本地调试构建，禁止上传）。

---

## 当前记录（新格式，最新在上）

### R037 — 正式 final 单文件 basic 回归：红色环境兜底未污染 basic (2026-06-12, basic)
- **构建**: commit `39b6cfe`，直接使用 `submissions/final/team_controller.py`，不使用 debug 构建；md5 与 fastest 相同，为 `f4b79c09f6811580817ecfe04d1fb11a`。
- **配置**: 官方 `run_local.py --code-path submissions/final/team_controller.py --world basic --car-slot car_1`，通过官方 validator 后启动 Webots；AI 跑到 `t≈150.69s` 主动停止。
- **记录完整性**: telemetry 时间单调且可读，但因主动 kill，metadata 仍带旧总帧数，脚本标为 suspect。本轮没有控制日志和相机帧，只用于正式单文件 basic 回归。
- **结果**: telemetry 无事件、无近停，末帧 `x≈-19.76,y≈121.03,speed≈3.94,status=normal`。全段真实速度 mean `5.12`、median `6.09`、p95 `6.10`；近停占比 `<0.3=0.00`。
- **现象**: `t=40→95` 直道/右弯速度中位数 `6.10`；`t=100→130` 顶部左侧弯最低速度约 `2.00`，状态一直 normal；`t=130→150` 起点区域均速约 `5.29`。没有出现贴边、长爬行或事件。
- **结论/下一步**: 正式 final 单文件没有在 basic 前 150 秒引入明显回归，说明 Phase 2.2 的 complex 红色环境单目白线兜底没有污染 basic。下一步仍是人眼跑 complex 终判。

### R036 — 正式 final 单文件 complex 冒烟：关键风险窗行为与 debug 证据一致 (2026-06-12, complex)
- **构建**: commit `35b96a1`，直接使用 `submissions/final/team_controller.py`，不使用 debug 构建；md5 与 fastest 相同，为 `f4b79c09f6811580817ecfe04d1fb11a`。
- **配置**: 官方 `run_local.py --code-path submissions/final/team_controller.py --world complex --car-slot car_1`，通过官方 validator 后启动 Webots；AI 监控旧风险坐标，跑过旧起点前窗口后主动停止，实际到 `t≈360.32s`。
- **记录完整性**: telemetry 时间单调且可读，但因主动 kill，metadata 仍带旧总帧数，脚本标为 suspect。本轮没有控制日志和相机帧，只用于确认最终上传单文件的物理行驶没有偏离 R035 debug 证据。
- **结果**: telemetry 无事件、无近停，末帧 `x≈197.25,y≈-17.89,speed≈3.00,status=normal`。最近旧 `x≈169,y≈111` 距离约 `0.72`，最近旧 `x≈-42,y≈124` 距离约 `1.98`，最近旧起点前 `x≈-10,y≈-27` 距离约 `0.68`，最近 `x≈28,y≈-28` 距离约 `1.24`，均以 `normal` 和非近停速度通过。
- **现象**: 第一个左弯 `t=27→43` 真实速度最低约 `1.36`；旧 `130→185s` 最低约 `1.74`；旧 `x≈-42,y≈124` 核心窗口 `t=248→256` 最低约 `2.04`；旧起点前 `t=310→333` 最低约 `1.55`，无长爬行。
- **结论/下一步**: R036 证明实际上传的 final 单文件在 Webots 物理仿真中复现了 R035 的通过状态。它不替代 R035/R034 的视觉 overlay，也不替代人眼终判；下一步仍是人跑当前 final，确认视觉上是否稳定沿中间白色虚线。

### R035 — Phase 2.2 候选长跑通过旧终点前卡点并进入下一轮 (2026-06-12, complex)
- **构建**: commit `9e4ce5e`，即 R034 记录后的 Phase 2.2 候选；控制代码仍等同 `95740ed`。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 12`，world=complex, car_1, practice；不追求完整官方 lap，跑过 R034 之后的后段并进入下一轮早段后主动停止，实际到 `t≈399.74s`。
- **记录完整性**: 控制日志 clean，`12491` 帧。telemetry 时间单调且可读，但因主动 kill，metadata 仍带旧总帧数，脚本标为 suspect；本轮只用 telemetry 判断位置、速度和事件。保存约 `1041` 对 stereo PNG，主动停止导致 1 个 join 差异，所选 overlay 正常。
- **结果**: telemetry 无事件、无近停，末帧 `x≈174.11,y≈158.86,speed≈5.50,status=normal`。车辆最近到旧 `x≈-42,y≈124` 的距离约 `2.20`，最近到旧起点前 `x≈-10,y≈-27` 的距离约 `0.68`，最近到 `x≈28,y≈-28` 的距离约 `1.24`，这些点都以 `normal` 状态和非近停速度通过。
- **现象**: 全局控制日志 lost 为 0，`mean|lat|=0.063`，低命令速度 `<0.3` 占比约 `1%`。旧起点前窗口 `t=310→333` 中真实速度最低约 `1.55`、均值约 `4.49`；下一轮早段 `t=356→394` 真实速度最低约 `1.49`、均值约 `4.83`。overlay 显示车阵、起点前直道、下一轮左弯和上方复合弯里，白线候选都在路面虚线附近，没有明显锁到车辆或栏杆。
- **白线居中审计**: 对 R035 控制日志按 `line_conf>=0.6` 统计，`t>5s` 全段 `|line_offset|` 中位数 `0.043`、p90 `0.288`、p95 `0.359`，signed mean `+0.032`。关键窗口中，旧 `130→185s` 中位数 `0.035`，旧起点前 `310→333s` 中位数 `0.026`，下一轮早段 `356→394s` 中位数 `0.004`。最高 offset 帧（如 `t≈226.9/312.6`）已抽 overlay，确认是车短时偏离虚线后回中，不是栏杆/车辆误锁。
- **结论/下一步**: R035 是目前最强的 AI 自主证据：旧 R024/R025/R018/R024-space/起点前卡点都未复现，且车辆已经进入下一轮早段。仍不能标完成：项目规则里人眼 Webots 终判是驾驶走线的裁判，下一步应让人跑一次当前候选，确认视觉上是否稳定沿中间白色虚线。

### R034 — Phase 2.2 候选覆盖旧 R024 空间卡点：未复现 x≈-42,y≈124 近停 (2026-06-12, complex)
- **构建**: working-tree；包含 R033 文档修正，控制代码仍等同 `95740ed`。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 8`，world=complex, car_1, practice；按坐标监控旧 R024 的 `x≈-42,y≈124` 空间卡点，经过后主动停止，实际到 `t≈274.43s`。
- **记录完整性**: 控制日志 clean，`8575` 帧。telemetry 时间单调且可读，但因主动 kill，metadata 仍带上一轮总帧数，脚本标为 suspect；本轮只用 telemetry 判断位置、速度和事件。保存 `1072` 对 stereo PNG，主动停止导致最后一张 PNG 有读取警告，所选 overlay 正常。
- **结果**: telemetry 无事件、无近停，末帧 `x≈12.62,y≈82.77,speed≈3.10,status=normal`。最近旧卡点的一帧是 `t=253.15,x≈-43.98,y≈123.96,speed≈2.55,status=normal`，距目标约 `1.98`。
- **现象**: 旧空间窗口 `t=248→256` 中，真实速度最低约 `2.04`、均值约 `2.86`，状态全 `normal`；控制日志 `line_conf>0` 为 `241/250`，lost 为 0，低命令速度 `<0.3` 为 0。overlay 显示 `t≈245/250/254/258` 的白线点沿路面虚线分布，没有锁到远处白色栏杆。
- **结论/下一步**: 这次补上了 R033 缺失的坐标级证据：旧 R024 的 `x≈-42,y≈124` 空间卡点未复现。当前候选已用 AI 短测覆盖第一个左弯、旧 `130→185s`、R018 `280→330s`、旧 `x≈-42,y≈124` 四类风险窗。仍不能标完成：还缺完整场或更后段验证，以及人眼确认车辆视觉上稳定沿中间白色虚线。

### R033 — Phase 2.2 候选延长跑到 t≈450s：干净，但旧空间点未单独取证 (2026-06-12, complex)
- **构建**: commit `f986cb0`，即 R032 记录后的 Phase 2.2 候选；控制代码仍等同 `95740ed`。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 8`，world=complex, car_1, practice；原计划覆盖旧 R024 的后段风险窗口，实际主动停止于 `t≈450.43s`。
- **记录完整性**: clean。控制日志 `14076` 帧，telemetry `14076` 行，`metadata.total_frames=14076`；保存 `1759` 对 stereo PNG。停止后确认无 Webots / controller 残留进程。
- **结果**: telemetry 无事件、无近停，末帧 `x≈122.64,y≈94.50,speed≈2.70,status=normal`。当前候选在 `t=392→413` 的位置是 `x≈194.2→139.7,y≈147.9→144.5`，和旧 R024 同时间的 `x≈-42,y≈124` 不对应。
- **现象**: `t=380→430` 控制日志 clean，`line_conf>0` 为 `1514/1562`，lost 为 0，低命令速度 `<0.3` 仅 1 帧；overlay 显示白线候选落在路面虚线附近，远处白色栏杆没有被当成中心线。但这只能说明当前运行到 `t≈450s` 前仍干净。
- **结论/下一步**: R033 证明候选可以比 R032 继续跑到 `t≈450s` 且没有新事件；但本轮一开始误按旧时间窗口分析，没有单独按坐标取旧 `x≈-42,y≈124` 空间点。该证据由 R034 补上。

### R032 — Phase 2.2 候选从头覆盖 R018 风险窗口：未复现 x≈9,y≈87 内切卡点 (2026-06-12, complex)
- **构建**: commit `a3e6250`，即 R031 记录后的 Phase 2.2 候选，控制代码等同 `95740ed`。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 6`，world=complex, car_1, practice；不跑完整场，从头覆盖 R018 的 `t≈289→296, x≈9,y≈87` 风险窗口后主动停止，实际到 `t≈351.68s`。
- **记录完整性**: clean。控制日志 `10990` 帧，telemetry `10990` 帧，`metadata.total_frames=10990`；保存 `1831` 对 stereo PNG。
- **结果**: telemetry 无事件、无近停，末帧 `x=180.34,y=-29.48,speed=4.04,status=normal`。`t=280→330` 从 `x≈14.9,y≈65.4` 走到 `x≈57.5,y≈-29.2`，最低真实速度约 `1.55`，旧 R018 `x≈9,y≈87` 内切卡点未复现。
- **现象**: `t=280→330` 控制日志 lost 为 0，`line_conf` 均值 `0.764`，`line_offset` 均值 `0.047`，低命令速度 `<0.3` 仅 8 帧。`t≈289/296` overlay 显示白线点在路面中间虚线附近，没有把远处栏杆当成中心线。
- **结论/下一步**: 当前候选已从头覆盖第一左弯、旧 R024/R025 后段窗口和 R018 风险窗口，均未复现长爬行/内侧栏杆卡点。仍不能标完成：还缺人眼确认视觉上是否沿中间白色虚线，以及更晚段/完整场是否有新问题。

### R031 — Phase 2.2 候选覆盖旧后段内切窗口：未复现长爬行 (2026-06-12, complex)
- **构建**: commit `2c12f6d`，即 R029/R030 后的 Phase 2.2 候选。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 4`，world=complex, car_1, practice；不跑完整场，覆盖旧 R024/R025 的 `t≈130→185` 后段内切窗口后主动停止，实际到 `t≈220.35s`。
- **记录完整性**: clean。控制日志 `6886` 帧，telemetry `6886` 帧，`metadata.total_frames=6886`；保存 `1721` 对 stereo PNG。
- **结果**: telemetry 无事件、无近停，末帧 `x=46.32,y=114.04,speed=5.79,status=normal`。旧窗口 `t=130→185` 从 `x≈118.5,y≈98.3` 走到 `x≈79.6,y≈5.4`，最低真实速度约 `1.74`，没有复现旧 `x≈169,y≈111` 长爬行。
- **现象**: 旧窗口控制日志 `line_conf>0` 为 `1673/1719`，lost 为 0；命令速度最低 `0.2949`，低速 `<0.3` 仅 1 帧。`t≈149→155` 有一段强左舵和低命令速度，但 overlay 显示白线候选仍在路面中，远处栏杆没有被当成中心虚线。
- **结论/下一步**: Phase 2.2 不只通过第一个左弯，也覆盖了历史后段内切窗口。仍不能标完成：目标要求人眼确认“沿中间白色虚线”，且本轮没有跑完整场。

### R030 — Phase 2.2 候选 basic 短回归：红色环境单目兜底未污染 basic (2026-06-12, basic)
- **构建**: working-tree；同 R029 Phase 2.2 候选。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh basic --frames 4`，world=basic, car_1, practice；只跑早段回归，主动停止于 `t≈46.78s`。
- **记录完整性**: clean。控制日志 `1462` 帧，telemetry `1462` 帧，`metadata.total_frames=1462`。
- **结果**: telemetry 无事件、状态 `normal`，末帧 `x=84.69,y=265.23,speed=5.95`；全段近停占比 `<0.3=0.00`，真实速度 mean `5.168` / median `6.090`。
- **现象**: `red_env` 全程 0，说明 R029 新增的红色环境单目白线兜底没有在 basic 启用。控制日志 `mean|lat|=0.039`，`|lat|>0.3=0.00`，lost 仅 `21/1462≈1%`，无明显贴边或异常减速。
- **结论/下一步**: Phase 2.2 候选没有在 basic 早段引入明显回归。仍需人眼跑 complex，确认第一个左弯是否视觉上沿中间白色虚线且无轻微擦左。

### R029 — Phase 2.2 候选自主短测：补上弯中白线短掉线，第一个左弯通过 (2026-06-12, complex)
- **构建**: working-tree；在 R028 后新增红色环境单目白线兜底（低置信折扣）、放宽曲线虚线扫描连续性/y 跨度，并把 offset-heading 冲突的回中优先阈值从 `0.30` 降到 `0.18`。已重新生成 `submissions/fastest` / `safe` / `final`。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 2`，world=complex, car_1, practice；按用户要求只跑到当前问题窗口之后，实际主动停止于 `t≈70.75s`。
- **记录完整性**: clean。控制日志 `2211` 帧，telemetry `2211` 帧，`metadata.total_frames=2211`；保存 `1105` 对 stereo PNG。
- **结果**: 第一个左弯窗口通过。telemetry `t=27→43` 从 `x≈170.4,y≈-29.5` 到 `x≈199.0,y≈5.6`，状态一直 `normal`，无事件；窗口 supervisor 速度最低约 `1.36`，全段近停占比 `<0.3=0.00`。
- **现象**: 对比 R028，`t=27→43` 控制日志中 `line_conf>0` 从 `348/500` 提到 `481/500`，最长白线短掉线基本消失；窗口命令速度均值 `0.607`，低速 `<0.3` 约 `1%`。`t≈31→32` 左舵明显收小并开始右向回中；`t≈34→36` 仍有正常左弯舵角，但 telemetry 不近停、不撞，`t≈42` 已稳定出弯。
- **白线居中量化**: 第一个左弯 `t=27→43` 内，白线 `|offset|` 中位数 `0.102`、p90 `0.386`；出弯段 `t=37→43` 中位数降到 `0.028`、p90 `0.170`，并在 `t≈41.0→43.0` 连续接近 0。这说明车在弯内从偏离白线逐步回到中间虚线附近。
- **验证**: `pytest -q` 为 `113 passed`；`py_compile` + `bash -n` 通过；`scripts/validate_submission.py submissions/final/team_controller.py` 通过；官方 validator 通过但有 W014 性能软警告（p95 `36.24ms`）。md5：fastest/final=`f4b79c09f6811580817ecfe04d1fb11a`，safe=`db16a4ac92af6082fcc2396ee46fe9be`。
- **结论/下一步**: 当前候选比 R028 更接近目标：弯中白线连续性强，车没有复现长爬行或撞栏事件。本轮不继续盲调。case 仍保持 open，因为这是 AI 短测，尚未由人眼确认是否完全沿中间白色虚线。

### R028 — Phase 2.1 候选自主短测：第一个左弯窗口通过，仍有低速瞬态 (2026-06-12, complex)
- **构建**: working-tree；包含 R027 后的 Phase 2.1 offset 优先候选（offset trust 0.75、heading/offset 冲突时保留回中优先级）。
- **配置**: AI 自主运行 `bash scripts/webots_run.sh complex --frames 2`，world=complex, car_1, practice；按用户要求没有跑完整场，只跑到当前问题窗口之后，约 `t=64.6s` 主动停止。
- **记录完整性**: 控制日志 clean，`2018` 帧，`t=0.03→64.58`；保存 `1009` 对 stereo PNG。telemetry 时间单调、可读，但因主动 kill，metadata 未正常收尾，脚本标为 suspect（`2019` 帧 vs `metadata.total_frames=1280`），本轮只用它判断窗口内位置、速度和事件。
- **结果**: 第一个左弯窗口已通过。telemetry 在 `t=27→43` 从 `x≈170.2,y≈-29.5` 走到 `x≈198.9,y≈-0.55`，状态一直 `normal`，无碰撞事件，supervisor 速度最低约 `1.26`；全段 `t=0.03→64.61` 近停占比 `<0.3=0.00`，末帧 `x=199.08,y=124.56,speed=5.79,status=normal`。
- **现象**: 控制日志里 `t=27→43` 有 `348/500` 帧 `line_conf>0`，`line_offset` 最高 `0.70`，说明弯中白线召回和大 offset 信任都在生效。残留在 `t≈32→35`：一小段 `line_conf=0` / `track_conf≈0.09-0.16`，`heading/lookahead` 很负，最小命令速度 `0.223`，最大左舵约 `-0.65`；但随后 `t≈36` 白线恢复，`t≈42` 已回到直道中央并加速到 `0.95`。关键 overlay 也显示白线候选没有锁到护栏。
- **结论/下一步**: 当前候选已经解决 R026 的 14 秒爬行问题，也没有复现 R027 的持续左侧撞/擦；本轮不继续盲调驾驶参数。case 仍保持 open，因为这是 AI 短测，不是完整场，也没有人眼终判。若下一次人跑仍看到左侧擦碰，优先查 `t≈32→35` 这段短暂 line/trust 降级，而不是回退 offset trust 或继续堆 escape。

### R027 — Phase 2 后第一左弯仍撞左，定位为 heading 压过 offset 回中 (2026-06-12, complex)
- **构建**: working-tree；包含 Phase 2 候选（12 行扫描、offset trust 0.55）。
- **配置**: `bash scripts/webots_run.sh complex`，world=complex, car_1, practice；调试构建，默认保存帧。用户观察：第一次拐弯仍撞左边，随后手动停止。
- **记录完整性**: clean。控制日志 `1438` 帧，telemetry `1438` 帧，保存 `143` 对 stereo PNG。
- **结果**: telemetry 无 collision event，末帧 `t=46.02,x=198.97,y=10.63,speed=5.79,status=normal`；没有 R026 的 14s 长爬行（`<0.3` 近停占比 `0.00`），但肉眼仍见第一次左弯撞/擦左边。
- **现象**: 白线不再是全程缺失。`t=27→37` 窗口 `line_conf>0` 为 `191/313` 帧，`line_offset` 最高到 `0.71`。关键帧 `t≈31.36` 有 `line_offset=+0.214,line_heading=-0.652`，车应向右回中，但 `heading/lookahead` 强负，最终仍 `steering≈-0.38`；`t≈33.8→35.2` 多帧 `line_offset≈0.62→0.71` 又超过旧 `0.55` 信任门，被主链路拒绝。
- **结论/下一步**: 问题从“看不见线”变成“看见线但弯中 heading 压过 offset 回中”。本轮已实现新候选：offset 与 heading 反号且 offset 足够大时，estimator 削弱 line_heading、lookahead 不允许被拉过中心；policy 在弯中保留一部分纯 offset 后置修正；offset trust 放宽到 `0.75`，`0.75+` 仍拒。开环回放显示 `32.64/32.96/34.88/35.20` 这类大 offset 帧能进链路并明显收左舵。下一步需重新跑 complex 终判。

### R026 — Phase 1 后第一个左转仍半径过小，Phase 2 修法取证 (2026-06-12, complex)
- **构建**: working-tree；包含白线感知 Phase 1（近中性白 + 两侧深灰路面 + 近处实测 offset），尚未完成本轮 Phase 2 回归验证。
- **配置**: `bash scripts/webots_run.sh complex`，world=complex, car_1, practice；调试构建，默认保存帧。手动停止于 `t=93.60s`。
- **记录完整性**: clean。控制日志 `2925` 帧，telemetry `2925` 帧，默认保存 `292` 对 stereo PNG。
- **结果**: lost 从此前约 19% 级别降到 `19/2925≈1%`，起步居中明显改善；但 telemetry 最长爬行段仍为 `14.1s`，`t=33.8→47.8`，位置约 `x=188.6,y=-27.1 → x=188.9,y=-26.9`。
- **现象**: 第一个左转仍半径过小。控制日志显示 `t≈31.36` 时 `lateral≈-0.04`，road-mask 口径几乎居中，但 `heading≈-0.56`、`lookahead≈-0.37`、`target_steering≈-0.42`，车在还没充分靠白线回中前就按远处左弯预判大幅左打。
- **结论/下一步**: 保存帧用当前代码离线回放，`t=31.36` 已可得到 `line_offset≈+0.43,line_conf≈0.8`；旧日志此刻为 `line_conf=0`。这说明 Phase 2 的两个旋钮成立：加密扫描行找回稀疏弯中虚线，并把白线信任门从 0.30 放宽到 0.55，让真实 off-center 白线能进入主链路。case 已归档为 `experiments/cases/R026_first_left_tight_radius/`，报告图已归档为 `experiments/figures/R026_first_left_tight_radius/`。case 保持 open，需下一次 complex 实跑回归。

### R025 — 白线优先失效取证：关键窗口没有可用白线信号 (2026-06-11, complex)
- **构建**: working-tree；R024 的 boundary escape 加强已撤回，控制策略回到 `313e882` 同等行为。本轮只为取证加相机帧窗口。
- **配置**: `bash scripts/webots_run.sh complex --frames 6 --frame-window 130 185`，world=complex, car_1, 单车, practice；调试构建。跑到 `t≈190.34s` 后手动停止。
- **记录完整性**: 控制日志 clean，约 `5948` 帧；相机帧窗口保存 `286` 对 stereo（`572` 个 `.npy`），分析后删除原始帧，只保留 7 组 overlay/stereo PNG 在 `.tmp/r025_line_priority_run/line_window_preview/`。telemetry 和控制日志保留在 `.tmp/r025_line_priority_run/`。
- **结果**: 未作为完赛验证。本轮确认 `135-185s` 窗口里 `line_conf=0`、`line_offset=0`、line correction 为 0，控制日志 `mode_reason` 长期是 `no_line_conf`。也就是说，算法并不是“看见白线但不优先用”，而是白线感知链路没有给 policy 提供可用目标。
- **现象**: 这个窗口对应用户指出的内切/低速段。按设计，白线修正应把车带回车身中心；实际没有生效，因为输入信号为空。另查 `380-420s` 段，白线偶尔出现但 `line_offset≈0.5-0.86`，会被信任门控当作护栏/错误线拒绝。
- **结论/下一步**: 核心旋钮不是继续提高 road mask 权重，也不是简单放宽白线信任阈值。下一步要用保留的 overlay 检查 `_camera_line_state` 为什么在 `x≈169,y≈111` 一带不给出白线候选，同时保留白栏杆/白车误锁防护。

### R024 — boundary escape 提前触发反例：没有修好转弯半径问题 (2026-06-11, complex)
- **构建**: `313e882` 之后的临时 working-tree；把边界障碍脱困触发帧数从 `8` 降到 `4`、速度上限从 `0.46` 放到 `0.52`，并让 boundary path 不要求 stable view。本轮结束后已撤回。
- **配置**: `bash scripts/webots_run.sh complex`，world=complex, car_1, 单车, practice；调试构建，无相机帧。
- **记录完整性**: 控制日志 clean，`19438` 帧；telemetry 同步可读。手动停止时无孤儿 Webots 进程残留。
- **结果**: 未跑通。末帧 `t=622.016,x=28.758,y=-28.280,heading=-1.5707,speed=0.0`。最长近停段：`514.85-622.02s`（约 `107.2s`，`x≈27.9,y≈-28.1 → x≈28.8,y≈-28.3`）；另外还有 `135.26-172.64s`（约 `37.4s`，`x≈169.1,y≈112.0 → x≈169.5,y≈110.7`）、`392.61-412.99s`（约 `20.4s`，`x≈-42.5,y≈124.1 → x≈-42.5,y≈123.5`）、`99.33-110.43s`（约 `11.1s`，`x≈140.7,y≈147.5`）。
- **现象**: 更早、更宽松的 escape 没有解决车入弯半径太小的问题。用户指出核心仍是转弯时没把白线保持在车身中间，这个判断与数据一致。
- **结论/下一步**: 该改动已撤回，不作为候选。继续堆 escape 只会掩盖问题，下一步必须修“白线没有被有效感知/采用”的链路。

### R023 — basic 回归：贴边 escape 方向改动未引入异常 (2026-06-11, basic)
- **构建**: working-tree；在 R022 的保守入弯半径参数和贴边 escape 方向修复上复验 basic。
- **配置**: `bash scripts/webots_run.sh basic`，world=basic, car_1, 单车, practice；调试构建。
- **记录完整性**: telemetry 最后归档段 `t=0.03→119.01s`，控制日志 clean，`4081` 帧，`t=0.03→130.59s`。
- **结果**: 手动停止时仍正常行驶；telemetry 末帧 `x=-0.80,y=-16.65,speed=6.10,status=normal`。控制日志：`mean|lat|=0.033`，`|lat|>0.3≈0.00`，`lost=0.06`，近停占比 `<0.3=0.02`。
- **现象**: 没有出现新贴边、卡死或误 escape；横向偏置均值 `-0.004`，基本居中。
- **结论/下一步**: 本轮 policy 改动没有破坏 basic 短跑回归。若后续继续调 complex，还要保留 basic 回归验证。

### R022 — 按历史有效方法放大入弯半径，并把 escape 限定为贴边脱困 (2026-06-11, complex)
- **构建**: working-tree；按 notes 中 R012/C004/C005 的有效方向，降低远处前瞻与急弯舵角、提高速度相关收舵和弯道降速；同时把 escape 方向改成“几何兜底 + 单侧余量极小时远离低余量一侧”，避免贴左栏还继续左打、贴右栏还继续右打。
- **配置**: `bash scripts/webots_run.sh complex`，world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: telemetry 归档段 `t=0.03→177.41s` 可读，控制日志 clean，`6174` 帧，`t=0.03→197.57s`；本轮无孤儿进程残留。
- **结果**: 旧卡点已通过。R021 会在 `x≈169,y≈111` 长爬行 25.3s；本轮 `t≈145.7s` 已到 `x=137.25,y=90.97,speed=4.32,status=normal`，`t≈177.4s` 到 `x=91.12,y=155.50,status=normal`。telemetry 最长近停仍只有早段固定 5.0s，未出现 R021 的长时间贴栏爬行。
- **现象**: 120s 后段入口不再因为远处右弯过早大舵角切进内圈；控制日志 `mean|lat|=0.056`、`|lat|>0.3=0.07`，escape 只短暂介入，不主导常规驾驶。
- **结论/下一步**: 用户判断“常规循线”和“碰撞/贴边后 escape”应分开是对的。提交接口没有直接碰撞传感器，只能用图像余量、低速/冻结和历史舵角间接推断。当前修复证明 `x≈169,y≈111` 旧卡点已过，但还没证明整条 complex 完整跑通；下一步应继续跑到更后段，确认是否还有新的内切/低速窗口。

### R021 — 采样色卡落配置：开头贴左与假丢线改善，后段仍卡 x≈169,y≈111 (2026-06-11, complex)
- **构建**: working-tree；把 Webots 原始帧采样到的深灰路面、浅灰路牙、浅灰栏杆、绿草、红地、蓝天写入 `COLOR_PROFILE`，道路 mask 只用采样暗灰路面核心；白线作为发车和低置信道路的优先参考；提交构建新增剥离注释/docstring 以满足 100KB 限制。
- **配置**: 先用 `bash scripts/webots_run.sh complex --frames 15` 抽稀取证，随后用 `bash scripts/webots_run.sh complex` 不存帧闭环验证，world=complex, car_1, 单车, practice。
- **记录完整性**: 带帧 run telemetry clean，`t=0.03→97.73s`，帧分析后已删除 `.tmp/run.prev/frames_complex`，只保留小型 JSON/overlay；闭环 run 后手动停止，metadata 沿用旧 total_frames，控制日志可用。
- **结果**: 离线同批真实帧重放从感知丢线 `194/203 (95.6%)` 降到 `0/203`。闭环 complex 前 95.8s lost 仅 `23/2995 (0.01)`，横向均值 `+0.001`，第一处左弯未撞；后续在 `x≈169.49,y≈110.91` 进入 25.3s 长爬行，仍未跑通。
- **现象**: 关键 bug 不是通道错，`.npy` 确认是 BGR；而是采样暗灰路面被 red 环境填充率惩罚压到低置信，导致有效扫描线被融合阶段丢掉。把惩罚阈值改到接近异常饱和后，开头和 90s 窗口都恢复 24 个观测点。蓝灰侧栏杆不再通过蓝门桥接并入 road mask。
- **结论/下一步**: 用户指出的“颜色必须真实采样”是对的，本轮已修成配置化色卡和保守暗灰路面 mask。当前目标仍未完成；下一步要针对 `x≈169,y≈111` 的低速卡点抓短窗口帧，不要再回退成宽松 road mask。

### R020 — 低置信入弯门控反例：退回早段内侧栏杆卡死 (2026-06-11, complex)
- **构建**: working-tree；在 R018 边界障碍脱困候选上，临时加入“红色环境低置信/居中入弯限舵”和“near_obstacle 几何冲突限舵”（本轮结束前已撤回）。
- **配置**: `bash scripts/webots_run.sh complex --frames 6`，world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: telemetry suspect（metadata 沿用旧 total_frames），控制日志可用；相机帧保存在当轮 `.tmp/run/frames_complex/`，后续 run 轮换后仅作临时证据。
- **结果**: 未跑通。`t=0.03→153.66s`，末帧 `x=165.53,y=119.08,speed=0.000`；最长爬行 `41.8s`，`t=111.9→153.7`，`x=165.1,y=119.3 → x=165.5,y=119.1`。
- **现象**: 试图压住后段 `t≈290s` 大右舵后，早段重新卡在 R014 附近。说明这个低置信入弯门控不是安全修法。
- **结论/下一步**: 本改动已撤回。不要沿这个方向继续扩大“低置信限舵”，它会破坏早段通过能力。

### R019 — escape 执行中翻向反例：早段卡点退化 (2026-06-11, complex)
- **构建**: working-tree；在 R018 上尝试让执行中的 escape 根据最新单侧边界余量实时翻转方向（本轮结束前已撤回）。
- **配置**: `bash scripts/webots_run.sh complex --frames 6`，world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: telemetry suspect；控制日志可用；早段 overlay 见当轮 `.tmp/run/early_stuck_overlays/`。
- **结果**: 未跑通。`t=0.03→145.02s`，末帧 `x=166.90,y=117.47,speed=0.010`；最长爬行 `34.1s`，`t=110.9→145.0`。
- **现象/取证**: `t≈106.8` 左侧余量为 0 时右打 escape，随后 `right_margin=0` 后逻辑翻成持续左打；画面显示车已贴内侧栏杆，持续左打前进无法脱出。R018 同一区域能通过，说明“escape 中途按余量翻向”会破坏早段。
- **结论/下一步**: 本改动已撤回。escape 方向不能在执行中直接按边界余量翻转；若要修后段，必须更早防止切内线或设计更有状态的摆脱节奏。

### R018 — 边界障碍脱困候选：通过早段，后段 x≈9,y≈87 卡死 (2026-06-11, complex)
- **构建**: working-tree；新增 `boundary_obstacle_stall`：红色环境、近障碍、单侧边界余量接近 0、画面稳定且指令速度仍高于 low_speed 时，更早触发强脱困；脱困方向按触发瞬间左右余量选择。**本轮结束时保留这部分代码。**
- **配置**: `bash scripts/webots_run.sh complex --frames 3`，world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: clean；telemetry `14068` 帧，`t=0.03→450.18s`；控制日志 `14069` 帧；帧保存在 `.tmp/run.prev/frames_complex/`（后续清理前不要删）。
- **结果**: 未跑通。早段 `x≈169,y≈111` 从上一轮 31s 爬行缩短并通过；但 `t≈295.6s` 后在 `x≈8.4,y≈88.3` 进入长近停，末帧 `x=9.41,y=87.25,speed=0.010`，最长爬行 `154.6s`。
- **现象/取证**: 入口 `t≈289.98` 有 `st≈+0.59, sp≈0.42, lat≈0, heading≈+0.64, curvature≈-0.26, near_obstacle=true, track_conf≈0.46`，大右舵把车切进内侧。卡死后 `right_margin=0`、`near_obstacle=true`，策略持续 `escaping st=-0.76, sp=0.86`，但车身实际速度约 0，说明已物理顶死，单靠顶住后 escape 太晚。
- **结论/下一步**: 当前保留的边界障碍脱困能改善一个卡点，但不足以达成目标。下一步不要只加强脱困；应在 `t≈288-296` 入口用 overlay/感知链路修“居中低置信时突然大右舵”的来源，且必须避免 R019/R020 的早段退化。

### R017 — 线信任门控复验：首弯改善，后段 x≈-10,y≈-27 仍卡 (2026-06-11, complex)
- **构建**: `656b222` 后的工作树；线修正信任门控 + 几何脱困低速门槛。
- **配置**: `bash scripts/webots_run.sh complex --frames 3`，world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: clean；控制日志 `16634` 帧，telemetry `t=0.03→532.32s`，帧曾保存在 `.tmp/run/frames_complex/`，后续已被轮换。
- **结果**: 未跑通。第一左弯和直道摆动明显改善；`x≈169,y≈111` 旧卡点能恢复通过；但最终停在 `x=-10.21,y=-27.25,speed=0.010`，最长爬行 `31.1s`（手动停止时仍在近停）。
- **现象/取证**: 后段 `x≈-10,y≈-27` 处 `right_margin=0`、`near_obstacle=true`、指令速度仍在 `0.22-0.4`，低速脱困阈值触发不充分；开环显示边界障碍脱困可以在同一批卡死画面触发 `escaping`。
- **结论/下一步**: R015/R016 的白线和误触发问题基本命中，但 complex 仍未跑通；据此实施 R018 的边界障碍脱困候选。

### R016 — complex 白线降级版首跑：护栏误锁致直道摆动，escape 误触发致左弯撞栏 (2026-06-11, complex)
- **构建**: working-tree（白线降级为后置修正 + lost 帧透传白线）；`bash scripts/webots_run.sh complex --frames 3`。
- **配置**: world=complex, car_1, 单车, practice；调试构建。
- **记录完整性**: clean；控制日志 1310 帧 `t=0.03→41.9s`，相机帧 436 对（`.tmp/run/frames_complex/`，stride=3）。
- **结果**: 未跑通。第一个左弯撞左栏并卡死（末态 `lat=+0.65`、speed 物理为 0、escape 方向正确但车头顶栏无法脱出）。
- **现象/取证**（控制日志逐帧）:
  1. **直道左右打轮**：白线检测把右侧白色护栏认成车道线，`line_offset` 在 0 与 +0.4~+0.93 间闪烁（如 t=26.8-27.6 车完全居中时）→ 后置修正被钳到 +0.34 → steering 0↔+0.30 反复跳。
  2. **撞栏链路**：t=35.5-35.8 正常建立左打（hd→-0.43, st→-0.38）；t=35.84-36.10 护栏误锁 `lo=+0.43→+0.52` 的 +0.34 修正把左打抵消甚至打成 +0.14 约 0.3s；t=36.5-37.2 车以 sp≈0.42-0.47 平稳巡弯时，**急弯卡边几何脱困把"高弯量+签名稳定+高置信"误判为卡边**，t=37.2 强制 `st=-0.58, sp=0.62` 持续 0.8s（t=37.6 还叠加线修正到 -0.86）→ 车被怼向左侧，t=38 起右打回正已不及，`lat` 涨至 +0.65 顶死左栏。
  3. 直道上另有约每 0.6s 一次的道路中心向左毛刺（lat 短暂 -0.2~-0.38，自行恢复，伴随 hard_turn/recovering 抖动），疑似红色环境 mask 噪声或蓝色 checkpoint 门影响，**未取证**，帧已保留。
- **结论/下一步**: 修复方向已实施（见 STATUS）：线修正信任门控（|offset|>0.30 拒绝、连续 3 帧确认、EMA 平滑、弯中压零、near_obstacle 拒绝、escaping 不叠加）+ 几何脱困加低速门槛（指令速度 >0.36 不许触发）。直道左毛刺待用 `frames_complex` 渲 overlay 取证。

### R015 — basic 白线降级版首跑：整体行驶正常，弯中线闪烁与白车误锁两处残留 (2026-06-11, basic)
- **构建**: working-tree（同 R016 代码）；`bash scripts/webots_run.sh basic`（无帧 dump）。
- **配置**: world=basic, car_1, 单车, practice；调试构建。
- **记录完整性**: 控制日志 clean，4619 帧 `t=0.03→147.8s` 手动停；telemetry 已被下一次 run 清除，无坐标/速度统计。
- **结果**: 行驶正常未撞停；用户肉眼：第二个弯（约 49s）仍打轮偏早、切右侧栏杆过弯；接近终点车阵时在白车 car_5 后减速并向右打了两下轮后回正。
- **现象/取证**（控制日志逐帧）:
  1. 弯中（t=48-50）`line_offset` 在 0/-0.3/-0.64 间闪烁（白线画成三段不连续 + 单帧误锁），修正单帧从 +0.20 跳 -0.19，加剧弯中抖动。
  2. t=140.9（车阵区，`near_obstacle=true`）单帧 `lo=+0.35, lc=0.6` → steering 从 0.26 突跳 +0.51——即用户看到的"朝白车打轮"，把白车/斑马线认成线。
- **结论/下一步**: 两处都由线修正信任门控覆盖（单帧不生效、|offset| 超界拒绝、near_obstacle 拒绝、弯中压零）。"打轮偏早切右栏"在线闪烁修复后再上车复查，若仍存在则按入弯门控/感知接缝方向取证。

### R014 — complex 白线前移与边界保护：仍切内线撞栏，无法脱困 (2026-06-11, complex)
- **构建**: working-tree；把白线检测前移到 perception/estimator，policy 直接消费白线目标；新增近处左右边界余量保护和 hard_turn/recovering 连续帧确认。
- **配置**: world=complex, car_1, 单车, practice；正式 `submissions/final/team_controller.py`。
- **记录完整性**: interleaved；`analyze_telemetry.py` 检测到 3 段 run，仅使用最后一段；归档到 `.tmp/recordings/complex_line_state_R014/`。
- **结果**: 未完整跑通。最后一段 telemetry 6716 帧，`t=0.03→214.91s`；末帧 `x=165.23,y=119.25,speed=0.000`。速度 mean=2.110、median=1.930、p95=5.430，近停占比 `<0.3=0.45`。
- **现象**: 第一左弯旧卡点 `x≈186,y≈-27` 只爬行约 2.9s 后通过；后续在 `t≈121.1s` 起卡在 `x≈164.5,y≈119.6`，最长爬行段 93.8s。用户截图和肉眼反馈显示：车在弯中仍然转弯半径太小，直接贴内侧栏杆/撞栏，且无法自行脱困；这不是单纯的“新坐标卡点”，本质仍是切内线问题没有解决。
- **用户反馈**: R014 仍出现三类核心问题：一是转弯半径太小，车贴内侧栏杆过弯；二是车没有稳定骑在白线上，仍会在白线一侧行驶；三是仍有无意义打轮、减速，最后这个现象尤其明显。也就是说，“白线前移到 estimator/policy + 边界余量保护”没有把用户关心的走线问题修好。
- **结论/下一步**: 本轮结构改动只能算诊断字段和接口铺垫，不能算行为修复。下一步不应继续小幅调 `line_gain` 或速度；应抓取撞栏窗口的 debug 帧和控制日志，直接核对：白线是否被检测到、`line_offset` 是否符号正确、`right/left_margin` 是否在撞栏前已经变小、policy 为什么仍允许继续向内打轮、脱困条件为什么没触发。

### R013 — basic 白线前移与边界保护：能跑完代理，但比 R011 慢且视觉走线仍不达标 (2026-06-11, basic)
- **构建**: working-tree；同 R014 的结构改动，重建正式 `submissions/final/team_controller.py`。
- **配置**: world=basic, car_1, 单车, practice；正式 `submissions/final/team_controller.py`。
- **记录完整性**: interleaved；`analyze_telemetry.py` 检测到 2 段 run，仅使用最后一段；归档到 `.tmp/recordings/basic_line_state_R013/`。
- **结果**: 运行到 `t=442.08s` 后手动终止。最后一段 telemetry 13815 帧；速度 mean=5.238、median=6.090、p95=6.100、max=6.130，近停占比 `<0.3=0.00`。车在 `t≈299.36s` 重新进入 basic 起点区域 `x≈-19.23,y≈127.88`，按历史代理记为物理完成一圈。
- **现象**: 没有 car5 撞停或低速卡死；末帧 `x=-19.16,y=106.27,speed=2.94`，仍正常行驶。与 R011 相比，物理完成一圈代理时间从约 `259.84s` 内仍高速行驶/车阵通过，变成约 `299.36s` 才回到起点区域，basic 明显变慢。用户肉眼仍认为车没有稳定压住白线，且仍会出现不必要打轮和减速。
- **结论/下一步**: R013 不能写成“basic 无退化”。真实结论是：basic 没有撞停，但速度退化，视觉走线目标仍不达标。后续如果继续 basic，应先拿 debug 构建记录白线字段和最终 steering 分解，找出为什么“看见白线”没有变成“车身中心压白线”。

### R012 — complex 白线位置优先修正：通过首个左弯卡点，但未完整跑通 (2026-06-11, complex)
- **构建**: working-tree；新增白线后置校正，白线位置优先、方向辅助；开启近车检测；同时降低远处前瞻/急弯舵角以放大转弯半径。
- **配置**: world=complex, car_1, 单车, practice；正式 `submissions/final/team_controller.py`。
- **记录完整性**: clean；telemetry 13758 帧，`t=0.03→440.26s`，归档到 `.tmp/recordings/complex_line_follow_long_2026_06_11/`。
- **结果**: 未完整跑通。原先第一个左弯 `x≈183,y≈-27` 会直接长时间卡死；本版通过该区域，`t≈43.9→72.8s` 从 `x=180.0,y=-29.0` 行进到 `x=198.5,y=-15.1`。后续跑到 `t≈360.7s` 后在 `x≈-10,y≈-27` 近停，手动中止于 `t≈440.26s`。
- **现象**: 第一个左弯从“死卡”变成“短暂停顿后通过”，说明白线位置优先校正方向有效，但 complex 仍有后段卡点。速度 mean=2.889、median=3.240、p95=5.550，近停占比 `<0.3=0.22`，主要来自末段近停。
- **结论/下一步**: complex 还不能算跑通。下一步应针对 `x≈-10,y≈-27` 后段近停抓帧，而不是继续调第一个左弯。

### R011 — basic 白线位置优先修正：车阵通过且速度恢复 (2026-06-11, basic)
- **构建**: working-tree；同 R012，但在 basic 上验证加强后的白线位置修正。
- **配置**: world=basic, car_1, 单车, practice；正式 `submissions/final/team_controller.py`。
- **记录完整性**: clean；telemetry 8120 帧，`t=0.03→259.84s`，归档到 `.tmp/recordings/basic_line_follow_strong_2026_06_11/`。
- **结果**: 手动中止于 `t≈259.84s`，车仍正常行驶。速度 mean=5.469、median=6.090、p95=6.100、max=6.120，近停占比 `<0.3=0.00`。
- **现象**: 末段静态车阵不再撞 car5；车阵窗口 `y=95→135` 的 `x=-19.64→-19.38`，明显比失败版 `x≈-18` 更靠近中心线，末段车速保持 `≈6.10m/s`。用户仍肉眼指出若干路段车身没有完全骑在白线上，但车阵处已从撞车变为通过。
- **结论/下一步**: basic 当前可继续作为调参基线；若继续追求“车身中线完全压白线”，需要在控制日志里记录白线 correction，按画面逐段调而不是再用固定偏置。

### R010 — P2 白线接缝修复：闭环抓帧复查未见同类污染 (2026-06-11, basic)
- **构建**: working-tree；在 R008 直道提速基础上，给 edge fallback 加窄段过滤：窄 fallback 只有靠近画面中心或延续上一条中心线时才允许作为扫描走廊。
- **配置**: world=basic, car_1, 单车, practice；调试构建 `.tmp/run/team_controller_p2_dump.py`，控制日志 `.tmp/run/control_p2_webots_dump.jsonl`，相机帧 `.tmp/run/frames_p2_webots/`（stride=2）。
- **记录完整性**: clean；控制日志 1316 帧，`t=0.03→42.11s`。telemetry 1316 帧，归档到 `.tmp/recordings/p2_webots_short_2026_06_11/`。
- **结果**: 手动中止于 `t≈42.11s`。控制日志 mean|lat|=0.038、`|lat|>0.3` 占比 0.01；supervisor 速度 mean=4.882、median=6.080、p95=6.100，近停占比 `<0.3=0.00`，无事件。
- **现象**: 当前速度更快，旧 C006 的第二弯时间窗不再是 `78-80s`，对应弯区约在 `t≈22.3-22.6s`。这段有短暂 hard_turn 峰值（最大 `lat=+0.403, heading=-0.730, steering=+0.300`），但 overlay `.tmp/p2_webots_peak_overlays/montage_p2_webots_peak.png` 显示扫描中心沿可行驶走廊/车道虚线连续走，不是 R007 那种近处孤立窄白线把 seed 拉到栏杆侧。
- **结论/下一步**: P2 的“白线接缝污染中心线”已被当前过滤切掉。残留的 `t≈22s` 峰值更像弯中低置信 + 保守降速/走线问题，若继续优化，应单独作为入弯速度或轨迹平滑任务处理，不要回退这次 fallback 过滤。

### R009 — P2 白线接缝修复：闭环 100s 控制日志短跑 (2026-06-11, basic)
- **构建**: working-tree；同 R010 的 P2 fallback 过滤版本。
- **配置**: world=basic, car_1, 单车, practice；调试构建 `.tmp/run/team_controller_p2_debug.py`，控制日志 `.tmp/run/control_p2_webots.jsonl`。
- **记录完整性**: clean；控制日志 3138 帧，`t=0.03→100.42s`。本次 telemetry 后续被 R010 覆盖，未归档；跑后确认无 Webots 残留进程。
- **结果**: 手动中止于 `t≈100.42s`，覆盖旧 C006 问题弯区。控制速度 mean=0.890、median=1.000、p95=1.000；mean|lat|=0.028、`|lat|>0.3` 占比约 0.00，mean|heading|=0.052。
- **现象**: 旧日志 `78-80s` 的异常窗口在当前更快策略下已不对应同一赛段；该窗口当前是直道/丢线滑行，几何量接近 0。最大非 lost 横向峰值转移到 `t≈22.5s`，因此追加 R010 抓帧确认。
- **结论/下一步**: 100s 闭环日志没有复现 R007 那种持续中心线污染；用 R010 的相机 overlay 判定峰值性质。

### R008 — 直道 lost 滑行提速：干净复测速度已超过 1.5 (2026-06-11, basic)
- **构建**: working-tree；在 C006 基础上调整 policy：直道判定主要看 `curvature/lookahead/lateral`，`heading` 只做宽松兜底；新增直道记忆和居中低舵 lost 直道滑行，basic 直道目标速度为 1.00。
- **配置**: world=basic, car_1, 单车, practice；调试构建 `.tmp/run/team_controller_straight_speed_debug.py`，控制日志 `.tmp/run/control_straight_speed_clean2.jsonl`。
- **记录完整性**: clean；跑前清空 SDK 录制目录，telemetry 3158 帧，控制日志 3157 帧，归档到 `.tmp/recordings/straight_speed_clean2_2026_06_11/`。
- **结果**: 手动中止于 `t≈101.06s`。控制日志速度 mean=0.889、median=1.000、p95=1.000；supervisor 速度 mean=5.231、median=6.100、p95=6.100、max=6.120，近停占比 `<0.3=0.00`。
- **现象**: 起步后直道候选帧 2568 帧，命令速度 median=1.000，真实速度 p05=3.18、p10=4.10、median=6.10，`world_speed>=1.5` 占比 1.000。高速小舵角命令帧 2351 帧，真实速度 p05=4.31，`>=1.5` 占比 1.000。
- **结论/下一步**: “直道慢速”已在本地 Webots 干净复测中修复，直道真实速度稳定超过 1.5。后续若继续调，应转回第二个弯贴内线问题；不要再用单纯 lost 率否决本轮速度修复。

### R007 — C006 入弯门控 + 直道提速：部分见效，交接给 Codex (2026-06-11, basic)
- **构建**: C004 之上叠加两项（均**实验性、按下方状态**）：
  - **入弯时机门控**（C005, policy）：前瞻项 ×`turn_in_gate`，`gate=0.55+0.45×corner_arrival`，`corner_arrival=|lateral|/0.30+|heading|/0.45`。车居中近处还直时压制前瞻项，弯到了再放开。
  - **直道提速**（C006, policy）：`curve_risk≤0.12 且 offset_risk≤0.12` 时给速度下限 `straight_speed`（basic 0.78）。
- **配置**: world=basic, car_1, 单车, practice；带 `--dump-frames` → 帧在 `.tmp/run/frames_C006/`（~2900 对，可复盘）。
- **现象（用户实车）**:
  - **直道没明显变快**。数据确诊：`straight_speed` 确实够到了（max speed=**0.780**），但**只命中 24% 帧**——因为 ①**53% 帧 lost → 限速 0.24**；②直道条件太严：`heading` 噪声大（非lost帧 mean=0.13 > 阈值 0.12）→ `curve_risk` 常 >0.12 → 直道判不成立。mean speed 仍 0.38。**机制对，欠触发。**
  - **入弯门控**：一般弯改善（不再普遍提前拐）；但**"第二个弯"仍提前拐 + 贴右(内)栏杆**。
- **关于"第二个弯"的更正**: 它**不是 Y 形分叉**，而是**单纯一个右弯**，只是**车道白线画成 3 段不连续**，两两相接处很乱 → 推测感知中心线在接缝处被带偏 → 近处 `lateral/heading` 跳变 → 骗开入弯门控 → 早拐。**用户诉求：让车尽量保持在白线上（跟中心线），别脱出贴栏杆。** 需用 `frames_C006` 调出该弯的帧确认。
- **状态**: C005+C006 已提交在分支（实验性，未合 main）。当前**最佳仍以 C004 为可靠基线**；C006 两项需 Codex 继续打磨。当前交接只看 `experiments/STATUS.md`。
- **构建**: C003(grass+pinned+gate-bridge) 之上加**估计器曲率可信度门控**——`curvature = raw × trust`，`trust=点数×纵向跨度×拟合质量`，点少/聚簇/拟合差时曲率收向 0。
- **配置**: world=basic, car_1, 单车, practice。
- **现象（用户实车 = ground truth）**: **迄今最好**。过弯不再往反方向（左）打轮；"车离开中心线"明显好转。
- **数据**: `幻觉左弯(curv<-0.1)` 从 C002 的 hard_turn 里 0.22 降到 **0.056**；`mean|lat|=0.027`（贴中心线很紧）；steer mean +0.023（正确偏右）。lost=0.69 是 gate-bridge 的良性虚高（车 lost 时直线滑行，不据此判好坏——见 [[on-track-truth-over-offline-proxy]]）。
- **残留问题（下一主攻）**: **转弯转得太早 → 贴内线栏杆**（corner cut）。机制：转向目标里"远处前瞻项"(lookahead×0.9 + heading + curvature)在车还居中、近处还直时(lateral≈0)就因远处路已弯而提前打轮 → 切内线。证据：起步帧 lateral +0.09 时 steer 已 +0.45（由 curv+lookahead 驱动）。
- **结论**: C004 保留为最佳基线。下一步做"入弯时机门控"——远处弯但近处还没到时压制前瞻项，让车跟着中心线、等弯真正到了再转。
- **构建**: 在 C002 基础上加"蓝色 checkpoint 门并入道路 mask"（gate-bridge）。
- **配置**: world=basic, car_1, 单车, practice。
- **现象（用户肉眼 = ground truth）**: **比之前所有版本都好**——蓝门前的大拐弯、过弯剐蹭栏杆**全部消失**，只剩第一个蓝门前稍微丢一点线。
- **数据（注意：这是误导性的代理指标）**: 控制日志 lost=0.54、离线 frames_basic 全局感知丢线 0.227→0.660。原因：蓝门色相≈天空，部分含天空帧 mask 饱和→被判 lost。**但 lost≠开得差**：lost 时车直线滑行、不停车不偏出，所以这部分 lost 是良性的。
- **关键纠错**: 我（Claude）一度因"全局 lost 升 3 倍"把这版**误判为回归并回退**——这是工作流程错误：用离线代理指标否决了用户的实车 ground truth。lost 率不是质量指标。**已按用户指正恢复 gate-bridge。** 见 [[on-track-truth-over-offline-proxy]]。
- **结论**: gate-bridge **保留**，是当前最佳基线。残留"第一蓝门前稍丢线"是次要、可后续打磨（用更安全方式，别再用 lost 率当判据）。下一主攻仍是过弯走线（policy）。

### R004 — C002：grass-fix + pinned-escape（保留） (2026-06-11, basic)
- **构建**: grass-fix（mask 显式扣草、撤销 C001 饱和放宽）+ pinned-escape（顶栏杆冻结+大偏移+大反打、速度落 low_speed 空档时触发朝路面脱困脉冲）。
- **配置**: world=basic, car_1, 单车, practice；控制日志干净（9925 帧 / 317.6s）。
- **结果/现象**: lost=0.27、mean|lat|=0.042（跟踪干净，无 C001 的偏置）；**pinned-escape 触发**（t≈208.8 有 28 帧 escaping），用户确认"**原先卡死点没再卡**"。残留：蓝门处 2 个大摆动（t≈79、t≈208）未解决（R005 尝试修但回退）。
- **结论**: 这是当前**验证可用**的改进基线，已提交。下一步真正的痛点是过弯贴栏杆（属 racing-line/policy）和蓝门遮挡（需安全的感知方案）。

### R003 — C001 上车验证：拒绝合并，暴露"草地被当成路"根因 (2026-06-11, basic)
- **构建**: 分支 codex/perception-dropout，C001（`controller/perception.py`：饱和 mask 置信度惩罚 0.25→`saturated_mask_confidence_scale`=0.50）的调试构建。
- **配置**: world=basic, car_1, 单车, practice。（第一次误触复位重跑；记录的是第二次。）
- **记录完整性**: 控制日志可信（取最后一段 4177 帧, t→133.66）。用户在卡死点手动停。
- **结果**: **未完赛**。在"进入第二段直道前的弯"卡上右侧栏杆、无法自行脱困，手动停。
  - 卡死帧：`lateral=-0.65`（路在左=车顶右栏）、`steering=-0.78`（已朝路面/左打，方向是对的）、`speed=0.386` 恒定、`mode=hard_turn`、conf=0.83。
  - 脱困没触发：basic 关闭了几何脱困；低速脱困要 speed≤0.22，而这里 0.386，落在覆盖空档。
- **指标对比 R002**:
  - lost 占比 27%→**16%**（确实降了）。
  - 但 `mean|lat|` 0.043→**0.199**（中心线跟踪恶化 4.6×）、hard_turn 23%→46%、`mean|steer|` 0.063→0.260。
- **根因（看 overlay 实锤）**: `.tmp/run/perception_overlays_*` 显示——道路 mask 把**绿色草地当成路**（fill≈0.93 饱和），出现在两类画面：① 直道上路面缩成细条、草地占满下方 ROI（t≈2.2）；② 车已偏出、正对草地（t≈236）。原因是 `_build_masks` 在暗色沥青 mask 稀疏时回退到"颜色 mask"，而颜色种子取自 ROI 底部中心——那里此时是草，于是整片草都匹配成"路"。C001 把这类饱和帧从 lost 放行成"可用"，中心点落在草里 → 车朝草/栏杆打 → 卡死。**离线 lost 率 22.7%→0.3% 正是被代理指标 game 了**（之前预警的过拟合）。
- **结论/下一步**: **拒绝 C001**（不合并）。真正要修的在上游：让 mask **用低饱和/灰度判据排除草地**、不要回退到以草为种子的颜色 mask；沥青不可见时就老实 lost（直道滑行是安全的，R002 已证明滑行不停车）。这能同时降假 lost（细条路被正确分割）和消除"朝草地漂"。验证指标要升级：不只看 lost 数，要确认"可用帧"的中心点确实落在灰色沥青像素上。

### R002 — P0+P1 带日志干净基线：确诊"慢"的主因 (2026-06-11, basic)
- **构建**: 同 R001 的 P0+P1 代码，构建为调试单文件（`build_submission --debug-log .tmp/run/control_basic.jsonl`）。
- **配置**: world=basic, car_1, 单车, practice。
- **记录完整性**: **控制日志 clean**（10222 帧 == metadata.total_frames 10222）；遥测交错（脚本检测到 5 段残留，已自动只取最近一段 = 10222 帧, clean）。本条数据可信。
- **结果**: duration_sim=327.104s，finish_reason=supervisor_stop，lap=0；末帧 x=-19.78,y=232.67 仍在动（world speed 1.46）。属诊断跑，未判定完赛。
- **现象（控制日志，最可信）**:
  - **lost 占比 = 27%**；mode 占比 cruise 42% / lost 27% / hard_turn 23% / recovering 7%。
  - 指令速度 mean=0.47, median=0.45, max=0.876（始终够不到 base_speed 0.96）。
  - 转向 mean|steer|=0.063，**换向仅 0.06 次/秒 → 几乎没有左右磨**（推翻"一会左一会右"假设）。
  - 横向偏置 mean(signed)=-0.002, mean|lat|=0.043 → lateral_error 层面**几乎无系统性内侧偏置**。
  - 遥测（最近段）world speed mean=2.70，**近停占比 0.00 → 物理上稳定行进、不卡顿**，但只到峰值约 60–75%（p95 4.24 / 历史峰 5.65）。
- **结论/下一步**: "慢"的主因不是转向震荡、也不是停车，而是 **27% 时间丢线 → 指令速度被压到 lost_speed 0.24**，加上速度因子保守（cruise 也只 ~0.68）。
  - 优先级 1：**降低丢线率**（perception/estimator 鲁棒性）——这是提速最大杠杆。
  - 优先级 2：放宽速度上限（`confidence_factor` 下限、加速限制、base_speed）——但要等丢线降下来再提，否则更容易冲出。
  - 用户肉眼的"偏内侧"未在 `lateral_error` 体现，需结合弯道帧 / 感知 overlay 进一步定位（可能是 hard_turn 切弯而非稳态偏移）。

### R001 — P0+P1：收过舵 + 脱困方向改朝路面 (2026-06-11, basic)
- **构建**: working-tree（基于 `99b25e4`，P0+P1 未提交）。
  - P0：新增 `_road_direction_sign`，脱困方向改为朝**感知到的路面一侧**（优先 `lateral_error`，
    丢线退回 `_LAST_GOOD_BIAS`，再退回反打上一帧），取代写死的 `-1.0` / 盲目反打；低速贴墙脱困
    **放宽置信度门槛**且 basic / complex 都启用（依赖几何的急弯·大偏移脱困仍只在 red/complex）；
    lost 模式不再死保上一帧满舵，改为衰减并向最近可信道路方向回收。
  - P1：去掉 `hard_turn` 固定 `×1.05`（改参数 `hard_turn_steering_scale`）；新增**速度相关收舵**
    `steering_speed_cap_scale`（高速降低最大舵量上限）；basic 单独降激进度：
    `max_abs_steering 1.0→0.88`、`gain_heading 0.98→0.90`、`near_weight_offset_boost 0.55→0.45`、
    `curve_slowdown 0.66→0.70`。28 单测 + 本地/官方 validator 通过。
- **配置**: world=basic, car_1, 单车, practice（metadata: session_type=practice, total_laps=1）。
- **记录完整性**: **interleaved / 不可靠**。metadata.total_frames=11236（≈359.55s × 31fps），
  但分析脚本从 live `telemetry.jsonl` 读到 40273 帧且 `t` 非单调 → 与孤儿 / 后续 run 写入交错
  （同历史「telemetry 交错」问题）。故本次**不据 telemetry 给精确坐标 / 速度统计**。
- **结果**: 按用户肉眼记 `physical_finish_unofficial`（约 282s 穿越起点，**未经 telemetry 核验**）；
  supervisor 侧 `finish_reason=supervisor_stop`、`lap=0`、`final_rankings=[]`（沿用 checkpoint 不匹配判定）；
  session 实际跑到 `duration_sim=359.552s`。
- **现象**: 过弯比改动前**更宽**（P1 收过舵方向正确），但仍**系统性偏内侧**；最后一个弯仍轻擦栏杆，
  基本擦着通过。撞击太轻没触发脱困 → **未能观察脱困方向修复是否生效**。
- **结论/下一步**: 收过舵有效，但「内侧偏置 + 最后一弯」未解决；「太慢」疑为长时间近停拉低均值。
  下一步跑**带控制日志的干净基线（R002）**，用 `analyze_control_log` 区分慢的主因
  （加速限制 / 转向震荡压速 / 内侧偏置），再定向调
  `steering_speed_cap_scale` / `max_abs_steering` / `curve_slowdown`。

---

## 历史记录（旧格式，2026-06-11 之前，未编号）

> 以下为引入 Run ID 规范之前的流水记录，保留原文，不再追加；新测试一律走上面的新格式。

### 2026-06-10 Webots basic 调试

- 修复了直道上有效扫描点纵向跨度不足导致的假丢线：`min_y_span` 从 60 降到 30 后，6 到 8 个远处扫描点不再直接进入 lost。
- 右上角固定卡点的主要原因是车贴右侧护栏时，远处弯道项抵消了回中项。现在 `curve_risk` 可直接触发 hard_turn，并在回中项和远处项方向冲突时削弱远处项。
- 当前最好结果：非 debug 单文件控制器在 `basic` 上物理完成一圈。telemetry 显示 `t=288.187s` 从左侧穿过起点区域 `x=-19.498,y=122.6`，300 秒结束在 `x=-19.741,y=155.472`。
- 本地 metadata 仍显示 `timeout/laps=0`，原因是 SDK supervisor 的 checkpoint 坐标和 `track_basic.wbt` 实际赛道不一致。这里以 telemetry 轨迹作为实跑是否穿过赛道的证据。
- 尝试把全宽道路段放行到 `max_segment_width_ratio=1.0` 后，直道假丢线减少，但中心线过度居中，右上角再次贴外侧卡住，已回退。
- 最后采用的提速方式是：保留右上角/右下角的回中冲突抑制，只提高 lost/recovery 阶段速度，并给居中、高置信 hard_turn 小幅速度奖励。

### 2026-06-10 Webots complex 冒烟测试

- 使用当前 `submissions/final/team_controller.py` 直接跑官方 `track_complex.wbt`，单车 `car_1`，目标 1 圈。
- 结果：300 秒超时，`laps=0`，`status=normal`，重大碰撞 0。末帧位置 `x=107.595,y=143.495`，速度约 1.68。
- 过程里车辆没有被判严重碰撞或取消资格，问题更像是复杂赛道上路线效率和速度策略不足，而不是接口或沙箱错误。
- 当前 baseline 应标记为 `basic` 跑通，不能视为多赛道跑通。下一步需要专门针对 `complex` 调参数，至少先减少低速徘徊和回中/前瞻冲突导致的效率损失。

### 2026-06-10 Webots complex 分叉排查

- CP3 后失败点稳定出现在东北复合弯。车会从上方直道掉进内部环，再在 `x≈140,y≈145` 或 `x≈169,y≈110` 附近贴边低速。
- 临时测试过固定负向、正向、直行覆盖和 CP2->CP3 提前限速，都不能通过 CP3；这说明车到 CP3 时已经贴近护栏，单靠后段转向覆盖救不回来。
- 保存帧检查显示，CP3 附近道路 mask 填充率常到 0.68-0.74，几条道路被识别成一个超宽暗区。已把 `max_segment_width_ratio` 从 0.995 收紧到 0.90，并加入短时反打脱困；iter9 仍 timeout，末帧 `x=169.014,y=101.689`。
- 加入超宽道路段本地化后有改善：iter10 在 300 秒末到达 `x=97.884,y=155.443`，接近 CP4，但仍未完赛。调试帧显示 `t≈142s` 时观测点仍被内环道路拖到右侧，车继续掉入内部回路。
- 将超宽本地窗口全局收窄到 34% 后，practice 长跑能继续通过 CP4/CP5/CP6/CP7/CP8，但很慢，最终在起点前 `x≈-10,y≈-27` 卡住。这个版本在 300 秒 qualifying 内仍只到 CP4 附近。
- 试过把 CP3 贴右屏边的暗区锚到左边界附近：初始方向更像外圈上沿，但容易贴边后掉回内环，iter13 末帧 `x=144.900,y=90.478`。
- 试过低速稳定画面脱困：会在 CP3 低速阶段过早介入，iter15 practice 在 `x≈168,y≈116` 卡住，已回退。
- 试过 CP3 时间窗固定控制：正向/负向 `±0.45` 都会在 CP3 附近直接顶住；直行加速能让车保持在上沿 `y≈159`，但会卡在 `x≈145`，不能到 CP4。
- 试过 CP3 小幅负向覆盖：`-0.15` 能把车保持在 `y≈154`，但仍在 `x≈144` 附近低速卡住；延长覆盖到 170 秒会更早顶在 `x≈156,y≈157`，已回退。
- 试过右边界超宽段渐进左偏：会过早扰乱 CP2->CP3，iter17 在 `t≈152s` 还停留在 `x≈193,y≈146`，已回退。
- 试过提高 hard_turn 速度：iter16 在 `t≈139s` 卡在 `x≈141,y≈148`，说明问题不是单纯缺速度，而是 CP3 后目标线仍不可靠。
- 查官方 `track_complex.wbt` 和赛道文档后确认，CP3 后本来就是一组 T3/T4 复合弯，内侧回路不一定是错路。practice 能最终到 CP8，说明主要问题是多个顶边点耗时太长。
- 将高曲率卡边脱困从 42 帧提前到 18 帧，并把脱困速度提高到 0.62 后，iter18 在 300 秒末到达 `x=78.435,y=124.319`，已经过 CP4 往 CP5 方向走，比只到 CP4 附近的 iter10/12 更好。
- iter19 practice 用同一参数能过 CP5/CP6/CP7/CP8，但在起点前 `x≈-10,y≈-27` 长时间低速卡住。后半程已不是 CP3 路线问题，剩余关键是最终直道前的稳态卡边脱困。
- iter20 practice 加入低速稳态脱困后仍到最终卡点；阈值 0.06 太低，最终卡点速度约 0.18，触发不到。已把低速稳态阈值提高到 0.22，触发帧数保持 260，避免 CP3 正常慢弯过早介入。
- iter21 practice 使用低速阈值 0.22 后仍卡在最终点 `x≈-9.8,y≈-27.3`；推测是几何签名抖动超过 0.045，低速稳态脱困没有真正触发。下一版放宽签名稳定阈值。
- iter22 practice 使用签名阈值 0.10 后仍卡在最终点 `x≈-9.36,y≈-27.21`，说明要么触发后方向不对，要么反打力度不足。最终卡点车头几乎正向，下一步让低速稳态脱困使用固定正向转向，和急弯反打分开。
- iter23 practice 已复核固定正向低速脱困：它能在长时运行中走完整条 `complex` 物理路线，约 `t=902.336s` 接近 CP8，约 `t=981.248s` 回到起点区域，重大碰撞 0。问题是太慢，300 秒正式窗口内远未完成；本地 supervisor 的 `lap` 仍为 0，`metadata.finish_reason=supervisor_stop`，这和硬编码 checkpoint/窄起终点线有关，不能把它当线上完赛证据。
- 下一步应重点压缩 CP3->CP4、CP5->CP8 这些顶边耗时，而不是只修最后起点前卡点；不要再做 CP3 固定时间转向覆盖。
- iter30 提高急弯速度、降低弯道和转向降速后，300 秒末帧到 `x=78.603,y=56.009`，已过 CP4 并接近 CP5；这说明速度策略是有效方向。代价是 CP3 内侧仍会低速一段，但整体比 iter23 快很多。
- iter31/33 practice 显示后半程也明显加快：CP8 从 iter23 的 `t≈902s` 提前到 `t≈590-602s`。当前一圈物理路线已经能回到起终点前，约 `t=700s` 到 `x≈-10,y≈-27`。
- 新发现：本地单车配置只控制 `car_1`，其他 Webots 车辆仍停在发车格。iter33 的俯视图显示最终卡点前方有静止白车，右侧有静止黑车；这会挡住回到起点的车，不能完全当作策略没有脱困。后续如果要验证完整穿线，应使用所有车位都有控制器的配置，或明确把这个作为本地 supervisor/world 的测试限制记录。
- iter34 用 6 车位都加载同一控制器后，静止车阻挡消失，但多车会在 CP3/CP4 聚集互相影响，不适合评估单车路线速度。
- iter35 复制官方 `track_complex.wbt` 到 `.tmp/run/webots_tmp/worlds/`，只把 `car_2` 到 `car_6` 移到赛道外。结果：`car_1` 约 `t=603.520s` 到 CP8，`t=670.880s` 穿过起点区域并继续第二圈。结论是当前策略在无静止车阻挡时能物理跑完整个 `complex`，但距离 300 秒正式窗口还有很大差距。这个临时 world 只用于本地诊断，不作为官方提交依据。
- iter36 尝试进一步提速：提高 `hard_turn_speed/recovery_speed/correction_speed`、降低 `curve_slowdown/steering_slowdown`。结果退步，CP1/CP2/CP3 都变晚，300 秒末帧 `x=117.652,y=98.390`。已回退这些过激速度参数，保留 iter30/33 那组更稳的速度设置。
- iter37/38 尝试把提速限制在晚段：`late_speed_start=115s` 会拖慢 CP3->CP4，`late_speed_start=255s` 基本回到 iter30 水平，没有实际收益。已移除 late speed 逻辑，避免提交里留下无效复杂度。
- 用户触发复测使用当前 `submissions/final/team_controller.py`、官方 `track_complex.wbt`、单车 `car_1`。有效 telemetry 段从 `t=0.032` 到 `t=746.688`，没有 checkpoint/lap/finish 事件。`t=600` 左右车已回到起终点附近，随后在 `x≈-10,y≈-27` 低速停住；俯视图显示白车和黑车仍停在发车格，挡住了前方路线。本次按官方单车 world 判定未完赛，结束原因为手动中止；按无静止车临时 world 的旧记录，策略能物理绕完整条 complex，但用时约 671 秒，距离正式窗口仍太慢。
- 试过把道路段合并间隔从 90 全局降到 48，终点障碍帧离线扫描更干净，但 Webots 实跑在 CP3 退化，`t=210.944` 仍停在 `x=169.444,y=111.082`，已回退。
- 新版改成近处车身遮挡才收紧合并间隔：用下半部中间 ROI 的大连通域检测彩色、白色和黑色车身，只在低扫描线把 gap 降到 48。离线检查显示终点白/黑静止车帧触发，普通弯道和终点前空路不触发。
- 条件障碍版在官方 `track_complex.wbt` 单车 `car_1` 中能绕过原来的发车格静止车：约 `t=599.392` 回到起点区域，`t=611.616` 已到 `x=50.014,y=-28.729` 并继续向前，手动停止于 `t=639.168`。它解决了单车 world 的静止车阻挡，但 300 秒位置退到 `x=78.624,y=126.619`，比 iter30 慢，后续还要继续提速。
- basic 回归未过：单纯给近处障碍检测加时间门槛、把 stable-bias 脱困改成反打、以及把超宽道路本地化改成 red-world 门控，都不能恢复 basic 完赛。当前失败点从早期 `x≈-14,y≈255` 推进到 `x≈70,y≈275`，但仍沿上边界卡住。下一步应回调 policy 中相对 baseline 改动较大的 far/heading/curve 增益和速度限制，而不是继续加卡点脱困。
- 场景感知参数分流恢复了 basic：非红色场景用接近旧 baseline 的 policy 参数，red/complex 才启用超宽道路本地化和脱困状态机。`basic_scene_baseline_policy` 在官方 `track_basic.wbt` 上约 `t=288.192` 穿过起点区域并继续第二圈。
- 当前 final 也能在官方 `track_complex.wbt` 单车 `car_1` 上物理跑完一圈：`scene_complex_check` 约 `t=609.504` 到达起终点栅格 `x=45.029,y=-28.625`，之后继续前进。由于本地 supervisor 的 checkpoint/lap 计数仍显示 0，这里继续把 telemetry 坐标作为完赛证据；正式 300 秒窗口仍明显不够。
- 为避免 complex 后半程被静止车或道路遮挡帧误判成 basic，估计器现在会在连续红色环境帧后锁存 red environment 标记；timestamp reset 或测试显式 reset 会清空该标记，单帧误检不会污染整轮 basic。
- 连续红色环境锁存版 final 已复测：`basic_red_latch_check` 于 `t=287.520` 到达 basic 起点区域，`complex_red_latch_check` 于 `t=609.504` 到达 complex 起终点栅格。两次 telemetry 的 lap 仍为 0，原因沿用前面的本地 supervisor/checkpoint 计数问题；从物理轨迹看，basic 和 complex 都已完成一圈。

### 2026-06-11 单车优先拆分

- 已把近处车身检测拆到 `controller/opponent.py`，参数移到 `OPPONENT_PROFILE`，并把 `enable_opponent_avoidance` 默认设为 `False`。`perception.py` 默认不会调用对手车检测，主线只做道路分割和中心线估计。
- `basic` 复测无退化：官方 `track_basic.wbt` 单车 `car_1` 仍在 `t=287.520` 到达起点区域。
- `complex` 按“赛道上只有 car_1”复测：使用 `.tmp/run/webots_tmp/worlds/track_complex_car1_only.wbt`，只把 `car_2` 到 `car_6` 移出赛道，不改赛道几何。结果 `t=667.584` 到达起终点栅格，没有比此前官方 world + 静止车处理版的 `609.504` 更快，说明主要瓶颈仍在 CP3 和左侧低速点，不在末段车阵。
- 本轮第一次 complex 复测前，上一轮 basic Webots 没有退出，导致 telemetry 交错；已清理孤儿 Webots 进程并重跑 clean 版本。最终有效记录只含 `solo_opponent_off_complex_clean` 一个 team_id。
