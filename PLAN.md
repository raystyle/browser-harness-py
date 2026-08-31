# PLAN：当前目标实施计划

> 角色：**当前目标方案文档**——怎么做。分工：`TODO.md`=做到哪；本文件=怎么做；通用工作流见 `docs\guide\`。

## 当前目标：项目结构对齐 ohmyagents

> 对应 `GOAL.md`，登记日 2026-08-31。

### 1. 结构落盘

- 根目录三原语 + 总索引：`GOAL` / `PLAN` / `TODO` / `INDEX`，加 `ROADMAP` / `CHANGELOG`。
- `docs\` 六目录：`proven` / `diary` / `research` / `references` / `guide` / `mistakes`。
- 编号体系：P（方案归档，4 位）/ S（研究，3 位）/ R（参考，3 位）/ G（元规范，3 位）/ M（错误，分类 M1xx、行级 M0xx）。

### 2. 不改动

- 不移动 `src\browser_harness\` 源码、`tests\`、`install.md`、`SKILL.md`、`skills\`、`interaction-skills\`、`agent-workspace\`（避免破坏包导入、CLI 入口与 skill 引用）。

### 3. 验收

- `INDEX.md` 能完整定位当前代码与文档。
- `dev/work` 工作区干净并推送到 `mine`。

## 完成的定义

- 三原语 + `INDEX` + `ROADMAP` + `CHANGELOG` 落盘，并写入 `AGENTS.md`。
- `docs\` 六目录就位，`docs\guide\` 含 `template.md` 与 `G001`。
