---
layout: article
title: CLion + Docker 搭建容器化编译环境
date: 2026-02-25 10:00:00 +0800
tags:
  - docker
  - qt
  - clion
  - wsl
---


## 一、环境概述

本文记录在 Windows 11 下搭建 CLion + Docker 容器化编译环境的完整过程。

**Docker 在此场景中的定位**：Docker 在 Windows 下以 WSL2 作为后端，容器共享宿主机的 x86_64 内核，因此容器内的编译工具链架构固定为 x86_64，无法通过 Docker 本身改变目标架构。Docker 的核心价值在于**锁定工具链版本**——将指定版本的编译器、Qt 库、系统依赖打包为可复现的镜像，避免不同开发机之间的环境差异。

**目标**：在 Windows 开发机上，使用 Docker 容器提供固定版本的 Qt 5.14 + GCC 7 编译环境，通过 CLion 进行 x86_64 Linux 程序的开发和调试。

**技术栈**：
- 宿主机：Windows 11 + WSL2
- 容器管理：Docker
- 开发工具：CLion
- 基础镜像：rabits/qt:5.14-desktop
- GUI 转发：VcXsrv

## 二、Docker 环境搭建

### 1、Docker Desktop 安装

在 Windows 11 下安装 Docker Desktop，依赖 WSL2 作为后端。安装完成后，Docker 会自动配置 WSL2 集成。

### 2、数据目录迁移

Docker 默认将镜像和容器数据存储在 C 盘，可以迁移到其他盘符节省空间。

**查看默认存储位置**：
```
%LOCALAPPDATA%\Docker\wsl
```

该目录包含两个关键文件：
- `disk/docker_data.vhdx`（1.68GB）：存储所有镜像和容器
- `main/ext4.vhdx`（140MB）：Docker 本身的系统文件

**迁移步骤**：
1. 打开 Docker Desktop
2. 进入 **Settings → Resources → Advanced → Disk image location**
3. 选择目标路径（如 D 盘）
4. 点击 Apply，Docker 会自动迁移文件

**注意**：迁移后如果出现镜像识别问题，可在 Help 菜单中恢复出厂设置后重新操作。

### 3、配置镜像源

如果 `docker pull` 遇到连接超时或 EOF 错误：
```
Error response from daemon: failed to resolve reference "docker.io/library/alpine:latest"
```

可在 **Settings → Docker Engine** 中添加镜像源：

```json
{
  "registry-mirrors": [
    "https://docker.registry.cyou",
    "https://docker-cf.registry.cyou",
    "https://dockercf.jsdelivr.fyi",
    "https://docker.jsdelivr.fyi",
    "https://dockertest.jsdelivr.fyi",
    "https://mirror.aliyuncs.com",
    "https://dockerproxy.com",
    "https://mirror.baidubce.com",
    "https://docker.m.daocloud.io",
    "https://docker.nju.edu.cn",
    "https://docker.mirrors.sjtug.sjtu.edu.cn",
    "https://docker.mirrors.ustc.edu.cn",
    "https://mirror.iscas.ac.cn",
    "https://docker.rainbond.cc"
  ]
}
```

或者直接使用 VPN 访问官方源。

### 4、基础命令验证

```bash
# 拉取测试镜像
docker pull nginx

# 查看镜像列表
docker images

# 运行容器（后台模式）
docker run -d nginx

# 端口映射
docker run -p 80:80 nginx

# 目录挂载
docker run -v 宿主目录:容器目录 nginx

# 查看运行中的容器
docker ps

# 删除容器和镜像
docker rm -f <container_id>
docker rmi <image_name>
```

### 5、镜像选型：rabits/qt:5.14-desktop

选择 `rabits/qt:5.14-desktop` 镜像的原因：锁定 Qt 5.14.2 + GCC 7 的工具链版本，基于 Ubuntu 18.04（glibc 2.27），确保编译产物在 glibc 版本相近的目标系统上可运行。

**镜像架构解析**：

该镜像通过自动化脚本模拟 Qt 官方安装器的行为，实现无人值守安装。核心 Dockerfile 结构：

