# TODO：当前目标任务进度清单

> 角色：**当前目标的任务进度清单**。当天做的事只记 `docs\diary\`；当前目标完成后，过程与经验回填 `docs\proven\` 对应方案。

## 当前目标

browser-harness 测试（Windows 收尾 + macOS 接管），对应 `GOAL.md`，登记日 2026-08-31。

## 任务进度清单

| 任务项 | 进度 | 说明 | 日期 |
| --- | --- | --- | --- |
| Windows doctor | 已完成 | chrome running / daemon alive / 1 连接 | 2026-08-31 |
| Windows 真实 Chrome 冒烟 | 已完成 | page_info 返回真实标签页（会话复用） | 2026-08-31 |
| Windows 单元测试 | 进行中 | 181/190，9 个 Windows 环境失败待修 | 2026-08-31 |
| Windows 只读冒烟扩展 | 待办 | list_tabs / js / 截图 | — |
| 集成测试 test_js.py | 待办 | mock，无需 CDP | — |
| 修 9 个 Windows 用例 | 待办 | killpg / symlink / SKILL.md 软链 → skipif(win32) | — |
| macOS 接管 | 待办 | 环境 + mac-approve + 冒烟 + 单元/集成 | — |
| Linux（可选） | 待办 | 冒烟 + 单元（Snap CDP 阻断） | — |

## 队列目标

（暂无）
