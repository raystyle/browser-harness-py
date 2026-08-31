# P0001 个人 fork 与分支维护

- 状态：已完成
- 日期：2026-08-31
- 关联：TODO 建立 fork 分支维护

## 背景与问题

browser-harness 作为个人 fork 用于本地开发与测试，需要与上游 `browser-use/browser-harness` 干净同步，并把个人工作推到 `raystyle/browser-harness`。

## 目标与非目标

- 目标：`origin`（上游只拉取）、`mine`（fork 推送目标）、`main`（上游镜像）、`dev/work`（开发分支）。
- 非目标：不改上游代码。

## 方案

参照 deepseek-harness：`git remote add mine https://github.com/raystyle/browser-harness.git`；`git switch -c dev/work`；`git push -u mine dev/work`；AGENTS.md 加 LOCAL-FORK-WORKFLOW 段。

## 实施过程与经验

- 完成 fork 远程与分支，`mine/dev/work` 已推送。
- 同步上游命令：`git switch main && git pull --ff-only origin main && git switch dev/work && git merge main`。

## 验收标准

- `git remote -v` 含 origin/mine；`git branch -vv` 显示 dev/work 跟踪 mine/dev/work。
