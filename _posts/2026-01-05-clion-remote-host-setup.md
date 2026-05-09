---
layout: article
title: CLion Remote Host 远程开发环境搭建
date: 2026-01-05 10:00:00 +0800
tags:
  - clion
  - qt
  - ssh
  - cpp/dev
  - kylin
---

目标：使用Clion Remote Host连接到远程ARM主机上，进行本地编码，远端编译调试的开发模式，跑通Qt5的demo程序。

## 第 0 步（可选）：Windows ICS 网络共享

目标主机无网络时，可通过 Windows 的 **Internet 连接共享（ICS）** 借用开发机的网络。

配置步骤：

1. 控制面板 → 网络和共享中心 → 更改适配器设置
2. 右键已联网网卡（如 WLAN）→ 属性 → 共享
3. 勾选「允许其他网络用户通过此计算机的 Internet 连接来连接」
4. 下拉框选择连接目标主机的局域网网卡（如以太网）

ICS 启用后，Windows 会在局域网网卡上固定分配 `192.168.137.1`，目标主机需手动配置静态 IP：

| 项目 | 值 |
|---|---|
| IP 地址 | `192.168.137.x`（任意未占用地址） |
| 子网掩码 | `255.255.255.0` |
| 默认网关 | `192.168.137.1` |
| DNS | `192.168.137.1` 或 `8.8.8.8` |

配置完成后，目标主机即可通过开发机访问互联网，用于后续安装 `openssh-server`、`patchelf`、下载 Qt 源码等。Windows主机长时间休眠后，可能会出现共享自动关闭（显示勾选，但没生效）的情况，进入网卡属性中，关闭共享，确认后，再次打开共享，然后再次确认，即可重新生效。

## 第 1 步：安装 SSH 服务端

SSH 分为客户端（`ssh`）和服务端（`sshd`）。远程开发需要在**目标机器**上运行 `sshd`。

验证是否已安装：

```bash
systemctl status sshd
```

若显示 `not found`，安装并启动：

```bash
sudo apt install openssh-server -y
sudo systemctl start ssh
sudo systemctl enable ssh   # 开机自启
```

在开发机上首次连接时，SSH 会提示确认服务器指纹（fingerprint），输入 `yes` 后指纹写入 `~/.ssh/known_hosts`，后续不再提示：

```bash
ssh ftd2000@192.168.137.x
# The authenticity of host '...' can't be established.
# Are you sure you want to continue connecting (yes/no)? yes
```

此后可直接用 `ssh ftd2000@192.168.137.x` 登录目标主机进行操作。

## 第 2 步：在 ARM64 上安装 Qt5

### 流程概述

部分 Linux 发行版可能默认安装了部分 Qt 组件，可通过以下命令查看：

```bash
qmake --version
```

本机系统默认版本为 Qt 5.12.12。

**版本选择建议**：

| 场景 | 推荐方案 | 说明 |
|---|---|---|
| 对版本无要求 | 系统包管理器安装 | 最简单，兼容性最好 |
| 需要指定版本 | 源码编译，版本 ≤ 5.14.2 | 5.14.2 是最后一个官方提供安装包的版本（无 ARM64 版） |
| 必须使用 5.15.x | 源码编译 | 可能遇到编译问题，见下文说明 |

若对 Qt 版本无特定要求，直接使用系统包管理器安装：

```bash
sudo apt install qt5-default qtbase5-dev qtdeclarative5-dev qtquickcontrols2-5-dev qml-module-qtquick2 qml-module-qtquick-controls2 build-essential
```

**关于 Qt 5.15 在 ARM64 上的编译问题**：Qt 5.15 系列对底层 JavaScript 引擎（V4）和正则表达式引擎（Yarr）进行了激进的性能优化，导致在某些平台上出现链接错误，典型报错：

