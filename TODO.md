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
| daemon 单实例守卫 | 已完成 | Issue #1 / M109：内核锁（flock/LockFileEx，进程死自动释放）+ claim 争抢语义（让位/等待/接管）；单测 222 绿 + 本机 E2E 三分支；启动路径收敛为仅经 CLI | 2026-09-02 |
| stdin 与命令模式双兼容 | 已完成 | Issue #2：`run_app()` 通用子命令桥 + `web_fetch()` 别名（默认对齐 CLI）+ R003 双模式条款；单测 227 绿，真栈验证随发版自验 | 2026-09-03 |
| v0.6.7 发版 | 已完成 | 预检四件套全绿（227 单测/symlink 零/树净/版本就绪）→ tag + Release「daemon 单实例守卫与管道命令双模式对齐」→ 本机 `--update` 升 0.6.7（M108 未犯、尾部输出落地版本）+ doctor 绿 + stdin 真栈（run_app/web_fetch 过冷启动 daemon，M109 健康拉起活体复核）；README 五处随版对齐 | 2026-09-03 |
| 任务生命周期三分类 + 闲置看门狗 | 已完成 v0.6.9 | 用户定向：持久（默认，`BH_IDLE_TIMEOUT` 默认 30 分钟闲置自退 + 末位 daemon 连带关 agent Chrome，x-monitor 轮询自动续活）/ 批量 `--batch` / 一次性 `--once`（调用级 teardown，只拆自己冷启动的栈，已在跑的栈永不被动）；顺修 restart_daemon Windows 死等误判（os.kill(pid,0)=CTRL_C_EVENT 换 OpenProcess 探活）与 cleanup_endpoint unlink 竞态；+11 单测 248 绿，dev 真栈三场景实证；一例未解之谜挂待观察 | 2026-09-03 |
| v0.6.9 发版 | 已完成 | 发版前全量验收矩阵全绿（全树 265 / 生命周期三场景 / 带栈翻转往返 / M109 复用 / x-monitor 长跑型 / 七插件 happy-path）→ tag + Release「任务生命周期三分类与翻转竞态修复」→ 本机 `--update` 升 0.6.9 + doctor 版本对齐 + 装机 CLI `--once` 用完即清实证 | 2026-09-03 |

## 队列目标

| 目标 | 状态 | 说明 |
| --- | --- | --- |
| agent-workspace 更名 browser-workspace | 已完成 | 用户定向 + 二次缩范围（profile 一族不动）；C1 核心（env 回退链 + 整目录自动迁移 + 模块垫片）/C2 repo 119 文件迁移/C3 文档三副本/C4 发版 v0.6.8；真机迁移自验：123 文件与 x_tweets.db 字节级随迁、旧目录消、profile 未动、x-search 读到全量 1064 推、doctor 绿、stdin 冒烟过；单测 conftest BH_HOME 隔离顺带根治存量隐患，234 绿 | 2026-09-03 |
| dev 环境 Windows 侧真栈姿势 | 已完成 | launcher 按 uname 分家 BH_HOME（Windows→`.browser-harness-dev-win`，端口 9225；WSL 留原目录 9224）；Windows 侧 `./browser-harness` 真栈 stdin 一次过（daemon 冷启动 + 无头 Chrome + 真导航），装机栈 9223 不受扰；沉淀 R006（端口分配全景 9223/9224/9225）；单测侧隔离由 v0.6.8 conftest 先行根治 | 2026-09-03 |
| Linux/macOS 接管 | 已完成 | WSL 半（S006/S007）+ Windows 复测（R004）+ macOS 半（R005 验收全过、S008 钥匙串发现 + chrome-mode 双模）三侧闭环，2026-09-01 收口 |
| chrome-mode 翻转双拉起竞态 | 已完成 v0.6.9 | 根因两层：翻转不杀 rmux 栈（活 worker 复活 daemon 撞停/拉窗口）+ 拉起原语无互斥；修复 = 翻转先静默 rmux 会话再动 daemon/Chrome + `_launch_agent_chrome` 挂 M109 同款内核锁（败者等赢者）；+3 单测，dev 栈真栈实证（静默序正确、9223/9225 各恰一实例、栈恢复）；S008 遗留销项 | 2026-09-03 |
| --update 限流误报 up to date | 排后 | M108：API 403 时缓存回退伪装成"确认无新版"；修复方向 = 显式 --update 失败时告警 + --force 旁路 |
| cookies export 默认 endpoint 硬编码 | 排后 | export 默认 `http://127.0.0.1:9223`，与 import 取 `BU_CDP_URL` 不一致；dev/WSL（9224/9225）场景需显式 `--endpoint`；统一为 `BU_CDP_URL` 回退 9223 | 2026-09-03 |
| agent Chrome 独立应用身份 | 排后 | macOS 同 bundle 双实例 Dock 激活混淆（无头实例顶包用户 Chrome）；候选解 = 独立副本改 CFBundleIdentifier（S008 遗留） |
| 站点专用提取扩充 | 排后 | domain-skills 按站点定制正文提取 |
| MCP 集成 | 不做 | 用户定向 2026-09-03 出队；`mcp_server.py` 与 pyproject optional 依赖保留现状不删 |
