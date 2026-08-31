# ROADMAP

项目全局路线：**大里程碑**。状态：`未开始` / `进行中` / `已完成` / `挂起`。细碎轨迹见 `docs\diary\`；方案详情见 `docs\proven\`。

## 阶段总览

| 阶段 | 目标 | 状态 |
| --- | --- | --- |
| 0 | 基础设施：个人 fork 分支维护 + 项目结构对齐 | 已完成 |
| 1 | Windows 测试：doctor + 冒烟 + 单元 190/190 | 进行中 |
| 2 | macOS 接管：mac-approve + 冒烟 + 单元/集成 | 未开始 |
| 3 | Linux（可选）+ 按需扩展 | 未开始 |

## 阶段 0：基础设施

个人 fork 远程（origin/mine）、`dev/work` 分支、三原语与总索引、docs 六目录。

## 阶段 1：Windows 测试

`./browser-harness --doctor` + 真实 Chrome 冒烟（`print(page_info())` 复用会话）+ 单元测试 190/190（修 9 个 Windows 环境用例）。

## 阶段 2：macOS 接管

`./browser-harness mac-approve`（Accessibility 授权）+ doctor + 冒烟 + 单元/集成全绿。

## 阶段 3：扩展

Linux 冒烟（Snap CDP 阻断见 `docs\snap-linux-headless.md`）+ 按需扩充 `agent-workspace\` / `examples\` / `.tools\`。
