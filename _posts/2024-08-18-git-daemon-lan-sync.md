---
layout: article
title: 使用 Git Daemon 在局域网中进行代码同步
date: 2024-08-18 14:30:00 +0800
tags:
  - git
  - net
---


## 一、适用场景与原理

在无中央服务器（如 GitHub、内网 GitLab）的环境中，需要在局域网内多台设备间同步代码时，可使用 Git Daemon 提供轻量级的 Git 协议服务。Git Daemon 是 Git 内置的服务端程序，通过 `git://` 协议对外提供仓库访问，无需额外安装服务端软件，适合临时协作或小型团队内网使用。

`git://` 协议默认端口为 9418，传输效率高，但不提供认证和加密，仅适用于受信任的局域网环境。

## 二、服务端：启动 Git Daemon

在作为服务端的设备上执行以下命令启动 Git Daemon：

```bash
git daemon --verbose --export-all --base-path="D:\alc\c\recon"
```

### 1、参数说明

**`--base-path`**

指定仓库根目录。客户端访问时，URL 中的路径是相对于此根目录的路径。例如：

- 服务端设置 `--base-path="D:\alc\c\recon"`
- 客户端访问 `git://192.168.2.150/project`，实际访问的是 `D:\alc\c\recon\project` 目录

`base-path` 下的每个子目录都可作为独立的 Git 仓库供客户端访问。

**`--export-all`**

导出 `base-path` 下的所有仓库。默认情况下，Git Daemon 仅导出包含 `git-daemon-export-ok` 文件的仓库。使用此参数后，所有仓库均可被访问，无需逐个添加标记文件。

**`--verbose`**

输出详细日志，便于调试连接问题。

**`--enable=receive-pack`**

允许客户端推送。Git Daemon 默认禁止推送操作（出于安全考虑），仅允许 clone、fetch、pull。添加此参数后，客户端可执行 `git push`。

```bash
git daemon --verbose --export-all --base-path="D:\alc\c\recon" --enable=receive-pack
```

### 2、启动目录与 URL 路径的关系

Git Daemon 的 URL 路径解析规则取决于启动时是否指定 `--base-path`：

**情况 1：指定 `--base-path`**

```bash
# 在任意目录下启动，指定 base-path
git daemon --verbose --export-all --base-path="D:\alc\c\recon"
```

客户端 URL 中的路径相对于 `base-path`：
- `git://192.168.2.150/myproject` → 访问 `D:\alc\c\recon\myproject`
- `git://192.168.2.150/subdir/repo` → 访问 `D:\alc\c\recon\subdir\repo`

**情况 2：不指定 `--base-path`（直接在项目目录下启动）**

```bash
# 在项目目录 D:\alc\c\recon\myproject 下启动
cd D:\alc\c\recon\myproject
git daemon --verbose --export-all --enable=receive-pack
```

此时 daemon 以**当前目录**作为根。由于当前目录本身就是一个 Git 仓库（包含 `.git` 子目录），客户端需要显式指向 `.git` 来访问仓库数据：

```bash
# 客户端访问时需要加 /.git
git remote add origin git://192.168.2.150/.git
```

这里的 `.git` 是当前目录下的 `.git` 子目录，存储实际的仓库数据。URL 中的路径 `/.git` 表示根目录（启动 daemon 的目录）下的 `.git` 子目录。

**推荐做法**

为避免混淆，建议统一使用 `--base-path` 指向仓库的父目录，客户端通过仓库目录名访问：

```bash
# 服务端：在父目录启动，用 base-path 指向父目录
git daemon --verbose --export-all --base-path="D:\alc\c\recon" --enable=receive-pack

# 客户端：用仓库目录名访问
git remote add origin git://192.168.2.150/myproject
```

## 三、客户端：拉取与推送

### 1、直接使用完整地址

未配置 remote 时，可通过完整地址直接操作：