```dockerfile
FROM ubuntu:18.04

ARG QT_VERSION=5.14.2
ARG QT_INSTALLER_URL="https://mirrors.ocf.berkeley.edu/qt/archive/online_installers/3.2/qt-unified-linux-x64-3.2.1-2-online.run"

ENV QT_PATH=/opt/Qt \
    QT_BIN_PACKAGE=gcc_64
ENV QT_DESKTOP=${QT_PATH}/${QT_VERSION}/${QT_BIN_PACKAGE}
ENV PATH=${QT_DESKTOP}/bin:${QT_PATH}/Tools/CMake/bin:${QT_PATH}/Tools/Ninja:$PATH

# 安装基础依赖
RUN apt update && apt install -y \
    build-essential pkg-config libgl1-mesa-dev \
    libsm6 libice6 libxext6 libxrender1 libxkbcommon-x11-0 \
    libfontconfig1 libdbus-1-3

# 通过脚本静默安装 Qt
COPY extract-qt-installer.sh /tmp/qt/
RUN curl -fLs "${QT_INSTALLER_URL}" -o /tmp/qt/installer.run && \
    QT_CI_PACKAGES=qt.qt5.5142.gcc_64,qt.tools.cmake,qt.tools.ninja \
    /tmp/qt/extract-qt-installer.sh /tmp/qt/installer.run "${QT_PATH}"

# 清理冗余文件
RUN find "${QT_PATH}" -mindepth 1 -maxdepth 1 ! -name "${QT_VERSION}" ! -name "Tools" -exec rm -r '{}' \;

USER user
WORKDIR /home/user
```

**关键特性**：
- **编译工具链**：GCC 7.x（支持 C++11/14/17）
- **Qt 版本**：5.14.2（gcc_64 套件）
- **构建工具**：CMake 3.16.x、Ninja 1.10.x
- **图形依赖**：libgl1-mesa-dev（OpenGL）、libxcb 系列（X11 窗口系统）

**静默安装原理**：

镜像使用 JavaScript 脚本自动化 Qt 安装器的 GUI 操作：

```javascript
Controller.prototype.ComponentSelectionPageCallback = function() {
    var widget = gui.currentPageWidget();
    var packages = "qt.qt5.5142.gcc_64,qt.tools.cmake,qt.tools.ninja".split(",");

    widget.deselectAll();
    for (var i in packages) {
        widget.selectComponent(packages[i]);
    }
    gui.clickButton(buttons.NextButton);
}
```

通过 `QT_QPA_PLATFORM=minimal` 在无显示器环境下运行安装器，完成后删除文档、示例等冗余内容，最终镜像大小约 3-5GB。

### 6、Docker 镜像层优化

Docker 镜像采用分层存储，不同镜像可共享相同的层。但需注意：
- 层之间存在链式依赖
- 如果 layer1 改动，后续 layer2 也会失效需要重新构建

**最佳实践**：
- 将不变或少变的指令放在 Dockerfile 前面
- 频繁变动的代码放在后面
- 合理利用构建缓存加速镜像构建

## 三、CLion 配置

### 1、Toolchain 配置

CLion 通过 Docker 插件连接容器，需要手动指定工具路径。

**配置步骤**：
1. 打开 **Settings → Build, Execution, Deployment → Toolchains**
2. 添加 Docker 类型的 Toolchain
3. 选择镜像：`rabits/qt:5.14-desktop`
4. 手动填写工具路径：

| 工具 | 路径 |
|------|------|
| CMake | `/opt/Qt/Tools/CMake/bin/cmake` |
| Build Tool (Ninja) | `/opt/Qt/Tools/Ninja/ninja` |
| C Compiler | `/usr/bin/gcc` |
| C++ Compiler | `/usr/bin/g++` |
| Debugger | `/usr/bin/gdb` |

**路径验证**：

如果 CLion 提示找不到工具，可通过以下命令验证：

```bash
docker run --rm rabits/qt:5.14-desktop which cmake
docker run --rm rabits/qt:5.14-desktop which ninja
docker run --rm rabits/qt:5.14-desktop which gcc
```

