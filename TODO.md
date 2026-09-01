# TODO：当前目标任务进度清单

> 角色：**当前目标的任务进度清单**。当天做的事只记 `docs/diary/`；当前目标完成后，过程与经验回填 `docs/proven/`。

## 当前目标

WSL2 无头接管（对应 `GOAL.md`，队列目标「Linux/macOS 接管」的 Linux 半），2026-09-01 完成；S006 落档。

## 任务进度清单

| 任务项 | 进度 | 说明 | 日期 |
| --- | --- | --- | --- |
| fork 分支维护 | 已完成 | mine 远程 + dev/work 分支 | 2026-08-31 |
| 项目结构对齐 | 已完成 | 三原语 + INDEX + docs 六目录 | 2026-08-31 |
| X 监控 rmux 自愈 | 已完成 | x_worker + x_supervisor + x_search | 2026-08-31 |
| 网页正文提取 | 已完成 | web-fetch（pydefuddle + 站点选择器 + 反爬升级） | 2026-09-01 |
| 搜索引擎 | 已完成 | google-search / bing-search + 翻页 | 2026-09-01 |
| 浏览器/应用资源视图 | 已完成 | browsers / current + tab 绑定互斥 | 2026-09-01 |
| 用户/agent 浏览器分离 | 已完成 | 独立 profile + BU_CDP_URL（S004、M101） | 2026-09-01 |
| rmux 原子隔离 | 已完成 | label 固定 + kill-server | 2026-09-01 |
| 打包 | 已完成 | uv tool install + 应用集成主包 | 2026-09-01 |
| 文档体系对齐 | 已完成 | AGENTS/GOAL/PLAN/TODO/ROADMAP + G002/G003 | 2026-09-01 |
| 升级闭环 v0.6.0 | 已完成 | --update 停栈/升级/铺装 workspace/恢复 x-monitor 一条命令 | 2026-09-01 |
| WSL 安装原生 Chrome | 已完成 | google-chrome-stable .deb 152（WSL 无 snap） | 2026-09-01 |
| launcher 行尾修复 | 已完成 | .gitattributes 钉 browser-harness/*.sh 为 LF | 2026-09-01 |
| agent 端口可配 + 无头启动 | 已完成 | BH_AGENT_CDP_PORT / BH_CHROME_HEADLESS / EXTRA_FLAGS 透传 | 2026-09-01 |
| browsers 视图 Linux 枚举 | 已完成 | /proc 扫描 + M104 cmdline 兼容 | 2026-09-01 |
| WSL 验证 | 已完成 | 单测 207 全绿 + doctor 全绿 + web-fetch/管道自动化实测 | 2026-09-01 |
| WSL x-monitor 登录 | 待办 | agent profile 需在 9224 登录 X 后 x-monitor 才可跑 | 待用户 |

## 队列目标

| 目标 | 状态 | 说明 |
| --- | --- | --- |
| Linux/macOS 接管 | Linux 半已完成 | WSL 无头栈全链路实测（S006）；macOS（mac-approve 等）仍排后 |
| 站点专用提取扩充 | 排后 | domain-skills 按站点定制正文提取 |
| MCP 集成 | 排后 | web-fetch / 搜索暴露为 MCP 工具 |
