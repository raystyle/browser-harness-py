# M107 CRLF 检出致 skills 哈希永不相等

> 分类：跨平台仓库卫生（与 M106 同族：仓库字节形态跨平台必须确定）。首犯发现 2026-09-01（Windows 拉取 Mac 侧 S008 提交后回归）。

## 现象

Windows 上 `uv run pytest tests/unit` 挂 `test_skills_sync::test_sync_creates_and_updates`：同步后副本哈希 `6be65309…` ≠ 打包源 `081b28cb…`。更严重的是生产面：`browser-harness skills` 对 claude/codex 永远报 OUTDATED，`skills sync` 完再查还是 OUTDATED——同步永远"没完成"。Mac/WSL 侧全绿（221 passed），纯 Windows 检出环境才爆。[实证: 2026-09-01 本机 `skills sync` 前后对照]

## 根因

两层叠加：

1. `.gitattributes` 只钉了 `browser-harness` 启动器与 `*.sh` 为 LF；`SKILL.md`/`*.md`/`*.py` 未钉。Windows `core.autocrlf=true` 检出时 smudge 成 CRLF。
2. `skills.py::_skill_hash` 按**原始字节**哈希，而 `_sync_tree` 对 SKILL.md 做 LF 规范化写出（`read_text` 通用换行 + `write_text(newline="\n")`）→ 源（CRLF）与副本（LF）字节永不相等。

链条：Mac 侧 LF 提交 → Windows pull 物化 CRLF → 哈希按字节 → 误报 OUTDATED。单测只是这个生产 bug 的第一个显形点；此前 Windows 侧绿是因为工作树 SKILL.md 恰好已是 LF 形态（未被重物化过）。

## 处理

三管齐下（2026-09-01）：

- `.gitattributes` 钉全仓 `* text=auto eol=lf`（二进制自动探测，`*.png binary` 显式兜底）——任何平台检出字节一致；`git add --renormalize` 顺带修正 `.gitignore` 历史混入的 7 行 CRLF。
- `skills.py` 新增 `_norm_bytes`（文本后缀 `.md`/`.py` 折 CRLF→LF）用于 `_skill_hash` 与 `_provision_diff/_provision_sync`——对 editable install（用户侧 autocrlf 各异）也免误报。
- 回归测试 +2：`test_sync_tolerates_crlf_checkout`（CRLF 源 sync 后哈希相等 + provision 换行无差）、`test_repo_skill_copies_are_real_files`（三副本与打包树禁 symlink，M106 防复发）。Windows 215 passed / 9 skipped。

## 预防

- 仓库字节形态跨平台必须唯一：`.gitattributes` 全仓钉 eol，别只钉启动器（M102 的 `bash\r` 是同一族的前哨）。
- 哈希/比较内容前先问：字节比较还是语义比较？文本内容跨环境流转，一律换行归一。
- 新平台首次检出即跑全量单测——本坑在 Mac 侧永远不显形，Windows 拉取后 30 秒就抓到了。
