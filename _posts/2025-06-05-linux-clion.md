---
title: Clion配置WSL工具链
tags:
  - linux
  - clion
  - wsl
---


##  概述
为了在windows平台下进行linux环境下的开发工作，比较方便的办法是在Clion中配置WSL工具链来进行构建。[上一篇文章](./2024-12-31-linux-environment.md)讲到了如何在windows平台下安装WSL，这里不再赘述。本文将介绍如何在Clion中配置WSL工具链。

## WSL中配置linux环境
在安装完wsl之后，需要下载C/C++开放所需要的核心工具链，包括gcc,g++,gdb以及cmake等工具。启动wsl后，在bash中输入以下命令：

```bash
sudo apt update && sudo apt upgrade
sudo apt install build-essential gdb cmake
```

## WSL中安装Qt 5.14.2

Qt 5.14.2 是最后一个提供离线安装包的版本，稳定性较好，适合在 WSL 环境中进行 Qt 开发。

### 下载安装包

从 Qt 官网下载 `qt-opensource-linux-x64-5.14.2.run` 离线安装包。参考文档：[腾讯云开发者文章](https://cloud.tencent.com/developer/article/2248312)。

### 安装依赖库

直接运行安装程序会报错缺少共享库：

```bash
./qt-opensource-linux-x64-5.14.2.run
# 错误：error while loading shared libraries: libxkbcommon-x11.so.0: cannot open shared object file: No such file or directory
```

安装缺失的 X11 键盘映射库：

```bash
sudo apt update
sudo apt install libxkbcommon-x11-0
```

安装完成后即可正常运行 Qt 安装程序。

### 解决 OpenGL 头文件缺失

在 CLion 中配置 WSL 工具链后，编译 Qt 项目可能报错 `Failed to find "GL/gl.h"`。需要安装 Mesa OpenGL 开发包：

```bash
sudo apt install libgl1-mesa-dev
```

**libgl1-mesa-dev 的作用**：该包提供标准 OpenGL 编程接口的头文件和库，是 OpenGL 开发的 SDK/API。Qt 的 GUI 模块依赖这些头文件来确定系统支持的图形功能。

另外，WSLg可以自动处理 GUI 显示，无需配置 DISPLAY。注意wsl默认没有安装中文图形字体，直接显示中文可能有乱码。可以手动安装，比如：
```bash
sudo apt install fonts-noto-cjk
```

如果就希望通过x11本机显示，可以参考文章[CLion Remote Host 远程开发环境搭建](./2026-01-05-clion-remote-host-setup.md)中vcxsrv安装和配置的部分，注意wsl默认使用NAT模式，主机就是是wsl的网关。

## Clion配置WSL工具链
打开clion，进入Settings > Build, Execution, Deployment > Toolchains，找到工具链，添加WSL工具链，按照下图所示完成配置，确保检测到CMake、编译器和调试器。
![clion-wsl](https://noonafter.cn/assets/images/posts/2025-06-05-linux-clion/clion-wsl.jpg)

重启Clion后，即可选择新的工具链完成项目构建。