**常见问题**：

1. **路径斜杠方向错误**：
   - 错误：`\opt\Qt\Tools\CMake\bin\cmake`
   - 正确：`/opt/Qt/Tools/CMake/bin/cmake`

2. **OCI runtime exec failed**：
   - 检查 Container Settings 中是否有错误的 Volume 映射
   - 确保没有覆盖容器内的 `/opt` 目录

3. **降级方案**：
   如果 `/opt/Qt` 下的工具无法调用，可使用系统自带工具：
   - CMake: `/usr/bin/cmake`
   - 仍需在 CMake Options 中指定 Qt 路径

### 2、CMake 配置

在 **Settings → Build, Execution, Deployment → CMake** 中添加：

```
-DCMAKE_PREFIX_PATH=/opt/Qt/5.14.2/gcc_64
```

该选项告诉 CMake 在哪里查找 Qt5Config.cmake，解决 `find_package(Qt5 ...)` 报错。

### 3、环境变量配置

在 **Run/Debug Configurations** 的 **Environment variables** 中添加：

```
PATH=/opt/Qt/5.14.2/gcc_64/bin:/opt/Qt/Tools/CMake/bin:/opt/Qt/Tools/Ninja:$PATH
QT_PLUGIN_PATH=/opt/Qt/5.14.2/gcc_64/plugins
QML2_IMPORT_PATH=/opt/Qt/5.14.2/gcc_64/qml
LD_LIBRARY_PATH=/opt/Qt/5.14.2/gcc_64/lib:$LD_LIBRARY_PATH
```

这些环境变量确保 Qt 运行时能找到插件和 QML 模块。

## 四、GUI 程序调试

### 1、问题背景

Docker 容器是隔离的沙盒环境，没有显卡和显示器。Qt GUI 程序默认通过 xcb 插件连接 X11 服务绘图，但容器内找不到显示设备会报错：

```
qt.qpa.xcb: could not connect to display
qt.qpa.plugin: Could not load the Qt platform plugin "xcb"
Process finished with exit code 139
```

### 2、解决方案：VcXsrv

VcXsrv 是 Windows 下的 X Server，可接收容器内程序的图形输出并显示在 Windows 桌面。

**安装与配置**：