```bash
# 克隆仓库
git clone git://192.168.2.150/recon

# 拉取更新
git pull git://192.168.2.150/recon master

# 推送（需服务端开启 --enable=receive-pack）
git push git://192.168.2.150/recon master
```

URL 格式为 `git://<服务端IP>/<仓库目录名>`，其中仓库目录名是 `base-path` 下的相对路径。

### 2、配置 origin remote

频繁输入完整地址容易出错，建议配置 remote 别名：

```bash
git remote add origin git://192.168.2.150/recon
```

配置后可使用简化命令：

```bash
git pull origin master
git push origin master
```

### 3、设置 upstream 简化操作

为本地分支设置上游分支，省略分支参数：

```bash
git branch --set-upstream-to=origin/master master
```

设置后，仅需执行 `git pull` 或 `git push`，Git 会自动关联到 `origin/master`。

### 4、推送所需条件

客户端执行 `git push` 需满足以下条件：

1. 服务端启动时添加 `--enable=receive-pack` 参数
2. 客户端已配置 remote 或使用完整地址
3. 服务端仓库不是工作目录（建议使用裸仓库），否则推送可能导致服务端工作目录与仓库状态不一致

## 四、常见问题：Fetch 后看不到远程分支

### 1、问题描述

执行以下命令后，在 VS Code Git Graph 或 `git branch -r` 中看不到远程分支：

```bash
git fetch git://192.168.2.150/recon master
```

### 2、原因分析

`git fetch <URL> <分支>` 直接使用 URL 时，Git 仅将获取的数据写入 `FETCH_HEAD` 引用，不会创建 `origin/master` 等远程分支引用。这种方式是一次性的临时操作，Git 不会保存该 URL 的关联信息。

`FETCH_HEAD` 是特殊引用，指向最近一次 fetch 操作获取的分支头。可通过以下命令验证数据已下载：

```bash
git log FETCH_HEAD
```

如显示提交记录，说明数据已在本地，但未建立持久的远程分支引用。

### 3、解决方案

**步骤 1：添加 remote**

```bash
git remote add origin git://192.168.2.150/recon
```

**步骤 2：重新 fetch**

```bash
git fetch origin
```

此时 Git 会创建 `origin/master` 等远程分支引用。

**步骤 3：验证远程分支**

```bash
git branch -r
```

应显示 `origin/master`。在 VS Code Git Graph 中刷新视图，远程分支将可见。

### 4、Fetch 与 Merge 的区别

- **`git fetch`**：仅下载远程数据到本地仓库，更新 `origin/master` 引用，不改动工作目录
- **`git merge`**：将远程分支合并到当前分支，改动工作目录文件

查看远程更新但不合并时，执行 `git fetch` 后检查 `origin/master` 与本地 `master` 的差异：

```bash
git log master..origin/master
```

确认无误后再执行 `git merge origin/master`，或直接使用 `git pull`（相当于 `fetch` + `merge`）。

### 5、VS Code Git Graph 中查看远程分支

1. 打开 Git Graph 视图
2. 在左侧分支列表或图形标签中找到 `origin/master`（或 `remotes/origin/master`）
3. 本地 `master` 指向当前工作目录状态，`origin/master` 指向最近一次 fetch 获取的远程状态
4. 若远程分支不显示，点击右上角刷新图标或执行 `git fetch origin` 重新获取

## 五、总结

Git Daemon 提供的 `git://` 协议适合局域网内快速搭建代码同步服务，无需配置复杂的认证系统。关键配置点：

- 服务端使用 `--base-path` 指定仓库根目录，`--export-all` 导出所有仓库
- 允许推送需添加 `--enable=receive-pack` 参数
- 客户端建议配置 `git remote add` 建立持久的 remote 引用，避免直接 URL 操作导致的远程分支丢失
- `git fetch` 仅下载数据不修改工作目录，需配合 `git merge` 或直接使用 `git pull`

注意 Git Daemon 不提供认证和加密，仅在可信网络中使用。生产环境建议使用 SSH 协议或 HTTPS 协议的 Git 服务。
