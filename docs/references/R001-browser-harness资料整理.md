# R001 browser-harness 资料整理

> 开发测试参考（要做什么、怎么做）。登记日 2026-09-01。
> 来源：Google 搜索（browser-harness google-search）+ 上游仓库与社区文章。

## 官方资源

| 资源 | 地址 | 说明 |
| --- | --- | --- |
| Python 主仓库 | https://github.com/browser-use/browser-harness | 本 fork 的源，核心 harness（CDP daemon + helpers + agent-workspace） |
| JS 版 | https://github.com/browser-use/browser-harness-js | Node 版（`npx skills add ... --skill cdp`） |
| Windows 版 | https://github.com/browser-use/windows-harness | 面向 PC 全任务的 harness（更新方向） |
| 安装指南 | https://github.com/browser-use/browser-harness/blob/main/install.md | `uv tool install` + chrome://inspect 远程调试 |
| 技能文档 | https://github.com/browser-use/browser-harness/blob/main/SKILL.md | agent 操作路由（browser-use skill） |
| 技术文档 | https://deepwiki.com/browser-use/browser-harness | DeepWiki 生成的安装/架构解读 |
| 官网 | https://browser-harness.com | 官方站点 |
| Browser Use CLI | https://docs.browser-use.com/open-source/browser-use-cli | 云/开源 CLI 文档 |

## 中文技术解读

- 《Browser Harness：让 AI 直接接管真实浏览器的轻量自愈执行层》— silenceper.com（2026-04-21）
  https://silenceper.com/article/2026-04-21-browser-harness-ai-browser-control/
- 《Browser-Harness：让 LLM 直接「驾驶」真实浏览器的自愈式 CDP 工具》— DeepSeek 技术社区（CSDN）
  https://deepseek.csdn.net/6a31fd32662f9a54cb802bea.html
- 《600 行代码统治浏览器：Browser Harness 如何让 AI 智能体获得完全自由》— 腾讯云开发者社区（2026-04-29）
  https://developer.cloud.tencent.cn/article/2663247
- AI 原生全景图 — browser-harness 条目
  https://landscape.jimmysong.io/zh/projects/browser-harness/

## 视频

- 《Browser Use Harness Changed AI Agents (Hermes, Claude...)》— YouTube（2026-05-07）
  https://www.youtube.com/watch?v=xleOmMsnwjY

## 第三方目录 / 安全提示

- heyclau.de 工具目录：https://heyclau.de/entry/tools/browser-harness
  - 安全提示：远程调试可能暴露当前登录会话、扩展、书签；安装前先读源码与安全说明。

## 核心设计（供本项目对照）

- 一句话哲学：One websocket to Chrome, nothing between（把 CDP 直接交给 LLM，不套框架）。
- 结构：`browser-harness` CLI + CDP daemon + helpers + `agent-workspace/`（agent 可写区）。
- 技能系统（Domain Skills）：按站点沉淀操作知识，`BH_DOMAIN_SKILLS=1` 启用。
- 隔离自动化：`--remote-debugging-port` + `BU_CDP_URL` 连接独立 Chrome；云浏览器用 Browser Use Cloud。