1. 下载并安装 [VcXsrv](https://sourceforge.net/projects/vcxsrv/)

2. 启动 XLaunch，按以下配置：
   - **Display settings**：Multiple windows，Display number = 0
   - **Start clients**：Start no client
   - **Extra settings**：
     - ✅ **Disable access control**（必须勾选，否则 Docker 连接被拒绝）
     - ❌ **Native OpenGL**（必须取消勾选，见下文说明）

3. 完成后，系统托盘会显示 X 图标

**CLion 运行配置**：

在 **Run/Debug Configurations** 的 **Environment variables** 中添加：

```
DISPLAY=host.docker.internal:0.0
XDG_RUNTIME_DIR=/tmp/runtime-user
```

`host.docker.internal` 是 Docker 自动映射到 Windows 宿主机的特殊域名。

### 3、Native OpenGL 问题详解

**为什么必须取消勾选 Native OpenGL？**

当勾选 Native OpenGL 时，VcXsrv 尝试使用 Windows 的 WGL 接口直接调用显卡硬件渲染。但 Docker 容器内的 libGL 与 Windows 显卡驱动版本不匹配，导致图形上下文创建失败：

```
libGL error: No matching fbConfigs or visuals found
libGL error: failed to load driver: swrast
QGLXContext: Failed to create dummy context
```

**取消勾选后的工作机制**：

VcXsrv 切换到**间接渲染模式**（Indirect Rendering）：
1. 容器内的 Qt 将绘图指令打包成 GLX 协议信号
2. 通过网络发送给 VcXsrv
3. VcXsrv 在 Windows 层面解释并绘制

这种方式牺牲少量性能，但彻底解决驱动兼容性问题。

**渲染模式对比**：

| 模式 | 适用场景 | 优点 | 缺点 |
|------|----------|------|------|
| Native OpenGL | 本地开发 | 性能最优 | Docker 环境下驱动不兼容 |
| Indirect Rendering | Docker + VcXsrv | 兼容性好 | 性能略降 |
| Software Rendering | 远程 SSH | 无需显卡 | 性能最低 |

### 4、QML 版本兼容性

Qt 5.14 要求 QML 导入语句必须显式指定版本号：

```qml
// Qt 6 风格（错误）
import QtQuick
import QtQuick.Controls

// Qt 5.14 风格（正确）
import QtQuick 2.14
import QtQuick.Window 2.14
import QtQuick.Controls 2.14

Window {
    visible: true
    width: 640
    height: 480
    title: qsTr("Hello Qt")

    Text {
        anchors.centerIn: parent
        text: "Hello from QML"
        font.pixelSize: 20
    }
}
```

如果遗漏版本号，会报错：
```
QQmlApplicationEngine failed to load component
qrc:/main.qml: Library import requires a version
```

### 5、WSL2 替代方案

如果已安装 WSL2，可利用 Windows 11 自带的 WSLg（GUI 支持）：

**方案一：挂载 X11 Socket（尝试未成功）**

在 Docker 运行参数中添加：
```bash
-v /tmp/.X11-unix:/tmp/.X11-unix
-e DISPLAY=:0
-e WAYLAND_DISPLAY=wayland-0
-e XDG_RUNTIME_DIR=/tmp
```

**方案二：直接使用 WSL2 开发**

更推荐的方式是在 WSL2 内部开发，避免 Docker 嵌套：
1. 在 WSL2 中安装 Ubuntu 20.04
2. 安装 Qt5 开发环境
3. 使用 CLion 的 Remote Development (WSL) 模式连接
4. WSLg 自动处理 GUI 显示，无需配置 DISPLAY

这种方式编译速度更快，GUI 显示更流畅。

## 五、后续扩展

### 1、添加额外依赖库

基于 `rabits/qt:5.14-desktop` 镜像，可通过 Dockerfile 叠加项目依赖：

```dockerfile
FROM rabits/qt:5.14-desktop

USER root
RUN apt-get update && apt-get install -y \
    libboost-dev \
    libliquid-dev \
    && rm -rf /var/lib/apt/lists/*

USER user
```

### 2、针对 ARM64 目标的开发方式

Docker 容器共享宿主机的 x86_64 内核，容器内的 GCC 只能生成 x86_64 二进制，无法直接运行在 ARM64 目标机上。若需针对 ARM64（如银河麒麟 V10 + FT-2000）开发，有以下两种可行路径：

**方案一：Remote Host（推荐）**

直接 SSH 连接到目标机或同架构的 ARM64 Linux 虚拟机，使用 CLion 的 Remote Development 模式：
1. 在 **Settings → Toolchains** 中添加 SSH 类型的 Toolchain
2. 填写目标机的 IP、用户名、密钥
3. CLion 会自动将源码同步到远端，在远端编译和调试

优点：编译产物直接在目标架构上运行，无需处理交叉编译的库依赖问题。

**方案二：交叉编译（复杂度较高）**

在 x86_64 容器内安装 `gcc-aarch64-linux-gnu` 工具链，配合从目标机提取的 sysroot 进行交叉编译。该方案需要维护 sysroot 与目标机的同步，且 CLion 的调试支持有限，适合 CI/CD 场景而非日常开发。

## 六、总结

本文记录了 Windows 11 + CLion + Docker + Qt 5.14 的开发环境搭建过程，核心要点：

1. **Docker 的定位**：锁定工具链版本（Qt 5.14 + GCC 7 + Ubuntu 18.04），而非改变编译架构
2. **CLion 集成**：手动指定工具路径，配置 `CMAKE_PREFIX_PATH`
3. **GUI 调试**：使用 VcXsrv 并取消 Native OpenGL，启用间接渲染
4. **QML 兼容**：Qt 5.x 必须显式指定导入版本号
5. **ARM64 开发**：推荐使用 Remote Host 方式直连目标机，而非在 Docker 中配置交叉编译