```
YarrPattern.cpp:(.text+0x9e0): undefined reference to `JSC::Yarr::newlineCreate()'
YarrPattern.cpp:(.text+0xa74): undefined reference to `JSC::Yarr::digitsCreate()'
YarrPattern.cpp:(.text+0xaf4): undefined reference to `JSC::Yarr::spacesCreate()'
```

这是 Qt 5.15.0 - 5.15.8 期间的已知问题，符号可见性规则在这些版本中变得极其复杂。Qt 5.14.2 的实现方式不同，编译更加稳定。因此若项目允许，建议选择 5.14.2 或更早版本。

本文以 5.14.2 为例进行说明（项目需要该版本以保持团队开发环境一致），Qt 官方未提供 ARM64 架构的离线安装包，在线安装器理论上支持 ARM64 但需要账号登录且网络稳定性要求较高，源码编译方式更可控。

在 ARM64 平台上编译 Qt 分三个阶段：
```bash
./configure [选项]  →  make -j<N>  →  make install
```

### 下载源码

```bash
# 从 Qt 官方镜像下载，约 500MB
wget https://download.qt.io/archive/qt/5.14/5.14.2/single/qt-everywhere-src-5.14.2.tar.xz
tar xf qt-everywhere-src-5.14.2.tar.xz
cd qt-everywhere-src-5.14.2
```

### 安装编译依赖

configure 脚本会自动检测系统环境，若缺少某些依赖则会跳过对应模块（不报错）。为确保 Qt Quick 等模块正常编译，需提前安装 OpenGL 和 X11 相关开发库：

```bash
sudo apt install build-essential libgl1-mesa-dev libfontconfig1-dev libfreetype6-dev libx11-dev libxext-dev libxfixes-dev libxi-dev libxrender-dev libxcb1-dev libx11-xcb-dev libxcb-glx0-dev
```

### configure

```bash
./configure \
  -prefix /opt/Qt5.14.2 \
  -opensource -confirm-license \
  -nomake examples \
  -nomake tests
```

- `-prefix`：安装目录，后续 CMake 的 `CMAKE_PREFIX_PATH` 指向此处
- `-nomake examples/tests`：跳过示例和测试，节省编译时间

**关于 OpenGL 参数**：OpenGL ES 2.0 是专为嵌入式设备（如手机、单片机）设计的精简版图形接口。ARM PC 运行 Linux 桌面系统时拥有完整的桌面级显卡驱动，应使用标准桌面版 OpenGL。去掉 `-opengl` 参数后，Qt 的 configure 脚本会自动检测并使用系统自带的桌面版 OpenGL 环境。

configure 结束后检查 Summary，确认所需模块（如 Qt Widgets、Qt Quick）显示为 `yes` 再继续。

### 编译与安装

```bash
make -j$(nproc)
sudo make install
```

`-j$(nproc)` 自动使用全部 CPU 核心。编译时间较长（ARM64 上通常需要数小时），期间需留意输出，并行编译偶尔因依赖竞争出错，中断后重新执行 `make -j$(nproc)` 通常可恢复。

### make clean vs make distclean

若需重新编译，注意两个命令的区别：

| 命令 | 删除内容 | 保留内容 | 适用场景 |
|---|---|---|---|
| `make clean` | `.o` 文件、可执行文件 | Makefile、configure 结果 | 增量重编译 |
| `make distclean` | 所有产物 + Makefile + 配置缓存 | 原始源码 | 完全重新配置 |

增量编译用 `make clean`，执行 `make distclean` 后必须重新跑 `./configure`。

### 验证 Qt Quick 模块

编译安装完成后，可验证 Qt Quick 模块是否正常安装：

```bash
find /opt/Qt5.14.2 -name "Qt5Quick*"
```

若有输出则表示 Qt Quick 模块已成功编译。若无输出，说明 configure 阶段因缺少依赖跳过了该模块，需补全依赖后重新编译。

## 第 3 步：Windows 安装 VcXsrv

CLion 在远程主机上运行 Qt 程序时，GUI 窗口需要一个 X Server 来渲染。Windows 上使用 **VcXsrv** 充当 X Server，将远程窗口显示到本地。

1. 下载并安装 [VcXsrv](https://sourceforge.net/projects/vcxsrv/)
2. 启动 XLaunch，配置如下：
   - Display settings：**Multiple windows**
   - Client startup：**Start no client**
   - Extra settings：勾选 **Disable access control**（允许远程连接）
3. 完成后系统托盘出现 VcXsrv 图标，表示 X Server 已运行

**注意**：Windows 防火墙可能拦截 X11 连接（端口 6000），需允许 VcXsrv 的入站规则。

## 第 4 步：CLion 配置与运行 Qt5 Demo

### 4.1 配置远程工具链

Settings → Build, Execution, Deployment → **Toolchains**

添加类型为 **Remote Host** 的工具链，填写 SSH 连接信息（主机 IP、用户名、密码或密钥）。CLion 会自动检测远程主机上的编译器和调试器。

### 4.2 配置 CMake Profile

Settings → Build, Execution, Deployment → **CMake**

添加一个 CMake Profile，将 Toolchain 指向上一步创建的远程工具链。CMake 选项中添加 Qt 路径：

```
-DCMAKE_PREFIX_PATH=/opt/Qt5.14.2
```

### 4.3 配置 Deployment（文件同步）

Settings → Build, Execution, Deployment → **Deployment**

配置本地项目目录到远程目录的映射。CLion 会通过 SFTP 将项目文件同步到远程主机。

检查 Excluded Paths，确认 `third_party` 等依赖目录未被排除。

首次配置完成后，手动上传一次：Tools → Deployment → **Upload to \<remote\>**。

这一步也可以**使用rsync进行文件同步**：

rsync 是一款Linux系统下的文件同步和传输工具。其核心特点是增量传输，即每次同步时，只传送源端与目标端有差异的部分，而不是每次都发送整个文件，因此效率非常高.

Windows 本身不原生支持 rsync，但通过 [cwRsync](https://softradar.com/cwrsync/) 可以直接使用。cwRsync 是一套打包好的工具，它把 rsync 和它所需的 Cygwin 模拟环境以及 OpenSSH 客户端集成在了一起。

下载cwRsync解压后，在Clion的 Settings -> Tools -> Rsync中填入对应的路径，然后到Settings -> Build, Execution, Deployment -> Deployment中勾选使用rsync进行同步。

### 4.4 配置 DISPLAY 环境变量

Run/Debug Configurations → 选择目标 → **Environment variables**，添加：

```
DISPLAY=<Windows 主机 IP>:0
```

例如：`DISPLAY=192.168.137.1:0`

这告诉 Qt 程序将窗口渲染到 Windows 上运行的 VcXsrv，这一步需要提前完成[第三步](#第-3-步windows-安装-vcxsrv)。

### 4.5 运行 Demo

点击 Run，CLion 将：

1. 通过 SFTP 同步修改的文件到远程主机
2. 在远程主机上执行 CMake 构建
3. 在远程主机上启动程序，程序通过 X11 协议将窗口渲染到本地 VcXsrv

若出现以下错误：

```
qt.qpa.xcb: could not connect to display
qt.qpa.plugin: Could not load the Qt platform plugin "xcb"
```

检查 `DISPLAY` 环境变量是否正确，以及 VcXsrv 是否正在运行且防火墙未拦截。

## 其他问题

### 麒麟系统安全授权弹窗

在麒麟（Kylin）系统上，运行程序时可能出现安全授权确认：

```
[麒麟安全授权认证]
检测到未认证程序试图执行，是否允许？
程序：libdevice_driver_interfaced.so    调用者：fpga_sdk_demo
路径：/tmp/.../libdevice_driver_interfaced.so
  禁止(N)  允许(Y)  本次允许(O)：
