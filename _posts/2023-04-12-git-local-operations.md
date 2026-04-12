---
layout: article
title: Git 本地操作
date: 2023-04-12 10:00:00 +0800
tags:
  - git
  - version-control
---


## 一、数据模型：commit 与 DAG

**commit 是快照**，不是差异记录。每次提交，Git 保存当前所有文件的完整状态，并生成一个唯一的 SHA-1 哈希值作为标识。

Git 的提交历史是**有向无环图（DAG, Directed Acyclic Graph）**，而非链表。图中每个节点（commit）持有指向其 parent 的引用，方向是子 → 父。

普通 commit 有一个 parent；**merge commit 有两个 parent**，这是 DAG 而非链表的直接体现。

```
A ← B ← C        # 线性历史（DAG 的特殊情况）↑
A ← B ← M        # M 是 merge commit，有两个 parent
       /
    D ←
```

---

## 二、指针系统：branch 与 HEAD

### 1、branch 是可移动指针

`branch` 本质上是一个指向某个 commit 的可移动指针，存储在 `.git/refs/heads/` 下。创建分支的开销极低，仅创建一个文件。

```bash
git branch feature   # 在当前 commit 处创建 feature 指针
```

### 2、HEAD 与 attached/detached 状态

`HEAD` 是一个特殊指针，表示当前工作区对应的快照位置。

**正常状态（attached）**：HEAD 指向一个 branch，branch 再指向 commit：

```
HEAD → main → commit C
```

**分离状态（detached HEAD）**：HEAD 直接指向某个 commit，不经过任何 branch：

```
HEAD → commit B
```

`checkout` 到一个 commit hash 时会进入 detached 状态。此时的新提交不属于任何分支，切走后若无引用将被 GC 回收。


## 三、三区模型

Git 本地维护三个层次：

| 区域 | 说明 |
|------|------|
| 仓库（Repository） | `.git` 目录，存储所有 commit 对象 |
| 暂存区（Index/Stage） | 下次 commit 将包含的内容快照 |
| 工作区（Working Tree） | 磁盘上实际的文件 |

数据流向：工作区 `git add` → 暂存区 `git commit` → 仓库。

---

## 四、指针移动操作

Git 中大量操作的本质是**移动指针**。

### 1、git checkout

移动 HEAD。

```bash
git checkout main        # HEAD 指向 main（attached）
git checkout abc123      # HEAD 直接指向该 commit（detached）
git checkout HEAD~2      # 使用相对引用，向上移动两步
```

`^` 表示第一个 parent，`~n` 表示向上 n 步。对 merge commit，`^2` 可访问第二个 parent。

### 2、git branch -f

单独移动 branch 指针，不影响 HEAD。

```bash
git branch -f main HEAD~3   # 将 main 强制移动到 HEAD 的第 3 个祖先
git branch -f main abc123   # 将 main 移动到指定 commit
```

### 3、git reset

同时移动 HEAD 和其所指向的 branch（仅在 attached 状态下有意义）。根据对工作区和暂存区的处理方式，分为三种模式：

| 模式 | 暂存区 | 工作区 |
|------|--------|--------|
| `--soft` | 保留（变更在暂存区，已 stage） | 保留 |
| `--mixed`（默认） | 清空（变更退回工作区，未 stage） | 保留 |
| `--hard` | 清空 | 清空（变更丢失，不可恢复） |

```bash
git reset --soft HEAD~1    # 撤销最近一次 commit，变更保留在暂存区
git reset --mixed HEAD~1   # 撤销最近一次 commit，变更退回工作区
git reset --hard HEAD~1    # 撤销最近一次 commit，变更完全丢弃
```


## 五、撤销操作：reset vs revert

两者都能撤销变更，但机制不同，适用场景也不同。

| | `git reset` | `git revert` |
|---|---|---|
| 原理 | 移动 branch 指针，重写历史 | 生成一个新的 commit 来抵消目标 commit 的变更 |
| 历史 | 目标 commit 之后的记录消失 | 历史完整保留 |
| 适用场景 | 变更尚未推送到远端 | 变更已推送，需要安全撤销 |

```bash
git reset HEAD~1          # 撤销最近一次 commit（本地）
git revert abc123         # 生成新 commit 抵消 abc123 的变更（已推送）
```

`reset` 重写历史，若已推送则会与远端产生分歧，需要 force push，会影响其他协作者。`revert` 不重写历史，是协作场景下的安全选择。

---

## 六、commit 复制操作

### 1、git cherry-pick

将指定 commit 的变更复制到当前 HEAD 之后，生成新的 commit（hash 不同）。

```bash
git cherry-pick abc123          # 复制单个 commit
git cherry-pick abc123 def456   # 复制多个 commit，按顺序追加
```

适用于从其他分支摘取特定修复，而不合并整个分支。

### 2、git rebase

将当前分支从**最近公共祖先（LCA）** 之后的 commit，逐一复制到目标基点之后。

```bash
git rebase main          # 将当前分支 rebase 到 main
git rebase main feature  # 将 feature 分支 rebase 到 main（等价于先 checkout feature 再 rebase main）
```

过程示意：

```
# rebase 前
main:    A ← B ← C
feature:     ↑
             D ← E

# rebase 后（D、E 被复制为 D'、E'，原 D、E 无引用后被 GC）
main:    A ← B ← C ← D' ← E'
```

rebase 同样是**生成新 commit**，而非移动原 commit。原 commit 的 hash 会改变。

### 3、git rebase -i

交互式 rebase，在复制过程中可对 commit 进行重排、合并、删除或修改提交信息。

```bash
git rebase -i HEAD~4   # 对最近 4 个 commit 进行交互式操作
```

常用指令：

| 指令 | 含义 |
|------|------|
| `pick` | 保留该 commit |
| `squash` | 合并到上一个 commit |
| `reword` | 修改提交信息 |
| `drop` | 删除该 commit |