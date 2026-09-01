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
| cookie 跨设备迁移 | 已完成 | cookies export/import 应用（S007），X 登录态 Windows→WSL 实测迁移成功 | 2026-09-01 |
| WSL x-monitor 登录 | 已完成 | cookie 导入即登录（S007）；Windows 侧停栈后 WSL 侧 x-monitor 已接管实跑（首分钟 24 推入库、11 分钟 +27 推）；验证完成后用户叫停全栈，profile 登录态保留、随起随用 | 2026-09-01 |
| Windows 无头复测 | 已完成 | R004 路径 A 实证：无头拉起 9223（HeadlessChrome/154 UA）→ doctor 全绿 → x-monitor 直接接管 → 两轮 1062→1064；顺修 M105（单测平台依赖，双平台复跑绿） | 2026-09-01 |
| v0.6.6 发版 | 已完成 | 预检四件套全绿（215 单测/symlink 零/树净/版本就绪）→ tag + Release「三平台无头接管与 chrome-mode 双模切换」→ 本机升级 0.6.6 + skills resync；M107 修复随版，M108（API 限流误报 up to date）当日记档 | 2026-09-01 |
| macOS 无头接管验收 | 已完成 | R005 四条全过（无头拉起 / cookie 导入登录 / doctor 全绿 / 两轮增量 25→42）；Linux/macOS 接管队列目标收口（S008） | 2026-09-01 |
| chrome-mode 双模切换 | 已完成 | 用户定向落地：`chrome-mode status\|headed\|headless`，翻转 = .env 重写 + pid 精确停 Chrome + 双 daemon 重启 + x-monitor 恢复；macOS 往返翻转实证；登录录入标准姿势 = headed 人工登录（S008） | 2026-09-01 |
| browsers 视图 Darwin 枚举 | 已完成 | `ps -axo` 扫描 + 首 flag 前头部识别二进制（路径含空格）；Mac 实测列实例/tab/rmux | 2026-09-01 |

## 队列目标

| 目标 | 状态 | 说明 |
| --- | --- | --- |
| Linux/macOS 接管 | 已完成 | WSL 半（S006/S007）+ Windows 复测（R004）+ macOS 半（R005 验收全过、S008 钥匙串发现 + chrome-mode 双模）三侧闭环，2026-09-01 收口 |
| chrome-mode 翻转双拉起竞态 | 待观察 | 首次翻转后偶见 Chrome 二次拉起（flip 与 x-monitor 恢复各自 ensure 疑似竞态），后续翻转未复现；复现则修（S008 遗留） |
| --update 限流误报 up to date | 排后 | M108：API 403 时缓存回退伪装成"确认无新版"；修复方向 = 显式 --update 失败时告警 + --force 旁路 |
| agent Chrome 独立应用身份 | 排后 | macOS 同 bundle 双实例 Dock 激活混淆（无头实例顶包用户 Chrome）；候选解 = 独立副本改 CFBundleIdentifier（S008 遗留） |
| 站点专用提取扩充 | 排后 | domain-skills 按站点定制正文提取 |
| MCP 集成 | 排后 | web-fetch / 搜索暴露为 MCP 工具 |
