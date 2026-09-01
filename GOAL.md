# GOAL：任务目标管理

> 角色：**工作任务管理**，四个部分——**起点**、**锚点**、**进程**、**历史**。随工作实时更新。
> 与其它文档分工：`ROADMAP.md`=阶段路线；`CHANGELOG.md`=版本成果；`docs/diary/YYYY-MM-DD-*.md`=项目日记；`docs/proven/PNNNN-*.md`=方案与过程经验；`TODO.md`=进度清单；`PLAN.md`=实施指导。

## 起点

- **日期**：2026-08-31。
- **起点**：browser-harness 作为个人 fork 引入，用于本地开发与测试。首期对齐 deepseek-harness 的 fork 分支维护方式（origin/mine、dev/work），再对齐 ohmyagents 的项目结构（三原语 + INDEX + docs 分类）。[实证: 2026-08-31 已建立 fork 与项目结构]

## 锚点

- **锚定的目标**：把 browser-harness fork 从「薄 CDP harness」扩展为「可封版的自愈浏览器应用集」，v0.2.0 已于 2026-09-01 封版。[实证: v0.2.0 tag 已推 mine]

### 推进时间线

> 倒序：最新进展在最上。

| 日期 | 进展 |
| --- | --- |
| 2026-09-01 | 会话 cookie 跨设备迁移（S007）：`cookies export/import` 插件（agent Chrome 间免重登迁移，修正 S004 旧结论的适用边界）；X 登录态 Windows→WSL 无头 Chrome 实测迁移成功 |
| 2026-09-01 | WSL2 无头适配（S006）：装原生 Linux Chrome 152、launcher 行尾修 LF、agent 端口可配（`BH_AGENT_CDP_PORT`，WSL 用 9224 避开 mirrored 网络下 Windows 侧 9223）、`BH_CHROME_HEADLESS` 无头启动、`browsers` 视图 Linux 枚举（M104 cmdline 重写坑）。本机 WSL `--doctor` 全绿、web-fetch/管道自动化实测通过、单测 207 全绿 |
| 2026-09-01 | v0.6.1–v0.6.3 升级可靠性三连修：文档统一以 `--update` 为首选；Windows 自更新改 pwsh 接力（原地自替换必败且失败会半拆安装，M102 第三形态）；版本缓存不再劫持升级判定（tag ≤ 已装即强制重拉，两次实证藏更新）。E2E 实证 0.6.2→0.6.3 接力全链路 |
| 2026-09-01 | v0.6.0 可靠升级闭环：`--update` 一条命令停栈（rmux+双daemon，M102 根治）→ uv 升级 @main → 铺装 skills/workspace → 恢复 x-monitor；up-to-date 路径同样铺装对齐；本机 E2E 通过 |
| 2026-09-01 | 独立主仓收官：v0.5.0 摆脱上游（origin 唯一）、v0.5.1 默认分支更名 main（`--update` 源与文档链接同步）、本机升级闭环、M102 落档、diary 补记 |
| 2026-09-01 | v0.2.0 封版：资源视图对齐——rmux 服务/会话/窗格状态、x-monitor 幂等 + 自愈、10 分钟空闲门控刷新、AGENTS/GOAL/PLAN/TODO/ROADMAP 对齐 ohmyagents 文档体系 |
| 2026-09-01 | 抓取能力增强：web-fetch 站点选择器 + 反爬自动升级、新 tab 抓完即关（不再污染 tab）、S005 对比研究落档 |
| 2026-09-01 | 应用集成进主包：x_worker/x_supervisor/x_search/page_text/agent_helpers 迁入 src/browser_harness，page-text 改名 web-fetch，start-x-monitor.ps1 并入 x-monitor，uv tool install 可用 |
| 2026-09-01 | 浏览器/应用资源视图：browsers（实例+tab+应用归属）、current（附加状态）、应用 tab 精确域名绑定互斥、用户/agent 浏览器分离（S004、M101） |
| 2026-09-01 | rmux 原子隔离：label 固定、kill-server、rmux_binary 优先本机安装（不与 ohmyagents 的 rmux 混用） |
| 2026-09-01 | 搜索引擎 + 翻页：google-search / bing-search（搜索→正文提取、--page N、Bing ck/a 链接解码） |
| 2026-08-31 | X 监控 rmux 自愈：x_worker + x_supervisor（心跳检测、kill+respawn）、x_search 查询/统计、空闲门控刷新、SQLite 去重 |
| 2026-08-31 | 网页正文提取：defuddle 三层回退 → 纯 Python（pydefuddle + bs4 fallback，去掉 npx） |
| 2026-08-31 | fork 分支维护 + 项目结构对齐（三原语 + INDEX + docs 六目录） |

## 进程

- 当前无现役切片（v0.2.0 已封版），待用户定向下一个目标。

## 历史

| 日期 | 目标 | 结果 |
| --- | --- | --- |
| 2026-09-01 | WSL2 无头接管（队列目标「Linux/macOS 接管」的 Linux 半） | 达成：WSL 自包含无头栈全链路实测（S006）；macOS 半仍排后 |
| 2026-09-01 | v0.2.0 封版：X 监控 + web-fetch + 搜索 + rmux 隔离 + 资源视图 + 打包 | 达成：tag v0.2.0 已推 mine/dev/work |
| 2026-08-31 | 个人 fork 分支维护（deepseek-harness 模式） | 达成：mine 远程 + dev/work 分支 + fork 工作流 |
| 2026-09-01 | 摆脱上游，独立主仓库 | 达成：origin=raystyle 唯一远程、默认分支 dev/work、身份文档更新（v0.5.0） |
| 2026-08-31 | 项目结构对齐 ohmyagents | 达成：三原语 + INDEX + docs 六目录 |

## 维护规则

- **起点**：开工时写一句「何时发起 + 为什么发起」。
- **锚点**：每完成一个节点补一行（日期 + 进展）。
- **进程**：只记当前目标；达成后整条移入「历史」。
- **历史**：日期 + 目标 + 结果，倒序。
- **日记与方案**：当天流水账进 `docs/diary/`；方案与过程经验进 `docs/proven/`。