```

通过 CLion 远程调试时，弹窗出现在远程主机侧，每次运行都需手动确认，影响开发效率。以下三种方案可解决此问题。

**方案一：给文件添加白名单（推荐）**

使用 `kysec_set` 命令对指定文件或目录授信，一次性解决所有弹窗：

```bash
# 对单个文件授信
sudo kysec_set -n exectl -v verified /path/to/libdevice_driver_interfaced.so

# 对整个目录递归授信
sudo kysec_set -r -n exectl -v verified /path/to/cmake-build-debug-remote-host/tests/
```

验证是否授信成功：

```bash
kysec_get -n exectl /path/to/libdevice_driver_interfaced.so
```

**方案二：将安全模式改为 Softmode**

Softmode 下系统只记录不拦截，适合开发调试阶段：

```bash
# 查看当前状态
getstatus

# 改为软模式
sudo setstatus softmode
```

也可以只关闭执行控制，保留其他保护：

```bash
sudo setstatus -f exectl off   # 关闭执行控制
sudo setstatus -f exectl on    # 恢复执行控制
```

**方案三：图形界面关闭执行控制**

桌面环境：设置 → 安全中心 → 应用保护 → 将「应用程序执行控制」改为关闭。

此方案需要远程桌面访问，纯 SSH 环境下使用方案一或方案二。



## 参考文章

[CLion使用remote host在本地进行远程Linux程序调试](https://blog.csdn.net/weixin_43145361/article/details/107460448)


