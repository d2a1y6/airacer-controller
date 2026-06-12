# 文档索引

这里放流程文档和官方环境说明。当前状态不在本目录维护，先读 `experiments/STATUS.md`。

| 文档 | 负责什么 | 什么时候读 |
|---|---|---|
| `official_testing.md` | 官方 SDK、Webots、validator、run_local 的安装和命令 | 首次配环境、提交前验证 |
| `official_test_matrix.md` | 官方 world、车位、线上/本地测试入口和赛制静态清单 | 查赛道和测试入口 |
| `human_webots_testing.md` | AI 或人类跑 Webots，并保存控制日志、相机帧和观察结论 | 需要真实上车验证时 |
| `ai_offline_review.md` | AI 用 telemetry、控制日志、相机帧和 overlay 诊断一轮 run | 跑完后复盘机制 |

## 推荐阅读顺序

1. 新接手：先读 `experiments/STATUS.md`，再回到根目录 `README.md`。
2. 要跑 Webots：读 `human_webots_testing.md`。AI 日常迭代可以自跑，关键验收再请人类看。
3. 要分析一轮 run：读 `ai_offline_review.md`，再按需要看 `scripts/README.md`。
4. 要提交或跑官方校验：读 `official_testing.md`。
