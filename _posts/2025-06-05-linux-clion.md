---
title: Clion配置WSL工具链
tags: linux
---


##  概述
为了在windows平台下进行linux环境下的开发工作，比较方便的办法是在Clion中配置WSL工具链来进行构建。[上一篇文章](https://noonafter.cn/2024/12/31/linux-environment.html)讲到了如何在windows平台下安装WSL，这里不再赘述。本文将介绍如何在Clion中配置WSL工具链。

## WSL中配置linux环境
在安装完wsl之后，需要下载C/C++开放所需要的核心工具链，包括gcc,g++,gdb以及cmake等工具。启动wsl后，在bash中输入以下命令：

```bash
sudo apt update && sudo apt upgrade
sudo apt install build-essential gdb cmake
```

## Clion配置WSL工具链
打开clion，进入Settings > Build, Execution, Deployment > Toolchains，找到工具链，添加WSL工具链，按照下图所示完成配置，确保检测到CMake、编译器和调试器。
![clion-wsl](https://noonafter.cn/assets/images/posts/2025-06-05-linux-clion/clion-wsl.jpg)

重启Clion后，即可选择新的工具链完成项目构建。