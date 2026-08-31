# ROADMAP

项目全局路线：**大里程碑**。状态：`未开始` / `进行中` / `已完成` / `挂起`。细碎轨迹见 `docs\diary\`；方案详情见 `docs\proven\`。

## 阶段总览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 0 | 基础设施：个人 fork 分支维护 + 项目结构对齐 | 已完成 |
| 1 | 与上游保持干净同步 + 本地开发验证 | 进行中 |
| 2 | 按需扩展：agent-workspace 领域技能 / examples / 工具脚本 | 未开始 |

## 阶段 0：基础设施

个人 fork 远程（origin/mine）、`dev/work` 分支、三原语与总索引、docs 六目录。

## 阶段 1：同步与验证

用 `git switch main && git pull --ff-only origin main && git switch dev/work && git merge main` 保持与上游同步；用 `./browser-harness --doctor` 与 `uv run --with pytest python -m pytest tests/unit -q` 做本地验证。

## 阶段 2：扩展

按需扩充 `agent-workspace\domain-skills\`、`examples\`、`.tools\` 脚本。
