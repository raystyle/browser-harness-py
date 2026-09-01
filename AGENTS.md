# AGENTS.md

本文件是协作规则的**最高约束**，四段职责依次为：**项目定位**、**操作规则**、**意图路由**、**资源索引**。

## 一、项目定位

> 本项目的本质与边界。根为定位，下分本质、边界、管理对象、方案索引、fork 工作流。

1. **本质**
   - browser-harness 是把 LLM 直接连到真实浏览器的薄 CDP harness：一个 CDP websocket，agent 边做边写缺失的 helper。
   - 本仓是 `browser-use/browser-harness` 的个人 fork，个人工作推到 `raystyle/browser-harness`。

2. **边界**
   - 连接模型：默认 daemon、`BU_CDP_URL` / `BU_CDP_WS`（独立 automation Chrome），纯本地，无 cloud。
   - **用户浏览器与 agent 浏览器分离**：agent 只操作独立 `agent-chrome-profile`（9223），永不碰用户的 `Profile 3`（见 S004）。
   - 核心代码在 `src/browser_harness/`；agent 可编辑区在 `agent-workspace/`。

3. **管理对象**
   - 浏览器实例（agent / user）+ tab（应用绑定 X / Google / Bing）。
   - rmux 服务 / 会话 / 窗格（`-L browser-harness` label，原子隔离）。
   - 推文数据（`x_tweets.db`，SQLite 去重）。

4. **方案索引**
   - 定位 / 归档：`docs/proven/`；研究：`docs/research/`；参考：`docs/references/`；错误：`docs/mistakes/`。
   - 唯一索引：`INDEX.md`。

5. **fork 工作流**
   - `origin`（上游只拉取）、`mine`（fork 推送）、`main`（上游镜像，不直接改）、`dev/work`（开发分支）。
   - 规则：不推 `origin`；在 `dev/work` 开发；合并上游用 `git switch main && git pull --ff-only origin main && git switch dev/work && git merge main`；本地验证 `browser-harness --doctor` + `uv run --with pytest python -m pytest tests/unit -q`。

## 二、操作规则

> 两类场景：**工作节奏**（何时做什么）与**写作编码**（写什么按什么标准）。

### 工作节奏

1. **每轮对话**
   - 可以：先核对三原语 `GOAL.md`、`TODO.md`、`PLAN.md`；实质推进当场更新 todo 与 plan。
   - 禁止：不核对三原语就干活；偏离当前目标；推进了不更新 todo/plan。

2. **踩坑时**
   - 可以：当场按当前最大号接编 MNNN，落 `docs/mistakes/` 对应分类文件一行；同根因合并进已有条目（保留最早编号）；主题深挖落 `docs/research/`。
   - 禁止：只留在对话里反复试错。

3. **发现问题时**
   - 可以：走五步闭环——**定位**（先搜 `INDEX.md` 与相关文档）→ **归类**（文档错修文档、规则缺补规则、知识缺落研究、出错记 mistakes、验证过沉淀 references）→ **修正**（改源头，下游引用/索引/三原语同步）→ **验证**（`pytest` + 对账 INDEX 与磁盘）→ **提交**（一事一提交，diary 记钩子）。
   - 禁止：跳过定位直接改；只修表象不回写体系；问题只留在对话或记忆里。

4. **交付变更时**
   - 可以：改代码同步对应文档，改文档同步索引与 `docs/diary/`；遵守命名标准。
   - 禁止：只改代码不落文档；改了文档不更新索引。

5. **经验沉淀时（强规则，G004）**
   - 可以：成功的 plan 沉淀归 `docs/proven/`（方案与过程）；研究被实证后的做法与多次错误后沉淀成的正确工作流进 `docs/references/` 并挂意图路由；错误踩坑当场记 `docs/mistakes/`（同根因聚合）；同型坑二犯以上把正确处理升格成 references 工作流并互指。
   - 禁止：`[经验]` 断言只留在研究文档不落 references；错误只记现象不记根因与处理；`[推断]`/`[假设]` 跳级进 references；一条知识两个权威落位互相重复。

6. **提交时**
   - 可以：`feat:` / `docs:` / `fix:` / `chore:` 前缀加中文描述；一次提交只做一件事。
   - 禁止：多事混一提交；未经指示推远端。

