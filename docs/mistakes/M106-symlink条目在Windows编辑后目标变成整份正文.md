# M106 symlink 条目在 Windows 编辑后目标变成整份正文

> 分类：跨平台仓库卫生。首犯发现 2026-09-01（Mac 首次真 POSIX clone），病灶自 fork 基线前就存在。

## 现象

macOS `git clone` 报 `unable to create symlink skills/browser-harness/SKILL.md: File name too long`，checkout 失败（clone 成功、工作树残缺）；同仓库在 Windows / WSL-mnt 侧一切正常。[实证: 2026-09-01 Mac clone 日志]

## 根因

`skills/browser-harness/SKILL.md` 与 `src/browser_harness/SKILL.md` 在 index 里是 **120000（symlink）模式**（上游 browser-use 基线 a9c3192 之前即如此）。Windows `core.symlinks=false` 下 checkout 会把它们落成普通文本文件（内容=链接目标），后续「三副本同步编辑」直接改正文，`git add` 沿用 index 的 120000 模式——结果提交出的 symlink blob 是 **19,749 字节的整份 SKILL.md 正文**。真 POSIX 端 `symlink()` 拿到超长目标名 → ENAMETOOLONG。

链条：上游把副本变成 symlink（fork 时继承）→ Windows 侧长期无感知（普通文件形态，内容恰好正确）→ fork 后每次同步编辑都在加深病灶 → 首个 POSIX clone 爆雷。

## 处理

两条转真实文件（工作树内容本就正确，只需换 index 模式）：

```powershell
git rm --cached <两条路径>
Copy-Item SKILL.md <两条路径> -Force
git add <两条路径>   # 存为 100644
```

## 预防

- 跨平台仓库**不放 symlink blob**：`git ls-files -s | rg '^120000'` 纳入发版前巡检（R003 清单）。
- Windows 上「编辑了一个你以为的普通文件」提交前，留意 `git status` 里该文件的模式；symlink 以文本形态落地后改它 = 制造本坑。
- 新平台首次 clone（尤其 POSIX）要当一次冒烟测试——本坑在 Windows/WSL 侧永远不显形。
