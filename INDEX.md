# INDEX：项目总索引

> 角色：全仓**唯一索引**——只做定位：编号表、目录结构、代码文件位置。规则权威源见 `AGENTS.md`；命名与编号见 `docs\guide\G001-文档标准细则-命名写作规范.md`。

## 一、编号体系

**前缀定位**：`P`（proven，已完成方案归档，4 位）；`S`（research，研究原型过程，3 位）；`R`（references，开发测试参考，3 位）；`G`（guide，元规范，3 位）；`M`（mistakes，分类文件 M1xx、行级 M0xx）。根目录三原语：`GOAL`（目标轨迹）/ `PLAN`（当前目标方案）/ `TODO`（进度清单）。

**目录职能**：`proven` 已完成方案归档；`diary` 一天一篇总结自省；`research` 研究原型过程（为什么）；`references` 开发测试参考（要做什么、怎么做）；`guide` 元规范（含 `template.md`）；`mistakes` 出错怎么纠。

## 二、目录结构与代码文件位置

| 类别 | 目录 | 说明 |
| --- | --- | --- |
| 文档 | `docs\`（proven / diary / research / references / guide / mistakes）+ 根目录 GOAL / PLAN / TODO / INDEX / AGENTS / README / CONTRIBUTING / CHANGELOG / ROADMAP | 见上节 |
| 代码 | `src\browser_harness\` | Python 包（admin / daemon / helpers / run 等） |
| 配置 | `pyproject.toml` | 依赖与打包（uv / setuptools，`requires-python >=3.11`） |
| 测试 | `tests\` | `unit`（无浏览器）+ `integration`（需 CDP） |
| 技能 | `skills\` / `interaction-skills\` / `agent-workspace\` | skill 与 agent 可写区 |
| 示例 | `examples\` | 研究/验证用 POC 探针（不参与打包） |
| 入口 | `browser-harness` / `mcp_server.py` | 本地启动器与 MCP 服务 |

**代码文件位置**：

| 文件 | 职责 |
| --- | --- |
| `src\browser_harness\run.py` | `browser-harness` CLI 入口 |
| `src\browser_harness\admin.py` | daemon 生命周期、诊断、更新、profile |
| `src\browser_harness\daemon.py` | 浏览器与 agent 之间的长驻中间进程 |
| `src\browser_harness\helpers.py` | CDP 封装与浏览器原语 |
| `src\browser_harness\xapps.py` / `browsers.py` / `rmux.py` | 应用子命令 / 资源视图 / rmux 集成 |
| `src\browser_harness\x_worker.py` / `x_supervisor.py` / `x_search.py` | X 监控 worker / 自愈 supervisor / 推文查询 |
| `src\browser_harness\web_fetch.py` / `agent_helpers.py` | 网页正文提取 CLI / agent 辅助函数 |
| `src\browser_harness\_ipc.py` / `paths.py` / `macos.py` / `recorder.py` / `video.py` / `video_render.py` | 支撑模块 |
| `mcp_server.py` | MCP stdio 工具暴露 |
| `tests\unit\` / `tests\integration\` | 分层测试 |
| `examples\poc-os-input.py` | OS 级输入 vs CDP 输入域泄漏实证（S001 依据，Windows） |

## 三、方案归档

| 编号 | 文件 | 主题 |
| --- | --- | --- |
| P0001 | `P0001-个人fork与分支维护.md` | origin/mine、dev/work、fork 工作流 |
| P0002 | `P0002-独立agent浏览器与rmux原子隔离.md` | 独立 Chrome + BU_CDP_URL + rmux label 隔离 |

## 四、项目日记

- `2026-08-31-建立fork工作流与项目结构.md`
- `2026-09-01-从封版到独立主仓库.md`
- `2026-09-02-daemon单实例守卫.md`

## 五、研究 / 参考 / 元规范 / 错误

- 研究（S）：`S001-patchright与CDP-Patches集成研究.md`、`S002-rmux集成研究.md`、`S003-defuddle网页正文提取研究.md`、`S004-用户浏览器与agent浏览器隔离研究.md`、`S005-抓取内容提取能力对比研究.md`、`S006-WSL2无头环境适配研究.md`、`S007-会话cookie跨设备迁移研究.md`、`S008-macOS无头接管与钥匙串登录态持久化研究.md`
- 参考（R）：`R001-browser-harness资料整理.md`、`R002-浏览器隔离与抓取工作流.md`、`R003-插件开发与测试规范.md`、`R004-Windows无头模式测试指引.md`、`R005-macOS无头模式接管验收指引.md`
- 元规范（G）：`G001-文档标准细则-命名写作规范.md`、`G002-研究标准细则-结构与六态标记.md`、`G003-工作流标准细则-从登记到归档五步.md`、`G004-经验沉淀细则-成功与错误经验分治.md`、`template.md`
- 错误（M）：`M101-Chrome的user-data-dir引号导致profile污染.md`、`M102-CLI升级前运行中的进程锁住venv.md`、`M103-uv-tool-uninstall删除dangling环境连带shim目录.md`、`M104-Linux下Chrome重写cmdline导致NUL切分失效.md`、`M105-单测字符串比对路径在win32失效.md`、`M106-symlink条目在Windows编辑后目标变成整份正文.md`、`M107-CRLF检出致skills哈希永不相等.md`、`M108-匿名API限流403被误报为up-to-date.md`、`M109-daemon无单实例守卫致同机多实例并存.md`

## 六、阶段与版本

- `ROADMAP.md`：阶段路线
- `CHANGELOG.md`：版本里程碑
