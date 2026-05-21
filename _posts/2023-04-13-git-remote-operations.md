---
layout: article
title: Git 远程操作原理
date: 2023-04-13 10:06:40 +0800
tags:
  - git
---


## 一、三方分支模型

Git 是分布式版本控制系统。在与远程仓库通信时，涉及三个层次的分支：

```
本地分支 (main)
    ↕  merge / rebase
远程跟踪分支 (origin/main)   ← 本地只读镜像
    ↕  fetch / push
远程分支 (远端的 main)
```

| 角色 | 存在位置 | 可直接提交 | 示例 |
|------|----------|-----------|------|
| 本地分支 | 本地仓库 | 是 | `main` |
| 远程跟踪分支 | 本地仓库 | 否（只读） | `origin/main` |
| 远程分支 | 远程仓库 | 是（通过 push） | 远端的 `main` |

## 二、远程跟踪分支的本质

**远程跟踪分支**（remote-tracking branch）是本地仓库中对远程分支状态的只读引用，格式为 `<remote>/<branch>`，如 `origin/main`。它记录的是上次与远端通信时远程分支的位置，不随本地操作变化。

远程跟踪分支无法直接修改，只能通过 `fetch`、`pull`、`push` 与远端通信后更新。若直接 `checkout` 到远程跟踪分支，Git 会进入 **detached HEAD** 状态，与 checkout 到普通 commit 的行为一致。

```bash
git checkout origin/main   # 进入 detached HEAD，不可提交
```

## 三、核心命令的工作机制

### 1、fetch

`fetch` 将远程分支的最新状态下载到本地，**只更新远程跟踪分支，不修改本地分支**。

```bash
git fetch origin          # 同步所有远程分支到对应的远程跟踪分支
git fetch origin main     # 只同步 main
```

这一设计的意义在于：开发者可以先检查远程跟踪分支的变更（`git log origin/main`、`git diff main origin/main`），再决定是否合并，而不是直接覆盖本地分支。

`fetch` 默认同步所有分支。

### 2、push

`push` 将本地分支推送到远程分支，成功后更新对应的远程跟踪分支。

```bash
git push origin main      # 推送本地 main 到远端 main，并更新 origin/main
```

`push` 默认只推送当前分支（前提是该分支已配置上游跟踪）。若本地分支在远端不存在，Git 会在远端创建该分支，同时在本地创建对应的远程跟踪分支。

`push` 与 `fetch` 在数据流向上互为逆过程：

- `fetch`：远程分支 → 远程跟踪分支
- `push`：本地分支 → 远程分支，然后更新远程跟踪分支

### 3、pull

`pull` 等价于 `fetch` 加 `merge`：

```bash
git pull origin foo
# 等价于：
git fetch origin foo
git merge origin/foo
```

`pull` 先将远程分支同步到远程跟踪分支，再将远程跟踪分支合并进当前本地分支，也可以使用 `git pull --rebase`，等价于`fetch` 加 `rebase`。

### 4、clone

`clone` 是上述机制的组合初始化操作，与 `fetch`/`pull` 的区别在于：

- `fetch`/`pull`：只更新远程跟踪分支，不新建本地跟踪分支。
- `clone`：既创建所有远程跟踪分支（如 `origin/main`），也创建对应的本地跟踪分支（如 `main`），并将本地 `main` 设置为跟踪 `origin/main`。

```bash
git clone <url>
# 结果：
# - 远程跟踪分支：origin/main, origin/dev, ...
# - 本地跟踪分支：main（跟踪 origin/main）
# - HEAD 指向 main
```

## 四、团队协作场景

### 1、小团队：无 PR 限制

所有成员均有权限直接 `push origin main`。此时依赖成员自觉，通常约定在各自的功能分支上开发，完成后推送功能分支，不直接操作 `main`。

若两人同时修改了 `main`，后推送的一方会因远端 `main` 已更新而失败：

```bash
git push origin main   # 报错：rejected, non-fast-forward
# 解决：先 pull，再 push
git pull origin main
git push origin main
```

### 2、大团队：启用 PR 规则

在仓库设置中开启 **Require pull request before merging**，禁止直接 `push origin main`。开发流程变为：

1. 在功能分支上开发并推送：`git push origin feature/foo`
2. 在网页端发起 Pull Request，指定目标分支为 `main`
3. 团队审核通过后，由平台执行合并

此模式下，即使本地 `main` 有修改，`push origin main` 也会被服务端拒绝（通过hooks脚本实现）。其优势是合并操作受平台管控，不依赖个人操作规范。
