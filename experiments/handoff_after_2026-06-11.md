# Handoff：2026-06-11 R025 后

> `experiments/STATUS.md` 仍是唯一活动交接文档。本文只记录这轮相对上一份 handoff/STATUS 新增的工作，方便快速追溯。

## 这轮做了什么

1. 提交并验证了 Webots controller console 捕获能力（commit `313e882`）：调试构建会把 controller 进程的 `stdout/stderr` 写到 `.tmp/run/webots_console/*.log`，AI 可以 `tail -f` 实时看，跑完也能读。
2. 试了 R024 boundary escape 提前触发：把触发帧数缩短、速度门槛放宽、去掉 stable view 要求。结果 complex 仍在多个位置长时间近停，尤其 `x≈169,y≈111` 旧窗口复现。该策略改动已撤回。
3. 做了 R025 白线取证：用 `--frame-window 130 185` 补存关键窗口相机帧，渲了 7 组 overlay/stereo。结论是 `135-185s` 控制日志里 `line_conf=0`，不是 policy 压低白线优先级，而是白线感知链路没有给出可用目标。
4. 新增跳点取证工具：
   - `scripts/make_teleport_world.py`
   - `scripts/webots_jump_run.sh`
   - `tests/test_make_teleport_world.py`

   它可以从已有 telemetry 的某个时间点生成临时 world，把 `car_1` 放到相近 `x/y/heading` 后只跑几秒取相机帧。
5. 清理 `.tmp`：从约 700MB 清到约 18MB，只保留颜色采样、R024 小预览和 R025 关键日志/overlay。

## 效果

- console 捕获有效，后续能第一时间看到 controller 侧提示。
- R024 证明“更早 escape”不是解法，继续堆脱困逻辑会偏离主问题。
- R025 把问题缩小到白线感知链路：关键窗口没有 `line_conf`，所以“保持白线在车中间”的策略没有输入。
- 跳点工具 smoke test 通过，适合快速补视觉证据；它不是完整状态恢复，不能当正式验证。

## 现在还有的问题

- complex 还不能 merge 到 main。R024 已经证明旧低速/内切窗口仍会复现。
- 车在弯里仍可能没有把白线保持在车身中心，核心证据是 R025 的 `line_conf=0`。
- `380-420s` 另有大 offset 白线候选被拒绝的情况，需要确认是真白线被误拒，还是护栏/白车被正确过滤。
- basic 只保留 R023 短跑正常结论；下一次改白线感知后还要回归 basic。

## 继续时先看哪里

1. `experiments/STATUS.md`
2. `experiments/notes.md` 的 R024/R025
3. `.tmp/r025_line_priority_run/line_window_preview/`
4. 需要补画面时用：

```bash
bash scripts/webots_jump_run.sh complex 144 --duration 5 --frames 1 \
  --telemetry .tmp/r025_line_priority_run/telemetry.jsonl
```

正式策略验证仍从头跑：

```bash
bash scripts/webots_run.sh complex
```