### 写作编码

7. **执行命令与写文件时**
   - 可以：Windows 用 PowerShell 7（`pwsh`）；源码 / 文档 UTF-8。
   - 禁止：Windows 默认用 `powershell.exe` 5.1。

8. **写 Python 时**
   - 可以：用 `uv` 管理依赖；优先复用现成库（`cdp-use`、`pydefuddle`），最少代码组合，不重复造轮子。
   - 禁止：在现成库已能稳定完成时从零实现；一次拉一堆用不上的依赖。

9. **写文档时**
   - 可以：遵守 `docs/guide/G001-*.md`（文件名即标题、标题干净、无装饰符号）。
   - 禁止：标题带括号 / 破折号 / emoji / 箭头。

10. **写研究与测试文档时**
   - 可以：事实性断言标六态之一——`[实证]`（本机实测）、`[推断]`（逻辑推出）、`[经验]`（历史惯例）、`[记忆]`（待复核）、`[假设]`（待验证）、`[直觉]`（主观倾向）；标准见 `docs/guide/G002-*.md`；关键结论不标六态即视为未完成。
   - 禁止：把「没验证」写成「已验证」；断言不标六态；用猜测冒充结论。

11. **写测试时**
    - 可以：`uv run --with pytest python -m pytest tests/unit -q`；单元测试优先，集成测试需 live browser 按需跑；期望值来自独立来源。
    - 禁止：只测 happy path；期望值来自被测同款逻辑（重言式断言）。

### 交互原则（本仓特有）

12. **动用户桌面 / 浏览器时**
    - 可以：非阻塞、渐进、向导式——先告知 → 用户授权 → 确认 → 继续；Chrome 144+「Allow remote debugging?」授权先提示用户点 Allow。
    - 禁止：突然抢焦点；默默阻塞等弹窗；弹窗未应答时空轮询重试。

## 三、意图路由

> 需求意图 → 命令映射。命令细则见 `SKILL.md`。

- **核对照 / 诊断**：`browser-harness --doctor`（chrome / daemon / 连接 / rmux 状态）
- **X 持续监控**：`browser-harness x-monitor`（幂等：启动独立 Chrome + rmux supervisor/worker；10 分钟空闲门控刷新）
- **查 / 搜已存推**：`browser-harness x-search --stats|--recent|--since|关键词`
- **网页正文**：`browser-harness web-fetch <url> --text|--json|--current`
- **搜索**：`browser-harness google-search|bing-search <query> [--page N]`
- **rmux 管理**：`browser-harness rmux list|ensure|status|capture|kill|kill-server`
- **资源视图**：`browser-harness browsers`（浏览器实例 + tab + rmux）、`browser-harness current`（附加状态）
- **安装**：`uv tool install git+https://github.com/raystyle/browser-harness@dev/work`
- **查文档**：先搜 `INDEX.md` 定位编号，再读文件。

## 四、资源索引

> 唯一索引 `INDEX.md`（编号表、目录结构、代码文件位置）。本节是配合 INDEX 的搜索方法。

**速记**：前缀 `P`（proven 归档）/ `S`（research 研究）/ `R`（references 参考）/ `G`（guide 元规范）/ `M`（mistakes 错误；文件 M1xx、行级 M0xx）；根目录三原语 `GOAL` / `PLAN` / `TODO`。

**搜索方法（文档）**：

```powershell
rg -n "关键词" INDEX.md                    # 1 先搜总索引，定位编号或文件
rg --files docs | rg 关键词                 # 2 按文件名搜文档
rg -n "关键词" docs\research docs\references # 3 全文搜研究参考
rg -n "关键词" docs\mistakes\               # 4 搜错误处理

# mq（markdown 结构查询，D:\ohmyenv\mq\mq.exe，jq 风格；section 模块必须 -A）
mq -F grep '.h2' docs\research\*.md         # 跨文件按节标题定位
mq -A 'section::section(., "关键结论")' 文档  # 抽整节内容
```

## Security

- 不提交 secrets、会话 cookie（`agent-chrome-profile/` 已 gitignore）。
- 最小改动修 bug，不扩大 CDP surface。
